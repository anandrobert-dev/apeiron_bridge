# Standard Operating Procedure (SOP)

## Rate Analysis & Comparison (RA&C) Module

**Apeiron Bridge** includes a powerful Rate Analysis & Comparison (RA&C) module designed to handle carrier rate agreements (numeric rates), Terms & Conditions (T&C contractual clauses), and shipment-level cost analysis. All processing runs strictly locally to guarantee data privacy.

Follow this step-by-step guide to run comparisons and analyses.

---

### Phase 1: Launch & Mode Selection

1. **Launch the Module**
   * On the Welcome Screen, locate the **"Rate Analysis & Comparison"** card and click the amber **Launch** button.

2. **Select Mode**
   * You will see the Mode Selector dashboard with three options:
     * **[ Rate Comparison ]**: Compare numeric rates across carrier agreements.
     * **[ Terms & Conditions Comparison ]**: Compare contractual clauses, payment terms, accessorials, and liability.
     * **[ Rate Analysis ]**: Audit shipment history against carrier agreements to find savings.

---

### Phase 2: Agreement Upload & Parsing (Rate & T&C Comparison)

Rate Comparison and T&C Comparison share a unified upload and parsing workflow.

1. **Upload Carrier Agreements**
   * Click **Add Agreements** to upload 2 or more files (PDF, Word, Excel, CSV, or scanned images).
   * For each file, fill in the metadata:
     * **Carrier Name**: Autocomplete or type the carrier's name (required).
     * **Agreement Version Flag**: Mark as `New`, `Old / superseded`, or `N/A (only version)`. The `Old` and `New` flags trigger rate-increase and clause-change tracking for the same carrier.
     * **Effective Dates**: Optional start/end dates (auto-extracted if possible).
     * **Service Mode**: Dropdown selection (e.g., LTL, FTL, Parcel, Ocean).

2. **Auto-Parsing and Mapping**
   * The background worker extracts rate tables and T&C clauses.
   * If a rate table structure isn't recognized, a **Column Mapping** screen will appear. Map the required columns (Origin Zip/City, Destination Zip/City, Weight Slabs, Rate) to proceed.

3. **Clause Review & Acceptance**
   * A **Clause Review** panel displays the extracted contractual clauses under a structured taxonomy.
   * Review, edit, accept, or reject clauses. Rejected clauses are excluded from the comparisons.

4. **Comparison Configuration**
   * Toggle comparison rules:
     * **Nearby-Lane Matching**: Uses the local Postgres geographic database to match nearby lanes/suburbs if an exact lane matches is missing (uses search radius from settings).
     * **Missing-Lane Detection**: Flags lanes covered by one carrier but omitted by another.
     * **No-Rate Detection**: Highlights lanes with blank, zero, or "on request" rates.
     * **Baseline Carrier**: Choose which carrier to use as the pricing baseline for percentage differences.
     * **Clause Favorability Rubric**: Edit or select the scoring rules to evaluate which carrier terms are shipper-favorable.

5. **Generate Reports**
   * Click **Run Comparison** to open the final dashboard tabs.

---

### Phase 3: Shipment History Upload (Rate Analysis)

Rate Analysis maps actual billed shipments to agreement-defined pricing rules.

1. **Upload Shipment History**
   * Select your historical shipment file (CSV or Excel).
   * Map the required columns: Invoice #, BOL #, Shipment Date, Carrier, Billed Freight, Billed Fuel, Origin Zip, Destination Zip, Weight, Pallets, and Mode.

2. **Select Agreements**
   * Select one or more parsed carrier agreements to compare against your shipment history.

3. **Run Analysis**
   * Click **Run Analysis** to execute the fully-loaded cost engine (calculating hypothetical freight, fuel surcharge, accessorials, and minimums per carrier).

---

### Phase 4: Navigating Results

#### 1. Rate Comparison Dashboard
* **Detailed Rates**: Line-by-line rate comparison across carriers for each lane.
* **Lane Rate Grid**: Pivot grid comparing rates for origins and destinations.
* **Weight Slab Summary**: Side-by-side view of slab-based pricing.
* **Missing Lanes**: Highlights gaps in carrier coverage.
* Color codes: Green represents the cheaper rate, Red represents the more expensive rate, and Grey flags missing/unrated lanes.

#### 2. T&C Comparison Dashboard
* **Clause Coverage Matrix**: Displays which carriers have clauses in each category (silent categories are flagged).
* **Clause Delta**: Highlights text differences for the same clause type between carriers.
* **Favorability Scoring**: Displays calculated scores showing whether clauses favor the shipper or carrier.
* **Change Tracking**: Displays red/green diffs showing changes between `Old` and `New` versions of the same carrier's contract.

#### 3. Rate Analysis Dashboard
* **Shipment Audit**: Computes Billed amount vs. Hypothetical quotes for each carrier.
* **Cheapest Option**: Identifies the lowest-cost carrier for each shipment on a fully loaded basis.
* **Potential Savings**: Aggregates total savings if shipments had been routed optimally.
* **Pattern Analysis**: Identifies lanes where you consistently overpay, carrier win-rates, and rate-creep over time.

---

### Phase 5: Exporting Reports
* **Export to Excel**: Generates formatted workbooks featuring detailed rate comparisons, T&C matrices, and shipment audits.
* **Export to PDF**: Generates executive summaries, charts, and audit dashboards.

---

### Security & AI Configuration
* **Offline First**: All parsing, calculations, and reporting run 100% locally.
* **Data Anonymization**: No raw shipment IDs or full contract text are ever sent to external networks.
* **Optional AI Assistance**: If the user registers a private API key, the app can supply clause-similarity ranking and narrative phrasing using only de-identified, short text snippets.
