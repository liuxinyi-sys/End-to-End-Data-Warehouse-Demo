"""Load DIM tables from ODS via TRUNCATE + mxgate."""
import subprocess, io, pandas as pd

def _psql(sql):
    subprocess.run(["psql","-h","localhost","-p","5432","-U","mxadmin","-d","dw_demo","-c",sql],
                   capture_output=True, text=True)

def load_dim_product(ods_products):
    _psql("TRUNCATE dim_product;")
    rows = ods_products[["product_id","product_name","category","price"]].drop_duplicates()
    buf = io.StringIO(); rows.to_csv(buf, index=False, header=False)
    subprocess.run(["mxgate","--source","stdin","--db-database","dw_demo",
        "--db-master-host","localhost","--db-master-port","5432","--db-user","mxadmin",
        "--target","dim_product","--parallel","64","--delimiter",","],
        input=buf.getvalue(), text=True)
    return len(rows)

def load_dim_user(ods_users):
    _psql("TRUNCATE dim_user;")
    rows = ods_users[["user_id","name","city","status","register_date"]].drop_duplicates()
    buf = io.StringIO(); rows.to_csv(buf, index=False, header=False)
    subprocess.run(["mxgate","--source","stdin","--db-database","dw_demo",
        "--db-master-host","localhost","--db-master-port","5432","--db-user","mxadmin",
        "--target","dim_user","--parallel","64","--delimiter",","],
        input=buf.getvalue(), text=True)
    return len(rows)

def load_all(dfs):
    result = {"dim_product": load_dim_product(dfs["products"]), "dim_user": load_dim_user(dfs["users"])}
    print(f"dim_product: {result['dim_product']} rows, dim_user: {result['dim_user']} rows")
    return result
