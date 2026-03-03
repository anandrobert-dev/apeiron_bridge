import sys
import os
import pandas as pd
import glob

# Add project root to path
sys.path.append(os.getcwd())

from app.core.soa_engine import SOAEngine

def run_test():
    print("User Test: Verifying SOA Engine Logic...")
    
    # 1. Create Dummy Data
    soa_data = {
        "Invoice": ["INV001", "INV002", "INV003"],
        "Date": ["2023-01-01", "2023-01-02", "2023-01-03"],
        "Amount": [100.0, 200.0, 300.0]
    }
    soa_df = pd.DataFrame(soa_data)
    
    ref_data = {
        "Invoice #": ["INV001", "INV002"],
        "Total": [100.0, 150.0], # INV002 Mismatch
        "Status": ["Paid", "Pending"]
    }
    ref_df = pd.DataFrame(ref_data)
    
    # 2. Config
    ref_configs = [
        (ref_df, "Invoice #", ["Total", "Status"], "Ref1")
    ]
    
    # 3. Instantiate Engine
    engine = SOAEngine(
        soa_df=soa_df,
        soa_match_col="Invoice",
        date_col="Date",
        amount_col="Amount",
        ref_configs=ref_configs,
        mode="SOA"
    )
    
    # 4. Run
    try:
        print("Running Engine...")
        result_df, saved_path, discrepancy_df, schema_df = engine.run()
        
        print("\n--- Reconciliation Successful ---")
        print(f"Saved to: {saved_path}")
        print("\nDiscrepancy Report Head:")
        print(discrepancy_df.head() if not discrepancy_df.empty else "No Discrepancies")
        
        # Verify Results
        assert not result_df.empty, "Result DF should not be empty"
        assert saved_path and os.path.exists(saved_path), "Excel file should be created"
        
        print("\n✅ Verification Passed: No crashes, output generated.")
        
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
