# Apeiron Bridge — Rate Analysis & Comparison (RA&C) Module
## Build Instructions for Antigravity

**Document status:** Living spec. **Phase 1 — v0.2** (added T&C comparison, Postgres, tightened AI/data-privacy). Will be amended as client requirements firm up.
**Target repo:** `github.com/anandrobert-dev/apeiron_bridge`
**Local path:** `/home/grace/dev/app/apeiron_bridge`
**Target OS:** Ubuntu 22.04 LTS and above (stand-alone desktop app)
**UI framework already in use:** PySide6 (Python/Qt)

---

## 0. Hard rules (read first, do not violate)

1. **DO NOT modify SOA Reconciliation code or logic.** It is working in production. Treat `app/soa_reconciliation/` (or whatever the existing SOA module path is) as read-only. If shared utilities must be touched, copy-and-fork them into the new module instead of editing in place.
2. **DO NOT modify Multi-File Comparison code or logic** unless explicitly told. Same read-only treatment.
3. **You MAY replace the "Quick CSV Match" landing card** on the home screen with a new "Rate Analysis & Comparison" card. The Quick CSV Match module code can be archived under `app/_archive/quick_csv_match/` rather than deleted, so it can be restored if the client changes their mind.
4. **Stand-alone app constraint:** No external services required for the app to install and launch. Optional AI features (LLM-powered agents) must degrade gracefully when no API key is configured — the deterministic engine must still produce a full report on its own.
5. **Data must not leave the desk.** This is a hard client requirement.
   - No telemetry, no cloud uploads of client data, no third-party SaaS for parsing. Customer data is freight pricing and contractual terms — treat it as confidential.
   - **No AI touches raw client data directly.** Not the shipment records, not the rate tables, not the verbatim T&C prose. Even when the user enables AI features:
     - AI input must be either (a) the user's own typed prompts, or (b) **derived/aggregate/anonymized** data (e.g., "Carrier A is cheapest on 18 lanes; Carrier B on 7 lanes; total savings = $X" — but never the actual lane list or shipment IDs).
     - For clause work, AI may receive **clause-type labels and short de-identified excerpts** only if the user explicitly approves per-clause, never the full document.
   - **No hard-coded API keys, no hard-coded provider endpoints, no bundled "default" cloud service.** If the user wants AI, they supply their own provider, their own key, their own endpoint. The app provides the plumbing only.
   - The deterministic, no-AI path must produce a complete and correct report end-to-end. AI is strictly additive (better narrative phrasing, better clause-similarity ranking) — never load-bearing.
6. **Python 3.10+** (whatever the existing app already targets — match it, do not bump).
7. **Match existing project conventions:** code style, logging, threading (QThread workers off the main thread), progress reporting, error dialogs. Read the SOA module first to learn the house style, then mirror it.

---

## 1. What we're building

A new module under Apeiron Bridge called **Rate Analysis & Comparison (RA&C)**. It replaces the "Quick CSV Match" card on the home screen.

RA&C covers **three distinct dimensions** of carrier-agreement intelligence. The client treats them as different jobs and we must not conflate them — each has its own workflow, its own report, and its own export:

### 1A. Rate **Comparison**
Given **multiple carriers' rate agreements** (in any format — PDF, Word, XLS/XLSX, CSV, and ideally images/scanned PDFs later), produce a side-by-side comparison of the **numeric rates** so the user can see, for every lane the carriers cover:
- Lane-to-lane direct comparison (same origin + destination across carriers)
- Nearby-lane / suburb comparison (when an exact lane is missing on a carrier, find the geographically nearest covered lane and flag the substitution) — driven by the Postgres lane database, see §4
- **Missing lanes** (carrier X covers it, carrier Y does not)
- **No-rate detection** (lane is listed but rate field is blank/zero/"on request")
- **Carrier-to-carrier rate deltas** (which carrier increased rates vs. which decreased, by how much, in % and absolute) — using the explicit old/new flag set at upload time (§3.3), not filename guessing

Rate Comparison is **agreement vs. agreement.** It does NOT need actual shipment history.

### 1B. Terms & Conditions **Comparison** *(new in v0.2 — the part the client emphasized "is not about rates")*
Rate numbers alone are **not enough** to evaluate a carrier agreement. The contractual clauses around those rates can change the real cost of doing business more than the line-haul rate does. Examples that materially affect total cost:
- Payment terms (NET 15 vs. NET 30 vs. NET 45)
- Fuel surcharge methodology (DOE-indexed weekly? flat %? mileage-based? capped?)
- Minimum charge and minimum-weight rules
- Accessorial schedules (detention, layover, lumper, reconsignment, redelivery, liftgate, inside delivery, residential, after-hours, hazmat)
- Free-time and detention/demurrage triggers
- Liability limits and cargo-claim procedures (per-pound caps, claim filing windows, salvage rules)
- Insurance requirements (minimums, additional insured, COI cadence)
- Volume / lane commitments and tonnage guarantees
- Service-level commitments (transit time, on-time %, performance penalties)
- Rate validity / re-rating triggers (annual GRI, fuel reset cadence)
- Termination clauses (notice periods, for-cause vs. without-cause)
- Indemnity, force majeure, governing law / venue

For each uploaded agreement, the module must **extract clauses into a structured taxonomy** (see §7.3) and produce a side-by-side comparison so the user can see:
- **Clause coverage matrix** — which carrier has a clause for each category, which is silent.
- **Clause delta** — concrete differences in the same clause type across carriers (e.g., payment terms: A = NET 30, B = NET 45, C = NET 15).
- **Favorability scoring** — for each clause type, mark which carrier's terms are more favorable to *the shipper* (the client) vs. more favorable to the *carrier*. The scoring rubric must be **stored in Postgres and user-editable** — not hard-coded.
- **Change tracking** — when the same carrier's renewed agreement is uploaded (old/new flag, §3.3), highlight which clauses changed and how.

T&C Comparison **shares the upload workflow** with Rate Comparison. One upload pass extracts both the rate tables and the clauses; the user then picks which report to view (or views both).

### 1C. Rate **Analysis**
Given the user's **shipment history** (their actual billed shipments) plus the **carriers' rate agreements**, produce an analytical report that says, per shipment:
- What the current carrier billed (Freight + Fuel + Subtotal)
- What each other carrier *would have* charged on the same lane, weight, pallets — applying that carrier's rate **and** their applicable T&C (minimum charges, accessorials, fuel methodology) extracted in §1B
- The cheapest carrier for that shipment, on a **fully-loaded** basis (not just line-haul)
- Total potential savings if shipments had been routed optimally
- Patterns: which lanes are most over-paid on, which carrier consistently wins, which carrier creeps up

The attached template `RATE_ANALYSIS_CURRENT_TEMPLET_FOR_CLIENT.xlsx` is the **legacy version** of this output (10+ years old, flat spreadsheet, rates-only — does not account for T&C). We are **inspired by its data fields, not its layout, and we go further by folding in T&C-aware pricing.** We are building a modern interactive report. See §7.

---

## 2. Reference: what the legacy template actually contained

For data-model purposes only. We do **not** copy this layout.

**Shipment identifiers**
- INVOICE #, BOL #, INVOICE DATE, SHIPMENT DATE

**Current carrier (billed)**
- CARRIER NAME, FREIGHT AMT, FUEL AMT, SUB TOTAL

**Origin (Shipper)**
- SHIPPER (name), SH ADDRESS, SH CITY, SH STATE, SH COUNTRY, SH ZIP

**Destination (Consignee)**
- CONSIGNEE (name), CN ADDRESS, CN CITY, CN STATE, CN COUNTRY, CN ZIP

**Cargo**
- QUANTITY BILLED TEXT, WEIGHT UNIT NAME, Total Pallets (INV)

**Per quoting carrier (A–E in the template — must be N carriers in our build)**
- Freight, Fuel %, Fuel Rate, Sub Total

**Summary block**
- Sub Total per carrier (recap), Cheaper Amount, Cheaper Carrier

Lane key in this dataset = **SH ZIP → CN ZIP** (with city/state as fallback). Build the data model around this.

---

## 3. UI changes

### 3.1 Home screen card swap
- Replace the third card "Quick CSV Match" with a new card titled **"Rate Analysis & Comparison"**.
- Tagline under the title: *"Compare carrier rate agreements and analyze shipment-level savings."*
- Button: **Launch** (same visual style as the other two cards — match the existing green/red/blue color scheme; pick a fourth accent color, e.g. amber/orange `#F59E0B`, that is visibly distinct from blue/red/green).
- Below Launch, add a secondary outlined button **"SOP for RA&C"** mirroring the SOA card's "SOP FOR SOA" pattern. The SOP file can be a placeholder PDF for now.

### 3.2 New RA&C window (modal or stacked, match SOA pattern)
On launch, present a **mode selector** with three tiles:
- **[ Rate Comparison ]** — agreement vs. agreement, numeric rates
- **[ Terms & Conditions Comparison ]** — agreement vs. agreement, contractual clauses
- **[ Rate Analysis ]** — shipments vs. agreements (rates + applicable T&C)

Rate Comparison and T&C Comparison **share the upload workflow** under the hood (one pass extracts both), but the user picks one report at a time. Rate Analysis has its own upload workflow because it also needs shipment history. Do not mix workflows on the same screen.

### 3.3 Comparison upload workflow (Rate + T&C share this)
1. **Upload carrier agreements.** Accept ≥2 files. For each file, the user fills:
   - **Carrier name** — required, free-text, with autocomplete from previously-saved carriers in Postgres (`carriers` table). Filename may **suggest** a default, but never auto-commit it.
   - **Agreement version flag** — radio with three states: `New`, `Old / superseded`, `N/A (only version)`. Default = `N/A`. The `Old` and `New` flags only matter when two files carry the **same carrier name** — that's the trigger for rate-increase / clause-change tracking. Different carrier names → flag ignored.
   - **Effective dates** — optional, auto-extracted from the document if possible, user-editable.
   - **Service level / mode** — optional dropdown (LTL, FTL, Parcel, Air, Ocean, Intermodal, Other).
2. **Parsing progress** with per-file status (parsed / failed / needs mapping). Both the rate-table parser and the clause extractor run in this stage.
3. **Column mapping** screen (only for files where rate-table auto-detect failed) — Apeiron already has this pattern in Multi-File Comparison; reuse the same widget if possible without modifying SOA's copy.
4. **Clause review** screen — show the clauses extracted per agreement (collapsed by default, expandable). User can edit, accept, or reject each extracted clause. Rejected clauses are excluded from comparison. This is a manual gate on a fundamentally noisy extraction step; do not skip it.
5. **Configure comparison** — toggles for: include nearby-lane matching (on/off; if on, radius is pulled from Postgres `settings.nearby_lane_radius_miles`, see §4), missing-lane detection, no-rate flagging, baseline carrier (the one others get compared *against* for % delta), clause favorability rubric (pulled from Postgres, user-editable).
6. **Run** → progress → Results screen. User picks: Rate Comparison report, T&C Comparison report, or both side-by-side (see §7.1 and §7.3).

### 3.4 Rate Analysis workflow (screens)
1. **Upload shipment history** (one file: CSV/XLSX). Map columns to the canonical shipment schema (§6.1).
2. **Upload carrier agreements** (≥1 file). Same upload pattern as 3.3 (carrier name, version flag, dates, service level). Same clause-review step.
3. **Configure analysis** — fuel surcharge methodology resolution (use extracted T&C per carrier if available; fall back to user override), date range filter, lane filter, accessorial inclusion (passthrough vs. modeled from T&C).
4. **Run** → progress → **Results screen** (see §7.2).

### 3.5 Shared UI requirements
- Off-main-thread workers for all parsing/compute (QThread, matching SOA's pattern).
- Real-time chunked progress with per-file granularity.
- Cancellable jobs.
- Persistent templates: save the column-mapping + configuration for re-use (mirror Apeiron's existing "Template Persistency" feature).
- Dark mode + light mode (the app already supports this — match it).

---

## 4. Database — Postgres (new in v0.2)

The client has authorized a Postgres database for long-term persistence. **Postgres only — no SQLite, no other engine, even for local single-user installs.**

### 4.1 Why we need a DB now (not "in v2")
- **Nearby-lane lookups** — radius-based proximity queries need indexed geo data; this is the trigger for adding Postgres at all per the client's instruction.
- **Carrier profile memory** — the user types a carrier name once; from then on it's autocompleted, and that carrier's history of uploaded agreements (old/new chain) is tracked.
- **Clause taxonomy & favorability rubric** — user-editable, persistent across sessions, **not hard-coded in the codebase**.
- **Saved templates** — column-mapping templates, comparison configurations, report definitions.
- **Agreement history** — every uploaded agreement is fingerprinted and stored so old/new flagging can be cross-checked and rate-change tracking works over time, not just within one session.

### 4.2 Deployment model
- Single-user desktop install: bundle a local Postgres (via `apt install postgresql` documented in `BUILD_UBUNTU_22_04.md`), create a dedicated DB `apeiron_bridge`, dedicated role `apeiron`, on `localhost:5432` only. No network listener exposed.
- Migrations: use **Alembic**. Migration scripts versioned in `app/rate_analysis_comparison/db/migrations/`.
- Connection string from a config file at `~/.config/apeiron_bridge/db.toml` — never hard-coded, never checked in. App generates this on first launch if missing.
- Schema isolation: all RA&C tables live under a Postgres schema `rac` (e.g. `rac.carriers`, `rac.agreements`). SOA and Multi-File Comparison are untouched.

### 4.3 Tables (initial set — extend with migrations as the spec evolves)

```
rac.settings                  -- key/value app settings, user-editable
  key TEXT PK, value JSONB, updated_at TIMESTAMPTZ
  -- seeded keys:
  --   nearby_lane_radius_miles  (default 50)
  --   fuel_default_method       (default 'percentage')
  --   currency_default          (default 'USD')

rac.zip_geo                   -- ZIP / postal code → lat/long for nearby-lane math
  postal_code TEXT, country TEXT, lat NUMERIC, lng NUMERIC,
  city TEXT, state TEXT,
  PRIMARY KEY (country, postal_code)
  -- seeded from a bundled CSV (US first; CA next); never reaches out to the internet.

rac.carriers                  -- user-managed carrier directory
  id UUID PK, name TEXT UNIQUE (case-insensitive), aliases TEXT[],
  created_at, updated_at, notes TEXT

rac.agreements                -- one row per uploaded agreement
  id UUID PK, carrier_id UUID FK,
  source_file_name TEXT, source_file_hash TEXT,
  version_flag TEXT CHECK (version_flag IN ('new','old','na')),
  effective_from DATE, effective_to DATE,
  service_level TEXT, uploaded_at TIMESTAMPTZ,
  raw_storage_path TEXT       -- local filesystem path to a copy

rac.rate_rows                 -- normalized rate lines (one agreement → many rows)
  id BIGSERIAL PK, agreement_id UUID FK,
  -- mirrors §6.2 CarrierRate canonical schema

rac.clauses                   -- extracted clauses from each agreement
  id BIGSERIAL PK, agreement_id UUID FK,
  clause_type TEXT,           -- from rac.clause_taxonomy
  extracted_text TEXT,        -- short, may be redacted for AI use
  structured_value JSONB,     -- e.g. {"net_days": 30} for payment terms
  user_status TEXT,           -- 'accepted' / 'rejected' / 'edited'
  source_locator TEXT         -- "page 3, ¶2"

rac.clause_taxonomy           -- the dictionary of clause types
  code TEXT PK,               -- e.g. 'payment_terms', 'fuel_method'
  label TEXT, description TEXT,
  schema JSONB                -- JSON schema for structured_value

rac.clause_favorability_rubric  -- user-editable scoring rubric
  clause_type TEXT FK, criterion TEXT, weight NUMERIC,
  shipper_favorable_pattern JSONB, carrier_favorable_pattern JSONB

rac.templates                 -- saved column-mapping & run configurations
  id UUID PK, name TEXT, scope TEXT,   -- 'comparison'|'analysis'
  payload JSONB, created_at, updated_at
```

### 4.4 Hard rules for the DB layer
- All RA&C code accesses Postgres through a single `app/rate_analysis_comparison/db/` layer. **No raw SQL scattered through agent code.** Use SQLAlchemy 2.x Core (not the ORM) for explicitness and to keep query plans visible.
- Every write is in a transaction. Every long-running read uses a server-side cursor when row count could exceed ~10k.
- The DB stores **structured data only**. Original uploaded files stay on the local filesystem (path stored in `rac.agreements.raw_storage_path`); we do not push large PDFs into Postgres.
- No client data is ever serialized into log lines or telemetry. Logs use opaque IDs.

---

## 5. Input format support

### 5.1 Required for v1
- **CSV** (`.csv`, `.tsv`) — pandas
- **Excel** (`.xls`, `.xlsx`, `.xlsm`) — openpyxl for xlsx/xlsm, xlrd or pandas for xls
- **PDF** — `pdfplumber` for text-based tables, fallback to `pypdf` for raw text. Tables are the priority. Multi-page tables must be stitched.
- **Word** (`.docx`) — `python-docx`. Read both tables and paragraphs (rates sometimes appear in prose like "Chicago to Dallas: $1,250 flat").

### 5.2 Required for v2 (stub now, implement later)
- **Scanned PDFs / images** (`.png`, `.jpg`, scanned `.pdf`) — OCR via `pytesseract` + table reconstruction. Add the dependency now but gate the UI option behind a feature flag.
- **Email-attached agreements** — accept `.eml` and pull attachments.

### 5.3 Universal parser contract
Every parser must output the same intermediate dataclass:

```python
@dataclass
class RawRateRow:
    source_file: str
    source_page: int | None        # PDF/Word
    source_sheet: str | None       # Excel
    raw_fields: dict[str, str]     # everything the parser found, unnormalized
```

The normalization stage (separate from parsing) maps `raw_fields` → canonical schema (§6).

### 5.4 Auto-detection
For each uploaded file, try to auto-detect whether it is:
- A **rate agreement** (lane list + price columns), or
- A **shipment history** (invoice/BOL + dates + billed amounts).

Use header keyword heuristics. If ambiguous, ask the user.

---

## 6. Canonical data schemas

### 6.1 Shipment (analysis input)
```
shipment_id              str
invoice_number           str | None
bol_number               str | None
invoice_date             date | None
shipment_date            date | None
current_carrier          str
origin_name              str | None
origin_address           str | None
origin_city              str | None
origin_state             str | None
origin_country           str | None
origin_zip               str | None
dest_name                str | None
dest_address             str | None
dest_city                str | None
dest_state               str | None
dest_country             str | None
dest_zip                 str | None
quantity_text            str | None
weight                   float | None
weight_unit              str | None        # lb, kg
pallet_count             int | None
billed_freight           Decimal
billed_fuel              Decimal
billed_subtotal          Decimal           # derived if missing
billed_accessorials      Decimal | None
billed_total             Decimal
```

### 6.2 Carrier rate (comparison input)
```
carrier_name             str
agreement_effective_from date | None
agreement_effective_to   date | None
origin_city              str | None
origin_state             str | None
origin_country           str | None
origin_zip               str | None
origin_zip_range_lo      str | None        # for zone-based agreements
origin_zip_range_hi      str | None
dest_city                str | None
dest_state               str | None
dest_country             str | None
dest_zip                 str | None
dest_zip_range_lo        str | None
dest_zip_range_hi        str | None
service_level            str | None        # standard, expedited, LTL, FTL...
weight_break_lo          float | None
weight_break_hi          float | None
pallet_break_lo          int | None
pallet_break_hi          int | None
freight_rate             Decimal | None
freight_rate_unit        str | None        # per_shipment, per_cwt, per_mile, per_pallet
fuel_pct                 Decimal | None    # e.g. 0.28 for 28%
fuel_flat                Decimal | None
minimum_charge           Decimal | None
notes                    str | None
source_file              str
source_locator           str               # "page 3" or "Sheet2!A14"
```

A single carrier file produces many `CarrierRate` rows.

### 6.3 Lane normalization rules
- A "lane" is identified by `(origin_zip, dest_zip)` when both ZIPs are present; else `(origin_city+state, dest_city+state)`; else log and skip.
- ZIPs are normalized to 5 digits (US) or first 3 alphanumeric (CA postal codes). International is allowed; preserve as-is.
- City/state are case-folded and stripped. "St." ↔ "Saint", "Mt." ↔ "Mount" — maintain a small alias dict.

---

## 7. Outputs

### 7.1 Rate Comparison report
**Interactive in-app view (primary)**, exportable to XLSX and PDF.

**Tabs:**
1. **Lane Matrix** — rows = lanes; columns = carriers; cells = rate + fuel. Color-code: cheapest = green, most expensive = red, missing = grey, no-rate = amber.
2. **Coverage Heatmap** — visual map of which carriers cover which regions (origin state × dest state grid).
3. **Rate Deltas** — for every lane covered by ≥2 carriers, show absolute and % difference vs. baseline carrier.
4. **Missing Lanes** — table grouped by carrier: lanes covered by competitors but not this one.
5. **No-Rate Lanes** — lanes where the rate is empty/zero/"call for quote".
6. **Carrier Increases** — when the same carrier appears in two uploaded files (old agreement + new agreement), compute and rank the increases. Detect via filename hints ("2024", "v2", "renewed") or ask the user to mark which is old vs. new.

**Export:** XLSX with one sheet per tab. Apply the formatting standards from the xlsx skill (Arial, frozen header row, conditional color, formulas not hardcoded values for any computed cells).

### 7.2 Rate Analysis report
**Interactive in-app view (primary)**, exportable to XLSX and PDF.

**Tabs:**
1. **Shipment Detail** — one row per shipment with: shipment ID, lane, current carrier subtotal, each alternative carrier's would-be subtotal, cheapest alternative, savings if switched. This is the modernized replacement for the legacy template.
2. **Carrier Scoreboard** — per carrier: # shipments where it would have been cheapest, total realized savings if used, average % savings vs. current.
3. **Lane Hotspots** — lanes ranked by total annual overpayment (lanes where current carrier loses to alternatives most often).
4. **Trend Analysis** — over time (by invoice month): is the current carrier creeping up? Are alternatives narrowing or widening their gap?
5. **Executive Summary** — auto-generated one-page summary (KPI cards: total potential savings, % savings, # lanes optimizable, top 3 recommendations).

**Export:** XLSX (multi-sheet) + a PDF executive summary (matplotlib charts embedded).

### 7.3 T&C Comparison report *(new in v0.2)*
**Interactive in-app view (primary)**, exportable to XLSX and PDF.

**Tabs:**
1. **Clause Matrix** — rows = clause types from `rac.clause_taxonomy` (Payment Terms, Fuel Method, Min Charge, Detention, Liability Limit, Insurance, Claims Window, Volume Commitment, Service Levels, GRI, Termination, Indemnity, Force Majeure, Governing Law, …). Columns = carriers. Cells = structured value where extractable (e.g. "NET 30", "$0.50/lb max"), with a tooltip showing the source excerpt and page reference. Color-code: silent/missing = grey, user-rejected = strikethrough, edited-by-user = italic.
2. **Coverage Gaps** — clauses present in some carrier agreements but silent in others. Grouped by carrier.
3. **Favorability Heatmap** — applies the user-editable rubric from `rac.clause_favorability_rubric`. Each cell is shaded green (shipper-favorable) / red (carrier-favorable) / neutral. Per-carrier composite favorability score at the bottom.
4. **Clause Deltas (Same Carrier, Old vs New)** — only populated when the old/new flag was set on uploaded agreements with matching carrier names. Shows clause-by-clause what changed in the renewal.
5. **Risk Flags** — auto-generated callouts where extracted terms cross thresholds defined in the rubric (e.g., "Payment terms NET 60 — exceeds typical 30-day shipper standard").
6. **Raw Excerpts (audit trail)** — for every clause shown elsewhere, the exact source text and file/page reference, so the user can audit any extraction.

**Export:** XLSX with one sheet per tab, plus a PDF that's suitable for procurement-team review.

### 7.4 Modernization vs. the legacy template
The legacy template was a single flat sheet with per-shipment rows and per-carrier column groups. We keep that as the **Shipment Detail** tab (because operators still want it for audit), but we add the four analytical tabs above it. **Default view on report open = Executive Summary, not Shipment Detail.** Old habit was bottom-up (look at every row); new habit is top-down (look at the summary, drill into rows only when needed).

---

## 8. Agentic architecture

The client asked for "agentic model that works with agents." Here is the architecture. It runs **fully locally by default** and only calls an LLM when the user enables it in Settings and provides their own API key.

### 8.1 Agents (each = a Python class with a clear contract)

1. **IngestionAgent** — given a file path, returns parsed `RawRateRow[]` and `RawClauseChunk[]`. Picks the right parser by extension and content sniffing.
2. **NormalizationAgent** — given raw rows, produces canonical `CarrierRate[]` or `Shipment[]`. Handles unit conversion, ZIP normalization, alias expansion. **Deterministic.** Uses `rac.zip_geo` for ZIP enrichment. May optionally consult an LLM **only for column-name guessing** (no rate data passed) when heuristics fail and the user has opted in.
3. **ClauseExtractionAgent** *(new)* — given the raw text of an agreement (PDF/Word/Excel notes), segments it into clauses and classifies each against `rac.clause_taxonomy`. Deterministic pipeline first: section-header heuristics + regex + keyword anchors per clause type. Optional LLM assist (off by default) for ambiguous segments — and when on, **only short, user-approved excerpts** are sent, never the whole document. Output is written to `rac.clauses` with `user_status='pending'` so the §3.3 review step can approve/reject.
4. **ClauseComparisonAgent** *(new)* — given accepted clauses across N carriers, builds the clause matrix, computes favorability using `rac.clause_favorability_rubric`, identifies coverage gaps and risk flags.
5. **LaneMatchingAgent** — given two carriers' rates, finds direct lane matches and (if enabled) nearby-lane matches using `rac.zip_geo` and the configurable radius from `rac.settings.nearby_lane_radius_miles`. **No hard-coded radius.**
6. **RateComparisonAgent** — given matched lanes across N carriers, computes deltas, flags missing/no-rate, builds the matrix. Renamed from "ComparisonAgent" for clarity now that there's also clause comparison.
7. **PricingAgent** — given a `Shipment` and a `CarrierRate[]` for that lane **plus** the carrier's accepted clauses (min charge, fuel method, accessorials), computes what that carrier would have charged on a fully-loaded basis.
8. **AnalysisAgent** — given priced-out shipments, builds the analysis tabs (Scoreboard, Hotspots, Trends).
9. **NarrativeAgent** — given the analysis output, writes the Executive Summary prose. **This agent's LLM path receives only aggregated metrics**, never raw shipment or rate rows. Fallback: template-filled summary using f-strings if no LLM is configured.
10. **PersistenceAgent** *(new)* — wraps all Postgres reads/writes for the other agents. Single point of DB access so the rest of the agent code stays storage-agnostic.
11. **OrchestratorAgent** — runs the above in sequence, emits progress events to the Qt UI, handles errors, supports cancellation.

### 8.2 Agent contract
```python
class Agent(Protocol):
    name: str
    def run(self, ctx: RunContext, inputs: dict) -> AgentResult: ...
    # AgentResult carries: status, outputs, warnings, errors, telemetry
```

### 8.3 LLM integration (optional, off by default, data-protective)
- **Default: Off.** Every agent that could use an LLM runs its deterministic path. The app produces complete Rate, T&C, and Analysis reports with AI Off — full stop. AI is strictly a quality boost, never a load-bearing dependency.
- **Provider-agnostic plumbing only.** The app ships with a `LLMClient` abstraction. It supports Anthropic, OpenAI, and a local Ollama endpoint. **No provider is hard-coded as the default. No keys, endpoints, or model IDs are bundled.** The user supplies their own provider, endpoint, and key in Settings.
- **API keys** are stored in the OS keyring (`keyring` package), never on disk in plaintext, never in logs.
- **What the LLM may receive:** column-name candidates, ambiguous clause excerpts that the user has explicitly approved for AI processing (per-clause checkbox in the §3.3 review step), and aggregated/anonymized metrics for the Executive Summary narrative. **What the LLM never receives:** shipment IDs, invoice numbers, full lane lists with rates, full carrier names paired with full rate tables, or full T&C documents.
- **Settings panel: "AI Features"** with three modes:
  - `Off` (default)
  - `Local model (Ollama)` — user enters their localhost endpoint and model name
  - `Cloud API (BYO key)` — user picks a provider, pastes their key, the app validates with a no-data test call
- A visible badge on every report tab indicates whether AI assisted that view, and which mode was used.

---

## 9. Dependencies to add (proposed)

Add to `requirements.txt`:
```
pdfplumber>=0.11
python-docx>=1.1
pypdf>=4.0
pytesseract>=0.3.10        # OCR — gated behind feature flag
Pillow>=10.0
rapidfuzz>=3.0             # fuzzy city/state matching, clause-text similarity
keyring>=24.0              # secure API key storage
matplotlib>=3.8            # PDF chart export
reportlab>=4.0             # PDF assembly for exec summary
SQLAlchemy>=2.0            # DB layer (Core, not ORM)
psycopg[binary]>=3.1       # Postgres driver
alembic>=1.13              # DB migrations
```
**Do not add `uszipcode`** — the ZIP geo data lives in `rac.zip_geo` (seeded from a bundled CSV), not in a separate library. Do not pin upper bounds tightly; let pip resolve against the existing PySide6 version already locked.

System-level (document in `BUILD_UBUNTU_22_04.md`):
```
sudo apt install tesseract-ocr poppler-utils postgresql postgresql-contrib
```
The installer (`install.sh`) must:
1. Create Postgres role `apeiron` and database `apeiron_bridge` (idempotent — skip if present).
2. Run Alembic migrations to head.
3. Seed `rac.zip_geo`, `rac.clause_taxonomy`, and `rac.settings` from bundled CSVs.
4. Write `~/.config/apeiron_bridge/db.toml` with the local connection string.
5. Verify Postgres is bound to `localhost` only.

---

## 10. Folder structure (proposed, mirroring existing app/ layout)

```
app/
  rate_analysis_comparison/
    __init__.py
    ui/
      home_card.py             # the new landing card widget
      rac_window.py            # mode selector (3 tiles)
      comparison_workflow.py
      tc_comparison_workflow.py
      analysis_workflow.py
      column_mapping.py
      clause_review.py         # accept/edit/reject extracted clauses
      results_rate_comparison.py
      results_tc_comparison.py
      results_analysis.py
      settings_ai.py
      settings_db.py
      carrier_directory.py     # browse/edit rac.carriers
    agents/
      base.py
      ingestion.py
      normalization.py
      clause_extraction.py
      clause_comparison.py
      lane_matching.py
      rate_comparison.py
      pricing.py
      analysis.py
      narrative.py
      persistence.py
      orchestrator.py
    parsers/
      csv_parser.py
      excel_parser.py
      pdf_parser.py
      docx_parser.py
      ocr_parser.py            # stub for v1
    clauses/
      taxonomy_seed.json       # seeds rac.clause_taxonomy
      rubric_seed.json         # seeds rac.clause_favorability_rubric
      extractors/              # one heuristic module per clause type
        payment_terms.py
        fuel_method.py
        min_charge.py
        accessorials.py
        detention.py
        liability.py
        insurance.py
        claims.py
        volume_commitment.py
        service_level.py
        gri.py
        termination.py
        indemnity.py
        force_majeure.py
        governing_law.py
    schemas/
      shipment.py
      carrier_rate.py
      lane.py
      clause.py
    db/
      __init__.py
      engine.py                # SQLAlchemy engine + session factory
      models.py                # Core table defs (not ORM)
      queries.py               # named query functions
      migrations/              # Alembic
      seed/
        zip_geo_us.csv
        zip_geo_ca.csv
    services/
      llm_client.py            # provider-agnostic LLM, BYO key
      keyring_store.py
    reports/
      rate_comparison_xlsx.py
      tc_comparison_xlsx.py
      analysis_xlsx.py
      exec_summary_pdf.py
    workers/
      ingestion_worker.py      # QThread
      compute_worker.py        # QThread
    templates/
      sop_rac.pdf              # placeholder for now
    tests/
      ...
```

---

## 11. Testing requirements

- **Unit tests** for every parser (one fixture per format).
- **Unit tests** for every agent with deterministic inputs/outputs.
- **Unit tests** for clause extractors — one fixture per clause type with both positive (clause present) and negative (silent) cases.
- **DB tests** with a disposable test database (pytest fixture spinning up a temp schema). Cover migrations up and down, seed loading, and every named query in `db/queries.py`.
- **Golden-file tests** for the Rate, T&C, and Analysis XLSX exports (regenerate fixtures with a flag, diff in CI).
- **AI data-flow audit test** — a recorded test that puts the app in "AI On" mode against a mock LLM endpoint, runs a full Rate + T&C + Analysis cycle on fixtures, and asserts the captured request bodies contain **no** shipment IDs, no invoice numbers, no rate values, no full document text. This test must pass on every CI run; if it fails, the build fails.
- **Manual QA checklist** in `tests/MANUAL_QA_RAC.md`: load 3 PDF rate agreements + 1 XLSX shipment history, run all three reports, verify exec summary renders, verify XLSX export opens in LibreOffice without formula errors, verify clause review accept/reject flow, verify nearby-lane radius change in Settings takes effect on the next run.

---

## 12. Acceptance criteria for Phase 1

The build is "done for Phase 1" when:

1. Home screen shows the new RA&C card; SOA Reconciliation and Multi-File Comparison still launch and run unchanged.
2. Quick CSV Match is archived (code moved to `app/_archive/`) and no longer reachable from the UI.
3. Postgres is provisioned by `install.sh` on a clean Ubuntu 22.04 VM, schema migrations run to head, and seed data (`rac.zip_geo`, `rac.clause_taxonomy`, `rac.clause_favorability_rubric`, `rac.settings`) is loaded.
4. The mode selector shows all three tiles (Rate Comparison, T&C Comparison, Rate Analysis) and each launches its own workflow.
5. All three workflows accept CSV, XLSX, PDF, and DOCX inputs and complete a run on the bundled sample fixtures without crashing.
6. Rate Comparison report shows all 6 tabs with real data on the sample fixtures.
7. T&C Comparison report shows all 6 tabs with real data on the sample fixtures, including a populated favorability heatmap driven by the seeded rubric.
8. Rate Analysis report shows all 5 tabs with real data on the sample fixtures, and pricing is **T&C-aware** (min charges and fuel methods come from extracted clauses, not hard-coded defaults).
9. Clause review screen lets the user accept / reject / edit every extracted clause, and rejected clauses are excluded from the T&C report.
10. Old/new agreement flag, when set on two uploads of the same carrier name, drives both the Rate Comparison "Carrier Increases" tab and the T&C "Clause Deltas" tab.
11. Nearby-lane radius is read from `rac.settings`, not hard-coded; changing it in Settings affects the next comparison run.
12. XLSX exports open in LibreOffice Calc and Microsoft Excel with zero formula errors and zero broken references.
13. PDF executive summary exports and is legible.
14. AI Features default to Off; all three reports generate fully with AI Off. With AI On, the data-flow audit (see §11) confirms no raw shipment, lane-with-rate, or full-document content was sent to the LLM.
15. App launches and runs end-to-end on a clean Ubuntu 22.04 VM following `BUILD_UBUNTU_22_04.md`.
16. SOA Reconciliation regression test passes (existing SOA test suite green).

---

## 13. Out of scope for Phase 1 (do not build yet)

- Real-time rate API integrations (carrier EDI, Project44, etc.)
- TMS integrations
- User authentication / multi-user
- Cloud sync
- Mobile / web companion
- Carrier negotiation recommendations (we'll add this in Phase 2 once the basic analytics are stable)
- Accessorial charges modeling beyond "billed accessorials passthrough"

---

## 14. Open questions (resolve with the client before/during build)

**Resolved in v0.2:**
- ~~Nearby-lane radius default~~ → stored in `rac.settings`, user-editable, no hard-code. Default seed value = 50 miles, change at will.
- ~~AI: local vs. cloud~~ → both supported via BYO key/endpoint. Off by default. No raw data ever sent to AI — only column-name hints, user-approved short excerpts, and aggregated metrics.
- ~~Old/new agreement detection~~ → user-assigned carrier name (Postgres-backed autocomplete) + explicit `New`/`Old`/`N/A` flag at upload. No filename heuristics.
- ~~Database engine~~ → Postgres only, local install, localhost-bound.

**Still open:**
1. **Clause taxonomy completeness** — the v0.2 seed list (Payment Terms, Fuel Method, Min Charge, Detention, Liability, Insurance, Claims, Volume Commitment, Service Level, GRI, Termination, Indemnity, Force Majeure, Governing Law) is a starter set. The client should review and add/remove clause types specific to their industry. Easy to extend via `rac.clause_taxonomy` migration.
2. **Favorability rubric authority** — who owns the rubric? Procurement? Legal? Default seed will be conservative shipper-leaning; the client should mark a clause-type owner who can edit the rubric in-app.
3. **Currency** — single-currency reports only in Phase 1, or multi-currency from day one? (Default assumption: single currency, USD, set via `rac.settings.currency_default`.)
4. **Weight breaks** — Do the rate agreements in scope use weight-break tables (e.g. 0–500 lb, 501–1000 lb) or flat per-shipment rates? Both will exist in the schema; we need a sample agreement to confirm parsing.
5. **Service levels** — Are LTL and FTL ever in the same agreement, or always separate files?
6. **Date overlap** — When a carrier has multiple non-superseded agreements over time, pick the one active on the shipment date for analysis? (Default proposed: yes — pick by date, warn if no agreement is active.)
7. **Clause extraction confidence threshold** — below what score should a clause go straight to "needs review" vs. auto-accept? Tunable in Settings.
8. **SOP document** — Who supplies `sop_rac.pdf`? Placeholder for now.
9. **Postgres backup / export** — Is the user expected to manage their own backups, or should the app provide an "Export DB" button (pg_dump under the hood) and a matching restore? Recommend: yes, build it, but Phase 2.
10. **Quantity-billed-text field** — Phase 1: parsed best-effort into `weight` + `pallet_count`, original string retained in `quantity_text`. Revisit after client review.

---

## 15. Change log
- **v0.2** — Major scope expansion based on client feedback:
  - Added **Terms & Conditions Comparison** as a third pillar (§1B, §7.3). Rates alone are insufficient; clause-level comparison is now in scope.
  - Added **Postgres** as the persistence layer (§4). Replaces `uszipcode` and any SQLite plans. Hosts ZIP geo data, carrier directory, agreement history, clause taxonomy, favorability rubric, settings, and saved templates.
  - Tightened **data-privacy stance** (§0, §8.3): no AI ever sees raw client data; AI is BYO-key/endpoint; deterministic path must produce complete reports.
  - **Old/new agreement** detection is now an explicit upload-time flag tied to a user-assigned carrier name, not a filename guess (§3.3).
  - **Nearby-lane radius** moved from a config constant to a Postgres-backed user setting (§4.3).
  - Added agents: `ClauseExtractionAgent`, `ClauseComparisonAgent`, `PersistenceAgent` (§8.1).
  - Added AI data-flow audit test as a CI gate (§11).
  - Acceptance criteria expanded from 10 to 16 items (§12).
- **v0.1** — initial spec, Phase 1 foundation.
- *(Future entries go here as the client clarifies requirements.)*
