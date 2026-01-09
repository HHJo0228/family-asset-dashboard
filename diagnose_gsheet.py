import pandas as pd
import sys
from modules import data_loader
import streamlit as st

sys.stdout.reconfigure(encoding='utf-8')

st.title("Debug GSheet Inventory")

# Auto-run
try:
    print("=== START GSHEET DIAGNOSIS ===")
    data = data_loader.load_data()
    if data:
        df_inv = data.get('inventory') # 자산종합
        if df_inv is not None:
             print("### Inventory Sheet Columns:", df_inv.columns.tolist())
             if '종목' in df_inv.columns:
                 # Check '원화' and '달러' specifically
                 cash_rows = df_inv[df_inv['종목'].isin(['원화', '달러'])]
                 print(cash_rows.to_string())
                 
                 # Also check for huge negative numbers or other weirdness
                 print("\nFull Data Shape:", df_inv.shape)
             else:
                 print("ERROR: '종목' column missing.")
                 print(df_inv.head().to_string())
        else:
            print("ERROR: Inventory DataFrame is None.")
    else:
        print("ERROR: data_loader returned None.")
        
    print("=== END GSHEET DIAGNOSIS ===")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
