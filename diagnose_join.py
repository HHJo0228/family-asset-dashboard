import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def check_join():
    conn = sqlite3.connect('assets.db')
    
    print("=== Account Master ===")
    df_acct = pd.read_sql("SELECT owner, account_name, type FROM account_master", conn)
    print(df_acct.to_string())
    
    print("\n=== View Asset Inventory (Distinct Owners/Accounts) ===")
    df_view = pd.read_sql("SELECT DISTINCT owner, account_name FROM view_asset_inventory", conn)
    print(df_view.to_string())
    
    print("\n=== Check Merge ===")
    merged = df_view.merge(df_acct, on=['owner', 'account_name'], how='left')
    print(merged.to_string())
    
    conn.close()

if __name__ == "__main__":
    check_join()
