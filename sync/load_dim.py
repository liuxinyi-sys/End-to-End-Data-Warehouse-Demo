"""Load DIM tables from ODS via TRUNCATE + mxgate."""
import subprocess, io, pandas as pd

def _psql(sql):
    return subprocess.run(["docker-compose","exec","-T","ymatrix","/opt/ymatrix/matrixdb5/bin/psql",
        "-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-v","ON_ERROR_STOP=1","-t","-A","-c",sql],
        capture_output=True, text=True, check=True)

def _count(target):
    result = _psql(f"SELECT COUNT(*) FROM {target};")
    return int(result.stdout.strip())

def _gate(target, rows):
    before = _count(target)
    buf = io.StringIO()
    rows.to_csv(buf, index=False, header=False)
    subprocess.run(["docker-compose","exec","-T","ymatrix","/opt/ymatrix/matrixdb5/bin/mxgate","--source","stdin","--db-database","dw_demo",
        "--db-master-host","localhost","--db-master-port","5432","--db-user","mxadmin",
        "--target",target,"--parallel","16","--delimiter",",","--time-format","raw"],
        input=buf.getvalue().encode("utf-8"), check=True)
    loaded = _count(target) - before
    if loaded != len(rows):
        raise RuntimeError(f"mxgate loaded {loaded} of {len(rows)} rows into {target}")

def load_dim_product(ods_products):
    _psql("TRUNCATE dim_product;")
    rows = ods_products[["product_id","product_name","category","price"]].drop_duplicates()
    _gate("dim_product", rows)
    return len(rows)

def load_dim_user(ods_users):
    _psql("TRUNCATE dim_user;")
    rows = ods_users[["user_id","name","city","status","register_date"]].drop_duplicates()
    _gate("dim_user", rows)
    return len(rows)

def load_all(dfs):
    result = {"dim_product": load_dim_product(dfs["products"]), "dim_user": load_dim_user(dfs["users"])}
    print(f"dim_product: {result['dim_product']} rows, dim_user: {result['dim_user']} rows")
    return result
