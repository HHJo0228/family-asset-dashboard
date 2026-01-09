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
    # 1. Init DB (Ensure Views exist)
    database.initialize_sqlite_db()
    from modules import db_manager
    db_manager.init_db() # Force create Views (view_asset_inventory)
    
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
        
        # 6. Sync History Snapshot
        df_hist = data.get('history')
        _sync_history(db, df_hist)

        # 7. Sync Inventory Snapshot (Baseline)
        # CRITICAL FIX: We must load this from the SOURCE (GSheet/Data Loader), NOT from the View.
        # Calculating from View (which sums Snapshot + Log) and writing back to Snapshot creates an infinite loop.
        # This table represents the STATIC BASELINE (e.g. Sept 2025).
        
        df_inv_source = data.get('inventory')
        
        if True: # Force Skip for Safety
            print("Skipping Source Inventory Sync to prevent duplication.")
            print("Note: Initial Balance is already merged into Transaction Log.")
            _sync_inventory(db, pd.DataFrame())
        elif df_inv_source is not None and not df_inv_source.empty:
            # We need to map GSheet columns to DB Schema columns if they differ.
            # Usually data_loader returns GSheet column names.
            # DB Schema (InventorySnapshot): owner, account_name, asset_name, ticker, qty, price, amount, dividend, realized, currency, asset_class
            
            # Use _sync_inventory directly, assuming data_loader format is compatible with what _sync_inventory expects.
            # _sync_inventory expects: '소유자', '계좌', '종목', '티커', '수량', '평단가', '평가금액', '배당수익', '확정손익', '통화', '자산구분'
            
            # Note: GSheet usually has '매입금액' for Amount. '평가금액' is calculated.
            # Adjust column mapping if necessary.
            # Previous code mapped 'net_book_value_amount' -> '평가금액' -> 'amount'.
            # Here we expect '매입금액' from GSheet to be mapped to 'amount'.
            
            # Let's verify standard GSheet columns:
            # 소유자, 계좌, 종목, 티커, 포트폴리오 구분, 화폐, 보유주수(수량), 평단가, 현재가, 매입금액, 평가금액...
            
            # Ensure critical columns exist or rename
            rename_map = {
                '보유주수': '수량',
                '매입금액': '평가금액', # In DB 'amount' is mapped from '평가금액' in _sync logic? 
                                     # Let's check _sync_inventory (Line 307: amount=float(row.get('평가금액', 0))).
                                     # Wait, 'amount' should represent BOOK VALUE (Invested) or CURRENT VALUE?
                                     # In Snapshot, it's usually Book Value.
                                     # If GSheet has '매입금액', we should map it to '평가금액' key for _sync_inventory to pick it up?
                                     # That's confusing. Let's fix _sync_inventory input expectation or map here.
                '화폐': '통화'
            }
            df_inv_source.rename(columns=rename_map, inplace=True)
            
            # If '평가금액' is missing but '매입금액' exists (common in GSheet raw data), use '매입금액'.
            # We want 'amount' in DB to be Invested Amount.
            if '평가금액' not in df_inv_source.columns and '매입금액' in df_inv_source.columns:
                 df_inv_source['평가금액'] = df_inv_source['매입금액']

            _sync_inventory(db, df_inv_source)
        else:
            print("Warning: Source Inventory is empty. Clearing Snapshot.")
            _sync_inventory(db, pd.DataFrame())

        db.commit()
        print("Migration complete.")
        return True, "Migration successful."

    except Exception as e:
        db.rollback()
        print(f"Migration error: {e}")
        return False, f"Error: {e}"
    finally:
        db.close()

def _sync_history(db: Session, df: pd.DataFrame):
    """
    Syncs the History DataFrame to HistorySnapshot table.
    Strategy: Full Replace (Snapshot) for simplicity and consistency.
    """
    if df is None or df.empty:
        return

    try:
        # 1. Clear existing snapshots
        db.query(models.HistorySnapshot).delete()
        
        # 2. Transform to Long Format
        # df columns: '날짜', '요일', 'Total', 'OwnerA', ...
        # Exclude '요일' if present
        id_vars = ['날짜']
        value_vars = [c for c in df.columns if c not in ['날짜', '요일']]
        
        df_melted = df.melt(id_vars=id_vars, value_vars=value_vars, var_name='key', value_name='value')
        
        # 3. Bulk Insert
        # Prepare objects
        objects = []
        for _, row in df_melted.iterrows():
            date_val = row['날짜']
            if pd.isna(date_val): continue
            
            # Ensure date object
            if isinstance(date_val, pd.Timestamp):
                date_val = date_val.date()
                
            objects.append(models.HistorySnapshot(
                date=date_val,
                key=str(row['key']),
                value=float(row['value']) if pd.notnull(row['value']) else 0.0,
                updated_at=datetime.utcnow()
            ))
            
        # Optimize: Use bulk_save_objects
        db.bulk_save_objects(objects)
        print(f"Synced {len(objects)} history points.")
        
    except Exception as e:
        print(f"History Sync Error: {e}")
        # Non-critical, just log

def _sync_inventory(db: Session, df: pd.DataFrame):
    """
    Syncs the Inventory DataFrame to InventorySnapshot table.
    Strategy: Full Replace (Snapshot).
    """
    if df is None or df.empty:
        return

    try:
        # 1. Clear existing
        db.query(models.InventorySnapshot).delete()
        
        # 2. Insert
        objects = []
        for _, row in df.iterrows():
            objects.append(models.InventorySnapshot(
                owner=str(row.get('소유자', '')).strip(),
                account_name=str(row.get('계좌', '')).strip(),
                asset_name=str(row.get('종목', '')).strip(),
                ticker=str(row.get('티커', '')).strip() if '티커' in row else None,
                
                qty=float(row.get('수량', 0)),
                price=float(row.get('평단가', 0)), # Avg Price
                amount=float(row.get('평가금액', 0)), # Invested Amount
                
                dividend=float(row.get('배당수익', 0)),
                realized=float(row.get('확정손익', 0)),
                
                currency=str(row.get('통화', 'KRW')).strip(),
                asset_class=str(row.get('자산구분', '')).strip(),
                
                updated_at=datetime.utcnow()
            ))
            
        db.bulk_save_objects(objects)
        print(f"Synced {len(objects)} inventory items.")
        
    except Exception as e:
        print(f"Inventory Sync Error: {e}")

