import sqlite3
import os
import streamlit as st
import pandas as pd

DB_FILE = "asset_database.db"

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

    # 3. Transaction Log
    # Note: Removed 'owner' as it is normalized (joined via account_master)
    # However, for Incremental Sync efficiency, we might need to know 'owner' to build the Hash?
    # No, Hash builds from the GSheet fields. GSheet has 'owner'.
    # We will exclude 'owner' from the physical table but use it for Hash generation in Python.
    c.execute("""
    CREATE TABLE IF NOT EXISTS transaction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
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

    # 4. View: Transaction Details (Reconstruction)
    c.execute("DROP VIEW IF EXISTS view_transaction_details;")
    c.execute("""
    CREATE VIEW view_transaction_details AS
    SELECT 
        t.id,
        t.date,
        a.owner,
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
    LEFT JOIN account_master a ON t.account_name = a.account_name
    LEFT JOIN asset_master am ON t.asset_name = am.asset_name;
    """)

    # 5. View: Inventory (Aggregation)
    c.execute("DROP VIEW IF EXISTS view_asset_inventory;")
    c.execute("""
    CREATE VIEW view_asset_inventory AS
    SELECT 
        a.owner,
        t.asset_name,
        am.ticker,
        
        -- 1. Quantity Calculation
        SUM(CASE
            -- A. Normal Assets
            WHEN t.asset_name NOT IN ('원화', '달러') AND t.type = '매수' THEN t.qty
            WHEN t.asset_name NOT IN ('원화', '달러') AND t.type = '매도' THEN -t.qty
            
            -- B. Cash: KRW
            WHEN t.asset_name = '원화' AND t.type = '입금' THEN t.qty 
            WHEN t.asset_name = '원화' AND t.type = '출금' THEN -t.qty
            WHEN t.asset_name = '원화' AND t.type = '환전' AND t.asset_name = '원화' THEN t.qty 
            WHEN t.asset_name = '원화' AND t.type = '환전' AND t.asset_name = '달러' THEN -t.amount 
            
            -- KRW form Trading
            WHEN t.asset_name = '원화' AND t.type = '매도' AND t.currency = '₩' THEN t.amount 
            WHEN t.asset_name = '원화' AND t.type = '매수' AND t.currency = '₩' THEN -t.amount
            WHEN t.asset_name = '원화' AND t.type = '배당금' AND t.currency = '₩' THEN t.amount

            -- C. Cash: USD
            WHEN t.asset_name = '달러' AND t.type = '환전' AND t.asset_name = '달러' THEN t.qty 
            WHEN t.asset_name = '달러' AND t.type = '환전' AND t.asset_name = '원화' THEN -t.amount 
            -- Trading Impact
            WHEN t.asset_name = '달러' AND t.type = '매도' AND t.currency = '$' THEN t.amount
            WHEN t.asset_name = '달러' AND t.type = '매수' AND t.currency = '$' THEN -t.amount
            WHEN t.asset_name = '달러' AND t.type = '배당금' AND t.currency = '$' THEN t.amount
            
            ELSE 0 
        END) as current_qty,

        -- 2. Net Invested Amount (For Avg Price)
        SUM(CASE
            WHEN t.type = '매수' THEN t.amount
            WHEN t.type = '매도' THEN -t.amount
            WHEN t.type = '확정손익' THEN t.amount
            ELSE 0
        END) as net_book_value_amount,
        
        MAX(t.date) as last_transaction_date

    FROM transaction_log t
    JOIN account_master a ON t.account_name = a.account_name
    LEFT JOIN asset_master am ON t.asset_name = am.asset_name
    GROUP BY a.owner, t.asset_name;
    """)

    conn.commit()
    conn.close()
