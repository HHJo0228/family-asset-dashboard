import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def check_db_data():
    conn = sqlite3.connect('assets.db')
    
    print("=== 1. Inventory Snapshot (Baseline) ===")
    try:
        df_snap = pd.read_sql("SELECT count(*) as count, asset_name, qty, amount FROM inventory_snapshot GROUP BY asset_name LIMIT 10", conn)
        print(df_snap.to_string())
        
        count = pd.read_sql("SELECT count(*) as total_rows FROM inventory_snapshot", conn).iloc[0]['total_rows']
        print(f"\nTotal Snapshot Rows: {count}")
    except Exception as e:
        print(f"Error reading inventory_snapshot: {e}")
        
    print("\n=== 2. View Asset Inventory (Calculated) ===")
    try:
        df_view = pd.read_sql("SELECT count(*) as count, asset_name, SUM(current_qty) as qty, SUM(net_book_value_amount) as amount FROM view_asset_inventory GROUP BY asset_name LIMIT 10", conn)
        print(df_view.to_string())
        
        count_view = pd.read_sql("SELECT count(*) as total_rows FROM view_asset_inventory", conn).iloc[0]['total_rows']
        print(f"\nTotal View Rows: {count_view}")
    except Exception as e:
        print(f"Error reading view_asset_inventory: {e}")
        
    conn.close()

if __name__ == "__main__":
    check_db_data()
