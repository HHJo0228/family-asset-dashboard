import pandas as pd
import sqlite3
import os
from modules.db_manager import get_connection
from modules.data_loader import load_data

def bootstrap_history():
    print("Starting history bootstrap from Google Sheets...")
    data = load_data()
    if not data or 'history' not in data:
        print("Error: Could not load history from GSheet.")
        return
    
    df = data['history']
    if df.empty:
        print("Error: History sheet is empty.")
        return

    # User's Sheet Structure (Verified Indices):
    # 2-6: Eval
    # 7-11: Principal
    # 12-16: Ref Price
    # 17-21: Index
    
    portfolio_names = ['쇼호 α', '쇼호 β', '조연재', '조이재', '박행자']
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Clear existing history to avoid duplicates during bootstrap
    cur.execute("DELETE FROM portfolio_history")
    
    count = 0
    for idx, row in df.iterrows():
        try:
            date_val = str(row['날짜']).split(' ')[0] # YYYY-MM-DD
            if not date_val or date_val == 'NaT': continue
            
            for i, p_name in enumerate(portfolio_names):
                eval_val = row.iloc[2 + i]
                principal = row.iloc[7 + i]
                ref_price = row.iloc[12 + i]
                index_val = row.iloc[17 + i]
                
                # Check for NaNs/0 to avoid garbage data
                if pd.isna(eval_val) or eval_val == 0: continue
                
                cur.execute("""
                    INSERT OR REPLACE INTO portfolio_history 
                    (date, portfolio_name, eval_value, invested_principal, ref_price, index_val, is_final)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (date_val, p_name, float(eval_val), float(principal), float(ref_price), float(index_val)))
                count += 1
        except Exception as e:
            print(f"Row {idx} error: {e}")
            continue

    conn.commit()
    conn.close()
    print(f"Bootstrap complete. Inserted {count} historic points.")

if __name__ == "__main__":
    bootstrap_history()
