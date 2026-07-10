# YMatrix 数仓端到端 Demo

## 1. 项目目标

构建一个从**业务库（MySQL）到数仓分层（YMatrix）再到可视化仪表盘（Grafana）**的最小可运行 Demo，完整展示 YMatrix 在数据仓库场景中的核心优势：

- **MARS3 行列混存引擎**：lz4 压缩，相比 HEAP 行存节省 83%+ 存储
- **mxgate 高性能写入**：直连 Segment 并行写入，20 万订单全链路 ETL 约 80 秒
- **time_bucket 时序聚合**：分钟级流量、双11累计 GMV 窗口函数
- **MPP 分布式架构**：DISTRIBUTED BY + ORDER BY + RANGE 分区
- **物化视图预聚合**：标准 MATERIALIZED VIEW + REFRESH，7 个 DWS 预聚合
- **五层数仓架构**：ODS → DIM → DWD → DWS → ADS，分层清晰

---

## 目录结构

```
End-to-End-Data-Warehouse-Demo/
├── init_all.sh                          # [入口] 一键初始化脚本：等待就绪 → 建表 → ETL → 验证
├── README.md                            # 项目说明文档（本文件）
├── AGENTS.md                            # AI 协作开发指南
├── report.md                            # 项目报告
├── ai_usage.md                          # AI 使用记录
├── config.example.yaml                  # 全部可配置参数参考
├── docker-compose.yml                   # 三容器编排：MySQL + YMatrix + Grafana
├── ymatrix_dw_demo_skill.md             # YMatrix 数仓使用技能文档
├── .gitattributes                       
├── .gitignore
│
├── mysql/
│   └── init.sql                         # 业务库 DDL + 种子数据（容器入口点）
│
├── ymatrix/                             # YMatrix 数仓引擎
│   ├── Dockerfile                       # 镜像构建文件（已预构建为 lxy0315/ymatrix5.2-clean:latest 上传 Docker Hub）
│   ├── docker-entrypoint.sh             # 容器入口脚本：初始化 + 启动
│   ├── matrixdb5-5.2.1+community-1.el7.x86_64.rpm   # YMatrix RPM 安装包（构建镜像用，普通用户无需关心）
│   ├── init/                            # 容器入口点 initdb 脚本（按编号顺序执行）
│   │   ├── 01_init.sql                  # CREATE EXTENSION matrixts, APM 自动分区, dim_date 生成
│   │   ├── 02_ods.sql                   # ODS 6 表 DDL（MARS3, TIMESTAMP(3), RANGE 月分区）
│   │   ├── 03_dim.sql                   # DIM 维度表 DDL（HEAP, 10 城市 region, 3 促销）
│   │   ├── 03_dwd.sql                   # DWD 3 事实表 DDL（MARS3, order_time, status_event_fact）
│   │   ├── 04_dws.sql                   # 7 个物化视图（time_bucket 分钟级, 状态漏斗, 履约延迟）
│   │   ├── 05_ads.sql                   # 12 个 ADS 视图（含 ads_gmv_running_total 累计 GMV）
│   │   └── 06_fdw.sql                   # mysql_fdw 联邦查询（可选展示）
│   └── verify/
│       └── 01_compression.sql           # MARS3 vs HEAP 压缩率对比查询
│
├── sync/                                # 数据同步 / ETL 引擎
│   ├── sync_data.py                     # [入口] 编排全流程：extract → transform → load
│   ├── gen_data.py                      # 生成 MySQL 种子数据（CSV）
│   ├── extract.py                       # MySQL → DataFrame 抽取
│   ├── transform.py                     # pandas 清洗逻辑
│   ├── load_ods.py                      # mxgate stdin → ODS 高速写入
│   ├── load_dim.py                      # TRUNCATE + mxgate → DIM 维度表
│   ├── load_dwd.py                      # SQL INSERT INTO...SELECT → DWD / REFRESH MV
│   ├── verify.py                        # 21 项自动化断言验证 + etl_log 写入
│   ├── requirements.txt                 # pandas, PyMySQL, psycopg2-binary, sqlalchemy
│   └── __pycache__/                     # Python 字节码缓存（gitignored 之外的历史提交）
│
├── grafana/                             # Grafana 预置配置
│   ├── datasources/
│   │   └── ymatrix.yaml                 # YMatrix (PostgreSQL) 数据源
│   └── dashboards/
│       ├── ymatrix_dw_demo.json         # 预置 13 面板 Dashboard
│       └── provider.yaml               # Dashboard 自动加载配置
│
├── docs/                                # 文档
│   ├── supplementary.md                 # 补充文档：设计决策记录
│   ├── ecommerce-timeseries-verification-2026-07-09.md  # 时序验证报告
│   ├── full-flow-repair-verification-2026-07-08.md      # 全链路修复验证
│   ├── full-flow-test-report-2026-07-08.md              # 全链路测试报告
│   └── superpowers/
│       ├── specs/                       # 设计规范文档
│       │   ├── 2026-07-08-full-flow-repair-design.md
│       │   └── 2026-07-09-ecommerce-business-timeseries-design.md
│       └── plans/                       # 实施计划文档
│           ├── 2026-07-07-ymatrix-dw-demo-implementation.md
│           ├── 2026-07-08-full-flow-repair.md
│           └── 2026-07-09-ecommerce-business-timeseries-implementation.md
│
└── results/                             # 运行结果
    ├── run-results-2026-07-09.md        # 全链路运行结果记录
    └── screenshots/                     # Grafana 仪表盘截图
```

---

## 2. 环境依赖

### 2.1 主机要求

| 组件 | 最低版本 | 用途 | 下载 |
|------|---------|------|------|
| **Docker Desktop** | 4.20+ (引擎 24.0+) | 容器编排 MySQL + YMatrix + Grafana | [下载](https://www.docker.com/products/docker-desktop/) |
| **Git** | 2.30+ | 克隆仓库、运行 init_all.sh | [下载](https://git-scm.com/) |
| **Python** | 3.6+ | ETL 脚本（extract/transform/load/verify），代码兼容 3.6 | [下载](https://www.python.org/) |

> **说明**：MySQL 8.0、YMatrix 5.2.1、Grafana 均运行在 Docker 容器中，无需主机单独安装。Python 仅用于运行 ETL 脚本。

### 2.2 Python 依赖

```bash
pip install -r sync/requirements.txt
```

>如果直接 `pip install pandas sqlalchemy`（不指定版本），会安装 SQLAlchemy 2.0+，导致 ETL 报错 `AttributeError: 'OptionEngine' object has no attribute 'execute'`（详见 [§8.4](#84-python-依赖版本冲突attributeerror-optionengine-object-has-no-attribute-execute)）。

依赖清单及锁定版本说明见 [sync/requirements.txt](sync/requirements.txt)。

### 2.3 Docker 资源建议

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 5 GB | 10 GB+（含 Docker 镜像约 1.5GB） |

---

## 3. 安装步骤

### 3.1 克隆仓库

```bash
git clone https://github.com/liuxinyi-star/End-to-End-Data-Warehouse-Demo.git
cd End-to-End-Data-Warehouse-Demo
```

### 3.2 启动三容器

```bash
docker-compose up -d
```

Docker Compose 会自动从 Docker Hub 拉取三个镜像并启动容器：

| 容器 | 镜像 | 端口 | 健康检查 |
|------|------|------|---------|
| e2e-mysql | mysql:8.0 | 3306 | mysqladmin ping |
| e2e-ymatrix | lxy0315/ymatrix5.2-clean:latest | 5432 | psql SELECT 1 |
| e2e-grafana | grafana/grafana:latest | 3000 | /api/health |

> 首次拉取 YMatrix 镜像约 364MB，后续直接使用本地缓存。

等待全部健康（约 30-60 秒）：

```bash
docker-compose ps
```

确认三个容器状态均为 `Up (healthy)`。

### 3.3 一键初始化数仓

```bash
bash init_all.sh
```

`init_all.sh` 按顺序执行：
1. 等待 MySQL / YMatrix / Grafana 就绪
2. 生成 CSV 种子数据（默认 20 万订单，10 城市，5 品类）
3. `LOAD DATA LOCAL INFILE` 加载 CSV 到 MySQL
4. 重置 YMatrix 数仓对象（DROP + CREATE）
5. 执行 ETL Pipeline（extract → transform → load_ods → load_dim → load_dwd → refresh）
6. 运行 verify.py（21 项自动化断言检查）

> 脚本可在不删除 Docker volumes 的情况下重复执行。默认 20 万订单全程约 80 秒。

---

## 4. 配置说明

### 4.1 docker-compose.yml

```yaml
services:
  mysql:     # 端口 3306, 用户 root, 密码 root, 数据库 ecommerce
  ymatrix:   # 端口 5432, 用户 mxadmin, 密码 mxadmin123, 数据库 dw_demo
  grafana:   # 端口 3000, 用户 admin, 密码 admin
```

### 4.2 数据规模配置

通过环境变量 `ORDER_COUNT` 控制订单规模：

```bash
# 默认 20 万订单（开发验证）
bash init_all.sh

# 100 万订单（性能演示）
ORDER_COUNT=1000000 bash init_all.sh

# 500 万订单（极限压测）
ORDER_COUNT=5000000 bash init_all.sh
```

| 规模 | 环境变量 | 订单数 | 预期耗时 | 用途 |
|------|---------|--------|---------|------|
| 默认 | `ORDER_COUNT=200000` | 200,000 | ~80s | 全链路验证 |
| 性能 | `ORDER_COUNT=1000000` | 1,000,000 | ~5min | 性能演示 |
| 压测 | `ORDER_COUNT=5000000` | 5,000,000 | ~25min | 极限压测 |

### 4.3 Benchmark 压测对比

初始化完成后，运行 benchmark 脚本生成 4 维度性能对比报告:

```bash
cd sync && python benchmark.py 5
```

| 对比维度 | 内容 | 示例结果 |
|---------|------|---------|
| 存储压缩 | MARS3 lz4 vs HEAP 同数据 | 节省 83.2% (96MB vs 573MB) |
| 查询性能 | MARS3 vs HEAP 4 类查询 | 列存快 2.2~2.8x |
| 分区裁剪 | 命中单分区 vs 全表扫描 | EXPLAIN 证明跳过 12/13 分区 |
| 物化视图 | 预聚合 vs 实时 GROUP BY | 加速 8.1x |

结果输出到 `results/benchmark-results.md`。详细 SQL 版本见 `ymatrix/verify/02_benchmark.sql`。

### 4.3 完整配置参考

详见 [config.example.yaml](config.example.yaml)，包含 MySQL / YMatrix / ETL / Grafana / 数仓分层 / 验证阈值等全部可配置参数。

### 4.4 YMatrix 初始化 SQL 顺序

```
ymatrix/init/
├── 01_init.sql        # CREATE EXTENSION matrixts, APM 自动分区, dim_date 生成
├── 02_ods.sql         # ODS 6 表 DDL（MARS3, TIMESTAMP(3), RANGE 月分区）
├── 03_dim.sql         # DIM 维度表 DDL（HEAP, 10 城市 region, 3 促销）
├── 03_dwd.sql         # DWD 3 事实表 DDL（MARS3, order_time, status_event_fact）
├── 04_dws.sql         # 7 个物化视图（time_bucket 分钟级, 状态漏斗, 履约延迟）
├── 05_ads.sql         # 12 个 ADS 视图（含 ads_gmv_running_total 累计 GMV）
└── 06_fdw.sql         # mysql_fdw 联邦查询（可选展示）
```

### 4.5 业务时区

- 业务时区：`Asia/Shanghai`
- 源时间字段：`orders.order_date`、`payments.pay_date`，升级为毫秒级 `DATETIME(3)`
- DWD 语义字段：`order_time`、`pay_time`、`order_date`，ODS 的 `TIMESTAMP(3)` 已存储为本地时间

---

## 5. 运行方式

### 5.1 一键全链路（推荐）

```bash
docker-compose up -d && bash init_all.sh
```

### 5.2 仅重启 ETL（容器已运行）

```bash
cd sync && python sync_data.py && cd ..
```

### 5.3 分步执行

```bash
# 1. 生成种子数据（默认 20 万订单）
cd sync && python gen_data.py && cd ..

# 2. 开启 MySQL local_infile 并清空旧数据
docker-compose exec -T mysql mysql -uroot -proot -e "SET GLOBAL local_infile=1;"
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e "SET FOREIGN_KEY_CHECKS=0; TRUNCATE TABLE order_status_events; TRUNCATE TABLE payments; TRUNCATE TABLE order_items; TRUNCATE TABLE orders; TRUNCATE TABLE products; TRUNCATE TABLE users; SET FOREIGN_KEY_CHECKS=1;"

# 3. 逐表加载 CSV 到 MySQL
docker-compose exec -T mysql mysql --local-infile=1 -uroot -proot -D ecommerce -e "LOAD DATA LOCAL INFILE '/dev/stdin' INTO TABLE users FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n';" < sync/seed_users.csv
docker-compose exec -T mysql mysql --local-infile=1 -uroot -proot -D ecommerce -e "LOAD DATA LOCAL INFILE '/dev/stdin' INTO TABLE products FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n';" < sync/seed_products.csv
docker-compose exec -T mysql mysql --local-infile=1 -uroot -proot -D ecommerce -e "LOAD DATA LOCAL INFILE '/dev/stdin' INTO TABLE orders FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n';" < sync/seed_orders.csv
docker-compose exec -T mysql mysql --local-infile=1 -uroot -proot -D ecommerce -e "LOAD DATA LOCAL INFILE '/dev/stdin' INTO TABLE order_items FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n';" < sync/seed_order_items.csv
docker-compose exec -T mysql mysql --local-infile=1 -uroot -proot -D ecommerce -e "LOAD DATA LOCAL INFILE '/dev/stdin' INTO TABLE payments FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n';" < sync/seed_payments.csv
docker-compose exec -T mysql mysql --local-infile=1 -uroot -proot -D ecommerce -e "LOAD DATA LOCAL INFILE '/dev/stdin' INTO TABLE order_status_events FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"' LINES TERMINATED BY '\n';" < sync/seed_order_status_events.csv

# 4. 验证 MySQL 数据
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e "SELECT 'users' AS t, COUNT(*) AS n FROM users UNION ALL SELECT 'products', COUNT(*) FROM products UNION ALL SELECT 'orders', COUNT(*) FROM orders UNION ALL SELECT 'order_items', COUNT(*) FROM order_items UNION ALL SELECT 'payments', COUNT(*) FROM payments UNION ALL SELECT 'order_status_events', COUNT(*) FROM order_status_events;"

# 5. 创建 YMatrix schema（按编号顺序执行 init SQL）
for f in ymatrix/init/*.sql; do
    echo "Running $(basename "$f")..."
    docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -v ON_ERROR_STOP=1 -f "/docker-entrypoint-initdb.d/$(basename "$f")"
done

# 6. 执行 ETL Pipeline（extract → transform → load_ods → load_dim → load_dwd → refresh）
cd sync && python sync_data.py && cd ..

# 7. 运行自动化验证（21 项断言）
cd sync && python verify.py && cd ..
```

### 5.4 彻底重来

```bash
docker-compose down -v
docker-compose up -d
bash init_all.sh
```

### 5.5 SQL 查询示例

以下演示如何进入容器直接操作 YMatrix 和 MySQL，逐条执行查询。

#### 进入 YMatrix 容器

```bash
docker exec -it e2e-ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo
```

进入 psql 交互界面后，逐条执行以下 SQL：

```sql
-- 1. 查看所有表和分区
\dt

-- 2. 查看每日 GMV 趋势（前 10 天）
SELECT dt, order_count, gmv, avg_order_amount FROM ads_daily_gmv ORDER BY dt LIMIT 10;

-- 3. 查看双11当天 GMV 对比日常
SELECT dt, order_count, gmv FROM ads_daily_gmv WHERE dt IN ('2024-11-10','2024-11-11','2024-11-12') ORDER BY dt;

-- 4. 查看双11累计 GMV（逐分钟，前 10 分钟）
SELECT bucket_time, minute_gmv, running_gmv, minute_order_count, running_order_count FROM ads_gmv_running_total ORDER BY bucket_time LIMIT 10;

-- 5. 查看商品销售 Top 10
SELECT product_name, category, total_qty, total_revenue FROM ads_top_products;

-- 6. 查看品类销售占比
SELECT category, revenue, pct FROM ads_category_sales ORDER BY revenue DESC;

-- 7. 查看 GMV 按省份分布
SELECT province, order_cnt, gmv FROM ads_gmv_by_region ORDER BY gmv DESC;

-- 8. 查看用户复购率
SELECT repurchase_rate, repeat_buyers, total_buyers FROM ads_user_repurchase;

-- 9. 查看用户价值分层
SELECT segment, user_count, total_orders FROM ads_user_segment ORDER BY segment;

-- 10. 查看促销期 vs 日常期对比
SELECT period, days, order_cnt, gmv, daily_avg_gmv, avg_order_value, uplift_pct FROM ads_promo_compare;

-- 11. 查看订单状态漏斗
SELECT status, order_count FROM ads_order_status_funnel;

-- 12. 查看双11分钟级流量（前 20 分钟）
SELECT bucket_time, minute_order_count, minute_gmv FROM ads_minute_traffic WHERE bucket_time >= TIMESTAMP '2024-11-11 00:00:00' AND bucket_time < TIMESTAMP '2024-11-12 00:00:00' ORDER BY bucket_time LIMIT 20;

-- 13. 查看流量峰值 Top 20 分钟
SELECT bucket_time, minute_order_count, minute_gmv FROM ads_traffic_peak_minutes;

-- 14. 查看履约延迟（小时）
SELECT paid_to_shipped_hours, shipped_to_completed_hours FROM ads_order_fulfillment_latency;

-- 15. 查看 MARS3 vs HEAP 压缩率对比
SELECT pg_total_relation_size('ods_orders_mars_compare') AS mars3_bytes, pg_total_relation_size('ods_orders_heap') AS heap_bytes, ROUND((1.0 - 1.0 * pg_total_relation_size('ods_orders_mars_compare') / pg_total_relation_size('ods_orders_heap')) * 100, 1) AS savings_pct;

-- 16. 查看 ETL 审计日志
SELECT log_id, step, status, rows_processed, duration_ms, log_time FROM etl_log ORDER BY log_id;

-- 退出 psql
\q
```

#### 进入 MySQL 容器

```bash
docker exec -it e2e-mysql mysql -uroot -proot -D ecommerce
```

进入 mysql 交互界面后，执行：

```sql
-- 17. 查看业务库各表行数
SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'payments', COUNT(*) FROM payments
UNION ALL SELECT 'order_status_events', COUNT(*) FROM order_status_events;

-- 18. 查看订单状态分布
SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status ORDER BY cnt DESC;

-- 19. 查看双11当天订单量
SELECT COUNT(*) AS nov11_orders FROM orders WHERE order_date >= '2024-11-11' AND order_date < '2024-11-12';

-- 退出 mysql
exit;
```

---

## 6. 示例输出

### 6.1 Grafana 仪表盘

访问 [http://localhost:3000](http://localhost:3000)（用户 admin / 密码 admin），预置 13 个面板：

| # | 面板 | 图表类型 | 数据源 |
|---|------|---------|--------|
| 1 | 每日 GMV 趋势 | 折线图 | `ads_daily_gmv` |
| 2 | 商品销售 Top 10 | 表格 | `ads_top_products` |
| 3 | 品类销售占比 | 饼图 | `ads_category_sales` |
| 4 | 用户复购率 | 单值 Stat | `ads_user_repurchase` |
| 5 | GMV 按省份分布 | 柱状图 | `ads_gmv_by_region` |
| 6 | 双11 累计 GMV | 折线图 | `ads_gmv_running_total` |
| 7 | 双11 累计订单量 | 折线图 | `ads_gmv_running_total` |
| 8 | 订单状态漏斗 | 柱状图 | `ads_order_status_funnel` |
| 9 | 促销期 vs 日常期 | 条形仪表 | `ads_promo_compare` |
| 10 | 用户价值分层 | 环形图 | `ads_user_segment` |
| 11 | 双11 分钟级流量 | 折线图 | `ads_minute_traffic` |
| 12 | 履约延迟 | 单值 Stat | `ads_order_fulfillment_latency` |
| 13 | 流量峰值 Top 20 分钟 | 表格 | `ads_traffic_peak_minutes` |

### 6.2 核心业务指标（20 万订单默认规模）

| 指标 | 数值 |
|------|------|
| MySQL orders | 200,000 |
| MySQL order_items | 483,200 |
| MySQL order_status_events | 699,451 |
| 双11 GMV | ¥140,425,396 |
| 日常日均 GMV | ¥2,852,071 |
| 双11 GMV 倍数 | 49.2x 日常 |
| 双11订单倍数 | 74x 日常 |
| 用户复购率 | 45.8% |
| MARS3 压缩节省 | 83.2% |
| ETL 总耗时 | ~80 秒 |
| 验证结果 | 21/21 PASS |

### 6.3 自动化验证输出

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
  ods_orders equals configured scale: 200000 rows -> PASS
  Nov 11 >= 50x normal daily average: 33816 vs 456 -> PASS
  running GMV non-empty: 1427 rows -> PASS
  running GMV monotonic: 0 violations -> PASS
  DWD timezone date aligned: 0 shifted rows -> PASS
  ... (21/21 passed)
```

完整运行结果详见 [results/run-results-2026-07-09.md](results/run-results-2026-07-09.md)。

---

## 7. 已知限制

- **单节点部署**：仅演示单台 Docker 容器，不涉及 MPP 多节点集群扩展
- **批量 ETL 模式**：使用标准物化视图 + REFRESH，非 Domino 流式实时处理
- **模拟数据**：默认 20 万订单为程序生成的可信电商数据，非真实业务数据
- **无 HA / 容错**：未配置 Mirror 镜像 / 数据备份 / 故障自动转移
- **YMatrix 社区版**：部分企业功能（如 Domino 连续视图、Kafka 直连）不可用
- **跨平台**：已通过 `.gitattributes` 强制 LF 行尾解决 Windows CRLF 问题，推荐在 Git Bash 中运行 `init_all.sh`

---

## 8. 部署常见问题及解决方案

> 以下问题均在**纯净 Windows 环境模拟客户现场部署**时实际遇到并验证过。

### 8.1 Docker Desktop 安装失败 / WSL 安装损坏

**适用场景**：在未安装过 Docker 的 Windows 电脑上首次安装 Docker Desktop。

**问题现象**：

Docker Desktop 安装过程中提示 WSL 相关错误，安装无法完成，或安装后启动时报 WSL 内核异常。

**原因分析**：

- Docker Desktop on Windows 依赖 WSL2（Windows Subsystem for Linux 2）。
- 如果系统之前有残留的损坏安装痕迹（如 `C:\Program Files` 下存在 **0 字节空位文件**），WSL 组件可能无法正常初始化。
- 某些 Windows 版本未默认启用 WSL2 或虚拟机平台功能。

**解决方案**：

1. **清理残留文件**：检查 `C:\Program Files` 下是否有 0 字节的空位文件（可能是之前安装失败残留），手动删除后重新安装 Docker Desktop。
2. **手动启用 WSL2**：以管理员身份打开 PowerShell，执行：
   ```powershell
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   ```
   重启电脑后，安装 [WSL2 Linux 内核更新包](https://aka.ms/wsl2kernel)，再安装 Docker Desktop。
3. **验证**：`docker --version` 和 `docker-compose --version` 正常输出即可。

> **提示**：如果本机已安装其他 MySQL 服务（见下节端口冲突），建议在安装 Docker 前先确认本机端口占用情况。

---

### 8.2 MySQL 端口 3306 冲突

**适用场景**：本机已安装 MySQL 服务，或 3306 端口被其他程序占用。

**问题现象**：

执行 `docker-compose up -d` 时，MySQL 容器无法启动，终端返回：

```text
Error response from daemon: ports are not available: exposing port TCP 0.0.0.0:3306
  -> 127.0.0.1:0: listen tcp 0.0.0.0:3306: bind:
  Only one usage of each socket address (protocol/network address/port) is normally permitted.
```

**原因分析**：

本机已有 MySQL 服务（`mysqld.exe`）默认监听 3306 端口，而 Docker Compose 中 MySQL 容器也映射主机端口 3306 → 容器端口 3306，两者冲突。

**排查命令**：

```bash
# 查看占用 3306 的进程
netstat -ano | findstr :3306

# 确认进程名（替换 PID 为上一步查到的值）
tasklist /FI "PID eq <PID>"
```

如果输出 `mysqld.exe`，说明是本机 MySQL 服务占用了端口。

**解决方案（推荐）：修改主机端口映射**

将 Docker Compose 中 MySQL 的**主机端口**（左侧）从 3306 改为 3307，容器内端口（右侧）保持 3306 不变：

**第 1 步**：编辑 `docker-compose.yml`

```yaml
# 修改前
mysql:
  ports:
    - "3306:3306"

# 修改后
mysql:
  ports:
    - "3307:3306"     # 左侧主机端口改为 3307，右侧容器端口不变
```

**第 2 步**：同步修改 `sync/extract.py` 中的连接端口号（ETL 脚本通过主机端口连接 MySQL）：

```python
# sync/extract.py 第 6 行
# 修改前
MYSQL_URI = "mysql+pymysql://root:root@localhost:3306/ecommerce?charset=utf8mb4"

# 修改后
MYSQL_URI = "mysql+pymysql://root:root@localhost:3307/ecommerce?charset=utf8mb4"
```

**第 3 步**：重新启动容器并执行初始化：

```bash
docker-compose down
docker-compose up -d
bash init_all.sh
```

**验证**：

```bash
# 容器状态为 Up (healthy)
docker-compose ps

# 可通过 3307 端口连接容器内 MySQL
mysql -h 127.0.0.1 -P 3307 -u root -proot -D ecommerce -e "SELECT 1"
```

**备选方案（不推荐）**：停止本机 MySQL 服务

如果必须使用 3306 端口，可以停止本机 MySQL 服务：

```bash
# 以管理员身份运行
net stop MySQL80          # 服务名可能是 MySQL80 / MySQL57 等
```

> ⚠️ 此方案会影响客户本机已有 MySQL 服务的正常运行，不适用于多服务共存的客户环境。**推荐使用修改端口方案**。

---

### 8.3 端口可配置说明

为方便客户在端口冲突时快速调整，以下是项目中所有涉及端口的位置：

| 端口 | 服务 | docker-compose.yml 位置 | 代码中引用位置 |
|------|------|------------------------|--------------|
| 3306 | MySQL | `mysql.ports` | [sync/extract.py:6](sync/extract.py#L6) 的 `MYSQL_URI` |
| 5432 | YMatrix | `ymatrix.ports` | ETL 内部通过 `docker-compose exec` 连接容器，无需改 |
| 3000 | Grafana | `grafana.ports` | 浏览器访问 `http://localhost:3000` |

> **修改原则**：只需修改 `docker-compose.yml` 中端口映射的**左侧**（主机端口），右侧（容器端口）保持不变。MySQL 主机端口修改后，需同步修改 `sync/extract.py` 中的 `MYSQL_URI` 端口号。YMatrix 和 Grafana 的主机端口修改后无需改代码（ETL 通过 `docker-compose exec` 容器内连接，不经过主机端口）。

---

### 8.4 Python 依赖版本冲突：`AttributeError: 'OptionEngine' object has no attribute 'execute'`

**适用场景**：执行 ETL 脚本（`python sync_data.py`）时。

**问题现象**：

```text
AttributeError: 'OptionEngine' object has no attribute 'execute'
```

**原因分析**：

SQLAlchemy 2.0（2023 年 1 月发布）移除了 `engine.execute()` 方法。pandas 1.x 的 `pd.read_sql(sql_string, engine)` 在内部调用 `engine.execute()`，如果用户环境安装了 SQLAlchemy 2.0+，就会触发此错误。

| 组件 | SQLAlchemy < 2.0 | SQLAlchemy 2.0+ |
|------|-------------------|-----------------|
| `engine.execute()` | 支持（弃用警告） | **已移除** |
| `pd.read_sql("SELECT ...", engine)` | ✅ 正常 | ❌ 报错 |
| `pd.read_sql(text("SELECT ..."), engine)` | ✅ 正常 | ✅ 正常 |

**解决方案**：

本项目已通过两种方式修复，用户任选其一即可：

#### 方式一（推荐）：使用已锁定的 requirements.txt 安装

```bash
cd sync
pip install -r requirements.txt
```

requirements.txt 已锁定为经过验证的兼容版本组合：

```
pandas==1.5.3
numpy==1.24.4
PyMySQL==1.1.0
psycopg2-binary==2.9.9
SQLAlchemy==1.4.52          # 锁定 1.4.x，避免 2.0 不兼容
```

如果之前已安装高版本 SQLAlchemy，需先卸载再安装：

```bash
pip uninstall SQLAlchemy -y
pip install SQLAlchemy==1.4.52
```

#### 方式二：升级 pandas + SQLAlchemy 2.0（代码已兼容）

extract.py 已改用 `text()` 包装 SQL 语句，同时兼容 SQLAlchemy 1.4 和 2.0：

```python
# 修改前（仅兼容 SQLAlchemy 1.x）
df = pd.read_sql(f"SELECT * FROM {table}", engine)

# 修改后（兼容 1.4 和 2.0）
from sqlalchemy import text
df = pd.read_sql(text(f"SELECT * FROM {table}"), engine)
```

如使用此方式，安装兼容版本：

```bash
pip install "pandas>=2.0" "SQLAlchemy>=2.0"
```

> **验证**：运行 `python -c "from sqlalchemy import text; print('OK')"` 无报错即正常。

---

### 8.5 依赖安装汇总

一键安装所有 Python 依赖（推荐使用锁定版本）：

```bash
cd sync
pip install -r requirements.txt
```

| 包 | 锁定版本 | 用途 | 备注 |
|----|---------|------|------|
| pandas | 1.5.3 | 数据清洗与 DataFrame 操作 | 1.5.x 最后稳定版，兼容 Python 3.8+ |
| numpy | 1.24.4 | 数值计算 | pandas 1.5.3 的依赖 |
| PyMySQL | 1.1.0 | Python → MySQL 连接驱动 | extract.py 使用 |
| psycopg2-binary | 2.9.9 | Python → YMatrix 连接驱动 | PostgreSQL 协议 |
| SQLAlchemy | 1.4.52 | ORM 引擎 | **必须 < 2.0**，否则 `pd.read_sql` 报错 |
