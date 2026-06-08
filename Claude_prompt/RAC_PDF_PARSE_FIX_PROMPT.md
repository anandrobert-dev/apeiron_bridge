# Apeiron Bridge RA&C — PDF Parsing Failure: Investigation & Fix Prompt

**Status:** Upload screen working. Two real carrier PDFs uploaded. Both return "Failed"
status with no error detail shown to the user. This prompt covers two tasks:

1. Surface error details in the UI so the user can always see *why* a file failed.
2. Diagnose and fix the actual PDF parsing failure on real carrier documents.

Do not change anything outside the parsing layer and the upload results table.

---

## Task 1 — Show the error message in the upload table (required first)

**Current behaviour:** The Status column shows only "Failed" (red). The user has no way
to know whether the file is corrupted, whether a dependency is missing, or whether the
parser simply cannot detect the table structure.

**Required behaviour:** When a file fails, the Status cell must show:
- The word "Failed" in red as before, AND
- A short error reason on the second line, or in a tooltip on hover.

### Implementation

**File:** `app/rate_analysis_comparison/workers/parsing_worker.py`

The worker already catches exceptions per file. Wherever it sets the status to "Failed",
it must also pass the exception message string back to the UI. The Qt signal for
`file_failed` must carry the error string:

```python
# Current (likely):
self.file_failed.emit(file_path, "Failed")

# Required:
self.file_failed.emit(file_path, str(exception))   # pass the actual exception text
```

**File:** `app/rate_analysis_comparison/ui/rac_window.py`

In the slot that handles `file_failed`, update the Status column cell to show the
truncated error message as a tooltip AND as a second line of text (grey, smaller font):

```python
def on_file_failed(self, file_path: str, error_msg: str):
    # Find the row for this file_path in the table
    # Set Status cell text to "Failed"
    # Set the cell tooltip to the full error_msg
    # Optionally show the first 60 chars of error_msg as a second line in the cell
    status_item = QTableWidgetItem("Failed")
    status_item.setForeground(QColor("#E24B4A"))
    status_item.setToolTip(error_msg)          # full message on hover
    short = error_msg[:80] + "…" if len(error_msg) > 80 else error_msg
    status_item.setText(f"Failed\n{short}")
    self.upload_table.setItem(row, STATUS_COL, status_item)
    self.upload_table.setRowHeight(row, 52)    # two-line row height
```

After this change, the user will immediately see what went wrong without needing the
terminal. Do this before touching the parser.

---

## Task 2 — Diagnose and fix PDF parsing on real carrier documents

### Step 1: Read the terminal error

Before writing any code, run the app and upload the two PDF files again:

```bash
cd /home/grace/dev/app/apeiron_bridge
venv/bin/python main.py 2>&1 | tee /tmp/rac_parse_debug.txt
```

Upload the files, let them fail, then read `/tmp/rac_parse_debug.txt`. The full
traceback will tell you exactly which line in the parser is throwing and what the
exception type is. Do not guess — read the error first.

### Step 2: Common failure modes for real carrier PDFs

Based on the file names ("Apetito Rates 2026_01082026.pdf" and
"Western Lanes RFP_3PL Links.pdf"), here are the most likely causes ranked by
probability. Check them in order.

---

**Failure mode A — pdfplumber or poppler not installed / incompatible version**

```bash
venv/bin/python -c "import pdfplumber; print(pdfplumber.__version__)"
which pdfinfo   # poppler must be installed
```

If `pdfplumber` import fails, run `venv/bin/pip install pdfplumber`.
If `pdfinfo` is missing, run `sudo apt install poppler-utils`.

After installing, try opening one PDF manually to confirm it is not encrypted:

```bash
venv/bin/python -c "
import pdfplumber
with pdfplumber.open('path/to/Apetito Rates 2026_01082026.pdf') as pdf:
    print(f'Pages: {len(pdf.pages)}')
    page = pdf.pages[0]
    tables = page.extract_tables()
    print(f'Tables on page 1: {len(tables)}')
    if tables:
        print('First table preview:', tables[0][:3])
    else:
        words = page.extract_words()
        print(f'Words on page 1: {len(words)}')
        print('First 5 words:', words[:5])
"
```

This tells you immediately: does pdfplumber open the file? Does it see tables? Does it
see words (borderless table case)?

---

**Failure mode B — PDF is actually a scanned image, not text-based**

Some carrier PDFs are scans (image inside a PDF container with no selectable text).
pdfplumber returns zero words and zero tables for these.

Detection:

```python
with pdfplumber.open(path) as pdf:
    words = pdf.pages[0].extract_words()
    if len(words) == 0:
        # This is a scanned PDF — OCR required (Phase 2 feature)
        raise ParseError(file_path, "Scanned PDF detected — OCR not yet enabled. "
                         "Please provide a text-based PDF or an Excel file.")
```

If this is the cause, surface a clear message to the user and stop — do not attempt
to parse a blank page. OCR is a Phase 2 feature.

---

**Failure mode C — Text PDF but table extraction returns nothing (Mode A fails, Mode B needed)**

The PDF has text but no ruled table borders. `extract_tables()` returns an empty list
because pdfplumber's line-detection finds no borders.

The PDF parser must fall through to Mode B (bounding-box word clustering). Verify this
fallback is actually implemented and not just stubbed. Check `pdf_parser.py`:

```python
# This MUST be present and NOT stubbed out:
def _parse_mode_b(self, page) -> list[RawRateRow]:
    """Borderless table reconstruction from word bounding boxes."""
    words = page.extract_words(extra_attrs=["x0", "x1", "top", "bottom"])
    if not words:
        return []
    rows = self._cluster_words_into_rows(words, tolerance=3.0)
    header_row_idx = self._detect_header_row(rows)
    if header_row_idx is None:
        return []
    col_bounds = self._infer_column_bounds(rows[header_row_idx])
    result = []
    for row in rows[header_row_idx + 1:]:
        raw = self._assign_words_to_columns(row, col_bounds)
        result.append(self._build_raw_rate_row(raw))
    return result
```

If any of these methods are stubbed (raise `NotImplementedError` or just `return []`
unconditionally), implement them now. Refer to `PROMPT_V1_ANTIGRAVITY.md §2.3` for
the full algorithm specification.

---

**Failure mode D — Exception in the context-carry-down logic or unpivot step**

The multi-pass algorithm (described in `PROMPT_V1_ANTIGRAVITY.md §2.2`) can throw if:
- The header row detection returns `None` and downstream code doesn't guard for it
- The weight-break column list is empty and the unpivot loop crashes
- A rate cell contains an unexpected value that breaks `Decimal()` conversion

Wrap every pass individually in a try/except that logs which pass failed:

```python
try:
    header_idx = self._detect_header_row(sheet_grid)
except Exception as e:
    raise ParseError(file_path, f"Pass 3 (header detection) failed: {e}") from e
```

This makes the error message in the UI actually useful.

---

### Step 3: Minimum viable PDF parser for Phase 1

If the full Mode A + Mode B implementation is not working, implement this simplified
but correct version that handles the formats shown in the client's sample files:

```python
def parse_pdf(self, file_path: str) -> ParsedResult:
    """
    Phase 1 PDF parser.
    Mode A: pdfplumber bordered table extraction.
    Mode B: word-bounding-box row/column reconstruction for borderless tables.
    Emits ParseWarning for uncertain extractions, ParseError for hard failures.
    """
    try:
        import pdfplumber
    except ImportError:
        raise ParseError(file_path, "pdfplumber is not installed. Run: pip install pdfplumber")

    rate_rows: list[RawRateRow] = []
    clause_chunks: list[RawClauseChunk] = []
    warnings: list[ParseWarning] = []
    sheet_notes: list[str] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) == 0:
                raise ParseError(file_path, "PDF has no pages.")

            # Detect if text-based or scanned
            first_page_words = pdf.pages[0].extract_words()
            if not first_page_words:
                raise ParseError(
                    file_path,
                    "No selectable text found. This appears to be a scanned PDF. "
                    "Scanned PDFs require OCR (coming in Phase 2). "
                    "Please provide a text-based PDF or convert to Excel."
                )

            # Accumulate context carried across pages
            page_context: dict[str, str] = {}

            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract page-level context (carrier, origin, effective date)
                page_context.update(self._extract_page_context(page))

                # Try Mode A first (bordered tables)
                tables = page.extract_tables()
                if tables and any(len(t) >= 2 and len(t[0]) >= 4 for t in tables):
                    for table in tables:
                        rows, chunks, warns = self._process_table_grid(
                            table, file_path, page_num, page_context
                        )
                        rate_rows.extend(rows)
                        clause_chunks.extend(chunks)
                        warnings.extend(warns)
                else:
                    # Fall back to Mode B (borderless word clustering)
                    words = page.extract_words(extra_attrs=["x0", "x1", "top", "bottom"])
                    if not words:
                        continue
                    rows, chunks, warns = self._parse_borderless_page(
                        words, file_path, page_num, page_context
                    )
                    rate_rows.extend(rows)
                    clause_chunks.extend(chunks)
                    warnings.extend(warns)

    except ParseError:
        raise
    except Exception as e:
        raise ParseError(file_path, f"Unexpected error reading PDF: {type(e).__name__}: {e}") from e

    if not rate_rows and not clause_chunks:
        raise ParseError(
            file_path,
            "Parser completed but found no rate rows and no clause data. "
            "The PDF may use an unsupported layout. Try exporting to Excel and uploading again."
        )

    return ParsedResult(
        source_file=file_path,
        rate_rows=rate_rows,
        clause_chunks=clause_chunks,
        warnings=warnings,
        sheet_notes=sheet_notes,
    )
```

The helper methods `_extract_page_context`, `_process_table_grid`, and
`_parse_borderless_page` must be implemented following `PROMPT_V1_ANTIGRAVITY.md §2.3`.
They are not optional stubs.

---

## Task 3 — One manual diagnostic to run now (before anything else)

Run this from the project root before touching any code. It tells us exactly what
pdfplumber sees in the two failing PDFs:

```bash
venv/bin/python - << 'EOF'
import sys
import pdfplumber

files = [
    "path/to/Apetito Rates 2026_01082026.pdf",
    "path/to/Western Lanes RFP_3PL Links.pdf",
]

for f in files:
    print(f"\n{'='*60}")
    print(f"FILE: {f}")
    try:
        with pdfplumber.open(f) as pdf:
            print(f"  Pages: {len(pdf.pages)}")
            for i, page in enumerate(pdf.pages[:3]):
                tables = page.extract_tables()
                words  = page.extract_words()
                print(f"  Page {i+1}: {len(tables)} tables, {len(words)} words")
                if tables:
                    print(f"    Table[0] rows: {len(tables[0])}, cols: {len(tables[0][0])}")
                    print(f"    Header row: {tables[0][0]}")
                elif words:
                    print(f"    First 6 words: {[w['text'] for w in words[:6]]}")
                    print(f"    y-range: {min(w['top'] for w in words):.0f}"
                          f" – {max(w['bottom'] for w in words):.0f}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
EOF
```

Replace the file paths with the actual paths on the filesystem. The output of this
script must appear in the PR description or as a comment — it is the evidence base
for every parsing decision that follows.

---

## Acceptance criteria for this fix

1. "Failed" rows in the upload table show a tooltip (and optionally a second line)
   with the actual exception message when hovered.
2. At least one of the two test PDFs parses successfully and shows a non-zero row
   count in the Status column (e.g. "Parsed — 42 rows").
3. If a PDF is genuinely scanned (image-only), the Status shows:
   "Failed — Scanned PDF. Please provide a text-based PDF or Excel file."
   Not a Python traceback — a human-readable message.
4. Terminal output contains no raw unhandled tracebacks for PDF parsing. All errors
   are captured as ParseError and surfaced in the UI.
5. All 8 existing unit tests continue to pass.

---

## What NOT to change

- Do not modify `app/soa_reconciliation/` or `app/multi_file_comparison/`.
- Do not change the DB schema, migration scripts, or any agent other than
  `IngestionAgent` (if it wraps the parser) and `pdf_parser.py`.
- Do not add new UI screens or navigation flows.
- These are targeted parser fixes only.
