
import pandas as pd
import os

class DataLoader:
    """
    Handles loading of data from various file formats (CSV, Excel).
    """

    @staticmethod
    def load_file(file_path: str, sheet_name: str = None) -> pd.DataFrame:
        """
        Loads a file into a Pandas DataFrame.
        Detects file type based on extension.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.csv':
            return pd.read_csv(file_path)
        elif ext in ['.xlsx', '.xls']:
            if sheet_name:
                return pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                # If no sheet specified, load the first one (default behavior)
                # Or we could return a dict of sheets, but for now let's stick to simple
                return pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def get_sheet_names(file_path: str) -> list:
        """
        Returns a list of sheet names for an Excel file.
        Returns None or empty list for CSV.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.xlsx', '.xls']:
            xls = pd.ExcelFile(file_path)
            return xls.sheet_names
        return []
