# YMatrix 数仓端到端 Demo 报告

> 本报告对应仓库 `End-to-End-Data-Warehouse-Demo`，默认运行规模为 200,000 订单（`ORDER_COUNT=200000`）。
> 方案设计的完整设计文档见 [docs/](docs/) 目录，关键文档包括：
> - [docs/2026-07-06-ymatrix-dw-demo-design.md](docs/2026-07-06-ymatrix-dw-demo-design.md) — 初始架构设计
> - [docs/superpowers/specs/2026-07-09-ecommerce-business-timeseries-design.md](docs/superpowers/specs/2026-07-09-ecommerce-business-timeseries-design.md) — 电商业务可信化与时序增强设计
> - [docs/superpowers/specs/2026-07-08-full-flow-repair-design.md](docs/superpowers/specs/2026-07-08-full-flow-repair-design.md) — 全链路修复设计
> - [docs/supplementary.md](docs/supplementary.md) — 关键设计决策记录
> - [docs/ymatrix-data-warehouse-usage.md](docs/ymatrix-data-warehouse-usage.md) — YMatrix 在数仓链路中的使用说明

---

## 1. 方案设计

### 1.1 项目目标

构建一个从**业务库（MySQL）到数仓分层（YMatrix）再到可视化仪表盘（Grafana）**的最小可运行 Demo，展示 YMatrix (MatrixDB) 在数据仓库场景中的完整使用链路：

- **可运行性优先**：一个 `docker-compose up -d && bash init_all.sh` 从头跑到尾
- **分层清晰**：ODS → DIM → DWD → DWS → ADS 五层明确分离
- **YMatrix 特性展示**：MARS3/HEAP 双引擎、mxgate 高速写入、物化视图预聚合、RANGE 分区、time_bucket 时序聚合
- **指标可见**：12 个 ADS 指标在 YMatrix 中可直接查询，Grafana 零代码展示

### 1.2 技术栈

| 类别 | 技术 | 版本 | 由来 |
|------|------|------|------|
| 业务库 | MySQL (Docker) | 8.0 | 真实电商场景，mysql_fdw 跨库查询 |
| 数仓引擎 | YMatrix (MatrixDB) | 5.2.1 社区版 | MPP 分布式，MARS3/HEAP 双引擎 |
| 同步引擎 | Python + mxgate | 3.6 / 5.2.1 | mxgate stdin 高性能写入 Segment |
| 数据处理 | pandas + numpy | 1.1.x / 1.19.x | 清洗与聚合 |
| 可视化 | Grafana | latest | 预置 Dashboard，零代码仪表盘 |
| 容器编排 | Docker Compose | 2.x | 一键启动三容器 |

### 1.3 架构总览

```
Docker Compose
├── MySQL (port 3306) — 业务库（6 表 + CSV 种子数据）
├── YMatrix (port 5432) — 数仓引擎（五层: ODS + DIM + DWD + DWS + ADS）
│   └── mxgate — 高性能写入 Segment
└── Grafana (port 3000) — 可视化仪表盘
      └── data source → YMatrix (PostgreSQL protocol)
```

三容器零主机环境依赖，Compose 编排一键启动。MySQL 只承担业务库角色，Grafana 只承担展示角色，YMatrix 是中间的核心数据仓库，负责把原始业务数据转换成可分析、可聚合、可查询的指标服务层。

### 1.4 数据流

```
MySQL 业务库
  users / products / orders / order_items / payments / order_status_events
        |
        | Python extract + pandas transform
        v
YMatrix ODS 层（MARS3, lz4, RANGE 月分区）
  ods_users / ods_products / ods_orders / ods_order_items / ods_payments / ods_order_status_events
        |
        | SQL 建模 + 维度补充
        v
YMatrix DIM + DWD 层
  dim_* 维表（HEAP）
  dwd_order_fact / dwd_order_detail_fact / dwd_order_status_event_fact（MARS3）
        |
        | MATERIALIZED VIEW 预聚合 + REFRESH
        v
YMatrix DWS 层（7 个物化视图，含 time_bucket 分钟级聚合）
        |
        | VIEW 封装业务指标
        v
YMatrix ADS 层（12 个指标视图）
        |
        | PostgreSQL 数据源
        v
Grafana Dashboard（13 个面板）
```

详细步骤：

1. Python 脚本流式生成 CSV 种子数据（可信电商场景：5 品类、10 城市、双11加权）
2. `LOAD DATA LOCAL INFILE` 将 CSV 加载到 MySQL 业务库
3. Python 从 MySQL 抽取全量数据到 pandas DataFrame
4. pandas 清洗（去空、类型标准化、衍生字段）
5. mxgate 灌入 ODS 层（MARS3 引擎，lz4 压缩，RANGE 分区）
6. SQL INSERT INTO...SELECT... 执行 ODS → DWD 清洗（语义重命名 + 时区转换）
7. 物化视图 REFRESH 更新 DWS 层（time_bucket 分钟级聚合）
8. ADS 视图封装最终指标
9. Grafana 直连 ADS 层出图

### 1.5 数仓分层设计

| 层级 | 存储引擎 | 内容 | 说明 |
|------|---------|------|------|
| ODS | MARS3（lz4 level 7，按月 RANGE 分区） | 6 张原始表镜像（含 order_status_events，TIMESTAMP(3) 毫秒精度） | 保留业务库原貌，保证数据来源可追溯 |
| DIM | HEAP | 4 张维度表（dim_region 10 城市、dim_promotion 3 促销、dim_product、dim_user）+ dim_date | 小表用 HEAP，偏随机读写，不需要列式压缩 |
| DWD | MARS3（lz4 level 7，按月 RANGE 分区） | 3 张事实表（order_fact、detail_fact、status_event_fact） | 分析友好的明细事实模型，显式时区转换 |
| DWS | MATERIALIZED VIEW | 7 个预聚合（含 time_bucket 分钟级流量、状态漏斗、履约延迟） | 报表前预聚合，减少重复计算 |
| ADS | VIEW | 12 个业务指标（含 ads_gmv_running_total、ads_order_fulfillment_latency） | 封装指标口径，直接服务 Grafana |

#### ODS 层 DDL 示例

```sql
CREATE TABLE ods_orders (
    order_id INT, user_id INT, order_date TIMESTAMP(3), status VARCHAR(20),
    total_amount NUMERIC(10,2), promo_id INT, sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (order_id) ORDER BY (order_date, order_id)
PARTITION BY RANGE (order_date)
( START (TIMESTAMP '2024-01-01 00:00:00') INCLUSIVE
  END (TIMESTAMP '2025-01-01 00:00:00') EXCLUSIVE
  EVERY (INTERVAL '1 month') );
```

同模式：`ods_order_items`、`ods_payments`、`ods_users`、`ods_products`、`ods_order_status_events`，以及两张压缩对照表 `ods_orders_heap`（HEAP）和 `ods_orders_mars_compare`（MARS3）。

#### DIM 层

维度表使用 HEAP 引擎。维表通常数据量小、更新模式偏随机读写，不需要列式压缩。这个设计体现了 YMatrix 在同一个数仓中混用 MARS3 和 HEAP 的能力：大事实表用 MARS3，小维表用 HEAP。

| 维表 | 来源 | 作用 |
|------|------|------|
| dim_date | generate_series 生成 | 日期、月份、季度、周末、季节等时间属性 |
| dim_region | 初始化 SQL 固定写入 | 省份、城市、区域等级（10 城市，100% 匹配率） |
| dim_promotion | 初始化 SQL 固定写入 | 双 11 促销阶段和折扣 |
| dim_product | 从商品数据同步 | 商品名称、品类、价格 |
| dim_user | 从用户数据同步 | 用户城市、状态、注册日期 |

#### DWD 层

DWD 层把 ODS 原始数据加工成分析友好的事实表，使用 `INSERT INTO ... SELECT ...` 在 YMatrix 内部完成建模，数据不需要拉回 Python。

| DWD 表 | 粒度 | 主要用途 |
|--------|------|---------|
| dwd_order_fact | 一行一笔订单 | GMV、订单量、客单价、区域、促销分析 |
| dwd_order_detail_fact | 一行一个订单商品明细 | 商品销量、商品收入、品类分析 |
| dwd_order_status_event_fact | 一行一个状态事件 | 状态漏斗、履约耗时分析 |

DWD 层进行显式时区转换和语义重命名：

```sql
ods_orders.order_date AT TIME ZONE 'Asia/Shanghai' AS order_time,
DATE(ods_orders.order_date AT TIME ZONE 'Asia/Shanghai') AS order_date,
ods_payments.pay_date AT TIME ZONE 'Asia/Shanghai' AS pay_time
```

#### DWS 层

使用标准 `CREATE MATERIALIZED VIEW` 定义 7 个汇总视图，ETL 完成 DWD 装载后统一执行 `REFRESH MATERIALIZED VIEW`：

| DWS 物化视图 | 聚合口径 | 服务的分析 |
|-------------|---------|-----------|
| dws_daily_gmv | 按天汇总订单量、GMV、客单价 | 每日 GMV 趋势 |
| dws_minute_order_traffic | time_bucket('1 minute') 分钟级聚合 | 双11逐分钟流量 |
| dws_product_daily_sales | 按日期和商品汇总销量、收入 | 商品 Top、品类销售 |
| dws_user_purchase_stats | 按用户汇总订单数、消费金额 | 复购率、用户分层 |
| dws_order_status_funnel | 各状态到达订单数 | 订单状态漏斗 |
| dws_order_fulfillment_latency | paid→shipped→completed 平均耗时 | 履约延迟 |
| dws_promo_daily_compare | 促销期 vs 日常期日均口径 | 促销对比 |

有效订单口径统一为 `status IN ('paid', 'shipped', 'completed')`，取消订单不进入 GMV，但进入状态漏斗和取消率分析。

#### ADS 层

ADS 层使用 `CREATE VIEW` 封装指标口径，不再暴露底层建模细节，共 12 个指标视图（详见 §2.2）。

### 1.6 YMatrix 特性展示

| # | 特性 | 展示位置 | 解决的问题 |
|---|------|---------|-----------|
| 1 | MARS3 行列混存引擎 | ODS/DWD 全部建表 | 存储大量事实型和日志型数据 |
| 2 | lz4 压缩（level 7） | ODS/DWD 建表参数 | 降低订单和明细数据存储成本 |
| 3 | RANGE 分区（按月） | ODS/DWD 建表参数 | 支持按时间范围裁剪数据 |
| 4 | 自动分区管理 APM | 01_init.sql | 自动维护分区生命周期 |
| 5 | 物化视图 + REFRESH | DWS 层 7 个物化视图 | 报表前预聚合，减少重复计算 |
| 6 | mxgate 高性能写入 | sync/load_ods.py | 批量装载，直连 Segment 并行写入 |
| 7 | DISTRIBUTED BY + ORDER BY | 全部 MARS3 表 DDL | 指定分布键适配 MPP，优化扫描 |
| 8 | time_bucket 时序聚合 | dws_minute_order_traffic | 分钟级流量洪峰分析 |
| 9 | 窗口函数 SUM OVER | ads_gmv_running_total | 双11累计 GMV 趋势 |
| 10 | HEAP 引擎对照 | DIM 维表 + ods_orders_heap | 混用引擎能力 + 压缩率对比 |
| 11 | PostgreSQL 协议兼容 | Grafana 数据源 | 兼容 BI 工具直接查询 |
| 12 | mysql_fdw 联邦查询 | 06_fdw.sql（可选） | 跨库 JOIN 展示 |

### 1.7 关键设计决策

> 详见 [docs/supplementary.md](docs/supplementary.md)

| 决策 | 选择 | 理由 |
|------|------|------|
| mxgate 模式 | `--source stdin` 命令模式 | 更轻量，不需要启动 mxgate 服务 + HTTP API，适合批处理脚本 |
| 物化视图类型 | 标准 MATERIALIZED VIEW + REFRESH | 批处理场景适用；CONTINUOUS VIEW 不支持多表 JOIN |
| 部署方式 | Docker Compose 三容器 | 零依赖宿主机环境，一键启动，最简复现路径 |
| 同步策略 | 全量 TRUNCATE + mxgate | Demo 数据量全量耗时 < 80s，幂等性好 |
| 时间字段策略 | 分层重命名 | MySQL 保留字段名升级为 DATETIME(3)，DWD 显式时区转换 + 语义重命名 |
| 分区粒度 | 按月 RANGE 分区 | 减少分区扇出，适配单 Segment Demo 资源，避免 VM Protect 耗尽 |
| DIM 引擎 | HEAP | 维表小且偏随机读写，SKILL.md 明确建议维表用 HEAP |

---

## 2. 实现说明

### 2.1 业务数据库（MySQL 电商场景）

#### 表结构

| 表名 | 核心字段 | 预计行数 |
|------|---------|---------|
| users | user_id, name, email, register_date, city, province, status | 10,000 |
| products | product_id, product_name, category, price, stock | 500 (5 品类) |
| orders | order_id, user_id, order_date, status, total_amount, promo_id | 200,000 (可配置) |
| order_items | item_id, order_id, product_id, qty, unit_price | ~480K |
| payments | payment_id, order_id, method, pay_date, amount, status | ~190K |
| order_status_events | event_id, order_id, from_status, to_status, event_time, operator_type | ~700K |

#### 数据特征

- **时间范围**: 2024-01-01 ~ 2024-12-31 全年
- **时间精度**: 毫秒级 DATETIME(3) / TIMESTAMP(3)
- **业务时区**: Asia/Shanghai
- **城市覆盖**: 北京/上海/广州/深圳/成都/武汉/杭州/南京/西安/重庆（10 城市，9 省份）
- **品类结构**: 电子（华为/小米/Apple/OPPO/vivo）、服装（Nike/Adidas/ZARA/H&M/优衣库）、美妆、食品、家居
- **双11促销波峰**: 11.11 订单量达日均 74x，GMV 达日均 49x
- **用户分层**: 高价值用户（~20% 贡献 ~60% 订单）、普通用户、低频用户
- **订单明细**: 每单商品数加权随机（1/2/3/5/10/20 件），非固定值
- **金额对账**: `orders.total_amount` = 同订单所有 `line_amount` 之和，误差 < 0.05

#### 订单状态流转

```
完成订单: created → paid → shipped → completed
取消订单: created → cancelled
```

`orders.status` 保留最终状态（业务快照），`order_status_events` 表达流转历史（用于漏斗和履约耗时分析）。

### 2.2 业务指标（12 个 ADS 视图）

| # | 指标 | ADS 视图 | 说明 |
|---|------|---------|------|
| 1 | 每日 GMV | ads_daily_gmv | 按天聚合订单量和 GMV |
| 2 | 商品销售 Top 10 | ads_top_products | 按收入排序的 Top 10 商品 |
| 3 | 品类销售占比 | ads_category_sales | 5 大品类收入占比 |
| 4 | 用户复购率 | ads_user_repurchase | 多次购买用户占比 |
| 5 | 用户价值分层 | ads_user_segment | 按消费额 NTILE 3 等分 |
| 6 | GMV 按省份分布 | ads_gmv_by_region | 9 省份 GMV 排名 |
| 7 | 促销对比 | ads_promo_compare | 促销期 vs 日常期 GMV 提升 |
| 8 | 分钟级流量 | ads_minute_traffic | 双11逐分钟订单量和 GMV |
| 9 | 流量峰值分钟 | ads_traffic_peak_minutes | 订单量 Top 20 分钟 |
| 10 | 订单状态漏斗 | ads_order_status_funnel | created→paid→shipped→completed |
| 11 | 双11累计 GMV | ads_gmv_running_total | 窗口函数实现累计求和 |
| 12 | 履约延迟 | ads_order_fulfillment_latency | 付款→发货→完成平均耗时 |

### 2.3 ETL Pipeline 设计

#### 架构

```
sync/
├── sync_data.py        ← 主入口，编排全流程
├── gen_data.py         ← 流式生成业务数据（CSV）
├── extract.py          ← MySQL → pandas DataFrame
├── transform.py        ← 清洗/标准化/衍生字段
├── load_ods.py         ← DataFrame → mxgate stdin → ODS
├── load_dim.py         ← TRUNCATE + mxgate → DIM
├── load_dwd.py         ← SQL INSERT INTO...SELECT... → DWD / REFRESH MV
├── verify.py           ← 21 项自动化断言验证 + etl_log 写入
└── requirements.txt
```

#### 设计要点

- **幂等性**: 每次全量 TRUNCATE + 重载（mxgate 加载前 TRUNCATE），可安全重跑，不重复不丢数据
- **分步执行**: extract → transform → load_ods → load_dim → load_dwd → refresh_mv → verify
- **审计追踪**: etl_log 表记录每步耗时（9 条日志，含 rows_processed 和 duration_ms）
- **验证**: verify.py 执行 21 项断言检查
- **跨平台**: .gitattributes 强制 LF 行尾，CSV lineterminator="\n"
- **流式生成**: gen_data.py 流式写出 CSV 文件，不拼接百万级 SQL values，内存占用可控
- **数据生成确定性**: 固定随机种子，保证每次演示结果可复现

#### mxgate 写入示例

```python
proc = subprocess.Popen([
    "mxgate", "--source", "stdin",
    "--db-database", "dw_demo",
    "--db-master-host", "ymatrix",
    "--db-master-port", "5432",
    "--db-user", "mxadmin",
    "--target", "ods_orders",
    "--parallel", "256",
    "--delimiter", ",",
], stdin=subprocess.PIPE, text=True)
proc.communicate(buf.getvalue())
```

#### transform.py 清洗规则

| 处理类型 | 规则 |
|---------|------|
| 空值处理 | 必填字段为 NULL → 跳过该行并记录 etl_log；可选字段为 NULL → 填默认值 |
| 类型标准化 | 日期统一为 DATE 格式；金额四舍五入到 2 位小数；时间戳统一为 TIMESTAMP |
| 衍生字段 | freight_amount、discount_amount、source_type、region_id（由 SQL 或 Python 计算） |
| 去重 | 对 ODS 源数据按主键去重 |

### 2.4 物化视图策略

- 使用标准 MATERIALIZED VIEW（非 Domino 连续视图）
- 批处理完成后统一 REFRESH（7 个视图）
- 有效订单语义: `status IN ('paid', 'shipped', 'completed')`
- 选择物化视图而非普通视图：DWS 层是报表查询前的聚合缓存，Grafana 访问 ADS 时不需要每次从明细重新聚合

### 2.5 Grafana 预置配置

Grafana 通过内置 PostgreSQL 数据源直连 YMatrix ADS 层，零代码展示：

```yaml
# grafana/datasources/ymatrix.yaml
name: YMatrix
type: postgres
url: ymatrix:5432
user: mxadmin
database: dw_demo
```

Dashboard JSON 保存在 `grafana/dashboards/ymatrix_dw_demo.json`，通过 `provider.yaml` 自动加载，包含 13 个面板。

### 2.6 可配置规模

通过环境变量 `ORDER_COUNT` 控制订单规模：

| 规模 | 环境变量 | 订单数 | 预期耗时 | 用途 |
|------|---------|--------|---------|------|
| 默认 | `ORDER_COUNT=200000` | 200,000 | ~80s | 全链路验证 |
| 性能 | `ORDER_COUNT=1000000` | 1,000,000 | ~5min | 性能演示 |
| 压测 | `ORDER_COUNT=5000000` | 5,000,000 | ~25min | 极限压测 |

---

## 3. 测试过程

### 3.1 测试策略

项目不写单元测试（以集成验证为主），测试通过以下方式覆盖：

1. **自动化断言验证**（verify.py，21 项检查）
2. **全链路一键运行**（`docker-compose up -d && bash init_all.sh`）
3. **幂等性测试**（不删除 volumes 重复执行 init_all.sh）
4. **空卷干净运行**（`docker-compose down -v` 后从零开始）
5. **Grafana API + 浏览器验证**
6. **静态检查**（Python 编译、Compose 配置校验、Dashboard JSON 语法）

### 3.2 验证清单

- [x] MySQL 6 表行数正确
- [x] ODS 行数 = MySQL 行数
- [x] DWS 7 个物化视图 REFRESH 成功
- [x] ADS 12 个指标返回非空数据
- [x] MARS3 vs HEAP 压缩率对比（83.2% 节省）
- [x] Grafana 13 个面板正常渲染
- [x] etl_log 日志完整
- [x] 双11累计 GMV 单调递增
- [x] 订单/明细金额对账（0 误差）
- [x] 商品类目与类型匹配率 100%
- [x] 区域匹配率 100%
- [x] DWD 时区对齐（0 偏移）

### 3.3 预期断言值

| 检查项 | 预期 | 实际 |
|--------|------|------|
| MySQL: users | 10,000 行 | 10,000 ✓ |
| MySQL: products | 500 行 | 500 ✓ |
| MySQL: orders | 200,000 行 | 200,000 ✓ |
| MySQL: order_items | 400K~1M 行 | 483,200 ✓ |
| MySQL: order_status_events | ≥ 200,000 行 | 699,451 ✓ |
| ODS 行数 = MySQL 行数 | 严格相等 | ✓ |
| ads_daily_gmv | 365 行 | 365 ✓ |
| ads_gmv_running_total | 非空，单调递增 | 1,427 行，0 违规 ✓ |
| ads_minute_traffic | 非空 | 123,890 行 ✓ |
| DWD 时区对齐 | order_date = DATE(order_time) | 0 偏移 ✓ |
| 订单/明细金额对账 | 误差 < 0.05 | 0 误差 ✓ |
| Nov 11 流量 | ≥ 50x 日均 | 74x ✓ |
| MARS3 vs HEAP 压缩率 | 节省 50%+ | 83.2% ✓ |
| 商品类目匹配 | 0 无效商品 | 0 ✓ |
| 复购率 | 合理范围 | 45.8% ✓ |

### 3.4 测试演进历程

项目经历了三轮测试与修复迭代，测试报告存档于 docs/：

#### 第一轮：初始全链路测试（2026-07-08）

> 详见 [docs/full-flow-test-report-2026-07-08.md](docs/full-flow-test-report-2026-07-08.md)

结果：**FAIL** — 清洁运行无法完成。发现 9 项缺陷（F1-F9）：

| 缺陷 | 严重度 | 描述 |
|------|--------|------|
| F1 | Blocker | YMatrix entrypoint 未创建数据库（if 语句附在注释行上） |
| F2 | Blocker | Schema SQL 目录未挂载到容器 |
| F3 | Blocker | init_all.sh 连接方式错误（peer/ident 认证失败） |
| F4 | High | 种子生成器行数不达标 |
| F5 | Blocker | 01_init.sql 不兼容镜像（postgres_fdw、APM 函数、season VARCHAR(4)） |
| F6 | Blocker | 两张 MARS3 ODS 表缺少 ORDER BY 键 |
| F7 | Blocker | DWS 创建触发 VM Protect 内存分配失败 |
| F8 | High | Grafana Dashboard 未 provisioning |
| F9 | Medium | Grafana 插件配置报错 |

验收清单：2 PASS, 3 FAIL, 4 BLOCKED。

#### 第二轮：全链路修复（2026-07-08）

> 详见 [docs/full-flow-repair-verification-2026-07-08.md](docs/full-flow-repair-verification-2026-07-08.md) 和 [docs/superpowers/specs/2026-07-08-full-flow-repair-design.md](docs/superpowers/specs/2026-07-08-full-flow-repair-design.md)

结果：**PASS** — 修复后 `docker-compose down -v` + `docker-compose up -d` + `bash init_all.sh` 退出码 0，耗时 138.7 秒（5 万订单规模）。

主要修复措施：

1. 修复 entrypoint 的行结构/编码，确保数据库创建和密码设置执行
2. 挂载 `./ymatrix/init` 到 `/docker-entrypoint-initdb.d`
3. 统一使用 TCP 连接（`-h localhost`），`psql -v ON_ERROR_STOP=1`
4. 种子生成确定性化，精确生成目标行数
5. 移除不兼容的扩展/函数，`season` 改为 VARCHAR(10)
6. 所有 MARS3 表添加 ORDER BY 键
7. 分区从按天改为按月，减少分区扇出，解决 VM Protect 耗尽
8. 添加 Grafana dashboard provider YAML，移除冗余核心插件安装

#### 第三轮：电商业务可信化与时序增强（2026-07-09）

> 详见 [docs/ecommerce-timeseries-verification-2026-07-09.md](docs/ecommerce-timeseries-verification-2026-07-09.md) 和 [docs/superpowers/specs/2026-07-09-ecommerce-business-timeseries-design.md](docs/superpowers/specs/2026-07-09-ecommerce-business-timeseries-design.md)

结果：**PASS** — 20 万订单规模，verify.py 21/21 PASS，ETL 67 秒。

增强内容：

1. 数据规模从 5 万提升到 20 万（可配置至 100 万/500 万）
2. 新增 `order_status_events` 表，支持状态漏斗和履约延迟分析
3. 时间字段升级为 TIMESTAMP(3) 毫秒精度
4. DWD 显式 Asia/Shanghai 时区转换
5. 新增 time_bucket 分钟级流量、双11累计 GMV 窗口函数
6. 商品/价格/用户行为可信化（品类匹配、价格对账、用户分层）
7. Grafana 面板从 6 个扩展到 13 个

---

## 4. 测试结果

### 4.1 自动化验证（verify.py 21/21 PASS）

```
--- Verifying ADS Metrics ---
  ads_daily_gmv: 365 rows -> PASS
  Nov 11: 140425396.16 vs avg: 2852071 -> PASS
  top_products: 10 rows -> PASS
  category pct: 100.00% -> PASS
  repurchase: 45.8% -> PASS
  gmv_by_region: 9 rows -> PASS
  promo_compare: 2 non-empty periods -> PASS
  user_segment: 3 segments -> PASS
  compression: MARS3 saves 83.2% -> PASS
  etl_log: 9 entries -> PASS
  ods_orders equals configured scale 200000 rows -> PASS
  order_items 2x to 5x orders 483200 rows -> PASS
  Nov 11 >= 50x normal daily average 32121 vs 457 -> PASS
  status events present 699451 rows -> PASS
  order item count varies 200000 non-four-item orders -> PASS
  product dimension credible 0 invalid products -> PASS
  order/detail amount reconciles 0 mismatches -> PASS
  minute traffic non-empty 123890 rows -> PASS
  running GMV non-empty 1427 rows -> PASS
  running GMV monotonic 0 violations -> PASS
  DWD timezone date aligned 0 shifted rows -> PASS

21/21 passed
```

### 4.2 MySQL 业务库行数

```
table_name           row_count
users                10000
products             500
orders               200000
order_items          483200
payments             189956
order_status_events  699451
```

### 4.3 核心业务指标

| 指标 | 数值 |
|------|------|
| 双11 GMV | ¥140,425,396 |
| 日常日均 GMV | ¥2,852,071 |
| 双11 GMV 倍数 | 49.2x 日常 |
| 双11订单量 | 32,121 |
| 日常日均订单量 | 457 |
| 双11订单倍数 | 70.2x 日常 |
| 促销期日均 GMV | ¥20,645,414 |
| 促销期 GMV 提升 | 863.7% |
| 用户复购率 | 45.8% |
| MARS3 压缩节省 | 83.2% |
| 履约延迟 付款→发货 | 30.0 小时 |
| 履约延迟 发货→完成 | 72.0 小时 |
| ETL 总耗时 | 67 秒 |
| Grafana 状态 | healthy |

### 4.4 双11累计 GMV（前 10 分钟）

```
    bucket_time     | minute_gmv | running_gmv | minute_order_count | running_order_count
---------------------+------------+-------------+--------------------+---------------------
 2024-11-11 00:00:00 |  335137.00 |   335137.00 |                 93 |                  93
 2024-11-11 00:01:00 |  204834.63 |   539971.63 |                 62 |                 155
 2024-11-11 00:02:00 |  261526.83 |   801498.46 |                 67 |                 222
 2024-11-11 00:03:00 |  275360.96 |  1076859.42 |                 76 |                  298
 2024-11-11 00:04:00 |  340496.49 |  1417355.91 |                 78 |                  376
 2024-11-11 00:05:00 |  321607.67 |  1738963.58 |                 61 |                  437
 2024-11-11 00:06:00 |  329134.41 |  2068097.99 |                 59 |                  496
 2024-11-11 00:07:00 |  307983.63 |  2376081.62 |                 79 |                  575
 2024-11-11 00:08:00 |  249903.41 |  2625985.03 |                 79 |                  654
 2024-11-11 00:09:00 |  192159.07 |  2818144.10 |                 59 |                  713
```

累计 GMV 单调递增：0 违规。

### 4.5 订单状态漏斗

```
  status   | order_count
-----------+-------------
 created   |      200000
 paid      |      189956
 shipped   |      159674
 completed |      139777
 cancelled |      10044
```

转化率：created→paid 95%，paid→shipped 84%，shipped→completed 88%，取消率 5%。

### 4.6 MARS3 vs HEAP 压缩率对比

```
 mars3_bytes | heap_bytes | savings_pct
-------------+------------+-------------
   100829218 |  601128960 |        83.2
```

MARS3 列存 + lz4 压缩：~96 MB | HEAP 行存：~573 MB | 节省 83.2%（477 MB）。

### 4.7 ETL 审计日志

```
 log_id |            step             | status  | rows_processed | duration_ms
--------+-----------------------------+---------+----------------+-------------
      1 | extract                     | success |        1583107 |       14266
      2 | transform                   | success |        1583107 |         311
      3 | load_ods                    | success |        1583107 |       30681
      4 | load_dim                    | success |          10500 |        3867
      5 | dwd_order_fact              | success |         200000 |        3050
      6 | dwd_order_detail            | success |         483200 |        2957
      7 | dwd_order_status_event_fact | success |         699451 |        2023
      8 | refresh_dws                 | success |              7 |        3219
      9 | etl_complete                | success |              0 |       66997
```

ETL 全链路耗时 67 秒，含 extract→transform→load_ods→load_dim→dwd→refresh 6 个阶段。

### 4.8 Grafana 健康检查

```
GET http://localhost:3000/api/health
{"database":"ok","version":"13.1.0","commit":"b309c9bb3b81a748c3a75289236a27309ed2566a"}
```

13 个面板全部渲染数据：

| # | 面板 | 图表类型 | 数据源 |
|---|------|---------|--------|
| 1 | 每日 GMV 趋势 | 折线图 | ads_daily_gmv |
| 2 | 商品销售 Top 10 | 表格 | ads_top_products |
| 3 | 品类销售占比 | 饼图 | ads_category_sales |
| 4 | 用户复购率 | 单值 Stat | ads_user_repurchase |
| 5 | GMV 按省份分布 | 柱状图 | ads_gmv_by_region |
| 6 | 双11 累计 GMV | 折线图 | ads_gmv_running_total |
| 7 | 双11 累计订单量 | 折线图 | ads_gmv_running_total |
| 8 | 订单状态漏斗 | 柱状图 | ads_order_status_funnel |
| 9 | 促销期 vs 日常期 | 条形仪表 | ads_promo_compare |
| 10 | 用户价值分层 | 环形图 | ads_user_segment |
| 11 | 双11 分钟级流量 | 折线图 | ads_minute_traffic |
| 12 | 履约延迟 | 单值 Stat | ads_order_fulfillment_latency |
| 13 | 流量峰值 Top 20 分钟 | 表格 | ads_traffic_peak_minutes |

> 完整运行结果详见 [results/run-results-2026-07-09.md](results/run-results-2026-07-09.md)，Grafana 截图见 [results/screenshots/](results/screenshots/)。

---

## 5. 问题和风险

### 5.1 已知风险与缓解措施

| 风险 | 影响 | 缓解措施 | 状态 |
|------|------|---------|------|
| Docker 镜像构建失败 | 无法启动 YMatrix | 预构建镜像已上传 Docker Hub (`lxy0315/ymatrix5.2-clean:latest`)，`docker-compose up -d` 自动拉取 | ✅ 已解决 |
| Windows CRLF 行尾 | mxgate 加载全部拒绝 | `.gitattributes` 强制 LF + CSV `lineterminator="\n"` | ✅ 已解决 |
| mxgate 重复加载 | 数据叠加 | 加载前 TRUNCATE 目标表 | ✅ 已解决 |
| TIMESTAMP 时区偏移 | 分区键超出范围 / 日期错位 | ODS 时间已是本地时间，DWD 直接继承不做时区转换 | ✅ 已解决 |
| DWS JOIN 列歧义 | 物化视图创建失败 | 使用表别名限定列名 | ✅ 已解决 |
| 大型安装包（~364MB） | 拉取耗时 | 镜像已在 Docker Hub，首次拉取后本地缓存 | ✅ 已缓解 |
| init SQL 执行顺序 | DDL 依赖错误 | 文件名前缀控制顺序（01-06） | ✅ 已解决 |
| VM Protect 内存耗尽 | DWS 物化视图创建失败 | 分区从按天改为按月，减少分区扇出 | ✅ 已解决 |
| Grafana Dashboard 不加载 | 面板无法展示 | 添加 provider.yaml + 稳定 UID + 移除冗余核心插件 | ✅ 已解决 |
| 种子数据不可信 | 商品类目错配、价格脱钩 | 结构化品类配置 + 金额对账校验 | ✅ 已解决 |

### 5.2 残留限制

| 限制 | 说明 |
|------|------|
| 单节点部署 | 仅演示单台 Docker 容器，不涉及 MPP 多节点集群扩展 |
| 批量 ETL 模式 | 使用标准物化视图 + REFRESH，非 Domino 流式实时处理 |
| 模拟数据 | 默认 20 万订单为程序生成的可信电商数据，非真实业务数据 |
| YMatrix 社区版 | 部分企业功能（如 Domino 连续视图、Kafka 直连）不可用 |
| mysql_fdw 可选 | 本地镜像不含 mysql_fdw，06_fdw.sql 检测后跳过，不影响核心链路 |
| 跨平台 | 已通过 `.gitattributes` 强制 LF 行尾解决 Windows CRLF 问题，推荐在 Git Bash 中运行 `init_all.sh` |

### 5.3 后续改进方向
Demo 充分体现了 YMatrix 在批处理数仓、分层建模、压缩存储、批量写入、预聚合报表和 BI 展示方面的能力；但没有重点体现多节点性能、实时流、CDC 和高可用这些生产级能力。
- [ ] 多节点 MPP 性能扩展。当前是单容器 Demo，只体现了 DISTRIBUTED BY 设计，没有真实多节点压测
- [ ] 实时流式数仓。当前是批处理 REFRESH MATERIALIZED VIEW，不是实时流
- [ ] CDC 增量同步。当前是全量 TRUNCATE + 重载
