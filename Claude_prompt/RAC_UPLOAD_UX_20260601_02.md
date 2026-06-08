# Apeiron Bridge RA&C — Upload Table UX: Review, Remove, Proceed Logic

**Context:** The upload table is working correctly — files parse, warnings show in amber,
errors show in red. Three UX gaps now need to be addressed before the workflow is usable.

Do not touch any parser code, DB schema, or SOA module.

---

## Gap 1 — No way to remove an uploaded file

**Symptom:** Once a file is added to the upload table, the user cannot remove it.
If they upload the wrong file they must close the window and start over.

**Required:** Each row in the upload table must have a remove button (trash/× icon)
in the first (checkbox) column or as a dedicated last column. Clicking it:
1. Removes that row from the table.
2. Clears that file's parsed data from memory (if already parsed).
3. Re-evaluates the "Proceed to Analysis" button state.
4. Does NOT ask for confirmation — just removes immediately. If needed, the user
   can re-add the file.

### Implementation

Add a dedicated **"×"** button cell at the end of each row:

```python
# When building a row, add a remove button in the last column
remove_btn = QPushButton("✕")
remove_btn.setFixedWidth(32)
remove_btn.setFixedHeight(28)
remove_btn.setStyleSheet("""
    QPushButton {
        background: transparent;
        color: #888;
        border: none;
        font-size: 14px;
        border-radius: 4px;
    }
    QPushButton:hover {
        color: #E24B4A;
        background: rgba(226, 75, 74, 0.12);
    }
""")
remove_btn.setToolTip("Remove this file")
remove_btn.clicked.connect(lambda _, r=row_index: self.remove_uploaded_file(r))
self.upload_table.setCellWidget(row_index, REMOVE_COL_INDEX, remove_btn)
```

```python
def remove_uploaded_file(self, row: int):
    """Remove a file row and its parsed data from the upload table."""
    file_path = self.upload_table.item(row, FILE_PATH_COL_INDEX)
    if file_path:
        path = file_path.text()
        # Clear parsed data if it exists
        self._parsed_results.pop(path, None)
    self.upload_table.removeRow(row)
    # Renumber remaining rows
    for r in range(self.upload_table.rowCount()):
        num_item = QTableWidgetItem(str(r + 1))
        num_item.setTextAlignment(Qt.AlignCenter)
        self.upload_table.setItem(r, 0, num_item)
    self._update_proceed_button_state()
```

The remove button column must be added to the table header. Suggested column order:
`# | Carrier Name | Version Flag | File Path | Status | Review | ✕`

---

## Gap 2 — No way to review parsed data before proceeding

**Symptom:** After parsing, the Status column shows "Parsed — 42 rate rows" but the
user cannot verify *which* rows were extracted, *what* the origin/destination/rate values
look like, or *whether* the column mapping was correctly inferred. They are asked to
proceed on faith.

**Required:** Each successfully parsed row must show a **"Review"** button in the Status
area (or as its own column). Clicking it opens a modal dialog showing:
1. A preview table of the first 50 parsed rate rows (origin, destination, mode, service,
   weight break, rate).
2. A count summary: "N rate rows, M clause chunks extracted."
3. Any ParseWarnings for that file (listed below the table).
4. A "Close" button. No editing — this is read-only review only.

### Implementation

**Review button — add next to the status cell:**

```python
review_btn = QPushButton("Review")
review_btn.setFixedHeight(28)
review_btn.setStyleSheet("""
    QPushButton {
        background: transparent;
        color: #F59E0B;
        border: 1px solid #F59E0B;
        border-radius: 4px;
        padding: 0 8px;
        font-size: 11px;
    }
    QPushButton:hover {
        background: rgba(245, 158, 11, 0.15);
    }
""")
review_btn.setToolTip("Preview parsed rate rows")
review_btn.clicked.connect(lambda _, p=file_path: self.show_review_dialog(p))
self.upload_table.setCellWidget(row, REVIEW_COL_INDEX, review_btn)
```

Only show the Review button when the file status starts with "Parsed". Files with
"Failed" or "Warning" status show no Review button (nothing to review).

**Review dialog:**

```python
def show_review_dialog(self, file_path: str):
    """Open a modal read-only preview of the parsed rate rows for a file."""
    result = self._parsed_results.get(file_path)
    if not result or not result.rate_rows:
        return

    dialog = QDialog(self)
    dialog.setWindowTitle(f"Parsed Data Review — {Path(file_path).name}")
    dialog.setMinimumSize(860, 520)
    layout = QVBoxLayout(dialog)

    # Summary line
    summary = QLabel(
        f"{len(result.rate_rows)} rate rows  ·  "
        f"{len(result.clause_chunks)} clause chunks  ·  "
        f"{len(result.warnings)} warnings"
    )
    summary.setStyleSheet("color: #F59E0B; font-weight: bold; padding: 4px 0;")
    layout.addWidget(summary)

    # Rate rows preview table
    columns = ["Origin", "Destination", "Mode", "Service",
               "Weight Break", "Rate", "No-Rate", "Source"]
    preview = QTableWidget()
    preview.setColumnCount(len(columns))
    preview.setHorizontalHeaderLabels(columns)
    preview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
    preview.setSelectionBehavior(QAbstractItemView.SelectRows)
    preview.setAlternatingRowColors(True)

    rows_to_show = result.rate_rows[:50]
    preview.setRowCount(len(rows_to_show))

    for r_idx, row in enumerate(rows_to_show):
        fields = row.raw_fields
        values = [
            fields.get("origin", ""),
            fields.get("destination", ""),
            fields.get("mode", ""),
            fields.get("service", ""),
            fields.get("weight_break", ""),
            fields.get("rate", ""),
            fields.get("no_rate", "False"),
            f"p{row.source_page}" if row.source_page else (row.source_sheet or ""),
        ]
        for c_idx, val in enumerate(values):
            item = QTableWidgetItem(str(val))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            preview.setItem(r_idx, c_idx, item)

    layout.addWidget(preview)

    if len(result.rate_rows) > 50:
        note = QLabel(f"Showing first 50 of {len(result.rate_rows)} rows.")
        note.setStyleSheet("color: #888; font-size: 11px; padding: 2px 0;")
        layout.addWidget(note)

    # Warnings section
    if result.warnings:
        warn_label = QLabel("Warnings:")
        warn_label.setStyleSheet("color: #F59E0B; font-weight: bold; margin-top: 8px;")
        layout.addWidget(warn_label)
        for w in result.warnings[:5]:
            wl = QLabel(f"• {w.message}")
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

## Gap 3 — "Proceed to Analysis" enabled with insufficient data

**Symptom:** The "Proceed to Analysis" button is active even when fewer than 2 files
have successfully parsed rate rows. Rate Comparison requires at least 2 carriers with
rate data to produce a meaningful comparison. Proceeding with 0 or 1 parsed file will
produce an empty or single-carrier report with no comparison possible.

**Required:** The "Proceed to Analysis" (or "Proceed to Comparison") button must:
1. Be **disabled** (greyed out) unless ≥2 files have status starting with "Parsed"
   AND each of those files has at least 1 rate row.
2. When disabled, show a tooltip explaining why:
   `"Upload and parse at least 2 carrier agreements to compare."`
3. When exactly 1 file is parsed and others have failed/warnings, show the tooltip:
   `"1 carrier parsed. Add at least 1 more carrier agreement to compare."`

### Implementation

```python
def _update_proceed_button_state(self):
    """Enable Proceed only when ≥2 files have parsed rate rows."""
    parsed_count = sum(
        1
        for path, result in self._parsed_results.items()
        if result and result.rate_rows
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
```

Call `_update_proceed_button_state()`:
- After every file finishes parsing (success or failure).
- After every file is removed via the remove button.
- On initial UI construction (button starts disabled).

---

## Storage requirement

The dialog in Gap 2 reads from `self._parsed_results`, which must be a dict mapping
`file_path → ParsedResult`. This should already exist in the worker result handler.
If it does not, add it:

```python
# In __init__:
self._parsed_results: dict[str, ParsedResult] = {}

# In handle_parser_finished (or equivalent):
self._parsed_results[file_path] = result
```

---

## Column layout after changes

The upload table will have 7 columns:

| Col | Header | Width |
|---|---|---|
| 0 | `#` | 36px fixed |
| 1 | `Carrier Name` | stretch |
| 2 | `Version Flag` | 160px |
| 3 | `File Path` | stretch |
| 4 | `Status` | 220px |
| 5 | `Review` | 80px fixed |
| 6 | `✕` | 40px fixed |

Columns 5 and 6 use `setCellWidget`. Do not set text items in those columns.

---

## Verification

1. Upload 1 file → "Proceed" button is disabled with tooltip.
2. Upload 2 files, both parse successfully → "Proceed" button becomes active.
3. Upload 2 files, 1 fails → "Proceed" button disabled, tooltip shows "1 carrier parsed."
4. Upload 3 files, click ✕ on one → that row disappears, row numbers update, button
   re-evaluates.
5. Click "Review" on a successfully parsed file → dialog opens with rate rows table,
   summary counts, and any warnings listed.
6. Review dialog is read-only — no cells are editable.
7. All 11 existing tests continue to pass.

---

## What NOT to change

- Parser code (`pdf_parser.py`, `excel_parser.py`, `docx_parser.py`, `csv_parser.py`).
- DB schema, migration scripts, agents.
- `app/soa_reconciliation/` or `app/multi_file_comparison/`.
- Any existing signal/slot connections other than the ones explicitly mentioned above.
