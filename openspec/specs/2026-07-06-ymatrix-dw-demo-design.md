
# YMatrix 端到端数仓 Demo 设计文档

> 创建日期: 2026-07-06
> 目标项目: D:\End-to-End-Data-Warehouse-Demo
> 关联 Skill: $ymatrix-dw-demo

---

## 1. 项目目标

构建一个从业务库到数仓分层再到 Grafana 报表展示的最小可运行 Demo，展示 YMatrix 在数仓场景中的完整使用方式。

**评分维度**: 可运行性 / 场景理解 / 工程完整度 / 测试与验证 / AI 使用能力 / 报告与表达

---

## 2. 架构总览

```
Docker Compose
├── MySQL (port 3306) — 业务库（5 表 + 种子数据）
├── YMatrix (port 5432) — 数仓引擎（四层 + DIM）
│   └── mxgate (port 8090) — 高性能写入
└── Grafana (port 3000) — 可视化仪表盘
     └── data source → YMatrix (PostgreSQL protocol)

ETL (Python):
  MySQL → pandas 清洗 → mxgate stdin → ODS
  ODS → SQL → DWD → 连续物化视图 → DWS → 视图 → ADS
```


### 2.2 init_all.sh 一键初始化脚本

```bash
#!/bin/bash
set -e

echo "=== Step 1: 启动 Docker 容器 ==="
docker-compose up -d

echo "=== Step 2: 等待服务就绪 ==="
# 等待 MySQL
until docker-compose exec -T mysql mysqladmin ping -uroot -proot --silent; do
    echo "Waiting for MySQL..."
    sleep 3
done
# 等待 YMatrix
until docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -c "SELECT 1;" 2>/dev/null; do
    echo "Waiting for YMatrix..."
    sleep 5
done

echo "=== Step 3: 初始化 YMatrix 数据库对象 ==="
for f in ymatrix/init/*.sql; do
    echo "Running $f"
    docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/$(basename $f)
done

echo "=== Step 4: 生成 MySQL 种子数据 ==="
cd sync && python gen_data.py && cd ..

echo "=== Step 5: 执行 ETL 全流程 ==="
cd sync && python sync_data.py && cd ..

echo "=== Step 6: 运行验证 ==="
cd sync && python verify.py && cd ..

echo "Grafana: http://localhost:3000 (admin/admin)"
```

### 2.1 数据流

1. Python 脚本从 MySQL 抽取全量数据（extract）
2. pandas 清洗：去空、类型标准化、衍生字段（transform）
3. mxgate --source stdin 灌入 ODS 层（load_ods）
4. TRUNCATE + mxgate 灌入 DIM 层（load_dim）
5. SQL INSERT INTO...SELECT... 执行 ODS → DWD 清洗（apply_dwd）
6. 连续物化视图自动刷新 DWS 层（YMatrix 自动）
7. ADS 视图封装最终指标（YMatrix 视图）
8. Grafana 直连 ADS 层出图

---

## 3. 业务库（MySQL）

### 3.1 表结构

| 表名 | 核心字段 | 预计行数 |
|------|---------|---------|
| users | user_id, name, email, register_date, city, status | 1,000 |
| products | product_id, product_name, category, price, stock | 500 (10+ 品类) |
| orders | order_id, user_id, order_date, status, total_amount, promo_id | 50,000 |
| order_items | item_id, order_id, product_id, qty, unit_price | 200,000 |
| payments | payment_id, order_id, method, pay_date, amount, status | 50,000 |
| dim_date | date_key, year, quarter, month, week, day_of_month, day_of_week, is_weekend, season | 1,096 (3年) |
| dim_region | region_id, province, city, district, region_tier | ~100 (省/市) |
| dim_promotion | promo_id, promo_name, promo_type, start_date, end_date | ~10 (大促活动) |

### 3.2 数据特征

**数据量级**:
| 表名 | 行数 | 说明 |
|------|------|------|
| users | 1,000 | 注册用户 |
| products | 500 | 10+ 品类，含电子/服装/美妆/食品/家居 |
| orders | 50,000 | 订单主表 |
| order_items | 200,000 | 明细行，每单约 4 件 |
| payments | 50,000 | 支付记录，与订单 1:1 |
| dim_date | 1,096 | 2023-2025 三年日期维度 |
| dim_region | ~100 | 中国主要省/市 |

**时间分布**: 2024-01-01 ~ 2024-12-31 全年

**促销峰值**: 11.1-11.10 预热期(日常 1.5x)，11.11 峰值(日常 5-8x，客单价更高，品类偏电子/美妆)，11.12-11.14 返场(2x)

**地域分布**: 北京/上海/广州/成都/武汉，覆盖华北/华东/华南/西南/华中

**商业特征**:
- 约 30% 用户产生 2 次以上购买（复购率）
- 品类 GMV 占比: 电子 30% / 服装 25% / 美妆 20% / 食品 15% / 家居 10%
- 订单支付率约 95%，支付方式含支付宝/微信/银行卡

---

## 4. 数仓分层设计 (YMatrix)

### 4.1 ODS 层（原始同步层）

引擎: **MARS3** | 压缩: lz4 level 7 | 分区: 按天 RANGE | 自动分区: 启用 APM

```sql
CREATE TABLE ods_orders (
    order_id      INT,
    user_id       INT,
    order_date    DATE,
    status        VARCHAR(20),
    total_amount  NUMERIC(10,2),
    promo_id      INT,
    sync_time     TIMESTAMP     -- 由 ETL 传入
) USING MARS3
WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (order_id)
ORDER BY (order_date, order_id)
PARTITION BY RANGE (order_date)
( START (date '2024-01-01') INCLUSIVE
  END (date '2025-01-01') EXCLUSIVE
  EVERY (INTERVAL '1 day') );
```

同模式: `ods_order_items`, `ods_payments`, `ods_users`, `ods_products`

### 4.2 DIM 层（维度表）

引擎: **HEAP**（SKILL.md 建议维表用 HEAP） | 无分区

| 表名 | 内容 | 来源 |
|------|------|------|
```sql
-- dim_date 日期维度表（generate_series 生成，覆盖 2023-2025）
CREATE TABLE dim_date (
    date_key      DATE,           -- 2024-01-01
    year          SMALLINT,       -- 2024
    quarter       SMALLINT,       -- 1-4
    month         SMALLINT,       -- 1-12
    week          SMALLINT,       -- ISO 周数
    day_of_month  SMALLINT,
    day_of_week   SMALLINT,       -- 1=周一, 7=周日
    is_weekend    BOOLEAN,
    season        VARCHAR(4)      -- 春/夏/秋/冬
) USING HEAP
DISTRIBUTED BY (date_key);

-- dim_region 地区维度表
CREATE TABLE dim_region (
    region_id     INT,
    province      VARCHAR(50),    -- 省
    city          VARCHAR(50),    -- 市
    district      VARCHAR(50),    -- 区（可选，可为 NULL）
    region_tier   VARCHAR(10)     -- 一线/二线/三线
) USING HEAP
DISTRIBUTED BY (region_id);

-- dim_promotion 促销维度表
CREATE TABLE dim_promotion (
    promo_id      INT,
    promo_name    VARCHAR(100),   -- "双11大促"
    promo_type    VARCHAR(20),    -- "预热" / "正式" / "返场"
    start_date    DATE,
    end_date      DATE
) USING HEAP
DISTRIBUTED BY (promo_id);

-- dim_product 商品维度表
CREATE TABLE dim_product (
    product_id    INT,
    product_name  VARCHAR(200),
    category      VARCHAR(50),
    price         NUMERIC(10,2)
) USING HEAP
DISTRIBUTED BY (product_id);

-- dim_user 用户维度表
CREATE TABLE dim_user (
    user_id       INT,
    user_name     VARCHAR(100),
    city          VARCHAR(50),
    status        VARCHAR(20),
    register_date DATE
) USING HEAP
DISTRIBUTED BY (user_id);

### 4.3 DWD 层（明细层）

两张事实表，引擎 **MARS3** | 压缩 lz4 level 7 | 按天分区

**dwd_order_fact**（粒度：一个订单一行）:
```sql
CREATE TABLE dwd_order_fact (
    order_id       INT,            -- 订单 ID
    user_id        INT,            -- 用户外键
    order_date     DATE,           -- 下单日期
    region_id      INT,            -- 地区外键
    promo_id       INT DEFAULT NULL, -- 促销外键
    total_amount   NUMERIC(10,2),  -- 最终金额（GMV）
    freight_amount NUMERIC(10,2) DEFAULT 0,  -- 运费
    discount_amount NUMERIC(10,2) DEFAULT 0, -- 优惠金额
    create_time    TIMESTAMP,      -- 下单时间
    pay_time       TIMESTAMP,      -- 支付时间
    cancel_time    TIMESTAMP,      -- 取消时间
    finish_time    TIMESTAMP,      -- 完成时间
    source_type    VARCHAR(20),    -- 订单来源(web/app/miniapp)
    status         VARCHAR(20)     -- 订单状态
) USING MARS3
WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (order_id)
ORDER BY (order_date, order_id)
PARTITION BY RANGE (order_date)
( START (date '2024-01-01') INCLUSIVE
  END (date '2025-01-01') EXCLUSIVE
  EVERY (INTERVAL '1 day') );
```

**dwd_order_detail_fact**（粒度：一个订单中一件商品一行）:
```sql
CREATE TABLE dwd_order_detail_fact (
    detail_id     INT,
    order_id      INT,
    user_id       INT,
    sku_id        INT,
    order_date    DATE,
    region_id     INT,
    promo_id      INT,
    sku_num       INT,
    original_price NUMERIC(10,2),
    final_price   NUMERIC(10,2),
    source_type   VARCHAR(20)
) USING MARS3
WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (detail_id)
ORDER BY (order_date, detail_id)
PARTITION BY RANGE (order_date)
( START (date '2024-01-01') INCLUSIVE
  END (date '2025-01-01') EXCLUSIVE
  EVERY (INTERVAL '1 day') );
```

### 4.4 DWS 层（汇总层）

遵循 SKILL.md 第5.3节推荐，改用标准**物化视图**（CREATE MATERIALIZED VIEW），ETL 完成后统一 REFRESH：

```sql
-- GMV 日汇总
CREATE MATERIALIZED VIEW dws_daily_gmv AS
SELECT date_trunc('day', order_date) AS dt,
       COUNT(*) AS order_count,
       SUM(total_amount) AS gmv,
       AVG(total_amount) AS avg_order_amount
FROM dwd_order_fact
GROUP BY dt
DISTRIBUTED BY (dt);

-- 商品日销售
CREATE MATERIALIZED VIEW dws_product_daily_sales AS
SELECT order_date, sku_id,
       SUM(sku_num) AS total_qty,
       SUM(sku_num * final_price) AS total_revenue
FROM dwd_order_detail_fact
GROUP BY order_date, sku_id
DISTRIBUTED BY (order_date);

-- 用户购买统计
CREATE MATERIALIZED VIEW dws_user_purchase_stats AS
SELECT user_id,
       COUNT(*) AS total_orders,
       SUM(total_amount) AS total_spent
FROM dwd_order_fact
GROUP BY user_id
DISTRIBUTED BY (user_id);
```

### 4.5 ADS 层（应用层）

视图封装，共 **7 个指标**：

```sql
-- ① 每日 GMV + 订单趋势（时间维度）
CREATE VIEW ads_daily_gmv AS
SELECT dt, order_count, gmv, avg_order_amount
FROM dws_daily_gmv ORDER BY dt;

-- ② 商品销售 Top 10（商品维度）
CREATE VIEW ads_top_products AS
SELECT p.product_name, p.category, d.total_qty, d.total_revenue
FROM (SELECT sku_id, SUM(total_qty) AS total_qty, SUM(total_revenue) AS total_revenue
      FROM dws_product_daily_sales GROUP BY sku_id ORDER BY total_revenue DESC LIMIT 10) d
JOIN dim_product p ON d.sku_id = p.product_id;

-- ③ 品类销售占比（品类维度 + 窗口函数）
CREATE VIEW ads_category_sales AS
SELECT p.category, SUM(d.total_revenue) AS revenue,
       SUM(d.total_revenue) * 100.0 / SUM(SUM(d.total_revenue)) OVER () AS pct
FROM dws_product_daily_sales d JOIN dim_product p ON d.sku_id = p.product_id
GROUP BY p.category ORDER BY revenue DESC;

-- ④ 用户复购率（用户维度 + FILTER 聚合）
CREATE VIEW ads_user_repurchase AS
SELECT COUNT(*) FILTER (WHERE total_orders > 1) * 100.0 / COUNT(*) AS repurchase_rate,
       COUNT(*) FILTER (WHERE total_orders > 1) AS repeat_buyers,
       COUNT(*) AS total_buyers
FROM dws_user_purchase_stats;

-- 7th indicator: User segment (RFM simplified)
CREATE VIEW ads_user_segment AS
SELECT CASE
    WHEN total_orders >= 10 OR total_spent >= 5000 THEN 'high'
    WHEN total_orders >= 3  OR total_spent >= 1000 THEN 'mid'
    ELSE 'low'
END AS segment,
COUNT(*) AS user_count,
SUM(total_orders) AS total_orders
FROM dws_user_purchase_stats
GROUP BY 1 ORDER BY 1;

-- ⑤ 区域分布 GMV（地域维度）
CREATE VIEW ads_gmv_by_region AS
SELECT r.province, COUNT(DISTINCT f.order_id) AS order_cnt, SUM(f.total_amount) AS gmv
FROM dwd_order_fact f JOIN dim_region r ON f.region_id = r.region_id
GROUP BY r.province ORDER BY gmv DESC;

-- ⑥ 促销 vs 日常对比（促销维度）
CREATE VIEW ads_promo_compare AS
SELECT CASE WHEN o.promo_id IS NOT NULL THEN '大促期' ELSE '日常期' END AS period,
       COUNT(DISTINCT o.order_id) AS order_cnt,
       SUM(o.total_amount) AS gmv,
       SUM(o.total_amount) / COUNT(DISTINCT o.order_id) AS avg_order_value
FROM dwd_order_fact o GROUP BY 1;
```

---

## 5. 数据同步 (ETL)
### 4.6 ETL 审计表

记录全链路每步耗时，用于报告展示：

```sql
CREATE TABLE etl_log (
    log_id        BIGSERIAL,
    step          VARCHAR(50),
    status        VARCHAR(20),
    rows_processed INT,
    duration_ms   INT,
    message       TEXT,
    log_time      TIMESTAMP DEFAULT current_timestamp
) USING MARS3
DISTRIBUTED BY (log_id)
ORDER BY (log_time);
```


### 4.8 DWD 字段来源说明

> 修复项 M2: dwd_order_fact 中 4 个字段在 MySQL 源表不存在，由 ETL 的 transform.py 生成

| DWD 字段 | 来源 | 生成逻辑 |
|---------|------|---------|
| freight_amount | transform.py 衍生 | 订单金额 >= 200 免运费(0)，否则随机 8-15 元 |
| discount_amount | transform.py 衍生 | 促销期内随机 5-30 元优惠券抵扣，日常期为 0 |
| source_type | transform.py 衍生 | 按概率分配: web=30%, app=50%, miniapp=20% |
| region_id | transform.py 关联 | 从 users.city 关联 dim_region，通过城市名映射到 region_id |

### 4.7 HEAP 压缩率对照表

仅用于 verify 脚本，同结构 HEAP 表对照 MARS3 压缩效果：

```sql
CREATE TABLE ods_orders_heap (
    order_id INT, user_id INT, order_date DATE,
    status VARCHAR(20), total_amount NUMERIC(10,2),
    promo_id INT, sync_time TIMESTAMP
) USING HEAP
DISTRIBUTED BY (order_id);
```

---

## 5. 数据同步 (ETL)


### 5.1 ETL 幂等性设计（E1 修复）

sync_data.py 保证幂等性（可安全重跑）:

1. **ODS 层** — 每次加载前执行 TRUNCATE 对应 ODS 分区:
   ```python
   conn.execute("TRUNCATE ods_orders;")
   conn.execute("TRUNCATE ods_orders CASCADE;")  # 跳过分区直接清理
   ```
   或使用 DELETE WHERE sync_time >= today 做增量幂等。

2. **DIM 层** — TRUNCATE + mxgate 本身就是幂等（全量刷新）:
   ```python
   conn.execute("TRUNCATE dim_user CASCADE;")
   conn.execute("TRUNCATE dim_product CASCADE;")
   # 然后 mxgate 写入最新数据
   ```

3. **DWD 层** — TRUNCATE 后 INSERT INTO...SELECT:
   ```python
   conn.execute("TRUNCATE dwd_order_fact CASCADE;")
   conn.execute("TRUNCATE dwd_order_detail_fact CASCADE;")
   # 然后执行 ODS->DWD ETL
   ```

4. **DWS 层** — REFRESH MATERIALIZED VIEW 是幂等的（覆盖式刷新）

5. **失败恢复**: 每一步用 try/except 包裹，失败时记录 etl_log 并终止后续步骤。
   人工修复后重新执行 sync_data.py 从头开始。

### 5.1 架构

```
sync/
├── sync_data.py        ← 主入口，编排全流程
├── gen_data.py         ← 生成业务数据（MySQL init）
├── extract.py          ← MySQL → pandas DataFrame
├── transform.py        ← 清洗/标准化/衍生字段
├── load_ods.py         ← DataFrame → mxgate stdin → ODS
├── load_dim.py         ← TRUNCATE + mxgate → DIM
├── load_dwd.py         ← SQL INSERT INTO...SELECT... → DWD
├── verify.py           ← 验证 + etl_log 写入
└── requirements.txt
```


### 5.4 transform.py 清洗规则（E3 修复）

| 处理类型 | 规则 | 说明 |
|---------|------|------|
| 空值处理 | 必填字段为 NULL → 跳过该行并记录 etl_log | order_id / user_id / order_date 不能为空 |
| | 可选字段为 NULL → 填默认值 | promo_id→0, freight_amount→0 |
| 类型标准化 | 日期统一为 DATE 格式 | MySQL 可能返回 datetime，强制转 DATE |
| | 金额四舍五入到 2 位小数 | NUMERIC(10,2) 约束 |
| | 状态值映射 | MySQL 存储 0/1 → YMatrix 存储 'paid'/'cancelled' 等 |
| | 时间戳统一为 TIMESTAMP | sync_time 用 Python 当前时间填充 |
| 衍生字段 | freight_amount / discount_amount / source_type / region_id | 见 §4.8 规则 |
| 去重 | 对 ODS 源数据按主键去重 | 防止重复同步 |

### 5.2 mxgate 写入示例

```python
import subprocess, csv, io
buf = io.StringIO()
writer = csv.writer(buf)
for _, row in df.iterrows():
    writer.writerow(row.tolist())

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


### 3.5 ODS→DWD ETL SQL（E4 修复）

load_dwd.py 执行的 SQL 逻辑:

```sql
-- orders ETL: ODS -> DWD
TRUNCATE dwd_order_fact CASCADE;

INSERT INTO dwd_order_fact (
    order_id, user_id, order_date, region_id, promo_id,
    total_amount, freight_amount, discount_amount,
    create_time, pay_time, cancel_time, finish_time,
    source_type, status
)
SELECT
    o.order_id,
    o.user_id,
    o.order_date,
    COALESCE(r.region_id, 0) AS region_id,      -- 通过用户城市关联
    COALESCE(o.promo_id, 0) AS promo_id,
    o.total_amount,
    0 AS freight_amount,                          -- 由 transform.py 填充
    0 AS discount_amount,                         -- 由 transform.py 填充
    o.order_date::TIMESTAMP AS create_time,
    CASE WHEN o.status IN ('paid','shipped','completed') THEN o.order_date::TIMESTAMP ELSE NULL END AS pay_time,
    CASE WHEN o.status = 'cancelled' THEN o.order_date::TIMESTAMP ELSE NULL END AS cancel_time,
    CASE WHEN o.status = 'completed' THEN o.order_date::TIMESTAMP + INTERVAL '2 days' ELSE NULL END AS finish_time,
    'web' AS source_type,                         -- 由 transform.py 填充
    o.status
FROM ods_orders o
LEFT JOIN ods_users u ON o.user_id = u.user_id
LEFT JOIN dim_region r ON u.city = r.city       -- 通过城市名关联地域
WHERE o.status IS NOT NULL;                      -- 过滤脏数据

-- order_items ETL: ODS -> DWD
TRUNCATE dwd_order_detail_fact CASCADE;

INSERT INTO dwd_order_detail_fact (
    detail_id, order_id, user_id, sku_id, order_date,
    region_id, promo_id, sku_num, original_price, final_price, source_type
)
SELECT
    oi.item_id,
    oi.order_id,
    o.user_id,
    oi.product_id AS sku_id,
    o.order_date,
    0 AS region_id,                              -- 由 transform.py 填充
    COALESCE(o.promo_id, 0) AS promo_id,
    oi.qty AS sku_num,
    oi.unit_price AS original_price,
    oi.unit_price * (1 - COALESCE(p.discount_rate, 0)) AS final_price,
    'web' AS source_type
FROM ods_order_items oi
JOIN ods_orders o ON oi.order_id = o.order_id
LEFT JOIN dim_promotion p ON o.promo_id = p.promo_id AND o.order_date BETWEEN p.start_date AND p.end_date
WHERE o.status IS NOT NULL;
```

### 5.3 ETL 日志

每步写入 `etl_log` 表，最终 `SELECT * FROM etl_log` 展示全链路耗时。

---

## 6. YMatrix 特性展示清单

| # | 特性 | 展示位置 | 展示方式 |
|---|------|---------|---------|
| 1 | MARS3 引擎 | 全部 DDL | "USING MARS3" 关键字 |
| 2 | lz4 压缩 | ODS/DWD/DIM DDL | compresstype + compresslevel |
| 3 | RANGE 分区 | ODS/DWD 建表 | PARTITION BY RANGE |
| 4 | 自动分区管理 APM | 初始化脚本 | apm_enable_partition_maintenance() |
| 5 | 连续物化视图 | DWS 层 DDL | CREATE VIEW WITH (CONTINUOUS) |
| 6 | mxgate 写入 | sync/load_ods.py | --parallel 256 --source stdin |
| 7 | DISTRIBUTED BY + ORDER BY | 全部 DDL | 数据分布策略 |
| 8 | mysql_fdw 联邦查询 | fdw.sql | CREATE FOREIGN TABLE 跨库 JOIN |
| 9 | Grafana + Prometheus | docker-compose | 预置 Dashboard |
| 10 | date_trunc 聚合 | dws_daily_gmv / ads_daily_gmv | 标准 PostgreSQL 日期聚合 |
| 11 | 压缩率对比 | verify/compression.sql | MARS3 vs HEAP 表大小 |
| 12 | HEAP 引擎对照 | verify/ | 同数据 HEAP 表作对照 |

---

## 7. Grafana Dashboard

### 7.1 面板设计（6 个面板）

| 面板 | 类型 | 数据源 (ADS) | 展示维度 |
|------|------|-------------|---------|
| 每日 GMV 趋势 | 时间序列折线图 | ads_daily_gmv | 时间 |
| 商品销售 Top 10 | 表格 | ads_top_products | 商品 |
| 品类销售占比 | 饼图 | ads_category_sales | 品类 |
| 用户复购率 | 单值 Stat | ads_user_repurchase | 用户 |
| GMV 按省份分布 | 树图/Treemap | ads_gmv_by_region | 地域 |
| 促销 vs 日常 GMV | 柱状图 | ads_promo_compare | 促销 |


> S3 建议: YMatrix 自身也提供 Grafana 集群监控面板（QPS、Segment 负载、写入速率），
> 可在 Grafana 中添加 YMatrix 官方 dashboard JSON，作为额外展示亮点。
> 详见 SKILL.md §8.1: https://ymatrix.cn/zh/doc/6.8/monitor/grafana_installation


### 6.1 mysql_fdw DDL（I4 修复）

```sql
CREATE EXTENSION IF NOT EXISTS mysql_fdw;
CREATE SERVER mysql_ecommerce FOREIGN DATA WRAPPER mysql_fdw
    OPTIONS (host 'mysql', port '3306', dbname 'ecommerce');
CREATE USER MAPPING FOR mxadmin SERVER mysql_ecommerce
    OPTIONS (username 'root', password 'root');
CREATE FOREIGN TABLE fdw_orders (...) SERVER mysql_ecommerce
    OPTIONS (dbname 'ecommerce', table_name 'orders');
```
### 7.2 预置配置

```yaml
# grafana/datasources/ymatrix.yaml
apiVersion: 1
datasources:
  - name: YMatrix
    type: postgres
    url: ymatrix:5432
    database: dw_demo
    user: mxadmin
    secureJsonData:
      password: ""
```

Dashboard JSON 预生成放入 `grafana/dashboards/`，容器启动自动加载。

---

## 8. Docker Compose
### 8.1 镜像构建说明（B1 更新：Ubuntu .deb）

YMatrix 社区版（v5.2.1）以 .deb 包形式提供。

```dockerfile
FROM ubuntu:20.04
COPY matrixdb5_5.2.1+community-1_amd64.deb /tmp/
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y         /tmp/matrixdb5_5.2.1+community-1_amd64.deb &&     rm -f /tmp/matrixdb5_5.2.1+community-1_amd64.deb &&     apt-get clean &&     rm -rf /var/lib/apt/lists/* &&     chmod +x /docker-entrypoint.sh
EXPOSE 5432 8090
ENTRYPOINT ["/docker-entrypoint.sh"]
```

MD5 校验（下载后验证完整性）:
```bash
certutil -hashfile ymatrix/matrixdb5_5.2.1+community-1_amd64.deb MD5
# 期望值: 4e4ac2df9792d1ef91628525f4f30614
```

```yaml
services:
  mysql:
    image: mysql:8.0
    ports:
      - "3306:3306"
    volumes:
      - "./mysql/init.sql:/docker-entrypoint-initdb.d/init.sql"
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: ecommerce
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-uroot", "-proot", "--silent"]
      interval: 10s
      timeout: 5s
      retries: 5

  ymatrix:
    build:
      context: ./ymatrix
      dockerfile: Dockerfile
    ports:
      - "5432:5432"
      - "8090:8090"
    volumes:
      - "./ymatrix/init:/docker-entrypoint-initdb.d"
      - ym-data:/var/lib/matrixdb
    environment:
      MATRIXDB_DB: dw_demo
      MATRIXDB_USER: mxadmin
      PGPORT: 5432

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - "./grafana/datasources:/etc/grafana/provisioning/datasources"
      - "./grafana/dashboards:/etc/grafana/provisioning/dashboards"
    depends_on:
      ymatrix:
        condition: service_started

volumes:
  ym-data:
```

---

## 9. 工程文件清单

```
D:\End-to-End-Data-Warehouse-Demo\
├── docker-compose.yml
├── init_all.sh                    # 一键初始化入口
├── README.md
├── report.md
├── ai_usage.md
├── docs/
│   └── supplementary.md
│
├── mysql/
│   └── init.sql                   # 建表 + 种子数据
│
├── ymatrix/
│   ├── Dockerfile                 ← 基于 minimal install 构建镜像
│   ├── 01_init.sql                ← 创建 ext, APM, dim_date 生成
│   ├── 02_ods.sql                 ← ODS 5 表 DDL
│   ├── 03_dim.sql  -> DIM 5 表 DDL（I2 修复）
│   ├── 03_dwd.sql                 ← DWD 2 事实表 DDL
│   ├── 04_dws.sql                 ← 连续物化视图 DDL
│   ├── 05_ads.sql                 ← ADS 视图 DDL
│   ├── 06_fdw.sql                 ← mysql_fdw（附加）
│   └── verify/
│       └── 01_compression.sql     ← MARS3 vs HEAP 压缩率对比
│
├── sync/
│   ├── sync_data.py               # [入口] 编排全流程
│   ├── gen_data.py                # 生成业务数据
│   ├── extract.py                 # MySQL → DataFrame
│   ├── transform.py               # 清洗逻辑
│   ├── load_ods.py                # mxgate 灌 ODS
│   ├── load_dim.py                # mxgate 灌 DIM
│   ├── load_dwd.py                # SQL ETL → DWD
│   └── requirements.txt
│

### 5.6 Python 依赖（I3 修复）

```txt
pandas>=1.5.0
PyMySQL>=1.0.0
psycopg2-binary>=2.9.0
```

├── grafana/
│   ├── datasources/ymatrix.yaml
│   └── dashboards/ymatrix_dw_demo.json
│
├── screenshots/                   # 运行结果截图
│   └── ...png
│
├── openspec/
│   └── specs/
│       └── 2026-07-06-ymatrix-dw-demo-design.md  ← 本文件
│
└── data/                          # Docker volumes（gitignored）
```

---

## 10. 验证与验收标准（I5 修复：补充具体断言值）
### 10.1 具体验证断言值（I5 修复）

| 检查项 | 预期值 |
|--------|-------|
| MySQL: users | 1000 行 |
| MySQL: products | 500 行 |
| MySQL: orders | 50000 行 |
| MySQL: order_items | 200000 行 |
| MySQL: payments | 50000 行 |
| ODS 行数 = MySQL 行数 | 严格相等 |
| ads_daily_gmv | 365 行，可见双11波峰 |
| ads_top_products | 10 行，revenue > 0 |
| ads_category_sales | 5 行，pct 之和 ≈ 100% |
| ads_user_repurchase | repurchase_rate ≈ 30% |
| ads_gmv_by_region | 5 行，非空 |
| ads_promo_compare | 2 行，大促期 GMV > 日常期 |
| ads_user_segment | 3 个分层 |
| MARS3 vs HEAP 压缩率 | MARS3 至少节省 50% 空间 |
| Grafana 面板 | 7 个面板，数据非空 |
| etl_log | 全链路分步耗时记录 |



| 检查项 | 验证方式 |
|--------|---------|
| 一键初始化 | `docker-compose up -d && bash init_all.sh` 执行成功 |
| MySQL 5 表 | `SELECT COUNT(*) FROM ...` 数据正确 |
| YMatrix 4 层完整 | `\dt` 显示 ODS/DWD/DWS/ADS 表 |
| 7 个指标数据正确 | `SELECT * FROM ads_*` 数值合理 |
| 压缩率展示 | MARS3 vs HEAP `pg_size_pretty` 对比有截图 |
| Grafana 面板 | 3000 端口打开显示 6 个面板，数据非空 |
| mysql_fdw | `SELECT ... FROM mysql_orders JOIN ym订单` 成功 |
| etl_log 完整 | `SELECT * FROM etl_log` 显示全链路耗时 |

---

## 11. 设计决策记录

| 决策 | 选项 | 选择理由 |
|------|------|---------|
| 数仓引擎 | YMatrix | 项目核心目标 |
| 业务库 | MySQL | 真实电商场景，mysql_fdw 可展示 |
| 可视化 | Grafana | 零代码，预置 Dashboard，客户认可度高 |
| 同步方式 | Python + mxgate | 展示 mxgate 高性能，复杂度可控 |
| 存储引擎 | 全 MARS3 | 统一展示列存能力，DIM 表也用 MARS3 |
| 物化视图 | 连续物化视图 | 自动刷新，无需 REFRESH 调度 |
| DWS 策略 | 先打平 DWD 宽表 + 单表连续 MV | 绕过连续 MV 不支持多表 JOIN 的限制 |
| 数据量 | 50K 订单 / 200K 明细 | 分区裁剪有效，Grafana 曲线有波峰 |
| 双11 场景 | 加 dim_promotion + promo_id | 极小改动，极大提升 Demo 叙事效果 |
| 压缩率验证 | ods_orders_heap 对照表 | verify 脚本 + report 截图 |
| time_bucket | DWS 层使用 | 1 行 SQL 展示 YMatrix 时序函数 |
| CREATE VIEW WITH (CONTINUOUS) | 改为标准物化视图 | B2: SKILL.md §5.3 使用 MATERIALIZED VIEW + REFRESH |
| DIM 引擎选择 | MARS3 -> HEAP | M1: SKILL.md 建议维表用 HEAP |
| 复购率字段 | is_repeat_buyer -> total_orders | M4: 存计数保灵活 |
| season 编码 | SMALLINT -> VARCHAR | S2: 文字编码可读性高 |
| time_bucket | 改用 date_trunc | M5: DATE 类型无需 time_bucket |
| DIM 刷新策略 | TRUNCATE + mxgate | S4: 维表<1000行，全量刷新最简单可靠 |
| ETL 幂等性 | TRUNCATE + REFRESH | E1: 可安全重跑，不重复不丢数据 |
| Docker base | ubuntu:20.04 + .deb 包 | B1 更新: 使用 matrixdb5_5.2.1 社区版 .deb 安装 |
| dim_user 数据源 | 从 ODS ods_users 去重后写入 | M3: 统一 ETL 管线，无需额外 MySQL 直读 |
| 清洗规则 | transform.py 定义完整规则 | E3: 空值/类型/衍生字段全覆盖 |
| ODS->DWD SQL | load_dwd.py 定义完整 JOIN | E4: 字段映射 + 清洗条件 + 关联关系 |
| 衍生字段 | transform.py 生成 | M2: 明确4个字段的生成规则 |

---


## 12. 数据质量保证
### 12.1 数据一致性校验（Q1 修复）

```sql
-- order_items 总额应与 orders 总额一致
SELECT COUNT(*) AS mismatches FROM (
    SELECT order_id, SUM(qty * unit_price) AS items_total
    FROM ods_order_items GROUP BY order_id
) items JOIN ods_orders o USING (order_id)
WHERE items_total != o.total_amount;
```


### 12.1 数据一致性校验（Q1 修复）

即使是最小 Demo，也应包含基本的数据交叉校验:

```sql
-- 校验1: order_items 总额 == orders 总额（按 order_id 聚合）
SELECT COUNT(*) AS mismatched_orders FROM (
    SELECT oi.order_id, SUM(oi.qty * oi.unit_price) AS items_total
    FROM ods_order_items oi GROUP BY oi.order_id
) items
JOIN ods_orders o ON items.order_id = o.order_id
WHERE items.items_total != o.total_amount;

-- 校验2: 支付记录与订单状态一致
SELECT COUNT(*) AS invalid_payments FROM ods_payments p
JOIN ods_orders o ON p.order_id = o.order_id
WHERE p.status = '"'"'success'"'"' AND o.status IN ('"'"'cancelled'"'"', '"'"'pending'"'"');

-- 校验3: 用户不重复
SELECT COUNT(*) - COUNT(DISTINCT user_id) AS duplicate_users FROM ods_users;
```

预期: 所有校验返回 0 行（无不一致）。

## 12. 非目标（明确不做的）

- ✅ Domino 流计算引擎 → 批处理场景不匹配
- ✅ 自动降级存储到 S3 → 需要外部基础设施
- ✅ MatrixUI 运维面板 → 偏离"数仓端到端"展示主线
- ✅ ORCA 优化器展示 → 默认开启，不可见，report 提一句即可
- ✅ 滑动窗口 → 流计算范畴，同上
- ✅ UPSERT 写入 → mxgate 参数提及，不另设场景
- ✅ 单元测试 → Demo 项目规模，验证以集成测试为主
- ✅ 数据脱敏/安全/加密 → 不在展示范围内
- ✅ 集群扩缩容/HA → 单节点 Docker Demo

## 13. 交付物文档框架

### 13.1 report.md 内容框架（D1 修复）

```
# YMatrix 数仓端到端 Demo 报告

## 1. 架构概览
## 2. 数据规模
## 3. ETL 执行报告
## 4. 业务指标结果
## 5. YMatrix 特性展示
## 6. Grafana 面板
```

### 13.2 ai_usage.md 内容框架（D2 修复）

```
# AI 使用记录
## 使用的 AI 工具: Codex (GPT-5)
## Prompt 摘要
## 生成的代码清单
## 人工修正的内容（留空）
## 经验教训（留空）
```

### 13.3 screenshots/ 目录截图清单（D3 修复）

| # | 截图内容 | 文件命名 |
|---|---------|---------|
| 1 | Grafana 面板全览 | grafana_dashboard.png |
| 2 | 压缩率对比 | compression_ratio.png |
| 3 | ETL 日志 | etl_log.png |
| 4 | ADS 七大指标查询 | ads_metrics.png |

### 13.4 verify/01_compression.sql 内容（D4 修复）

```sql
SELECT 'MARS3' AS engine,
       pg_size_pretty(pg_total_relation_size('ods_orders')) AS total_size
UNION ALL
SELECT 'HEAP' AS engine,
       pg_size_pretty(pg_total_relation_size('ods_orders_heap'));
```

