"""Load data into ODS layer via mxgate stdin."""
import subprocess, io, pandas as pd

def _count(target: str) -> int:
    result = subprocess.run([
        "docker-compose","exec","-T","ymatrix","/opt/ymatrix/matrixdb5/bin/psql",
        "-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-t","-A",
        "-c",f"SELECT COUNT(*) FROM {target};"
    ], capture_output=True, text=True, check=True)
    return int(result.stdout.strip())

def _gate(target: str, df: pd.DataFrame):
    before = _count(target)
    cmd = ["docker-compose","exec","-T","ymatrix","/opt/ymatrix/matrixdb5/bin/mxgate","--source","stdin","--db-database","dw_demo",
           "--db-master-host","localhost","--db-master-port","5432",
           "--db-user","mxadmin","--target",target,"--parallel","16","--delimiter",",",
           "--time-format","raw"]
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    subprocess.run(cmd, input=buf.getvalue().encode("utf-8"), check=True)
    loaded = _count(target) - before
    if loaded != len(df):
        raise RuntimeError(f"mxgate loaded {loaded} of {len(df)} rows into {target}")

def load_ods_users(df):
    rows = df[["user_id","name","email","register_date","city","province","status"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_users", rows); return len(rows)

def load_ods_products(df):
    rows = df[["product_id","product_name","category","price","stock"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_products", rows); return len(rows)

def load_ods_orders(df):
    rows = df[["order_id","user_id","order_date","status","total_amount","promo_id"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_orders", rows)
    _gate("ods_orders_heap", rows)
    return len(rows)

def load_ods_order_items(df):
    rows = df[["item_id","order_id","product_id","qty","unit_price"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_order_items", rows); return len(rows)

def load_ods_payments(df):
    rows = df[["payment_id","order_id","method","pay_date","amount","status"]].copy()
    rows["sync_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    _gate("ods_payments", rows); return len(rows)

def load_all(dfs):
    loaders = {"users":load_ods_users,"products":load_ods_products,"orders":load_ods_orders,"order_items":load_ods_order_items,"payments":load_ods_payments}
    result = {}
    for name, loader in loaders.items():
        print(f"Loading {name} -> ods_{name} via mxgate...")
        result[name] = loader(dfs[name])
        print(f"  -> {result[name]} rows")
    return result
