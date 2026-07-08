"""Generate seed data SQL files for MySQL business database."""
import random
import os

random.seed(42)

def gen_users(num=1000):
    cities = [("北京","北京市"),("上海","上海市"),("广州","广东省"),("深圳","广东省"),
              ("成都","四川省"),("武汉","湖北省"),("杭州","浙江省"),("南京","江苏省"),
              ("西安","陕西省"),("重庆","重庆市")]
    vals = []
    for i in range(1, num+1):
        city, prov = random.choice(cities)
        vals.append(f"({i},'user_{i}','user{i}@email.com',DATE_ADD('2023-01-01',INTERVAL {random.randint(0,365)} DAY),'{city}','{prov}','active')")
    sql = "INSERT INTO users VALUES\n" + ",\n".join(vals) + ";"
    with open("seed_users.sql","w",encoding="utf-8") as f: f.write(sql)
    print(f"users: {num} rows")

def gen_products(num=500):
    cats = {"电子":["华为","小米","Apple","OPPO","vivo"],"服装":["Nike","Adidas","优衣库","ZARA","H&M"],
            "美妆":["雅诗兰黛","兰蔻","SK-II","欧莱雅","资生堂"],"食品":["三只松鼠","良品铺子","百草味","来伊份","恰恰"],
            "家居":["宜家","MUJI","网易严选","小米有品","名创优品"]}
    prods = ["手机","平板","笔记本","耳机","充电器","T恤","牛仔裤","外套","运动鞋","帽子",
             "精华液","面霜","眼霜","面膜","洗面奶","坚果礼盒","肉干","果脯","饼干","巧克力",
             "台灯","收纳盒","毛巾","拖鞋","靠垫"]
    vals = []; pid = 1
    for cat, brands in cats.items():
        for _ in range(num // len(cats)):
            brand = random.choice(brands)
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
        day = random.randint(0, 364)
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
        total = 0.0
        for _ in range(4):
            prod = random.randint(1, 500)
            qty = random.choices([1,2,3], weights=[60,30,10])[0]
            up = round(random.uniform(19.9, 9999.0), 2)
            fp = round(up * (1 - disc), 2)
            total += fp * qty
            item_vals.append(f"({item_id},{oid},{prod},{qty},{round(up,2)})")
            item_id += 1
        total = round(total, 2)
        order_vals.append(f"({oid},{uid},{od},'{st}',{total},{pid})")
        method = random.choices(["支付宝","微信","银行卡"], weights=[40,40,20])[0]
        pd_ = f"DATE_ADD('2024-01-01',INTERVAL {day+random.randint(0,2)} DAY)"
        pay_vals.append(f"({pay_id},{oid},'{method}',{pd_},{total},'completed')")
        pay_id += 1
    for name, vals in [("seed_orders.sql",order_vals),("seed_order_items.sql",item_vals),("seed_payments.sql",pay_vals)]:
        tbl = name.split("_",1)[1].replace(".sql","")
        with open(name,"w",encoding="utf-8") as f:
            f.write("INSERT INTO " + tbl + " VALUES\n" + ",\n".join(vals) + ";")
        print(f"{name}: {len(vals)} rows")

def write_sql_files():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    gen_users()
    gen_products()
    gen_orders()
    print("All seed SQL files generated")

if __name__ == "__main__":
    write_sql_files()
