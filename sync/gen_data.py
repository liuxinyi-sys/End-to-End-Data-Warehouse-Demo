"""Generate deterministic seed CSV files for the MySQL business database."""
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
        writer = csv.writer(handle, lineterminator="\n")
        for row in rows:
            writer.writerow(row)
    return path


def format_datetime(value):
    return value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def gen_users(num=1000):
    cities = [
        ("北京", "北京市"),
        ("上海", "上海市"),
        ("广州", "广东省"),
        ("深圳", "广东省"),
        ("成都", "四川省"),
        ("武汉", "湖北省"),
        ("杭州", "浙江省"),
        ("南京", "江苏省"),
        ("西安", "陕西省"),
        ("重庆", "重庆市"),
    ]
    rows = []
    weighted_user_ids = []
    register_base = datetime(2023, 1, 1)
    for user_id in range(1, num + 1):
        city, province = random.choice(cities)
        register_date = (register_base + timedelta(days=random.randint(0, 365))).date()
        rows.append(
            [
                user_id,
                "user_{}".format(user_id),
                "user{}@email.com".format(user_id),
                register_date.isoformat(),
                city,
                province,
                "active",
            ]
        )
        if user_id <= 200:
            weight = 6
        elif user_id <= 700:
            weight = 3
        else:
            weight = 1
        weighted_user_ids.extend([user_id] * weight)

    write_csv("seed_users.csv", rows)
    print("users: {} rows".format(len(rows)))
    return weighted_user_ids


def gen_products(num=500):
    products = []
    rows = []
    categories = list(PRODUCT_CATALOG.keys())
    product_id = 1

    for index in range(num):
        category = categories[index % len(categories)]
        spec = PRODUCT_CATALOG[category]
        brand = random.choice(spec["brands"])
        product_type = random.choice(spec["types"])
        min_price, max_price = spec["price"]
        price = money(random.uniform(min_price, max_price))
        stock = random.randint(10, 5000)
        product_name = "{} {}".format(brand, product_type)
        product = {
            "product_id": product_id,
            "product_name": product_name,
            "category": category,
            "price": price,
            "stock": stock,
        }
        products.append(product)
        rows.append([product_id, product_name, category, str(price), stock])
        product_id += 1

    write_csv("seed_products.csv", rows)
    print("products: {} rows".format(len(rows)))
    return products


def choose_day():
    days = list(range(365))
    weights = []
    for day in days:
        day_of_year = day + 1
        if day_of_year == 316:
            weight = 100.0
        elif 306 <= day_of_year <= 315:
            weight = 5.0
        elif 317 <= day_of_year <= 319:
            weight = 10.0
        else:
            weight = 1.0

        order_date = BASE_TIME + timedelta(days=day)
        if order_date.weekday() >= 5:
            weight *= 1.5
        weights.append(weight)
    return random.choices(days, weights=weights, k=1)[0]


def choose_order_time(day):
    day_of_year = day + 1
    if day_of_year == 316:
        hours = list(range(24))
        hour_weights = [
            18 if hour in (0, 10, 20, 21, 22) else 6 if hour in (1, 9, 11, 19, 23) else 1
            for hour in hours
        ]
        hour = random.choices(hours, weights=hour_weights, k=1)[0]
    else:
        hour = random.choices(
            list(range(24)),
            weights=[1, 1, 1, 1, 1, 2, 4, 5, 6, 6, 5, 5, 5, 5, 5, 6, 7, 8, 8, 7, 6, 4, 3, 2],
            k=1,
        )[0]

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


def write_event(writer, event_id, order_id, from_status, to_status, event_time, operator_type="system"):
    writer.writerow([event_id, order_id, from_status, to_status, format_datetime(event_time), operator_type])


def gen_orders(products, weighted_user_ids, num=DEFAULT_ORDER_COUNT):
    order_path = os.path.join(OUTPUT_DIR, "seed_orders.csv")
    item_path = os.path.join(OUTPUT_DIR, "seed_order_items.csv")
    payment_path = os.path.join(OUTPUT_DIR, "seed_payments.csv")
    event_path = os.path.join(OUTPUT_DIR, "seed_order_status_events.csv")

    item_id = 1
    payment_id = 1
    event_id = 1
    order_count = 0
    item_count = 0
    payment_count = 0
    event_count = 0
    status_choices = ["completed", "paid", "shipped", "cancelled"]
    status_weights = [70, 15, 10, 5]
    payment_methods = ["支付宝", "微信", "银行卡"]
    payment_weights = [40, 40, 20]

    with open(order_path, "w", newline="", encoding="utf-8") as order_handle, open(
        item_path, "w", newline="", encoding="utf-8"
    ) as item_handle, open(payment_path, "w", newline="", encoding="utf-8") as payment_handle, open(
        event_path, "w", newline="", encoding="utf-8"
    ) as event_handle:
        order_writer = csv.writer(order_handle, lineterminator="\n")
        item_writer = csv.writer(item_handle, lineterminator="\n")
        payment_writer = csv.writer(payment_handle, lineterminator="\n")
        event_writer = csv.writer(event_handle, lineterminator="\n")

        for order_id in range(1, num + 1):
            user_id = random.choice(weighted_user_ids)
            day = choose_day()
            order_time = choose_order_time(day)
            promo_id, discount_rate = promo_for_day(day)
            status = random.choices(status_choices, weights=status_weights, k=1)[0]
            item_total = random.choices([1, 2, 3, 5, 10, 20], weights=[45, 30, 12, 8, 4, 1], k=1)[0]
            total = Decimal("0.00")

            for _ in range(item_total):
                product = random.choice(products)
                quantity = random.choices([1, 2, 3], weights=[60, 30, 10], k=1)[0]
                unit_price = money(product["price"] * money(random.uniform(0.95, 1.05)))
                line_amount = money(unit_price * quantity * (Decimal("1.00") - discount_rate))
                total += line_amount
                item_writer.writerow([item_id, order_id, product["product_id"], quantity, str(unit_price)])
                item_id += 1
                item_count += 1

            order_writer.writerow(
                [
                    order_id,
                    user_id,
                    format_datetime(order_time),
                    status,
                    str(money(total)),
                    promo_id if promo_id is not None else "",
                ]
            )
            order_count += 1

            write_event(event_writer, event_id, order_id, "", "created", order_time)
            event_id += 1
            event_count += 1

            if status == "cancelled":
                cancelled_time = order_time + timedelta(minutes=random.randint(1, 60))
                write_event(event_writer, event_id, order_id, "created", "cancelled", cancelled_time)
                event_id += 1
                event_count += 1
                continue

            paid_time = order_time + timedelta(minutes=random.randint(0, 10), milliseconds=random.randint(0, 999))
            write_event(event_writer, event_id, order_id, "created", "paid", paid_time, "payment")
            event_id += 1
            event_count += 1

            payment_writer.writerow(
                [
                    payment_id,
                    order_id,
                    random.choices(payment_methods, weights=payment_weights, k=1)[0],
                    format_datetime(paid_time),
                    str(money(total)),
                    "completed",
                ]
            )
            payment_id += 1
            payment_count += 1

            if status in ("shipped", "completed"):
                shipped_time = paid_time + timedelta(hours=random.randint(12, 48), milliseconds=random.randint(0, 999))
                write_event(event_writer, event_id, order_id, "paid", "shipped", shipped_time)
                event_id += 1
                event_count += 1

                if status == "completed":
                    completed_time = shipped_time + timedelta(days=random.randint(1, 5), milliseconds=random.randint(0, 999))
                    write_event(event_writer, event_id, order_id, "shipped", "completed", completed_time)
                    event_id += 1
                    event_count += 1

    print("orders: {} rows".format(order_count))
    print("order_items: {} rows".format(item_count))
    print("payments: {} rows".format(payment_count))
    print("order_status_events: {} rows".format(event_count))


def write_seed_files():
    random.seed(RANDOM_SEED)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    weighted_user_ids = gen_users()
    products = gen_products()
    gen_orders(products, weighted_user_ids, DEFAULT_ORDER_COUNT)
    print("All seed CSV files generated in {}".format(OUTPUT_DIR))


if __name__ == "__main__":
    write_seed_files()
