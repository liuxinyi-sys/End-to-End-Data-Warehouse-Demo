"""Transform and clean extracted data."""
import pandas as pd
from typing import Dict

def clean_users(df): df=df.dropna(subset=["user_id","name"]); df["status"]=df["status"].fillna("active"); return df
def clean_products(df): df=df.dropna(subset=["product_id","product_name"]); df["price"]=df["price"].fillna(0).round(2); df["stock"]=df["stock"].fillna(0).astype(int); return df
def clean_orders(df): df=df.dropna(subset=["order_id","user_id","order_date"]); df["total_amount"]=df["total_amount"].fillna(0).round(2); df["status"]=df["status"].fillna("unknown"); df["promo_id"]=df["promo_id"].fillna(0).astype(int); return df
def clean_order_items(df): df=df.dropna(subset=["item_id","order_id","product_id"]); df["qty"]=df["qty"].fillna(1).astype(int); df["unit_price"]=df["unit_price"].fillna(0).round(2); return df
def clean_payments(df): df=df.dropna(subset=["payment_id","order_id"]); df["amount"]=df["amount"].fillna(0).round(2); df["status"]=df["status"].fillna("completed"); return df

def clean_order_status_events(df):
    df=df.dropna(subset=["event_id","order_id","to_status","event_time"])
    df["from_status"]=df["from_status"].fillna("")
    df["operator_type"]=df["operator_type"].fillna("system")
    return df

def transform_all(data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    cleaners = {"users":clean_users,"products":clean_products,"orders":clean_orders,"order_items":clean_order_items,"payments":clean_payments,"order_status_events":clean_order_status_events}
    result = {}
    for name, df in data.items():
        result[name] = cleaners[name](df)
        dropped = len(df) - len(result[name])
        print(f"Transform {name}: {len(result[name])} rows (dropped {dropped})")
    return result

if __name__ == "__main__":
    from extract import extract_all
    d = transform_all(extract_all())
    for n, df in d.items(): print(f"{n}: {len(df)} rows")
