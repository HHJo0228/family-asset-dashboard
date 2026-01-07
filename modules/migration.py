import pandas as pd
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from modules import database,models
from modules import data_loader
import streamlit as st

def generate_sync_hash(row):
    """
    Generates a unique hash for a transaction row.
    Cols: Date, Owner, Account, Asset, Type, Amount, Qty
    """
    unique_str = f"{str(row.get('날짜', '')).strip()}_" \
                 f"{str(row.get('소유자', '')).strip()}_" \
                 f"{str(row.get('계좌', '')).strip()}_" \
                 f"{str(row.get('종목', '')).strip()}_" \
                 f"{str(row.get('거래구분', '')).strip()}_" \
                 f"{float(row.get('거래금액', 0))}_" \
                 f"{float(row.get('수량', 0))}"
    return hashlib.md5(unique_str.encode('utf-8')).hexdigest()

def migrate_google_sheets_to_sqlite():
    """
    Full migration logic:
    1. Load data from Sheets (mock or real).
    2. Sync Masters (Account/Asset).
    3. Sync Transactions.
    """
    # 1. Init DB
    database.initialize_sqlite_db()
    
    # 2. Fetch Data
    print("Fetching data from Google Sheets...")
    # Note: data_loader.load_data() is cached.
    # We might want to force reload if needed, but for now use cache.
    data = data_loader.load_data()
    
    if not data:
        print("Failed to load data.")
        return False, "Failed to load GSheet data."

    db = next(database.get_db())
    try:
        # 3. Sync Account Master
        df_acct = data.get('account_master')
        if df_acct is not None and not df_acct.empty:
            print(f"Syncing {len(df_acct)} accounts...")
            for _, row in df_acct.iterrows():
                acct_num = str(row.get('계좌번호', '')).strip()
                if not acct_num: continue
                
                acct = db.query(models.Account).filter_by(account_number=acct_num).first()
                if not acct:
                    acct = models.Account(account_number=acct_num)
                
                acct.owner = str(row.get('소유자', '')).strip()
                acct.account_name = str(row.get('계좌명', '')).strip()
                acct.broker = str(row.get('증권사', '')) if '증권사' in row else None
                acct.type = str(row.get('포트폴리오 구분', row.get('계좌구분', ''))).strip() or "General"
                
                db.add(acct)
        
        # 4. Sync Asset Master
        df_asset = data.get('asset_master')
        if df_asset is not None and not df_asset.empty:
            print(f"Syncing {len(df_asset)} assets...")
            for _, row in df_asset.iterrows():
                asset_name = str(row.get('종목명', '')).strip()
                if not asset_name: continue
                
                asset = db.query(models.Asset).filter_by(asset_name=asset_name).first()
                if not asset:
                    asset = models.Asset(asset_name=asset_name)
                
                asset.ticker = str(row.get('티커', '')).strip()
                asset.currency = str(row.get('통화', 'KRW')).strip()
                asset.asset_class = 'Cash' if asset_name in ['원화', '달러'] else 'Stock'
                asset.updated_at = datetime.utcnow()
                
                db.add(asset)

        # 5. Sync Transactions
        df_txn = data.get('transactions')
        if df_txn is not None and not df_txn.empty:
            print(f"Syncing {len(df_txn)} transactions...")
            processed_hashes = set() # Track for intra-batch duplicates
            
            for idx, row in df_txn.iterrows():
                date_str = str(row.get('날짜', '')).strip()
                if not date_str or date_str == 'NaT': continue
                
                try:
                    # Parse date
                    dt = pd.to_datetime(date_str).date()
                except:
                    continue

                sync_hash = generate_sync_hash(row)
                
                # Check for duplicates within this batch execution
                if sync_hash in processed_hashes:
                    continue
                processed_hashes.add(sync_hash)
                
                txn = db.query(models.Transaction).filter_by(sync_hash=sync_hash).first()
                if not txn:
                    txn = models.Transaction(sync_hash=sync_hash)
                
                txn.date = dt
                txn.owner = str(row.get('소유자', '')).strip()
                txn.account_name = str(row.get('계좌', '')).strip()
                txn.asset_name = str(row.get('종목', '')).strip()
                txn.type = str(row.get('거래구분', '')).strip()
                txn.amount = float(row.get('거래금액', 0))
                txn.qty = float(row.get('수량', 0))
                txn.price = 0.0 # Not in GSheet explicit column usually
                txn.currency = str(row.get('통화', 'KRW')).strip()
                
                # Fee & Note
                txn.note = str(row.get('비고', '')).strip()
                # Default status to Settled (완료) unless specified
                txn.status = '완료' 
                
                txn.source_row_index = idx + 2
                txn.synced_at = datetime.utcnow()
                
                db.add(txn)
        
        db.commit()
        print("Migration complete.")
        return True, "Migration successful."

    except Exception as e:
        db.rollback()
        print(f"Migration error: {e}")
        return False, f"Error: {e}"
    finally:
        db.close()
