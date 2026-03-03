# Standard Operating Procedure (SOP)

## SOA Reconciliation Module

**Apeiron Bridge** is designed to simplify the reconciliation of your Statement of Account (SOA) against multiple Reference files (e.g., system dumps, carrier reports, payment logs).

Follow this step-by-step guide to perform a reconciliation.

---

### Phase 1: Launch & File Selection

1. **Launch the Module**
    * On the Welcome Screen, locate the **"SOA Reconciliation"** card (left side).
    * Click the green **"Launch"** button.

2. **Select Base File (SOA)**
    * Click **"Browse Base File"**.
    * Select your primary Statement of Account file (Excel or CSV).
    * *Tip: This is the "Master" file that determines what you are looking for.*

3. **Select Reference Files**
    * Click **"Add Reference File(s)"**.
    * Select one or more files you want to check against the SOA.
    * *You can add multiple files (e.g., Ref1, Ref2, Ref3).*

4. **Proceed**
    * Click **"Next: Configure Columns"** to move to the Mapping Screen.

---

### Phase 2: Mapping & Configuration

The Mapping Screen is divided into three colorful panels. You can resize them by dragging the dividers.

#### 1. Configure Base File (Left Blue Panel)

* **Base File Columns**: This list shows all columns in your SOA.
* **Action**: Select the column that contains the unique identifier (e.g., **Invoice #**, Reference ID).
* **Date Column**: Select the column containing the Invoice Date (used for Age Bucketing).
* **Amount Column**: Select the column containing the Open Amount (used for Discrepancy checks).

#### 2. Configure Reference Files (Center Green Panel)

* **Select Reference File**: Choose which file you are currently configuring from the dropdown (e.g., `Ref1.xlsx`).
* **Match Column**: Choose the column in this file that matches the SOA's unique identifier (e.g., **Invoice No**).
* **Return Columns**: Select which columns you want to **copy** from this file into your final report (e.g., Status, Remarks, Payment Date).
  * *Tip: Use "Select All" if you want everything, or pick specific relevant fields.*

**IMPORTANT:** If you have multiple reference files:

1. Select `Ref1` in the dropdown → Configure match/return columns.
2. Switch dropdown to `Ref2` → Configure match/return columns for Ref2.
3. Each file has its own independent settings.

#### 3. Rules & Templates (Right Purple Panel)

* **Fuzzy Match**: Check "Enable Partial/Fuzzy Match" ONLY if your invoice numbers are messy (e.g., `INV-100` vs `100`). For most financial data, leave this **unchecked** (Exact Match).
* **Save Ref Mapping**: Click this button to confirm your settings for the current reference file.
* **Templates**:
  * **Save Tmplt**: Save your current configuration (for all files) to use again later.
  * **Load Tmplt**: Load a previously saved configuration.

---

### Phase 3: Execution & Review

1. **Run Reconciliation**
    * Click the **"Run Reconciliation"** button at the bottom right.
    * The system will process the data. This may take a few seconds depending on file size.

2. **View Results**
    * The Results Screen has two tabs:
        * **Detailed View**: Shows your original SOA data merged with the found columns from all Reference files.
        * **Discrepancy Report**: A high-level summary showing matches, accidental duplicates, and amount variances (Underpaid vs Overpaid).

3. **Export**
    * Click **"Export to Excel"** to save the final report to your `Downloads/apeiron_output` folder.

---

### Troubleshooting

* **"Partial Reconciliation Errors"**: If you see this popup, it means one of your files could not be processed. Check the error message for details (e.g., "File corrupt", "Column missing").
* **No Matches?**: Ensure you selected the correct "Match Column" for both the Base and Reference files. Check for leading zeros or spaces in your data.
