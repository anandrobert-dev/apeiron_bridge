# Apeiron Bridge - User Guide

Welcome to **Apeiron Bridge**, a high-performance reconciliation engine designed to bridge data discrepancies across disjointed datasets. This guide will walk you through the end-to-end process of performing a reconciliation.

---

## Step 1: Launch and Module Selection

Upon launching the application, you will see the **Apeiron Bridge** main dashboard.

- **Select Module**: Click on the **SOA Reconciliation** card to begin.
- *Note*: Other modules (Multi-Statement, CSV Conversion) are currently in development or follow similar logic.

## Step 2: File Selection

The file selection screen is where you gather all files required for the bridge.

1. **Add Files**: Use the "Add Excel/CSV Files" button or drag-and-drop files directly into the window.
2. **Custom Naming (NEW)**: Next to each reference file, you will see a text box (e.g., defaulting to `Ref1`). You can type a **Custom Name** (like `OI360` or `Carrier_Data`). This name will be used as the column header in all exports, making your reports much easier to read!
3. **Set Base File (SOA)**: Ensure your Statement of Account is designated as the primary file.
4. **Proceed**: Click **"Next"** to continue.

## Step 3: Map Columns & Configure Rules

This screen defines the "Bridge" between your SOA and your Reference files.

1. **Select Reference**: Use the center dropdown to choose one of your reference files.
2. **Match Key**: Select the column from your SOA and the corresponding column from your Reference that should match (e.g., `Invoice Number`).
3. **Advanced Settings**:
   - **Date Column**: Select the column in your SOA containing dates. This enables the **Age Bucketing** and **Aging Analysis**.
   - **Amount Column**: Select the column in your SOA containing amounts. This enables the **AI Insights Engine** and automatic discrepancy calculation.
4. **Run**: Click **"Run Reconciliation"**. Due to our new **High-Performance Threading**, the app will not freeze even on 200MB+ files. A progress dialog will keep you updated!

## Step 4: Results & AI Insights

Once processing is complete, you will see a multi-tabbed results screen:

1. **📋 Detailed View**: A row-by-row breakdown of every matched invoice across all sources.
2. **⚠️ Discrepancy Report**: Focused strictly on mismatches, showing individual reference amounts, calculated `Delta`, and the precise `Status` (e.g., `MATCH`, `Underpaid (Short)`, `MISSING IN REF`).
3. **🔍 Normalized Comparison**: A view aligning data based on your Multi-File schema (if configured).
4. **🧠 Insights Dashboard (NEW)**: Our AI-powered analysis engine provides:
   - **KPI Summary**: Your overall Match Rate and Health Score.
   - **Status Breakdown**: A quick tally of where things went wrong.
   - **Pattern Detection**: Automatically flags systematic issues (e.g., "Source X consistently underpays by 5%").
   - **Source Reliability**: Grades each of your reference files (A+ down to D) based on accuracy and coverage.
   - **Top Discrepancies**: The highest-impact issues sorted automatically.
   - **Statistical Analysis**: Outlier detection using IQR (Interquartile Range).

## Step 5: Export to Excel

Clicking **"Export to Excel"** generates a beautifully formatted workbook with:

- Dedicated sheets for Detailed View and Discrepancy Report with color-coded highlighters.
- A dedicated **Reconciliation Insights** sheet containing the full dashboard summary.
- A dedicated **Risk Analysis** sheet assigning a 0-100 risk score to every problematic invoice based on age, amount, and missing data!

---
*Developed by Koinonia Technologies. All rights reserved. Proprietary Software.*
