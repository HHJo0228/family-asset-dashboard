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
