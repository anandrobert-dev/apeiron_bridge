
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

    _header_cache = {}

    @classmethod
    def load_file_headers(cls, file_path: str) -> list:
        """
        Efficiently loads only the headers (columns) of a file.
        Caches the result based on file modification time to prevent redundant slow Excel parsing.
        """
        if not os.path.exists(file_path):
            return []

        try:
            mtime = os.path.getmtime(file_path)
            if file_path in cls._header_cache:
                cached_mtime, cached_headers = cls._header_cache[file_path]
                if cached_mtime == mtime:
                    return cached_headers

            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.csv':
                df = pd.read_csv(file_path, nrows=0)
                headers = df.columns.tolist()
            elif ext in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path, nrows=0)
                headers = df.columns.tolist()
            else:
                headers = []

            if headers:
                cls._header_cache[file_path] = (mtime, headers)
            return headers
        except Exception as e:
            print(f"Error loading headers for {file_path}: {e}")
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
