
import unittest
import pandas as pd
import os
import sys

# Add app to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.data_loader import DataLoader

class TestColumnConfig(unittest.TestCase):
    def setUp(self):
        # Create dummy data
        self.data = {
            'A': [1, 2, 3],
            'B': [4, 5, 6],
            'C': [7, 8, 9],
            'D': [10, 11, 12]
        }
        self.df = pd.DataFrame(self.data)
        self.csv_path = 'test_cols.csv'
        self.xlsx_path = 'test_cols.xlsx'
        
        self.df.to_csv(self.csv_path, index=False)
        self.df.to_excel(self.xlsx_path, index=False)

    def tearDown(self):
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)
        if os.path.exists(self.xlsx_path):
            os.remove(self.xlsx_path)

    def test_csv_filtering_subset(self):
        # Select only A and C
        usecols = ['A', 'C']
        df_loaded = DataLoader.load_file(self.csv_path, usecols=usecols)
        self.assertListEqual(list(df_loaded.columns), sorted(usecols) if 'B' < 'A' else usecols) # Pandas might keep order or not depending on version/method, usually keeps file order if list matches
        # Actually pandas read_csv usecols result order depends on list order? No, usually file order.
        # Let's check set equality
        self.assertSetEqual(set(df_loaded.columns), set(usecols))
        self.assertEqual(len(df_loaded.columns), 2)

    def test_excel_filtering_subset(self):
        # Select only B and D
        usecols = ['B', 'D']
        df_loaded = DataLoader.load_file(self.xlsx_path, usecols=usecols)
        self.assertSetEqual(set(df_loaded.columns), set(usecols))
        self.assertEqual(len(df_loaded.columns), 2)

    def test_none_usecols(self):
        # Select All (None)
        df_loaded = DataLoader.load_file(self.csv_path, usecols=None)
        self.assertEqual(len(df_loaded.columns), 4)

if __name__ == '__main__':
    unittest.main()
