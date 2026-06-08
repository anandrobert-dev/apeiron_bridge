import os
from .base_parser import BaseParser, CarrierRate, ExtractedClause, ParsedAgreement, ParseError
from .excel_parser import ExcelParser
from .pdf_parser import PdfParser
from .docx_parser import DocxParser
from .csv_parser import CsvParser

def parse_document(file_path: str, progress_callback=None) -> ParsedAgreement:
    """
    Unified entry point for parsing carrier agreement documents.
    Detects file types and delegates to the appropriate specialized parser.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in (".xlsx", ".xls", ".xlsm"):
        parser = ExcelParser()
    elif ext == ".pdf":
        parser = PdfParser()
    elif ext in (".csv", ".tsv"):
        parser = CsvParser()
    elif ext == ".docx":
        parser = DocxParser()
    else:
        raise ParseError(file_path, f"Unsupported file type: {ext}")

    return parser.parse(file_path, progress_callback)


