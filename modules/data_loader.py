import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

import concurrent.futures

from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx

import time
import random
from functools import wraps

# Rate Limit Retry Decorator
def retry_with_backoff(retries=3, backoff_in_seconds=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        if x == retries:
                            raise e
                        sleep = (backoff_in_seconds * 2 ** x + 
                                 random.uniform(0, 1))
                        time.sleep(sleep)
                        x += 1
                    else:
                        raise e
        return wrapper
    return decorator

@st.cache_data(ttl=600)
def load_data():
    """
    Fetches data from multiple worksheets in the '★온가족 자산 정리' Google Sheet in parallel.
    Returns a dictionary of DataFrames.
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Capture the current script context
        ctx = get_script_run_ctx()

        @retry_with_backoff(retries=3)
        def _fetch(worksheet, ttl, header=0):
            # Attach the context to this thread
            if ctx:
                add_script_run_ctx(threading.current_thread(), ctx)
            return conn.read(worksheet=worksheet, ttl=ttl, header=header)

        # Use ThreadPoolExecutor
        import threading 
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor: # Limit workers to reduce burst
            # Submit all tasks
            f_history = executor.submit(_fetch, "자산기록", "10m", 1)
            f_cagr = executor.submit(_fetch, "수익률", "10m", 0)
            f_inventory = executor.submit(_fetch, "자산종합", "10m", 0)
            f_beta = executor.submit(_fetch, "베타포트폴리오", "10m", 0)
            f_txn = executor.submit(_fetch, "00_거래일지", "10m", 0)
            f_master = executor.submit(_fetch, "01_계좌마스터", "10m", 0)
            f_asset_master = executor.submit(_fetch, "02_종목마스터", "10m", 0)
            f_temp = executor.submit(_fetch, "자산기록_TEMP", "0", 0)

            # Wait for results & Process
            # 1. History
            df_history = _clean_history_data(f_history.result())

            # 2. CAGR
            df_cagr = f_cagr.result()

            # 3. Inventory
            df_inventory = _clean_numeric_cols(f_inventory.result(), ['Qty', 'Price', 'EvalValue', '수량', '평단가', '평가금액', '배당수익', '확정손익'])

            # 4. Beta Plan
            df_beta = _clean_numeric_cols(f_beta.result(), ['CurrentWeight', 'TargetWeight', '현재비중', '목표비중'])

            # 5. Transaction Log
            df_txn = _clean_numeric_cols(f_txn.result(), ['Amount', 'Qty', '수량', '금액'])

            # 6. Masters
            df_master = f_master.result()
            try:
                df_asset_master = f_asset_master.result()
            except Exception:
                # If sheet doesn't exist or error, return empty to avoid crash
                df_asset_master = pd.DataFrame()

            # 7. Temp History
            try:
                df_temp_history = f_temp.result()
                df_temp_history = _clean_numeric_cols(df_temp_history, ['투자원금', '평가금액'])
            except Exception:
                df_temp_history = pd.DataFrame()

        return {
            "history": df_history,
            "cagr": df_cagr,
            "inventory": df_inventory,
            "beta_plan": df_beta,
            "transactions": df_txn,
            "account_master": df_master,
            "asset_master": df_asset_master,
            "temp_history": df_temp_history
        }

    except Exception as e:
        st.error(f"Error loading data: {e}. Check sheet names and permissions.")
        return None

@retry_with_backoff(retries=3)
def _read_sheet(conn, worksheet, ttl=0):
    return conn.read(worksheet=worksheet, ttl=ttl)

@retry_with_backoff(retries=3)
def _update_sheet(conn, worksheet, data):
    return conn.update(worksheet=worksheet, data=data)

def get_transaction_options():
    """
    Reads '00_거래일지' to get unique values for dropdowns.
    Returns a dict with lists for 'owners', 'accounts', 'tickers', 'types', 'currencies'.
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = _read_sheet(conn, worksheet="00_거래일지", ttl="0") # Cached by decorator logic if needed, but here mostly for retry
        
        if df is None or df.empty:
            return {}

        return {
            "owners": sorted(df['소유자'].dropna().unique().tolist()) if '소유자' in df.columns else [],
            "accounts": sorted(df['계좌'].dropna().unique().tolist()) if '계좌' in df.columns else [],
            "tickers": sorted(df['종목'].dropna().unique().tolist()) if '종목' in df.columns else [],
            "types": sorted(df['거래구분'].dropna().unique().tolist()) if '거래구분' in df.columns else [],
            "currencies": sorted(df['통화'].dropna().unique().tolist()) if '통화' in df.columns else [],
        }
    except Exception as e:
        st.error(f"Error fetching options: {e}")
        return {}

def add_transaction_log(new_row_data):
    """
    Appends a new row to '00_거래일지'.
    new_row_data: dict containing keys matching columns.
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = _read_sheet(conn, worksheet="00_거래일지", ttl="0")
        
        # Convert dict to DataFrame
        new_df = pd.DataFrame([new_row_data])
        
        # Append
        updated_df = pd.concat([df, new_df], ignore_index=True)
        
        # Update Sheet
        _update_sheet(conn, worksheet="00_거래일지", data=updated_df)
        
        # Clear cache to reflect changes immediately
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error saving transaction: {e}")
        return False

def overwrite_transaction_log(df_new):
    """
    Overwrites '00_거래일지' with the provided DataFrame.
    Used for batch updates (e.g. Pending -> Settled).
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        _update_sheet(conn, worksheet="00_거래일지", data=df_new)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error updating logs: {e}")
        return False

def get_latest_transaction_log():
    """
    Fetches the '00_거래일지' sheet explicitly with ttl=0 to bypass cache.
    Crucial for overwrite operations to avoid using stale data (zombie rows).
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # Force fresh read
        df = _read_sheet(conn, worksheet="00_거래일지", ttl="0")
        if df is None:
            return pd.DataFrame()
        return _clean_numeric_cols(df, ['Amount', 'Qty', '수량', '금액'])
    except Exception as e:
        st.error(f"Error fetching latest logs: {e}")
        return pd.DataFrame()

def _clean_history_data(df):
    """
    Cleans the history dataframe: converts dates, ensures numerics.
    """
    if df is None or df.empty:
        return df
    
    # Copy to avoid SettingWithCopy
    df = df.copy()
    
    # Date conversion (Handle '25. 9. 22' format)
    if '날짜' in df.columns:
        # Check if date is string and try specific format if common 'YY. MM. DD' logic fails
        # pd.to_datetime can be smart, but let's help it.
        # Removing spaces can help if it's "25. 9. 22" -> "25.9.22"
        if df['날짜'].dtype == object:
             df['날짜'] = df['날짜'].astype(str).str.replace(' ', '')
        
        # Try converting with dayfirst=False, yearfirst=True usually for YY
        df['날짜'] = pd.to_datetime(df['날짜'], format='%y.%m.%d', errors='coerce')
        
        # Fallback for standard formats if above failed (optional, but robust)
        # df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
        
        # Filter invalid dates
        df = df.dropna(subset=['날짜'])
        df = df.sort_values('날짜')
    
    # Attempt to convert other columns to numeric, ignoring errors (coercing to NaN then 0)
    # We essentially want all columns except '날짜', '요일' to be numeric.
    cols_to_numeric = [c for c in df.columns if c not in ['날짜', '요일']]
    for col in cols_to_numeric:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Filter Weekends (User Request: Exclude 1=Sun, 7=Sat)
    if '요일' in df.columns:
        # Ensure it's numeric for comparison
        df['요일'] = pd.to_numeric(df['요일'], errors='coerce')
        # Drop rows where '요일' is 1 (Sunday) or 7 (Saturday)
        df = df[~df['요일'].isin([1, 7])]

    return df

def _clean_numeric_cols(df, candidates):
    """
    Clean specific numeric columns if they exist.
    """
    if df is None: return None
    df = df.copy()
    for col in candidates:
        if col in df.columns:
             # Handle string formatting like commas or currency symbols
             if df[col].dtype == object:
                 df[col] = df[col].astype(str).str.replace(',', '').str.replace('₩', '').str.replace('$', '').str.replace(' ', '')
             df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def calculate_dod(df_history):
    """
    Calculates Day-over-Day change for the latest date.
    Returns a dict: { 'PortfolioName': {'value': current_val, 'change': diff_val, 'pct': diff_pct} }
    """
    if df_history is None or len(df_history) < 2:
        return {}
    
    # Get last two rows
    latest = df_history.iloc[-1]
    prev = df_history.iloc[-2]
    
    # Identify value columns (excluding Date, Day, and Index cols which end in _idx)
    # Assumes columns not ending in '_idx' and not '날짜', '요일' represent Asset Value.
    value_cols = [c for c in df_history.columns if c not in ['날짜', '요일'] and not c.endswith('_idx')]
    
    dod_data = {}
    for col in value_cols:
        curr_val = latest[col]
        prev_val = prev[col]
        diff = curr_val - prev_val
        pct = (diff / prev_val) if prev_val != 0 else 0
        
        dod_data[col] = {
            'value': curr_val,
            'diff': diff,
            'pct': pct
        }
        
    return dod_data

# --- SQLite Sync Logic ---
import hashlib
from modules import db_manager

def _generate_hash(row):
    """
    Generates a unique hash for a transaction row using key fields.
    Fields used: date, account, asset, type, amount, qty.
    NOTE: 'note' is explicitly EXCLUDED to allow 'Pending' -> 'Settled' updates.
    """
    # Normalize strings (strip) and numbers (float)
    # Row keys match GSheet columns: '날짜', '계좌', '종목', '거래구분', '거래금액', '수량'
    # Mapped to DB cols: date, account_name, asset_name, type, amount, qty
    
    unique_str = f"{str(row.get('날짜', '')).strip()}_" \
                 f"{str(row.get('계좌', '')).strip()}_" \
                 f"{str(row.get('종목', '')).strip()}_" \
                 f"{str(row.get('거래구분', '')).strip()}_" \
                 f"{float(row.get('거래금액', 0))}_" \
                 f"{float(row.get('수량', 0))}"
                 
    return hashlib.md5(unique_str.encode('utf-8')).hexdigest()

def sync_to_sqlite(data_dict):
    """
    Synchronizes the fetched GSheet data to local SQLite DB.
    """
    if not data_dict:
        return False, "No data to sync."
    
    try:
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # 1. Sync Masters
        _sync_masters(cursor, data_dict.get('account_master'), data_dict.get('asset_master'))
        
        # 2. Sync Transactions (Incremental)
        added_count = _sync_transactions(cursor, data_dict.get('transactions'))
        
        conn.commit()
        conn.close()
        return True, f"Sync check complete. {added_count} new/updated rows."
        
    except Exception as e:
        return False, f"Sync failed: {e}"

def _sync_masters(cursor, df_acct, df_asset):
    """
    Upserts master data.
    """
    # Account Master
    if df_acct is not None and not df_acct.empty:
        # Expected Cols: 계좌번호, 소유자, 계좌명, 증권사(Optional), 계좌구분(Optional)
        # DB Cols: account_number, owner, account_name, broker, type
        for _, row in df_acct.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO account_master (account_number, owner, account_name, broker, type)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(row.get('계좌번호', '')).strip(),
                str(row.get('소유자', '')).strip(),
                str(row.get('계좌명', '')).strip(),
                str(row.get('증권사', '')) if '증권사' in row else None,
                str(row.get('계좌구분', '')) if '계좌구분' in row else None
            ))
            
    # Asset Master
    if df_asset is not None and not df_asset.empty:
        # Expected Cols: 티커, 종목명, 통화, 자산구분
        # DB Cols: ticker, asset_name, currency, asset_class
        for _, row in df_asset.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO asset_master (ticker, asset_name, currency, asset_class)
                VALUES (
                    (SELECT ticker FROM asset_master WHERE asset_name = ?), -- Preserve existing Ticker if null? No, Master is source of truth.
                    ?, ?, ?
                )
            """, ( # Actually REPLACE might change ID. Let's use INSERT OR REPLACE on Unique Name logic?
                   # Since ID is Autoincrement, REPLACE deletes old row (and ID). 
                   # It's safer to Upsert by Name.
                   # But SQLite UPSERT requires ON CONFLICT.
                   # Let's simplify: Just REPLACE based on Name?
                   # Name is UNIQUE.
                   pass
            ))
            # Retry with proper UPSERT syntax
            cursor.execute("""
                INSERT INTO asset_master (ticker, asset_name, currency, asset_class)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(asset_name) DO UPDATE SET
                    ticker=excluded.ticker,
                    currency=excluded.currency,
                    asset_class=excluded.asset_class,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                str(row.get('티커', '')).strip(),
                str(row.get('종목명', '')).strip(),
                str(row.get('통화', 'KRW')).strip(),
                str(row.get('자산구분', 'Stock')).strip()
            ))

def _sync_transactions(cursor, df_txn):
    """
    Incrementally loads transactions.
    """
    if df_txn is None or df_txn.empty:
        return 0
        
    count = 0
    # Optimize: Get all existing hashes to avoid trying INSERT on everything?
    # Or just use INSERT OR REPLACE provided usage of Unique Index on sync_hash.
    
    # We must prepare the rows.
    for idx, row in df_txn.iterrows():
        # Clean Data
        r_hash = _generate_hash(row)
        r_date = str(row.get('날짜', '')).strip()
        
        # Skip empty rows
        if not r_date or r_date == 'NaT':
            continue
            
        try:
            # Insert or Update (if Pending -> Settled change happens, hash is SAME? NO wait.)
            # If 'note' changes, does hash change?
            # User requirement: 'Note' excluded from Hash.
            # So if Hash X exists with note='Pending', and now we have Hash X with note='Settled'.
            # INSERT OR REPLACE will update the row (Hash collision).
            
            cursor.execute("""
                INSERT INTO transaction_log (
                    date, account_name, asset_name, type, amount, qty, price, currency, note,
                    source_row_index, sync_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sync_hash) DO UPDATE SET
                    note = excluded.note,
                    source_row_index = excluded.source_row_index,
                    synced_at = CURRENT_TIMESTAMP
            """, (
                r_date,
                str(row.get('계좌', '')).strip(),
                str(row.get('종목', '')).strip(),
                str(row.get('거래구분', '')).strip(),
                float(row.get('거래금액', 0)),
                float(row.get('수량', 0)),
                0.0, # Price is not reliable in log, usually derived. Or we can calc? amount/qty?
                # Actually log doesn't have explicit 'Price' column usually? 
                # Let's check GSheet. Yes, no explicit Price col in '00_거래일지' usually. But app logic might need it.
                # Just store 0 or calc.
                str(row.get('통화', 'KRW')).strip(),
                str(row.get('비고', '')).strip(),
                idx + 2, # Approx row number (header+1)
                r_hash
            ))
            
            # Check if row was inserted (Optimization: counting is hard with upsert, assume processed)
            count += 1
            
        except Exception as e:
            print(f"Row error: {e}")
            continue
            
    return count
