-- ============================================================
-- MySQL 业务库初始化脚本
-- 在容器首次启动时由 /docker-entrypoint-initdb.d/init.sql 自动执行
-- 创建 8 张表 (5 张业务表 + 3 张维度表) 并插入种子数据
-- ============================================================

DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS dim_promotion;
DROP TABLE IF EXISTS dim_region;
DROP TABLE IF EXISTS dim_date;

-- ============================================================
-- 业务表
-- ============================================================

CREATE TABLE users (
    user_id       INT             NOT NULL AUTO_INCREMENT,
    name          VARCHAR(50)     NOT NULL,
    email         VARCHAR(100)    NOT NULL,
    register_date DATE            NOT NULL,
    city          VARCHAR(50)     NOT NULL,
    province      VARCHAR(50)     NOT NULL,
    status        VARCHAR(20)     NOT NULL DEFAULT 'active',
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE products (
    product_id    INT             NOT NULL AUTO_INCREMENT,
    product_name  VARCHAR(200)    NOT NULL,
    category      VARCHAR(50)     NOT NULL,
    price         DECIMAL(10,2)   NOT NULL,
    stock         INT             NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE orders (
    order_id      INT             NOT NULL AUTO_INCREMENT,
    user_id       INT             NOT NULL,
    order_date    DATE            NOT NULL,
    status        VARCHAR(20)     NOT NULL DEFAULT 'pending',
    total_amount  DECIMAL(10,2)   NOT NULL DEFAULT 0.00,
    promo_id      INT             DEFAULT NULL,
    PRIMARY KEY (order_id),
    KEY idx_user_id (user_id),
    KEY idx_order_date (order_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE order_items (
    item_id       INT             NOT NULL AUTO_INCREMENT,
    order_id      INT             NOT NULL,
    product_id    INT             NOT NULL,
    qty           INT             NOT NULL DEFAULT 1,
    unit_price    DECIMAL(10,2)   NOT NULL,
    PRIMARY KEY (item_id),
    KEY idx_order_id (order_id),
    KEY idx_product_id (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE payments (
    payment_id    INT             NOT NULL AUTO_INCREMENT,
    order_id      INT             NOT NULL,
    method        VARCHAR(30)     NOT NULL,
    pay_date      DATE            NOT NULL,
    amount        DECIMAL(10,2)   NOT NULL,
    status        VARCHAR(20)     NOT NULL DEFAULT 'completed',
    PRIMARY KEY (payment_id),
    KEY idx_order_id (order_id),
    KEY idx_pay_date (pay_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 维度表
-- ============================================================

CREATE TABLE dim_date (
    date_key      DATE            NOT NULL,
    year          SMALLINT        NOT NULL,
    quarter       SMALLINT        NOT NULL,
    month         SMALLINT        NOT NULL,
    week          SMALLINT        NOT NULL,
    day_of_month  SMALLINT        NOT NULL,
    day_of_week   SMALLINT        NOT NULL,
    is_weekend    BOOLEAN         NOT NULL DEFAULT FALSE,
    season        VARCHAR(4)      NOT NULL,
    PRIMARY KEY (date_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE dim_region (
    region_id     INT             NOT NULL AUTO_INCREMENT,
    province      VARCHAR(50)     NOT NULL,
    city          VARCHAR(50)     NOT NULL,
    district      VARCHAR(50)     DEFAULT NULL,
    region_tier   VARCHAR(10)     NOT NULL DEFAULT 'T3',
    PRIMARY KEY (region_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE dim_promotion (
    promo_id      INT             NOT NULL AUTO_INCREMENT,
    promo_name    VARCHAR(100)    NOT NULL,
    promo_type    VARCHAR(30)     NOT NULL,
    start_date    DATE            NOT NULL,
    end_date      DATE            NOT NULL,
    discount_rate DECIMAL(3,2)    NOT NULL DEFAULT 0.00,
    PRIMARY KEY (promo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- 种子数据
-- ============================================================

INSERT INTO dim_region (province, city, district, region_tier) VALUES
    ('北京市',   '北京',   '朝阳区', '一线'),
    ('上海市',   '上海',   '浦东新区', '一线'),
    ('广东省',   '广州',   '天河区', '一线'),
    ('广东省',   '深圳',   '南山区', '一线'),
    ('四川省',   '成都',   '高新区', '新一线');

-- dim_promotion: 3 条促销数据
INSERT INTO dim_promotion (promo_name, promo_type, start_date, end_date, discount_rate) VALUES
    ('双11预热期', '预热', '2024-11-01', '2024-11-10', 0.10),
    ('双11正式期', '正式', '2024-11-11', '2024-11-11', 0.25),
    ('双11返场期', '返场', '2024-11-12', '2024-11-14', 0.15);
