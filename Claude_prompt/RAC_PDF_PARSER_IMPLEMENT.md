# Apeiron Bridge RA&C — PDF Parser Implementation Prompt

**Root cause confirmed from terminal output:**

```
- PDF parser fallback (using default Excel parser wrapper)...
ExcelParser: Starting multi-pass parsing on Apetito Rates 2026_01082026.pdf
ValueError: Excel file format cannot be determined, you must specify an engine manually.
```

`parsers/__init__.py` detects a `.pdf` file, has no working PDF parser, and falls back
to `ExcelParser`. `ExcelParser` calls `pd.ExcelFile()` on a PDF, which fails immediately.

**The PDF parser was never implemented. It must be written now.**

Do not refactor anything else. Three files need changes:
1. `parsers/pdf_parser.py` — write the full implementation.
2. `parsers/__init__.py` — fix the router to call `PdfParser`, remove the Excel fallback.
3. `workers/parsing_worker.py` — surface the error message in the `file_failed` signal.

---

## Fix 1 — `parsers/__init__.py`: wire the router correctly

**Current broken behaviour:** For `.pdf` files, the router prints
"PDF parser fallback (using default Excel parser wrapper)" and calls `ExcelParser`.

**Required:** For `.pdf` files, call `PdfParser`. Never call `ExcelParser` on a PDF.

```python
# parsers/__init__.py

from .excel_parser import ExcelParser
from .pdf_parser   import PdfParser
from .csv_parser   import CsvParser       # if it exists
from .docx_parser  import DocxParser      # if it exists

import os

def parse_document(file_path: str, progress_callback=None):
    """Route file to the correct parser based on extension."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".xlsx", ".xls", ".xlsm"):
        return ExcelParser().parse(file_path, progress_callback)
    elif ext == ".pdf":
        return PdfParser().parse(file_path, progress_callback)
    elif ext in (".csv", ".tsv"):
        return CsvParser().parse(file_path, progress_callback)
    elif ext == ".docx":
        return DocxParser().parse(file_path, progress_callback)
    else:
        from .base_parser import ParseError
        raise ParseError(file_path, f"Unsupported file type: {ext}")
```

Remove every line that says "fallback", "default Excel parser wrapper", or routes a
non-Excel file to ExcelParser. That code must not exist.

---

## Fix 2 — `parsers/pdf_parser.py`: write the real implementation

This is the main deliverable. Implement the full class below. Every method marked
IMPLEMENT must be written — do not stub, do not raise NotImplementedError.

```python
"""
PDF rate agreement parser.

Implements Mode A (pdfplumber bordered table extraction) and
Mode B (bounding-box word-cluster reconstruction for borderless tables).

All logic is deterministic. No LLM calls. No network calls.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .base_parser import (
    ParsedResult,
    ParseError,
    ParseWarning,
    RawRateRow,
    RawClauseChunk,
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
            raise ParseError(
                file_path,
                "Parser completed but found no rate rows and no clause data. "
                "The PDF may use an unsupported layout. "
                "Try exporting to Excel and re-uploading."
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

        header = [str(c).strip().lower() if c else "" for c in table[0]]

        # Detect T&C / accessorial clause table
        if self._is_clause_table(header):
            chunks = self._parse_clause_table(table, file_path, page_num)
            clause_chunks.extend(chunks)
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

        # Step 3: infer column x-boundaries from header word positions
        col_bounds = self._infer_column_bounds(header_words)

        # Step 4: check for T&C layout
        if self._is_clause_table(header_texts):
            # Build a synthetic table grid and parse as clauses
            synthetic = self._clusters_to_grid(row_clusters, col_bounds)
            chunks = self._parse_clause_table(synthetic, file_path, page_num)
            clause_chunks.extend(chunks)
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

    def _parse_clause_table(
        self, table: list[list], file_path: str, page_num: int
    ) -> list[RawClauseChunk]:
        """
        Parse a clause/accessorial table into RawClauseChunk objects.
        Expected columns: Service | Min | CWT | Max | Unit | Description
        """
        chunks: list[RawClauseChunk] = []
        if not table or len(table) < 2:
            return chunks

        header = [str(c).strip().lower() if c else "" for c in table[0]]

        # Map column names to indices (case-insensitive, partial match)
        def col_idx(keyword: str) -> int:
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

            def cell(idx: int) -> str | None:
                if idx == -1 or idx >= len(row):
                    return None
                val = row[idx]
                return str(val).strip() if val else None

            service_name = cell(svc_col)
            if not service_name:
                continue

            chunks.append(RawClauseChunk(
                source_file=file_path,
                source_page=page_num,
                source_sheet=None,
                source_row=row_idx,
                raw_service_name=service_name,
                raw_min=cell(min_col),
                raw_cwt=cell(cwt_col),
                raw_max=cell(max_col),
                raw_unit=cell(unit_col),
                raw_description=cell(desc_col) or "",
            ))

        return chunks

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _is_clause_table(self, header: list[str]) -> bool:
        """Return True if the header row looks like a T&C/accessorial table."""
        h_set = set(h.strip() for h in header)
        has_service = any("service" in h for h in h_set)
        has_desc    = any("description" in h for h in h_set)
        has_cwt     = any("cwt" in h for h in h_set)
        # A clause table has "service" + ("description" or "cwt")
        return has_service and (has_desc or has_cwt)

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
            "minimum": ["minimum", "min charge"],
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
                # Check if it's a weight-break column (numeric label or LTL/MIN)
                normalized = h_lower.replace(",", "").replace(" ", "")
                if normalized in WEIGHT_BREAK_KEYWORDS or normalized.isdigit():
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
                rows.append(sorted(current_row, key=lambda w: w["x0"]))
                current_row = [word]
                current_mid = mid

        if current_row:
            rows.append(sorted(current_row, key=lambda w: w["x0"]))

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
            texts = {w["text"].lower().replace(",", "") for w in row}
            score = sum(1 for t in texts if t in WEIGHT_BREAK_KEYWORDS)
            score += sum(1 for t in texts if any(
                kw in t for kw in ("origin", "dest", "service", "mode", "carrier")
            ))
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
```

---

## Fix 3 — `workers/parsing_worker.py`: pass the error message to the UI

The `file_failed` signal must carry the exception string so the UI can display it.

```python
# In the run() method, wherever the exception is caught:
try:
    result = parse_document(self.file_path, progress_callback=emit_progress)
    # ... handle success ...
except Exception as exc:
    logger.error("Parsing failed for %s: %s", self.file_path, exc, exc_info=True)
    # Pass the actual message, not a hardcoded string
    self.file_failed.emit(self.file_path, str(exc))
```

The `file_failed` Qt signal must be declared as `Signal(str, str)` — file path + message.
Update the signal declaration if it is currently `Signal(str)`.

---

## Fix 4 — `ui/rac_window.py`: show error detail in the Status column

In the slot that handles `file_failed`:

```python
def on_file_failed(self, file_path: str, error_msg: str):
    row = self._find_table_row(file_path)
    if row is None:
        return
    item = QTableWidgetItem("Failed")
    item.setForeground(QColor("#E24B4A"))
    # Show truncated message as tooltip — always show on hover
    item.setToolTip(error_msg)
    # Show first 70 chars in the cell as a second line
    short = (error_msg[:70] + "…") if len(error_msg) > 70 else error_msg
    item.setText(f"Failed\n{short}")
    self.upload_table.setItem(row, STATUS_COLUMN_INDEX, item)
    self.upload_table.setRowHeight(row, 52)
```

---

## Verification

After implementing all four fixes:

1. Run the app:
   ```bash
   venv/bin/python main.py
   ```

2. Upload the two PDFs again. Expected:
   - At least one file shows "Parsed — N rows" in the Status column.
   - If a file is scanned/image-only, Status shows:
     `"Failed\nScanned PDF — no selectable text. Please re-upload as text-based PDF."`
   - No `ValueError: Excel file format cannot be determined` in the terminal.
   - No "PDF parser fallback (using default Excel parser wrapper)" log line.

3. Run the test suite:
   ```bash
   venv/bin/python -m unittest discover tests
   ```
   All 8 tests must pass. If the new parser code breaks any test, fix the test
   to match the new behaviour (do not roll back the parser to make tests pass).

4. Add at least one test in `tests/test_pdf_parser.py` that:
   - Creates a minimal in-memory PDF using `reportlab` or uses a fixture file.
   - Asserts that `PdfParser().parse()` returns a `ParsedResult` with `rate_rows`
     containing at least one `RawRateRow`.

---

## What NOT to change

- `app/soa_reconciliation/` — do not touch.
- `app/multi_file_comparison/` — do not touch.
- `app/ui/welcome.py` — do not touch (bug fixes were applied in the previous pass).
- DB schema, migration scripts, agents — do not touch.
- The Excel parser — do not touch. It works for `.xlsx` files. The only change to
  `parsers/__init__.py` is fixing the routing so `.pdf` files never reach it.
