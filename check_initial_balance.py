import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def check_initial_balance():
    conn = sqlite3.connect('assets.db')
    
    print("=== Checking for Initial Balance in Transaction Log ===")
    try:
        # Check based on 'note' column which data_loader sets to '기초자산'
        df = pd.read_sql("SELECT count(*) as count, owner, account_name, asset_name, amount FROM transaction_log WHERE note LIKE '%기초자산%' OR note LIKE '%Initial%' GROUP BY owner, account_name", conn)
        
        if df.empty:
            print("NO Initial Balance records found in transaction_log.")
        else:
            print(df.to_string())
            
        # Also check total count
        total = pd.read_sql("SELECT count(*) as total FROM transaction_log", conn).iloc[0]['total']
        print(f"\nTotal Transactions: {total}")
        
    except Exception as e:
        print(f"Error: {e}")
        
    conn.close()

if __name__ == "__main__":
    check_initial_balance()
