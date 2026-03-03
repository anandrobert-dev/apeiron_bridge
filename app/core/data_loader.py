
import pandas as pd
import os

class DataLoader:
    """
    Handles loading of data from various file formats (CSV, Excel).
    """

    @staticmethod
    def load_file(file_path: str, sheet_name: str = None, usecols: list = None) -> pd.DataFrame:
        """
        Loads a file into a Pandas DataFrame.
        Detects file type based on extension.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.csv':
            try:
                return pd.read_csv(file_path, usecols=usecols)
            except UnicodeDecodeError:
                # Fallback encoding
                return pd.read_csv(file_path, usecols=usecols, encoding='latin1')

        elif ext in ['.xlsx', '.xls']:
            if sheet_name:
                return pd.read_excel(file_path, sheet_name=sheet_name, usecols=usecols)
            else:
                # If no sheet specified, load the first one (default behavior)
                # Or we could return a dict of sheets, but for now let's stick to simple
                return pd.read_excel(file_path, usecols=usecols)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def load_file_headers(file_path: str) -> list:
        """
        Efficiently loads only the headers (columns) of a file.
        """
        if not os.path.exists(file_path):
            return []

        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == '.csv':
                # Read only the first row
                df = pd.read_csv(file_path, nrows=0)
                return df.columns.tolist()
            elif ext in ['.xlsx', '.xls']:
                # Read only headers (nrows=0 might still load some data in Excel, but it's faster)
                df = pd.read_excel(file_path, nrows=0)
                return df.columns.tolist()
        except Exception as e:
            print(f"Error loading headers for {file_path}: {e}")
            return []
        
        return []

    @staticmethod
    def get_sheet_names(file_path: str) -> list:
        """
        Returns a list of sheet names for an Excel file.
        Returns None or empty list for CSV.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.xlsx', '.xls']:
            try:
                xls = pd.ExcelFile(file_path)
                return xls.sheet_names
            except Exception:
                return []
        return []
