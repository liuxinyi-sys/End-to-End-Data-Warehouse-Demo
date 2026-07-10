# YMatrix 在数仓场景中的使用说明

本文说明本 Demo 如何把 MySQL 业务库的数据同步到 YMatrix，完成 ODS、DIM、DWD、DWS、ADS 分层建模，并通过 Grafana 展示报表指标。重点不是只展示 SQL 语法，而是说明 YMatrix 在一个端到端数仓链路中承担什么角色、如何落地、哪些能力被用来解决数仓问题。

## 1. 总体链路

本项目模拟一个电商业务系统，业务数据首先保存在 MySQL 中，随后通过 Python ETL 脚本抽取、清洗并写入 YMatrix。YMatrix 作为数仓引擎，负责存储明细数据、构建维度和事实模型、预聚合指标，并对外提供 PostgreSQL 协议查询接口。Grafana 通过 PostgreSQL 数据源直连 YMatrix 的 ADS 层视图，完成可视化展示。

```text
MySQL 业务库
  users / products / orders / order_items / payments
        |
        | Python extract + pandas transform
        v
YMatrix ODS 层
  ods_users / ods_products / ods_orders / ods_order_items / ods_payments
        |
        | SQL 建模 + 维度补充
        v
YMatrix DIM + DWD 层
  dim_* 维表
  dwd_order_fact / dwd_order_detail_fact
        |
        | MATERIALIZED VIEW 预聚合
        v
YMatrix DWS 层
  dws_daily_gmv / dws_product_daily_sales / dws_user_purchase_stats
        |
        | VIEW 封装业务指标
        v
YMatrix ADS 层
  7 个报表指标视图
        |
        | PostgreSQL 数据源
        v
Grafana Dashboard
```

在这个链路中，MySQL 只承担业务库角色，Grafana 只承担展示角色。YMatrix 是中间的核心数据仓库，负责把原始业务数据转换成可分析、可聚合、可查询的指标服务层。

## 2. 业务库到 ODS：用 mxgate 高速写入原始数据

MySQL 中的业务表包括用户、商品、订单、订单明细和支付 5 类数据。ETL 脚本先通过 `sync/extract.py` 读取 MySQL，再通过 `sync/transform.py` 做类型标准化、空值处理和字段清洗，最后由 `sync/load_ods.py` 写入 YMatrix 的 ODS 层。

ODS 层的目标是保留业务库原貌，因此表结构基本对应 MySQL 原始表：

| MySQL 表 | YMatrix ODS 表 | 说明 |
| --- | --- | --- |
| `users` | `ods_users` | 用户基础信息 |
| `products` | `ods_products` | 商品基础信息 |
| `orders` | `ods_orders` | 订单主表 |
| `order_items` | `ods_order_items` | 订单明细 |
| `payments` | `ods_payments` | 支付记录 |

ODS 表使用 YMatrix 的 `MARS3` 引擎，并启用 `lz4` 压缩。以 `ods_orders` 为例，表按 `order_date` 做 RANGE 分区，按 `order_id` 分布，并按 `(order_date, order_id)` 排序。这种设计适合订单这类不断追加、经常按时间过滤和聚合的事实型数据。

数据写入使用 `mxgate --source stdin`。Python 脚本把 DataFrame 转成 CSV 流，通过 stdin 直接交给 mxgate 写入 YMatrix。相比逐行 INSERT，这种方式更适合批量装载，能更好展示 YMatrix 面向数仓批量写入的能力。

## 3. ODS 到 DIM：用 HEAP 管理小而稳定的维度

维度层负责把分析中常用的描述性信息独立出来，便于事实表关联和指标分组。本项目的维度层包括：

| 维表 | 来源 | 作用 |
| --- | --- | --- |
| `dim_date` | `generate_series` 生成 | 日期、月份、季度、周末、季节等时间属性 |
| `dim_region` | 初始化 SQL 固定写入 | 省份、城市、区域等级 |
| `dim_promotion` | 初始化 SQL 固定写入 | 双 11 促销阶段和折扣 |
| `dim_product` | 从商品数据同步 | 商品名称、品类、价格 |
| `dim_user` | 从用户数据同步 | 用户城市、状态、注册日期 |

DIM 表使用 `HEAP` 引擎。原因是维表通常数据量小、更新模式更偏随机读写，不需要像订单明细一样追求高压缩的列式存储。这个设计也体现了 YMatrix 在同一个数仓中混用 `MARS3` 和 `HEAP` 的能力：大事实表用 MARS3，小维表用 HEAP。

## 4. ODS 到 DWD：用 SQL 构建明细事实模型

DWD 层把 ODS 原始数据加工成分析友好的事实表。本项目包含两张事实表：

| DWD 表 | 粒度 | 主要用途 |
| --- | --- | --- |
| `dwd_order_fact` | 一行一笔订单 | GMV、订单量、客单价、区域、促销分析 |
| `dwd_order_detail_fact` | 一行一个订单商品明细 | 商品销量、商品收入、品类分析 |

`sync/load_dwd.py` 使用 `INSERT INTO ... SELECT ...` 在 YMatrix 内部完成建模。这样做的好处是数据已经在数仓内，不需要再拉回 Python 处理，JOIN、过滤、字段派生都由 YMatrix 执行。

`dwd_order_fact` 会从 `ods_orders` 关联 `ods_users` 和 `dim_region`，补充区域 ID，并派生运费、折扣、创建时间、支付时间、完成时间、来源渠道等字段。`dwd_order_detail_fact` 会关联订单、订单明细和促销维表，计算商品原价、折后价和来源渠道。

DWD 事实表同样使用 `MARS3`、`lz4` 压缩和按日期 RANGE 分区。它们是后续 DWS、ADS 指标的明细基础。

## 5. DWD 到 DWS：用物化视图做预聚合

DWS 层面向常用分析主题做预聚合，减少报表查询时的重复计算。本项目使用标准 `CREATE MATERIALIZED VIEW` 定义 3 个汇总视图：

| DWS 物化视图 | 聚合口径 | 服务的分析 |
| --- | --- | --- |
| `dws_daily_gmv` | 按天汇总订单量、GMV、客单价 | 每日 GMV 趋势 |
| `dws_product_daily_sales` | 按日期和商品汇总销量、收入 | 商品 Top、品类销售 |
| `dws_user_purchase_stats` | 按用户汇总订单数、消费金额 | 复购率、用户分层 |

其中 `dws_daily_gmv` 使用 `time_bucket('1 day', order_date::TIMESTAMP)` 进行时间桶聚合，展示 YMatrix 的时序分析能力。ETL 完成 DWD 装载后，会统一执行 `REFRESH MATERIALIZED VIEW`，保证 DWS 数据与本次批处理结果一致。

这里选择物化视图而不是普通视图，是因为 DWS 层是报表查询前的聚合缓存。Grafana 访问 ADS 指标时，不需要每次都从订单明细重新聚合，查询路径更短、更稳定。

## 6. DWS 到 ADS：用视图封装业务指标

ADS 层是直接面向报表和业务分析的指标层。它不再暴露底层建模细节，而是把报表需要的口径封装为 7 个视图：

| ADS 视图 | 指标含义 | 典型图表 |
| --- | --- | --- |
| `ads_daily_gmv` | 每日 GMV、订单量、客单价 | 折线图 |
| `ads_top_products` | 销售额 Top 10 商品 | 表格或条形图 |
| `ads_category_sales` | 品类销售额和占比 | 饼图 |
| `ads_user_repurchase` | 复购用户数、购买用户数、复购率 | Stat 指标 |
| `ads_user_segment` | 用户消费分层 | 饼图或柱状图 |
| `ads_gmv_by_region` | 省份维度 GMV 和订单量 | Treemap |
| `ads_promo_compare` | 大促期与日常期 GMV、订单量、客单价对比 | 柱状图 |

ADS 层使用 `CREATE VIEW`。它的职责是封装指标口径，而不是继续保存数据副本。对于 Grafana 来说，只需要查询 ADS 视图即可，不必知道底层有 ODS、DIM、DWD、DWS 多层模型。

## 7. ADS 到 Grafana：用 PostgreSQL 协议直接出图

YMatrix 兼容 PostgreSQL 协议，因此 Grafana 可以使用内置 PostgreSQL 数据源直接连接。项目中的 `grafana/datasources/ymatrix.yaml` 预置了数据源：

```yaml
name: YMatrix
type: postgres
url: ymatrix:5432
user: mxadmin
database: dw_demo
```

Dashboard JSON 保存在 `grafana/dashboards/ymatrix_dw_demo.json`。Grafana 启动后会自动加载数据源和面板，面板 SQL 直接查询 ADS 层视图。这种方式让数仓输出结果可以零代码展示，也说明 YMatrix 不只是存储层，还能直接作为 BI 查询服务。

## 8. YMatrix 特性的具体落点

本 Demo 中的 YMatrix 用法可以归纳为以下几个方面：

| YMatrix 能力 | 项目落点 | 解决的问题 |
| --- | --- | --- |
| `MARS3` 存储引擎 | ODS、DWD、`etl_log` | 存储大量事实型和日志型数据 |
| `HEAP` 存储引擎 | DIM 维表 | 管理小表和维度数据 |
| `lz4` 压缩 | ODS、DWD 表 DDL | 降低订单和明细数据存储成本 |
| `DISTRIBUTED BY` | 所有主要表 | 指定分布键，适配 MPP 数据分布 |
| `ORDER BY` | ODS、DWD 表 | 优化按时间和主键扫描的查询 |
| RANGE 分区 | `ods_orders`、DWD 事实表等 | 支持按时间范围裁剪数据 |
| `mxgate` | `sync/load_ods.py` | 高效批量写入 ODS |
| `time_bucket` | `dws_daily_gmv` | 按时间桶做时序聚合 |
| 物化视图 | DWS 层 | 报表前预聚合，减少重复计算 |
| PostgreSQL 协议 | Grafana 数据源 | 兼容 BI 工具直接查询 |
| `mysql_fdw` 检测 | `ymatrix/init/06_fdw.sql` | 展示跨库访问能力的可选入口 |

此外，项目还建立了 `ods_orders_mars_compare` 和 `ods_orders_heap` 两张对照表，用于比较 MARS3 与 HEAP 在相同订单样本上的存储差异。验证 SQL 位于 `ymatrix/verify/01_compression.sql`。

## 9. 为什么这种分层适合数仓 Demo

这个 Demo 的核心价值在于把“从业务库到报表”的全过程拆成清晰边界：

- MySQL 保留在线业务系统的原始数据。
- ODS 在 YMatrix 中承接业务数据镜像，保证数据来源可追溯。
- DIM 提供时间、区域、促销、商品、用户等分析维度。
- DWD 将订单和明细加工为标准事实表，统一后续指标口径。
- DWS 用物化视图提前聚合高频主题，提升查询稳定性。
- ADS 把最终业务指标封装成简单视图，直接服务 Grafana。

在这个结构里，YMatrix 既是存储引擎，也是建模和计算引擎。它通过 MARS3、压缩、分区、分布键、物化视图和 PostgreSQL 兼容接口，把原始业务数据逐层加工成可以被报表直接消费的指标结果。

## 10. 一键运行后的验证方式

完整链路通过以下命令运行：

```bash
docker-compose up -d
bash init_all.sh
```

运行完成后，可以从三个角度验证 YMatrix 数仓是否工作正常：

1. 检查 MySQL 源表行数是否符合预期。
2. 检查 YMatrix 中 ODS、DIM、DWD、DWS、ADS 对象是否创建并有数据。
3. 打开 Grafana `http://localhost:3000`，确认 7 个 ADS 指标对应的面板可以正常展示。

如果只想验证 YMatrix 中的指标，可直接查询 ADS 视图：

```bash
docker-compose exec ymatrix psql -U mxadmin -d dw_demo -c "SELECT * FROM ads_daily_gmv ORDER BY dt LIMIT 10;"
docker-compose exec ymatrix psql -U mxadmin -d dw_demo -c "SELECT * FROM ads_top_products;"
docker-compose exec ymatrix psql -U mxadmin -d dw_demo -c "SELECT * FROM ads_user_repurchase;"
```

这些查询能够证明：业务库数据已经被同步到 YMatrix，经过分层建模和预聚合后，最终形成了可直接服务报表的数仓指标。
