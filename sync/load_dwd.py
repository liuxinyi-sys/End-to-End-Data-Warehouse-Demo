"""ETL ODS -> DWD via SQL INSERT..SELECT, then REFRESH MV."""
import subprocess, time

def _sql(cmd):
    r = subprocess.run(["docker-compose","exec","-T","ymatrix","/opt/ymatrix/matrixdb5/bin/psql",
        "-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-v","ON_ERROR_STOP=1","-t","-A","-c",cmd],
        capture_output=True, text=True, check=True)
    return r

def _count(table):
    r = _sql(f"SELECT COUNT(*) FROM {table};")
    return int(r.stdout.strip()) if r.stdout.strip() else 0

def run_all():
    results = []

    t0 = time.time()
    _sql("TRUNCATE dwd_order_fact CASCADE;")
    _sql("""
    INSERT INTO dwd_order_fact (order_id,user_id,order_date,order_time,region_id,promo_id,total_amount,freight_amount,discount_amount,pay_time,cancel_time,finish_time,source_type,status)
    SELECT
      o.order_id,
      o.user_id,
      DATE(o.order_date) AS order_date,
      o.order_date AS order_time,
      COALESCE(r.region_id,0),
      COALESCE(o.promo_id,0),
      o.total_amount,
      CASE WHEN o.total_amount >= 200 THEN 0 ELSE ROUND((RANDOM()*7+8)::NUMERIC,2) END,
      ROUND(COALESCE(d.discount_amount, 0), 2),
      p.pay_date AS pay_time,
      CASE WHEN o.status='cancelled' THEN e_cancel.event_time ELSE NULL END,
      CASE WHEN o.status='completed' THEN e_finish.event_time ELSE NULL END,
      CASE MOD(o.order_id,10) WHEN 0 THEN 'miniapp' WHEN 1 THEN 'miniapp' WHEN 2 THEN 'web' WHEN 3 THEN 'web' WHEN 4 THEN 'web' ELSE 'app' END,
      o.status
    FROM ods_orders o
    LEFT JOIN ods_users u ON o.user_id=u.user_id
    LEFT JOIN dim_region r ON u.city=r.city AND u.province=r.province
    LEFT JOIN ods_payments p ON o.order_id=p.order_id
    LEFT JOIN ods_order_status_events e_cancel ON o.order_id=e_cancel.order_id AND e_cancel.to_status='cancelled'
    LEFT JOIN ods_order_status_events e_finish ON o.order_id=e_finish.order_id AND e_finish.to_status='completed'
    LEFT JOIN (
      SELECT oi.order_id, SUM(ROUND(oi.qty * oi.unit_price * COALESCE(pm.discount_rate,0), 2)) AS discount_amount
      FROM ods_order_items oi
      JOIN ods_orders oo ON oi.order_id=oo.order_id
      LEFT JOIN dim_promotion pm ON oo.promo_id=pm.promo_id
      GROUP BY oi.order_id
    ) d ON o.order_id=d.order_id
    WHERE o.status IS NOT NULL;""")
    rows = _count("dwd_order_fact")
    results.append({"step":"dwd_order_fact","rows":rows,"ms":int((time.time()-t0)*1000),"status":"success"})
    print(f"dwd_order_fact: {rows} rows ({results[-1]['ms']}ms)")

    t0 = time.time()
    _sql("TRUNCATE dwd_order_detail_fact CASCADE;")
    _sql("""
    INSERT INTO dwd_order_detail_fact (detail_id,order_id,user_id,sku_id,order_date,order_time,region_id,promo_id,sku_num,original_price,final_price,line_amount,source_type)
    SELECT
      oi.item_id,
      oi.order_id,
      o.user_id,
      oi.product_id,
      DATE(o.order_date) AS order_date,
      o.order_date AS order_time,
      COALESCE(r.region_id,0),
      COALESCE(o.promo_id,0),
      oi.qty,
      oi.unit_price,
      ROUND(oi.unit_price * (1 - COALESCE(p.discount_rate,0)), 2),
      ROUND(oi.qty * oi.unit_price * (1 - COALESCE(p.discount_rate,0)), 2),
      CASE MOD(oi.order_id,10) WHEN 0 THEN 'miniapp' WHEN 1 THEN 'miniapp' WHEN 2 THEN 'web' WHEN 3 THEN 'web' WHEN 4 THEN 'web' ELSE 'app' END
    FROM ods_order_items oi
    JOIN ods_orders o ON oi.order_id=o.order_id
    LEFT JOIN ods_users u ON o.user_id=u.user_id
    LEFT JOIN dim_region r ON u.city=r.city AND u.province=r.province
    LEFT JOIN dim_promotion p ON o.promo_id=p.promo_id
    WHERE o.status IS NOT NULL;""")
    rows = _count("dwd_order_detail_fact")
    results.append({"step":"dwd_order_detail","rows":rows,"ms":int((time.time()-t0)*1000),"status":"success"})
    print(f"dwd_order_detail_fact: {rows} rows ({results[-1]['ms']}ms)")

    t0 = time.time()
    _sql("TRUNCATE dwd_order_status_event_fact CASCADE;")
    _sql("""
    INSERT INTO dwd_order_status_event_fact (event_id,order_id,user_id,from_status,to_status,event_time,event_date,operator_type)
    SELECT
      e.event_id,
      e.order_id,
      o.user_id,
      e.from_status,
      e.to_status,
      e.event_time AS event_time,
      DATE(e.event_time) AS event_date,
      e.operator_type
    FROM ods_order_status_events e
    JOIN ods_orders o ON e.order_id=o.order_id;""")
    rows = _count("dwd_order_status_event_fact")
    results.append({"step":"dwd_order_status_event_fact","rows":rows,"ms":int((time.time()-t0)*1000),"status":"success"})
    print(f"dwd_order_status_event_fact: {rows} rows ({results[-1]['ms']}ms)")

    t0 = time.time()
    for v in [
        "dws_daily_gmv",
        "dws_minute_order_traffic",
        "dws_product_daily_sales",
        "dws_user_purchase_stats",
        "dws_order_status_funnel",
        "dws_order_fulfillment_latency",
        "dws_promo_daily_compare",
    ]:
        _sql(f"REFRESH MATERIALIZED VIEW {v};")
    results.append({"step":"refresh_dws","rows":7,"ms":int((time.time()-t0)*1000),"status":"success"})
    print(f"DWS materialized views refreshed ({results[-1]['ms']}ms)")

    return results

if __name__ == "__main__":
    for r in run_all():
        print(f"  {r['step']}: {r['status']} ({r['rows']} rows, {r['ms']}ms)")
