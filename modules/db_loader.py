
import streamlit as st
import pandas as pd
from modules import db_manager, models

@st.cache_data
def load_all_data_from_db():
    """
    Loads all necessary data from SQLite Database.
    Replaces the Google Sheet 'load_data' function.
    Returns a dictionary of DataFrames with columns mapped to legacy GSheet format to ensure UI compatibility.
    """
    try:
        conn = db_manager.get_connection()
        
        # 1. History (Pivot Long -> Wide for UI compatibility)
        # Old table: history_snapshot (key, value)
        # New table: portfolio_history (portfolio_name, eval_value, index_val)
        
        df_p_history = pd.read_sql("SELECT date, portfolio_name, eval_value, index_val FROM portfolio_history", conn)
        df_history = pd.DataFrame()
        
        if not df_p_history.empty:
            # Clean up names to avoid matching issues
            df_p_history['portfolio_name'] = df_p_history['portfolio_name'].astype(str).str.strip()
            
            # 1a. Pivot Eval Value (e.g., '쇼호 α')
            df_eval = df_p_history.pivot(index='date', columns='portfolio_name', values='eval_value').reset_index()
            
            # 1b. Pivot Index Value (e.g., '쇼호 α_idx')
            df_index = df_p_history.pivot(index='date', columns='portfolio_name', values='index_val').reset_index()
            # Append _idx to column names except 'date'
            idx_rename = {col: f"{col}_idx" for col in df_index.columns if col != 'date'}
            df_index.rename(columns=idx_rename, inplace=True)
            
            # 1c. Merge back
            df_history = df_eval.merge(df_index, on='date', how='outer')
            df_history.rename(columns={'date': '날짜'}, inplace=True)
            df_history['날짜'] = pd.to_datetime(df_history['날짜'])
            df_history.sort_values('날짜', inplace=True)
        else:
            # Fallback to legacy snapshot if exists
            try:
                df_hist_long = pd.read_sql("SELECT date, `key`, value FROM history_snapshot", conn)
                if not df_hist_long.empty:
                    df_history = df_hist_long.pivot(index='date', columns='key', values='value').reset_index()
                    df_history.rename(columns={'date': '날짜'}, inplace=True)
                    df_history['날짜'] = pd.to_datetime(df_history['날짜'])
                    df_history.sort_values('날짜', inplace=True)
            except:
                pass
        
        # 2. Inventory (Load from View to reflect Hybrid Logic: Snapshot + Transactions)
        df_inv = pd.read_sql("SELECT * FROM view_asset_inventory", conn)
        
        # Enrich with Account Info (Portfolio Type)
        df_acct_raw = pd.read_sql("SELECT account_name, owner, type FROM account_master", conn)
        
        if not df_inv.empty and not df_acct_raw.empty:
            df_inv = df_inv.merge(df_acct_raw, on=['account_name', 'owner'], how='left')
            
        # Enrich with Asset Master (Currency, Asset Class) as View doesn't output them explicitly
        df_asset_raw = pd.read_sql("SELECT asset_name, currency, asset_class FROM asset_master", conn)
        if not df_inv.empty and not df_asset_raw.empty:
            df_inv = df_inv.merge(df_asset_raw, on='asset_name', how='left')

        # Map columns back to Korean for UI compatibility
        # View Columns: owner, account_name, asset_name, ticker, current_qty, net_book_value_amount, total_dividends...
        df_inv.rename(columns={
            'owner': '소유자',
            'account_name': '계좌',
            'asset_name': '종목',
            'ticker': '티커',
            'current_qty': '수량',         # View Output
            'net_book_value_amount': '매입금액',   # View Output (Invested/Book Value)
            'total_dividends': '배당수익',
            'total_realized_gains': '확정손익',
            'currency': '통화',            # From Asset Master Merge
            'asset_class': '자산구분',      # From Asset Master Merge
            'type': '포트폴리오 구분'       # From Account Master Merge
        }, inplace=True)
        
        # Safety Check: Ensure '포트폴리오 구분' exists
        if '포트폴리오 구분' not in df_inv.columns:
            if 'type' in df_inv.columns:
                df_inv.rename(columns={'type': '포트폴리오 구분'}, inplace=True)
            else:
                df_inv['포트폴리오 구분'] = 'General'
        
        # Safely fill '포트폴리오 구분' NaNs
        df_inv['포트폴리오 구분'] = df_inv['포트폴리오 구분'].fillna('Unknown')

        # Calculate '평단가' explicitly if missing or zero (Invested / Qty)
        # Needed for UI tooltips
        if '평단가' not in df_inv.columns:
            df_inv['평단가'] = 0.0
            
        # Ensure numeric types
        for col in ['수량', '매입금액']:
             df_inv[col] = pd.to_numeric(df_inv[col], errors='coerce').fillna(0)
             
        mask_qty_nz = df_inv['수량'] != 0
        df_inv.loc[mask_qty_nz, '평단가'] = df_inv.loc[mask_qty_nz, '매입금액'] / df_inv.loc[mask_qty_nz, '수량']
        
        # Fetch real-time prices and calculate evaluation amounts
        from modules import price_fetcher
        df_inv = price_fetcher.enrich_inventory_with_prices(
            df_inv, 
            ticker_col='티커', 
            qty_col='수량', 
            invested_col='매입금액'
        )
        # This adds: 현재가, 평가금액, 총평가손익, plus ..._Native variants
        
        # Safety Check: Ensure ALL calculated columns exist (even if empty) to prevent UI crash
        # List must match app.py aggregation requirements
        required_calc_cols = [
            '평가금액', '현재가', '총평가손익', '매입금액',
            '매입금액_Native', '평가금액_Native', '총평가손익_Native', '현재가_Native'
        ]
        
        if df_inv.empty:
            # Create empty DF with columns if totally empty
            for col in required_calc_cols:
                 if col not in df_inv.columns:
                     df_inv[col] = pd.Series(dtype='float64')
        else:
             # Fill missing columns with 0.0
             for col in required_calc_cols:
                if col not in df_inv.columns:
                    df_inv[col] = 0.0
        
        # 3. Transactions
        # Join with Master tables if needed, but Log table usually has denormalized names.
        # Check models.py: Transaction has owner, account_name, etc. stored directly.
        df_txn = pd.read_sql("SELECT * FROM transaction_log ORDER BY date DESC", conn)
        df_txn.rename(columns={
            'date': '날짜',
            'owner': '소유자',
            'account_name': '계좌',
            'asset_name': '종목',
            'type': '거래구분',
            'amount': '거래금액', # In DB logic, amount might be total value? GSheet '거래금액' is usually total.
            'qty': '수량',
            'price': '평단가', # DB default 0
            'currency': '통화',
            'note': '비고'
        }, inplace=True)
        if not df_txn.empty:
            df_txn['날짜'] = pd.to_datetime(df_txn['날짜'])
            
        # 4. Masters
        df_acct = pd.read_sql("SELECT * FROM account_master", conn)
        df_acct.rename(columns={'account_number': '계좌번호', 'owner': '소유자', 'account_name': '계좌명', 'broker': '증권사', 'type': '계좌구분'}, inplace=True)
        
        df_asset = pd.read_sql("SELECT * FROM asset_master", conn)
        df_asset.rename(columns={'asset_name': '종목명', 'ticker': '티커', 'currency': '통화', 'asset_class': '자산구분'}, inplace=True)
        
        # 5. Placeholders (Legacy)
        df_cagr = pd.DataFrame() # Not synced to DB yet
        df_beta = pd.DataFrame() # Not synced to DB yet
        df_temp = pd.DataFrame()

        return {
            "history": df_history,
            "cagr": df_cagr,
            "inventory": df_inv,
            "beta_plan": df_beta,
            "transactions": df_txn,
            "account_master": df_acct,
            "asset_master": df_asset,
            "temp_history": df_temp
        }

    except Exception as e:
        st.error(f"DB Load Error: {e}")
        return None
