# Apeiron Bridge RA&C — Review Dialog Fix + Resizable Columns + Proceed Button

**Three targeted fixes. Do not refactor anything outside the areas described below.**

---

## Bug 1 — `AttributeError: 'ParsedAgreement' object has no attribute 'warnings'`

**File:** `app/rate_analysis_comparison/ui/rac_window.py`
**Line:** 728 — inside `show_review_dialog`

**Root cause:** The Excel parser (`ExcelParser`) returns a `ParsedAgreement` object.
The PDF parser (`PdfParser`) returns a `ParsedResult` object. Both are stored in
`self._parsed_results`, but `show_review_dialog` was written only for `ParsedResult`
and accesses `.warnings`, `.rate_rows`, `.clause_chunks` — none of which exist on
`ParsedAgreement`.

`ParsedAgreement` has:
- `.rates`    → list of `CarrierRate`
- `.clauses`  → list of `ExtractedClause`
- No `.warnings` attribute

`ParsedResult` has:
- `.rate_rows`     → list of `RawRateRow`
- `.clause_chunks` → list of `RawClauseChunk`
- `.warnings`      → list of `ParseWarning`

**Fix — add `warnings` to `ParsedAgreement` and write a unified accessor:**

### Step A: Add `warnings` field to `ParsedAgreement`

**File:** `app/rate_analysis_comparison/parsers/base_parser.py`

Find the `ParsedAgreement` dataclass and add a `warnings` field:

```python
@dataclass
class ParsedAgreement:
    source_file: str
    rates:    list           # list[CarrierRate]
    clauses:  list           # list[ExtractedClause]
    warnings: list = field(default_factory=list)   # ADD THIS LINE
```

If `ParsedAgreement` uses `__init__` instead of `@dataclass`, add:
```python
self.warnings = warnings if warnings is not None else []
```
in its `__init__`.

This one-line change makes both object types compatible with any code that reads
`.warnings` — no conditional checks needed in the UI.

### Step B: Rewrite `show_review_dialog` to handle both object types

**File:** `app/rate_analysis_comparison/ui/rac_window.py`

Replace the entire `show_review_dialog` method with a version that inspects the
object type and reads the right attributes:

```python
def show_review_dialog(self, file_path: str):
    """
    Open a read-only preview of the parsed data for a file.
    Handles both ParsedAgreement (Excel/DOCX/CSV) and ParsedResult (PDF) objects.
    """
    result = self._parsed_results.get(file_path)
    if not result:
        return

    # Normalise to a common interface regardless of which parser produced the result
    # ParsedAgreement has .rates / .clauses
    # ParsedResult    has .rate_rows / .clause_chunks
    if hasattr(result, "rate_rows"):
        rate_items   = result.rate_rows
        clause_items = result.clause_chunks
        rate_count   = len(rate_items)
        clause_count = len(clause_items)
        warnings     = getattr(result, "warnings", [])
        # Build display rows from RawRateRow.raw_fields
        def get_display_row(item):
            f = item.raw_fields
            return [
                f.get("origin", ""),
                f.get("destination", ""),
                f.get("mode", ""),
                f.get("service", ""),
                f.get("weight_break", ""),
                f.get("rate", ""),
                f.get("no_rate", "False"),
                f"p{item.source_page}" if item.source_page
                    else (item.source_sheet or ""),
            ]
    else:
        # ParsedAgreement path
        rate_items   = result.rates
        clause_items = result.clauses
        rate_count   = len(rate_items)
        clause_count = len(clause_items)
        warnings     = getattr(result, "warnings", [])
        # Build display rows from CarrierRate canonical fields
        def get_display_row(item):
            return [
                getattr(item, "origin_city",  "") or "",
                getattr(item, "dest_city",    "") or "",
                getattr(item, "service_level","") or "",
                "",   # mode — not always on CarrierRate
                str(getattr(item, "weight_break_lo", "") or ""),
                str(getattr(item, "freight_rate",    "") or ""),
                "False",
                getattr(item, "source_locator", "") or "",
            ]

    if not rate_items:
        # Nothing to preview — should not happen if button only shows on Parsed rows
        return

    dialog = QDialog(self)
    dialog.setWindowTitle(f"Parsed Data Review — {Path(file_path).name}")
    dialog.setMinimumSize(900, 540)
    layout = QVBoxLayout(dialog)
    layout.setSpacing(8)
    layout.setContentsMargins(12, 12, 12, 12)

    # Summary line
    summary = QLabel(
        f"{rate_count} rate rows   ·   "
        f"{clause_count} clause chunks   ·   "
        f"{len(warnings)} warnings"
    )
    summary.setStyleSheet(
        "color: #F59E0B; font-weight: bold; font-size: 13px; padding: 4px 0;"
    )
    layout.addWidget(summary)

    # Rate rows preview table
    col_headers = [
        "Origin", "Destination", "Mode / Service Level",
        "Service", "Weight Break", "Rate", "No-Rate", "Source"
    ]
    preview = QTableWidget()
    preview.setColumnCount(len(col_headers))
    preview.setHorizontalHeaderLabels(col_headers)
    preview.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    preview.horizontalHeader().setStretchLastSection(True)
    preview.verticalHeader().setVisible(False)
    preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
    preview.setSelectionBehavior(QAbstractItemView.SelectRows)
    preview.setAlternatingRowColors(True)
    preview.setShowGrid(True)

    rows_to_show = rate_items[:50]
    preview.setRowCount(len(rows_to_show))

    for r_idx, item in enumerate(rows_to_show):
        values = get_display_row(item)
        for c_idx, val in enumerate(values):
            cell = QTableWidgetItem(str(val) if val is not None else "")
            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            preview.setItem(r_idx, c_idx, cell)

    preview.resizeColumnsToContents()
    layout.addWidget(preview)

    if len(rate_items) > 50:
        note = QLabel(f"Showing first 50 of {rate_count} rows.")
        note.setStyleSheet("color: #888; font-size: 11px; padding: 2px 0;")
        layout.addWidget(note)

    # Warnings section
    if warnings:
        warn_label = QLabel(f"Warnings ({len(warnings)}):")
        warn_label.setStyleSheet(
            "color: #F59E0B; font-weight: bold; margin-top: 8px;"
        )
        layout.addWidget(warn_label)
        for w in warnings[:5]:
            msg = w.message if hasattr(w, "message") else str(w)
            wl = QLabel(f"• {msg}")
            wl.setWordWrap(True)
            wl.setStyleSheet("color: #aaa; font-size: 11px; padding: 1px 0;")
            layout.addWidget(wl)

    # Close button
    close_btn = QPushButton("Close")
    close_btn.setFixedWidth(100)
    close_btn.clicked.connect(dialog.accept)
    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_row.addWidget(close_btn)
    layout.addLayout(btn_row)

    dialog.exec()
```

---

## Bug 2 — Columns not resizable by the user

**File:** `app/rate_analysis_comparison/ui/rac_window.py`
**Symptom:** The upload table columns have fixed widths. The user cannot drag column
dividers to see truncated content (long file paths, carrier names, status text).

**Fix:** Change the resize mode from `ResizeToContents` or `Fixed` to `Interactive`
for all columns, and set `setStretchLastSection(False)` so the `✕` column stays narrow.
Keep minimum widths so columns don't collapse to zero.

In the table initialization block:

```python
header = self.upload_table.horizontalHeader()
header.setSectionResizeMode(QHeaderView.Interactive)   # all columns user-draggable
header.setStretchLastSection(False)

# Set initial widths — user can drag to adjust after this
self.upload_table.setColumnWidth(0, 36)    # #
self.upload_table.setColumnWidth(1, 200)   # Carrier Name
self.upload_table.setColumnWidth(2, 160)   # Version Flag
self.upload_table.setColumnWidth(3, 280)   # File Path
self.upload_table.setColumnWidth(4, 220)   # Status
self.upload_table.setColumnWidth(5, 80)    # Review
self.upload_table.setColumnWidth(6, 40)    # ✕

# Minimum widths prevent collapse
self.upload_table.horizontalHeader().setMinimumSectionSize(36)
```

Also set the table itself to scroll horizontally if the window is too narrow:
```python
self.upload_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
```

---

## Bug 3 — "Proceed to Analysis" still active / not gating correctly

**File:** `app/rate_analysis_comparison/ui/rac_window.py`

**Symptom:** The Proceed button is active even when fewer than 2 files have parsed
rate rows, OR clicking it produces no visible result.

### Fix A — Ensure `_update_proceed_button_state` references the correct button

Search the file for where the proceed button is created. It may be stored under
different names in different code paths (`self.btn_proceed`, `self.btn_proceed_mapping`,
`self.proceed_btn`). Find the actual attribute name and use it consistently.

```python
# Find this (whatever it is actually named in the file):
self.btn_proceed = QPushButton("Proceed to Analysis >>")

# Ensure _update_proceed_button_state uses the exact same name:
def _update_proceed_button_state(self):
    parsed_count = sum(
        1 for path, result in self._parsed_results.items()
        if result and self._get_rate_count(result) > 0
    )
    if parsed_count >= 2:
        self.btn_proceed.setEnabled(True)
        self.btn_proceed.setToolTip("")
    elif parsed_count == 1:
        self.btn_proceed.setEnabled(False)
        self.btn_proceed.setToolTip(
            "1 carrier parsed. Add at least 1 more carrier agreement to compare."
        )
    else:
        self.btn_proceed.setEnabled(False)
        self.btn_proceed.setToolTip(
            "Upload and parse at least 2 carrier agreements to compare."
        )

def _get_rate_count(self, result) -> int:
    """Return the number of rate rows/items from either ParsedResult or ParsedAgreement."""
    if hasattr(result, "rate_rows"):
        return len(result.rate_rows)
    if hasattr(result, "rates"):
        return len(result.rates)
    return 0
```

### Fix B — Call `_update_proceed_button_state` in all the right places

Make sure this method is called:
1. At the end of `__init__` (button starts disabled).
2. At the end of `handle_parser_finished` (after every successful parse).
3. At the end of `handle_parser_error` (after every failed parse).
4. At the end of `remove_uploaded_file` (after every row deletion).

If any of these call sites are missing, add them now.

### Fix C — Verify the button starts disabled

In the button creation:
```python
self.btn_proceed.setEnabled(False)
self.btn_proceed.setToolTip("Upload and parse at least 2 carrier agreements to compare.")
```

---

## Verification

1. Upload 1 XLSX file → it parses (e.g. "Parsed — 36 rate rows").
   - "Review" button appears on that row and opens the dialog without crashing.
   - Dialog shows rate rows with origin, destination, weight break, rate columns filled.
   - Proceed button is **disabled** with tooltip "1 carrier parsed..."
2. Upload a second XLSX file → both parse.
   - Proceed button becomes **enabled**.
3. Click "Review" on both files — dialog opens for both without error.
4. Click "✕" on one file → row disappears, row numbers update, Proceed becomes disabled again.
5. Upload a PDF that parses (e.g. Apetito Rates PDF, "Parsed — 42 rate rows").
   - "Review" button on that row opens dialog without `AttributeError`.
6. Run tests:
   ```bash
   venv/bin/python -m unittest discover tests
   ```
   All 11 tests pass.

---

## What NOT to change

- Parser code — do not touch `pdf_parser.py`, `excel_parser.py`, `docx_parser.py`.
- DB schema, agents, SOA module, Multi-File Comparison module.
- The `ParsedAgreement` data layout beyond adding the `warnings` field.
