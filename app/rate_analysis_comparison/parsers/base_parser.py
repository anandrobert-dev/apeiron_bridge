from abc import ABC, abstractmethod
import datetime
from typing import List, Dict, Any, Optional

class CarrierRate:
    """Represents a single parsed rate entry from a carrier agreement."""
    def __init__(self,
                 origin_city: Optional[str] = None,
                 origin_state: Optional[str] = None,
                 origin_country: Optional[str] = "US",
                 origin_zip: Optional[str] = None,
                 origin_zip_range_lo: Optional[str] = None,
                 origin_zip_range_hi: Optional[str] = None,
                 dest_city: Optional[str] = None,
                 dest_state: Optional[str] = None,
                 dest_country: Optional[str] = "US",
                 dest_zip: Optional[str] = None,
                 dest_zip_range_lo: Optional[str] = None,
                 dest_zip_range_hi: Optional[str] = None,
                 service_level: Optional[str] = None,
                 weight_break_lo: Optional[float] = None,
                 weight_break_hi: Optional[float] = None,
                 pallet_break_lo: Optional[int] = None,
                 pallet_break_hi: Optional[int] = None,
                 freight_rate: Optional[float] = None,
                 freight_rate_unit: str = "per_shipment",  # per_shipment, per_cwt, per_mile, per_pallet
                 fuel_pct: Optional[float] = None,
                 fuel_flat: Optional[float] = None,
                 minimum_charge: Optional[float] = None,
                 no_rate: bool = False,
                 rate_note: Optional[str] = None,
                 notes: Optional[str] = None,
                 source_file: str = "",
                 source_locator: str = ""):
        self.origin_city = origin_city
        self.origin_state = origin_state
        self.origin_country = origin_country
        self.origin_zip = origin_zip
        self.origin_zip_range_lo = origin_zip_range_lo
        self.origin_zip_range_hi = origin_zip_range_hi
        self.dest_city = dest_city
        self.dest_state = dest_state
        self.dest_country = dest_country
        self.dest_zip = dest_zip
        self.dest_zip_range_lo = dest_zip_range_lo
        self.dest_zip_range_hi = dest_zip_range_hi
        self.service_level = service_level
        self.weight_break_lo = weight_break_lo
        self.weight_break_hi = weight_break_hi
        self.pallet_break_lo = pallet_break_lo
        self.pallet_break_hi = pallet_break_hi
        self.freight_rate = freight_rate
        self.freight_rate_unit = freight_rate_unit
        self.fuel_pct = fuel_pct
        self.fuel_flat = fuel_flat
        self.minimum_charge = minimum_charge
        self.no_rate = no_rate
        self.rate_note = rate_note
        self.notes = notes
        self.source_file = source_file
        self.source_locator = source_locator

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

class ExtractedClause:
    """Represents a single parsed contractual terms & conditions clause."""
    def __init__(self,
                 clause_type: str,
                 extracted_text: str,
                 structured_value: Optional[Dict[str, Any]] = None,
                 source_locator: Optional[str] = None):
        self.clause_type = clause_type
        self.extracted_text = extracted_text
        self.structured_value = structured_value or {}
        self.source_locator = source_locator

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

class ParsedAgreement:
    """Holds all results from parsing a carrier agreement document."""
    def __init__(self,
                 carrier_name: Optional[str] = None,
                 effective_from: Optional[datetime.date] = None,
                 effective_to: Optional[datetime.date] = None,
                 service_level: Optional[str] = None,
                 rates: Optional[List[CarrierRate]] = None,
                 clauses: Optional[List[ExtractedClause]] = None,
                 warnings: Optional[list] = None):
        self.carrier_name = carrier_name
        self.effective_from = effective_from
        self.effective_to = effective_to
        self.service_level = service_level
        self.rates = rates or []
        self.clauses = clauses or []
        self.warnings = warnings if warnings is not None else []

class BaseParser(ABC):
    """Abstract Base Class for all document parsers (Excel, PDF, Word, Scanned Images)."""
    
    @abstractmethod
    def parse(self, file_path: str, progress_callback=None) -> ParsedAgreement:
        """Parses the given file and extracts rate sheets and T&C clauses."""
        pass


from dataclasses import dataclass, field

class ParseError(Exception):
    """Raised when parsing fails critically."""
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        self.message = message
        super().__init__(f"[{file_path}] {message}")

@dataclass
class ParseWarning:
    """Represents a non-critical parsing warning."""
    file_path: str
    page_num: int
    message: str

@dataclass
class RawRateRow:
    """Represents a raw extracted rate row before canonical schema mapping."""
    source_file: str
    source_page: int
    source_sheet: Optional[str]
    raw_fields: dict[str, str] = field(default_factory=dict)

@dataclass
class RawClauseChunk:
    """Represents a raw extracted clause block/accessorial entry."""
    source_file: str
    source_page: int
    source_sheet: Optional[str]
    source_row: int
    raw_service_name: str
    raw_min: Optional[str] = None
    raw_cwt: Optional[str] = None
    raw_max: Optional[str] = None
    raw_unit: Optional[str] = None
    raw_description: str = ""

class ParsedResult(ParsedAgreement):
    """
    Subclass of ParsedAgreement that also exposes raw fields for legacy/testing interfaces.
    """
    def __init__(self,
                 source_file: str,
                 rate_rows: list[RawRateRow],
                 clause_chunks: list[RawClauseChunk],
                 warnings: list[ParseWarning],
                 sheet_notes: list[str],
                 carrier_name: Optional[str] = None,
                 effective_from: Optional[datetime.date] = None,
                 effective_to: Optional[datetime.date] = None,
                 service_level: Optional[str] = None,
                 rates: Optional[List[CarrierRate]] = None,
                 clauses: Optional[List[ExtractedClause]] = None):
        super().__init__(
            carrier_name=carrier_name,
            effective_from=effective_from,
            effective_to=effective_to,
            service_level=service_level,
            rates=rates or [],
            clauses=clauses or []
        )
        self.source_file = source_file
        self.rate_rows = rate_rows
        self.clause_chunks = clause_chunks
        self.warnings = warnings
        self.sheet_notes = sheet_notes

