"""Generate deterministic seed SQL files for the MySQL business database."""
import os
import random

random.seed(42)


def gen_users(num=1000):
    cities = [
        ("北京", "北京市"), ("上海", "上海市"), ("广州", "广东省"),
        ("深圳", "广东省"), ("成都", "四川省"), ("武汉", "湖北省"),
        ("杭州", "浙江省"), ("南京", "江苏省"), ("西安", "陕西省"),
        ("重庆", "重庆市"),
    ]
    values = []
    for user_id in range(1, num + 1):
        city, province = random.choice(cities)
        register_day = random.randint(0, 365)
        values.append(
            "({},'user_{}','user{}@email.com',DATE_ADD('2023-01-01',INTERVAL {} DAY),'{}','{}','active')".format(
                user_id, user_id, user_id, register_day, city, province
            )
        )
    with open("seed_users.sql", "w", encoding="utf-8") as output:
        output.write("INSERT INTO users VALUES\n" + ",\n".join(values) + ";")
    print("users: {} rows".format(len(values)))


def gen_products(num=500):
    categories = {
        "电子": ["华为", "小米", "Apple", "OPPO", "vivo"],
        "服装": ["Nike", "Adidas", "优衣库", "ZARA", "H&M"],
        "美妆": ["雅诗兰黛", "兰蔻", "SK-II", "欧莱雅", "资生堂"],
        "食品": ["三只松鼠", "良品铺子", "百草味", "来伊份", "恰恰"],
        "家居": ["宜家", "MUJI", "网易严选", "小米有品", "名创优品"],
    }
    product_types = [
        "手机", "平板", "笔记本", "耳机", "充电器",
        "T恤", "牛仔裤", "外套", "运动鞋", "帽子",
        "精华液", "面霜", "眼霜", "面膜", "洗面奶",
        "坚果礼盒", "肉干", "果脯", "饼干", "巧克力",
        "台灯", "收纳盒", "毛巾", "拖鞋", "靠垫",
    ]
    values = []
    product_id = 1
    for category, brands in categories.items():
        for _ in range(num // len(categories)):
            brand = random.choice(brands)
            product_type = random.choice(product_types)
            price = round(random.uniform(19.9, 9999.0), 2)
            stock = random.randint(10, 5000)
            values.append("({},'{} {}','{}',{},{})".format(
                product_id, brand, product_type, category, price, stock
            ))
            product_id += 1
    with open("seed_products.sql", "w", encoding="utf-8") as output:
        output.write("INSERT INTO products VALUES\n" + ",\n".join(values) + ";")
    print("products: {} rows".format(len(values)))


def gen_orders(num=50000):
    order_values, item_values, payment_values = [], [], []
    item_id = 1
    payment_id = 1
    for order_id in range(1, num + 1):
        user_id = random.randint(1, 1000)
        if random.random() < 0.10:
            day = 315
        else:
            day = random.choice(list(range(315)) + list(range(316, 365)))
        order_date = "DATE_ADD('2024-01-01',INTERVAL {} DAY)".format(day)
        day_of_year = day + 1
        if 306 <= day_of_year <= 315:
            promo_id, discount = 1, 0.10
        elif day_of_year == 316:
            promo_id, discount = 2, 0.25
        elif 317 <= day_of_year <= 319:
            promo_id, discount = 3, 0.15
        else:
            promo_id, discount = "NULL", 0.0

        status_random = random.random()
        if status_random < 0.70:
            status = "completed"
        elif status_random < 0.85:
            status = "paid"
        elif status_random < 0.95:
            status = "shipped"
        else:
            status = "cancelled"

        total = 0.0
        for _ in range(4):
            product_id = random.randint(1, 500)
            quantity = random.choices([1, 2, 3], weights=[60, 30, 10])[0]
            unit_price = round(random.uniform(19.9, 9999.0), 2)
            final_price = round(unit_price * (1 - discount), 2)
            total += final_price * quantity
            item_values.append("({},{},{},{},{})".format(
                item_id, order_id, product_id, quantity, unit_price
            ))
            item_id += 1

        total = round(total, 2)
        order_values.append("({},{},{},'{}',{},{})".format(
            order_id, user_id, order_date, status, total, promo_id
        ))
        method = random.choices(["支付宝", "微信", "银行卡"], weights=[40, 40, 20])[0]
        pay_date = "DATE_ADD('2024-01-01',INTERVAL {} DAY)".format(day + random.randint(0, 2))
        payment_values.append("({},{},'{}',{},{},'completed')".format(
            payment_id, order_id, method, pay_date, total
        ))
        payment_id += 1

    files = [
        ("seed_orders.sql", order_values),
        ("seed_order_items.sql", item_values),
        ("seed_payments.sql", payment_values),
    ]
    for filename, values in files:
        table = filename.split("_", 1)[1].replace(".sql", "")
        with open(filename, "w", encoding="utf-8") as output:
            output.write("INSERT INTO " + table + " VALUES\n" + ",\n".join(values) + ";")
        print("{}: {} rows".format(filename, len(values)))


def write_sql_files():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    gen_users()
    gen_products()
    gen_orders()
    print("All seed SQL files generated")


if __name__ == "__main__":
    write_sql_files()
