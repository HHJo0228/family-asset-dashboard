import pandas as pd
from datetime import datetime
import sqlite3
from .db_manager import get_connection
from .price_fetcher import enrich_inventory_with_prices

def record_snapshot(date_override=None):
    """
    Captures a snapshot of current portfolio values and updates the INDEX.
    Handles 'Live' vs 'Final' states based on time.
    """
    now = datetime.now()
    today_str = date_override or now.strftime('%Y-%m-%d')
    is_after_market = now.hour >= 16
    
    conn = get_connection()
    
    # 1. Fetch current inventory from view
    df_inv = pd.read_sql("SELECT * FROM view_asset_inventory", conn)
    
    # Map View columns to the names expected by enrich_inventory_with_prices
    df_inv.rename(columns={
        'asset_name': '종목',
        'ticker': '티커',
        'current_qty': '수량',
        'net_book_value_amount': '매입금액'
    }, inplace=True)
    
    df_inv = enrich_inventory_with_prices(df_inv)
    
    # Get portfolio mappings to group by 'type' (e.g., 쇼호 α, 조연재)
    df_acct = pd.read_sql("SELECT account_name, owner, type as portfolio_name FROM account_master", conn)
    df_inv = df_inv.merge(df_acct, on=['account_name', 'owner'], how='left')
    
    # 2. Granular Asset History
    asset_records = []
    # Ensure current portfolio_name is assigned
    df_inv['portfolio_name'] = df_inv['portfolio_name'].fillna('General').str.strip()
    
    for _, row in df_inv.iterrows():
        asset_records.append((
            today_str,
            str(row['owner']).strip(),
            str(row['account_name']).strip(),
            str(row['종목']).strip(),
            row['수량'],
            row['현재가_Native'],
            row['평가금액'],
            1 if is_after_market else 0
        ))
    
    cur = conn.cursor()
    cur.executemany("""
        INSERT OR REPLACE INTO asset_history 
        (date, owner, account_name, asset_name, qty, price_native, eval_value_krw, is_final)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, asset_records)
    
    # 3. Portfolio-Level Summary & Index Calculation
    portfolios_agg = df_inv.groupby('portfolio_name').agg({
        '평가금액': 'sum',
        '매입금액': 'sum' 
    }).reset_index()
    
    for _, row in portfolios_agg.iterrows():
        p_name = str(row['portfolio_name']).strip()
        curr_eval = row['평가금액']
        curr_principal = row['매입금액']
        
        # Fetch previous record
        prev_data = cur.execute("""
            SELECT eval_value, invested_principal, ref_price, index_val 
            FROM portfolio_history 
            WHERE portfolio_name = ? AND date < ? 
            ORDER BY date DESC LIMIT 1
        """, (p_name, today_str)).fetchone()
        
        if prev_data:
            prev_eval = prev_data['eval_value']
            prev_princ = prev_data['invested_principal']
            prev_ref = prev_data['ref_price']
            
            # Flow adjustment: (Prev_Eval + Net_Flow) / Prev_Eval
            net_flow = curr_principal - prev_princ
            
            # Formula: Today_Ref = ((Prev_Eval + Net_Flow) / Prev_Eval) * Prev_Ref
            if prev_eval > 0:
                ref_price = ((prev_eval + net_flow) / prev_eval) * prev_ref
            else:
                ref_price = curr_principal # Initial state fallback
            
            index_val = (curr_eval / ref_price) * 100 if ref_price > 0 else 100.0
        else:
            # First time record (Bootstrap)
            ref_price = curr_principal
            index_val = 100.0
            
        cur.execute("""
            INSERT OR REPLACE INTO portfolio_history 
            (date, portfolio_name, eval_value, invested_principal, ref_price, index_val, is_final)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (today_str, p_name, curr_eval, curr_principal, ref_price, index_val, 1 if is_after_market else 0))
    
    conn.commit()
    conn.close()
    return True
