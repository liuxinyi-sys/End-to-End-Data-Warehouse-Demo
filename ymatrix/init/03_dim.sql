CREATE TABLE dim_region (
    region_id INT, province VARCHAR(50), city VARCHAR(50),
    district VARCHAR(50), region_tier VARCHAR(10)
) USING HEAP DISTRIBUTED BY (region_id);
INSERT INTO dim_region VALUES
(1,'北京市','北京','朝阳区','T1'),
(2,'上海市','上海','浦东新区','T1'),
(3,'广东省','广州','天河区','T1'),
(4,'广东省','深圳','南山区','T1'),
(5,'四川省','成都','高新区','T2'),
(6,'湖北省','武汉','洪山区','T2'),
(7,'浙江省','杭州','西湖区','T2'),
(8,'江苏省','南京','鼓楼区','T2'),
(9,'陕西省','西安','雁塔区','T2'),
(10,'重庆市','重庆','渝中区','T2');

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
