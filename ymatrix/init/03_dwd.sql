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
