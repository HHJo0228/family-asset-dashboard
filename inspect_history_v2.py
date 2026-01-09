import pandas as pd
from modules.data_loader import load_data
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def inspect_cells():
    data = load_data()
    df = data['history']
    
    print("Columns and their indices:")
    for i, col in enumerate(df.columns):
        print(f"{i}: {col}")
        
    print("\nSample Row (Last data row):")
    row = df.iloc[-1]
    for i in range(len(df.columns)):
        print(f"Col {i} ({df.columns[i]}): {row.iloc[i]}")

if __name__ == "__main__":
    inspect_cells()
