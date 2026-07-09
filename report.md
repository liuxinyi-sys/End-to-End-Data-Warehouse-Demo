# YMatrix 数仓端到端 Demo 报告

## 1. 方案设计

### 架构总览
```
Docker Compose
├── MySQL (port 3306) — 业务库（6 表 + CSV 种子数据）
├── YMatrix (port 5432) — 数仓引擎（五层 + DIM）
│   └── mxgate — 高性能写入 Segment
└── Grafana (port 3000) — 可视化仪表盘
      └── data source → YMatrix (PostgreSQL protocol)
```

### 数据流
1. Python 脚本生成 CSV 种子数据（可信电商场景：5 品类、10 城市、双11加权）
2. `LOAD DATA LOCAL INFILE` 将 CSV 加载到 MySQL 业务库
3. Python 从 MySQL 抽取全量数据到 pandas DataFrame
4. pandas 清洗（去空、类型标准化）
5. mxgate 灌入 ODS 层（MARS3 引擎，lz4 压缩，RANGE 分区）
6. SQL INSERT INTO...SELECT... 执行 ODS → DWD 清洗（语义重命名）
7. 物化视图 REFRESH 更新 DWS 层（time_bucket 分钟级聚合）
8. ADS 视图封装最终指标
9. Grafana 直连 ADS 层出图

### 数仓分层
| 层级 | 存储引擎 | 内容 |
|------|---------|------|
| ODS | MARS3（lz4 level 7，按月 RANGE 分区） | 6 张原始表镜像（含 order_status_events，TIMESTAMP(3) 毫秒精度） |
| DIM | HEAP | 4 张维度表（dim_region 10 城市、dim_promotion 3 促销、dim_product、dim_user） |
| DWD | MARS3（lz4 level 7，按月 RANGE 分区） | 3 张事实表（order_fact、detail_fact、status_event_fact） |
| DWS | MATERIALIZED VIEW | 7 个预聚合（含 time_bucket 分钟级流量、状态漏斗、履约延迟） |
| ADS | VIEW | 12 个业务指标（含 ads_gmv_running_total、ads_order_fulfillment_latency） |

### YMatrix 特性展示
| # | 特性 | 展示位置 |
|---|------|---------|
| 1 | MARS3 行列混存引擎 | ODS/DWD 全部建表 |
| 2 | lz4 压缩（level 7） | ODS/DWD 建表参数 |
| 3 | RANGE 分区（按月） | ODS/DWD 建表参数 |
| 4 | 自动分区管理 APM | 01_init.sql |
| 5 | 物化视图 + REFRESH | DWS 层 7 个物化视图 |
| 6 | mxgate 高性能写入 | sync/load_ods.py |
| 7 | DISTRIBUTED BY + ORDER BY | 全部 MARS3 表 DDL |
| 8 | time_bucket 时序聚合 | dws_minute_order_traffic |
| 9 | 窗口函数 SUM OVER | ads_gmv_running_total |
| 10 | HEAP 引擎对照 | ods_orders_heap vs ods_orders_mars_compare |
| 11 | Grafana 预置 Dashboard | grafana/dashboards/ |

## 2. 实现说明

### 业务数据库（MySQL 电商场景）
- users (1,000), products (500), orders (默认 200,000), order_items (~480K), payments (190K), order_status_events (~700K)
- 双11促销波峰（11.11 订单量达日均 74x，GMV 达日均 49x）
- 时间范围: 2024-01-01 ~ 2024-12-31
- 城市覆盖: 北京/上海/广州/深圳/成都/武汉/杭州/南京/西安/重庆
- 时间精度: 毫秒级 DATETIME(3)
- 业务时区: Asia/Shanghai

### 业务指标（12 个 ADS 视图）
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

### ETL Pipeline 设计
- 幂等: 每次全量 TRUNCATE + 重载（mxgate 加载前 TRUNCATE）
- 分步: extract → transform → load_ods → load_dim → load_dwd → refresh_mv → verify
- 审计: etl_log 表记录每步耗时（17 条日志）
- 验证: verify.py 执行 21 项断言检查
- 跨平台: .gitattributes 强制 LF 行尾，CSV lineterminator="\n"

### 物化视图策略
- 标准 MATERIALIZED VIEW（非 Domino 连续视图）
- 批处理完成后统一 REFRESH（7 个视图）
- 有效订单语义: status IN ('paid','shipped','completed')

## 3. 测试过程

### 验证清单
- [x] MySQL 6 表行数正确
- [x] ODS 行数 = MySQL 行数
- [x] DWS 7 个物化视图 REFRESH 成功
- [x] ADS 11 个指标返回非空数据
- [x] MARS3 vs HEAP 压缩率对比（83.2% 节省）
- [x] Grafana 6 个面板正常渲染
- [x] etl_log 日志完整（17 条）
- [x] 双11累计 GMV 单调递增
- [x] 订单/明细金额对账（0 误差）

### 预期断言值
| 检查项 | 预期 | 实际 |
|--------|------|------|
| MySQL: users | 1000 行 | 1000 ✓ |
| MySQL: orders | 200000 行 | 200000 ✓ |
| MySQL: order_items | 400K~1M 行 | 481931 ✓ |
| MySQL: order_status_events | ≥ 200000 行 | 699854 ✓ |
| ODS 行数 = MySQL 行数 | 严格相等 | ✓ |
| ads_daily_gmv | 365 行 | 365 ✓ |
| ads_gmv_running_total | 非空，单调递增 | 1425 行，0 违规 ✓ |
| ads_minute_traffic | 非空 | 124032 行 ✓ |
| DWD 时区对齐 | order_date = DATE(order_time) | 0 偏移 ✓ |
| 订单/明细金额对账 | 误差 < 0.05 | 0 误差 ✓ |
| Nov 11 流量 | ≥ 50x 日均 | 74x ✓ |
| MARS3 vs HEAP 压缩率 | 节省 50%+ | 83.2% ✓ |

## 4. 测试结果

### 自动化验证（verify.py 21/21 PASS）

```
  ads_daily_gmv: 365 rows -> PASS
  Nov 11: 126199926.89 vs avg: 2569047 -> PASS
  top_products: 10 rows -> PASS
  category pct: 100.00% -> PASS
  repurchase: 100.00% -> PASS
  gmv_by_region: 9 rows -> PASS
  promo_compare: 2 non-empty periods -> PASS
  user_segment: 3 segments -> PASS
  compression: MARS3 saves 83.2% -> PASS
  etl_log: 17 entries -> PASS
  ods_orders equals configured scale 200000 rows -> PASS
  order_items 2x to 5x orders 481931 rows -> PASS
  Nov 11 >= 50x normal daily average 33790 vs 456.62 -> PASS
  status events present 699854 rows -> PASS
  order item count varies 200000 non-four-item orders -> PASS
  product dimension credible 0 invalid products -> PASS
  order/detail amount reconciles 0 mismatches -> PASS
  minute traffic non-empty 124032 rows -> PASS
  running GMV non-empty 1425 rows -> PASS
  running GMV monotonic 0 violations -> PASS
  DWD timezone date aligned 0 shifted rows -> PASS

21/21 passed
```

### 核心业务指标

| 指标 | 数值 |
|------|------|
| 双11 GMV | ¥126,199,926.89 |
| 日常日均 GMV | ¥2,569,047 |
| 双11 GMV 倍数 | 49.2x 日常 |
| 双11订单量 | 32,062 |
| 日常日均订单量 | 457 |
| 双11订单倍数 | 70.2x 日常 |
| 促销期日均 GMV | ¥18,527,143 |
| 促销期 GMV 提升 | 858.7% |
| 复购率 | 100% |
| MARS3 压缩节省 | 83.2% |
| ETL 总耗时 | 78.9 秒 |
| Grafana 状态 | healthy |

### Grafana 健康检查
```
GET http://localhost:3000/api/health
{"database":"ok","version":"13.1.0","commit":"b309c9bb3b81a748c3a75289236a27309ed2566a"}
```

### 双11累计 GMV（前 10 分钟）
```
    bucket_time     | minute_gmv | running_gmv | minute_order_count | running_order_count
---------------------+------------+-------------+--------------------+---------------------
 2024-11-11 00:00:00 |  353851.17 |   353851.17 |                 84 |                  84
 2024-11-11 00:01:00 |  163053.97 |   516905.14 |                 59 |                 143
 2024-11-11 00:02:00 |  298688.15 |   815593.29 |                 76 |                  219
 2024-11-11 00:03:00 |  287136.18 |  1102729.47 |                 67 |                  286
 2024-11-11 00:04:00 |  272278.59 |  1375008.06 |                 78 |                  364
 2024-11-11 00:05:00 |  214278.80 |  1589286.86 |                 58 |                  422
 2024-11-11 00:06:00 |  403397.61 |  1992684.47 |                 63 |                  485
 2024-11-11 00:07:00 |  317501.52 |  2310185.99 |                 82 |                  567
 2024-11-11 00:08:00 |  318731.47 |  2628917.46 |                 86 |                  653
 2024-11-11 00:09:00 |  149344.82 |  2778262.28 |                 53 |                  706
```

> 完整运行结果详见 [results/run-results-2026-07-09.md](results/run-results-2026-07-09.md)

## 5. 问题和风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Docker 镜像构建失败 | 无法启动 YMatrix | 已验证 .deb MD5，Dockerfile 已测试 |
| Windows CRLF 行尾 | mxgate 加载全部拒绝 | .gitattributes 强制 LF + csv lineterminator="\n" |
| mxgate 重复加载 | 数据叠加 | 加载前 TRUNCATE 目标表 |
| TIMESTAMP 时区偏移 | 分区键超出范围 | ODS 时间已是本地时间，直接使用不做 AT TIME ZONE |
| DWS JOIN 列歧义 | 物化视图创建失败 | 使用表别名限定列名 |
| 大型 .deb 包（364MB） | 构建耗时长 | 首次构建后缓存镜像层 |
| init SQL 执行顺序 | DDL 依赖错误 | 文件名前缀控制顺序 |

## 6. 后续改进方向

- [ ] 切换为 Domino 连续视图实现实时 ETL
- [ ] 接入 Kafka 数据源
- [ ] 增加 UPSERT 增量更新
- [ ] 扩展为多节点 MPP 集群
- [ ] 增加 ORDER_COUNT=1000000 性能演示
- [ ] 接入 YMatrix 官方 Grafana 监控面板
- [ ] 增加数据质量监控告警
