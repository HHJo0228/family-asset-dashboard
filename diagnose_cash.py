import sqlite3
import pandas as pd
import sys
from modules import price_fetcher 

sys.stdout.reconfigure(encoding='utf-8')

def diagnose_cash_visibility():
    conn = sqlite3.connect('assets.db')
    
    print("=== 1. Checking View for Cash Assets ===")
    df_view = pd.read_sql("SELECT * FROM view_asset_inventory WHERE asset_name IN ('원화', '달러')", conn)
    print(df_view.to_string())
    
    print("\n=== 2. Checking Asset Master for Cash ===")
    df_asset = pd.read_sql("SELECT * FROM asset_master WHERE asset_name IN ('원화', '달러')", conn)
    print(df_asset.to_string())
    
    print("\n=== 3. Simulation: DB Loader Logic ===")
    if not df_view.empty:
        # Merge Asset Master
        df_merged = df_view.merge(df_asset, on='asset_name', how='left')
        
        # Rename like db_loader
        # Conflict: view has ticker (might be null), master has ticker (might be '-')
        # merge gives ticker_x, ticker_y
        
        # In db_loader:
        # df_inv.rename(columns={'ticker': '티커'})
        # View has 'ticker'. Merge doesn't overwrite unless suffixes.
        # If 'ticker' in both, we get ticker_x, ticker_y.
        # Check columns after merge
        print("Columns after merge:", df_merged.columns.tolist())
        
        if 'ticker_y' in df_merged.columns:
            # db_loader DOES NOT handle ticker_x/y explicitly in the snippet I saw?
            # Actually, let's verify if db_loader drops duplicates or handles suffixes.
            # Step 6797: df_inv = df_inv.merge(df_asset_raw, on='asset_name', how='left')
            # If 'ticker' exists in both, pandas adds suffixes.
            # Then 'df_inv.rename' renames 'ticker' -> '티커'.
            # If 'ticker' became 'ticker_x', then 'ticker' column IS MISSING for rename!
            pass
        
        # Rename map
        # If suffixes happened
        rename_map = {
            'asset_name': '종목',
            'current_qty': '수량',
            'net_book_value_amount': '매입금액',
            'currency': '통화'
        }
        # Be careful about ticker
        if 'ticker' in df_merged.columns:
            rename_map['ticker'] = '티커'
        elif 'ticker_x' in df_merged.columns:
             rename_map['ticker_x'] = '티커'
        
        df_merged.rename(columns=rename_map, inplace=True)
        
        # Simulate Price Fetcher
        print("\n[Simulation] Columns:", df_merged.columns.tolist())
        if '티커' in df_merged.columns:
            print("Ticker col exists. Values:\n", df_merged['티커'])
            
            try:
                df_enriched = price_fetcher.enrich_inventory_with_prices(df_merged, ticker_col='티커', qty_col='수량', invested_col='매입금액')
                print("\n[Enriched Result]")
                print(df_enriched[['종목', '현재가_Native', '평가금액', '화폐']].to_string())
            except Exception as e:
                print(f"Enrich Error: {e}")
        else:
            print("CRITICAL: '티커' column missing after rename (likely due to merge suffix)!")

    conn.close()

if __name__ == "__main__":
    diagnose_cash_visibility()
