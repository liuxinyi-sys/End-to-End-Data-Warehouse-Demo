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
WITH ranked AS (
  SELECT user_id,total_orders,total_spent,NTILE(3) OVER(ORDER BY total_spent)spend_tier
  FROM dws_user_purchase_stats
)
SELECT CASE spend_tier WHEN 1 THEN 'low' WHEN 2 THEN 'mid' ELSE 'high' END segment,
  COUNT(*)user_count,SUM(total_orders)total_orders FROM ranked GROUP BY 1 ORDER BY 1;
CREATE VIEW ads_gmv_by_region AS
SELECT r.province,COUNT(DISTINCT f.order_id)order_cnt,SUM(f.total_amount)gmv
  FROM dwd_order_fact f JOIN dim_region r ON f.region_id=r.region_id GROUP BY r.province ORDER BY gmv DESC;
CREATE VIEW ads_promo_compare AS
SELECT CASE WHEN o.promo_id > 0 THEN '大促期' ELSE '日常期' END period,
  COUNT(DISTINCT o.order_id)order_cnt,SUM(o.total_amount)gmv,
  SUM(o.total_amount)/COUNT(DISTINCT o.order_id)avg_order_value FROM dwd_order_fact o GROUP BY 1;
