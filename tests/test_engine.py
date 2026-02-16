
import unittest
import pandas as pd
import sys
import os

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.engine import MatchingEngine

class TestMatchingEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MatchingEngine()
        
        # Sample SOA (Base)
        self.soa_data = pd.DataFrame({
            "Invoice": ["INV001", "INV002", "INV003", "INV004"],
            "Amount": [100, 200, 300, 400]
        })
        self.engine.set_base_data(self.soa_data)

    def test_exact_match(self):
        # Sample Reference (Exact matches)
        ref_data = pd.DataFrame({
            "Ref_Inv": ["INV001", "INV002"],
            "Ref_State": ["Paid", "Pending"]
        })
        
        self.engine.add_reference_data("Bank", ref_data)
        self.engine.set_mapping("Bank", "Invoice", "Ref_Inv", "exact")
        
        result = self.engine.run_matching()
        
        # Expect 4 rows (same as base)
        self.assertEqual(len(result), 4)
        
        # INV001 should match
        match_row = result[result["Invoice"] == "INV001"].iloc[0]
        self.assertEqual(match_row["Bank_Ref_State"], "Paid")
        
        # INV003 should be NaN (unmatched)
        no_match_row = result[result["Invoice"] == "INV003"].iloc[0]
        self.assertTrue(pd.isna(no_match_row["Bank_Ref_State"]))

    def test_fuzzy_match(self):
        # Sample Reference (Close matches)
        ref_data = pd.DataFrame({
            "Ref_Inv": ["inv-001", "INV-004"], # subtle diffs
            "Ref_Note": ["Found 1", "Found 4"]
        })
        
        self.engine.add_reference_data("Ledger", ref_data)
        self.engine.set_mapping("Ledger", "Invoice", "Ref_Inv", "fuzzy")
        
        result = self.engine.run_matching()
        
        # INV001 should match "inv-001" (lowercase/hyphen handling by rapidfuzz)
        match_row = result[result["Invoice"] == "INV001"].iloc[0]
        self.assertEqual(match_row["Ledger_Ref_Note"], "Found 1")
        
        # INV004 should match "INV-004"
        match_row_4 = result[result["Invoice"] == "INV004"].iloc[0]
        self.assertEqual(match_row_4["Ledger_Ref_Note"], "Found 4")

if __name__ == "__main__":
    unittest.main()
