import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
from yahooquery import Ticker

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_prices(tickers_list):
    """
    Fetches current market prices for a list of tickers using yahooquery.
    Automatically handles Korean stock suffixes (.KS) for numeric tickers.
    """
    if not tickers_list:
        return {}
        
    prices = {}
    # Clean tickers and handle Korean suffix
    processed_tickers_map = {} # Original -> Yahoo
    
    for t in tickers_list:
        if not t or t == '-' or pd.isna(t):
            continue
        
        original_t = str(t).strip()
        # If 6-digit number, append .KS (KOSPI)
        if original_t.isdigit() and len(original_t) == 6:
            yahoo_t = f"{original_t}.KS"
        else:
            yahoo_t = original_t
            
        processed_tickers_map[original_t] = yahoo_t
    
    yahoo_tickers = list(set(processed_tickers_map.values()))
    
    if not yahoo_tickers:
        return {}
        
    try:
        # Batch fetch via yahooquery
        t_obj = Ticker(yahoo_tickers, asynchronous=False)
        data = t_obj.price
        
        for orig_t, yahoo_t in processed_tickers_map.items():
            try:
                if isinstance(data, dict) and yahoo_t in data:
                    ticker_data = data[yahoo_t]
                    if isinstance(ticker_data, dict):
                        price = ticker_data.get('regularMarketPrice')
                        if price is not None:
                            prices[orig_t] = float(price)
            except:
                continue
                        
    except Exception as e:
        print(f"Error fetching prices via yahooquery: {e}")
    
    return prices

@st.cache_data(ttl=300)
def get_usd_krw_rate():
    """
    Fetches the current USD/KRW exchange rate using yahooquery.
    Returns: float (e.g., 1320.5) or 1.0 if failed (fallback)
    """
    try:
        t = Ticker("USDKRW=X", asynchronous=False)
        data = t.price
        if isinstance(data, dict) and "USDKRW=X" in data:
            rate = data["USDKRW=X"].get('regularMarketPrice')
            if rate:
                return float(rate)
    except Exception as e:
        print(f"Error fetching exchange rate: {e}")
    
    return 1.0 # Fallback


def enrich_inventory_with_prices(df_inv, ticker_col='티커', qty_col='수량', invested_col='매입금액'):
    """
    Enrich inventory dataframe with current prices and calculated values
    
    Args:
        df_inv: Inventory dataframe
        ticker_col: Name of ticker column
        qty_col: Name of quantity column  
        invested_col: Name of invested amount column
        
    Returns:
        Enriched dataframe with 현재가, 평가금액, 총평가손익 columns
    """
    if df_inv.empty:
        return df_inv
    
    # Get unique tickers
    tickers = df_inv[ticker_col].dropna().unique().tolist()
    
    # Fetch prices
    price_map = fetch_prices(tickers)
    

def enrich_inventory_with_prices(df_inv, ticker_col='티커', qty_col='수량', invested_col='매입금액'):
    """
    Enrich inventory dataframe with current prices and calculated values
    
    Args:
        df_inv: Inventory dataframe
        ticker_col: Name of ticker column
        qty_col: Name of quantity column  
        invested_col: Name of invested amount column
        
    Returns:
        Enriched dataframe with 현재가, 평가금액, 총평가손익 columns
        And metadata columns for currency display.
    """
    if df_inv.empty:
        return df_inv
    
    # Get unique tickers
    tickers = df_inv[ticker_col].dropna().unique().tolist()
    
    # Fetch prices and Exchange Rate
    price_map = fetch_prices(tickers)
    usd_krw_rate = get_usd_krw_rate()
    
    # --- Helper to identify currency ---
    def get_currency_code(ticker, asset_name):
        if str(ticker) == '-':
            # Cash assets
            if '달러' in str(asset_name) or 'USD' in str(asset_name):
                return 'USD'
            return 'KRW'
        # Heuristic: Numeric 6-digit = KRW, Alphabetic = USD
        t_str = str(ticker).strip()
        if t_str.isdigit() and len(t_str) == 6:
            return 'KRW'
        # Check standard US tickers (AAPL, TSLA, etc)
        if t_str.isalpha():
            return 'USD'
        return 'KRW' # Default

    # Apply Currency Code
    if '종목' in df_inv.columns:
        df_inv['화폐'] = df_inv.apply(lambda x: get_currency_code(x[ticker_col], x['종목']), axis=1)
    else:
        df_inv['화폐'] = df_inv[ticker_col].apply(lambda x: get_currency_code(x, ''))

    # Map prices
    df_inv['현재가_Native'] = df_inv[ticker_col].map(price_map)
    
    # Special handling for '달러' (USD Cash)
    # Ticker is '-' but Currency is 'USD'.
    # For '달러', the "Price" is effectively the Exchange Rate if we value in KRW?
    # No, keep Native Price as 1.0 (1 Dollar = 1 Dollar).
    # Eval in KRW will use Rate.
    # Wait, if Ticker is '-' and Currency USD, fetch_prices won't return it.
    mask_usd_cash = (df_inv['화폐'] == 'USD') & ((df_inv[ticker_col] == '-') | (df_inv[ticker_col].isna()))
    df_inv.loc[mask_usd_cash, '현재가_Native'] = 1.0
    
    # Special handling for KRW Cash
    mask_krw_cash = (df_inv['화폐'] == 'KRW') & ((df_inv[ticker_col] == '-') | (df_inv[ticker_col].isna()))
    df_inv.loc[mask_krw_cash, '현재가_Native'] = 1.0

    # Fill NaN prices with avg price (defensive)
    if '평단가' in df_inv.columns:
        df_inv['현재가_Native'] = df_inv['현재가_Native'].fillna(df_inv['평단가'])
    else:
        df_inv['현재가_Native'] = df_inv['현재가_Native'].fillna(0)
        
    # --- Calculate Evaluation Types ---
    # 1. Native Valuation (in original currency)
    df_inv['평가금액_Native'] = df_inv[qty_col] * df_inv['현재가_Native']
    
    # 2. KRW Valuation (Total Wealth)
    # If USD, multiply by Rate. If KRW, keep as is.
    df_inv['Rate_Applied'] = df_inv['화폐'].apply(lambda x: usd_krw_rate if x == 'USD' else 1.0)
    
    df_inv['평가금액'] = df_inv['평가금액_Native'] * df_inv['Rate_Applied']
    df_inv['현재가'] = df_inv['현재가_Native'] * df_inv['Rate_Applied'] # Price in KRW for uniformity
    
    # 3. Invested Amount
    # Store Native Invested Amount
    df_inv['매입금액_Native'] = df_inv[invested_col]
    
    # Calculate Invested Amount in KRW (Approximation using Current Rate for Total Wealth aggregation)
    # Note: Ideally, we should use historical rate. But without it, we align with Current Valuation logic.
    df_inv[invested_col] = df_inv[invested_col] * df_inv['Rate_Applied']
    
    # Calculate P/L in Native Currency
    df_inv['총평가손익_Native'] = df_inv['평가금액_Native'] - df_inv['매입금액_Native']
    
    # Convert P/L to KRW (Or Recalculate from KRW columns)
    # Option A: Convert Native P/L
    # df_inv['총평가손익'] = df_inv['총평가손익_Native'] * df_inv['Rate_Applied']
    # Option B: Recalculate (Consistent)
    df_inv['총평가손익'] = df_inv['평가금액'] - df_inv[invested_col]
    
    # Fill NaN
    cols_to_fill = ['현재가', '평가금액', '총평가손익', '현재가_Native', '평가금액_Native', '총평가손익_Native', '매입금액_Native', invested_col]
    for c in cols_to_fill:
        if c in df_inv.columns:
            df_inv[c] = df_inv[c].fillna(0)
    
    return df_inv
