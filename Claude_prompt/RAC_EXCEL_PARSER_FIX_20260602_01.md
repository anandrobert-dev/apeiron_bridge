# Apeiron Bridge RA&C — Excel Parser: Integer Headers & Blank Leading Row Fix

**Root cause confirmed by reading the actual uploaded XLSX files.**

---

## Exact file structure of the two test files

Both files have identical layout:

```
Row 1:  [None, None, None, None, None, None, None, None, None, None]   ← blank row
Row 2:  [None, 'ORIGIN CITY', 'DESTINATION CITY', 'MIN', 'LTL', 500, 1000, 2000, 5000, 10000]
Row 3:  [None, 'ETOBICOKE, ON', 'AIRDRIE,AB', 105.23, 50.64, 37.69, 30.59, 26.39, 22.93, 20.86]
Row 4:  [None, 'ETOBICOKE, ON', 'ALEXANDRIA,ON', 99.81, 38.71, 27.82, 21.12, 17.46, 13.59, 9.91]
...
```

Cell types confirmed by openpyxl:
- Col A (index 0): `None` across all rows — blank leading column, to be ignored
- Col B (index 1): `str` — origin city
- Col C (index 2): `str` — destination city
- Col D (index 3): `str` — `'MIN'` (header), `float` (data)
- Col E (index 4): `str` — `'LTL'` (header), `float` (data)
- Col F–J (index 5–9): **`int`** — `500`, `1000`, `2000`, `5000`, `10000` (headers), `float` (data)

**The weight-break column headers are Python `int` objects, not strings.**

Expected output after fix:
- `LTL_RATES_2026-06-02_old.xlsx` → **175 rate rows** (25 lanes × 7 weight breaks)
- `LTL_RATES_2026-06-02_new.xlsx` → **308 rate rows** (44 lanes × 7 weight breaks)

---

## Root cause — two bugs, same file

### Bug A — Integer headers cause keyword matching to silently fail

**File:** `app/rate_analysis_comparison/parsers/excel_parser.py`

Anywhere the parser reads a cell from the header row and calls string methods, it
must convert the value to `str` first. The failing pattern is:

```python
# WRONG — crashes or silently fails when cell value is an int like 500
cell_value.lower()
cell_value.strip()
cell_value in WEIGHT_BREAK_KEYWORDS
```

The fix — apply this normalisation to every cell read from a header row:

```python
def _cell_to_str(val) -> str:
    """Convert any cell value to a clean lowercase string for comparison."""
    if val is None:
        return ""
    return str(val).strip().lower()
```

Use `_cell_to_str(cell)` everywhere a header cell is compared against keywords,
matched against patterns, or used to build the header schema. This must be applied in:

1. The **header row detection** pass (wherever the code checks how many
   weight-break-like keywords appear in a row to decide if it is the header row).
2. The **`_build_header_schema`** method (wherever individual column header values
   are classified as lane columns vs weight-break columns).

The corrected keyword check in `_build_header_schema`:

```python
for col_idx, raw_header in enumerate(header_row_cells):
    h = _cell_to_str(raw_header)         # converts int 500 → "500", None → ""

    if not h:
        continue                          # skip blank / None columns

    # Check lane columns
    matched_lane = False
    for field_name, keywords in LANE_COL_KEYWORDS.items():
        if any(kw in h for kw in keywords):
            if field_name not in lane_cols:
                lane_cols[field_name] = col_idx
            matched_lane = True
            break

    if not matched_lane:
        # Check weight-break columns: numeric label OR known LTL keyword
        if h in WEIGHT_BREAK_KEYWORDS or h.isdigit():
            weight_break_cols.append((col_idx, str(raw_header).strip()))
            # Store the ORIGINAL value as the break label (e.g. "500", not "500.0")
```

Note: store `str(raw_header).strip()` (not the lowercased version) as the break label
so that rate rows have labels like `"500"` and `"MIN"`, not `"500"` and `"min"`.

### Bug B — Blank leading row causes header detection to scan from wrong position

**File:** `app/rate_analysis_comparison/parsers/excel_parser.py`

Row 1 is all `None`. The PASS 2 region classifier must skip fully blank rows before
looking for the header row. If it treats row 1 as a candidate, it will never find a
valid header on that row, but depending on implementation, it might stop scanning
after the first failure or misidentify row 1 as a TITLE/CONTEXT region.

Fix: in the header-row scan, skip any row where every cell is `None` or `""`:

```python
def _is_blank_row(row_cells: list) -> bool:
    """Return True if every cell in the row is None or empty string."""
    return all(c is None or str(c).strip() == "" for c in row_cells)

# In the PASS 2 loop:
for row_idx, row in enumerate(sheet_grid):
    if _is_blank_row(row):
        continue   # skip blank rows entirely — do not treat as title, header, or context
    # ... continue with normal region classification
```

---

## The complete fix in `excel_parser.py`

The two bugs are tightly coupled. Here is how the corrected PASS 2 + PASS 3 logic
should look after fixing both (pseudo-code showing the logic, not necessarily the
exact function names — match whatever structure the existing file uses):

```python
WEIGHT_BREAK_KEYWORDS = {
    "min", "minimum", "ltl", "500", "1000", "2000", "3000",
    "5000", "10000", "20000", "30000", "cwt", "rate",
}

LANE_COL_KEYWORDS = {
    "origin":      ["origin", "from", "origin city"],
    "destination": ["destination", "dest", "to", "destination city"],
    "mode":        ["mode"],
    "service":     ["service", "type", "service level"],
    "province":    ["prov", "province", "state"],
}


def _cell_to_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip().lower()


def _is_blank_row(row: list) -> bool:
    return all(val is None or str(val).strip() == "" for val in row)


def _find_header_row(grid: list[list]) -> int | None:
    """
    Scan rows top-to-bottom. Return the index of the first row that:
      - Is NOT blank
      - Contains ≥2 weight-break-like or lane-name cells
    Returns None if no header is found.
    """
    for row_idx, row in enumerate(grid):
        if _is_blank_row(row):
            continue  # skip blank rows

        score = 0
        for val in row:
            h = _cell_to_str(val)
            if h in WEIGHT_BREAK_KEYWORDS or h.isdigit():
                score += 1
            elif any(kw in h for keywords in LANE_COL_KEYWORDS.values() for kw in keywords):
                score += 1

        if score >= 3:   # enough keywords to be a header row
            return row_idx

    return None


def _build_header_schema(
    header_row: list,
) -> tuple[dict[str, int], list[tuple[int, str]]]:
    """
    Classify header columns.
    Returns:
        lane_cols:        {field_name: column_index}
        weight_break_cols: [(column_index, break_label)]
    """
    lane_cols: dict[str, int] = {}
    weight_break_cols: list[tuple[int, str]] = []

    for col_idx, raw_val in enumerate(header_row):
        h = _cell_to_str(raw_val)   # handles int, float, str, None

        if not h:
            continue  # blank column — skip

        matched_lane = False
        for field_name, keywords in LANE_COL_KEYWORDS.items():
            if any(kw in h for kw in keywords):
                if field_name not in lane_cols:
                    lane_cols[field_name] = col_idx
                matched_lane = True
                break

        if not matched_lane:
            if h in WEIGHT_BREAK_KEYWORDS or h.isdigit():
                # Store original (not lowercased) for the break label
                weight_break_cols.append((col_idx, str(raw_val).strip()))

    return lane_cols, weight_break_cols
```

---

## Do NOT change the existing multi-pass detection for other formats

The multi-pass algorithm handles complex layouts (Format A calculator columns,
Format B clause tables, Format C context carry-down). Do not remove or simplify those
passes. The fix here is targeted to two specific gaps: integer type handling and
blank-row skipping. Everything else stays unchanged.

---

## Verification

After applying the fix, run:

```bash
venv/bin/python -c "
from app.rate_analysis_comparison.parsers.excel_parser import ExcelParser

for path, expected in [
    ('/home/grace/Downloads/LTL RATES_2026-06-02_old.xlsx', 175),
    ('/home/grace/Downloads/LTL RATES_2026-06-02_new.xlsx', 308),
]:
    result = ExcelParser().parse(path)
    actual = len(result.rates)
    status = 'PASS' if actual == expected else 'FAIL'
    print(f'{status}: {path.split(\"/\")[-1]} → {actual} rows (expected {expected})')
"
```

Expected output:
```
PASS: LTL RATES_2026-06-02_old.xlsx → 175 rows (expected 175)
PASS: LTL RATES_2026-06-02_new.xlsx → 308 rows (expected 308)
```

Then run the full test suite:
```bash
venv/bin/python -m unittest discover tests
```
All tests must pass.

Also upload both files via the app UI and confirm:
- Row 1: `LTL RATES — Old / superseded → Parsed — 175 rate rows`
- Row 2: `LTL RATES — New → Parsed — 308 rate rows`
- Review button opens showing origin city, destination city, weight break, rate
- Proceed button becomes enabled (2 parsed files with rate rows)

---

## What NOT to change

- PDF parser, DOCX parser, CSV parser — do not touch.
- DB schema, agents, SOA module, Multi-File Comparison module.
- The existing multi-pass logic for Format A (calculator columns), Format B (clause
  tables), Format C (context carry-down) — preserve all of it.
