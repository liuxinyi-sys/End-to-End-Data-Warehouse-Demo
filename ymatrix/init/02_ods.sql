CREATE TABLE ods_orders (
    order_id INT, user_id INT, order_date DATE, status VARCHAR(20),
    total_amount NUMERIC(10,2), promo_id INT, sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (order_id) ORDER BY (order_date, order_id)
PARTITION BY RANGE (order_date)
( START (DATE '2024-01-01') INCLUSIVE END (DATE '2025-01-01') EXCLUSIVE EVERY (INTERVAL '1 month') );

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
DISTRIBUTED BY (user_id) ORDER BY (user_id);

CREATE TABLE ods_products (
    product_id INT, product_name VARCHAR(200), category VARCHAR(50),
    price NUMERIC(10,2), stock INT, sync_time TIMESTAMP
) USING MARS3 WITH (compresstype='lz4', compresslevel=7)
DISTRIBUTED BY (product_id) ORDER BY (product_id);

CREATE TABLE ods_orders_heap (
    order_id INT, user_id INT, order_date DATE, status VARCHAR(20),
    total_amount NUMERIC(10,2), promo_id INT, sync_time TIMESTAMP
) USING HEAP DISTRIBUTED BY (order_id);
