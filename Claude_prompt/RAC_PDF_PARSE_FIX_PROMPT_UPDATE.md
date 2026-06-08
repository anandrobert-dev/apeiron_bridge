# Apeiron Bridge RA&C — PDF Parsing Fix: Transposed Tables, T&C Detection, Form Documents

**Root cause confirmed from diagnostic output. Do not guess — act on what is written here.**

---

## What pdfplumber actually finds in each PDF

### File 1: `Apetito Rates 2026_01082026.pdf` (2 pages)

Page 1 has **3 tables**. The parser runs and finds them but extracts zero rows because
the table shape does not match what the header-schema builder expects.

```
Table 0 (7 rows × 2 cols):
  Header:  ['NO. OF SKIDS', 'RATE']
  Row 1:   ['1', '$269']
  → Simple skid-count → flat-rate table (local/short-haul). Valid rate data.

Table 1 (8 rows × 7 cols):
  Header:  ['NO. OF SKIDS', 'WINNIPEG, MB', 'REGINA, SK', 'SASKATOON, SK',
             'CALGARY, AB', 'EDMONTON, AB', 'VANCOUVER, BC']
  Row 1:   ['1', '$357.00', '$405.00', '$444.00', '$405.00', '$444.00', '$458.00']
  → Transposed rate table. Destinations ARE the column headers.
    Rows are skid counts. This is the main inter-city rate data.

Table 2 (12 rows × 2 cols):
  Header:  ['TERMS & CONDITIONS', None]
  Row 1:   ['Waiting time for FTL', '$75.00 per hour / LTL - 30 min free / FTL-2hrs free']
  → T&C clause table, two-column: clause name | clause value.
```

Page 2: 0 tables, plain text — general notes about currency, fuel, pallet dimensions.
Extract as `sheet_notes`. Do not fail because of it.

### File 2: `Western Lanes RFP_3PL Links.pdf` (3 pages)

Zero tables across all 3 pages. The text is a **carrier form submission**:
- Page 1: "Western Lanes Freight RFP - Cover Page Submission", "Carrier Name: 3PL Links"
- Page 2: Accessorial checklist with partially filled answers
- Page 3: Signature page

There is no rate data in this file. The actual rate data is in
`Western Freight Lanes apetito RFP 20260212.xlsx`, which already parsed correctly.
The current "Failed" status is wrong — this should be a "Warning" with a clear
explanation that the file is a form document, not a rate agreement.

---

## Fix 1 — Transposed "destination-as-columns" table format

**File:** `app/rate_analysis_comparison/parsers/pdf_parser.py`

The Apetito format is:

```
NO. OF SKIDS | WINNIPEG, MB | CALGARY, AB | VANCOUVER, BC
1            | $357.00      | $405.00     | $458.00
2            | $420.00      | $480.00     | $530.00
```

The parser currently looks for weight-break keywords (MIN, LTL, 1000, 2000...) as
column headers. "WINNIPEG, MB" matches none of those. Fix: detect city+province
column headers and parse this format as a transposed table.

### Add detection method

```python
def _is_transposed_destination_table(self, header: list[str]) -> bool:
    """
    Return True if ≥2 column headers match a city+province/state pattern.
    Example: ['NO. OF SKIDS', 'WINNIPEG, MB', 'CALGARY, AB', 'VANCOUVER, BC']
    """
    city_pattern = re.compile(r'^[A-Z][A-Z\s/\.\-]+,\s*[A-Z]{2}$', re.IGNORECASE)
    return sum(1 for h in header if h and city_pattern.match(h.strip())) >= 2
```

### Add parsing method

```python
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
```

### Wire into `_process_raw_table`

In `_process_raw_table`, insert the transposed-format check immediately after the
clause-table check and before the existing `_build_header_schema` call:

```python
header_raw = [str(c).strip() if c else "" for c in table[0]]  # preserve original case
header     = [h.lower() for h in header_raw]

if self._is_clause_table(header):
    chunks = self._parse_clause_table(table, file_path, page_num)
    return [], chunks, []

# NEW: transposed destination-as-columns format
if self._is_transposed_destination_table(header_raw):
    rows = self._parse_transposed_table(table, file_path, page_num, context)
    return rows, [], []

# Existing: standard weight-break format
calc_boundary = self._find_calculator_boundary(header)
...
```

Note: pass `header_raw` (original case) to `_is_transposed_destination_table` because
city names are uppercase ("WINNIPEG, MB") and the regex uses IGNORECASE.

---

## Fix 2 — T&C clause table detection: "TERMS & CONDITIONS" two-column format

**File:** `app/rate_analysis_comparison/parsers/pdf_parser.py`

The Apetito T&C table has header `['TERMS & CONDITIONS', None]`. The current
`_is_clause_table` checks for "service" + ("description" or "cwt"). Neither appears.

Replace `_is_clause_table` with this version that handles both formats:

```python
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
```

Update `_parse_clause_table` to handle the two-column format explicitly:

```python
def _parse_clause_table(self, table, file_path, page_num):
    chunks = []
    if not table or len(table) < 2:
        return chunks

    header = [str(c).strip().lower() if c else "" for c in table[0]]

    # Detect two-column format: clause_name | value
    # Triggered when there are ≤3 columns and the first column is a T&C signal
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
```

---

## Fix 3 — Western Lanes PDF: form document gets a Warning, not Failed

**File:** `app/rate_analysis_comparison/parsers/pdf_parser.py`

At the end of `parse()`, after the page loop, replace the existing hard failure with
a form-detection check:

```python
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
        )

    raise ParseError(
        file_path,
        "Parser completed but found no rate rows and no clause data. "
        "The PDF may use an unsupported layout. "
        "Try exporting to Excel and re-uploading."
    )
```

**File:** `app/rate_analysis_comparison/ui/rac_window.py`

In the slot or handler that receives a completed `ParsedResult`, show "Warning" status
in amber when the result has warnings but zero rate rows:

```python
if result.rate_rows:
    row_count = len(result.rate_rows)
    clause_count = len(result.clause_chunks)
    status_text = f"Parsed — {row_count} rate rows"
    if clause_count:
        status_text += f", {clause_count} clauses"
    if result.warnings:
        status_text += f"  ({len(result.warnings)} warnings)"
    # Set cell color: green/normal
elif result.warnings:
    # No rows but has warnings — form document or unsupported layout with explanation
    msg = result.warnings[0].message if result.warnings else "No data found"
    short = msg[:70] + "…" if len(msg) > 70 else msg
    status_text = f"Warning\n{short}"
    # Set cell color: amber (#F59E0B text, not red)
    item.setForeground(QColor("#F59E0B"))
else:
    status_text = "Parsed — 0 rows"
```

---

## Fix 4 — Wire the DOCX parser

**File:** `app/rate_analysis_comparison/parsers/__init__.py`

The router is missing the `.docx` case. Add it:

```python
from .docx_parser import DocxParser

def parse_document(file_path: str, progress_callback=None):
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
        raise ParseError(file_path, f"Unsupported file type: {ext}")
```

If `docx_parser.py` is a stub that raises `NotImplementedError`, implement it properly.
The DOCX parser should convert each `doc.tables[i]` to a row/column grid and then
delegate to `PdfParser`'s table-processing methods
(`_is_clause_table`, `_is_transposed_destination_table`, `_process_raw_table`),
since those methods handle all three table shapes regardless of source format.

---

## Expected results after these fixes

| File | Expected Status |
|---|---|
| `Apetito Rates 2026_01082026.pdf` | `Parsed — N rate rows, M clauses` |
| `Western Lanes RFP_3PL Links.pdf` | `Warning — This PDF appears to be a cover page...` (amber) |
| `Western Freight Lanes apetito RFP 20260212.xlsx` | `Parsed — 172 rate rows, 4 clauses` (unchanged) |
| `Western_Lanes_RFP_20260212.docx` | Parsed or Warning (depending on content) |
| `Trenton, ON to Western Canada LTL Apetito Rates.xlsx` | `Parsed — 36 rate rows` (unchanged) |

---

## Add one test for the transposed table format

In `tests/test_pdf_parser.py`, add:

```python
def test_transposed_destination_table(self):
    """PdfParser detects and correctly unpivots a destination-as-columns table."""
    import io
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    data = [
        ["NO. OF SKIDS", "WINNIPEG, MB", "CALGARY, AB", "VANCOUVER, BC"],
        ["1", "$357.00", "$405.00", "$458.00"],
        ["2", "$420.00", "$480.00", "$530.00"],
    ]
    doc.build([Table(data)])
    buf.seek(0)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(buf.read())
        tmp_path = f.name

    try:
        result = PdfParser().parse(tmp_path)
        # 3 destinations × 2 skid rows = 6 rate rows
        self.assertEqual(len(result.rate_rows), 6)
        destinations = {r.raw_fields["destination"] for r in result.rate_rows}
        self.assertIn("WINNIPEG, MB", destinations)
        self.assertIn("CALGARY, AB", destinations)
        self.assertIn("VANCOUVER, BC", destinations)
        skid_counts = {r.raw_fields["weight_break"] for r in result.rate_rows}
        self.assertIn("1", skid_counts)
        self.assertIn("2", skid_counts)
    finally:
        os.unlink(tmp_path)
```

---

## Verification

```bash
venv/bin/python -m unittest discover tests
```

All tests pass. Upload the five files again and confirm the Status column matches
the expected table above. No red "Failed" for the Western Lanes cover PDF.

---

## What NOT to change

- `app/soa_reconciliation/` — do not touch.
- `app/multi_file_comparison/` — do not touch.
- The Excel parser — it is working correctly. Do not touch it.
- DB schema and migration scripts.
