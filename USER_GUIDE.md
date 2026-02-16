# Apeiron Bridge - User Guide

Welcome to **Apeiron Bridge**, a high-performance reconciliation engine designed to bridge data discrepancies across disjointed datasets. This guide will walk you through the end-to-end process of performing a reconciliation.

---

## Step 1: Launch and Module Selection

Upon launching the application, you will see the **Apeiron Bridge** main dashboard.

- **Select Module**: Click on the **SOA Reconciliation** card to begin.
- *Note*: Other modules (Multi-Statement, CSV Conversion) are currently in development or follow similar logic.

## Step 2: File Selection

The file selection screen is where you gather all files required for the bridge.

1. **Add Files**:
   - Click **"Add Excel/CSV Files"** to browse your computer.
   - **NEW**: You can now **Drag and Drop** files directly from your folder into the application window.
2. **Review List**: All added files will appear in the central list. You can remove unwanted files by selecting them and clicking **"Remove Selected"**.
3. **Set Base File (SOA)**: Use the dropdown menu at the bottom to designate which file is your **SOA (Statement of Account)**. This is the primary file that others will be matched against.
4. **Proceed**: Click **"Next: Map Columns"** to continue.

## Step 3: Map Columns & Configure Rules

This screen defines the "Bridge" between your SOA and your Reference files.

1. **Select Reference**: Use the center dropdown to choose one of your reference files.
2. **Match Key**:
   - Select the column from your **SOA** (Left) and the corresponding column from your **Reference** (Center) that should match (e.g., `Invoice Number`).
   - Click **"Add Mapping Rule"**.
   - *Optional*: Check **"Enable Partial/Fuzzy Match"** if your invoice numbers have different formats (e.g., prefix differences).
3. **Advanced Settings**:
   - **Date Column**: Select the column in your SOA containing dates. This enables the **Age Bucketing** feature (0-15, 16-30 days, etc.).
   - **Amount Column**: Select the column in your SOA containing amounts. This enables **Mismatch Highlighting** in the final report.
4. **Final Step**: Click **"Run Reconciliation"**.

## Step 4: Results & Export

Once processing is complete (using the high-speed **SOAEngine**):

1. **Preview**: A summary of matches will be displayed in the results table.
2. **Excel Report**: The system automatically generates a detailed report in your `output/` folder.
   - **Age Bucket**: Invoices are automatically categorized by age.
   - **Match Source**: Indicates which reference file(s) matched the record.
   - **Variance Highlighting**: Amounts that do not match between files are highlighted in **RED** for immediate investigation.
   - **Amount Difference**: A dedicated column shows the exact variance found.

---
*Developed by Koinonia Technologies. All rights reserved. Proprietary Software.*
