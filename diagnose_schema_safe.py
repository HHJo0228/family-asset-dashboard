import sys
import io
import pandas as pd
from modules import db_loader
from contextlib import redirect_stdout

# Force UTF-8 for stdout to prevent Windows encoding errors
sys.stdout.reconfigure(encoding='utf-8')

def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', 'ignore').decode('utf-8'))

safe_print("=== Starting Schema Diagnosis ===")

try:
    # Load data using the actual module logic
    data = db_loader.load_all_data_from_db()
    
    if data is None:
        safe_print("ERROR: db_loader returned None.")
        sys.exit(1)

    required_keys = ['inventory', 'history', 'transactions']
    
    for key, df in data.items():
        safe_print(f"\n[Table: {key}]")
        if df.empty:
            safe_print("  - Status: Empty DataFrame")
            continue
            
        safe_print(f"  - Shape: {df.shape}")
        safe_print("  - Columns:")
        for col in df.columns:
            # Check for non-numeric types in seemingly numeric columns
            dtype = df[col].dtype
            sample = df[col].iloc[0] if len(df) > 0 else "N/A"
            safe_print(f"    - {col} ({dtype}): Sample='{sample}'")
            
except Exception as e:
    safe_print(f"\nCRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()

safe_print("\n=== Diagnosis Complete ===")
