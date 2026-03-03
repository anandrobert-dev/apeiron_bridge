
import unittest
import pandas as pd
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.core.soa_engine import SOAEngine

class TestSchemaLogic(unittest.TestCase):
    def test_schema_comparison(self):
        # 1. Setup Data
        soa_df = pd.DataFrame({'ID': [1, 2, 3, 4], 'Date': ['2023-01-01']*4, 'Amount': [100, 200, 300, 400]})
        
        ref1_df = pd.DataFrame({'ID': [1, 2, 4], 'Shipper': ['ABC', 'XYZ', 'A'], 'Amount': [100, 200, 400]})
        ref2_df = pd.DataFrame({'Tracking': [1, 3, 4], 'Shipper Name': ['ABC', 'DEF', 'B'], 'Total': [100, 300, 400]})
        
        # 2. Configure Engine
        # Ref1: Match on ID, return Shipper
        # Ref2: Match on Tracking, return Shipper Name
        
        ref_configs = [
            (ref1_df, 'ID', ['Shipper'], 'Ref1'),
            (ref2_df, 'Tracking', ['Shipper Name'], 'Ref2')
        ]
        
        schema_config = [
            {
                "name": "Shipper Logic",
                "type": "Text",
                "mappings": {
                    "/path/to/ref1.csv": "Shipper",
                    "/path/to/ref2.csv": "Shipper Name"
                }
            }
        ]
        
        path_mapping = {
            "/path/to/ref1.csv": "Ref1",
            "/path/to/ref2.csv": "Ref2"
        }
        
        engine = SOAEngine(
            soa_df=soa_df,
            soa_match_col='ID',
            date_col='Date',
            amount_col=None, # SIMULATE USER SCENARIO
            ref_configs=ref_configs,
            mode='MULTI',
            schema_config=schema_config,
            path_mapping=path_mapping
        )
        
        # 3. Run
        # Mock results dir to temp
        engine.results_dir = "/tmp"
        result_df, excel_path, discrepancy_df = engine.run()
        
        print(f"Excel saved to: {excel_path}")
        
        # 4. Verify Output
        # Load the "Normalized Comparison" sheet
        try:
            schema_df = pd.read_excel(excel_path, sheet_name='Normalized Comparison')
            print("\n--- Schema Report ---")
            print(schema_df)
            
            # Expected:
            # Row 1 (ID=1): Ref1=ABC, Ref2=ABC. Status=MATCH
            # Row 2 (ID=2): Ref1=XYZ, Ref2=NaN. Status=PARTIAL MATCH
            # Row 3 (ID=3): Ref1=NaN, Ref2=DEF. Status=PARTIAL MATCH
            # Row 4 (ID=4): Ref1=A, Ref2=B. Status=MISMATCH
            
            # Verify Status
            status_col = "Shipper Logic Status"
            key_col = "ID / Key"
            self.assertIn(status_col, schema_df.columns)
            
            # Helper
            def check_status(id_val, expected):
                row = schema_df[schema_df[key_col] == id_val]
                if row.empty:
                    self.fail(f"ID {id_val} not found in schema report")
                actual = row.iloc[0][status_col]
                self.assertEqual(actual, expected, f"ID {id_val}: expected {expected}, got {actual}")

            check_status(1, "MATCH")
            check_status(2, "PARTIAL MATCH")
            check_status(3, "PARTIAL MATCH")
            check_status(4, "MISMATCH")
            
            print("\nTest Passed!")
            
        except Exception as e:
            self.fail(f"Verification failed: {e}")

if __name__ == '__main__':
    unittest.main()
