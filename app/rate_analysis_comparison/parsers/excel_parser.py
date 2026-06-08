import os
import re
import datetime
import pandas as pd
import openpyxl
from typing import List, Dict, Any, Optional
from .base_parser import BaseParser, CarrierRate, ExtractedClause, ParsedAgreement

WEIGHT_BREAK_KEYWORDS = {
    "min", "minimum", "ltl", "500", "1000", "2000", "3000",
    "5000", "10000", "20000", "30000", "cwt", "rate",
}

LANE_COL_KEYWORDS = {
    "origin":      ["origin", "from", "origin city", "origin zip", "origin_zip", "org zip", "o zip", "o_zip", "shipper zip", "sh zip", "origin postal", "org_postal"],
    "destination": ["destination", "dest", "to", "destination city", "dest zip", "dest_zip", "dst zip", "d zip", "d_zip", "consignee zip", "cn zip", "destination postal", "dest_postal"],
    "mode":        ["mode", "service", "level", "type"],
    "service":     ["service", "type", "service level"],
    "province":    ["prov", "province", "state", "origin state", "origin_state", "org state", "org_st", "o_st", "sh state", "shipper state", "dest state", "dest_state", "dst state", "dst_st", "d_st", "cn state", "consignee state"],
}

def _cell_to_str(val) -> str:
    if val is None or pd.isna(val):
        return ""
    # Strip ".0" if it's float ending in .0 (e.g. 500.0 -> "500")
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.lower()

def _is_blank_row(row: list) -> bool:
    return all(val is None or pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "nan" for val in row)

def _find_header_row(grid: List[List[Any]]) -> Optional[int]:
    for row_idx, row in enumerate(grid):
        if _is_blank_row(row):
            continue

        score = 0
        for val in row:
            h = _cell_to_str(val)
            if not h:
                continue
            # Check weight break
            if h in WEIGHT_BREAK_KEYWORDS or h.isdigit():
                score += 1
            # Check lane column keywords
            elif any(any(kw in h for kw in keywords) for keywords in LANE_COL_KEYWORDS.values()):
                score += 1

        if score >= 3:
            return row_idx
    return None

def _build_header_schema(header_row: list) -> tuple[dict[str, int], list[tuple[int, str]]]:
    lane_cols: dict[str, int] = {}
    weight_break_cols: list[tuple[int, str]] = []
    
    for col_idx, raw_val in enumerate(header_row):
        h = _cell_to_str(raw_val)
        if not h:
            continue
            
        matched = False
        # Origin zip
        if any(w in h for w in ("origin zip", "origin_zip", "org zip", "o zip", "o_zip", "shipper zip", "sh zip", "origin postal", "org_postal")):
            lane_cols["org_zip"] = col_idx
            matched = True
        # Origin city
        elif any(w in h for w in ("origin city", "origin_city", "org city", "sh city", "shipper city")):
            lane_cols["org_city"] = col_idx
            matched = True
        # Origin state
        elif any(w in h for w in ("origin state", "origin_state", "org state", "org_st", "o_st", "sh state", "shipper state")):
            lane_cols["org_state"] = col_idx
            matched = True
        # Destination zip
        elif any(w in h for w in ("dest zip", "dest_zip", "dst zip", "d zip", "d_zip", "consignee zip", "cn zip", "destination postal", "dest_postal", "destination zip")):
            lane_cols["dest_zip"] = col_idx
            matched = True
        # Destination city
        elif any(w in h for w in ("dest city", "dest_city", "dst city", "cn city", "consignee city", "destination city")):
            lane_cols["dest_city"] = col_idx
            matched = True
        # Destination state
        elif any(w in h for w in ("dest state", "dest_state", "dst state", "dst_st", "d_st", "cn state", "consignee state", "destination prov", "destination province")):
            lane_cols["dest_state"] = col_idx
            matched = True
        # Min charge
        elif any(w in h for w in ("min charge", "min_charge", "minimum charge", "mc")):
            lane_cols["min"] = col_idx
            matched = True
        # Fuel
        elif any(w in h for w in ("fuel", "fsc", "surcharge")):
            lane_cols["fuel"] = col_idx
            matched = True
        # Service level
        elif any(w in h for w in ("service", "mode", "level", "type")):
            lane_cols["service"] = col_idx
            matched = True
        # Rate (if no weight breaks)
        elif any(w in h for w in ("rate", "charge", "cwt rate", "base rate", "freight", "linehaul", "line haul")):
            lane_cols["rate"] = col_idx
            matched = True

        if not matched:
            # Check weight break: must be in WEIGHT_BREAK_KEYWORDS or isdigit or end with 'c'/'m'
            is_wb = (h in WEIGHT_BREAK_KEYWORDS or h.isdigit() or 
                     re.match(r'^(\d+)(?:\s*(?:lbs|lb|kg|cwt))?$', h) or
                     re.match(r'^([l]?\d+)m$', h) or
                     re.match(r'^([l]?\d+)c$', h))
            if is_wb:
                # Store the original string label
                # Clean trailing .0 if present
                clean_lbl = str(raw_val).strip()
                if clean_lbl.endswith(".0"):
                    clean_lbl = clean_lbl[:-2]
                weight_break_cols.append((col_idx, clean_lbl))

    return lane_cols, weight_break_cols

class ExcelParser(BaseParser):
    """
    Highly robust, multi-pass deterministic parser for Excel carrier rate sheets and T&C files.
    """
    
    def __init__(self):
        # Compiled patterns for parsing zip ranges
        self.zip_range_pattern = re.compile(r'(\w?\d+\w?)\s*(?:-|to|\.\.\.)\s*(\w?\d+\w?)')
        # Standard keyword taxonomy compiled patterns
        self.keyword_patterns = {}

    def _compile_keywords(self, taxonomy: list):
        for item in taxonomy:
            patterns = item.get("keyword_patterns", [])
            combined = "|".join([f"({pat})" for pat in patterns])
            self.keyword_patterns[item["code"]] = re.compile(combined, re.IGNORECASE)

    def parse(self, file_path: str, progress_callback=None) -> ParsedAgreement:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        print(f"📊 ExcelParser: Starting multi-pass parsing on {os.path.basename(file_path)}...")
        if progress_callback:
            progress_callback(10, "Loading Excel workbook...")

        # Load taxonomy for clause keyword matching if available
        # We'll use a standard fallback if DB is not populated yet
        default_taxonomy = [
            {"code": "payment_terms", "keyword_patterns": ["payment terms", "net 30", "net 15", "net 45", "invoice due", "days to pay"]},
            {"code": "minimum_charge", "keyword_patterns": ["minimum charge", "min charge", "min.*charge", "minimums"]},
            {"code": "detention_dry", "keyword_patterns": ["detention", "delay charge", "driver detention", "free time", "demurrage"]},
            {"code": "fuel_surcharge", "keyword_patterns": ["fuel surcharge", "fsc", "fuel program", "weekly.*fuel"]},
            {"code": "liability_limit", "keyword_patterns": ["liability", "cargo claim", "per pound", "per lb", "maximum liability"]},
            {"code": "insurance", "keyword_patterns": ["insurance", "coi", "certificate of insurance", "liability insurance"]},
            {"code": "termination", "keyword_patterns": ["termination", "notice period", "cancel", "terminate"]}
        ]
        self._compile_keywords(default_taxonomy)

        rates: List[CarrierRate] = []
        clauses: List[ExtractedClause] = []
        
        effective_from = None
        effective_to = None
        carrier_name = None
        service_level = None

        # Pass 1: Raw structural analysis of all sheets using openpyxl & pandas
        xls = pd.ExcelFile(file_path)
        sheet_names = xls.sheet_names
        
        for s_idx, sheet_name in enumerate(sheet_names):
            pct = 15 + int((s_idx / len(sheet_names)) * 60)
            if progress_callback:
                progress_callback(pct, f"Analyzing sheet '{sheet_name}'...")

            df = xls.parse(sheet_name)
            if df.empty:
                continue

            # Pass 2: Layout detection (Identify if it's a rate grid, rate list, or text-heavy clause block)
            # A sheet is a Rate Grid if it has columns that contain zip codes and numeric columns
            total_cells = df.size
            num_cells = df.select_dtypes(include=['number']).size
            numeric_ratio = num_cells / total_cells if total_cells > 0 else 0

            # Scan first few rows to auto-detect metadata (Carrier, effective dates, etc.)
            metadata_extracted = self._extract_sheet_metadata(df)
            if metadata_extracted.get("carrier_name") and not carrier_name:
                carrier_name = metadata_extracted["carrier_name"]
            if metadata_extracted.get("effective_from") and not effective_from:
                effective_from = metadata_extracted["effective_from"]
            if metadata_extracted.get("effective_to") and not effective_to:
                effective_to = metadata_extracted["effective_to"]
            if metadata_extracted.get("service_level") and not service_level:
                service_level = metadata_extracted["service_level"]

            is_rate_sheet = self._is_rate_layout(df, numeric_ratio)
            
            if is_rate_sheet:
                print(f"  - Detected rate grid layout on sheet '{sheet_name}'")
                parsed_rates = self._parse_rates_from_sheet(df, sheet_name, file_path)
                rates.extend(parsed_rates)
            else:
                print(f"  - Detected text/clause layout on sheet '{sheet_name}'")
                parsed_clauses = self._parse_clauses_from_sheet(df, sheet_name)
                clauses.extend(parsed_clauses)

        # Suggest default carrier name from filename if not extracted
        if not carrier_name:
            basename = os.path.basename(file_path)
            # Remove extension
            basename = os.path.splitext(basename)[0]
            # Try to grab letters
            name_match = re.match(r'^([a-zA-Z\s_]+)', basename)
            if name_match:
                carrier_name = name_match.group(1).replace("_", " ").strip()
            else:
                carrier_name = basename

        if progress_callback:
            progress_callback(90, "Cleaning and validating parsed agreements...")

        print(f"📊 ExcelParser: Parsed {len(rates)} rates and {len(clauses)} clauses from {os.path.basename(file_path)}.")
        return ParsedAgreement(
            carrier_name=carrier_name,
            effective_from=effective_from,
            effective_to=effective_to,
            service_level=service_level,
            rates=rates,
            clauses=clauses
        )

    def _is_rate_layout(self, df: pd.DataFrame, numeric_ratio: float) -> bool:
        """Determines if a dataframe represents a rate structure (contains coordinate looking columns and numbers)."""
        # Look for headers containing typical rate terms
        cols_lower = [str(c).lower().strip() for c in df.columns]
        rate_words = {"rate", "charge", "cwt", "origin", "dest", "destination", "zip", "postal", "flat", "min"}
        matches = [c for c in cols_lower if any(w in c for w in rate_words)]
        
        # Or if columns look like origin/destination zips
        has_zip_cols = any("zip" in c or "postal" in c or "origin" in c or "dest" in c for c in cols_lower)
        
        return len(matches) >= 2 or (has_zip_cols and numeric_ratio > 0.1) or numeric_ratio > 0.4

    def _extract_sheet_metadata(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Scans the header blocks (first 10 rows/columns) for carrier name, effective dates, and service mode."""
        meta = {}
        text_samples = []
        
        # Scan first 8 rows and all columns
        max_rows = min(8, len(df))
        for r_idx in range(max_rows):
            for c_idx in range(len(df.columns)):
                val = str(df.iloc[r_idx, c_idx]).strip()
                if val and val != "nan" and len(val) > 2:
                    text_samples.append((val, r_idx, c_idx))

        # Check for dates: e.g. "Effective: Jan 1, 2024" or "Validity: 01/01/2024 - 12/31/2024"
        date_pattern = re.compile(r'(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b)', re.IGNORECASE)
        
        for val, r, c in text_samples:
            # 1. Effective date check
            if "effective" in val.lower() or "valid" in val.lower() or "expiry" in val.lower() or "date" in val.lower():
                matches = date_pattern.findall(val)
                if matches:
                    try:
                        parsed_dates = []
                        for m in matches:
                            # Attempt parsing
                            for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y", "%b %d, %Y", "%B %d, %Y"):
                                try:
                                    parsed_dates.append(datetime.datetime.strptime(m.replace("  ", " "), fmt).date())
                                    break
                                except ValueError:
                                    continue
                        if parsed_dates:
                            if "effective" in val.lower() or "start" in val.lower() or len(parsed_dates) == 1:
                                meta["effective_from"] = parsed_dates[0]
                            if len(parsed_dates) > 1:
                                meta["effective_from"] = parsed_dates[0]
                                meta["effective_to"] = parsed_dates[1]
                    except:
                        pass

            # 2. Carrier check: e.g. "Carrier: Bison Transport"
            if "carrier" in val.lower() or "agreement between" in val.lower() or "for:" in val.lower():
                parts = re.split(r':|between|for', val, flags=re.IGNORECASE)
                if len(parts) > 1:
                     candidate = parts[1].strip()
                     if len(candidate) > 2 and "agreement" not in candidate.lower() and "rate" not in candidate.lower():
                          meta["carrier_name"] = candidate

            # 3. Service Level check: e.g. "LTL", "FTL", "Parcel"
            for mode in ("LTL", "FTL", "Truckload", "LTL/FTL", "Parcel", "Ocean", "Air"):
                 if mode.lower() in val.lower():
                      meta["service_level"] = mode

        return meta

    def _parse_rates_from_sheet(self, df: pd.DataFrame, sheet_name: str, file_path: str) -> List[CarrierRate]:
        """Pass 3 & 4: Matches columns to standard rate schema, cleans, casts, and returns parsed CarrierRate rows."""
        rates = []
        
        # Build grid representation including dataframe columns
        grid = [list(df.columns)] + df.values.tolist()
        
        # 1. Detect header row index
        header_idx = _find_header_row(grid)
        
        if header_idx is None:
            # Fallback to original columns mapping logic if no scoring header found
            header_row = list(df.columns)
            data_rows = df.values.tolist()
            start_row_offset = 2
        else:
            header_row = grid[header_idx]
            data_rows = grid[header_idx + 1:]
            start_row_offset = header_idx + 2  # Excel is 1-indexed, and grid starts with columns (row 1)

        # 2. Map columns using the new robust _build_header_schema logic
        lane_cols, weight_break_cols = _build_header_schema(header_row)

        idx_org_zip = lane_cols.get("org_zip", -1)
        idx_org_city = lane_cols.get("org_city", -1)
        idx_org_state = lane_cols.get("org_state", -1)
        idx_dest_zip = lane_cols.get("dest_zip", -1)
        idx_dest_city = lane_cols.get("dest_city", -1)
        idx_dest_state = lane_cols.get("dest_state", -1)
        idx_rate = lane_cols.get("rate", -1)
        idx_min = lane_cols.get("min", -1)
        idx_fuel = lane_cols.get("fuel", -1)
        idx_service = lane_cols.get("service", -1)

        # Resolve origin identifier column index
        if idx_org_zip == -1:
            if idx_org_city != -1:
                idx_org_zip = idx_org_city
            elif idx_org_state != -1:
                idx_org_zip = idx_org_state

        # Resolve destination identifier column index
        if idx_dest_zip == -1:
            if idx_dest_city != -1:
                idx_dest_zip = idx_dest_city
            elif idx_dest_state != -1:
                idx_dest_zip = idx_dest_state

        # Fallback if no specific origin/destination column matched
        if idx_org_zip == -1 and idx_dest_zip == -1:
             # Find the first two non-blank indices in header_row that aren't mapped to rate or weight break
             non_blank_indices = [i for i, val in enumerate(header_row) if val is not None and str(val).strip() != ""]
             if len(non_blank_indices) >= 2:
                 idx_org_zip = non_blank_indices[0]
                 idx_dest_zip = non_blank_indices[1]
             else:
                 idx_org_zip = 0
                 idx_dest_zip = 1
             if idx_rate == -1:
                  idx_rate = min(len(header_row) - 1, 2)

        # Parse weight break values from the identified weight break columns
        weight_breaks = []  # list of (col_idx, weight_value, original_label)
        for c_idx, raw_label in weight_break_cols:
            col_str = raw_label.lower().strip()
            weight_match = re.match(r'^(\d+)(?:\s*(?:lbs|lb|kg|cwt))?$', col_str)
            if weight_match:
                try:
                    w_val = float(weight_match.group(1))
                    weight_breaks.append((c_idx, w_val, raw_label))
                except:
                    pass
            else:
                m_match = re.match(r'^([l]?\d+)m$', col_str)
                if m_match:
                     try:
                         val_part = m_match.group(1).lower().replace("l", "")
                         weight_breaks.append((c_idx, float(val_part) * 1000.0, raw_label))
                     except:
                         pass
                else:
                     c_match = re.match(r'^([l]?\d+)c$', col_str)
                     if c_match:
                          try:
                              val_part = c_match.group(1).lower().replace("l", "")
                              weight_breaks.append((c_idx, float(val_part) * 100.0, raw_label))
                          except:
                              pass
                     elif col_str in ("min", "minimum"):
                          weight_breaks.append((c_idx, 0.0, raw_label))
                     elif col_str == "ltl":
                          weight_breaks.append((c_idx, 150.0, raw_label))  # typical LTL break

        # 3. Iterate data rows and extract CarrierRates
        for r_idx, row_data in enumerate(data_rows):
            if _is_blank_row(row_data):
                continue
                
            # Skip header repeats
            org_val_str = _cell_to_str(row_data[idx_org_zip]) if idx_org_zip < len(row_data) else ""
            if org_val_str in ("origin", "origin zip", "shipper", "shipper zip", "from"):
                continue

            # Core fields
            org_zip_raw = str(row_data[idx_org_zip]).strip() if (idx_org_zip != -1 and idx_org_zip < len(row_data) and row_data[idx_org_zip] is not None) else None
            dest_zip_raw = str(row_data[idx_dest_zip]).strip() if (idx_dest_zip != -1 and idx_dest_zip < len(row_data) and row_data[idx_dest_zip] is not None) else None
            
            # Skip empty rows or title rows
            if not org_zip_raw or org_zip_raw.lower() == "nan" or not dest_zip_raw or dest_zip_raw.lower() == "nan":
                continue

            # Check ZIP ranges: e.g. "K8V 1A1 - K8V 2B2"
            org_zip, org_lo, org_hi = self._parse_zip_or_range(org_zip_raw)
            dest_zip, dest_lo, dest_hi = self._parse_zip_or_range(dest_zip_raw)

            org_city = str(row_data[idx_org_city]).strip() if (idx_org_city != -1 and idx_org_city < len(row_data) and pd.notna(row_data[idx_org_city])) else None
            org_state = str(row_data[idx_org_state]).strip() if (idx_org_state != -1 and idx_org_state < len(row_data) and pd.notna(row_data[idx_org_state])) else None
            dest_city = str(row_data[idx_dest_city]).strip() if (idx_dest_city != -1 and idx_dest_city < len(row_data) and pd.notna(row_data[idx_dest_city])) else None
            dest_state = str(row_data[idx_dest_state]).strip() if (idx_dest_state != -1 and idx_dest_state < len(row_data) and pd.notna(row_data[idx_dest_state])) else None
            
            serv_level = str(row_data[idx_service]).strip() if (idx_service != -1 and idx_service < len(row_data) and pd.notna(row_data[idx_service])) else None
            
            min_chg = self._to_float(row_data[idx_min]) if (idx_min != -1 and idx_min < len(row_data)) else None
            fuel_s = self._to_float(row_data[idx_fuel]) if (idx_fuel != -1 and idx_fuel < len(row_data)) else None

            # Determine freight rate unit: does the sheet denote CWT pricing?
            freight_unit = "per_shipment"
            sheet_title_lower = sheet_name.lower()
            if "cwt" in sheet_title_lower or "per cwt" in sheet_title_lower or any("cwt" in _cell_to_str(col) for col in header_row):
                freight_unit = "per_cwt"
            elif "per mile" in sheet_title_lower or "per_mile" in sheet_title_lower or any("mile" in _cell_to_str(col) for col in header_row):
                freight_unit = "per_mile"

            # Create rates for each weight break if present, else create a single base rate
            if weight_breaks:
                # Sort weight breaks by value
                weight_breaks.sort(key=lambda x: x[1])
                for i, (w_col_idx, w_val, w_label) in enumerate(weight_breaks):
                    if w_col_idx >= len(row_data):
                        continue
                    rate_val = self._to_float(row_data[w_col_idx])
                    
                    # Weight range lo/hi
                    w_lo = 0.0 if i == 0 else weight_breaks[i-1][1]
                    w_hi = w_val

                    if rate_val is not None:
                        rates.append(CarrierRate(
                            origin_city=org_city,
                            origin_state=org_state,
                            origin_zip=org_zip,
                            origin_zip_range_lo=org_lo,
                            origin_zip_range_hi=org_hi,
                            dest_city=dest_city,
                            dest_state=dest_state,
                            dest_zip=dest_zip,
                            dest_zip_range_lo=dest_lo,
                            dest_zip_range_hi=dest_hi,
                            service_level=serv_level,
                            weight_break_lo=w_lo,
                            weight_break_hi=w_hi,
                            freight_rate=rate_val,
                            freight_rate_unit=freight_unit,
                            minimum_charge=min_chg,
                            fuel_pct=fuel_s,
                            no_rate=rate_val <= 0,
                            source_file=os.path.basename(file_path),
                            source_locator=f"Sheet: {sheet_name}, Row: {r_idx + start_row_offset}, Col: {w_label}"
                        ))
            else:
                # Single rate column
                rate_val = self._to_float(row_data[idx_rate]) if (idx_rate != -1 and idx_rate < len(row_data)) else None
                no_rt = rate_val is None or rate_val <= 0
                
                rates.append(CarrierRate(
                    origin_city=org_city,
                    origin_state=org_state,
                    origin_zip=org_zip,
                    origin_zip_range_lo=org_lo,
                    origin_zip_range_hi=org_hi,
                    dest_city=dest_city,
                    dest_state=dest_state,
                    dest_zip=dest_zip,
                    dest_zip_range_lo=dest_lo,
                    dest_zip_range_hi=dest_hi,
                    service_level=serv_level,
                    freight_rate=rate_val,
                    freight_rate_unit=freight_unit,
                    minimum_charge=min_chg,
                    fuel_pct=fuel_s,
                    no_rate=no_rt,
                    source_file=os.path.basename(file_path),
                    source_locator=f"Sheet: {sheet_name}, Row: {r_idx + start_row_offset}"
                ))

        return rates

    def _parse_clauses_from_sheet(self, df: pd.DataFrame, sheet_name: str) -> List[ExtractedClause]:
        """Passes sheet cells, groups adjacent text blocks, and searches for contractual terms & conditions."""
        clauses = []
        
        # Combine all cell values into a single text stream for scanning, keeping track of locators
        # Scan cell by cell to keep local contexts
        for r_idx in range(len(df)):
            for c_idx in range(len(df.columns)):
                cell_val = str(df.iloc[r_idx, c_idx]).strip()
                if not cell_val or cell_val == "nan" or len(cell_val) < 10:
                    continue

                # Run taxonomy keyword matcher
                for code, pat in self.keyword_patterns.items():
                    if pat.search(cell_val):
                        # Matched a clause!
                        # Extract structured value if possible (e.g. "Net 30 days" -> 30)
                        struct_val = {}
                        if code == "payment_terms":
                            days_match = re.search(r'net\s*(\d+)', cell_val, re.IGNORECASE)
                            if days_match:
                                struct_val["min_days"] = int(days_match.group(1))
                        elif code == "minimum_charge":
                            amt_match = re.search(r'(?:min|minimum)(?:[a-zA-Z\s_]*)?\$?\s*(\d+(?:\.\d{2})?)', cell_val, re.IGNORECASE)
                            if amt_match:
                                struct_val["min_charge_amount"] = float(amt_match.group(1))
                        elif code == "detention_dry":
                            hours_match = re.search(r'(\d+)\s*(?:hour|hr)s?\s*free', cell_val, re.IGNORECASE)
                            if hours_match:
                                struct_val["min_free_hours"] = float(hours_match.group(1))

                        clauses.append(ExtractedClause(
                            clause_type=code,
                            extracted_text=cell_val,
                            structured_value=struct_val,
                            source_locator=f"Sheet: {sheet_name}, Row: {r_idx + 2}, Col: {df.columns[c_idx]}"
                        ))
        
        return clauses

    def _parse_zip_or_range(self, val_str: str):
        """Parses a postal code string into: (canonical_zip, range_lo, range_hi)"""
        val_str = val_str.strip()
        # Clean range chars
        range_match = self.zip_range_pattern.search(val_str)
        if range_match:
             lo = range_match.group(1).strip().upper()
             hi = range_match.group(2).strip().upper()
             return None, lo, hi
        
        # Single postal code
        # Clean spacing (e.g. "K8V 1A1" -> "K8V")
        canonical = val_str.replace(" ", "").upper()
        # If it's a Canadian postal code, keep first 3 digits for comparison grouping
        if len(canonical) == 6 and canonical[0].isalpha() and canonical[1].isdigit():
             return canonical[:3], None, None
        return canonical, None, None

    def _to_float(self, val) -> Optional[float]:
        if pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            return float(val)
        # String conversion
        s = str(val).strip().replace("$", "").replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None
