import sqlite3
import pandas as pd
import sys

sys.stdout.reconfigure(encoding='utf-8')

def clean_initial_logs():
    conn = sqlite3.connect('assets.db')
    cursor = conn.cursor()
    
    print("=== Cleaning Previous Initial Assets ===")
    
    # Check count before delete
    before_count = cursor.execute("SELECT count(*) FROM transaction_log WHERE note LIKE '%기초자산%' OR note = 'Initial'").fetchone()[0]
    print(f"Found {before_count} records to delete.")
    
    if before_count > 0:
        cursor.execute("DELETE FROM transaction_log WHERE note LIKE '%기초자산%' OR note = 'Initial'")
        conn.commit()
        print("Deletion Complete.")
        
        # Verify
        after_count = cursor.execute("SELECT count(*) FROM transaction_log WHERE note LIKE '%기초자산%' OR note = 'Initial'").fetchone()[0]
        print(f"Remaining records: {after_count}")
        
    else:
        print("No records found. Already clean?")

    conn.close()

if __name__ == "__main__":
    clean_initial_logs()
