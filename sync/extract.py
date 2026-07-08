"""Extract data from MySQL into pandas DataFrames."""
import pandas as pd
from sqlalchemy import create_engine
from typing import Dict

MYSQL_URI = "mysql+pymysql://root:root@localhost:3306/ecommerce?charset=utf8mb4"
TABLES = ["users", "products", "orders", "order_items", "payments"]

def extract_all() -> Dict[str, pd.DataFrame]:
    engine = create_engine(MYSQL_URI)
    result = {}
    for table in TABLES:
        print(f"Extracting {table}...")
        df = pd.read_sql(f"SELECT * FROM {table}", engine)
        result[table] = df
        print(f"  -> {len(df)} rows")
    engine.dispose()
    return result

if __name__ == "__main__":
    data = extract_all()
    for n, df in data.items():
        print(f"{n}: {len(df)} rows, {len(df.columns)} cols")
