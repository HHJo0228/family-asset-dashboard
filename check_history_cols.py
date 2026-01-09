from modules.data_loader import load_data
try:
    data = load_data()
    if data and 'history' in data:
        print("Columns in 'history':")
        print(data['history'].columns.tolist())
        print("\nFirst 5 rows:")
        print(data['history'].head().to_string())
    else:
        print("Failed to load history data.")
except Exception as e:
    print(f"Error: {e}")
