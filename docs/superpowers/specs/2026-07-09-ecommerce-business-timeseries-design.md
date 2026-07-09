# 电商业务可信化与 YMatrix 时序分析增强设计

## 背景

当前 Demo 已经能跑通 MySQL -> YMatrix -> Grafana 的端到端链路，并覆盖 ODS、DIM、DWD、DWS、ADS 分层、mxgate 写入、MARS3/HEAP、物化视图和 Grafana 展示。但业务数据仍偏随机：商品品类与商品类型可能错配，订单明细价格与商品主数据价格脱钩，订单日期分布较均匀，订单明细数固定，订单状态只有最终快照。

本设计目标是把 Demo 从“工程链路可运行”提升到“电商业务场景可信，并能突出 YMatrix 时序分析能力”。

## 目标

1. 构造可信的最小电商业务数据库场景，保留现有五张业务表并新增订单状态事件表。
2. 修正商品、价格、用户行为、促销周期和指标口径，使指标可解释、可对账。
3. 将核心时间字段提升到 `TIMESTAMP(3)`，支持秒级/毫秒级事件分析。
4. 增强 YMatrix 展示点：`time_bucket` 分钟级聚合、滑动窗口、状态流转、促销流量洪峰。
5. 保持一键运行方式：`docker-compose up -d && bash init_all.sh`。

## 非目标

1. 不引入 Kafka、Flink、Spark 等外部实时链路。
2. 不扩展成完整电商系统，不新增库存扣减、退款售后、会员权益、优惠券核销等复杂模块。
3. 不改变当前三容器部署形态。
4. 不牺牲最小可演示性来追求真实生产系统复杂度。

## 方案选择

采用“轻量业务可信化 + YMatrix 时序分析增强”方案。

对比其他方案：

1. 最小修复：只修商品错配和取消订单口径，改动小，但无法展示 YMatrix 核心时序能力。
2. 轻量增强：修业务数据和指标口径，新增订单状态事件流，并加入分钟级流量分析。推荐采用。
3. 深度仿真：加入退款、库存、会员、营销投放等真实电商系统模块，表达力强但超出 Demo 范围。

## 业务数据库设计

### 保留表

继续保留五张业务表：

1. `users`
2. `products`
3. `orders`
4. `order_items`
5. `payments`

### 新增表

新增 `order_status_events`，表达订单生命周期。

字段：

```sql
event_id BIGINT
order_id INT
from_status VARCHAR(20)
to_status VARCHAR(20)
event_time TIMESTAMP(3)
operator_type VARCHAR(20)
```

典型事件链：

```text
created -> paid -> shipped -> completed
created -> cancelled
```

该表是展示 YMatrix 时序分析能力的核心业务事件表。

## 时间字段设计

核心时间字段统一使用 `TIMESTAMP(3)`：

1. `orders.order_date` 改为 `orders.order_time TIMESTAMP(3)`。
2. `payments.pay_date` 改为 `payments.pay_time TIMESTAMP(3)`。
3. ODS/DWD 同步保留 `order_time`、`pay_time`、`event_time`。
4. DWD 中派生 `order_date DATE` 作为分区字段，继续支持 RANGE 分区。

这样同时满足：

1. 分区裁剪仍可按日/月执行。
2. 分钟级、秒级、毫秒级查询可以基于 `TIMESTAMP(3)` 执行。
3. Grafana 可以展示促销流量峰值曲线。

## 商品与价格生成设计

商品生成改为结构化配置：

```text
电子: 华为/小米/Apple/OPPO/vivo -> 手机/平板/笔记本/耳机/充电器 -> 199 到 9999
服装: Nike/Adidas/ZARA/H&M/优衣库 -> T恤/牛仔裤/外套/运动鞋/帽子 -> 49 到 1299
美妆: 雅诗兰黛/SK-II/兰蔻/欧莱雅/资生堂 -> 精华/面霜/眼霜/面膜/洗面奶 -> 69 到 1999
食品: 三只松鼠/良品铺子/百草味/来伊份/洽洽 -> 坚果/肉干/果脯/饼干/巧克力 -> 9.9 到 299
家居: 宜家/MUJI/网易严选/小米有品/名创优品 -> 台灯/收纳盒/毛巾/拖鞋/靠垫 -> 19.9 到 999
```

规则：

1. 商品类型必须来自所属品类。
2. 商品价格必须落在所属品类价格区间。
3. `order_items.unit_price` 来自 `products.price`，允许 0.95 到 1.05 的成交波动。
4. 促销折扣作用在 DWD 成交价 `final_price`，不破坏商品主数据价格。

## 用户行为生成设计

用户按购买能力分层：

1. 高价值用户：约 20%，贡献约 60% 订单。
2. 普通用户：约 50%，贡献约 35% 订单。
3. 低频用户：约 30%，贡献约 5% 订单。

订单用户选择不再完全均匀随机，而是按上述分层权重抽样。目标是让复购率、用户分层和 Top 用户表现更接近真实业务。

## 订单时间与流量洪峰设计

订单日期采用权重分布：

```text
平日: 1
周末: 1.5
双 11 预热期 Day 306-315: 5
双 11 当天 Day 316: 100
双 11 返场期 Day 317-319: 10
```

双 11 当天订单量应至少达到平日均值 50 倍。

日内时间也采用权重分布：

1. 凌晨普通时段低权重。
2. 午休和晚间较高权重。
3. 双 11 当天 00:00-01:00、20:00-23:00 设为高峰时段。

时间戳使用秒级或毫秒级随机偏移，写入 `TIMESTAMP(3)`。

## 订单明细数量设计

每单商品数使用加权随机：

```python
random.choices([1, 2, 3, 5, 10, 20], weights=[45, 30, 12, 8, 4, 1])[0]
```

目标：

1. 大多数订单为 1 到 3 件。
2. 少数订单为 5 件以上。
3. 总明细规模保持在约 200,000 行，继续支撑压缩和聚合演示。

## 订单状态流转设计

订单生成时先决定最终结果，再生成状态事件。

完成订单：

```text
created: 下单时间
paid: 下单后 0 到 10 分钟
shipped: 支付后 0.5 到 2 天
completed: 发货后 1 到 5 天
```

取消订单：

```text
created: 下单时间
cancelled: 下单后 1 到 60 分钟
```

`orders.status` 保留最终状态，用于业务快照；`order_status_events` 表达流转历史，用于漏斗和履约耗时分析。

## 数仓分层调整

### ODS

新增：

1. `ods_order_status_events`

修改：

1. `ods_orders` 使用 `order_time TIMESTAMP(3)`。
2. `ods_payments` 使用 `pay_time TIMESTAMP(3)`。

### DIM

补齐 `dim_region`，覆盖用户生成使用的全部城市，区域匹配率必须达到 100%。

### DWD

`dwd_order_fact` 同时保留：

1. `order_time TIMESTAMP(3)`：时序分析字段。
2. `order_date DATE`：分区字段。

新增或调整：

1. `dwd_order_detail_fact.final_price` 必须由商品价格和促销折扣推导。
2. `dwd_order_status_event_fact` 用于状态事件分析。
3. 有效订单口径统一为 `status IN ('paid', 'shipped', 'completed')`。

### DWS

新增物化视图：

1. `dws_minute_order_traffic`
   - 使用 `time_bucket('1 minute', order_time)`。
   - 输出分钟级订单数、GMV、客单价。
2. `dws_order_status_funnel`
   - 基于状态事件统计各状态到达订单数。
3. `dws_order_fulfillment_latency`
   - 统计 paid -> shipped、shipped -> completed 的平均耗时。
4. `dws_promo_daily_compare`
   - 以日均口径比较促销期和日常期。

保留并修正：

1. `dws_daily_gmv`
2. `dws_product_daily_sales`
3. `dws_user_purchase_stats`

### ADS

新增或调整视图：

1. `ads_minute_traffic`
2. `ads_traffic_peak_minutes`
3. `ads_order_status_funnel`
4. `ads_order_fulfillment_latency`
5. `ads_promo_compare`

`ads_promo_compare` 输出：

```text
period
days
order_cnt
gmv
daily_avg_gmv
avg_order_value
uplift_pct
```

## 指标口径

GMV、品类销售、Top 商品、区域 GMV、复购率统一只统计有效订单：

```sql
status IN ('paid', 'shipped', 'completed')
```

取消订单不进入 GMV，但进入状态漏斗和取消率分析。

区域 GMV 必须覆盖所有有效订单，不允许因为维表缺失导致订单丢失。

商品和品类 GMV 以 DWD 明细事实表为准，并能与订单事实表 GMV 对账。

## Grafana 展示调整

保留现有面板，并增加或替换为更能体现 YMatrix 能力的面板：

1. 每日 GMV 趋势。
2. 分钟级订单流量洪峰。
3. 双 11 峰值分钟 Top N。
4. 商品销售 Top 10。
5. 品类销售占比。
6. 区域 GMV 分布。
7. 促销 vs 日常日均 GMV 提升。
8. 订单状态漏斗。
9. 履约耗时。

如果需要保持 6 面板限制，优先展示：

1. 每日 GMV 趋势
2. 分钟级流量洪峰
3. 商品销售 Top 10
4. 品类销售占比
5. 促销 vs 日常提升
6. 订单状态漏斗

## 验证设计

`sync/verify.py` 增加业务可信度和时序能力检查：

1. MySQL 5 张原有业务表行数准确。
2. 新增 `order_status_events` 行数非空。
3. 商品品类与商品类型匹配率 100%。
4. `order_items.unit_price` 与 `products.price` 偏差在 5% 内。
5. 每单商品数不是固定值，且分布覆盖 1、2、3、5 件以上订单。
6. 双 11 当天订单量至少是平日均值 50 倍。
7. 完成订单必须具备 created、paid、shipped、completed 事件。
8. 取消订单必须具备 created、cancelled 事件。
9. 区域匹配率 100%。
10. 取消订单不进入 ADS GMV。
11. `time_bucket('1 minute', order_time)` 返回非空结果。
12. 峰值分钟订单数高于普通分钟。
13. DWD 订单 GMV 与明细成交额可对账。
14. MARS3 vs HEAP 压缩验证继续通过。
15. Grafana 数据源和 Dashboard 继续可访问。

## 错误处理

1. 数据生成阶段固定随机种子，保证每次演示结果可复现。
2. 若生成数据未满足分布目标，生成脚本直接失败，避免带着坏数据进入 ETL。
3. ETL 各层继续使用 `ON_ERROR_STOP=1`。
4. mxgate 装载后继续校验写入行数。
5. 指标验证失败时 `init_all.sh` 返回非零退出码。

## 兼容性与迁移

1. `orders.order_date` 改为 `order_time` 会影响 ODS、DWD、DWS、ADS、Grafana 查询，需要同步修改。
2. 为便于分区，DWD 中派生 `order_date`，避免破坏已有 RANGE 分区设计。
3. `payments.pay_date` 改为 `pay_time`，同步修改 extract、transform、load 和 SQL。
4. 新增 `order_status_events` 后，MySQL 初始化、生成脚本、抽取、ODS DDL、加载器、DWD/DWS/ADS 均需注册。
5. README 和报告需要更新指标口径，明确有效订单定义。

## 验收标准

完成后必须满足：

1. `docker-compose up -d && bash init_all.sh` 从空卷完整跑通。
2. MySQL 业务表和新增状态事件表行数符合预期。
3. ODS -> DIM -> DWD -> DWS -> ADS 对象完整。
4. 商品、价格、区域、订单状态流转通过业务可信度验证。
5. 双 11 当天订单量至少是平日均值 50 倍。
6. 分钟级 `time_bucket` 查询返回非空结果，并能识别峰值分钟。
7. ADS 指标口径正确，取消订单不进入 GMV。
8. DWD 订单 GMV 与明细成交额可对账。
9. MARS3 压缩验证继续达到目标。
10. Grafana Dashboard 展示业务指标和时序峰值分析。

## 后续实施建议

按以下顺序实施：

1. 修改 MySQL DDL 和数据生成脚本。
2. 修改 ODS/DIM/DWD DDL。
3. 修改 extract、transform、ODS/DIM/DWD 加载逻辑。
4. 修改 DWS/ADS 指标。
5. 修改 Grafana Dashboard。
6. 扩展 verify.py 和 preflight.ps1。
7. 执行从空卷开始的全流程验证。

## 设计修订：大规模数据与累计时序指标

根据后续评审，设计需要进一步覆盖大规模业务数据、批量装载、字段迁移成本、订单金额对账和双 11 累计 GMV。

### 数据规模目标

订单生成规模从 50,000 单提升为可配置规模：

```text
default: 1,000,000 orders
stress: 5,000,000 orders
```

按每单平均约 3 到 4 个明细计算：

```text
default: 约 3,000,000 到 4,000,000 order_items
stress: 约 15,000,000 order_items
```

生成脚本不得再在内存中拼接完整 SQL values。必须改为流式写出 CSV 文件：

1. `seed_users.csv`
2. `seed_products.csv`
3. `seed_orders.csv`
4. `seed_order_items.csv`
5. `seed_payments.csv`
6. `seed_order_status_events.csv`

每个 CSV 文件按行流式写入，生成过程中维护必要的小型内存索引，例如产品价格表和用户分层权重，不保留百万级订单对象列表。

### MySQL 与 YMatrix 装载边界

`mxgate` 是 YMatrix/MatrixDB 的高速导入工具，不用于 MySQL 业务库。

大规模数据装载边界如下：

1. MySQL 业务库装载使用 `LOAD DATA LOCAL INFILE` 或 `mysqlimport`。
2. MySQL 容器需要允许本地文件导入，`init_all.sh` 负责把 CSV 文件通过容器挂载或 `docker-compose exec` 可访问路径导入。
3. YMatrix ODS 装载继续使用 `mxgate --source stdin` 或 CSV 文件输入。
4. 端到端流程仍保持 MySQL 是业务源库，YMatrix 是数仓引擎，不允许绕过 MySQL 直接生成 ADS。

这样既能模拟业务库批量初始化，也能保留 YMatrix `mxgate` 高速写入展示点。

### `order_date` 迁移策略

将源表字段直接从 `order_date DATE` 重命名为 `order_time TIMESTAMP(3)` 会影响 MySQL DDL、生成脚本、extract、transform、ODS、DWD、DWS、ADS、Grafana 和文档，迁移面较大。

推荐采用分层重命名策略：

1. MySQL `orders` 保留字段名 `order_date`，但类型升级为 `DATETIME(3)`。
2. MySQL `payments.pay_date` 保留字段名，类型升级为 `DATETIME(3)`。
3. ODS 保留源字段名，使用 `TIMESTAMP(3)` 承接。
4. DWD 层进行强类型转换和语义重命名：
   - `ods_orders.order_date::TIMESTAMP(3) AS order_time`
   - `DATE(ods_orders.order_date) AS order_date`
   - `ods_payments.pay_date::TIMESTAMP(3) AS pay_time`
5. DWS/ADS/Grafana 使用 DWD 的 `order_time` 做时序分析，使用 DWD 的 `order_date` 做日级分区和日级指标。

该策略把源库改动控制在类型升级，避免一次性重命名穿透所有层，同时在数仓 DWD 层提供清晰语义字段。

### 订单金额对账设计

当前缺少 `orders.total_amount` 与 `order_items.final_price` 的对账闭环。修订后必须满足：

1. 数据生成时，订单总额由明细成交价汇总得到。
2. 明细成交价公式为：

```text
line_amount = ROUND(unit_price * quantity * (1 - discount_rate), 2)
```

3. `orders.total_amount` 等于同订单所有 `line_amount` 之和。
4. DWD 层 `dwd_order_fact.total_amount` 来自订单事实。
5. DWD 层 `dwd_order_detail_fact.final_price` 或 `line_amount` 必须能还原明细成交额。
6. DWS/verify 中新增对账检查：

```sql
ABS(order_fact.total_amount - detail_fact.detail_amount) <= 0.05
```

如果使用 `final_price` 表示单价，则 DWS 对账使用 `SUM(sku_num * final_price)`；如果新增 `line_amount` 字段，则优先使用 `SUM(line_amount)`。

推荐在 DWD 明细事实表新增 `line_amount NUMERIC(12,2)`，避免重复计算和舍入误差扩散。

### 流量洪峰分布

订单日期权重调整为强洪峰模型：

```text
平日: 1
周末: 1.5
双 11 预热期 Day 306-315: 5
双 11 当天 Day 316: 100
双 11 返场期 Day 317-319: 10
```

验收要求：

1. 双 11 当天订单量至少为平日均值 50 倍。
2. 双 11 当天分钟级峰值订单数显著高于普通分钟。
3. `dws_minute_order_traffic` 必须能反映分钟级洪峰。

### 新增 ADS：双 11 当日累计 GMV

新增 ADS 视图：

```sql
ads_gmv_running_total
```

用途：展示双 11 当日从 00:00 开始的累计 GMV 趋势，突出 YMatrix 对时序窗口分析和大促实时看板的支撑能力。

建议字段：

```text
bucket_time TIMESTAMP(3)
minute_gmv NUMERIC(18,2)
running_gmv NUMERIC(18,2)
minute_order_count BIGINT
running_order_count BIGINT
```

建议逻辑：

```sql
SELECT
  bucket_time,
  minute_gmv,
  SUM(minute_gmv) OVER (ORDER BY bucket_time ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_gmv,
  minute_order_count,
  SUM(minute_order_count) OVER (ORDER BY bucket_time ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_order_count
FROM dws_minute_order_traffic
WHERE bucket_time >= TIMESTAMP '2024-11-11 00:00:00'
  AND bucket_time <  TIMESTAMP '2024-11-12 00:00:00';
```

Grafana 应新增或替换一个面板展示该累计曲线，标题建议为“双 11 当日累计 GMV”。

### 大规模验证补充

验证脚本新增：

1. `orders` 行数等于配置目标。
2. `order_items` 行数在目标订单数的 3 到 5 倍之间，且每单明细数分布非固定。
3. CSV 文件生成过程不出现内存级 SQL 拼接。
4. MySQL `LOAD DATA` 导入行数与 CSV 行数一致。
5. YMatrix ODS 行数与 MySQL 源表行数一致。
6. `orders.total_amount` 与明细成交额按订单可对账。
7. `ads_gmv_running_total` 返回双 11 当日非空累计曲线，且累计 GMV 单调递增。
8. 默认 1,000,000 订单规模可在本地演示环境完成初始化；5,000,000 订单作为压力配置，不作为默认验收门槛。
