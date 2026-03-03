
import pandas as pd
import sys
import os

# Add project root to path so we can import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.soa_engine import SOAEngine

def run_repro():
    print("--- Setting up Test Data ---")
    
    # 1. SOA Data
    soa_data = {
        'Invoice #': ['INV-001', 'INV-002', 'INV-003'],
        'Date': ['2023-01-01', '2023-01-02', '2023-01-03'],
        'Amount': [100.0, 200.0, 300.0]
    }
    soa_df = pd.DataFrame(soa_data)
    print("SOA DataFrame:")
    print(soa_df)
    
    # 2. Ref1 Data (Matches INV-001)
    ref1_data = {
        'Ref_Invoice': ['INV-001'],
        'Carrier': ['Carrier A'],
        'Status': ['Paid']
    }
    ref1_df = pd.DataFrame(ref1_data)
    print("\nRef1 DataFrame:")
    print(ref1_df)
    
    # 3. Ref2 Data (Matches INV-002)
    ref2_data = {
        'Vendor_Inv': ['INV-002'],
        'Payment_Date': ['2023-01-15'],
        'Check_No': ['CHK123']
    }
    ref2_df = pd.DataFrame(ref2_data)
    print("\nRef2 DataFrame:")
    print(ref2_df)

    # Configure Engine
    # Ref configs: (df, match_col, return_cols, ref_name)
    ref_configs = [
        (ref1_df, 'Ref_Invoice', ['Carrier', 'Status'], 'Ref1'),
        (ref2_df, 'Vendor_Inv', ['Payment_Date', 'Check_No'], 'Ref2')
    ]
    
    print("\n--- Running SOAEngine ---")
    engine = SOAEngine(soa_df, 'Invoice #', 'Date', 'Amount', ref_configs)
    
    # Run
    result_df, saved_path, discrepancy_df = engine.run()
    
    print("\n--- Result DataFrame Columns ---")
    print(result_df.columns.tolist())
    
    print("\n--- Result DataFrame Content ---")
    print(result_df.to_string())
    
    # Verification
    expected_cols = [
        'Ref1_Carrier', 'Ref1_Status', 
        'Ref2_Payment_Date', 'Ref2_Check_No'
    ]
    
    missing = [c for c in expected_cols if c not in result_df.columns]
    
    if missing:
        print(f"\n[FAIL] Missing columns: {missing}")
    else:
        print("\n[SUCCESS] All expected reference columns are present.")

if __name__ == "__main__":
    run_repro()
