# YMatrix 数仓端到端 Demo

## 1. 项目目标

构建一个从**业务库（MySQL）到数仓分层（YMatrix）再到可视化仪表盘（Grafana）**的最小可运行 Demo，完整展示 YMatrix 在数据仓库场景中的核心优势：

- **MARS3 行列混存引擎**：lz4 压缩，相比 HEAP 行存节省 83%+ 存储
- **mxgate 高性能写入**：直连 Segment 并行写入，20 万订单全链路 ETL 约 80 秒
- **time_bucket 时序聚合**：分钟级流量、双11累计 GMV 窗口函数
- **MPP 分布式架构**：DISTRIBUTED BY + ORDER BY + RANGE 分区
- **物化视图预聚合**：标准 MATERIALIZED VIEW + REFRESH，7 个 DWS 预聚合
- **五层数仓架构**：ODS → DIM → DWD → DWS → ADS，分层清晰

**评分维度**: 可运行性 / 场景理解 / 工程完整度 / 测试与验证 / AI 使用能力 / 报告与表达

---

## 2. 环境依赖

### 2.1 主机要求

| 组件 | 最低版本 | 用途 | 下载 |
|------|---------|------|------|
| **Docker Desktop** | 4.20+ (引擎 24.0+) | 容器编排 MySQL + YMatrix + Grafana | [下载](https://www.docker.com/products/docker-desktop/) |
| **Git** | 2.30+ | 克隆仓库、运行 init_all.sh | [下载](https://git-scm.com/) |
| **Python** | 3.8+ | ETL 脚本（extract/transform/load/verify） | [下载](https://www.python.org/) |

> **说明**：MySQL 8.0、YMatrix 5.2.1、Grafana 均运行在 Docker 容器中，无需主机单独安装。Python 仅用于运行 ETL 脚本。

### 2.2 Python 依赖

```bash
pip install pandas numpy PyMySQL psycopg2-binary sqlalchemy
```

依赖清单见 [sync/requirements.txt](sync/requirements.txt)。

### 2.3 Docker 资源建议

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+ |
| 磁盘 | 5 GB | 10 GB+（含 YMatrix RPM 包 364MB + 容器镜像） |

### 2.4 YMatrix 镜像构建

本 Demo 的 YMatrix 镜像需要从 RPM 包构建（首次约 5 分钟，之后缓存）：

```bash
docker-compose build ymatrix
```

> YMatrix 安装包已包含在仓库中：`ymatrix/matrixdb5-5.2.1+community-1.el7.x86_64.rpm`（364MB）

---

## 3. 安装步骤

### 3.1 克隆仓库

```bash
git clone https://github.com/liuxinyi-sys/End-to-End-Data-Warehouse-Demo.git
cd End-to-End-Data-Warehouse-Demo
```

### 3.2 构建YMatrix 镜像（首次运行）

```bash
docker-compose build ymatrix
```

此步骤基于 `ymatrix/Dockerfile`，从 `matrixdb/centos7_demo` 基础镜像安装 YMatrix 5.2.1 社区版 RPM 包。构建完成后镜像名为 `ymatrix5.2-clean:latest`。

> 首次构建约 5 分钟，后续直接使用缓存镜像。

### 3.3 启动三容器

```bash
docker-compose up -d
```

Docker Compose 会启动三个容器：

| 容器 | 镜像 | 端口 | 健康检查 |
|------|------|------|---------|
| e2e-mysql | mysql:8.0 | 3306 | mysqladmin ping |
| e2e-ymatrix | ymatrix5.2-clean:latest | 5432 | psql SELECT 1 |
| e2e-grafana | grafana/grafana:latest | 3000 | /api/health |

等待全部健康（约 30-60 秒）：

```bash
docker-compose ps
```

确认三个容器状态均为 `Up (healthy)`。

### 3.4 一键初始化数仓

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
# 1. 生成种子数据
cd sync && python gen_data.py && cd ..

# 2. 加载 CSV 到 MySQL
docker-compose exec -T mysql mysql --local-infile=1 -uroot -proot -e "SET GLOBAL local_infile=1;"
docker-compose exec -T mysql mysql --local-infile=1 -uroot -proot -D ecommerce -e "LOAD DATA LOCAL INFILE '/dev/stdin' INTO TABLE users FIELDS TERMINATED BY ',' LINES TERMINATED BY '\n';" < sync/seed_users.csv
# ... 其他表同理

# 3. 创建 YMatrix schema
for f in ymatrix/init/*.sql; do
    docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -v ON_ERROR_STOP=1 -f "/docker-entrypoint-initdb.d/$(basename $f)"
done

# 4. 执行 ETL
cd sync && python sync_data.py && cd ..

# 5. 验证
cd sync && python verify.py && cd ..
```

### 5.4 彻底重来

```bash
docker-compose down -v
docker-compose up -d
bash init_all.sh
```

### 5.5 SQL 查询示例

```bash
# 查看 YMatrix 所有表
docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -c "\dt"

# 查看双11累计 GMV
docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -c "SELECT * FROM ads_gmv_running_total ORDER BY bucket_time LIMIT 10;"

# 查看 MySQL 业务库行数
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e "SELECT 'orders', COUNT(*) FROM orders UNION ALL SELECT 'order_status_events', COUNT(*) FROM order_status_events;"
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
