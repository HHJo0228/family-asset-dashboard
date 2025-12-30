import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

@st.cache_data(ttl=600)
def load_data():
    """
    Fetches data from multiple worksheets in the '★온가족 자산 정리' Google Sheet.
    Returns a dictionary of DataFrames: 'history', 'cagr', 'inventory', 'beta_plan'.
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # 1. 자산기록 (History)
        # Header is on the 2nd row (index 1)
        df_history = conn.read(worksheet="자산기록", ttl="10m", header=1)
        df_history = _clean_history_data(df_history)

        # 2. 수익률 (CAGR)
        df_cagr = conn.read(worksheet="수익률", ttl="10m")
        
        # 3. 자산종합 (Inventory)
        df_inventory = conn.read(worksheet="자산종합", ttl="10m")
        df_inventory = _clean_numeric_cols(df_inventory, ['Qty', 'Price', 'EvalValue', '수량', '평단가', '평가금액'])

        # 4. 베타포트폴리오 (Beta Plan)
        df_beta = conn.read(worksheet="베타포트폴리오", ttl="10m")
        df_beta = _clean_numeric_cols(df_beta, ['CurrentWeight', 'TargetWeight', '현재비중', '목표비중'])

        return {
            "history": df_history,
            "cagr": df_cagr,
            "inventory": df_inventory,
            "beta_plan": df_beta
        }

    except Exception as e:
        st.error(f"Error loading data: {e}. Check sheet names and permissions.")
        return None

def get_transaction_options():
    """
    Reads '00_거래일지' to get unique values for dropdowns.
    Returns a dict with lists for 'owners', 'accounts', 'tickers', 'types', 'currencies'.
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="00_거래일지", ttl="0") # No cache to get latest
        
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
        df = conn.read(worksheet="00_거래일지", ttl="0")
        
        # Convert dict to DataFrame
        new_df = pd.DataFrame([new_row_data])
        
        # Append
        updated_df = pd.concat([df, new_df], ignore_index=True)
        
        # Update Sheet
        conn.update(worksheet="00_거래일지", data=updated_df)
        
        # Clear cache to reflect changes immediately
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Error saving transaction: {e}")
        return False

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
        
    return df

def _clean_numeric_cols(df, candidates):
    """
    Clean specific numeric columns if they exist.
    """
    if df is None: return None
    df = df.copy()
    for col in candidates:
        if col in df.columns:
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
