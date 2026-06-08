"""
PDF rate agreement parser.

Implements Mode A (pdfplumber bordered table extraction) and
Mode B (bounding-box word-cluster reconstruction for borderless tables).

All logic is deterministic. No LLM calls. No network calls.
"""

from __future__ import annotations

import logging
import re
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .base_parser import (
    ParsedResult,
    ParseError,
    ParseWarning,
    RawRateRow,
    RawClauseChunk,
    CarrierRate,
    ExtractedClause,
)

logger = logging.getLogger(__name__)

# Keywords that suggest a column is a weight-break (rate) column
WEIGHT_BREAK_KEYWORDS = {
    "min", "minimum", "ltl", "500", "1000", "2000", "3000", "5000",
    "10000", "20000", "30000", "cwt", "rate",
}

# Keywords that suggest a row is a T&C / accessorial clause row, not a rate row
CLAUSE_TABLE_HEADER_KEYWORDS = {"service", "description", "unit", "detention",
                                 "surcharge", "accessorial", "min", "cwt"}

# Regex for key:value metadata lines above the main table
CONTEXT_PATTERN = re.compile(
    r"(origin|carrier|from|effective|currency|mode|service)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)


class PdfParser:
    """Parse a PDF carrier rate agreement into RawRateRow and RawClauseChunk objects."""

    def parse(
        self, file_path: str, progress_callback: Optional[Callable] = None
    ) -> ParsedResult:
        """
        Entry point. Opens the PDF, iterates pages, routes each page's content
        to Mode A or Mode B, collects results.
        """
        try:
            import pdfplumber
        except ImportError:
            raise ParseError(
                file_path,
                "pdfplumber is not installed. Run: pip install pdfplumber"
            )

        rate_rows: list[RawRateRow] = []
        clause_chunks: list[RawClauseChunk] = []
        warnings: list[ParseWarning] = []
        sheet_notes: list[str] = []

        try:
            with pdfplumber.open(file_path) as pdf:
                if not pdf.pages:
                    raise ParseError(file_path, "PDF has no pages.")

                # Quick scan — detect if the whole document is image-only (scanned)
                first_words = pdf.pages[0].extract_words()
                if not first_words:
                    raise ParseError(
                        file_path,
                        "No selectable text found. This appears to be a scanned/image PDF. "
                        "Scanned PDFs require OCR (Phase 2 feature). "
                        "Please re-upload as a text-based PDF or export to Excel."
                    )

                # Context fields that persist across pages (e.g. origin defined on page 1
                # and carried forward to destination rows on subsequent pages)
                page_context: dict[str, str] = {}

                n_pages = len(pdf.pages)
                for page_idx, page in enumerate(pdf.pages):
                    if progress_callback:
                        pct = int(((page_idx + 1) / n_pages) * 100)
                        progress_callback(Path(file_path).name, pct)

                    # Extract any metadata key:value blocks at the top of this page
                    page_context.update(
                        self._extract_page_context(page, file_path, page_idx + 1)
                    )

                    # --- Mode A: bordered table detection ---
                    tables = page.extract_tables()
                    used_mode_a = False
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        # Minimum quality check: at least 3 columns, at least 1 data row
                        if not table[0] or len(table[0]) < 3:
                            continue

                        rows, chunks, warns = self._process_raw_table(
                            table, file_path, page_idx + 1, page_context
                        )
                        rate_rows.extend(rows)
                        clause_chunks.extend(chunks)
                        warnings.extend(warns)
                        used_mode_a = True

                    # --- Mode B: borderless word-cluster reconstruction (fallback) ---
                    if not used_mode_a:
                        words = page.extract_words(
                            extra_attrs=["x0", "x1", "top", "bottom"]
                        )
                        if not words:
                            continue  # blank page or image — skip silently

                        rows, chunks, warns = self._parse_borderless_page(
                            words, file_path, page_idx + 1, page_context
                        )
                        rate_rows.extend(rows)
                        clause_chunks.extend(chunks)
                        warnings.extend(warns)

        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(
                file_path,
                f"Unexpected error reading PDF: {type(exc).__name__}: {exc}"
            ) from exc

        if not rate_rows and not clause_chunks:
            # Check whether the document looks like a form submission rather than a
            # rate agreement. If so, return empty results with a warning — not an error.
            all_text = ""
            try:
                with pdfplumber.open(file_path) as pdf2:
                    for pg in pdf2.pages:
                        all_text += (pg.extract_text() or "") + "\n"
            except Exception:
                pass

            form_signals = [
                "cover page", "submission", "carrier name", "signature",
                "please complete", "please confirm", "return submission",
                "primary contact", "billing assumption",
            ]
            form_hits = sum(1 for sig in form_signals if sig in all_text.lower())

            if form_hits >= 2:
                warnings.append(ParseWarning(
                    file_path, None,
                    "This PDF appears to be a cover page or form submission, not a rate "
                    "agreement. No rate data was extracted. The actual rate tables are "
                    "likely in an associated Excel or PDF file — upload that file instead."
                ))
                return ParsedResult(
                    source_file=file_path,
                    rate_rows=[],
                    clause_chunks=[],
                    warnings=warnings,
                    sheet_notes=[all_text[:500]],
                    carrier_name=None,
                    effective_from=None,
                    effective_to=None,
                    service_level=None,
                    rates=[],
                    clauses=[]
                )

            raise ParseError(
                file_path,
                "Parser completed but found no rate rows and no clause data. "
                "The PDF may use an unsupported layout. "
                "Try exporting to Excel and re-uploading."
            )

        # 5. Map spatial rows to canonical database CarrierRate and ExtractedClause models
        carrier_name, effective_from, effective_to, service_level, rates, clauses = self._build_canonical_agreement(
            file_path, rate_rows, clause_chunks, page_context
        )

        logger.info(
            "PDF parse complete: %s — %d rate rows, %d clauses, %d warnings",
            Path(file_path).name, len(rate_rows), len(clause_chunks), len(warnings),
        )

        return ParsedResult(
            source_file=file_path,
            rate_rows=rate_rows,
            clause_chunks=clause_chunks,
            warnings=warnings,
            sheet_notes=sheet_notes,
            carrier_name=carrier_name,
            effective_from=effective_from,
            effective_to=effective_to,
            service_level=service_level,
            rates=rates,
            clauses=clauses,
        )

    # -------------------------------------------------------------------------
    # Context extraction
    # -------------------------------------------------------------------------

    def _extract_page_context(
        self, page, file_path: str, page_num: int
    ) -> dict[str, str]:
        """
        Scan the top 20% of the page for key:value metadata lines.
        Examples: "Origin: Trenton, ON", "Carrier: Apetito", "Effective: Jan 1 2026".
        Returns a dict of lower-cased key → stripped value.
        """
        context: dict[str, str] = {}
        page_height = page.height
        # Restrict to top 20% of the page
        top_crop = page.crop((0, 0, page.width, page_height * 0.20))
        text = top_crop.extract_text() or ""
        for line in text.splitlines():
            m = CONTEXT_PATTERN.match(line.strip())
            if m:
                key = m.group(1).lower().strip()
                val = m.group(2).strip()
                context[key] = val
        return context

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Transposed Destination Tables Support
    # -------------------------------------------------------------------------

    def _is_transposed_destination_table(self, header: list[str]) -> bool:
        """
        Return True if ≥2 column headers match a city+province/state pattern.
        Example: ['NO. OF SKIDS', 'WINNIPEG, MB', 'CALGARY, AB', 'VANCOUVER, BC']
        """
        city_pattern = re.compile(r'^[A-Z][A-Z\s/\.\-]+,\s*[A-Z]{2}$', re.IGNORECASE)
        return sum(1 for h in header if h and city_pattern.match(h.strip())) >= 2

    def _parse_transposed_table(
        self,
        table: list[list],
        file_path: str,
        page_num: int | None,
        context: dict[str, str],
    ) -> list[RawRateRow]:
        """
        Parse a table where destinations are column headers and rows are rate dimensions.

        Each (row, destination_col) cell becomes one RawRateRow:
          origin       = context.get("origin", "")
          destination  = column header (e.g. "WINNIPEG, MB")
          weight_break = row label (skid count, weight class, etc.)
          rate         = cell value (strip leading $ and commas)
        """
        rate_rows: list[RawRateRow] = []
        if not table or len(table) < 2:
            return rate_rows

        header = table[0]
        origin = context.get("origin", "")

        # Collect (column_index, destination_label) pairs — skip the first column (row label)
        destination_cols = [
            (i, str(header[i]).strip())
            for i in range(1, len(header))
            if header[i] and str(header[i]).strip()
        ]

        for row_idx, row in enumerate(table[1:], start=2):
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue

            row_label = str(row[0]).strip() if row[0] else ""
            if not row_label:
                continue

            for col_idx, destination in destination_cols:
                if col_idx >= len(row):
                    continue
                cell_val = str(row[col_idx]).strip() if row[col_idx] else ""
                no_rate = self._is_no_rate_value(cell_val)
                # Strip currency prefix
                cleaned = cell_val.lstrip("$").replace(",", "").strip()

                rate_rows.append(RawRateRow(
                    source_file=file_path,
                    source_page=page_num,
                    source_sheet=None,
                    raw_fields={
                        "origin":       origin,
                        "destination":  destination,
                        "mode":         context.get("mode", ""),
                        "service":      context.get("service", ""),
                        "weight_break": row_label,
                        "rate":         "" if no_rate else cleaned,
                        "no_rate":      str(no_rate),
                        "rate_note":    cell_val if no_rate else "",
                        "minimum":      "",
                    }
                ))

        return rate_rows

    # -------------------------------------------------------------------------
    # Mode A: process a table grid already extracted by pdfplumber
    # -------------------------------------------------------------------------

    def _process_raw_table(
        self,
        table: list[list[str | None]],
        file_path: str,
        page_num: int,
        context: dict[str, str],
    ) -> tuple[list[RawRateRow], list[RawClauseChunk], list[ParseWarning]]:
        """
        Given a raw table (list of rows, each row a list of cell strings),
        determine if it is a rate table or a T&C clause table, then parse it.
        """
        rate_rows: list[RawRateRow] = []
        clause_chunks: list[RawClauseChunk] = []
        warnings: list[ParseWarning] = []

        if not table or not table[0]:
            return rate_rows, clause_chunks, warnings

        header_raw = [str(c).strip() if c else "" for c in table[0]]  # preserve original case
        header     = [h.lower() for h in header_raw]

        # Detect T&C / accessorial clause table
        if self._is_clause_table(header):
            chunks = self._parse_clause_table(table, file_path, page_num)
            clause_chunks.extend(chunks)
            return rate_rows, clause_chunks, warnings

        # NEW: transposed destination-as-columns format
        if self._is_transposed_destination_table(header_raw):
            rows = self._parse_transposed_table(table, file_path, page_num, context)
            rate_rows.extend(rows)
            return rate_rows, clause_chunks, warnings

        # Detect calculator region — find the column index where "rate calc" appears
        calc_boundary = self._find_calculator_boundary(header)

        # Build header schema: lane columns + weight-break columns
        lane_cols, weight_break_cols = self._build_header_schema(
            header, calc_boundary
        )

        if not weight_break_cols:
            warnings.append(ParseWarning(
                file_path, page_num,
                f"No weight-break columns detected in table header: {header[:10]}"
            ))
            return rate_rows, clause_chunks, warnings

        # Parse data rows
        for row_idx, row in enumerate(table[1:], start=2):
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue  # skip blank rows

            # Check for footer-like rows (natural language sentences in first cell)
            first_cell = str(row[0]).strip() if row[0] else ""
            if self._is_footer_row(first_cell, row):
                continue

            raw = self._extract_raw_fields(
                row, lane_cols, weight_break_cols, calc_boundary, context
            )

            for weight_break_label, rate_value in raw["weight_breaks"].items():
                no_rate = self._is_no_rate_value(rate_value)
                rate_rows.append(RawRateRow(
                    source_file=file_path,
                    source_page=page_num,
                    source_sheet=None,
                    raw_fields={
                        "origin":       raw.get("origin", context.get("origin", "")),
                        "destination":  raw.get("destination", ""),
                        "mode":         raw.get("mode",    context.get("mode", "")),
                        "service":      raw.get("service", context.get("service", "")),
                        "weight_break": weight_break_label,
                        "rate":         "" if no_rate else str(rate_value),
                        "no_rate":      str(no_rate),
                        "rate_note":    str(rate_value) if no_rate else "",
                        "minimum":      raw.get("minimum", ""),
                    }
                ))

        return rate_rows, clause_chunks, warnings

    # -------------------------------------------------------------------------
    # Mode B: borderless page — reconstruct rows/columns from word bboxes
    # -------------------------------------------------------------------------

    def _parse_borderless_page(
        self,
        words: list[dict],
        file_path: str,
        page_num: int,
        context: dict[str, str],
    ) -> tuple[list[RawRateRow], list[RawClauseChunk], list[ParseWarning]]:
        """
        Reconstruct a table from word bounding boxes when pdfplumber finds no
        bordered table on the page.
        """
        rate_rows: list[RawRateRow] = []
        clause_chunks: list[RawClauseChunk] = []
        warnings: list[ParseWarning] = []

        if not words:
            return rate_rows, clause_chunks, warnings

        # Step 1: cluster words into rows by vertical proximity
        row_clusters = self._cluster_words_into_rows(words, tolerance=3.0)
        if len(row_clusters) < 2:
            return rate_rows, clause_chunks, warnings

        # Step 2: find the header row (contains weight-break keywords)
        header_idx = self._detect_header_row_in_clusters(row_clusters)
        if header_idx is None:
            warnings.append(ParseWarning(
                file_path, page_num,
                "Mode B: could not detect a header row — manual column mapping needed."
            ))
            return rate_rows, clause_chunks, warnings

        header_words = row_clusters[header_idx]
        header_texts = [w["text"].lower() for w in header_words]
        header_texts_raw = [w["text"] for w in header_words]

        # Step 3: infer column x-boundaries from header word positions
        col_bounds = self._infer_column_bounds(header_words)

        # Step 4: check for T&C layout
        if self._is_clause_table(header_texts):
            # Build a synthetic table grid and parse as clauses
            synthetic = self._clusters_to_grid(row_clusters, col_bounds)
            chunks = self._parse_clause_table(synthetic, file_path, page_num)
            clause_chunks.extend(chunks)
            return rate_rows, clause_chunks, warnings

        # NEW: check for transposed destination table layout
        if self._is_transposed_destination_table(header_texts_raw):
            synthetic = self._clusters_to_grid(row_clusters, col_bounds)
            rows = self._parse_transposed_table(synthetic, file_path, page_num, context)
            rate_rows.extend(rows)
            return rate_rows, clause_chunks, warnings

        calc_boundary = self._find_calculator_boundary(header_texts)
        lane_cols, weight_break_cols = self._build_header_schema(
            header_texts, calc_boundary
        )

        if not weight_break_cols:
            warnings.append(ParseWarning(
                file_path, page_num,
                f"Mode B: no weight-break columns in inferred header: {header_texts}"
            ))
            return rate_rows, clause_chunks, warnings

        # Step 5: extract context from rows above the header (origin carry-down)
        for row in row_clusters[:header_idx]:
            text = " ".join(w["text"] for w in row)
            m = CONTEXT_PATTERN.match(text.strip())
            if m:
                context[m.group(1).lower()] = m.group(2).strip()

        # Step 6: assign data rows
        for row_cluster in row_clusters[header_idx + 1:]:
            row_text = " ".join(w["text"] for w in row_cluster)
            if self._is_footer_row(row_text, []):
                continue

            assigned = self._assign_words_to_columns(row_cluster, col_bounds)
            raw = self._extract_raw_fields(
                assigned, lane_cols, weight_break_cols, calc_boundary, context
            )

            for wb_label, rate_value in raw["weight_breaks"].items():
                no_rate = self._is_no_rate_value(rate_value)
                rate_rows.append(RawRateRow(
                    source_file=file_path,
                    source_page=page_num,
                    source_sheet=None,
                    raw_fields={
                        "origin":       raw.get("origin", context.get("origin", "")),
                        "destination":  raw.get("destination", ""),
                        "mode":         raw.get("mode",    context.get("mode", "")),
                        "service":      raw.get("service", context.get("service", "")),
                        "weight_break": wb_label,
                        "rate":         "" if no_rate else str(rate_value),
                        "no_rate":      str(no_rate),
                        "rate_note":    str(rate_value) if no_rate else "",
                        "minimum":      raw.get("minimum", ""),
                    }
                ))

        return rate_rows, clause_chunks, warnings

    # -------------------------------------------------------------------------
    # T&C clause table parser
    # -------------------------------------------------------------------------

    def _parse_clause_table(self, table, file_path, page_num):
        chunks = []
        if not table or len(table) < 2:
            return chunks

        header = [str(c).strip().lower() if c else "" for c in table[0]]

        # Detect two-column format: clause_name | value
        # Triggered when there are <=3 columns and the first column is a T&C signal
        two_col_signals = ("terms", "condition", "service", "waiting", "detention",
                           "fuel", "payment", "liability")
        is_two_col = len(header) <= 3 and (
            not header[0] or any(sig in header[0] for sig in two_col_signals)
        )

        if is_two_col:
            for row_idx, row in enumerate(table[1:], start=2):
                if not row:
                    continue
                name  = str(row[0]).strip() if row[0] else ""
                value = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                if not name:
                    continue
                chunks.append(RawClauseChunk(
                    source_file=file_path,
                    source_page=page_num,
                    source_sheet=None,
                    source_row=row_idx,
                    raw_service_name=name,
                    raw_min=None,
                    raw_cwt=None,
                    raw_max=None,
                    raw_unit=None,
                    raw_description=value,
                ))
            return chunks

        # Multi-column format (Service | Min | CWT | Max | Unit | Description)
        def col_idx(keyword):
            for i, h in enumerate(header):
                if keyword in h:
                    return i
            return -1

        svc_col  = col_idx("service")
        min_col  = col_idx("min")
        cwt_col  = col_idx("cwt")
        max_col  = col_idx("max")
        unit_col = col_idx("unit")
        desc_col = col_idx("description")

        if svc_col == -1:
            return chunks

        for row_idx, row in enumerate(table[1:], start=2):
            if not row:
                continue
            def cell(idx):
                if idx == -1 or idx >= len(row):
                    return None
                v = row[idx]
                return str(v).strip() if v else None
            svc_name = cell(svc_col)
            if not svc_name:
                continue
            chunks.append(RawClauseChunk(
                source_file=file_path,
                source_page=page_num,
                source_sheet=None,
                source_row=row_idx,
                raw_service_name=svc_name,
                raw_min=cell(min_col),
                raw_cwt=cell(cwt_col),
                raw_max=cell(max_col),
                raw_unit=cell(unit_col),
                raw_description=cell(desc_col) or "",
            ))
        return chunks

    # -------------------------------------------------------------------------
    # Canonical mapping layer (spatial structures -> database models)
    # -------------------------------------------------------------------------

    def _build_canonical_agreement(
        self,
        file_path: str,
        rate_rows: list[RawRateRow],
        clause_chunks: list[RawClauseChunk],
        context: dict[str, str],
    ) -> tuple[Optional[str], Optional[datetime.date], Optional[datetime.date], Optional[str], list[CarrierRate], list[ExtractedClause]]:
        # 1. Carrier Name
        carrier_name = context.get("carrier")
        if not carrier_name:
            # Fallback to filename suggestion (same logic as ExcelParser!)
            basename = Path(file_path).stem
            name_match = re.match(r'^([a-zA-Z\s_]+)', basename)
            if name_match:
                carrier_name = name_match.group(1).replace("_", " ").strip()
            else:
                carrier_name = basename

        # 2. Dates
        effective_from = None
        effective_to = None
        eff_str = context.get("effective")
        if eff_str:
            # Parse dates using multiple formats
            date_pattern = re.compile(r'(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b)', re.IGNORECASE)
            matches = date_pattern.findall(eff_str)
            parsed_dates = []
            for m in matches:
                for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y", "%b %d, %Y", "%B %d, %Y"):
                    try:
                        parsed_dates.append(datetime.datetime.strptime(m.replace("  ", " "), fmt).date())
                        break
                    except ValueError:
                        continue
            if parsed_dates:
                effective_from = parsed_dates[0]
                if len(parsed_dates) > 1:
                    effective_to = parsed_dates[1]

        # 3. Service level
        service_level = context.get("service") or context.get("mode") or "LTL"

        # 4. Map Rate Rows
        rates: list[CarrierRate] = []
        
        for raw_row in rate_rows:
            raw = raw_row.raw_fields
            
            # Use _parse_location to resolve origin and destination fields
            org_zip, org_lo, org_hi, org_city, org_state = self._parse_location(raw.get("origin", ""))
            dest_zip, dest_lo, dest_hi, dest_city, dest_state = self._parse_location(raw.get("destination", ""))
            
            # Fallback to context/global fields if empty
            if not org_zip and not org_lo:
                # Try context
                ctx_org = context.get("origin") or context.get("from")
                if ctx_org:
                    org_zip, org_lo, org_hi, org_city, org_state = self._parse_location(ctx_org)

            freight_rate = self._to_float(raw.get("rate"))
            min_chg = self._to_float(raw.get("minimum"))
            
            # Determine freight rate unit (default per_shipment or per_cwt if specified in label)
            freight_unit = "per_shipment"
            wb_label = raw.get("weight_break", "").lower()
            if "cwt" in wb_label or "cwt" in service_level.lower():
                freight_unit = "per_cwt"

            # Parse weight break limits
            w_hi = None
            w_lo = None
            digit_match = re.search(r'(\d+)', wb_label)
            if digit_match:
                w_hi = float(digit_match.group(1))

            no_rt = raw.get("no_rate") == "True" or freight_rate is None or freight_rate <= 0
            
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
                service_level=raw.get("service") or service_level,
                weight_break_lo=w_lo,
                weight_break_hi=w_hi,
                freight_rate=freight_rate,
                freight_rate_unit=freight_unit,
                minimum_charge=min_chg,
                no_rate=no_rt,
                rate_note=raw.get("rate_note"),
                source_file=Path(file_path).name,
                source_locator=f"Page {raw_row.source_page}"
            ))

        # 5. Map Clauses
        clauses: list[ExtractedClause] = []
        
        # Taxonomy keywords (same as ExcelParser!)
        default_taxonomy = [
            {"code": "payment_terms", "keyword_patterns": ["payment terms", "net 30", "net 15", "net 45", "invoice due", "days to pay"]},
            {"code": "minimum_charge", "keyword_patterns": ["minimum charge", "min charge", "min.*charge", "minimums"]},
            {"code": "detention_dry", "keyword_patterns": ["detention", "delay charge", "driver detention", "free time", "demurrage"]},
            {"code": "fuel_surcharge", "keyword_patterns": ["fuel surcharge", "fsc", "fuel program", "weekly.*fuel"]},
            {"code": "liability_limit", "keyword_patterns": ["liability", "cargo claim", "per pound", "per lb", "maximum liability"]},
            {"code": "insurance", "keyword_patterns": ["insurance", "coi", "certificate of insurance", "liability insurance"]},
            {"code": "termination", "keyword_patterns": ["termination", "notice period", "cancel", "terminate"]}
        ]
        
        # Compile patterns
        keyword_patterns = {}
        for item in default_taxonomy:
            patterns = item.get("keyword_patterns", [])
            combined = "|".join([f"({pat})" for pat in patterns])
            keyword_patterns[item["code"]] = re.compile(combined, re.IGNORECASE)

        for chunk in clause_chunks:
            full_text = f"{chunk.raw_service_name or ''} {chunk.raw_description or ''}"
            
            # Run taxonomy matcher
            clause_type = "accessorial_schedule"
            for code, pat in keyword_patterns.items():
                if pat.search(full_text):
                    clause_type = code
                    break
                    
            # Extract structured value if possible
            struct_val = {}
            if clause_type == "payment_terms":
                days_match = re.search(r'net\s*(\d+)', full_text, re.IGNORECASE)
                if days_match:
                    struct_val["min_days"] = int(days_match.group(1))
            elif clause_type == "minimum_charge":
                amt_match = re.search(r'(?:min|minimum)(?:[a-zA-Z\s_]*)?\$?\s*(\d+(?:\.\d{2})?)', full_text, re.IGNORECASE)
                if amt_match:
                    struct_val["min_charge_amount"] = float(amt_match.group(1))
            elif clause_type == "detention_dry":
                hours_match = re.search(r'(\d+)\s*(?:hour|hr)s?\s*free', full_text, re.IGNORECASE)
                if hours_match:
                    struct_val["min_free_hours"] = float(hours_match.group(1))

            # Accessorials values from CWT/Min fields
            if chunk.raw_min:
                struct_val["raw_min"] = chunk.raw_min
            if chunk.raw_cwt:
                struct_val["raw_cwt"] = chunk.raw_cwt
            if chunk.raw_max:
                struct_val["raw_max"] = chunk.raw_max
            if chunk.raw_unit:
                struct_val["raw_unit"] = chunk.raw_unit

            clauses.append(ExtractedClause(
                clause_type=clause_type,
                extracted_text=full_text.strip(),
                structured_value=struct_val,
                source_locator=f"Page {chunk.source_page}, Row {chunk.source_row}"
            ))

        return carrier_name, effective_from, effective_to, service_level, rates, clauses

    def _parse_location(self, loc_str: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Parses a location string into: (canonical_zip, range_lo, range_hi, city, state)"""
        if not loc_str:
            return None, None, None, None, None
        
        loc_str = loc_str.strip()
        
        # Check for range: e.g. "K8V 1A1 - K8V 2B2" or "K8V-K8V"
        range_match = re.search(r'(\w?\d+\w?)\s*(?:-|to|\.\.\.)\s*(\w?\d+\w?)', loc_str)
        if range_match:
            lo = range_match.group(1).strip().upper()
            hi = range_match.group(2).strip().upper()
            return None, lo, hi, None, None
            
        # Single ZIP/postal
        canonical = loc_str.replace(" ", "").upper()
        # Canadian postal code e.g. K8V1A1 -> canonical[:3]
        if len(canonical) == 6 and canonical[0].isalpha() and canonical[1].isdigit():
            return canonical[:3], None, None, None, None
        
        # If it's a comma-separated city/state/zip: e.g. "Trenton, ON, K8V"
        parts = [p.strip() for p in loc_str.split(",")]
        if len(parts) >= 2:
            city = parts[0]
            state = parts[1]
            zip_val = parts[2] if len(parts) > 2 else None
            if zip_val:
                zip_val = zip_val.replace(" ", "").upper()
                if len(zip_val) == 6 and zip_val[0].isalpha() and zip_val[1].isdigit():
                    zip_val = zip_val[:3]
            return zip_val, None, None, city, state
            
        # Fallback
        if len(canonical) <= 4 and (canonical.isdigit() or (canonical[0].isalpha() and canonical[1].isdigit())):
            return canonical, None, None, None, None
            
        return None, None, None, loc_str, None

    def _to_float(self, val) -> Optional[float]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        # String conversion
        s = str(val).strip().replace("$", "").replace(",", "")
        try:
            return float(s)
        except ValueError:
            return None

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _is_clause_table(self, header: list[str]) -> bool:
        """
        Return True if the header indicates a T&C or accessorial clause table.

        Format A (accessorial schedule):  Service | Min | CWT | Max | Unit | Description
        Format B (two-column T&C list):   TERMS & CONDITIONS | (value/blank)
        Format C (clause-signal first col): first column is a known clause-type label
        """
        h = [str(x).strip().lower() for x in header if x]

        # Format A
        if any("service" in x for x in h) and any(
            kw in x for x in h for kw in ("description", "cwt", "unit")
        ):
            return True

        # Format B
        if h and ("terms" in h[0] or "condition" in h[0]):
            return True

        # Format C — first cell is a clause-type signal word
        clause_signals = (
            "payment", "liability", "insurance", "termination", "indemnif",
            "force majeure", "governing", "jurisdiction", "waiting time",
            "detention", "fuel surcharge", "minimum charge",
        )
        if h and any(sig in h[0] for sig in clause_signals):
            return True

        return False

    def _find_calculator_boundary(self, header: list[str]) -> int:
        """
        Return the column index of the first "RATE CALC" / "CALC" / "CALCULATION"
        header cell. Everything at and to the right of this index is a calculator
        output that must be excluded. Returns len(header) if not found.
        """
        for i, h in enumerate(header):
            h_lower = h.lower()
            if "rate calc" in h_lower or h_lower in ("calc", "calculation", "calculator"):
                return i
        return len(header)

    def _build_header_schema(
        self, header: list[str], calc_boundary: int
    ) -> tuple[dict[str, int], list[tuple[int, str]]]:
        """
        Classify header columns into lane columns and weight-break columns.
        Returns:
            lane_cols: dict of field_name → column_index
            weight_break_cols: list of (column_index, break_label)
        """
        lane_col_keywords = {
            "origin": ["origin", "from"],
            "destination": ["destination", "dest", "to", "city"],
            "mode": ["mode"],
            "service": ["service", "type"],
            "province": ["prov", "province", "state"],
            "minimum": ["minimum", "min charge", "min", "mc", "min_charge"],
        }

        lane_cols: dict[str, int] = {}
        weight_break_cols: list[tuple[int, str]] = []

        for i, h in enumerate(header):
            if i >= calc_boundary:
                break  # everything from here is a calculator column — stop

            h_lower = h.strip().lower()

            # Check if it's a lane column
            matched_lane = False
            for field_name, keywords in lane_col_keywords.items():
                if any(kw in h_lower for kw in keywords):
                    if field_name not in lane_cols:  # first match wins
                        lane_cols[field_name] = i
                    matched_lane = True
                    break

            if not matched_lane:
                # Check if it's a weight-break column (numeric label, keywords, or with unit suffixes)
                normalized = h_lower.replace(",", "").replace(" ", "")
                clean_num = re.sub(r'(?:lbs|lb|kg|cwt|m|c)$', '', normalized)
                if normalized in WEIGHT_BREAK_KEYWORDS or normalized.isdigit() or clean_num.isdigit():
                    weight_break_cols.append((i, h.strip()))

        return lane_cols, weight_break_cols

    def _extract_raw_fields(
        self,
        row: list,
        lane_cols: dict[str, int],
        weight_break_cols: list[tuple[int, str]],
        calc_boundary: int,
        context: dict[str, str],
    ) -> dict:
        """
        Given a data row, extract lane fields and weight-break rates.
        Returns a dict with lane field values and a 'weight_breaks' sub-dict.
        """
        def cell_str(idx: int) -> str:
            if idx >= len(row) or row[idx] is None:
                return ""
            return str(row[idx]).strip()

        result: dict = {}

        for field_name, col_idx in lane_cols.items():
            result[field_name] = cell_str(col_idx)

        # Assemble destination from city + province if both present
        if "destination" in result and "province" in result:
            city   = result["destination"]
            prov   = result["province"]
            if city and prov:
                result["destination"] = f"{city}, {prov}"

        # Inherit context fields where row is blank
        for ctx_key, ctx_val in context.items():
            if ctx_key not in result or not result[ctx_key]:
                result[ctx_key] = ctx_val

        # Weight breaks
        result["weight_breaks"] = {}
        for col_idx, break_label in weight_break_cols:
            if col_idx < calc_boundary:
                result["weight_breaks"][break_label] = cell_str(col_idx)

        return result

    def _is_no_rate_value(self, value: str) -> bool:
        """Return True if the rate cell represents a missing/on-request rate."""
        if not value:
            return True
        v = value.strip().lower()
        return v in ("", "0", "0.00", "n/a", "na", "tbd", "on request",
                     "call", "quote", "–", "-", "—")

    def _is_footer_row(self, first_cell: str, row: list) -> bool:
        """
        Return True if this row is a footer/notes row, not a data row.
        Heuristic: first cell is a sentence-like string with note keywords.
        """
        footer_keywords = (
            "rates are", "based on", "subject to", "note:", "notes:",
            "all rates", "prices are", "effective", "currency",
            "cad", "usd", "gst", "hst",
        )
        f = first_cell.lower()
        if any(kw in f for kw in footer_keywords):
            # The rest of the row should be mostly blank for a true footer
            non_blank = sum(
                1 for c in row[1:] if c is not None and str(c).strip() != ""
            )
            if non_blank <= 1:
                return True
        return False

    # -------------------------------------------------------------------------
    # Mode B helpers: row clustering and column inference
    # -------------------------------------------------------------------------

    def _merge_row_words_horizontally(self, row: list[dict], max_gap: float = 12.0) -> list[dict]:
        """
        Merge words on the same horizontal line that have a gap smaller than max_gap.
        """
        if not row:
            return []
        
        merged: list[dict] = []
        curr = dict(row[0])
        
        for next_w in row[1:]:
            gap = next_w["x0"] - curr["x1"]
            if gap <= max_gap:
                curr["x1"] = next_w["x1"]
                curr["text"] = f"{curr['text']} {next_w['text']}"
                curr["top"] = min(curr["top"], next_w["top"])
                curr["bottom"] = max(curr["bottom"], next_w["bottom"])
            else:
                merged.append(curr)
                curr = dict(next_w)
                
        merged.append(curr)
        return merged

    def _cluster_words_into_rows(
        self, words: list[dict], tolerance: float = 3.0
    ) -> list[list[dict]]:
        """
        Group words into rows based on their vertical midpoint.
        Words whose midpoints are within `tolerance` pixels are in the same row.
        """
        if not words:
            return []

        sorted_words = sorted(words, key=lambda w: (w["top"] + w["bottom"]) / 2)
        rows: list[list[dict]] = []
        current_row: list[dict] = [sorted_words[0]]
        current_mid = (sorted_words[0]["top"] + sorted_words[0]["bottom"]) / 2

        for word in sorted_words[1:]:
            mid = (word["top"] + word["bottom"]) / 2
            if abs(mid - current_mid) <= tolerance:
                current_row.append(word)
            else:
                sorted_r = sorted(current_row, key=lambda w: w["x0"])
                rows.append(self._merge_row_words_horizontally(sorted_r))
                current_row = [word]
                current_mid = mid

        if current_row:
            sorted_r = sorted(current_row, key=lambda w: w["x0"])
            rows.append(self._merge_row_words_horizontally(sorted_r))

        return rows

    def _detect_header_row_in_clusters(
        self, rows: list[list[dict]]
    ) -> int | None:
        """
        Find the row index that most looks like a column header.
        A header row contains the most weight-break or lane-keyword matches.
        """
        best_idx: int | None = None
        best_score = 0

        for i, row in enumerate(rows):
            original_texts = [w["text"] for w in row]
            texts = {w["text"].lower().replace(",", "") for w in row}
            score = sum(1 for t in texts if t in WEIGHT_BREAK_KEYWORDS)
            score += sum(1 for t in texts if any(
                kw in t for kw in ("origin", "dest", "service", "mode", "carrier")
            ))
            
            # Boost score if this looks like a transposed destination header
            if self._is_transposed_destination_table(original_texts):
                score += 5

            if score > best_score:
                best_score = score
                best_idx = i

        return best_idx if best_score >= 2 else None

    def _infer_column_bounds(
        self, header_words: list[dict]
    ) -> list[tuple[float, float, str]]:
        """
        From the header row's word positions, return a list of
        (x0, x1, label) column intervals.
        """
        return [(w["x0"], w["x1"], w["text"]) for w in header_words]

    def _assign_words_to_columns(
        self,
        row_words: list[dict],
        col_bounds: list[tuple[float, float, str]],
    ) -> list[str]:
        """
        Assign each word in a data row to the column whose x-interval best
        contains the word's horizontal midpoint.
        Returns a list of cell strings, one per column.
        """
        cells: list[list[str]] = [[] for _ in col_bounds]

        for word in row_words:
            mid_x = (word["x0"] + word["x1"]) / 2
            best_col = 0
            best_dist = float("inf")
            for i, (x0, x1, _) in enumerate(col_bounds):
                col_mid = (x0 + x1) / 2
                dist = abs(mid_x - col_mid)
                if dist < best_dist:
                    best_dist = dist
                    best_col = i
            cells[best_col].append(word["text"])

        return [" ".join(parts).strip() for parts in cells]

    def _clusters_to_grid(
        self,
        row_clusters: list[list[dict]],
        col_bounds: list[tuple[float, float, str]],
    ) -> list[list[str]]:
        """Convert row clusters to a 2D grid of strings (like a table from Mode A)."""
        header = [label for _, _, label in col_bounds]
        grid: list[list[str]] = [header]
        for row in row_clusters[1:]:
            grid.append(self._assign_words_to_columns(row, col_bounds))
        return grid
