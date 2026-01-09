import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def check_account_master():
    conn = sqlite3.connect('assets.db')
    
    # 1. Check Account Master
    try:
        df_acct = pd.read_sql("SELECT * FROM account_master", conn)
        print("=== Account Master ===")
        print(df_acct.to_string())
        
        if df_acct.empty:
            print("WARNING: Account Master is Empty!")
    except Exception as e:
        print(f"Error reading account_master: {e}")
        
    conn.close()

if __name__ == "__main__":
    check_account_master()
