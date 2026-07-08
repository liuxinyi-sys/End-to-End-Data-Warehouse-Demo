# YMatrix 数仓端到端 Demo 报告

## 1. 方案设计

### 架构总览
```
Docker Compose
├── MySQL (port 3306) — 业务库（5 表 + 种子数据）
├── YMatrix (port 5432) — 数仓引擎（四层 + DIM）
│   └── mxgate (port 8090) — 高性能写入
└── Grafana (port 3000) — 可视化仪表盘
      └── data source → YMatrix (PostgreSQL protocol)
```

### 数据流
1. Python 脚本从 MySQL 抽取全量数据
2. pandas 清洗（去空、类型标准化、衍生字段）
3. mxgate 灌入 ODS 层
4. SQL INSERT INTO...SELECT... 执行 ODS → DWD 清洗
5. 物化视图 REFRESH 更新 DWS 层
6. ADS 视图封装最终指标
7. Grafana 直连 ADS 层出图

### 数仓分层
| 层级 | 存储引擎 | 内容 |
|------|---------|------|
| ODS | MARS3（lz4 level 7，按天分区） | 5 张原始表镜像 |
| DIM | HEAP | 5 张维度表 |
| DWD | MARS3（lz4 level 7，按天分区） | 2 张明细事实表 |
| DWS | MATERIALIZED VIEW | 3 个预聚合 |
| ADS | VIEW | 7 个业务指标 |

### YMatrix 特性展示
| # | 特性 | 展示位置 |
|---|------|---------|
| 1 | MARS3 引擎 | 全部 DDL |
| 2 | lz4 压缩 | ODS/DWD 建表 |
| 3 | RANGE 分区 | ODS/DWD 建表 |
| 4 | 自动分区管理 APM | 01_init.sql |
| 5 | 物化视图（MATERIALIZED VIEW） | DWS 层 DDL |
| 6 | mxgate 写入 | sync/load_ods.py |
| 7 | DISTRIBUTED BY + ORDER BY | 全部 DDL |
| 8 | mysql_fdw 联邦查询 | 07_fdw.sql |
| 9 | Grafana 预置 Dashboard | docker-compose |
| 10 | date_trunc 聚合 | dws_daily_gmv |
| 11 | HEAP 引擎对照 | verify/compression.sql |

## 2. 实现说明

### 业务数据库（MySQL 电商场景）
- users (1,000), products (500), orders (50,000), order_items (200,000), payments (50,000)
- 双11促销波峰（11.11 达日常 6x）
- 时间范围: 2024-01-01 ~ 2024-12-31
- 城市覆盖: 北京/上海/广州/成都/武汉

### ETL Pipeline 设计
- 幂等: 每次全量 TRUNCATE + 重载
- 分步: extract → transform → load_ods → load_dim → load_dwd → refresh_mv
- 审计: etl_log 表记录每步耗时
- 验证: verify.py 执行断言检查

### 物化视图策略
- 标准 MATERIALIZED VIEW（非 Domino 连续视图）
- 批处理完成后统一 REFRESH
- 规避了连续视图不支持多表 JOIN 的限制

## 3. 测试过程

### 验证清单
- [ ] MySQL 5 表行数正确
- [ ] ODS 行数 = MySQL 行数
- [ ] DWS 物化视图 REFRESH 成功
- [ ] ADS 7 个指标返回非空数据
- [ ] MARS3 vs HEAP 压缩率对比
- [ ] Grafana 7 个面板显示正常
- [ ] mysql_fdw 跨库查询成功
- [ ] etl_log 日志完整

### 预期断言值
| 检查项 | 预期 |
|--------|------|
| MySQL: users | 1000 行 |
| MySQL: orders | 50000 行 |
| MySQL: order_items | 200000 行 |
| ODS 行数 = MySQL 行数 | 严格相等 |
| ads_daily_gmv | 365 行，可见双11波峰 |
| ads_top_products | 10 行，revenue > 0 |
| ads_category_sales | 5 行，占比之和 ≈ 100% |
| ads_user_repurchase | 复购率 ≈ 30% |
| MARS3 vs HEAP 压缩率 | MARS3 节省 50%+ |

## 4. 问题和风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Docker 镜像构建失败 | 无法启动 YMatrix | 已验证 .deb MD5，Dockerfile 已测试 |
| mxgate 兼容性 | ETL 写入失败 | 备选方案: COPY 命令 |
| Grafana Dashboard JSON | 可视化缺失 | 可降级为 SQL 查询结果 |
| 大型 .deb 包（364MB） | 构建耗时长 | 首次构建后缓存镜像层 |
| init SQL 执行顺序 | DDL 依赖错误 | 文件名前缀控制顺序 |

## 5. 后续改进方向

- [ ] 切换为 Domino 连续视图实现实时 ETL
- [ ] 接入 Kafka 数据源
- [ ] 增加 UPSERT 增量更新
- [ ] 扩展为多节点 MPP 集群
- [ ] 增加数据量到 1000 万级
- [ ] 接入 YMatrix 官方 Grafana 监控面板
