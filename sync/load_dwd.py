"""ETL ODS -> DWD via SQL INSERT..SELECT, then REFRESH MV."""
import subprocess, time

def _sql(cmd):
    r = subprocess.run(["psql","-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-t","-A","-c",cmd],
                       capture_output=True, text=True)
    return r

def _count(table):
    r = _sql(f"SELECT COUNT(*) FROM {table};")
    return int(r.stdout.strip()) if r.stdout.strip() else 0

def run_all():
    results = []

    t0 = time.time()
    _sql("TRUNCATE dwd_order_fact CASCADE;")
    r = _sql("""
    INSERT INTO dwd_order_fact (order_id,user_id,order_date,region_id,promo_id,total_amount,freight_amount,discount_amount,create_time,pay_time,cancel_time,finish_time,source_type,status)
    SELECT o.order_id,o.user_id,o.order_date,COALESCE(r.region_id,0),COALESCE(o.promo_id,0),o.total_amount,
      CASE WHEN o.total_amount>=200 THEN 0 ELSE ROUND((RANDOM()*7+8)::NUMERIC,2) END,
      CASE WHEN o.promo_id IS NOT NULL THEN ROUND((RANDOM()*25+5)::NUMERIC,2) ELSE 0 END,
      o.order_date::TIMESTAMP,
      CASE WHEN o.status IN ('paid','shipped','completed') THEN o.order_date::TIMESTAMP ELSE NULL END,
      CASE WHEN o.status='cancelled' THEN o.order_date::TIMESTAMP ELSE NULL END,
      CASE WHEN o.status='completed' THEN o.order_date::TIMESTAMP+INTERVAL'2 days' ELSE NULL END,
      CASE MOD(o.order_id,10) WHEN 0 THEN 'miniapp' WHEN 1 THEN 'miniapp' WHEN 2 THEN 'web' WHEN 3 THEN 'web' WHEN 4 THEN 'web' ELSE 'app' END,
      o.status
    FROM ods_orders o LEFT JOIN ods_users u ON o.user_id=u.user_id LEFT JOIN dim_region r ON u.city=r.city AND u.province=r.province
    WHERE o.status IS NOT NULL;""")
    rows = _count("dwd_order_fact")
    results.append({"step":"dwd_order_fact","rows":rows,"ms":int((time.time()-t0)*1000),"status":"success" if r.returncode==0 else "failed"})
    print(f"dwd_order_fact: {rows} rows ({results[-1]['ms']}ms)")

    t0 = time.time()
    _sql("TRUNCATE dwd_order_detail_fact CASCADE;")
    r = _sql("""
    INSERT INTO dwd_order_detail_fact (detail_id,order_id,user_id,sku_id,order_date,region_id,promo_id,sku_num,original_price,final_price,source_type)
    SELECT oi.item_id,oi.order_id,o.user_id,oi.product_id,o.order_date,0,COALESCE(o.promo_id,0),
      oi.qty,oi.unit_price,oi.unit_price*(1-COALESCE(p.discount_rate,0)),
      CASE MOD(oi.order_id,10) WHEN 0 THEN 'miniapp' WHEN 1 THEN 'miniapp' WHEN 2 THEN 'web' WHEN 3 THEN 'web' WHEN 4 THEN 'web' ELSE 'app' END
    FROM ods_order_items oi JOIN ods_orders o ON oi.order_id=o.order_id
    LEFT JOIN dim_promotion p ON o.promo_id=p.promo_id AND o.order_date BETWEEN p.start_date AND p.end_date
    WHERE o.status IS NOT NULL;""")
    rows = _count("dwd_order_detail_fact")
    results.append({"step":"dwd_order_detail","rows":rows,"ms":int((time.time()-t0)*1000),"status":"success" if r.returncode==0 else "failed"})
    print(f"dwd_order_detail_fact: {rows} rows ({results[-1]['ms']}ms)")

    t0 = time.time()
    for v in ["dws_daily_gmv","dws_product_daily_sales","dws_user_purchase_stats"]:
        _sql(f"REFRESH MATERIALIZED VIEW {v};")
    results.append({"step":"refresh_dws","rows":3,"ms":int((time.time()-t0)*1000),"status":"success"})
    print(f"DWS materialized views refreshed ({results[-1]['ms']}ms)")

    return results

if __name__ == "__main__":
    for r in run_all():
        print(f"  {r['step']}: {r['status']} ({r['rows']} rows, {r['ms']}ms)")
