import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def breakdown_won_calculation():
    conn = sqlite3.connect('assets.db')
    
    # Focus on the user's problematic account/asset
    # From screenshot: Asset='원화', Amount = -140,762,820
    # Let's verify which account has this. 9    박행자          LS1         원화      - -1.039813e+08 (Step 6843)
    # Wait, -140M in screenshot vs -103M in my diagnose log?
    # Maybe different account or aggregate?
    # Let's dump breakdown for ALL '원화' holdings
    
    print("=== 'WON' (KRW) Balance Breakdown ===")
    
    query = """
    SELECT 
        t.owner, 
        t.account_name,
        SUM(CASE 
            WHEN t.asset_name = '원화' AND t.type = '입금' THEN t.qty 
            ELSE 0 END) as 'Deposits',
        SUM(CASE 
            WHEN t.asset_name = '원화' AND t.type = '출금' THEN -t.qty 
            ELSE 0 END) as 'Withdrawals',
        SUM(CASE 
            WHEN t.type = '매도' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
            ELSE 0 END) as 'Stock_Sells',
        SUM(CASE 
            WHEN t.type = '매수' AND (t.currency = 'KRW' OR t.currency = '₩') THEN -t.amount
            ELSE 0 END) as 'Stock_Buys',
        SUM(CASE 
            WHEN t.type = '배당금' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
            ELSE 0 END) as 'Dividends',
        SUM(CASE 
            WHEN t.asset_name = '원화' AND t.type LIKE '%환전%' THEN t.qty 
            ELSE 0 END) as 'Exch_In',
        SUM(CASE 
            WHEN t.asset_name = '달러' AND t.type LIKE '%환전%' THEN -t.amount 
            ELSE 0 END) as 'Exch_Out',
        SUM(CASE 
            WHEN t.asset_name = '원화' AND t.type = '입금' THEN t.qty
            WHEN t.asset_name = '원화' AND t.type = '출금' THEN -t.qty
            WHEN t.type = '매도' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
            WHEN t.type = '매수' AND (t.currency = 'KRW' OR t.currency = '₩') THEN -t.amount
            WHEN t.type = '배당금' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
            WHEN t.asset_name = '원화' AND t.type LIKE '%환전%' THEN t.qty 
            WHEN t.asset_name = '달러' AND t.type LIKE '%환전%' THEN -t.amount 
            ELSE 0 
        END) as 'Calculated_Total'
    FROM transaction_log t
    GROUP BY t.owner, t.account_name
    HAVING Calculated_Total != 0
    """
    
    df = pd.read_sql(query, conn)
    print(df.to_string())
    
    print("\n=== Initial Snapshot Check ===")
    # Check if inventory_snapshot has anything
    snap_count = pd.read_sql("SELECT count(*) as c FROM inventory_snapshot", conn).iloc[0]['c']
    print(f"Snapshot Rows: {snap_count}")
    
    conn.close()

if __name__ == "__main__":
    breakdown_won_calculation()
