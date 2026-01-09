import sqlite3
import os
import streamlit as st
import pandas as pd

DB_FILE = os.path.join(os.getcwd(), "assets.db")
print(f"DEBUG: db_manager using DB at {DB_FILE}")

def get_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    # Enable accessing columns by name
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database with valid tables and views."""
    conn = get_connection()
    c = conn.cursor()

    # Force Schema Reset (Dev Phase) - REMOVED to persist data
    # c.execute("DROP VIEW IF EXISTS view_asset_inventory;")
    # c.execute("DROP VIEW IF EXISTS view_transaction_details;")
    # c.execute("DROP TABLE IF EXISTS transaction_log;")
    # c.execute("DROP TABLE IF EXISTS asset_master;")
    # c.execute("DROP TABLE IF EXISTS account_master;")

    # 1. Accounts Master
    c.execute("""
    CREATE TABLE IF NOT EXISTS account_master (
        account_number TEXT PRIMARY KEY,
        owner TEXT NOT NULL,
        account_name TEXT NOT NULL,
        broker TEXT,
        type TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    # Index for joins
    c.execute("CREATE INDEX IF NOT EXISTS idx_account_name ON account_master(account_name);")

    # 2. Asset Master
    c.execute("""
    CREATE TABLE IF NOT EXISTS asset_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        asset_name TEXT NOT NULL UNIQUE,
        currency TEXT DEFAULT 'KRW',
        asset_class TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_asset_ticker ON asset_master(ticker);")

    # 3. Inventory Snapshot (Legacy/Static Baseline)
    c.execute("""
    CREATE TABLE IF NOT EXISTS inventory_snapshot (
        owner TEXT,
        account_name TEXT,
        asset_name TEXT,
        ticker TEXT,
        qty REAL,
        amount REAL,
        dividend REAL,
        realized REAL
    );
    """)

    # 4. Portfolio History (Daily Snapshot for Trends & Index)
    c.execute("""
    CREATE TABLE IF NOT EXISTS portfolio_history (
        date TEXT,
        portfolio_name TEXT,
        eval_value REAL,
        invested_principal REAL,
        ref_price REAL,
        index_val REAL,
        is_final INTEGER DEFAULT 0,
        PRIMARY KEY (date, portfolio_name)
    );
    """)

    # 5. Asset History (Granular Daily Snapshot)
    c.execute("""
    CREATE TABLE IF NOT EXISTS asset_history (
        date TEXT,
        owner TEXT,
        account_name TEXT,
        asset_name TEXT,
        qty REAL,
        price_native REAL,
        eval_value_krw REAL,
        is_final INTEGER DEFAULT 0,
        PRIMARY KEY (date, owner, account_name, asset_name)
    );
    """)

    # 6. Transaction Log
    # Added 'owner' to resolve ambiguity (Account Name is not unique across owners)
    c.execute("""
    CREATE TABLE IF NOT EXISTS transaction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        owner TEXT NOT NULL, 
        account_name TEXT NOT NULL,
        asset_name TEXT NOT NULL,
        type TEXT NOT NULL,
        amount REAL DEFAULT 0,
        qty REAL DEFAULT 0,
        price REAL DEFAULT 0,
        currency TEXT,
        note TEXT,
        
        source_row_index INTEGER,
        sync_hash TEXT UNIQUE,
        synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON transaction_log(date);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_asset ON transaction_log(asset_name);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_owner ON transaction_log(owner);") # Good for filtering

    # 4. View: Transaction Details (Reconstruction)
    c.execute("DROP VIEW IF EXISTS view_transaction_details;")
    c.execute("""
    CREATE VIEW view_transaction_details AS
    SELECT 
        t.id,
        t.date,
        t.owner,
        t.account_name,
        t.asset_name,
        am.ticker,
        t.type,
        t.amount,
        t.qty,
        t.price,
        t.currency,
        t.note
    FROM transaction_log t
    LEFT JOIN account_master a ON t.account_name = a.account_name AND t.owner = a.owner
    LEFT JOIN asset_master am ON t.asset_name = am.asset_name;
    """)

    # --- VIEWS (Complex Aggregations) ---
    c.execute("DROP VIEW IF EXISTS view_asset_inventory;")
    c.execute("""
    CREATE VIEW view_asset_inventory AS
    SELECT 
        owner,
        account_name,
        asset_name,
        MAX(ticker) as ticker,
        SUM(current_qty) as current_qty,
        SUM(net_book_value_amount) as net_book_value_amount,
        SUM(total_dividends) as total_dividends,
        SUM(total_realized_gains) as total_realized_gains,
        MAX(last_transaction_date) as last_transaction_date
    FROM (
        -- 0. SNAPSHOT (Baseline)
        SELECT
            owner,
            account_name,
            asset_name,
            ticker,
            qty as current_qty,
            -- Force Balance = Invested for Cash/Unlisted in Snapshot Baseline
            CASE 
                WHEN asset_name IN ('원화', '달러') OR ticker = '-' OR ticker IS NULL THEN qty
                ELSE amount 
            END as net_book_value_amount,
            dividend as total_dividends,
            realized as total_realized_gains,
            NULL as last_transaction_date
        FROM inventory_snapshot
        
        UNION ALL

        -- 1. Standard Assets (Stocks/Non-Cash) FLOW
        SELECT 
            t.owner,
            t.account_name,
            t.asset_name,
            am.ticker,
            SUM(CASE
                WHEN t.type = '매수' OR t.type = '초기' THEN t.qty
                WHEN t.type = '매도' THEN -t.qty
                ELSE 0 
            END) as current_qty,

            SUM(CASE
                -- If Unlisted (ticker is NULL or '-'), then Invested = Balance (Qty * 1)
                WHEN am.ticker IS NULL OR am.ticker = '-' THEN (
                    CASE
                        WHEN t.type = '매수' OR t.type = '초기' THEN t.qty
                        WHEN t.type = '매도' THEN -t.qty
                        ELSE 0
                    END
                )
                -- Otherwise, use standard Cost Basis logic (Buy Price - Sell Price)
                WHEN t.type = '매수' OR t.type = '초기' THEN t.amount
                WHEN t.type = '매도' THEN -t.amount
                WHEN t.type = '확정손익' THEN t.amount 
                ELSE 0
            END) as net_book_value_amount,
            
            SUM(CASE
                WHEN t.type = '배당금' THEN t.amount
                ELSE 0
            END) as total_dividends,
            
            SUM(CASE
                WHEN t.type = '확정손익' THEN t.amount
                ELSE 0
            END) as total_realized_gains,
            
            MAX(t.date) as last_transaction_date

        FROM transaction_log t
        LEFT JOIN asset_master am ON t.asset_name = am.asset_name
        WHERE t.asset_name NOT IN ('원화', '달러')
        GROUP BY t.owner, t.account_name, t.asset_name

        UNION ALL

        -- 2. KRW (Won) Cash Logic (EXACT USER FORMULA)
        SELECT 
            t.owner, 
            t.account_name, 
            '원화' as asset_name, 
            '-' as ticker,
            SUM(CASE 
                -- Explicit Cash
                WHEN t.asset_name = '원화' AND t.type = '입금' THEN t.qty
                WHEN t.asset_name = '원화' AND t.type = '출금' THEN -t.qty
                
                -- Trading Flow (KRW)
                WHEN t.type = '매도' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
                WHEN t.type = '매수' AND (t.currency = 'KRW' OR t.currency = '₩') THEN -t.amount
                WHEN t.type = '배당금' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
                
                -- Exchange Logic
                WHEN t.asset_name = '원화' AND t.type LIKE '%환전%' THEN t.qty 
                WHEN t.asset_name = '달러' AND t.type LIKE '%환전%' THEN -t.amount 
                
                ELSE 0 
            END) as current_qty,

            -- Invested Amount for Cash = Current Balance (Balance = Invested)
            SUM(CASE 
                -- Explicit Cash
                WHEN t.asset_name = '원화' AND t.type = '입금' THEN t.qty
                WHEN t.asset_name = '원화' AND t.type = '출금' THEN -t.qty
                
                -- Trading Flow (KRW)
                WHEN t.type = '매도' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
                WHEN t.type = '매수' AND (t.currency = 'KRW' OR t.currency = '₩') THEN -t.amount
                WHEN t.type = '배당금' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
                
                -- Exchange Logic
                WHEN t.asset_name = '원화' AND t.type LIKE '%환전%' THEN t.qty 
                WHEN t.asset_name = '달러' AND t.type LIKE '%환전%' THEN -t.amount 
                ELSE 0 
            END) as net_book_value_amount,

            SUM(CASE
                WHEN t.asset_name = '원화' AND t.type = '배당금' THEN t.amount
                WHEN t.type = '배당금' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
                ELSE 0
            END) as total_dividends,
            
            SUM(CASE
                 WHEN t.asset_name = '원화' AND t.type = '배당금' THEN t.amount
                 WHEN t.type = '배당금' AND (t.currency = 'KRW' OR t.currency = '₩') THEN t.amount
                 -- We don't add 확정손익 to cash balance, but we can show it as "Realized" for the asset row if needed.
                 -- However, for Cash, 'Dividends' are the main realized gain.
                 ELSE 0
            END) as total_realized_gains,
            
            MAX(t.date) as last_transaction_date
        FROM transaction_log t
        GROUP BY t.owner, t.account_name

        UNION ALL

        -- 3. USD (Dollar) Cash Logic (EXACT USER FORMULA)
        SELECT 
            t.owner, 
            t.account_name, 
            '달러' as asset_name, 
            '-' as ticker,
            SUM(CASE 
                -- Explicit Cash
                WHEN t.asset_name = '달러' AND t.type = '입금' THEN t.qty
                WHEN t.asset_name = '달러' AND t.type = '출금' THEN -t.qty

                -- Trading Flow (USD)
                WHEN t.type = '매도' AND (t.currency = 'USD' OR t.currency = '$') THEN t.amount
                WHEN t.type = '매수' AND (t.currency = 'USD' OR t.currency = '$') THEN -t.amount
                WHEN t.type = '배당금' AND (t.currency = 'USD' OR t.currency = '$') THEN t.amount

                -- Exchange Logic
                WHEN t.asset_name = '달러' AND t.type LIKE '%환전%' THEN t.qty
                WHEN t.asset_name = '원화' AND t.type LIKE '%환전%' THEN -t.amount

                ELSE 0 
            END) as current_qty,

            -- Invested Amount for Cash = Current Balance (Balance = Invested)
            SUM(CASE 
                -- Explicit Cash
                WHEN t.asset_name = '달러' AND t.type = '입금' THEN t.qty
                WHEN t.asset_name = '달러' AND t.type = '출금' THEN -t.qty

                -- Trading Flow (USD)
                WHEN t.type = '매도' AND (t.currency = 'USD' OR t.currency = '$') THEN t.amount
                WHEN t.type = '매수' AND (t.currency = 'USD' OR t.currency = '$') THEN -t.amount
                WHEN t.type = '배당금' AND (t.currency = 'USD' OR t.currency = '$') THEN t.amount

                -- Exchange Logic
                WHEN t.asset_name = '달러' AND t.type LIKE '%환전%' THEN t.qty
                WHEN t.asset_name = '원화' AND t.type LIKE '%환전%' THEN -t.amount
                ELSE 0 
            END) as net_book_value_amount,

            SUM(CASE
                WHEN t.type = '배당금' AND (t.currency = 'USD' OR t.currency = '$') THEN t.amount
                ELSE 0
            END) as total_dividends,
            
            SUM(CASE
                WHEN t.type = '배당금' AND (t.currency = 'USD' OR t.currency = '$') THEN t.amount
                ELSE 0
            END) as total_realized_gains,
            
            MAX(t.date) as last_transaction_date
        FROM transaction_log t
        GROUP BY t.owner, t.account_name
    ) FinalView
    GROUP BY owner, account_name, asset_name;
    """)

    conn.commit()
    conn.close()
