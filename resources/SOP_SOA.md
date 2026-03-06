# Standard Operating Procedure (SOP)

## SOA Reconciliation Module

**Apeiron Bridge** is designed to simplify the reconciliation of your Statement of Account (SOA) against multiple Reference files (e.g., system dumps, carrier reports, payment logs).

Follow this step-by-step guide to perform a reconciliation.

---

### Phase 1: Launch & File Selection

1. **Launch the Module**
    * On the Welcome Screen, locate the **"SOA Reconciliation"** card and click the blue **Launch** button.

2. **Add Excel/CSV Files**
    * Click the green **"Add Excel/CSV Files"** button to browse, or simply **drag and drop** your files anywhere onto the list area. You can add as many reference files as you need.

3. **Set the MAIN File (SOA) & Properties**
    * Click the **Radio Button** on the far left of the row you want to act as your primary SOA (Main file).
    * Once selected, the **Date** and **Amount** selection boxes will appear for that file. Select the appropriate columns.
    * *Tip: You can type a custom name (e.g., "Main SOA") into the text box next to the radio button to rename the file for the report.*

4. **Configure Reference Files & Ordering**
    * For every other file in the list, select the column that matches the Master file using the **Match Key / Join Column** dropdown.
    * *Tip: You can click and hold any file row to **drag it up or down** to change the sequence of the report columns.*

5. **Run Reconciliation (Recommended)**
    * Click the purple **"RUN RECONCILIATION"** button to process immediately.
    * *This skips advance mapping and auto-maps all columns!*

6. **Optional: Advance Mapping**
    * Click the dark **"ADVANCE MAPPING"** button only if you need to build normalized schemas or filter specific columns before running.

---

### Phase 2: Advance Mapping (Optional)

Only used if you clicked "ADVANCE MAPPING".

#### 1. Configure Base File (Left Blue Panel)

* **Base File Columns**: This list shows all columns in your SOA.
* **Master ID Column**: Select the column that contains the unique identifier (e.g., **Invoice #**, Reference ID).
* **Date Column**: Select the column containing the Invoice Date (used for Age Bucketing).
* **Amount Column**: Select the column containing the Open Amount (used for Discrepancy checks).

#### 2. Configure Reference Files (Center Green Panel)

* **Select Reference File**: Choose which file you are currently configuring from the dropdown (e.g., `Ref1.xlsx`).
* **Match Column**: Choose the column in this file that matches the SOA's unique identifier (e.g., **Invoice No**).
* **Return Columns**: Select which columns you want to **copy** from this file into your final report.
  * *Tip: Use "Select All" if you want everything.*

#### 3. Schema & Rules (Right Purple Panel)

* **Cross-File Normalization**: Map standard names (like "Tracking_Code") to exact headers across files to align disjointed reports neatly.
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
