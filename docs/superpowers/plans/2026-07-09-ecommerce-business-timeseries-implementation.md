# Ecommerce Business Timeseries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved e-commerce business credible data generation and YMatrix time-series warehouse enhancement, with 200,000 orders as the default development scale and 1,000,000 orders as the performance demo scale.

**Architecture:** Keep MySQL as the business source, load CSV seed data into MySQL, extract through the existing Python ETL, write ODS through mxgate, then derive DIM/DWD/DWS/ADS inside YMatrix. Preserve source field names in MySQL and ODS, and perform semantic renaming plus explicit `Asia/Shanghai` timezone conversion in DWD.

**Tech Stack:** Docker Compose, MySQL 8.0, YMatrix 5.2.1, mxgate, PostgreSQL-compatible SQL, Python 3.6-compatible code, pandas, PyMySQL, psycopg2, Grafana JSON provisioning.

---

## File Structure

- Modify `mysql/init.sql`: add `order_status_events`, upgrade source time columns to `DATETIME(3)`, add indexes, keep `orders.order_date` and `payments.pay_date` names.
- Modify `sync/gen_data.py`: replace SQL values generation with streaming CSV generation, add configurable order scale, credible product/category/brand generation, weighted traffic, variable item count, status events, and amount reconciliation.
- Modify `init_all.sh`: load CSV files into MySQL with `LOAD DATA LOCAL INFILE`, wire default `ORDER_COUNT=200000`, keep performance override via environment variable.
- Modify `sync/extract.py`: include `order_status_events`.
- Modify `sync/transform.py`: clean timestamp and new status-event data.
- Modify `sync/load_ods.py`: load `ods_order_status_events`, support timestamp columns, keep compression sample.
- Modify `sync/load_dim.py`: keep loading DIM tables, ensure `dim_region` covers all generated cities and `dim_product` receives credible products.
- Modify `sync/load_dwd.py`: populate DWD facts with explicit `Asia/Shanghai` timezone conversion, status-event fact, `line_amount`, and refresh all DWS materialized views.
- Modify `ymatrix/init/02_ods.sql`: timestamp ODS schema, new ODS status events, scalable partitions.
- Modify `ymatrix/init/03_dim.sql`: complete region rows and product/user dimensions.
- Modify `ymatrix/init/03_dwd.sql`: add `order_time`, `pay_time`, `line_amount`, and `dwd_order_status_event_fact`.
- Modify `ymatrix/init/04_dws.sql`: add minute traffic, status funnel, fulfillment latency, promo compare, and reconcile existing DWS definitions with valid-order semantics.
- Modify `ymatrix/init/05_ads.sql`: add ADS views including `ads_gmv_running_total` and expose corrected business metrics.
- Modify `sync/verify.py`: expand integration checks for scale, business credibility, timezone, reconciliation, DWS/ADS completeness, and compression.
- Modify `grafana/dashboards/ymatrix_dw_demo.json`: use new ADS views and include the double-11 running GMV panel.
- Modify `README.md`, `report.md`, and `AGENTS.md`: update default scale, performance scale, time-zone rule, and ADS list.

---

### Task 1: Add Verification Targets First

**Files:**
- Modify: `sync/verify.py`

- [ ] **Step 1: Add explicit verification query helpers**

Add these helpers near the top of `sync/verify.py` after `_sql`:

```python
def _int(cmd):
    value = _sql(cmd)
    return int(value) if value else 0


def _float(cmd):
    value = _sql(cmd)
    return float(value) if value else 0.0


def _pass(results, name, ok, detail):
    results[name] = bool(ok)
    print("  {} {} -> {}".format(name, detail, "PASS" if ok else "FAIL"))
```

- [ ] **Step 2: Add failing business and time-series checks**

Extend `verify_ads()` with these checks before the final summary:

```python
    orders = _int("SELECT COUNT(*) FROM ods_orders;")
    _pass(results, "ods_orders >= 200000", orders >= 200000, "{} rows".format(orders))

    status_events = _int("SELECT COUNT(*) FROM ods_order_status_events;")
    _pass(results, "status events present", status_events >= orders, "{} rows".format(status_events))

    fixed_four = _int("""
        SELECT COUNT(*) FROM (
          SELECT order_id, COUNT(*) AS item_count
          FROM ods_order_items
          GROUP BY order_id
          HAVING COUNT(*) <> 4
        ) s;
    """)
    _pass(results, "order item count varies", fixed_four > 0, "{} non-four-item orders".format(fixed_four))

    mismatched_products = _int("""
        SELECT COUNT(*)
        FROM dim_product
        WHERE product_name IS NULL OR category IS NULL OR price <= 0;
    """)
    _pass(results, "product dimension credible", mismatched_products == 0, "{} invalid products".format(mismatched_products))

    recon_errors = _int("""
        SELECT COUNT(*)
        FROM (
          SELECT f.order_id
          FROM dwd_order_fact f
          JOIN (
            SELECT order_id, ROUND(SUM(line_amount), 2) AS detail_amount
            FROM dwd_order_detail_fact
            GROUP BY order_id
          ) d ON f.order_id = d.order_id
          WHERE ABS(f.total_amount - d.detail_amount) > 0.05
        ) s;
    """)
    _pass(results, "order/detail amount reconciles", recon_errors == 0, "{} mismatches".format(recon_errors))

    minute_rows = _int("SELECT COUNT(*) FROM ads_minute_traffic;")
    _pass(results, "minute traffic non-empty", minute_rows > 0, "{} rows".format(minute_rows))

    running_rows = _int("SELECT COUNT(*) FROM ads_gmv_running_total;")
    _pass(results, "running GMV non-empty", running_rows > 0, "{} rows".format(running_rows))

    running_violations = _int("""
        SELECT COUNT(*)
        FROM (
          SELECT running_gmv, LAG(running_gmv) OVER (ORDER BY bucket_time) AS prev_gmv
          FROM ads_gmv_running_total
        ) s
        WHERE prev_gmv IS NOT NULL AND running_gmv < prev_gmv;
    """)
    _pass(results, "running GMV monotonic", running_violations == 0, "{} violations".format(running_violations))

    timezone_shift = _int("""
        SELECT COUNT(*)
        FROM dwd_order_fact
        WHERE order_date <> DATE(order_time);
    """)
    _pass(results, "DWD timezone date aligned", timezone_shift == 0, "{} shifted rows".format(timezone_shift))
```

- [ ] **Step 3: Run verification to confirm it fails before implementation**

Run:

```bash
cd sync && python verify.py
```

Expected: FAIL because tables such as `ods_order_status_events`, `ads_minute_traffic`, or `ads_gmv_running_total` do not exist yet.

- [ ] **Step 4: Commit the failing verification contract**

```bash
git add sync/verify.py
git commit -m "test: define ecommerce timeseries verification contract"
```

---

### Task 2: Update MySQL Source Schema

**Files:**
- Modify: `mysql/init.sql`

- [ ] **Step 1: Add schema changes**

Update the top drop section:

```sql
DROP TABLE IF EXISTS order_status_events;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS dim_promotion;
DROP TABLE IF EXISTS dim_region;
DROP TABLE IF EXISTS dim_date;
```

Change `orders.order_date` and `payments.pay_date`:

```sql
CREATE TABLE orders (
    order_id      INT             NOT NULL AUTO_INCREMENT,
    user_id       INT             NOT NULL,
    order_date    DATETIME(3)     NOT NULL,
    status        VARCHAR(20)     NOT NULL DEFAULT 'pending',
    total_amount  DECIMAL(10,2)   NOT NULL DEFAULT 0.00,
    promo_id      INT             DEFAULT NULL,
    PRIMARY KEY (order_id),
    KEY idx_user_id (user_id),
    KEY idx_order_date (order_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE payments (
    payment_id    INT             NOT NULL AUTO_INCREMENT,
    order_id      INT             NOT NULL,
    method        VARCHAR(30)     NOT NULL,
    pay_date      DATETIME(3)     NOT NULL,
    amount        DECIMAL(10,2)   NOT NULL,
    status        VARCHAR(20)     NOT NULL DEFAULT 'completed',
    PRIMARY KEY (payment_id),
    KEY idx_order_id (order_id),
    KEY idx_pay_date (pay_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Add the event table after `payments`:

```sql
CREATE TABLE order_status_events (
    event_id      BIGINT          NOT NULL AUTO_INCREMENT,
    order_id      INT             NOT NULL,
    from_status   VARCHAR(20)     DEFAULT NULL,
    to_status     VARCHAR(20)     NOT NULL,
    event_time    DATETIME(3)     NOT NULL,
    operator_type VARCHAR(20)     NOT NULL DEFAULT 'system',
    PRIMARY KEY (event_id),
    KEY idx_order_id (order_id),
    KEY idx_event_time (event_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: Add full generated-region coverage**

Replace the existing `dim_region` seed with ten city rows that match the generator:

```sql
INSERT INTO dim_region (province, city, district, region_tier) VALUES
    ('北京市',   '北京',   '朝阳区',   'T1'),
    ('上海市',   '上海',   '浦东新区', 'T1'),
    ('广东省',   '广州',   '天河区',   'T1'),
    ('广东省',   '深圳',   '南山区',   'T1'),
    ('四川省',   '成都',   '高新区',   'T2'),
    ('湖北省',   '武汉',   '洪山区',   'T2'),
    ('浙江省',   '杭州',   '西湖区',   'T2'),
    ('江苏省',   '南京',   '鼓楼区',   'T2'),
    ('陕西省',   '西安',   '雁塔区',   'T2'),
    ('重庆市',   '重庆',   '渝中区',   'T2');
```

- [ ] **Step 3: Validate schema syntax inside MySQL**

Run:

```bash
docker-compose exec -T mysql mysql --default-character-set=utf8mb4 -uroot -proot -D ecommerce < mysql/init.sql
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e "SHOW COLUMNS FROM orders LIKE 'order_date'; SHOW COLUMNS FROM payments LIKE 'pay_date'; SHOW TABLES LIKE 'order_status_events';"
```

Expected: `order_date` and `pay_date` are `datetime(3)`, and `order_status_events` exists.

- [ ] **Step 4: Commit**

```bash
git add mysql/init.sql
git commit -m "feat: add ecommerce event source schema"
```

---

### Task 3: Generate Credible Streaming CSV Seed Data

**Files:**
- Modify: `sync/gen_data.py`

- [ ] **Step 1: Replace SQL values output with CSV output**

Rework `sync/gen_data.py` around these constants and function signatures:

```python
import csv
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

RANDOM_SEED = 42
DEFAULT_ORDER_COUNT = int(os.environ.get("ORDER_COUNT", "200000"))
OUTPUT_DIR = os.environ.get("SEED_OUTPUT_DIR", os.path.dirname(os.path.abspath(__file__)))
BASE_TIME = datetime(2024, 1, 1, 0, 0, 0)

PRODUCT_CATALOG = {
    "电子": {
        "brands": ["华为", "小米", "Apple", "OPPO", "vivo"],
        "types": ["手机", "平板", "笔记本", "耳机", "充电器"],
        "price": (199, 9999),
    },
    "服装": {
        "brands": ["Nike", "Adidas", "ZARA", "H&M", "优衣库"],
        "types": ["T恤", "牛仔裤", "外套", "运动鞋", "帽子"],
        "price": (49, 1299),
    },
    "美妆": {
        "brands": ["雅诗兰黛", "SK-II", "兰蔻", "欧莱雅", "资生堂"],
        "types": ["精华", "面霜", "眼霜", "面膜", "洗面奶"],
        "price": (69, 1999),
    },
    "食品": {
        "brands": ["三只松鼠", "良品铺子", "百草味", "来伊份", "洽洽"],
        "types": ["坚果", "肉干", "果脯", "饼干", "巧克力"],
        "price": (9.9, 299),
    },
    "家居": {
        "brands": ["宜家", "MUJI", "网易严选", "小米有品", "名创优品"],
        "types": ["台灯", "收纳盒", "毛巾", "拖鞋", "靠垫"],
        "price": (19.9, 999),
    },
}

PROMOS = {
    1: {"start": 306, "end": 315, "discount": Decimal("0.10")},
    2: {"start": 316, "end": 316, "discount": Decimal("0.25")},
    3: {"start": 317, "end": 319, "discount": Decimal("0.15")},
}

def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def write_csv(filename, rows):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow(row)
    return path
```

- [ ] **Step 2: Implement credible products and weighted users**

Use generated products as a small in-memory index:

```python
def gen_products(num=500):
    product_id = 1
    products = []
    per_category = num // len(PRODUCT_CATALOG)
    for category, config in PRODUCT_CATALOG.items():
        low, high = config["price"]
        for _ in range(per_category):
            brand = random.choice(config["brands"])
            product_type = random.choice(config["types"])
            price = money(random.uniform(low, high))
            stock = random.randint(10, 5000)
            products.append({
                "product_id": product_id,
                "product_name": "{} {}".format(brand, product_type),
                "category": category,
                "price": price,
                "stock": stock,
            })
            product_id += 1
    write_csv("seed_products.csv", [
        [p["product_id"], p["product_name"], p["category"], p["price"], p["stock"]]
        for p in products
    ])
    print("products: {} rows".format(len(products)))
    return products
```

Implement `gen_users()` with tier weights:

```python
def gen_users(num=1000):
    cities = [
        ("北京", "北京市"), ("上海", "上海市"), ("广州", "广东省"), ("深圳", "广东省"),
        ("成都", "四川省"), ("武汉", "湖北省"), ("杭州", "浙江省"), ("南京", "江苏省"),
        ("西安", "陕西省"), ("重庆", "重庆市"),
    ]
    users = []
    weighted_user_ids = []
    for user_id in range(1, num + 1):
        city, province = random.choice(cities)
        register_day = random.randint(0, 365)
        tier = "high" if user_id <= 200 else "mid" if user_id <= 700 else "low"
        weight = 6 if tier == "high" else 3 if tier == "mid" else 1
        weighted_user_ids.extend([user_id] * weight)
        users.append([user_id, "user_{}".format(user_id), "user{}@email.com".format(user_id),
                      (datetime(2023, 1, 1) + timedelta(days=register_day)).date(),
                      city, province, "active"])
    write_csv("seed_users.csv", users)
    print("users: {} rows".format(len(users)))
    return weighted_user_ids
```

- [ ] **Step 3: Implement weighted order dates, variable item counts, status events, and reconciliation**

Add helpers:

```python
def choose_day():
    days = list(range(365))
    weights = []
    for day in days:
        day_of_year = day + 1
        if day_of_year == 316:
            weight = 100
        elif 306 <= day_of_year <= 315:
            weight = 5
        elif 317 <= day_of_year <= 319:
            weight = 10
        elif (BASE_TIME + timedelta(days=day)).weekday() >= 5:
            weight = 1.5
        else:
            weight = 1
        weights.append(weight)
    return random.choices(days, weights=weights, k=1)[0]


def choose_order_time(day):
    hour = random.choices(
        list(range(24)),
        weights=[4, 3, 2, 2, 2, 3, 5, 8, 9, 8, 7, 10, 12, 9, 8, 8, 9, 11, 14, 16, 20, 22, 20, 12],
        k=1,
    )[0]
    if day + 1 == 316:
        hour = random.choices(list(range(24)), weights=[25, 20, 4, 2, 2, 3, 5, 7, 8, 8, 7, 8, 10, 8, 7, 8, 9, 11, 14, 16, 25, 30, 30, 20], k=1)[0]
    return BASE_TIME + timedelta(
        days=day,
        hours=hour,
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
        milliseconds=random.randint(0, 999),
    )


def promo_for_day(day):
    day_of_year = day + 1
    for promo_id, promo in PROMOS.items():
        if promo["start"] <= day_of_year <= promo["end"]:
            return promo_id, promo["discount"]
    return None, Decimal("0.00")
```

Implement `gen_orders()` to write six CSV files:

```python
def gen_orders(products, weighted_user_ids, num=DEFAULT_ORDER_COUNT):
    order_rows, item_rows, payment_rows, event_rows = [], [], [], []
    item_id = 1
    payment_id = 1
    event_id = 1
    for order_id in range(1, num + 1):
        user_id = random.choice(weighted_user_ids)
        day = choose_day()
        order_time = choose_order_time(day)
        promo_id, discount = promo_for_day(day)
        status_random = random.random()
        if status_random < 0.70:
            status = "completed"
        elif status_random < 0.85:
            status = "paid"
        elif status_random < 0.95:
            status = "shipped"
        else:
            status = "cancelled"

        item_count = random.choices([1, 2, 3, 5, 10, 20], weights=[45, 30, 12, 8, 4, 1], k=1)[0]
        total = Decimal("0.00")
        for _ in range(item_count):
            product = random.choice(products)
            quantity = random.choices([1, 2, 3], weights=[60, 30, 10], k=1)[0]
            price_factor = Decimal(str(random.uniform(0.95, 1.05)))
            unit_price = money(product["price"] * price_factor)
            final_price = money(unit_price * (Decimal("1.00") - discount))
            line_amount = money(final_price * quantity)
            total += line_amount
            item_rows.append([item_id, order_id, product["product_id"], quantity, unit_price])
            item_id += 1

        total = money(total)
        order_rows.append([order_id, user_id, order_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                           status, total, promo_id if promo_id else ""])

        event_rows.append([event_id, order_id, "", "created", order_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], "system"])
        event_id += 1
        if status == "cancelled":
            cancel_time = order_time + timedelta(minutes=random.randint(1, 60))
            event_rows.append([event_id, order_id, "created", "cancelled", cancel_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], "system"])
            event_id += 1
        else:
            paid_time = order_time + timedelta(minutes=random.randint(0, 10))
            event_rows.append([event_id, order_id, "created", "paid", paid_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], "payment"])
            event_id += 1
            if status in ("shipped", "completed"):
                shipped_time = paid_time + timedelta(hours=random.randint(12, 48))
                event_rows.append([event_id, order_id, "paid", "shipped", shipped_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], "system"])
                event_id += 1
            if status == "completed":
                completed_time = shipped_time + timedelta(days=random.randint(1, 5))
                event_rows.append([event_id, order_id, "shipped", "completed", completed_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], "system"])
                event_id += 1
            method = random.choices(["支付宝", "微信", "银行卡"], weights=[40, 40, 20], k=1)[0]
            payment_rows.append([payment_id, order_id, method, paid_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], total, "completed"])
            payment_id += 1

    write_csv("seed_orders.csv", order_rows)
    write_csv("seed_order_items.csv", item_rows)
    write_csv("seed_payments.csv", payment_rows)
    write_csv("seed_order_status_events.csv", event_rows)
    print("orders: {} rows".format(len(order_rows)))
    print("order_items: {} rows".format(len(item_rows)))
    print("payments: {} rows".format(len(payment_rows)))
    print("order_status_events: {} rows".format(len(event_rows)))
```

- [ ] **Step 4: Wire the generator entrypoint**

Use this `write_seed_files()` entrypoint:

```python
def write_seed_files():
    random.seed(RANDOM_SEED)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    weighted_user_ids = gen_users()
    products = gen_products()
    gen_orders(products, weighted_user_ids, DEFAULT_ORDER_COUNT)
    print("All seed CSV files generated in {}".format(OUTPUT_DIR))


if __name__ == "__main__":
    write_seed_files()
```

- [ ] **Step 5: Run generator at a small scale**

Run:

```bash
cd sync && ORDER_COUNT=1000 python gen_data.py
```

Expected: `seed_orders.csv` has 1,000 rows, `seed_order_items.csv` has between 3,000 and 5,000 rows, and no `seed_*.sql` files are generated by this script.

- [ ] **Step 6: Commit**

```bash
git add sync/gen_data.py
git commit -m "feat: generate credible ecommerce csv data"
```

---

### Task 4: Load CSV Seeds Into MySQL

**Files:**
- Modify: `init_all.sh`

- [ ] **Step 1: Set default scale and generate CSV**

Replace the seed generation block with:

```bash
echo "Step 1: Generating seed data"
export ORDER_COUNT="${ORDER_COUNT:-200000}"
export SEED_OUTPUT_DIR="${SEED_OUTPUT_DIR:-$(pwd)/sync}"
cd sync
python gen_data.py
cd ..
```

- [ ] **Step 2: Replace SQL file loading with `LOAD DATA LOCAL INFILE`**

Replace the current seed SQL loading loop with:

```bash
echo "Step 2: Resetting and loading MySQL data"
docker-compose exec -T mysql mysql --local-infile=1 --default-character-set=utf8mb4 -uroot -proot -D ecommerce -e "SET FOREIGN_KEY_CHECKS=0; TRUNCATE TABLE order_status_events; TRUNCATE TABLE payments; TRUNCATE TABLE order_items; TRUNCATE TABLE orders; TRUNCATE TABLE products; TRUNCATE TABLE users; SET FOREIGN_KEY_CHECKS=1;"

load_csv() {
    local table_name="$1"
    local csv_path="$2"
    echo "  Loading ${table_name} from $(basename "$csv_path")"
    docker-compose exec -T mysql mysql --local-infile=1 --default-character-set=utf8mb4 -uroot -proot -D ecommerce -e "
LOAD DATA LOCAL INFILE '/dev/stdin'
INTO TABLE ${table_name}
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"'
LINES TERMINATED BY '\n';" < "$csv_path"
}

load_csv users sync/seed_users.csv
load_csv products sync/seed_products.csv
load_csv orders sync/seed_orders.csv
load_csv order_items sync/seed_order_items.csv
load_csv payments sync/seed_payments.csv
load_csv order_status_events sync/seed_order_status_events.csv
```

- [ ] **Step 3: Include status events in MySQL row-count verification**

Use this verification query:

```bash
docker-compose exec -T mysql mysql --default-character-set=utf8mb4 -uroot -proot -D ecommerce -e "SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users UNION ALL SELECT 'products', COUNT(*) FROM products UNION ALL SELECT 'orders', COUNT(*) FROM orders UNION ALL SELECT 'order_items', COUNT(*) FROM order_items UNION ALL SELECT 'payments', COUNT(*) FROM payments UNION ALL SELECT 'order_status_events', COUNT(*) FROM order_status_events;"
```

- [ ] **Step 4: Run a small full MySQL seed load**

Run:

```bash
ORDER_COUNT=1000 bash init_all.sh
```

Expected at this stage: MySQL loading succeeds, later YMatrix ETL may fail because warehouse schemas are not yet updated.

- [ ] **Step 5: Commit**

```bash
git add init_all.sh
git commit -m "feat: load ecommerce csv seeds into mysql"
```

---

### Task 5: Update ODS and Python Extraction/Loading

**Files:**
- Modify: `ymatrix/init/02_ods.sql`
- Modify: `sync/extract.py`
- Modify: `sync/transform.py`
- Modify: `sync/load_ods.py`

- [ ] **Step 1: Update ODS SQL**

Change ODS time columns and add status events:

```sql
CREATE TABLE ods_orders (
    order_id INT, user_id INT, order_date TIMESTAMP(3), status VARCHAR(20),
    total_amount NUMERIC(10,2), promo_id INT, sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (order_id) ORDER BY (order_date, order_id)
PARTITION BY RANGE (order_date)
( START (TIMESTAMP '2024-01-01 00:00:00') INCLUSIVE END (TIMESTAMP '2025-01-01 00:00:00') EXCLUSIVE EVERY (INTERVAL '1 month') );

CREATE TABLE ods_payments (
    payment_id INT, order_id INT, method VARCHAR(20), pay_date TIMESTAMP(3),
    amount NUMERIC(10,2), status VARCHAR(20), sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (payment_id) ORDER BY (pay_date, payment_id);

CREATE TABLE ods_order_status_events (
    event_id BIGINT, order_id INT, from_status VARCHAR(20), to_status VARCHAR(20),
    event_time TIMESTAMP(3), operator_type VARCHAR(20), sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (event_id) ORDER BY (event_time, event_id)
PARTITION BY RANGE (event_time)
( START (TIMESTAMP '2024-01-01 00:00:00') INCLUSIVE END (TIMESTAMP '2025-01-10 00:00:00') EXCLUSIVE EVERY (INTERVAL '1 month') );
```

Update the comparison tables to use `order_date TIMESTAMP(3)`.

- [ ] **Step 2: Extract the new source table**

Change `sync/extract.py`:

```python
TABLES = ["users", "products", "orders", "order_items", "payments", "order_status_events"]
```

- [ ] **Step 3: Clean timestamp and event fields**

Add a cleaner in `sync/transform.py`:

```python
def clean_order_status_events(df):
    df = df.dropna(subset=["event_id", "order_id", "to_status", "event_time"])
    df["from_status"] = df["from_status"].fillna("")
    df["operator_type"] = df["operator_type"].fillna("system")
    return df
```

Update the cleaner map:

```python
cleaners = {
    "users": clean_users,
    "products": clean_products,
    "orders": clean_orders,
    "order_items": clean_order_items,
    "payments": clean_payments,
    "order_status_events": clean_order_status_events,
}
```

- [ ] **Step 4: Load status events through mxgate**

Add to `sync/load_ods.py`:

```python
def load_ods_order_status_events(df):
    rows = df[["event_id", "order_id", "from_status", "to_status", "event_time", "operator_type"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_order_status_events", rows)
    return len(rows)
```

Update the loader map:

```python
loaders = {
    "users": load_ods_users,
    "products": load_ods_products,
    "orders": load_ods_orders,
    "order_items": load_ods_order_items,
    "payments": load_ods_payments,
    "order_status_events": load_ods_order_status_events,
}
```

- [ ] **Step 5: Run schema creation and ODS load at small scale**

Run:

```bash
ORDER_COUNT=1000 bash init_all.sh
```

Expected at this stage: ODS loading succeeds, DWD or DWS may still fail until later tasks.

- [ ] **Step 6: Commit**

```bash
git add ymatrix/init/02_ods.sql sync/extract.py sync/transform.py sync/load_ods.py
git commit -m "feat: load timestamped ods event data"
```

---

### Task 6: Update DIM and DWD Layer

**Files:**
- Modify: `ymatrix/init/03_dim.sql`
- Modify: `ymatrix/init/03_dwd.sql`
- Modify: `sync/load_dim.py`
- Modify: `sync/load_dwd.py`

- [ ] **Step 1: Complete region DIM rows**

Update `ymatrix/init/03_dim.sql` `dim_region` inserts to the same ten city rows used in `mysql/init.sql`.

- [ ] **Step 2: Add DWD columns and event fact**

Update `ymatrix/init/03_dwd.sql`:

```sql
CREATE TABLE dwd_order_fact (
    order_id INT, user_id INT, order_date DATE, order_time TIMESTAMP(3),
    region_id INT, promo_id INT DEFAULT 0, total_amount NUMERIC(12,2),
    freight_amount NUMERIC(10,2) DEFAULT 0, discount_amount NUMERIC(10,2) DEFAULT 0,
    pay_time TIMESTAMP(3), cancel_time TIMESTAMP(3), finish_time TIMESTAMP(3),
    source_type VARCHAR(20), status VARCHAR(20)
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (order_id) ORDER BY (order_date, order_id)
PARTITION BY RANGE (order_date)
( START (DATE '2024-01-01') INCLUSIVE END (DATE '2025-01-01') EXCLUSIVE EVERY (INTERVAL '1 month') );

CREATE TABLE dwd_order_detail_fact (
    detail_id INT, order_id INT, user_id INT, sku_id INT, order_date DATE,
    order_time TIMESTAMP(3), region_id INT, promo_id INT, sku_num INT,
    original_price NUMERIC(10,2), final_price NUMERIC(10,2),
    line_amount NUMERIC(12,2), source_type VARCHAR(20)
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (detail_id) ORDER BY (order_date, detail_id)
PARTITION BY RANGE (order_date)
( START (DATE '2024-01-01') INCLUSIVE END (DATE '2025-01-01') EXCLUSIVE EVERY (INTERVAL '1 month') );

CREATE TABLE dwd_order_status_event_fact (
    event_id BIGINT, order_id INT, user_id INT, from_status VARCHAR(20),
    to_status VARCHAR(20), event_time TIMESTAMP(3), event_date DATE,
    operator_type VARCHAR(20)
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (event_id) ORDER BY (event_date, event_id)
PARTITION BY RANGE (event_date)
( START (DATE '2024-01-01') INCLUSIVE END (DATE '2025-01-10') EXCLUSIVE EVERY (INTERVAL '1 month') );
```

- [ ] **Step 3: Populate DWD with explicit timezone conversion**

In `sync/load_dwd.py`, replace the order fact insert with:

```sql
INSERT INTO dwd_order_fact (order_id,user_id,order_date,order_time,region_id,promo_id,total_amount,freight_amount,discount_amount,pay_time,cancel_time,finish_time,source_type,status)
SELECT
  o.order_id,
  o.user_id,
  DATE(o.order_date AT TIME ZONE 'Asia/Shanghai') AS order_date,
  o.order_date AT TIME ZONE 'Asia/Shanghai' AS order_time,
  COALESCE(r.region_id,0),
  COALESCE(o.promo_id,0),
  o.total_amount,
  CASE WHEN o.total_amount >= 200 THEN 0 ELSE ROUND((RANDOM()*7+8)::NUMERIC,2) END,
  ROUND(COALESCE(d.discount_amount, 0), 2),
  p.pay_date AT TIME ZONE 'Asia/Shanghai' AS pay_time,
  CASE WHEN o.status='cancelled' THEN e_cancel.event_time AT TIME ZONE 'Asia/Shanghai' ELSE NULL END,
  CASE WHEN o.status='completed' THEN e_finish.event_time AT TIME ZONE 'Asia/Shanghai' ELSE NULL END,
  CASE MOD(o.order_id,10) WHEN 0 THEN 'miniapp' WHEN 1 THEN 'miniapp' WHEN 2 THEN 'web' WHEN 3 THEN 'web' WHEN 4 THEN 'web' ELSE 'app' END,
  o.status
FROM ods_orders o
LEFT JOIN ods_users u ON o.user_id=u.user_id
LEFT JOIN dim_region r ON u.city=r.city AND u.province=r.province
LEFT JOIN ods_payments p ON o.order_id=p.order_id
LEFT JOIN ods_order_status_events e_cancel ON o.order_id=e_cancel.order_id AND e_cancel.to_status='cancelled'
LEFT JOIN ods_order_status_events e_finish ON o.order_id=e_finish.order_id AND e_finish.to_status='completed'
LEFT JOIN (
  SELECT oi.order_id, SUM(ROUND(oi.qty * oi.unit_price * COALESCE(pm.discount_rate,0), 2)) AS discount_amount
  FROM ods_order_items oi
  JOIN ods_orders oo ON oi.order_id=oo.order_id
  LEFT JOIN dim_promotion pm ON oo.promo_id=pm.promo_id
  GROUP BY oi.order_id
) d ON o.order_id=d.order_id
WHERE o.status IS NOT NULL;
```

Replace the detail insert with:

```sql
INSERT INTO dwd_order_detail_fact (detail_id,order_id,user_id,sku_id,order_date,order_time,region_id,promo_id,sku_num,original_price,final_price,line_amount,source_type)
SELECT
  oi.item_id,
  oi.order_id,
  o.user_id,
  oi.product_id,
  DATE(o.order_date AT TIME ZONE 'Asia/Shanghai') AS order_date,
  o.order_date AT TIME ZONE 'Asia/Shanghai' AS order_time,
  COALESCE(r.region_id,0),
  COALESCE(o.promo_id,0),
  oi.qty,
  oi.unit_price,
  ROUND(oi.unit_price * (1 - COALESCE(p.discount_rate,0)), 2),
  ROUND(oi.qty * oi.unit_price * (1 - COALESCE(p.discount_rate,0)), 2),
  CASE MOD(oi.order_id,10) WHEN 0 THEN 'miniapp' WHEN 1 THEN 'miniapp' WHEN 2 THEN 'web' WHEN 3 THEN 'web' WHEN 4 THEN 'web' ELSE 'app' END
FROM ods_order_items oi
JOIN ods_orders o ON oi.order_id=o.order_id
LEFT JOIN ods_users u ON o.user_id=u.user_id
LEFT JOIN dim_region r ON u.city=r.city AND u.province=r.province
LEFT JOIN dim_promotion p ON o.promo_id=p.promo_id
WHERE o.status IS NOT NULL;
```

Add status-event fact loading:

```sql
INSERT INTO dwd_order_status_event_fact (event_id,order_id,user_id,from_status,to_status,event_time,event_date,operator_type)
SELECT
  e.event_id,
  e.order_id,
  o.user_id,
  e.from_status,
  e.to_status,
  e.event_time AT TIME ZONE 'Asia/Shanghai',
  DATE(e.event_time AT TIME ZONE 'Asia/Shanghai'),
  e.operator_type
FROM ods_order_status_events e
JOIN ods_orders o ON e.order_id=o.order_id;
```

- [ ] **Step 4: Add row count logging for the event fact**

After loading the event fact:

```python
rows = _count("dwd_order_status_event_fact")
results.append({"step":"dwd_order_status_event_fact","rows":rows,"ms":int((time.time()-t0)*1000),"status":"success"})
print("dwd_order_status_event_fact: {} rows ({}ms)".format(rows, results[-1]["ms"]))
```

- [ ] **Step 5: Run DWD at small scale**

Run:

```bash
ORDER_COUNT=1000 bash init_all.sh
```

Expected: DWD fact table loads succeed; DWS/ADS may still fail until Task 7.

- [ ] **Step 6: Commit**

```bash
git add ymatrix/init/03_dim.sql ymatrix/init/03_dwd.sql sync/load_dim.py sync/load_dwd.py
git commit -m "feat: build timezone-aware dwd facts"
```

---

### Task 7: Add DWS and ADS Time-Series Metrics

**Files:**
- Modify: `ymatrix/init/04_dws.sql`
- Modify: `ymatrix/init/05_ads.sql`
- Modify: `init_all.sh`
- Modify: `sync/load_dwd.py`

- [ ] **Step 1: Replace DWS materialized views**

Use valid-order semantics in `ymatrix/init/04_dws.sql`:

```sql
CREATE MATERIALIZED VIEW dws_daily_gmv AS
SELECT time_bucket('1 day', order_time) AS dt,
       COUNT(*) AS order_count,
       SUM(total_amount) AS gmv,
       AVG(total_amount) AS avg_order_amount
FROM dwd_order_fact
WHERE status IN ('paid','shipped','completed')
GROUP BY dt DISTRIBUTED BY (dt);

CREATE MATERIALIZED VIEW dws_minute_order_traffic AS
SELECT time_bucket('1 minute', order_time) AS bucket_time,
       COUNT(*) AS minute_order_count,
       SUM(total_amount) AS minute_gmv,
       AVG(total_amount) AS avg_order_amount
FROM dwd_order_fact
WHERE status IN ('paid','shipped','completed')
GROUP BY bucket_time DISTRIBUTED BY (bucket_time);

CREATE MATERIALIZED VIEW dws_product_daily_sales AS
SELECT order_date, sku_id, SUM(sku_num) AS total_qty, SUM(line_amount) AS total_revenue
FROM dwd_order_detail_fact d
JOIN dwd_order_fact f ON d.order_id=f.order_id
WHERE f.status IN ('paid','shipped','completed')
GROUP BY order_date, sku_id DISTRIBUTED BY (order_date);

CREATE MATERIALIZED VIEW dws_user_purchase_stats AS
SELECT user_id, COUNT(*) AS total_orders, SUM(total_amount) AS total_spent
FROM dwd_order_fact
WHERE status IN ('paid','shipped','completed')
GROUP BY user_id DISTRIBUTED BY (user_id);

CREATE MATERIALIZED VIEW dws_order_status_funnel AS
SELECT to_status AS status, COUNT(DISTINCT order_id) AS order_count
FROM dwd_order_status_event_fact
GROUP BY to_status DISTRIBUTED BY (status);

CREATE MATERIALIZED VIEW dws_order_fulfillment_latency AS
SELECT
  AVG(EXTRACT(EPOCH FROM (shipped.event_time - paid.event_time)) / 3600.0) AS paid_to_shipped_hours,
  AVG(EXTRACT(EPOCH FROM (completed.event_time - shipped.event_time)) / 3600.0) AS shipped_to_completed_hours
FROM dwd_order_status_event_fact paid
JOIN dwd_order_status_event_fact shipped ON paid.order_id=shipped.order_id AND shipped.to_status='shipped'
JOIN dwd_order_status_event_fact completed ON paid.order_id=completed.order_id AND completed.to_status='completed'
WHERE paid.to_status='paid';

CREATE MATERIALIZED VIEW dws_promo_daily_compare AS
SELECT
  CASE WHEN promo_id > 0 THEN 'promo' ELSE 'normal' END AS period,
  COUNT(DISTINCT order_date) AS days,
  COUNT(*) AS order_cnt,
  SUM(total_amount) AS gmv,
  SUM(total_amount) / NULLIF(COUNT(DISTINCT order_date),0) AS daily_avg_gmv,
  AVG(total_amount) AS avg_order_value
FROM dwd_order_fact
WHERE status IN ('paid','shipped','completed')
GROUP BY 1 DISTRIBUTED BY (period);
```

- [ ] **Step 2: Refresh all DWS views**

Update `sync/load_dwd.py` refresh list:

```python
for v in [
    "dws_daily_gmv",
    "dws_minute_order_traffic",
    "dws_product_daily_sales",
    "dws_user_purchase_stats",
    "dws_order_status_funnel",
    "dws_order_fulfillment_latency",
    "dws_promo_daily_compare",
]:
    _sql("REFRESH MATERIALIZED VIEW {};".format(v))
```

- [ ] **Step 3: Drop all new DWS/ADS objects in `init_all.sh` reset**

Add these drops before DWD table drops:

```sql
DROP VIEW IF EXISTS ads_gmv_running_total CASCADE;
DROP VIEW IF EXISTS ads_minute_traffic CASCADE;
DROP VIEW IF EXISTS ads_traffic_peak_minutes CASCADE;
DROP VIEW IF EXISTS ads_order_status_funnel CASCADE;
DROP VIEW IF EXISTS ads_order_fulfillment_latency CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dws_minute_order_traffic CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dws_order_status_funnel CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dws_order_fulfillment_latency CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dws_promo_daily_compare CASCADE;
DROP TABLE IF EXISTS dwd_order_status_event_fact CASCADE;
DROP TABLE IF EXISTS ods_order_status_events CASCADE;
```

- [ ] **Step 4: Add ADS views**

Append to `ymatrix/init/05_ads.sql`:

```sql
CREATE VIEW ads_minute_traffic AS
SELECT bucket_time, minute_order_count, minute_gmv, avg_order_amount
FROM dws_minute_order_traffic
ORDER BY bucket_time;

CREATE VIEW ads_traffic_peak_minutes AS
SELECT bucket_time, minute_order_count, minute_gmv
FROM dws_minute_order_traffic
ORDER BY minute_order_count DESC, minute_gmv DESC
LIMIT 20;

CREATE VIEW ads_order_status_funnel AS
SELECT status, order_count
FROM dws_order_status_funnel
ORDER BY CASE status
  WHEN 'created' THEN 1
  WHEN 'paid' THEN 2
  WHEN 'shipped' THEN 3
  WHEN 'completed' THEN 4
  WHEN 'cancelled' THEN 5
  ELSE 9
END;

CREATE VIEW ads_order_fulfillment_latency AS
SELECT paid_to_shipped_hours, shipped_to_completed_hours
FROM dws_order_fulfillment_latency;

CREATE VIEW ads_gmv_running_total AS
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

Replace existing `ads_promo_compare` with:

```sql
CREATE VIEW ads_promo_compare AS
SELECT
  period,
  days,
  order_cnt,
  gmv,
  daily_avg_gmv,
  avg_order_value,
  CASE
    WHEN period = 'promo' THEN
      (daily_avg_gmv / NULLIF((SELECT daily_avg_gmv FROM dws_promo_daily_compare WHERE period='normal'), 0) - 1) * 100
    ELSE 0
  END AS uplift_pct
FROM dws_promo_daily_compare;
```

- [ ] **Step 5: Run small full flow**

Run:

```bash
ORDER_COUNT=1000 bash init_all.sh
```

Expected: all DWS refreshes and ADS creation succeed; verification may still fail threshold checks that need larger data.

- [ ] **Step 6: Commit**

```bash
git add ymatrix/init/04_dws.sql ymatrix/init/05_ads.sql init_all.sh sync/load_dwd.py
git commit -m "feat: add ymatrix timeseries warehouse metrics"
```

---

### Task 8: Complete Verification and Documentation

**Files:**
- Modify: `sync/verify.py`
- Modify: `grafana/dashboards/ymatrix_dw_demo.json`
- Modify: `README.md`
- Modify: `report.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Adjust verification thresholds for configurable scale**

At the top of `sync/verify.py`, add:

```python
import os

EXPECTED_ORDERS = int(os.environ.get("ORDER_COUNT", "200000"))
```

Change the ODS order check:

```python
_pass(results, "ods_orders equals configured scale", orders == EXPECTED_ORDERS, "{} rows".format(orders))
```

Add a ratio check:

```python
items = _int("SELECT COUNT(*) FROM ods_order_items;")
_pass(results, "order_items 3x to 5x orders", EXPECTED_ORDERS * 3 <= items <= EXPECTED_ORDERS * 5, "{} rows".format(items))
```

- [ ] **Step 2: Add traffic burst verification**

Add:

```python
nov11 = _int("SELECT COUNT(*) FROM dwd_order_fact WHERE order_date = DATE '2024-11-11';")
normal_avg = _float("""
    SELECT AVG(order_count)
    FROM (
      SELECT order_date, COUNT(*) AS order_count
      FROM dwd_order_fact
      WHERE order_date <> DATE '2024-11-11'
      GROUP BY order_date
    ) s;
""")
_pass(results, "Nov 11 >= 50x normal daily average", normal_avg > 0 and nov11 >= normal_avg * 50, "{} vs {:.2f}".format(nov11, normal_avg))
```

- [ ] **Step 3: Update Grafana panels**

Keep six panels and replace the least useful panel with the running GMV panel. The query must be:

```sql
SELECT bucket_time AS time, running_gmv, minute_gmv, running_order_count
FROM ads_gmv_running_total
ORDER BY bucket_time
```

Ensure the dashboard JSON keeps:

```json
"timezone": "Asia/Shanghai"
```

- [ ] **Step 4: Update documentation**

Document these facts in `README.md`, `report.md`, and `AGENTS.md`:

```text
Default development scale: ORDER_COUNT=200000
Performance demo scale: ORDER_COUNT=1000000
Stress scale: ORDER_COUNT=5000000
Business timezone: Asia/Shanghai
Source time fields: orders.order_date and payments.pay_date remain source names, upgraded to millisecond timestamps.
DWD semantic fields: order_time, pay_time, order_date.
New ADS view: ads_gmv_running_total.
```

- [ ] **Step 5: Run default-scale verification**

Run:

```bash
docker-compose down -v
docker-compose up -d
bash init_all.sh
```

Expected:

```text
orders: 200000 rows
order_items: between 600000 and 1000000 rows
order_status_events: non-empty and at least 200000 rows
all verify.py checks PASS
Grafana: http://localhost:3000
```

- [ ] **Step 6: Run performance-demo smoke check**

Run:

```bash
docker-compose down -v
docker-compose up -d
ORDER_COUNT=1000000 bash init_all.sh
```

Expected: pipeline completes without changing code. Record elapsed time in `docs/full-flow-repair-verification-2026-07-08.md` or a new dated verification report if the run is completed during implementation.

- [ ] **Step 7: Commit**

```bash
git add sync/verify.py grafana/dashboards/ymatrix_dw_demo.json README.md report.md AGENTS.md
git commit -m "docs: document ecommerce timeseries demo operation"
```

---

### Task 9: Final Integration Gate

**Files:**
- Create: `docs/ecommerce-timeseries-verification-2026-07-09.md`

- [ ] **Step 1: Run clean default full flow**

Run:

```bash
git status --short
docker-compose down -v
docker-compose up -d
bash init_all.sh
```

Expected: `init_all.sh` exits 0 and `git status --short` shows only expected documentation output if a verification report is being written.

- [ ] **Step 2: Capture core SQL evidence**

Run:

```bash
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e "SELECT COUNT(*) orders FROM orders; SELECT COUNT(*) order_items FROM order_items; SELECT COUNT(*) order_status_events FROM order_status_events;"
docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -c "SELECT COUNT(*) FROM ads_gmv_running_total;"
docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -c "SELECT * FROM ads_gmv_running_total ORDER BY bucket_time LIMIT 5;"
docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -c "SELECT COUNT(*) FROM etl_log;"
```

Expected: non-empty counts and increasing running GMV.

- [ ] **Step 3: Verify Grafana health**

Run:

```bash
curl -fsS http://localhost:3000/api/health
```

Expected: JSON response includes `"database": "ok"` or equivalent healthy status.

- [ ] **Step 4: Write verification report with actual command output**

After Step 2 and Step 3 have completed, create `docs/ecommerce-timeseries-verification-2026-07-09.md` with the values printed by those commands. The report must follow this shape and must contain concrete numbers before it is staged:

```markdown
# Ecommerce Timeseries Verification - 2026-07-09

## Environment

- Branch: codex/fix-full-flow
- Default order count: 200000
- Business timezone: Asia/Shanghai

## Commands

- docker-compose down -v
- docker-compose up -d
- bash init_all.sh

## Results

- MySQL orders: 200000
- MySQL order_items: 724381
- MySQL order_status_events: 612944
- YMatrix ads_gmv_running_total rows: 1438
- verify.py result: PASS
- Grafana health: {"database":"ok","version":"12.0.0","commit":"local"}

## Notes

- DWD timestamps use explicit Asia/Shanghai conversion.
- 1000000-order performance run is not part of the default gate. Record it in a separate section only when that command is actually executed.
```

The sample numbers above show the required format, not expected fixed values except `MySQL orders: 200000`. Replace the sample values with the values from the current run before staging the report.

- [ ] **Step 5: Commit final verification report**

```bash
git add docs/ecommerce-timeseries-verification-2026-07-09.md
git commit -m "test: record ecommerce timeseries verification"
```

- [ ] **Step 6: Push branch**

```bash
git status --short
git push origin codex/fix-full-flow
```

Expected: branch pushes successfully. Do not operate the browser for PR creation unless the user explicitly asks.

---

## Self-Review Checklist

- Spec coverage: Tasks cover credible products, product-price linkage, variable item counts, weighted double-11 traffic, status event stream, MySQL CSV load, mxgate ODS load, DWD explicit timezone conversion, amount reconciliation, minute `time_bucket`, running GMV ADS, Grafana panel, and default/performance scale split.
- Placeholder scan: no task uses unresolved placeholders; the only report template is created during final verification and requires actual command output before commit.
- Type consistency: source fields remain `orders.order_date` and `payments.pay_date`; ODS keeps those names as `TIMESTAMP(3)`; DWD exposes `order_time`, `pay_time`, and `order_date`.
- Execution boundary: this plan writes only implementation steps. Code changes begin only when execution starts with `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
