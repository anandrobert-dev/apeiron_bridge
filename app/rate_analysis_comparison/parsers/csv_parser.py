import os
import tempfile
import pandas as pd
from typing import Callable, Optional
from .base_parser import BaseParser, ParsedResult
from .excel_parser import ExcelParser

class CsvParser(BaseParser):
    """
    Parser for CSV/TSV carrier rate agreements.
    Converts CSV/TSV to a temporary Excel file and delegates parsing to ExcelParser.
    """

    def parse(self, file_path: str, progress_callback: Optional[Callable[[int, str], None]] = None) -> ParsedResult:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Determine delimiter
        ext = os.path.splitext(file_path)[1].lower()
        sep = "\t" if ext == ".tsv" else ","

        # Read CSV/TSV using pandas
        df = pd.read_csv(file_path, sep=sep, header=None)

        # Write to a temporary .xlsx file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with pd.ExcelWriter(tmp_path, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Sheet1", index=False, header=False)

            # Delegate to ExcelParser
            excel_parser = ExcelParser()
            result = excel_parser.parse(tmp_path, progress_callback)
            
            # Update the source file reference in results
            result.source_file = file_path
            for r in result.rates:
                r.source_file = os.path.basename(file_path)
            
            return result
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
