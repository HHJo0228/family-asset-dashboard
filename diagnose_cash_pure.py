import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def diagnose_cash_pure():
    conn = sqlite3.connect('assets.db')
    
    # 1. Inspect View Schema and Content
    print("=== 1. View Schema & Content for Cash ===")
    try:
        df_view = pd.read_sql("SELECT * FROM view_asset_inventory WHERE asset_name IN ('원화', '달러')", conn)
        print("View Columns:", df_view.columns.tolist())
        print(df_view.to_string())
    except Exception as e:
        print(f"View Error: {e}")

    # 2. Inspect Asset Master
    print("\n=== 2. Asset Master ===")
    try:
        df_asset = pd.read_sql("SELECT * FROM asset_master WHERE asset_name IN ('원화', '달러')", conn)
        print(df_asset.to_string())
    except Exception as e:
        print("Master Error:", e)

    # 3. Simulate Merge
    if 'df_view' in locals() and not df_view.empty:
        print("\n=== 3. Merge Simulation ===")
        # Merge
        if 'df_asset' in locals() and not df_asset.empty:
            df_merged = df_view.merge(df_asset, on='asset_name', how='left')
        else:
            df_merged = df_view.copy()
            
        print("Merged Columns:", df_merged.columns.tolist())
        
        # Check Ticker Columns
        ticker_cols = [c for c in df_merged.columns if 'ticker' in c]
        print("Ticker Related Columns:", ticker_cols)
        print(df_merged[['asset_name'] + ticker_cols].to_string())
        
        # 4. Check Evaluation Amount Inputs
        # View uses 'net_book_value_amount' -> 매입금액
        # View uses 'current_qty' -> 수량
        # For Cash: Qty = Amount? 
        if 'current_qty' in df_merged.columns:
             print("\nQty / Amount:")
             print(df_merged[['asset_name', 'current_qty', 'net_book_value_amount']].to_string())

    conn.close()

if __name__ == "__main__":
    diagnose_cash_pure()
