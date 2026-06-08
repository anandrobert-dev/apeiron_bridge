# Apeiron Bridge — RA&C Module: Antigravity Execution Prompt
## Phase 1 Build Prompt — Version 1.0

**Hand this file to Antigravity as the primary instruction.** It is self-contained. Cross-reference
`RAC_INSTRUCTIONS_FOR_ANTIGRAVITY.md` (the living spec) for schema definitions, DB tables, and
acceptance criteria. When there is a conflict, this prompt governs what to *build first*; the spec
governs *what it must eventually do*.

---

## CRITICAL: Read the existing code before writing a single line

Before any scaffolding, generation, or file creation:

1. Clone the repo at `github.com/anandrobert-dev/apeiron_bridge` and navigate to `/home/grace/dev/app/apeiron_bridge`.
2. Read `app/soa_reconciliation/` completely. Understand the house style: how workers are structured,
   how progress signals are emitted, how errors are surfaced, how the QThread pattern is used, how
   column mapping is implemented.
3. Read `main.py` and the home screen widget to understand how new cards are registered.
4. Read `requirements.txt` to understand the existing dependency baseline.
5. **Do not touch any file in `app/soa_reconciliation/` or `app/multi_file_comparison/`.** If a
   shared utility is needed, copy and fork it into the new module. No in-place edits.
6. Then and only then, begin scaffolding `app/rate_analysis_comparison/`.

This is not a toy project. Clients make procurement and routing decisions on the output. The
software handles confidential freight pricing and carrier contracts. Every component must be
correct, tested, and production-quality from the first commit.

---

## Part 1 — What you are building

A new module `app/rate_analysis_comparison/` under the existing Apeiron Bridge PySide6 desktop app.
It replaces the "Quick CSV Match" home screen card (archive the old code to `app/_archive/quick_csv_match/`
— do not delete it).

Full requirements: `RAC_INSTRUCTIONS_FOR_ANTIGRAVITY.md`.

**Phase 1 scope (this prompt):**
- Home screen card swap (§3.1 of the spec)
- Mode selector window with three tiles (§3.2)
- Complete ingestion + parsing layer (§5 of the spec — this is the hardest part, addressed in
  detail below)
- Canonical schemas and normalization (§6)
- Postgres DB scaffolding (§4): Alembic migrations, seed data, connection layer
- Comparison workflow UI shell (§3.3) — upload screens, column mapping, clause review placeholder
- Rate Comparison agent and report shell (§8.1 items 1, 2, 5, 6)
- All unit tests for parsers and the normalization agent

**Phase 1 explicitly excludes:** Rate Analysis, T&C Comparison report output, NarrativeAgent, LLM
integration, XLSX/PDF export. Those come in Phase 2.

---

## Part 2 — The parser layer: this is the hard problem

### 2.1 Why naive parsing fails on real carrier agreements

Real carrier agreements are not clean databases. The three format families below (drawn from actual
client documents) each break a different assumption. The parser must handle all three:

---

**Format A — Multi-region sheet (Image 1 in the project)**

```
| Origin    | Destination | Mode | Service      | Min    | LTL    | 1000  | 2000  | ... | RATE CALC | Weight | Rate | Base Charge | FSC Rate | FSC Amount | All-in |
| Trenton ON| Winnipeg MB | Road | Fresh/Frozen | 378.33 | 98.12  | 42.50 | 27.96 | ... |           | 15000  | 18.36| 2754.00     | 0.587    | 1616.60    | 4370.60|
```

The sheet contains two conceptually separate regions:
- **Region 1 (columns A–L):** The agreement — origin, destination, mode, service type, and weight
  breaks (Minimum, LTL, 1000 lb, 2000 lb, 5000 lb, 10000 lb, 20000 lb, 30000 lb rates per CWT).
- **Region 2 (columns M–S):** An embedded rate calculator — RATE CALC, Weight, Rate, Base Charge,
  FSC Rate, FSC Amount, All-in. This is a *user tool*, not agreement data. It must be detected and
  excluded entirely from the parsed output.

The column header `RATE CALC` (or similar: "RATE CALCULATOR", "CALC", "CALCULATION") is the
boundary signal. Everything to its right in the header row is calculator output, not agreement data.

The weight break columns (1000, 2000, 5000, …) are column *names*, not row data. They must be
**unpivoted** (melted): each weight-break column becomes a separate `RawRateRow` with `weight_break`
set to the column name and `rate` set to the cell value.

---

**Format B — T&C / Accessorial schedule (Image 2 in the project)**

```
| Service                              | Min     | CWT   | Max     | Unit                  | Description (long prose) |
| Delay Charges/Driver Detention (Dry) | $55.00  | n/a   | n/a     | $27.50 Per Quarter Hr | In the event the carrier's equipment... |
```

This is NOT a rate table. It is a **clause table** — each row is a structured accessorial charge
with a prose description. The parser must detect this region and route it to `RawClauseChunk[]`
rather than `RawRateRow[]`.

Detection heuristics (any one is sufficient):
- Header row contains "Service" AND ("Min" OR "CWT") AND ("Description" OR "Unit")
- First column values match known accessorial keywords: "detention", "layover", "lumper",
  "residential delivery", "fuel surcharge", "valuation charge", "pallet return", etc.
- No numeric lane data (origin/destination) in the first two columns.

When detected, parse each row as:
- `clause_type` = map service name to `rac.clause_taxonomy.code` (see §2.4 below)
- `structured_value` = `{"min": ..., "cwt_rate": ..., "max": ..., "unit": ...}`
- `extracted_text` = the Description column text (this is what the clause extractor works with later)
- `source_locator` = sheet name + row number

---

**Format C — Context-carry-down sheet (Image 3 in the project)**

```
Row 1:  [Title] "TRUCK (Frozen)"
Row 2:  "Origin"  [blank]  [blank] ...
Row 3:  "Trenton" "ON"     [blank] ...
Row 4:  [blank]
Row 5:  "Destinations" [blank] [blank] "MIN" "LTL" "500" "1000" "2000" "5000" "10000"
Row 6:  "Winnipeg"  "MB"  [blank] 229.82  70.70  70.70  65.09  55.79  50.90  36.75
Row 7:  "Calgary"   "AB"  [blank] 245.16  93.00  93.00  83.28  75.65  70.35  47.46
...
Row 13: "Kelowna"   "BC"  [blank] [blank] [blank] [blank] [blank] [blank] [blank] [blank]
Row 19: "Rates are all-in in CAD"
Row 20: "Based on 40\" x 48\" x up to 84\""
```

Problems the parser must solve:
1. **Title row ≠ header row.** Row 1 has the mode/service type in it, not column headers.
2. **Origin is in a context block** (rows 2–3), not in a per-row column. Origin = "Trenton, ON" applies
   to every destination row (rows 6–17). The parser must detect this context block and propagate the
   origin to all `RawRateRow` objects it produces from this sheet.
3. **Province in column B, unlabeled.** Column B contains the province code for each destination city.
   The city+province pair must be assembled into a single `dest_city`/`dest_state` pair.
4. **Actual header row is row 5**, not row 1. The heuristic: scan from row 1 downward; the first row
   that contains at least 3 numeric weight-break-like values ("LTL", "500", "1000", "MIN", etc.) in
   its cells is the header row.
5. **Missing-rate rows.** Row 13 (Kelowna), rows 15/17 (Prince George, Victoria) have destination
   names but all rate cells are blank. These must produce `RawRateRow` objects with `no_rate=True`,
   not be silently skipped.
6. **Footer rows** (rows 19–20) contain notes, not data. Detect: if a row's first cell value looks
   like a natural-language sentence (contains spaces and common note keywords: "based on", "rates
   are", "subject to", "CAD", "USD", "note:", etc.) and the rest of the row is blank, it is a footer.
   Extract footer text and attach it as `sheet_notes` to the parsed output — do not try to parse it
   as a data row.

---

### 2.2 Multi-pass Excel parsing algorithm

Every Excel parser (`parsers/excel_parser.py`) must implement this multi-pass pipeline:

```
PASS 1 — Sheet inventory
  For each sheet in the workbook:
    - Read all non-empty cells, including merged cell ranges.
    - Build a flat grid: dict[(row, col)] = cell_value. Resolve merged cells so every cell
      in a merged range has the value of the top-left cell (openpyxl: iterate ws.merged_cells,
      propagate values to all cells in the range).
    - Note sheet name and position.

PASS 2 — Region classifier
  For each sheet, scan row by row to classify content:
    - TITLE REGION: first 1–3 rows that contain a single non-empty cell with a string
      value that looks like a heading (no numeric content, often contains mode/service keywords).
    - CONTEXT BLOCK: a block of rows where the first cell is a label ("Origin", "Date",
      "Carrier", "Effective", etc.) and the second cell is the value. These become
      default context fields for all subsequent data rows in the same sheet.
    - HEADER ROW: the first row after the context block that contains ≥3 cells matching
      weight-break-like keywords (MIN, LTL, and/or numeric values like 500, 1000, 2000,
      5000, 10000, 20000, 30000, CWT).
    - DATA REGION: rows between the header row and the footer region.
    - CALCULATOR REGION: a contiguous block of columns (starting at a column whose header
      is "RATE CALC" or "CALC" or "CALCULATION") that begins within the header row.
      Mark these column indices as excluded from data parsing.
    - FOOTER REGION: rows after the data region that match the footer heuristic (see §2.1).
    - CLAUSE TABLE: a region where the header row matches the T&C detection heuristic
      (see §2.1 Format B). Route to RawClauseChunk, not RawRateRow.

PASS 3 — Header schema construction
  From the identified header row (excluding calculator columns):
    - Identify lane columns: Origin, Destination, Mode, Service, and any city/state/zip
      sub-columns. Build a column-index-to-field-name map.
    - Identify weight-break columns: any remaining numeric or LTL/MIN columns. Store as
      a list of (column_index, break_label) pairs. break_label is the cell value as a string.
    - Note: the same break_label may appear in different sheets with different numeric values
      (one sheet has up to 10000, another up to 30000). Do not hardcode any specific labels.

PASS 4 — Context resolution
  Merge the context fields extracted in PASS 2 with any per-row lane fields:
    - If origin is in the context block only, apply it to all data rows.
    - If origin is in a per-row column, use the per-row value.
    - If both exist, the per-row value wins (most specific).

PASS 5 — Row parsing + unpivoting
  For each row in the DATA REGION (excluding CALCULATOR REGION columns):
    For each weight-break column (from the header schema):
      rate_value = cell at (row, weight_break_column_index)
      Emit one RawRateRow:
        source_file = file path
        source_sheet = sheet name
        source_row = row number (1-indexed)
        raw_fields = {
          "origin": [context or per-row],
          "destination": [assembled from city + province if applicable],
          "mode": [if present],
          "service": [if present],
          "weight_break": break_label,
          "rate": rate_value (None or "" → set no_rate=True),
          ... any other columns
        }
    If ALL weight-break cells in a row are blank/zero, set no_rate=True on all emitted rows
    but still emit them (they become missing-lane records in the report).

PASS 6 — Footer and notes extraction
  Collect all footer rows' text values into a list.
  Attach as sheet_notes to the ParsedSheet result.
  These will be stored but not used in rate computation.
```

---

### 2.3 PDF parsing — handling non-linear and misaligned data

PDF tables are harder than Excel because the format does not encode table structure — the parser
must infer it from the position of text on the page.

**Strategy: bounding-box table reconstruction, not rely on pdfplumber's `extract_table()` alone.**

`extract_table()` uses line-detection to find table borders. It works for bordered tables but
fails for borderless tables (which many carrier PDFs use — just whitespace alignment).

Implement a two-mode PDF parser:

```
MODE A — Bordered table (preferred, faster):
  Use pdfplumber page.extract_table() or page.extract_tables().
  Post-process with the same multi-pass algorithm as Excel.

MODE B — Borderless table (fallback):
  Use pdfplumber page.extract_words(extra_attrs=["x0","x1","top","bottom"]).
  Each word has a bounding box. Reconstruct rows and columns:

  STEP 1 — Row clustering:
    Group words by y-coordinate into rows. Words are in the same row if their
    vertical midpoints are within TOLERANCE pixels of each other (TOLERANCE = 3.0 by
    default, configurable). Use a sweep-line algorithm: sort words by top, then
    cluster greedily.

  STEP 2 — Column boundary inference (from the header row):
    Once the header row is identified (heuristic: the row containing the most
    "column-header-like" words — MIN, LTL, numeric weight breaks), infer column
    x-boundaries:
      - Each header word's x0 defines the left boundary of its column.
      - Each header word's x1 defines the right boundary of its column.
      - Build a list of column intervals [(x0_i, x1_i, label_i)].

  STEP 3 — Cell assignment:
    For each word in each data row:
      Find the column interval whose [x0, x1] range contains the word's x-midpoint.
      If the word falls in a gap (between columns), assign it to the nearest column.
      If the word falls to the left of all columns, it is a left-margin label
      (likely an origin or destination) — treat as a new context field.

  STEP 4 — Multi-page table stitching:
    When a table spans multiple pages, the header row repeats at the top of each
    continuation page. Detect: if page N+1's first data-looking row matches the
    header of page N, it is a header repeat — skip it and continue appending rows.
    Heuristic: compare the first row of page N+1's extracted text against the known
    column labels from page N. If ≥80% of cells match, it is a header.

  STEP 5 — Context carry-down in PDFs:
    Some PDFs place the origin and carrier name in a block ABOVE the table (e.g.,
    a paragraph "Origin: Trenton, ON — Service: LTL — Effective: Jan 1, 2025").
    Before running Step 1 on the main table, scan the top of each page for
    key:value blocks (regex: r"(Origin|Carrier|From|Effective|Currency)\s*[:\-]\s*(.+)").
    Extract these as context fields and apply them to all rows parsed from that page.
```

**When to use Mode A vs Mode B:**
1. Attempt Mode A first.
2. If Mode A returns fewer than 2 rows with at least 4 columns, fall back to Mode B.
3. If Mode B returns fewer than 2 rows, emit a `ParseWarning(file, page, "Could not detect
   table structure — manual column mapping required")` and surface this in the UI.
4. Never silently skip a file. If parsing fails, the user must be told.

---

### 2.4 Clause detection and taxonomy mapping

When the parser identifies a clause table (Format B), each row is routed to `RawClauseChunk`:

```python
@dataclass
class RawClauseChunk:
    source_file: str
    source_page: int | None
    source_sheet: str | None
    source_row: int
    raw_service_name: str        # verbatim from the "Service" column
    raw_min: str | None          # "n/a" → None
    raw_cwt: str | None
    raw_max: str | None
    raw_unit: str | None
    raw_description: str         # full prose from the Description column
```

`ClauseExtractionAgent` (§8.1) takes `RawClauseChunk[]` and maps each to `rac.clauses`.
The taxonomy mapping is NOT done in the parser — it is done in the agent, against the
`rac.clause_taxonomy` table. The parser only identifies that a region is clause-like and extracts
the raw fields.

Initial taxonomy seed (`app/rate_analysis_comparison/clauses/taxonomy_seed.json`):

```json
[
  {"code": "detention_dry",           "label": "Detention/Delay — Dry",           "keyword_patterns": ["detention", "delay charge", "driver detention"]},
  {"code": "detention_refrigerated",  "label": "Detention/Delay — Refrigerated",  "keyword_patterns": ["heated", "refrigerated", "reefer"]},
  {"code": "protective_service",      "label": "Protective Service (Heat/Freeze)", "keyword_patterns": ["protective service", "heat protect", "frozen"]},
  {"code": "storage_dry",             "label": "Storage — Dry",                   "keyword_patterns": ["storage charge.*dry", "storage.*dry"]},
  {"code": "storage_refrigerated",    "label": "Storage — Refrigerated",          "keyword_patterns": ["storage.*heated", "storage.*refrigerated"]},
  {"code": "appointment_charge",      "label": "Appointment Charge",              "keyword_patterns": ["appointment", "booked appointment"]},
  {"code": "after_hours",             "label": "After Hours Delivery",            "keyword_patterns": ["after hours", "after-hours", "5:00 pm", "weekend"]},
  {"code": "lumper_single",           "label": "Lumper/Swamper — Single Delivery","keyword_patterns": ["swamper.*single", "lumper.*single"]},
  {"code": "lumper_consolidated",     "label": "Lumper/Swamper — Consolidated",   "keyword_patterns": ["swamper.*consolidat", "lumper.*consolidat"]},
  {"code": "lumper_dock",             "label": "Lumper/Swamper at Carrier Dock",  "keyword_patterns": ["swamper.*dock", "lumper.*dock"]},
  {"code": "additional_labour",       "label": "Additional Labour",               "keyword_patterns": ["additional labour", "additional labor"]},
  {"code": "tailgate_delivery",       "label": "Tailgate Delivery",               "keyword_patterns": ["tailgate"]},
  {"code": "residential_delivery",    "label": "Residential Delivery",            "keyword_patterns": ["residential"]},
  {"code": "construction_delivery",   "label": "Construction Site Delivery",      "keyword_patterns": ["construction site"]},
  {"code": "inside_delivery",         "label": "Inside Delivery",                 "keyword_patterns": ["inside delivery"]},
  {"code": "restricted_access",       "label": "Restricted Access / Special Equipment", "keyword_patterns": ["restricted access", "specific equipment"]},
  {"code": "trade_show",              "label": "Trade Show Delivery",             "keyword_patterns": ["trade show"]},
  {"code": "redelivery",              "label": "Re-Delivery",                     "keyword_patterns": ["re-delivery", "redelivery"]},
  {"code": "fuel_surcharge",          "label": "Fuel Surcharge",                  "keyword_patterns": ["fuel surcharge", "fsc"]},
  {"code": "valuation_charge",        "label": "Valuation Charge",               "keyword_patterns": ["valuation charge", "declared value"]},
  {"code": "pallet_return",           "label": "Pallet Return",                  "keyword_patterns": ["pallet return"]},
  {"code": "payment_terms",           "label": "Payment Terms",                  "keyword_patterns": ["payment terms", "net 30", "net 15", "net 45", "invoice due"]},
  {"code": "minimum_charge",          "label": "Minimum Charge",                 "keyword_patterns": ["minimum charge", "min charge"]},
  {"code": "liability_limit",         "label": "Liability Limit",                "keyword_patterns": ["liability", "cargo claim", "per pound", "per lb"]},
  {"code": "insurance",               "label": "Insurance Requirements",         "keyword_patterns": ["insurance", "coi", "certificate of insurance"]},
  {"code": "volume_commitment",       "label": "Volume / Lane Commitment",       "keyword_patterns": ["volume commitment", "lane guarantee", "tonnage"]},
  {"code": "service_level",           "label": "Service Level Commitments",      "keyword_patterns": ["transit time", "on-time", "service level"]},
  {"code": "gri",                     "label": "GRI / Rate Increase Trigger",    "keyword_patterns": ["general rate increase", "gri", "annual increase"]},
  {"code": "termination",             "label": "Termination",                    "keyword_patterns": ["termination", "notice period", "cancel"]},
  {"code": "governing_law",           "label": "Governing Law / Venue",          "keyword_patterns": ["governing law", "jurisdiction", "venue"]},
  {"code": "force_majeure",           "label": "Force Majeure",                  "keyword_patterns": ["force majeure", "act of god"]},
  {"code": "indemnity",               "label": "Indemnity",                      "keyword_patterns": ["indemnif", "hold harmless"]}
]
```

Taxonomy mapping in `ClauseExtractionAgent`:
- For each `RawClauseChunk`, compare `raw_service_name.lower()` against each taxonomy entry's
  `keyword_patterns` using `rapidfuzz.fuzz.partial_ratio` with a threshold of 85.
- If matched: set `clause_type = taxonomy.code`, `user_status = 'pending'`.
- If unmatched: set `clause_type = 'unknown'`, `user_status = 'pending'`, emit a warning.
- Do NOT hard-code string comparisons. Use the taxonomy from the DB (or the seed JSON during
  initial parsing before the DB is set up).

---

### 2.5 Handling the `no_rate` and `missing_rate` distinction

These are different and must not be conflated in the data model:

- **`no_rate=True`**: The lane IS listed in the carrier's agreement. A rate entry exists but the
  rate field is blank, zero, or contains a non-numeric placeholder ("TBD", "On Request", "Call",
  "N/A"). The carrier covers the lane but has not quoted a rate in this document.

- **`missing_lane=True`**: The lane does NOT appear in the carrier's agreement at all. Only
  determinable when comparing two carriers: carrier B has the lane, carrier A does not.

- **`nearby_lane_substitution=True`**: An exact lane was not found in this carrier's agreement, but
  a geographically proximate lane was found (radius from `rac.settings.nearby_lane_radius_miles`).
  `substitute_origin_zip`, `substitute_dest_zip` must be set to the lane that was used.

In the `RawRateRow` and the canonical `CarrierRate` schemas, add:
```python
no_rate: bool = False           # rate field is blank/zero/"on request"
rate_note: str | None = None    # the literal text found (e.g., "On Request")
```

`missing_lane` and `nearby_lane_substitution` are computed at comparison time by
`LaneMatchingAgent`, not at parse time.

---

### 2.6 Word document (.docx) parsing

`python-docx` can read tables (`doc.tables`) and paragraphs (`doc.paragraphs`).

Rate tables in Word documents usually appear as `doc.tables[i]`. Apply the same multi-pass logic
as Excel after converting the table to a row/column grid.

**Prose rates** sometimes appear in Word documents as sentences like:
  "From Chicago, IL to Dallas, TX: Flat rate $1,250.00 plus 22% FSC."

Use regex extraction for this pattern:
```python
PROSE_RATE_PATTERN = re.compile(
    r"(?:from\s+)?([\w\s,\.]+?)\s+to\s+([\w\s,\.]+?):\s*"
    r"(?:flat rate\s*)?\$?([\d,]+\.?\d*)"
    r"(?:\s*(?:plus|with|and)\s*([\d\.]+)%\s*(?:FSC|fuel))?",
    re.IGNORECASE
)
```

Log a `ParseWarning` for every prose rate extracted — they are more fragile than table rates and
the user should be aware they exist.

---

## Part 3 — Postgres database layer

### 3.1 Provisional DB setup requirements

`install.sh` (idempotent — safe to run multiple times):

```bash
# Create role and database (skip if present)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='apeiron'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE ROLE apeiron WITH LOGIN PASSWORD 'apeiron_local';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='apeiron_bridge'" | grep -q 1 || \
  sudo -u postgres createdb -O apeiron apeiron_bridge

# Bind to localhost only — verify pg_hba.conf and postgresql.conf
# (Documented in BUILD_UBUNTU_22_04.md, enforced by a startup check in app/rate_analysis_comparison/db/engine.py)

# Run Alembic migrations
cd /home/grace/dev/app/apeiron_bridge
alembic -c app/rate_analysis_comparison/db/alembic.ini upgrade head

# Seed reference data
python -m app.rate_analysis_comparison.db.seed
```

Connection string file `~/.config/apeiron_bridge/db.toml`:
```toml
[database]
url = "postgresql+psycopg://apeiron:apeiron_local@localhost:5432/apeiron_bridge"
```

**The app must generate this file with safe defaults on first launch if it does not exist.**
It must NEVER be committed to the repo. Add it to `.gitignore`.

### 3.2 DB layer rules

- All table definitions in `db/models.py` using SQLAlchemy 2.x Core `Table` objects.
- All query functions in `db/queries.py` as named functions. No SQL strings outside `db/`.
- Every write wrapped in a transaction. Every bulk read (>10k rows) uses a server-side cursor.
- `db/engine.py` must run a startup connectivity check and a localhost-binding check on
  every app launch. If Postgres is not reachable, the RA&C module disables itself with a clear
  error in the UI rather than crashing the whole app.
- Schema name `rac` for all RA&C tables. No changes to any existing schemas.

---

## Part 4 — Code quality standards

**These are not suggestions. Every file must meet them before it is committed.**

### 4.1 Style
- Match the existing SOA module's code style exactly. If SOA uses `snake_case` for variables and
  `PascalCase` for classes, RA&C does the same.
- Type hints on every function signature. No `# type: ignore` without a documented reason.
- Docstrings on every public class and public function. One sentence minimum; more if the
  behaviour is non-obvious.
- No print statements. Use the logging module at the level the SOA module uses.

### 4.2 Error handling
- Every parser must catch, log, and surface *all* exceptions as `ParseWarning` or `ParseError`
  objects in the result, never as unhandled exceptions that crash the UI.
- A `ParseError` on one file must not stop parsing of other files. The orchestrator continues
  and marks that file as failed.
- Distinguish: `ParseWarning` (parsing completed but something is uncertain — e.g., a prose rate
  was found, or a column mapping was guessed) vs `ParseError` (parsing could not complete —
  corrupt file, password-protected PDF, etc.).

### 4.3 Threading
- All parsing and computation runs in `QThread` workers. The UI thread is never blocked.
- Workers emit Qt signals for: `progress_updated(file_name, pct)`, `file_completed(file_name, row_count)`,
  `file_failed(file_name, error_message)`, `all_done(total_rows)`.
- Workers must respond to a `cancel()` call. Check a `self._cancelled` flag at each file boundary.

### 4.4 Data privacy (hard rules, non-negotiable)
- No raw client data (shipment IDs, invoice numbers, carrier rate values, lane lists) in log
  messages. Log opaque IDs only (UUIDs from `rac.agreements.id`).
- No raw client data ever passed to any LLM call, even when AI mode is on. The LLM interface
  (`services/llm_client.py`) must assert at the call boundary that the payload contains no
  raw rate or shipment data. Write a unit test that verifies this assertion fires.
- No telemetry of any kind. The app is air-gapped by client requirement.

### 4.5 Tests
Every parser must have unit tests in `tests/` covering:
- The specific format examples in §2.1 of this prompt (Format A, B, C).
- Empty file.
- Single-row file.
- File with no detectable table structure.
- File with all blank rate cells.
- Multi-page PDF with a repeating header row.
- DOCX with both a table and a prose rate sentence.

Fixture files (small, anonymised) go in `tests/fixtures/rac/`.

---

## Part 5 — Deliverables for Phase 1 commit

Commit a branch `feature/rac-phase-1` with:

```
app/_archive/quick_csv_match/        ← old module, archived
app/rate_analysis_comparison/
  __init__.py
  ui/
    home_card.py                     ← replaces Quick CSV Match card on home screen
    rac_window.py                    ← mode selector (3 tiles)
    comparison_workflow.py           ← upload + column mapping + clause review screens (shell)
    tc_comparison_workflow.py        ← (shell only — full in Phase 2)
    analysis_workflow.py             ← (shell only — full in Phase 2)
    column_mapping.py                ← reuse/fork from existing multi-file widget
    clause_review.py                 ← accept/edit/reject UI for extracted clauses
    results_rate_comparison.py       ← tab container for comparison report (Phase 2 fills tabs)
    settings_ai.py                   ← AI on/off/BYO-key panel
    settings_db.py                   ← DB connection status and settings
    carrier_directory.py             ← browse/edit rac.carriers
  agents/
    base.py                          ← Agent protocol + RunContext + AgentResult
    ingestion.py                     ← IngestionAgent (calls right parser by extension)
    normalization.py                 ← NormalizationAgent (RawRateRow → CarrierRate)
    clause_extraction.py             ← ClauseExtractionAgent (RawClauseChunk → rac.clauses)
    lane_matching.py                 ← LaneMatchingAgent (direct + nearby)
    rate_comparison.py               ← RateComparisonAgent
    persistence.py                   ← PersistenceAgent (all DB I/O)
    orchestrator.py                  ← OrchestratorAgent (Phase 1: comparison path only)
  parsers/
    __init__.py
    base.py                          ← ParsedSheet, RawRateRow, RawClauseChunk, ParseWarning, ParseError
    csv_parser.py
    excel_parser.py                  ← implements full multi-pass algorithm from §2.2
    pdf_parser.py                    ← Mode A + Mode B from §2.3
    docx_parser.py                   ← table + prose pattern from §2.6
    ocr_parser.py                    ← stub (raises NotImplementedError with feature-flag message)
  clauses/
    taxonomy_seed.json               ← from §2.4
    rubric_seed.json                 ← conservative shipper-leaning defaults (placeholder values)
    extractors/                      ← one module per taxonomy code (stubs for Phase 1)
  schemas/
    shipment.py
    carrier_rate.py
    lane.py
    clause.py
  db/
    __init__.py
    engine.py
    models.py
    queries.py
    alembic.ini
    migrations/
      env.py
      versions/
        0001_initial_rac_schema.py
    seed/
      __init__.py                    ← seed runner
      zip_geo_us.csv                 ← bundled US ZIP centroid data
      zip_geo_ca.csv                 ← bundled CA postal code centroids
  services/
    llm_client.py                    ← abstraction shell (no provider wired in Phase 1)
    keyring_store.py
  reports/
    rate_comparison_xlsx.py          ← Phase 2 fills this out
  workers/
    ingestion_worker.py              ← QThread
    compute_worker.py                ← QThread
  templates/
    sop_rac.pdf                      ← placeholder (one-page "coming soon" PDF)
  tests/
    fixtures/rac/
      format_a_rate_table.xlsx
      format_b_accessorial.xlsx
      format_c_context_carrydown.xlsx
      format_c_context_carrydown.pdf  ← if available; otherwise generate from xlsx
    test_excel_parser.py
    test_pdf_parser.py
    test_docx_parser.py
    test_csv_parser.py
    test_normalization_agent.py
    test_clause_extraction_agent.py
    test_lane_matching_agent.py
    test_db_migrations.py
    test_db_queries.py
    MANUAL_QA_RAC.md
requirements.txt                     ← updated with new deps (§9 of spec)
BUILD_UBUNTU_22_04.md               ← updated with Postgres setup steps
install.sh                           ← updated (idempotent Postgres + migration + seed steps)
```

**Do not modify:**
- `app/soa_reconciliation/` (any file)
- `app/multi_file_comparison/` (any file)
- `main.py` (except the single line that registers the new RA&C card)
- `tests/` existing tests (add new test files, do not edit existing ones)

---

## Part 6 — Questions to resolve before coding

1. **What Python version is the project on?** Match it exactly. Do not upgrade.
2. **Does the existing column-mapping widget in Multi-File Comparison export a clean interface
   that can be imported without modification?** If yes, import it. If it is tightly coupled to
   the Multi-File module's state, fork a copy into `rate_analysis_comparison/ui/column_mapping.py`.
3. **What is the existing test runner?** (`pytest` assumed — confirm). What is the CI setup?
   The AI data-flow audit test (§11 of spec) must be wired into the CI gate.
4. **The weight break columns in Image 3 are all-in rates (confirmed by the footer note "Rates
   are all-in in CAD").** Other carriers' rates may be base-freight-only (FSC added separately,
   as shown in Image 1 where FSC Rate and FSC Amount are separate). The canonical schema must
   support both. Flag this in the column mapping UI so the user can specify which format they are
   uploading.
5. **Image 3 weight breaks (500, 1000, 2000, 5000, 10000) are per-CWT or per-pallet or flat?**
   The note says "Based on 40\" x 48\" x up to 84\"" which suggests per-pallet pricing. The
   column headers do not say CWT. The parser must record `freight_rate_unit = "unknown"` and
   surface this for the user to confirm in column mapping.

---

*End of Phase 1 execution prompt. Questions → raise as comments in the branch PR.*
