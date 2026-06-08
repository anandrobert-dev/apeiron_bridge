# Apeiron Bridge - User Guide

Welcome to **Apeiron Bridge**, a high-performance reconciliation and carrier-agreement intelligence engine. This guide walks you through the end-to-end usage of the system's core modules.

---

## Module 1: Rate Analysis & Comparison (RA&C)

Compare carrier contracts, audit terms & conditions, and run shipment savings simulations.

### Step 1: Launch and Mode Selection
1. Click the amber **Launch** button on the **Rate Analysis & Comparison** card.
2. Select one of the three options:
   - **Rate Comparison**: Compares lane-by-lane carrier freight rates.
   - **Terms & Conditions Comparison**: Audits contract clauses, accessorial schedules, and payment terms.
   - **Rate Analysis**: Audits historical shipments against carrier agreements.

### Step 2: Upload Agreements (Rate & T&C)
1. Drag and drop two or more carrier contract files (Excel, PDF, Word, or Scanned Images).
2. Input metadata for each file:
   - **Carrier Name**: Auto-completes from the Postgres DB or accepts new entries.
   - **Version Flag**: Choose `New`, `Old / superseded`, or `N/A`.
   - **Effective Dates**: Optional date bounds (used to detect expiration).
   - **Service Mode**: Select LTL, FTL, Parcel, Ocean, etc.
3. Click **Next** to run the background parser.

### Step 3: Column Mapping & Clause Review
1. If a rate sheet format is unknown, map columns (e.g. Origin Zip, Destination Zip, Slabs, and Rates) using the visual mapper.
2. In the **Clause Review** screen, inspect the extracted terms. Correct, accept, or reject specific clauses.

### Step 4: Configure Rules & Run
1. Set the **Comparison Configuration**:
   - **Nearby-Lane Matching**: Uses geographic zip codes to find nearby pricing if an exact lane is missing.
   - **Baseline Carrier**: Choose a carrier to calculate relative price deltas against.
   - **Clause Favorability Rubric**: Select the rule set for grading payment terms, accessorials, etc.
2. Click **Run Comparison** to open the dashboard.

### Step 5: Auditing Shipments (Rate Analysis)
1. Select the **Rate Analysis** mode from the starting screen.
2. Upload your shipment log (CSV/Excel) and map fields (BOL #, Carrier, Origin/Destination Zip, Weight, Pallets, Billed Freight, Billed Fuel).
3. Select the parsed carrier agreements to check.
4. Click **Run Analysis** to find savings and review the fully loaded cost comparison dashboard.

---

## Module 2: SOA Reconciliation

Audit Statement of Account (SOA) invoices against internal ledger reports.

### Step 1: File Selection
1. Launch the **SOA Reconciliation** module.
2. Drag and drop your files. Specify the primary statement by checking the **Main File (SOA)** radio button.
3. Type custom names next to reference files to display reader-friendly column headers in your report.
4. Set the match columns (e.g. `Invoice Number`, `Date`, `Amount`).
5. Choose **"RUN RECONCILIATION"** to execute immediately, or **"ADVANCE MAPPING"** to filter fields manually.

### Step 2: Results & AI Insights
1. **📋 Detailed View**: Row-by-row mapping of all matched invoices.
2. **⚠️ Discrepancy Report**: View underpaid, overpaid, and missing invoices.
3. **🧠 Insights Dashboard**:
   - **Health Score**: A 0-100 grade based on discrepancy magnitude.
   - **Risk Scoring**: Assigns priority values (0-100) based on age, amount, and status severity.
   - **Pattern Detection**: Detects systematic fees, rounding, or underpayment percentages.
   - **Source Reliability**: Grades reference sources (A+ to D) for coverage and accuracy.

---

## Module 3: Multi-File Comparison

Sequence and match records across 2 to 5 distinct spreadsheets.

1. Add your files to the dashboard.
2. Drag and drop rows (or use `Alt + Up/Down`) to define processing sequence.
3. Map join keys and select fields to return.
4. Save mappings as **Templates** to instantly automate future runs.

---

## Exporting Reports
Click **Export to Excel** or **Export to PDF** on any results screen. Output files will be generated in `Downloads/apeiron_output`.

---
*Developed by Koinonia Technologies. All rights reserved.*
