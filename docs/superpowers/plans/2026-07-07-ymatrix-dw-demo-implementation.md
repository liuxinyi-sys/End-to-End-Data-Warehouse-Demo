# YMatrix DW Demo 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现设计文档中从 MySQL 业务库到 YMatrix 数仓分层再到 Grafana 仪表盘的完整端到端 Demo

**Architecture:** Docker Compose 三容器编排（MySQL + YMatrix + Grafana），Python ETL 通过 mxgate stdin 写入 ODS/DIM 层，SQL ETL 写入 DWD 层并 REFRESH 物化视图

**Tech Stack:** MySQL 8.0, YMatrix 5.2.1 (MARS3+HEAP), Grafana, Python 3.8+, pandas, mxgate

---

## 范围检查

设计文档涵盖单一端到端项目，所有子系统相互依赖形成一条完整流水线，适合一个计划多个阶段。

**已存在的文件**: docker-compose.yml, ymatrix/Dockerfile, ymatrix/docker-entrypoint.sh, docs/supplementary.md, AGENTS.md

**需创建的文件**: 共 16 个任务（MySQL -> YMatrix 模式 -> ETL 管线 -> Grafana -> Init -> 文档）

---
## 阶段 1: MySQL 业务数据库

### Task 1: 创建 MySQL 初始化 SQL（建表 + 种子数据）

**Files:**
- Create: `mysql/init.sql`

- [ ] **Step 1: 创建 mysql/init.sql**

```sql
DROP TABLE IF EXISTS payments, order_items, orders, products, users, dim_promotion, dim_region, dim_date;

CREATE TABLE users (
    user_id       INT PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(200) NOT NULL,
    register_date DATE NOT NULL,
    city          VARCHAR(50) NOT NULL,
    province      VARCHAR(50) NOT NULL,
    status        VARCHAR(20) DEFAULT "active"
);

CREATE TABLE products (
    product_id   INT PRIMARY KEY AUTO_INCREMENT,
    product_name VARCHAR(200) NOT NULL,
    category     VARCHAR(50) NOT NULL,
    price        DECIMAL(10,2) NOT NULL,
    stock        INT DEFAULT 0
);

CREATE TABLE orders (
    order_id     INT PRIMARY KEY AUTO_INCREMENT,
    user_id      INT NOT NULL,
    order_date   DATE NOT NULL,
    status       VARCHAR(20) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    promo_id     INT DEFAULT NULL
);

CREATE TABLE order_items (
    item_id    INT PRIMARY KEY AUTO_INCREMENT,
    order_id   INT NOT NULL,
    product_id INT NOT NULL,
    qty        INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL
);

CREATE TABLE payments (
    payment_id  INT PRIMARY KEY AUTO_INCREMENT,
    order_id    INT NOT NULL,
    method      VARCHAR(20) NOT NULL,
    pay_date    DATE NOT NULL,
    amount      DECIMAL(10,2) NOT NULL,
    status      VARCHAR(20) DEFAULT "completed"
);

CREATE TABLE dim_date (
    date_key      DATE PRIMARY KEY,
    year          SMALLINT NOT NULL,
    quarter       SMALLINT NOT NULL,
    month         SMALLINT NOT NULL,
    week          SMALLINT NOT NULL,
    day_of_month  SMALLINT NOT NULL,
    day_of_week   SMALLINT NOT NULL,
    is_weekend    BOOLEAN DEFAULT FALSE,
    season        VARCHAR(4) NOT NULL
);

CREATE TABLE dim_region (
    region_id   INT PRIMARY KEY AUTO_INCREMENT,
    province    VARCHAR(50) NOT NULL,
    city        VARCHAR(50) NOT NULL,
    district    VARCHAR(50) DEFAULT NULL,
    region_tier VARCHAR(10) NOT NULL
);

CREATE TABLE dim_promotion (
    promo_id      INT PRIMARY KEY AUTO_INCREMENT,
    promo_name    VARCHAR(100) NOT NULL,
    promo_type    VARCHAR(20) NOT NULL,
    start_date    DATE NOT NULL,
    end_date      DATE NOT NULL,
    discount_rate DECIMAL(3,2) DEFAULT 0
);
```
- [ ] **Step 2: 验证 MySQL 初始化**

```bash
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce < mysql/init.sql
docker-compose exec mysql mysql -uroot -proot -D ecommerce -e "SELECT table_name FROM information_schema.tables WHERE table_schema='ecommerce';"
```

Expected: 8 tables created (users, products, orders, order_items, payments, dim_date, dim_region, dim_promotion)

---

### Task 2: 创建种子数据生成器 gen_data.py

**Files:**
- Create: `sync/gen_data.py`

- [ ] **Step 1: 创建 sync/gen_data.py**

```python
"""Generate seed data SQL files for MySQL business database."""
import random
import os

random.seed(42)

def gen_users(num=1000):
    cities = [
        ("北京","北京市"), ("上海","上海市"), ("广州","广东省"),
        ("深圳","广东省"), ("成都","四川省"), ("武汉","湖北省"),
        ("杭州","浙江省"), ("南京","江苏省"), ("西安","陕西省"), ("重庆","重庆市"),
    ]
    vals = []
    for i in range(1, num+1):
        city, prov = random.choice(cities)
        vals.append(f"({i},'user_{i}','user{i}@email.com',"
                    f"DATE_ADD('2023-01-01',INTERVAL {random.randint(0,365)} DAY),"
                    f"'{city}','{prov}','active')")
    sql = "INSERT INTO users VALUES\n" + ",\n".join(vals) + ";"
    with open("seed_users.sql","w",encoding="utf-8") as f: f.write(sql)
    print(f"users: {num} rows")

def gen_products(num=500):
    cats = ["电子","服装","美妆","食品","家居"]
    brands = {
        "电子":["华为","小米","Apple","OPPO","vivo"],
        "服装":["Nike","Adidas","优衣库","ZARA","H&M"],
        "美妆":["雅诗兰黛","兰蔻","SK-II","欧莱雅","资生堂"],
        "食品":["三只松鼠","良品铺子","百草味","来伊份","恰恰"],
        "家居":["宜家","MUJI","网易严选","小米有品","名创优品"],
    }
    prods = ["手机","平板","笔记本","耳机","充电器","T恤","牛仔裤","外套","运动鞋",
             "帽子","精华液","面霜","眼霜","面膜","洗面奶","坚果礼盒","肉干","果脯",
             "饼干","巧克力","台灯","收纳盒","毛巾","拖鞋","靠垫"]
    vals = []
    pid = 1
    for cat in cats:
        for _ in range(num // len(cats)):
            brand = random.choice(brands[cat])
            prod = random.choice(prods)
            price = round(random.uniform(19.9, 9999.0), 2)
            stock = random.randint(10, 5000)
            vals.append(f"({pid},'{brand} {prod}','{cat}',{price},{stock})")
            pid += 1
    sql = "INSERT INTO products VALUES\n" + ",\n".join(vals) + ";"
    with open("seed_products.sql","w",encoding="utf-8") as f: f.write(sql)
    print(f"products: {len(vals)} rows")

def gen_orders(num=50000):
    order_vals, item_vals, pay_vals = [], [], []
    item_id, pay_id = 1, 1
    for oid in range(1, num+1):
        uid = random.randint(1, 1000)
        day = random.randint(0, 365)
        od = f"DATE_ADD('2024-01-01',INTERVAL {day} DAY)"
        doy = day + 1
        if 306 <= doy <= 315: pid, disc = 1, 0.10
        elif doy == 316: pid, disc = 2, 0.25
        elif 317 <= doy <= 319: pid, disc = 3, 0.15
        else: pid, disc = "NULL", 0.0
        r = random.random()
        if r < 0.70: st = "completed"
        elif r < 0.85: st = "paid"
        elif r < 0.95: st = "shipped"
        else: st = "cancelled"
        ni = random.choices([1,2,3,4,5,6], weights=[15,30,25,15,10,5])[0]
        total = 0.0
        for _ in range(ni):
            prod = random.randint(1, 500)
            qty = random.choices([1,2,3], weights=[60,30,10])[0]
            up = round(random.uniform(19.9, 9999.0), 2)
            fp = round(up * (1 - disc), 2)
            total += fp * qty
            item_vals.append(f"({item_id},{oid},{prod},{qty},{round(up,2)})")
            item_id += 1
        total = round(total, 2)
        order_vals.append(f"({oid},{uid},{od},'{st}',{total},{pid})")
        if random.random() < 0.95:
            method = random.choices(["支付宝","微信","银行卡"], weights=[40,40,20])[0]
            pd_ = f"DATE_ADD('2024-01-01',INTERVAL {day+random.randint(0,2)} DAY)"
            pay_vals.append(f"({pay_id},{oid},'{method}',{pd_},{total},'completed')")
            pay_id += 1
    for name, vals in [("seed_orders.sql",order_vals),("seed_order_items.sql",item_vals),("seed_payments.sql",pay_vals)]:
        with open(name,"w",encoding="utf-8") as f:
            f.write("INSERT INTO " + name.split("_",1)[1].replace(".sql","") + " VALUES\n" + ",\n".join(vals) + ";")
        print(f"{name}: {len(vals)} rows")

def write_sql_files():
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
    gen_users()
    gen_products()
    gen_orders()
    print("All seed SQL files generated in sync/")

if __name__ == "__main__":
    write_sql_files()
```

Run:
```bash
cd sync && python gen_data.py && cd ..
```

Expected: 5 SQL files generated (seed_users.sql, seed_products.sql, seed_orders.sql, seed_order_items.sql, seed_payments.sql)

- [ ] **Step 2: 验证种子数据**

```bash
wc -l sync/seed_*.sql
```

Expected: Total line count > 50000, all files non-empty.
---

## 阶段 2: YMatrix 数仓模式

### Task 3: 创建 YMatrix 初始化 SQL（扩展 + APM + dim_date）

**Files:**
- Create: `ymatrix/init/01_init.sql`

- [ ] **Step 1: 创建 ymatrix/init/01_init.sql**

```sql
CREATE EXTENSION IF NOT EXISTS matrixts;
CREATE EXTENSION IF NOT EXISTS postgres_fdw;
SELECT apm_enable_partition_maintenance();

CREATE TABLE dim_date (
    date_key DATE, year SMALLINT, quarter SMALLINT, month SMALLINT,
    week SMALLINT, day_of_month SMALLINT, day_of_week SMALLINT,
    is_weekend BOOLEAN, season VARCHAR(4)
) USING HEAP DISTRIBUTED BY (date_key);

INSERT INTO dim_date (date_key, year, quarter, month, week, day_of_month, day_of_week, is_weekend, season)
SELECT d::DATE,
    EXTRACT(YEAR FROM d)::SMALLINT, EXTRACT(QUARTER FROM d)::SMALLINT,
    EXTRACT(MONTH FROM d)::SMALLINT, EXTRACT(WEEK FROM d)::SMALLINT,
    EXTRACT(DAY FROM d)::SMALLINT, EXTRACT(DOW FROM d)::SMALLINT + 1,
    EXTRACT(DOW FROM d) IN (0,6),
    CASE WHEN EXTRACT(MONTH FROM d) IN (3,4,5) THEN 'spring'
         WHEN EXTRACT(MONTH FROM d) IN (6,7,8) THEN 'summer'
         WHEN EXTRACT(MONTH FROM d) IN (9,10,11) THEN 'autumn'
         ELSE 'winter' END
FROM generate_series('2023-01-01'::DATE, '2025-12-31'::DATE, '1 day') d;
```

Run:
```bash
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/01_init.sql
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -c "SELECT COUNT(*) FROM dim_date;"
```

Expected: matrixts extension created. dim_date 1096 rows.

---

### Task 4: 创建 ODS 层表（5 MARS3 + RANGE 分区 + HEAP 对照）

**Files:**
- Create: `ymatrix/init/02_ods.sql`

- [ ] **Step 1: 创建 ymatrix/init/02_ods.sql**

```sql
CREATE TABLE ods_orders (
    order_id INT, user_id INT, order_date DATE, status VARCHAR(20),
    total_amount NUMERIC(10,2), promo_id INT, sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (order_id) ORDER BY (order_date, order_id)
PARTITION BY RANGE (order_date)
( START (DATE '2024-01-01') INCLUSIVE END (DATE '2025-01-01') EXCLUSIVE EVERY (INTERVAL '1 day') );

CREATE TABLE ods_order_items (
    item_id INT, order_id INT, product_id INT, qty INT, unit_price NUMERIC(10,2), sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (item_id) ORDER BY (order_id, item_id)
PARTITION BY RANGE (order_id)
( START (1) INCLUSIVE END (200001) EXCLUSIVE EVERY (20000) );

CREATE TABLE ods_payments (
    payment_id INT, order_id INT, method VARCHAR(20), pay_date DATE,
    amount NUMERIC(10,2), status VARCHAR(20), sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (payment_id) ORDER BY (order_id, payment_id);

CREATE TABLE ods_users (
    user_id INT, name VARCHAR(100), email VARCHAR(200), register_date DATE,
    city VARCHAR(50), province VARCHAR(50), status VARCHAR(20), sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (user_id);

CREATE TABLE ods_products (
    product_id INT, product_name VARCHAR(200), category VARCHAR(50),
    price NUMERIC(10,2), stock INT, sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (product_id);

-- HEAP comparison table
CREATE TABLE ods_orders_heap (
    order_id INT, user_id INT, order_date DATE, status VARCHAR(20),
    total_amount NUMERIC(10,2), promo_id INT, sync_time TIMESTAMP
) USING HEAP DISTRIBUTED BY (order_id);
```

Run:
```bash
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/02_ods.sql
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -c "\dt ods_*"
```

Expected: 6 tables (5 MARS3 + 1 HEAP). All with DISTRIBUTED BY and compression/partition config.

---

### Task 5: 创建 DIM + DWD 层

**Files:**
- Create: `ymatrix/init/03_dim.sql`
- Create: `ymatrix/init/03_dwd.sql`

- [ ] **Step 1: 创建 ymatrix/init/03_dim.sql**

```sql
CREATE TABLE dim_region (
    region_id INT, province VARCHAR(50), city VARCHAR(50),
    district VARCHAR(50), region_tier VARCHAR(10)
) USING HEAP DISTRIBUTED BY (region_id);
INSERT INTO dim_region VALUES
(1,'北京市','北京','朝阳区','一线'),(2,'上海市','上海','浦东新区','一线'),
(3,'广东省','广州','天河区','一线'),(4,'广东省','深圳','南山区','一线'),
(5,'四川省','成都','高新区','新一线');

CREATE TABLE dim_promotion (
    promo_id INT, promo_name VARCHAR(100), promo_type VARCHAR(20),
    start_date DATE, end_date DATE, discount_rate NUMERIC(3,2) DEFAULT 0
) USING HEAP DISTRIBUTED BY (promo_id);
INSERT INTO dim_promotion VALUES
(1,'双11预热期','预热','2024-11-01','2024-11-10',0.10),
(2,'双11正式期','正式','2024-11-11','2024-11-11',0.25),
(3,'双11返场期','返场','2024-11-12','2024-11-14',0.15);

CREATE TABLE dim_product (
    product_id INT, product_name VARCHAR(200), category VARCHAR(50), price NUMERIC(10,2)
) USING HEAP DISTRIBUTED BY (product_id);

CREATE TABLE dim_user (
    user_id INT, user_name VARCHAR(100), city VARCHAR(50),
    status VARCHAR(20), register_date DATE
) USING HEAP DISTRIBUTED BY (user_id);
```

- [ ] **Step 2: 创建 ymatrix/init/03_dwd.sql**

```sql
CREATE TABLE dwd_order_fact (
    order_id INT, user_id INT, order_date DATE, region_id INT, promo_id INT DEFAULT 0,
    total_amount NUMERIC(10,2), freight_amount NUMERIC(10,2) DEFAULT 0,
    discount_amount NUMERIC(10,2) DEFAULT 0, create_time TIMESTAMP, pay_time TIMESTAMP,
    cancel_time TIMESTAMP, finish_time TIMESTAMP, source_type VARCHAR(20), status VARCHAR(20)
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (order_id) ORDER BY (order_date, order_id)
PARTITION BY RANGE (order_date)
( START (DATE '2024-01-01') INCLUSIVE END (DATE '2025-01-01') EXCLUSIVE EVERY (INTERVAL '1 day') );

CREATE TABLE dwd_order_detail_fact (
    detail_id INT, order_id INT, user_id INT, sku_id INT, order_date DATE,
    region_id INT, promo_id INT, sku_num INT, original_price NUMERIC(10,2),
    final_price NUMERIC(10,2), source_type VARCHAR(20)
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (detail_id) ORDER BY (order_date, detail_id)
PARTITION BY RANGE (order_date)
( START (DATE '2024-01-01') INCLUSIVE END (DATE '2025-01-01') EXCLUSIVE EVERY (INTERVAL '1 day') );
```

Run:
```bash
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/03_dim.sql
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/03_dwd.sql
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -c "\dt dim_* dwd_*"
```

Expected: 4 dim tables (HEAP) + 2 dwd tables (MARS3, partitioned).

---

### Task 6: 创建 DWS + ADS 层（物化视图 + 视图）

**Files:**
- Create: `ymatrix/init/04_dws.sql`
- Create: `ymatrix/init/05_ads.sql`

- [ ] **Step 1: 创建 ymatrix/init/04_dws.sql**

```sql
CREATE MATERIALIZED VIEW dws_daily_gmv AS
SELECT time_bucket('1 day', order_date::TIMESTAMP) AS dt,
       COUNT(*) AS order_count, SUM(total_amount) AS gmv, AVG(total_amount) AS avg_order_amount
FROM dwd_order_fact GROUP BY dt DISTRIBUTED BY (dt);

CREATE MATERIALIZED VIEW dws_product_daily_sales AS
SELECT order_date, sku_id, SUM(sku_num) AS total_qty, SUM(sku_num * final_price) AS total_revenue
FROM dwd_order_detail_fact GROUP BY order_date, sku_id DISTRIBUTED BY (order_date);

CREATE MATERIALIZED VIEW dws_user_purchase_stats AS
SELECT user_id, COUNT(*) AS total_orders, SUM(total_amount) AS total_spent
FROM dwd_order_fact GROUP BY user_id DISTRIBUTED BY (user_id);
```

- [ ] **Step 2: 创建 ymatrix/init/05_ads.sql**

```sql
CREATE VIEW ads_daily_gmv AS SELECT dt, order_count, gmv, avg_order_amount FROM dws_daily_gmv ORDER BY dt;
CREATE VIEW ads_top_products AS SELECT p.product_name,p.category,d.total_qty,d.total_revenue FROM
  (SELECT sku_id,SUM(total_qty)total_qty,SUM(total_revenue)total_revenue FROM dws_product_daily_sales GROUP BY sku_id ORDER BY total_revenue DESC LIMIT 10)d
  JOIN dim_product p ON d.sku_id=p.product_id;
CREATE VIEW ads_category_sales AS SELECT p.category,SUM(d.total_revenue)revenue,
  SUM(d.total_revenue)*100.0/SUM(SUM(d.total_revenue))OVER()pct
  FROM dws_product_daily_sales d JOIN dim_product p ON d.sku_id=p.product_id GROUP BY p.category ORDER BY revenue DESC;
CREATE VIEW ads_user_repurchase AS SELECT COUNT(*)FILTER(WHERE total_orders>1)*100.0/COUNT(*)repurchase_rate,
  COUNT(*)FILTER(WHERE total_orders>1)repeat_buyers,COUNT(*)total_buyers FROM dws_user_purchase_stats;
CREATE VIEW ads_user_segment AS SELECT CASE WHEN total_orders>=10 OR total_spent>=5000 THEN 'high'
  WHEN total_orders>=3 OR total_spent>=1000 THEN 'mid' ELSE 'low' END segment,
  COUNT(*)user_count,SUM(total_orders)total_orders FROM dws_user_purchase_stats GROUP BY 1 ORDER BY 1;
CREATE VIEW ads_gmv_by_region AS SELECT r.province,COUNT(DISTINCT f.order_id)order_cnt,SUM(f.total_amount)gmv
  FROM dwd_order_fact f JOIN dim_region r ON f.region_id=r.region_id GROUP BY r.province ORDER BY gmv DESC;
CREATE VIEW ads_promo_compare AS SELECT CASE WHEN o.promo_id IS NOT NULL THEN '大促期' ELSE '日常期' END period,
  COUNT(DISTINCT o.order_id)order_cnt,SUM(o.total_amount)gmv,
  SUM(o.total_amount)/COUNT(DISTINCT o.order_id)avg_order_value FROM dwd_order_fact o GROUP BY 1;
```

Run:
```bash
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/04_dws.sql
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/05_ads.sql
docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -c "\dv ads_*"
```

Expected: 3 materialized views + 7 views. `\dv` shows ads_* views.

---

### Task 7: 创建 FDW + 压缩率对比 + ETL 日志表

**Files:**
- Create: `ymatrix/init/06_fdw.sql`
- Create: `ymatrix/verify/01_compression.sql`
- Append to: `ymatrix/init/01_init.sql` (etl_log table)

- [ ] **Step 1: 创建 ymatrix/init/06_fdw.sql**

```sql
-- mysql_fdw (optional, requires mysql_fdw package)
-- CREATE EXTENSION IF NOT EXISTS mysql_fdw;
-- CREATE SERVER mysql_ecommerce FOREIGN DATA WRAPPER mysql_fdw
--     OPTIONS (host 'mysql', port '3306', dbname 'ecommerce');
-- CREATE USER MAPPING FOR mxadmin SERVER mysql_ecommerce
--     OPTIONS (username 'root', password 'root');
```

- [ ] **Step 2: 创建 ymatrix/verify/01_compression.sql**

```sql
SELECT 'MARS3' AS engine, pg_size_pretty(pg_total_relation_size('ods_orders')) AS total_size
UNION ALL
SELECT 'HEAP', pg_size_pretty(pg_total_relation_size('ods_orders_heap'));
```

- [ ] **Step 3: ETL 日志表（添加到 01_init.sql 末尾）**

```sql
CREATE TABLE etl_log (
    log_id BIGSERIAL, step VARCHAR(50), status VARCHAR(20),
    rows_processed INT, duration_ms INT, message TEXT,
    log_time TIMESTAMP DEFAULT current_timestamp
) USING MARS3 DISTRIBUTED BY (log_id) ORDER BY (log_time);
```
---

## 阶段 3: Python ETL 管线

### Task 8: 创建 extract.py + transform.py

**Files:**
- Create: `sync/extract.py`
- Create: `sync/transform.py`

- [ ] **Step 1: 创建 sync/extract.py**

```python
"""Extract data from MySQL into pandas DataFrames."""
import pandas as pd
from sqlalchemy import create_engine
from typing import Dict

MYSQL_URI = "mysql+pymysql://root:root@localhost:3306/ecommerce"
TABLES = ["users", "products", "orders", "order_items", "payments"]

def extract_all() -> Dict[str, pd.DataFrame]:
    engine = create_engine(MYSQL_URI)
    result = {}
    for table in TABLES:
        print(f"Extracting {table}...")
        df = pd.read_sql(f"SELECT * FROM {table}", engine)
        result[table] = df
        print(f"  -> {len(df)} rows")
    engine.dispose()
    return result

if __name__ == "__main__":
    data = extract_all()
    for n, df in data.items():
        print(f"{n}: {len(df)} rows, {len(df.columns)} cols")
```

- [ ] **Step 2: 创建 sync/transform.py**

```python
"""Transform and clean extracted data."""
import pandas as pd
import numpy as np
from typing import Dict

def clean_users(df): df=df.dropna(subset=["user_id","name"]); df["status"]=df["status"].fillna("active"); return df
def clean_products(df): df=df.dropna(subset=["product_id","product_name"]); df["price"]=df["price"].fillna(0).round(2); df["stock"]=df["stock"].fillna(0).astype(int); return df
def clean_orders(df): df=df.dropna(subset=["order_id","user_id","order_date"]); df["total_amount"]=df["total_amount"].fillna(0).round(2); df["status"]=df["status"].fillna("unknown"); df["promo_id"]=df["promo_id"].fillna(0).astype(int); return df
def clean_order_items(df): df=df.dropna(subset=["item_id","order_id","product_id"]); df["qty"]=df["qty"].fillna(1).astype(int); df["unit_price"]=df["unit_price"].fillna(0).round(2); return df
def clean_payments(df): df=df.dropna(subset=["payment_id","order_id"]); df["amount"]=df["amount"].fillna(0).round(2); df["status"]=df["status"].fillna("completed"); return df

def transform_all(data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    cleaners = {"users":clean_users,"products":clean_products,"orders":clean_orders,"order_items":clean_order_items,"payments":clean_payments}
    result = {}
    for name, df in data.items():
        result[name] = cleaners[name](df)
        dropped = len(df) - len(result[name])
        print(f"Transform {name}: {len(result[name])} rows (dropped {dropped})")
    return result

if __name__ == "__main__":
    from extract import extract_all
    d = transform_all(extract_all())
    for n, df in d.items(): print(f"{n}: {len(df)} rows")
```

Run:
```bash
python -c "from extract import extract_all; from transform import transform_all; d=transform_all(extract_all())"
```

Expected (requires MySQL running): 5 tables extracted and cleaned. 0 rows dropped (seed data is clean).

---

### Task 9: 创建 load_ods.py + load_dim.py（mxgate 写入）

**Files:**
- Create: `sync/load_ods.py`
- Create: `sync/load_dim.py`

- [ ] **Step 1: 创建 sync/load_ods.py**

```python
"""Load data into ODS layer via mxgate stdin."""
import subprocess, io, pandas as pd

def _gate(target: str, df: pd.DataFrame):
    cmd = ["mxgate","--source","stdin","--db-database","dw_demo",
           "--db-master-host","localhost","--db-master-port","5432",
           "--db-user","mxadmin","--target",target,"--parallel","256","--delimiter",","]
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
    proc.communicate(buf.getvalue())
    return proc.wait()

def load_ods_users(df):
    rows = df[["user_id","name","email","register_date","city","province","status"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_users", rows)
    return len(rows)

def load_ods_products(df):
    rows = df[["product_id","product_name","category","price","stock"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_products", rows); return len(rows)

def load_ods_orders(df):
    rows = df[["order_id","user_id","order_date","status","total_amount","promo_id"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_orders", rows); return len(rows)

def load_ods_order_items(df):
    rows = df[["item_id","order_id","product_id","qty","unit_price"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_order_items", rows); return len(rows)

def load_ods_payments(df):
    rows = df[["payment_id","order_id","method","pay_date","amount","status"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_payments", rows); return len(rows)

def load_all(dfs):
    loaders = {"users":load_ods_users,"products":load_ods_products,"orders":load_ods_orders,"order_items":load_ods_order_items,"payments":load_ods_payments}
    result = {}
    for name, loader in loaders.items():
        print(f"Loading {name} -> ods_{name} via mxgate...")
        result[name] = loader(dfs[name])
        print(f"  -> {result[name]} rows")
    return result
```

- [ ] **Step 2: 创建 sync/load_dim.py**

```python
"""Load DIM tables from ODS via TRUNCATE + mxgate."""
import subprocess, io, pandas as pd

def _psql(sql):
    subprocess.run(["psql","-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-c",sql],
                   capture_output=True, text=True)

def load_dim_product(ods_products):
    _psql("TRUNCATE dim_product;")
    rows = ods_products[["product_id","product_name","category","price"]].drop_duplicates()
    buf = io.StringIO(); rows.to_csv(buf, index=False, header=False)
    subprocess.run(["mxgate","--source","stdin","--db-database","dw_demo",
        "--db-master-host","localhost","--db-master-port","5432","--db-user","mxadmin",
        "--target","dim_product","--parallel","64","--delimiter",","],
        input=buf.getvalue(), text=True)
    return len(rows)

def load_dim_user(ods_users):
    _psql("TRUNCATE dim_user;")
    rows = ods_users[["user_id","name","city","status","register_date"]].drop_duplicates()
    buf = io.StringIO(); rows.to_csv(buf, index=False, header=False)
    subprocess.run(["mxgate","--source","stdin","--db-database","dw_demo",
        "--db-master-host","localhost","--db-master-port","5432","--db-user","mxadmin",
        "--target","dim_user","--parallel","64","--delimiter",","],
        input=buf.getvalue(), text=True)
    return len(rows)

def load_all(dfs):
    result = {"dim_product": load_dim_product(dfs["products"]), "dim_user": load_dim_user(dfs["users"])}
    print(f"dim_product: {result['dim_product']} rows, dim_user: {result['dim_user']} rows")
    return result
```

Run:
```bash
python -c "from extract import extract_all; from transform import transform_all; from load_ods import load_all as lod; d=transform_all(extract_all()); lod(d)"
python -c "from extract import extract_all; from transform import transform_all; from load_dim import load_all as ldim; d=transform_all(extract_all()); ldim(d)"
```

Expected (requires MySQL+YMatrix running): ODS tables ~301500 rows total. DIM tables ~500+1000 rows.

---

### Task 10: 创建 load_dwd.py（SQL ETL：ODS -> DWD + REFRESH MV）

**Files:**
- Create: `sync/load_dwd.py`

- [ ] **Step 1: 创建 sync/load_dwd.py**

```python
"""ETL ODS -> DWD via SQL INSERT...SELECT, then REFRESH MV."""
import subprocess, time

def _sql(cmd):
    r = subprocess.run(["psql","-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-t","-A","-c",cmd],
                       capture_output=True, text=True)
    return r

def _count(table):
    r = _sql(f"SELECT COUNT(*) FROM {table};")
    return int(r.stdout.strip()) if r.stdout.strip() else 0

def run_all():
    results = []

    t0 = time.time()
    _sql("TRUNCATE dwd_order_fact CASCADE;")
    r = _sql("""
    INSERT INTO dwd_order_fact (order_id,user_id,order_date,region_id,promo_id,total_amount,freight_amount,discount_amount,create_time,pay_time,cancel_time,finish_time,source_type,status)
    SELECT o.order_id,o.user_id,o.order_date,COALESCE(r.region_id,0),COALESCE(o.promo_id,0),o.total_amount,
      CASE WHEN o.total_amount>=200 THEN 0 ELSE ROUND((RANDOM()*7+8)::NUMERIC,2) END,
      CASE WHEN o.promo_id IS NOT NULL THEN ROUND((RANDOM()*25+5)::NUMERIC,2) ELSE 0 END,
      o.order_date::TIMESTAMP,
      CASE WHEN o.status IN ('paid','shipped','completed') THEN o.order_date::TIMESTAMP ELSE NULL END,
      CASE WHEN o.status='cancelled' THEN o.order_date::TIMESTAMP ELSE NULL END,
      CASE WHEN o.status='completed' THEN o.order_date::TIMESTAMP+INTERVAL'2 days' ELSE NULL END,
      CASE MOD(o.order_id,10) WHEN 0 THEN 'miniapp' WHEN 1 THEN 'miniapp' WHEN 2 THEN 'web' WHEN 3 THEN 'web' WHEN 4 THEN 'web' ELSE 'app' END,
      o.status
    FROM ods_orders o LEFT JOIN ods_users u ON o.user_id=u.user_id LEFT JOIN dim_region r ON u.city=r.city AND u.province=r.province
    WHERE o.status IS NOT NULL;""")
    rows = _count("dwd_order_fact")
    results.append({"step":"dwd_order_fact","rows":rows,"ms":int((time.time()-t0)*1000),"status":"success" if r.returncode==0 else "failed"})
    print(f"dwd_order_fact: {rows} rows ({results[-1]['ms']}ms)")

    t0 = time.time()
    _sql("TRUNCATE dwd_order_detail_fact CASCADE;")
    r = _sql("""
    INSERT INTO dwd_order_detail_fact (detail_id,order_id,user_id,sku_id,order_date,region_id,promo_id,sku_num,original_price,final_price,source_type)
    SELECT oi.item_id,oi.order_id,o.user_id,oi.product_id,o.order_date,0,COALESCE(o.promo_id,0),
      oi.qty,oi.unit_price,oi.unit_price*(1-COALESCE(p.discount_rate,0)),
      CASE MOD(oi.order_id,10) WHEN 0 THEN 'miniapp' WHEN 1 THEN 'miniapp' WHEN 2 THEN 'web' WHEN 3 THEN 'web' WHEN 4 THEN 'web' ELSE 'app' END
    FROM ods_order_items oi JOIN ods_orders o ON oi.order_id=o.order_id
    LEFT JOIN dim_promotion p ON o.promo_id=p.promo_id AND o.order_date BETWEEN p.start_date AND p.end_date
    WHERE o.status IS NOT NULL;""")
    rows = _count("dwd_order_detail_fact")
    results.append({"step":"dwd_order_detail","rows":rows,"ms":int((time.time()-t0)*1000),"status":"success" if r.returncode==0 else "failed"})
    print(f"dwd_order_detail_fact: {rows} rows ({results[-1]['ms']}ms)")

    t0 = time.time()
    for v in ["dws_daily_gmv","dws_product_daily_sales","dws_user_purchase_stats"]:
        _sql(f"REFRESH MATERIALIZED VIEW {v};")
    results.append({"step":"refresh_dws","rows":3,"ms":int((time.time()-t0)*1000),"status":"success"})
    print(f"DWS materialized views refreshed ({results[-1]['ms']}ms)")

    return results

if __name__ == "__main__":
    for r in run_all():
        print(f"  {r['step']}: {r['status']} ({r['rows']} rows, {r['ms']}ms)")
```

Run:
```bash
python sync/load_dwd.py
```

Expected (requires YMatrix running with ODS data): dwd_order_fact ~50000 rows, dwd_order_detail_fact ~200000 rows. DWS refreshed.

---

### Task 11: 创建 sync_data.py（编排器）+ requirements.txt

**Files:**
- Create: `sync/sync_data.py`
- Create: `sync/requirements.txt`

- [ ] **Step 1: 创建 sync/requirements.txt**

```
pandas>=1.5.0
PyMySQL>=1.0.0
psycopg2-binary>=2.9.0
sqlalchemy>=1.4.0
numpy>=1.24.0
```

- [ ] **Step 2: 创建 sync/sync_data.py**

```python
#!/usr/bin/env python3
"""ETL orchestrator: extract -> transform -> load ODS -> load DIM -> load DWD -> refresh -> verify."""
import time, sys, os, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import extract_all
from transform import transform_all
from load_ods import load_all as load_ods
from load_dim import load_all as load_dim
from load_dwd import run_all as run_dwd
from verify import verify_ads

def log(step, status, rows=0, ms=0, msg=""):
    sql = f"INSERT INTO etl_log(step,status,rows_processed,duration_ms,message) VALUES('{step}','{status}',{rows},{ms},'{msg}');"
    subprocess.run(["psql","-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-c",sql],
                   capture_output=True, text=True)

def main():
    t_start = time.time()
    print("="*50); print("YMatrix DW Demo - Full ETL Pipeline"); print("="*50)

    t0=time.time(); print("\n[1/6] Extract..."); raw=extract_all()
    t=int((time.time()-t0)*1000); log("extract","success",sum(len(v)for v in raw.values()),t)
    print(f"  {sum(len(v)for v in raw.values())} rows in {t}ms")

    t0=time.time(); print("\n[2/6] Transform..."); clean=transform_all(raw)
    t=int((time.time()-t0)*1000); log("transform","success",sum(len(v)for v in clean.values()),t)

    t0=time.time(); print("\n[3/6] Load ODS..."); oc=load_ods(clean)
    t=int((time.time()-t0)*1000); log("load_ods","success",sum(oc.values()),t)

    t0=time.time(); print("\n[4/6] Load DIM..."); dc=load_dim(clean)
    t=int((time.time()-t0)*1000); log("load_dim","success",sum(dc.values()),t)

    t0=time.time(); print("\n[5/6] DWD ETL + Refresh..."); dr=run_dwd()
    t=int((time.time()-t0)*1000)
    for r in dr: log(r["step"],r["status"],r["rows"],r["ms"])

    print("\n[6/6] Verify..."); vr=verify_ads()
    for n,r in vr.items(): print(f"  [{'PASS' if r else 'FAIL'}] {n}")

    tt=int((time.time()-t_start)*1000)
    print(f"\n{'='*50}\nETL Complete: {tt}ms\nGrafana: http://localhost:3000 (admin/admin)\n{'='*50}")
    log("etl_complete","success",0,tt)

if __name__=="__main__":
    main()
```

Run:
```bash
cd sync && python sync_data.py && cd ..
```

Expected (requires MySQL+YMatrix running): 6 steps all succeed. Total time < 60s.
---

## 阶段 4: Grafana 仪表盘

### Task 12: 创建 Grafana 数据源 + Dashboard JSON

**Files:**
- Create: `grafana/datasources/ymatrix.yaml`
- Create: `grafana/dashboards/ymatrix_dw_demo.json`

- [ ] **Step 1: 创建 grafana/datasources/ymatrix.yaml**

```yaml
apiVersion: 1
datasources:
  - name: YMatrix
    type: postgres
    access: proxy
    url: ymatrix:5432
    user: mxadmin
    database: dw_demo
    isDefault: true
    jsonData:
      sslmode: disable
      postgresVersion: 1500
      timescaledb: false
    secureJsonData:
      password: ""
```

- [ ] **Step 2: 创建 grafana/dashboards/ymatrix_dw_demo.json**

```json
{
  "title": "YMatrix DW Demo",
  "timezone": "Asia/Shanghai",
  "panels": [
    {"id":1,"title":"每日 GMV 趋势","type":"timeseries","gridPos":{"h":8,"w":12,"x":0,"y":0},
     "targets":[{"rawSql":"SELECT dt AS time, gmv, order_count FROM ads_daily_gmv ORDER BY dt","format":"time_series","datasource":"YMatrix"}],
     "fieldConfig":{"defaults":{"unit":"currencyCNY","custom":{"lineInterpolation":"smooth"}}}},
    {"id":2,"title":"商品销售 Top 10","type":"table","gridPos":{"h":8,"w":6,"x":12,"y":0},
     "targets":[{"rawSql":"SELECT product_name,category,total_qty,total_revenue FROM ads_top_products","format":"table","datasource":"YMatrix"}]},
    {"id":3,"title":"品类销售占比","type":"piechart","gridPos":{"h":8,"w":6,"x":18,"y":0},
     "targets":[{"rawSql":"SELECT category,revenue,pct FROM ads_category_sales ORDER BY revenue DESC","format":"table","datasource":"YMatrix"}],
     "options":{"pieType":"pie","displayLabels":["percent","name"]}},
    {"id":4,"title":"用户复购率","type":"stat","gridPos":{"h":6,"w":6,"x":0,"y":8},
     "targets":[{"rawSql":"SELECT repurchase_rate FROM ads_user_repurchase","format":"table","datasource":"YMatrix"}],
     "fieldConfig":{"defaults":{"unit":"percent","color":{"mode":"thresholds"},"thresholds":{"steps":[{"value":0,"color":"red"},{"value":30,"color":"yellow"},{"value":50,"color":"green"}]}}}},
    {"id":5,"title":"GMV 按省份分布","type":"treemap","gridPos":{"h":6,"w":6,"x":6,"y":8},
     "targets":[{"rawSql":"SELECT province,order_cnt,gmv FROM ads_gmv_by_region ORDER BY gmv DESC","format":"table","datasource":"YMatrix"}]},
    {"id":6,"title":"促销 vs 日常","type":"bargauge","gridPos":{"h":6,"w":12,"x":12,"y":8},
     "targets":[{"rawSql":"SELECT period,order_cnt,gmv,avg_order_value FROM ads_promo_compare","format":"table","datasource":"YMatrix"}],
     "options":{"orientation":"horizontal","showUnfilled":true}}
  ]
}
```

Verify:
```bash
docker-compose restart grafana
# Open http://localhost:3000 (admin/admin) -> should see YMatrix datasource + 6 panels
```

---

## 阶段 5: 初始化脚本 + 验证

### Task 13: 创建 init_all.sh

**Files:**
- Create: `init_all.sh`

- [ ] **Step 1: 创建 init_all.sh**

```bash
#!/bin/bash
set -e

echo "=== YMatrix DW Demo - Init All ==="

# Step 0: Verify containers
for svc in mysql ymatrix grafana; do
    docker-compose ps $svc | grep -q "Up" || { echo "ERROR: $svc not running"; exit 1; }
done
echo "All containers running."

# Step 1: Generate seed data
echo "Step 1: Generating seed data..."
cd sync && python gen_data.py && cd ..

# Step 2: Load seed data into MySQL
echo "Step 2: Loading seed data..."
for f in sync/seed_users.sql sync/seed_products.sql sync/seed_orders.sql sync/seed_order_items.sql sync/seed_payments.sql; do
    echo "  Loading $(basename $f)..."
    docker-compose exec -T mysql mysql -uroot -proot -D ecommerce < "$f"
done

# Step 3: Verify MySQL
echo "Step 3: MySQL verification..."
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e "SELECT 'users',COUNT(*)FROM users UNION SELECT 'products',COUNT(*)FROM products UNION SELECT 'orders',COUNT(*)FROM orders UNION SELECT 'order_items',COUNT(*)FROM order_items UNION SELECT 'payments',COUNT(*)FROM payments;"

# Step 4: Init YMatrix schema
echo "Step 4: YMatrix schema..."
for f in ymatrix/init/*.sql; do
    echo "  Running $(basename $f)..."
    docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f "/docker-entrypoint-initdb.d/$(basename $f)"
done

# Step 5: ETL pipeline
echo "Step 5: ETL pipeline..."
cd sync && python sync_data.py && cd ..

# Step 6: Verify
echo "Step 6: Verification..."
cd sync && python verify.py && cd ..

echo "=== All Done ==="
echo "Grafana: http://localhost:3000 (admin/admin)"
```

Make executable:
```bash
chmod +x init_all.sh
```

Run:
```bash
docker-compose up -d && bash init_all.sh
```

Expected: Full pipeline runs without errors. All 6 steps succeed.

---

### Task 14: 创建 verify.py（ADS 验证）

**Files:**
- Create: `sync/verify.py`

- [ ] **Step 1: 创建 sync/verify.py**

```python
"""Verify ADS metrics and compression ratio."""
import subprocess, sys

def _sql(cmd):
    r = subprocess.run(["psql","-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-t","-A","-c",cmd], capture_output=True, text=True)
    return r.stdout.strip()

def verify_ads():
    results = {}
    print("\n--- Verifying ADS Metrics ---")

    c = int(_sql("SELECT COUNT(*) FROM ads_daily_gmv;"))
    r = c == 365; results["ads_daily_gmv: 365 days"] = r; print(f"  ads_daily_gmv: {c} rows -> {'PASS' if r else 'FAIL'}")

    n11 = _sql("SELECT gmv FROM ads_daily_gmv WHERE dt='2024-11-11'::TIMESTAMP;")
    avg = _sql("SELECT AVG(gmv)::INT FROM ads_daily_gmv;")
    if n11 and avg:
        r = int(n11) > int(avg)*2; results["Nov 11 peak > 2x avg"] = r; print(f"  Nov 11: {n11} vs avg: {avg} -> {'PASS' if r else 'FAIL'}")

    c = int(_sql("SELECT COUNT(*) FROM ads_top_products;"))
    r = c == 10; results["ads_top_products: 10 rows"] = r; print(f"  top_products: {c} rows -> {'PASS' if r else 'FAIL'}")

    p = float(_sql("SELECT COALESCE(SUM(pct),0) FROM ads_category_sales;"))
    r = abs(p-100) < 0.2; results["category pct = 100%"] = r; print(f"  category pct: {p:.2f}% -> {'PASS' if r else 'FAIL'}")

    rate = float(_sql("SELECT COALESCE(repurchase_rate,0) FROM ads_user_repurchase;"))
    r = rate >= 30; results["repurchase >= 30%"] = r; print(f"  repurchase: {rate:.2f}% -> {'PASS' if r else 'FAIL'}")

    c = int(_sql("SELECT COUNT(*) FROM ads_gmv_by_region;"))
    r = c == 5; results["gmv_by_region: 5 provinces"] = r; print(f"  gmv_by_region: {c} rows -> {'PASS' if r else 'FAIL'}")

    p = _sql("SELECT gmv::TEXT FROM ads_promo_compare ORDER BY gmv DESC LIMIT 1;")
    reg = _sql("SELECT gmv::TEXT FROM ads_promo_compare ORDER BY gmv ASC LIMIT 1;")
    if p and reg:
        r = float(p) > float(reg); results["promo > regular GMV"] = r; print(f"  promo: {p} vs regular: {reg} -> {'PASS' if r else 'FAIL'}")

    c = int(_sql("SELECT COUNT(*) FROM ads_user_segment;"))
    r = c == 3; results["user_segment: 3 segments"] = r; print(f"  user_segment: {c} segments -> {'PASS' if r else 'FAIL'}")

    m3 = _sql("SELECT pg_total_relation_size('ods_orders');")
    hp = _sql("SELECT pg_total_relation_size('ods_orders_heap');")
    if m3 and hp and int(hp) > 0:
        ratio = (1 - int(m3)/int(hp))*100; r = ratio >= 50
        results["compression: MARS3 saves >= 50%"] = r; print(f"  compression: MARS3 saves {ratio:.1f}% -> {'PASS' if r else 'FAIL'}")

    lc = int(_sql("SELECT COUNT(*) FROM etl_log;"))
    r = lc >= 7; results["etl_log: >= 7 entries"] = r; print(f"  etl_log: {lc} entries -> {'PASS' if r else 'FAIL'}")

    print(f"\n{sum(1 for v in results.values() if v)}/{len(results)} passed")
    return results

if __name__ == "__main__":
    r = verify_ads()
    sys.exit(0 if all(r.values()) else 1)
```

Run:
```bash
python sync/verify.py
```

Expected (requires YMatrix with data): All ~10 checks PASS. Exit code 0.

---

## 阶段 6: 文档更新

### Task 15: 更新 README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 重写 README**

README.md 需对应设计文档的新架构：
- 项目标题和描述：Docker + YMatrix 端到端 Demo
- 快速开始：docker-compose up -d && bash init_all.sh（替换旧的 python init_all.py）
- 架构图：文字描述 ODS -> DIM -> DWD -> DWS -> ADS 五层
- 技术栈：MySQL 8.0 + YMatrix 5.2.1 + Grafana + Python ETL
- 移除旧 SQLite 命令

---

### Task 16: 更新 report.md + ai_usage.md

**Files:**
- Modify: `report.md`
- Modify: `ai_usage.md`

- [ ] **Step 1: 更新 report.md**

面向客户和评委，包含：
- 架构说明（Docker Compose 三容器）
- YMatrix 特性展示清单（MARS3/HEAP/mxgate/time_bucket/fdw 等 12 项）
- 7 个 ADS 指标说明
- 设计决策摘要（10+ 个决策点）
- 验证结果截图路径

- [ ] **Step 2: 更新 ai_usage.md**

记录 AI 使用过程：设计阶段（sketch 对话 -> 设计文档 -> 决策记录）、实施阶段（代码生成 -> 审查）、使用的技能和工具。

---

## 自检清单

**1. 设计覆盖：**
- MySQL 5 表 (users/products/orders/order_items/payments) -> Task 1
- 种子数据生成 (gen_data.py) -> Task 2
- YMatrix 四层 (ODS/DIM/DWD/DWS/ADS) -> Tasks 3-6
- mxgate 写入 ODS/DIM -> Task 9
- SQL ETL ODS->DWD + REFRESH MV -> Task 10
- 7 个 ADS 指标视图 -> Task 6
- ETL 编排器 (sync_data.py) -> Task 11
- Grafana 预置面板 (6 panels) -> Task 12
- 一鍵初始化脚本 (init_all.sh) -> Task 13
- 验证脚本 (verify.py) -> Task 14
- 文档更新 (README/report/ai_usage) -> Tasks 15-16

**2. 占位符扫描:** 无 TBD/TODO/implement later

**3. 类型一致性:** load_ods.load_all(dfs) 与 sync_data.py 调用签名一致

---

## 执行交接

计划完成，保存于 `docs/superpowers/plans/2026-07-07-ymatrix-dw-demo-implementation.md`。

两种执行方式：

**1. Subagent-Driven（推荐）** — 分派独立 subagent 按任务执行，任务间做审查

**2. Inline Execution** — 在此会话中按顺序执行，批量处理 + 检查点

选择哪种方式？
