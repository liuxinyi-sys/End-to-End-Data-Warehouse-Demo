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
