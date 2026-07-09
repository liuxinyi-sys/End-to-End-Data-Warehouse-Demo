"""Verify ADS metrics and compression ratio."""
import subprocess, sys

def _sql(cmd):
    r = subprocess.run(["docker-compose","exec","-T","ymatrix","/opt/ymatrix/matrixdb5/bin/psql",
        "-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-v","ON_ERROR_STOP=1","-t","-A","-c",cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True)
    return r.stdout.strip()

def _int(cmd):
    value = _sql(cmd)
    return int(value) if value else 0


def _float(cmd):
    value = _sql(cmd)
    return float(value) if value else 0.0


def _pass(results, name, ok, detail):
    results[name] = bool(ok)
    print("  {} {} -> {}".format(name, detail, "PASS" if ok else "FAIL"))

def verify_ads():
    results = {}; print("\n--- Verifying ADS Metrics ---")
    c = int(_sql("SELECT COUNT(*) FROM ads_daily_gmv;"))
    r = c == 365; results["ads_daily_gmv: 365 days"] = r; print(f"  ads_daily_gmv: {c} rows -> {'PASS' if r else 'FAIL'}")
    n11 = _sql("SELECT gmv FROM ads_daily_gmv WHERE dt='2024-11-11'::TIMESTAMP;")
    avg = _sql("SELECT AVG(gmv)::INT FROM ads_daily_gmv;")
    if n11 and avg:
        r = float(n11) > float(avg)*2; results["Nov 11 peak > 2x avg"] = r; print(f"  Nov 11: {n11} vs avg: {avg} -> {'PASS' if r else 'FAIL'}")
    c = int(_sql("SELECT COUNT(*) FROM ads_top_products;"))
    r = c == 10; results["ads_top_products: 10 rows"] = r; print(f"  top_products: {c} rows -> {'PASS' if r else 'FAIL'}")
    p = float(_sql("SELECT COALESCE(SUM(pct),0) FROM ads_category_sales;"))
    r = abs(p-100) < 0.2; results["category pct = 100%"] = r; print(f"  category pct: {p:.2f}% -> {'PASS' if r else 'FAIL'}")
    rate = float(_sql("SELECT COALESCE(repurchase_rate,0) FROM ads_user_repurchase;"))
    r = rate >= 30; results["repurchase >= 30%"] = r; print(f"  repurchase: {rate:.2f}% -> {'PASS' if r else 'FAIL'}")
    c = int(_sql("SELECT COUNT(*) FROM ads_gmv_by_region;"))
    r = c == 4; results["gmv_by_region: 4 provinces"] = r; print(f"  gmv_by_region: {c} rows -> {'PASS' if r else 'FAIL'}")
    promo_periods = int(_sql("SELECT COUNT(*) FROM ads_promo_compare WHERE gmv > 0;"))
    r = promo_periods == 2; results["promo_compare: 2 non-empty periods"] = r; print(f"  promo_compare: {promo_periods} non-empty periods -> {'PASS' if r else 'FAIL'}")
    c = int(_sql("SELECT COUNT(*) FROM ads_user_segment;"))
    r = c == 3; results["user_segment: 3 segments"] = r; print(f"  user_segment: {c} segments -> {'PASS' if r else 'FAIL'}")
    m3 = _sql("SELECT pg_total_relation_size('ods_orders_mars_compare');")
    hp = _sql("SELECT pg_total_relation_size('ods_orders_heap');")
    if m3 and hp and int(hp) > 0:
        ratio = (1-int(m3)/int(hp))*100; r = ratio >= 50
        results["compression: MARS3 saves >= 50%"] = r; print(f"  compression: MARS3 saves {ratio:.1f}% -> {'PASS' if r else 'FAIL'}")
    lc = int(_sql("SELECT COUNT(*) FROM etl_log;"))
    r = lc >= 7; results["etl_log: >= 7 entries"] = r; print(f"  etl_log: {lc} entries -> {'PASS' if r else 'FAIL'}")
    orders = _int("SELECT COUNT(*) FROM ods_orders;")
    _pass(results, "ods_orders >= 200000", orders >= 200000, "{} rows".format(orders))

    status_events = _int("SELECT COUNT(*) FROM ods_order_status_events;")
    _pass(results, "status events present", status_events >= orders, "{} rows".format(status_events))

    fixed_four = _int("""
        SELECT COUNT(*) FROM (
          SELECT order_id, COUNT(*) AS item_count
          FROM ods_order_items
          GROUP BY order_id
          HAVING COUNT(*) <> 4
        ) s;
    """)
    _pass(results, "order item count varies", fixed_four > 0, "{} non-four-item orders".format(fixed_four))

    mismatched_products = _int("""
        SELECT COUNT(*)
        FROM dim_product
        WHERE product_name IS NULL OR category IS NULL OR price <= 0;
    """)
    _pass(results, "product dimension credible", mismatched_products == 0, "{} invalid products".format(mismatched_products))

    recon_errors = _int("""
        SELECT COUNT(*)
        FROM (
          SELECT f.order_id
          FROM dwd_order_fact f
          JOIN (
            SELECT order_id, ROUND(SUM(line_amount), 2) AS detail_amount
            FROM dwd_order_detail_fact
            GROUP BY order_id
          ) d ON f.order_id = d.order_id
          WHERE ABS(f.total_amount - d.detail_amount) > 0.05
        ) s;
    """)
    _pass(results, "order/detail amount reconciles", recon_errors == 0, "{} mismatches".format(recon_errors))

    minute_rows = _int("SELECT COUNT(*) FROM ads_minute_traffic;")
    _pass(results, "minute traffic non-empty", minute_rows > 0, "{} rows".format(minute_rows))

    running_rows = _int("SELECT COUNT(*) FROM ads_gmv_running_total;")
    _pass(results, "running GMV non-empty", running_rows > 0, "{} rows".format(running_rows))

    running_violations = _int("""
        SELECT COUNT(*)
        FROM (
          SELECT running_gmv, LAG(running_gmv) OVER (ORDER BY bucket_time) AS prev_gmv
          FROM ads_gmv_running_total
        ) s
        WHERE prev_gmv IS NOT NULL AND running_gmv < prev_gmv;
    """)
    _pass(results, "running GMV monotonic", running_violations == 0, "{} violations".format(running_violations))

    timezone_shift = _int("""
        SELECT COUNT(*)
        FROM dwd_order_fact
        WHERE order_date <> DATE(order_time);
    """)
    _pass(results, "DWD timezone date aligned", timezone_shift == 0, "{} shifted rows".format(timezone_shift))
    print(f"\n{sum(1 for v in results.values() if v)}/{len(results)} passed")
    return results

if __name__ == "__main__":
    r = verify_ads()
    sys.exit(0 if all(r.values()) else 1)
