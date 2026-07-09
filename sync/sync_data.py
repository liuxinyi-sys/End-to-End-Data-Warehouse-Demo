#!/usr/bin/env python3
"""ETL orchestrator: extract -> transform -> load ODS -> load DIM -> load DWD -> refresh -> verify."""
import time, sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import extract_all
from transform import transform_all
from load_ods import load_all as load_ods
from load_dim import load_all as load_dim
from load_dwd import run_all as run_dwd
from verify import verify_ads

def log(step, status, rows=0, ms=0, msg=""):
    sql = f"INSERT INTO etl_log(step,status,rows_processed,duration_ms,message) VALUES('{step}','{status}',{rows},{ms},'{msg}');"
    subprocess.run(["docker-compose","exec","-T","ymatrix","/opt/ymatrix/matrixdb5/bin/psql",
        "-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-v","ON_ERROR_STOP=1","-c",sql],
        capture_output=True,text=True,check=True)

def main():
    t_start = time.time()
    print("="*50); print("YMatrix DW Demo - Full ETL Pipeline"); print("="*50)
    t0=time.time(); print("\n[1/6] Extract..."); raw=extract_all()
    t=int((time.time()-t0)*1000); log("extract","success",sum(len(v)for v in raw.values()),t)
    print(f"  {sum(len(v)for v in raw.values())} rows in {t}ms")
    t0=time.time(); print("\n[2/6] Transform..."); clean=transform_all(raw)
    t=int((time.time()-t0)*1000); log("transform","success",sum(len(v)for v in clean.values()),t)
    t0=time.time(); print("\n[3/6] Load ODS..."); oc=load_ods(clean)
    t=int((time.time()-t0)*1000); log("load_ods","success",sum(oc.values()),t)
    t0=time.time(); print("\n[4/6] Load DIM..."); dc=load_dim(clean)
    t=int((time.time()-t0)*1000); log("load_dim","success",sum(dc.values()),t)
    t0=time.time(); print("\n[5/6] DWD ETL + Refresh..."); dr=run_dwd()
    t=int((time.time()-t0)*1000)
    for r in dr: log(r["step"],r["status"],r["rows"],r["ms"])
    print("\n[6/6] Verify..."); vr=verify_ads()
    for n,r in vr.items(): print(f"  [{'PASS' if r else 'FAIL'}] {n}")
    tt=int((time.time()-t_start)*1000)
    print(f"\n{'='*50}\nETL Complete: {tt}ms\nGrafana: http://localhost:3000 (admin/admin)\n{'='*50}")
    log("etl_complete","success",0,tt)

if __name__=="__main__":
    main()
