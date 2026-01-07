import streamlit as st
import pandas as pd
from datetime import datetime
from modules import database, models, migration, data_loader
from sqlalchemy import func

def get_last_synced_row_index(db):
    """
    Returns the maximum source_row_index from the transaction_log.
    Used to identify where to start scanning for new rows.
    """
    max_idx = db.query(func.max(models.Transaction.source_row_index)).scalar()
    return max_idx if max_idx is not None else 0

def auto_sync():
    """
    Automatically syncs data on app startup.
    Uses efficient caching and incremental checks.
    """
    # 1. Check if we already synced in this session run (prevent redundant checks on interaction)
    if "data_synced" in st.session_state and st.session_state.data_synced:
        return

    msg_placeholder = st.empty()
    msg_placeholder.write("⏳ Checking for data updates...")

    try:
        # 2. Load Data (Cached by Streamlit)
        # This is fast if cache is hit, slower if TTL expired (~10m).
        data = data_loader.load_data()
        
        if not data:
            msg_placeholder.error("Failed to load data from Google Sheets.")
            return

        # 3. Incremental Logic
        # We assume data_loader returned the full dataset (or what matches the sheet).
        # We verify if we need to insert anything.
        
        db = next(database.get_db())
        last_idx = get_last_synced_row_index(db)
        
        df_txn = data.get('transactions')
        if df_txn is not None and not df_txn.empty:
            # Check the max index in the new data (approximate by length if index not explicit)
            # data_loader doesn't return the raw row index explicitly in the dataframe value, 
            # but migration logic calculates it as idx + 2.
            # So total rows + 1 should be roughly the max index.
            
            estimated_new_rows = len(df_txn) # Total rows in sheet
            # If we have significantly more rows in sheet than the Max Index in DB, strictly sync.
            # Or if it's just safer to run the robust deduplication migration every time (since it's fast locally).
            
            # For robustness in Phase 2, we RUN the migration logic 
            # because migration.py now has DUPLICATE DETECTION.
            # It will quickly skip existing hashes.
            
            # Only run if we actually have data
            success, msg = migration.migrate_google_sheets_to_sqlite()
            
            if success:
                msg_placeholder.success(f"Rx: {msg}")
                # Refresh Streamlit Cache if *something* changed? 
                # Actually data_loader cache is GSheet side. 
                # If DB updated, we might need to clear *Query Caches* if we had them.
            else:
                msg_placeholder.warning(f"Sync Issue: {msg}")

        st.session_state.data_synced = True
        st.session_state.last_sync_time = datetime.now().strftime('%H:%M:%S')
        
    except Exception as e:
        msg_placeholder.error(f"Auto-sync failed: {e}")
        st.session_state.last_sync_time = "Failed"
    finally:
        db.close()
        # Fade out message
        import time
        time.sleep(1)
        msg_placeholder.empty()
