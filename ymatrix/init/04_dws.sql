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
