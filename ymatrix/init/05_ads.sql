CREATE VIEW ads_daily_gmv AS SELECT dt, order_count, gmv, avg_order_amount FROM dws_daily_gmv ORDER BY dt;
CREATE VIEW ads_top_products AS
SELECT p.product_name,p.category,d.total_qty,d.total_revenue FROM
  (SELECT sku_id,SUM(total_qty)total_qty,SUM(total_revenue)total_revenue FROM dws_product_daily_sales GROUP BY sku_id ORDER BY total_revenue DESC LIMIT 10)d
  JOIN dim_product p ON d.sku_id=p.product_id;
CREATE VIEW ads_category_sales AS
SELECT p.category,SUM(d.total_revenue)revenue, SUM(d.total_revenue)*100.0/SUM(SUM(d.total_revenue))OVER()pct
  FROM dws_product_daily_sales d JOIN dim_product p ON d.sku_id=p.product_id GROUP BY p.category ORDER BY revenue DESC;
CREATE VIEW ads_user_repurchase AS
SELECT COUNT(*)FILTER(WHERE total_orders>1)*100.0/COUNT(*)repurchase_rate,
  COUNT(*)FILTER(WHERE total_orders>1)repeat_buyers,COUNT(*)total_buyers FROM dws_user_purchase_stats;
CREATE VIEW ads_user_segment AS
SELECT
  CASE
    WHEN total_spent >= 300000 THEN 'high'
    WHEN total_spent >= 10000 THEN 'mid'
    ELSE 'low'
  END segment,
  COUNT(*)user_count,
  SUM(total_orders)total_orders
FROM dws_user_purchase_stats
GROUP BY 1
ORDER BY 1;
CREATE VIEW ads_gmv_by_region AS
SELECT r.province,COUNT(DISTINCT f.order_id)order_cnt,SUM(f.total_amount)gmv
  FROM dwd_order_fact f JOIN dim_region r ON f.region_id=r.region_id GROUP BY r.province ORDER BY gmv DESC;
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
