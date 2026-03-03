import sys
import os

# Add project root explicitly
project_root = "/home/grace/dev/apps/apeiron_bridge"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pandas as pd
from app.core.soa_engine import SOAEngine

# Mock DataLoader behavior locally
def load_mock(path, usecols=None):
    data = {
        "Key": ["A", "B", "C"],
        "Value": [1, 2, 3],
        "Extra": ["x", "y", "z"]
    }
    df = pd.DataFrame(data)
    if usecols:
        # Simulate loading only selected cols
        existing = [c for c in usecols if c in df.columns]
        return df[existing]
    return df

def run_test():
    print("Testing Multi-File Execution Crash Scenario...")
    
    # Setup
    base_file = "base.xlsx"
    ref_file = "ref.xlsx"
    
    # 1. Config where Match Key is "Key", but user only selected "Value"
    config = {
        "rules": {
            ref_file: {
                "match_col": "Key",
                "return_cols": ["Value"]
            }
        },
        "master_match_col": "Key",
        "match_keys": {
             base_file: "Key",
             ref_file: "Key"
        },
        "column_config": {
            base_file: ["Value"], # Missing "Key"
            ref_file: ["Value"]   # Missing "Key"
        }
    }
    
    # Mimic MainWindow Loading Logic
    try:
        current_col_config = config.get("column_config", {})
        
        # Load Base
        base_usecols = current_col_config.get(base_file)
        # SIMULATE FIX: Ensure match key is present
        if base_usecols is not None and "Key" not in base_usecols:
            base_usecols = list(base_usecols) + ["Key"]
            
        soa_df = load_mock(base_file, usecols=base_usecols)
        print(f"Loaded Base Cols: {list(soa_df.columns)}")
        
        # Load Ref
        ref_configs = []
        path_mapping = {ref_file: "Ref1"}
        
        ref_usecols = current_col_config.get(ref_file)
        # SIMULATE FIX: Ensure match key is present
        if ref_usecols is not None and "Key" not in ref_usecols:
             ref_usecols = list(ref_usecols) + ["Key"]
             
        ref_df = load_mock(ref_file, usecols=ref_usecols)
        ref_configs.append((ref_df, "Key", ["Value"], "Ref1"))
        print(f"Loaded Ref Cols: {list(ref_df.columns)}")
        
        # Init Engine
        print("Initializing Engine...")
        engine = SOAEngine(
            soa_df=soa_df,
            soa_match_col="Key",
            date_col=None, 
            amount_col=None,
            ref_configs=ref_configs,
            mode="MULTI",
            path_mapping=path_mapping
        )
        
        print("Running Engine...")
        engine.run()
        print("✅ Finished without error (Unexpected)")
        
    except Exception as e:
        print(f"❌ Crash Detected: {e}")
        # import traceback
        # traceback.print_exc()

if __name__ == "__main__":
    run_test()
