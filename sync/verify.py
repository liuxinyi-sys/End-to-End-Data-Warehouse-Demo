"""Verify ADS metrics and compression ratio."""
import subprocess, sys

def _sql(cmd):
    r = subprocess.run(["docker-compose","exec","-T","ymatrix","/opt/ymatrix/matrixdb5/bin/psql",
        "-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-v","ON_ERROR_STOP=1","-t","-A","-c",cmd],
        capture_output=True,text=True,check=True)
    return r.stdout.strip()

def verify_ads():
    results = {}; print("\n--- Verifying ADS Metrics ---")
    c = int(_sql("SELECT COUNT(*) FROM ads_daily_gmv;"))
    r = c == 365; results["ads_daily_gmv: 365 days"] = r; print(f"  ads_daily_gmv: {c} rows -> {'PASS' if r else 'FAIL'}")
    n11 = _sql("SELECT gmv FROM ads_daily_gmv WHERE dt='2024-11-11'::TIMESTAMP;")
    avg = _sql("SELECT AVG(gmv)::INT FROM ads_daily_gmv;")
    if n11 and avg:
        r = int(n11) > int(avg)*2; results["Nov 11 peak > 2x avg"] = r; print(f"  Nov 11: {n11} vs avg: {avg} -> {'PASS' if r else 'FAIL'}")
    c = int(_sql("SELECT COUNT(*) FROM ads_top_products;"))
    r = c == 10; results["ads_top_products: 10 rows"] = r; print(f"  top_products: {c} rows -> {'PASS' if r else 'FAIL'}")
    p = float(_sql("SELECT COALESCE(SUM(pct),0) FROM ads_category_sales;"))
    r = abs(p-100) < 0.2; results["category pct = 100%"] = r; print(f"  category pct: {p:.2f}% -> {'PASS' if r else 'FAIL'}")
    rate = float(_sql("SELECT COALESCE(repurchase_rate,0) FROM ads_user_repurchase;"))
    r = rate >= 30; results["repurchase >= 30%"] = r; print(f"  repurchase: {rate:.2f}% -> {'PASS' if r else 'FAIL'}")
    c = int(_sql("SELECT COUNT(*) FROM ads_gmv_by_region;"))
    r = c == 5; results["gmv_by_region: 5 provinces"] = r; print(f"  gmv_by_region: {c} rows -> {'PASS' if r else 'FAIL'}")
    p_gmv = _sql("SELECT gmv::TEXT FROM ads_promo_compare ORDER BY gmv DESC LIMIT 1;")
    reg = _sql("SELECT gmv::TEXT FROM ads_promo_compare ORDER BY gmv ASC LIMIT 1;")
    if p_gmv and reg:
        r = float(p_gmv) > float(reg); results["promo > regular GMV"] = r; print(f"  promo: {p_gmv} vs regular: {reg} -> {'PASS' if r else 'FAIL'}")
    c = int(_sql("SELECT COUNT(*) FROM ads_user_segment;"))
    r = c == 3; results["user_segment: 3 segments"] = r; print(f"  user_segment: {c} segments -> {'PASS' if r else 'FAIL'}")
    m3 = _sql("SELECT pg_total_relation_size('ods_orders');")
    hp = _sql("SELECT pg_total_relation_size('ods_orders_heap');")
    if m3 and hp and int(hp) > 0:
        ratio = (1-int(m3)/int(hp))*100; r = ratio >= 50
        results["compression: MARS3 saves >= 50%"] = r; print(f"  compression: MARS3 saves {ratio:.1f}% -> {'PASS' if r else 'FAIL'}")
    lc = int(_sql("SELECT COUNT(*) FROM etl_log;"))
    r = lc >= 7; results["etl_log: >= 7 entries"] = r; print(f"  etl_log: {lc} entries -> {'PASS' if r else 'FAIL'}")
    print(f"\n{sum(1 for v in results.values() if v)}/{len(results)} passed")
    return results

if __name__ == "__main__":
    r = verify_ads()
    sys.exit(0 if all(r.values()) else 1)
