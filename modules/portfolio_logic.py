import pandas as pd
import numpy as np

# Portfolio Target Weights (Beta Portfolio)
TARGET_WEIGHTS = {
    "SPY": 0.30,
    "QQQ": 0.25,
    "GMF": 0.10,
    "VEA": 0.10,
    "BND": 0.05,
    "TIP": 0.05,
    "PDBC": 0.05,
    "GLD": 0.05,
    "VNQ": 0.025,
    "Cash": 0.025
}

TOLERANCE = 0.05

def calculate_portfolio_weights(df):
    """
    Calculates current weights for a given portfolio DataFrame.
    Expected df columns: ['Ticker', 'CurrentValue']
    """
    total_value = df['CurrentValue'].sum()
    if total_value == 0:
        return df
    
    df = df.copy()
    df['CurrentWeight'] = df['CurrentValue'] / total_value
    return df

def check_rebalancing(df):
    """
    Checks if any asset is outside the tolerance band.
    Adds 'TargetWeight', 'Diff', 'Action', 'RebalanceFlag' columns.
    """
    df = df.copy()
    # Map target weights; default to 0 if not in target list (e.g. for Alpha portfolio or new assets)
    df['TargetWeight'] = df['Ticker'].map(TARGET_WEIGHTS).fillna(0.0)
    
    # Calculate difference
    df['Diff'] = df['CurrentWeight'] - df['TargetWeight']
    
    # Flag if absolute diff > tolerance
    # Only applicable for assets that are in the TARGET_WEIGHTS list (Beta Portfolio)
    # We assume 'Beta' assets match the keys in TARGET_WEIGHTS. 
    # Logic: If Ticker is in TARGET_WEIGHTS, check tolerance.
    
    def get_action(row):
        if row['Ticker'] not in TARGET_WEIGHTS:
            return "N/A" # or Keep
        
        if row['Diff'] > TOLERANCE:
            return "SELL"
        elif row['Diff'] < -TOLERANCE:
            return "BUY"
        else:
            return "HOLD"

    df['Action'] = df.apply(get_action, axis=1)
    df['RebalanceFlag'] = df['Action'] != "HOLD"
    
    return df

def calculate_cagr(start_val, end_val, years):
    """
    Calculates Compound Annual Growth Rate.
    """
    if start_val <= 0 or years <= 0:
        return 0.0
    return (end_val / start_val) ** (1 / years) - 1

def normalize_index(df_history):
    """
    Normalizes a historical DataFrame (Date, Value) to start at 100.
    """
    df = df_history.sort_values('Date').copy()
    start_val = df['Value'].iloc[0]
    if start_val == 0:
        df['IndexValue'] = 0
    else:
        df['IndexValue'] = (df['Value'] / start_val) * 100
    return df
