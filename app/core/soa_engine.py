import pandas as pd
import numpy as np
import datetime
import os

class SOAEngine:
    """
    Ported logic from Oi360 RecoWorker with "Deep Analysis" enhancements.
    Handles exact reconciliation, age bucketing, duplicate detection,
    amount mismatch highlighting, and generates a structured Discrepancy Report.
    """
    def __init__(self, soa_df, soa_match_col, date_col, amount_col, ref_configs, mode="SOA", **kwargs):
        """
        ref_configs: List of tuples (ref_df, match_col, return_cols, ref_name)
        kwargs: schema_config, path_mapping (for multi-file schema comparison)
        """
        self.soa_df = soa_df.copy()
        self.soa_match = soa_match_col
        self.date_col = date_col
        self.amount_col = amount_col
        self.ref_configs = ref_configs # List of (df, match_col, return_cols, ref_name)
        self.mode = mode # "SOA" or "MULTI"
        self.schema_config = kwargs.get("schema_config", [])
        self.path_mapping = kwargs.get("path_mapping", {})
        
        self.log_messages = []
        self.errors = []
        self.results_dir = os.path.join(os.getcwd(), "reconciliation_results")
        os.makedirs(self.results_dir, exist_ok=True)

    def log(self, msg):
        print(f"[SOAEngine] {msg}")
        self.log_messages.append(msg)

    def run(self):
        """
        Executes the reconciliation logic.
        Returns: (df_result, excel_filename)
        """
        df_result = self.soa_df.copy()
        df_schema_report = pd.DataFrame()
        
        # Helper: Clean function
        def clean_match_value(val):
            s = str(val).strip()
            if s.startswith("'"):
                s = s[1:]
            
            # Handle pandas float string conversion (e.g., "123.0")
            if s.endswith('.0'):
                s = s[:-2]
                
            if s.isdigit() or (s and s.lstrip('0').isdigit()):
                s = s.lstrip('0') or '0'
            return s.upper()

        # --- 1. Age Bucket Logic ---
        original_date_col_values = None
        if self.date_col and self.date_col in df_result.columns:
            original_date_col_values = df_result[self.date_col].copy()
            try:
                today = pd.to_datetime(datetime.datetime.today())
                temp_dates = pd.to_datetime(
                    df_result[self.date_col], errors='coerce', format='mixed', dayfirst=True
                )
                df_result['Age (Days)'] = (today - temp_dates).dt.days

                def bucket(days):
                    if pd.isna(days): return "Unknown"
                    elif days <= 15: return "0-15"
                    elif days <= 30: return "16-30"
                    elif days <= 60: return "31-60"
                    elif days <= 90: return "61-90"
                    elif days <= 120: return "91-120"
                    else: return "121+"

                df_result['Age Bucket'] = df_result['Age (Days)'].apply(bucket)
                df_result.insert(0, 'Age Bucket', df_result.pop('Age Bucket'))
                df_result.insert(1, 'Age (Days)', df_result.pop('Age (Days)'))
                df_result[self.date_col] = original_date_col_values
            except Exception as e:
                self.log(f"Age Bucket Warning: {e}")
                if original_date_col_values is not None:
                    df_result[self.date_col] = original_date_col_values
        
        # Clean SOA match column
        soa_clean_col = f"_clean_{self.soa_match}"
        df_result[soa_clean_col] = df_result[self.soa_match].astype(str).apply(clean_match_value)
        
        # Track duplicate counts per ref for the Duplicate Summary column
        duplicate_counts = {}
        ref_names_ordered = []
        
        # --- DEEP ANALYSIS: Data Collection ---
        all_ref_entries = [] # List of dicts: {key, amount, source}
        all_ref_field_entries = []  # For Deep Analysis field comparison
        comparable_fields = {}  # {field_name_lower: (soa_col, ref_col)}

        # --- 3. Matching Logic ---
        # We need to preserve track of match sources for the detailed view
        soa_match_values_cleaned = df_result[soa_clean_col].tolist()
        match_sources_dict = {k: [] for k in soa_match_values_cleaned}

        for idx, config in enumerate(self.ref_configs):
            if not config: continue
            
            ref_df, ref_match_col, return_cols, ref_name = config
            ref_names_ordered.append(ref_name)
            
            self.log(f"Matching {ref_name} on {ref_match_col}")
            
            try:
                if ref_match_col not in ref_df.columns:
                    self.log(f"Skipping {ref_name}: Column {ref_match_col} not found.")
                    continue

                # --- CRITICAL: Strict Column Filtering First ---
                # As per request: "dont compare any column that we have not asked for"
                # We ONLY configure: Match Column + Return Columns.
                # All other columns (like "TERM" or random ones) must be DROPPED immediately.
                
                ref_cols_to_keep = [ref_match_col] + list(return_cols)
                ref_cols_to_keep = list(dict.fromkeys(ref_cols_to_keep)) # Ensure unique
                
                # Identify Amount Column FIRST (before dropping) only if we need it for deep analysis
                ref_amount_col = None
                
                ref_cols_lower = {c: c.lower().strip() for c in ref_df.columns}
                # Priority 1: Exact matches
                priority_exact = ['invoice total', 'open amount', 'total amount', 'net amount',
                                  'amount', 'total', 'invoice amount', 'inv total', 'inv amount',
                                  'balance', 'amount due', 'payment amount']
                for target in priority_exact:
                    for col, col_lower in ref_cols_lower.items():
                        if col_lower == target:
                            ref_amount_col = col
                            break
                    if ref_amount_col: break
                
                # Priority 2: Columns ending with key financial terms
                if not ref_amount_col:
                    ending_keywords = ['total', 'amount', 'amt', 'balance']
                    for kw in ending_keywords:
                        for col, col_lower in ref_cols_lower.items():
                            if col_lower.endswith(kw):
                                ref_amount_col = col
                                break
                        if ref_amount_col: break
                
                # Priority 3: Contains keyword (last resort)
                if not ref_amount_col:
                    fallback_keywords = ['total', 'amount', 'amt', 'price', 'cost', 'value', 'sum']
                    for kw in fallback_keywords:
                        for col, col_lower in ref_cols_lower.items():
                            if kw in col_lower:
                                ref_amount_col = col
                                break
                        if ref_amount_col: break
                
                if ref_amount_col:
                    self.log(f"Found amount column in {ref_name}: {ref_amount_col}")

                # Determine strict subset of columns to keep
                cols_needed = ref_cols_to_keep.copy()
                if ref_amount_col and ref_amount_col not in cols_needed:
                    cols_needed.append(ref_amount_col)
                
                # Prepare Ref DF (Strict Subset)
                ref_subset = ref_df[cols_needed].copy()
                
                # Prepare Clean Key
                ref_clean_col = f"_clean_{ref_name}_{ref_match_col}"
                ref_subset[ref_clean_col] = ref_subset[ref_match_col].astype(str).apply(clean_match_value)
                
                # --- DEEP ANALYSIS: Collect Amounts ---
                for _, row in ref_subset.iterrows():
                    key = row[ref_clean_col]
                    if ref_amount_col:
                        amt = self._to_float(row[ref_amount_col])
                        if amt is not None:
                            all_ref_entries.append({
                                "key": key,
                                "amount": amt,
                                "source": ref_name
                            })

                # --- MERGE LOGIC: OUTER JOIN ---
                # Request: "missing in SOA" -> We need invoices in Ref but not in SOA.
                
                extract_cols = list(return_cols)
                # MANDATORY: Always include match key in output
                if ref_match_col not in extract_cols:
                    extract_cols.insert(0, ref_match_col)
                
                # Rename for Merge (Prefixing)
                ref_extract = ref_subset[[ref_clean_col] + extract_cols].copy()
                rename_map = {c: f"{ref_name}_{c}" for c in extract_cols}
                rename_map[ref_clean_col] = ref_clean_col
                ref_extract = ref_extract.rename(columns=rename_map)
                
                # Perform MERGE
                # SOA mode -> Left Join (Strict)
                # MULTI mode -> Outer Join (Comprehensive)
                merge_how = 'left' if self.mode == "SOA" else 'outer'
                
                df_result = pd.merge(
                    df_result, 
                    ref_extract, 
                    left_on=soa_clean_col, 
                    right_on=ref_clean_col, 
                    how=merge_how,
                    suffixes=('', '_REF')
                )
                
                # Coalesce keys ONLY in MULTI mode (to build master list)
                if self.mode == "MULTI":
                    df_result[soa_clean_col] = df_result[soa_clean_col].fillna(df_result[ref_clean_col])
                
                # Update Match Sources tracking for existing keys
                first_ret_col = f"{ref_name}_{extract_cols[0]}"
                if first_ret_col in df_result.columns:
                    match_mask = df_result[first_ret_col].notna()
                    matched_indices = df_result.index[match_mask]
                    
                    for i in matched_indices:
                        key = df_result.at[i, soa_clean_col]
                        if key not in match_sources_dict:
                            match_sources_dict[key] = []
                        if ref_name not in match_sources_dict[key]:
                            match_sources_dict[key].append(ref_name)
                
                # Count duplicates
                ref_value_counts = ref_subset[ref_clean_col].value_counts().to_dict()
                ref_dup_counts = {}
                # Only need counts for SOA keys
                current_keys = df_result[soa_clean_col].unique()
                for k in current_keys:
                    ref_dup_counts[k] = ref_value_counts.get(k, 0)
                duplicate_counts[ref_name] = ref_dup_counts

                # Add Match Count column
                match_count_col = f"{ref_name}_Match_Count"
                df_result[match_count_col] = df_result[soa_clean_col].map(lambda v: ref_dup_counts.get(v, 0))
                
                # Drop temp col
                if ref_clean_col in df_result.columns and ref_clean_col != soa_clean_col:
                    df_result.drop(columns=[ref_clean_col], inplace=True)
                    
            except Exception as e:
                import traceback
                error_msg = f"{ref_name}: {str(e)}\n{traceback.format_exc()}"
                self.log(f"Error matching {ref_name}: {e}")
                self.errors.append(error_msg)

        # Construct Match Source Column
        # Re-generate from dict for all keys in final df
        df_result["Match Source"] = [
            ", ".join(match_sources_dict.get(val, []))
            for val in df_result[soa_clean_col].values
        ]
        
        # Duplicate Summary Column
        if ref_names_ordered:
            dup_summary_data = []
            for soa_val in df_result[soa_clean_col].values:
                parts = []
                for rname in ref_names_ordered:
                    count = duplicate_counts.get(rname, {}).get(soa_val, 0)
                    if count == 0: parts.append(f"{rname}: no entry")
                    elif count == 1: parts.append(f"{rname}: 1x")
                    else: parts.append(f"{rname}: {count}x")
                dup_summary_data.append(", ".join(parts))
            df_result["Duplicate Summary"] = dup_summary_data
            
        # Cleanup
        # Backfill removed (Left Join)
        if self.mode == "MULTI" and self.soa_match in df_result.columns:
             df_result[self.soa_match] = df_result[self.soa_match].fillna(df_result[soa_clean_col])

        if soa_clean_col in df_result.columns:
            df_result.drop(columns=[soa_clean_col], inplace=True)

        # Date Cleanup
        date_keywords = ['date', 'dt', 'dated']
        for col in df_result.columns:
            if any(kw in col.lower() for kw in date_keywords):
                try:
                    df_result[col] = df_result[col].astype(str).str.replace(r'\s+00:00:00$', '', regex=True)
                    df_result[col] = df_result[col].replace('nan', '')
                    df_result[col] = df_result[col].replace('NaT', '')
                except: pass

        # ==================================================================================
        # --- 7. DEEP ANALYSIS: Vectorized Discrepancy Calculation ---
        # ==================================================================================
        df_discrepancy = pd.DataFrame()
        
        if self.amount_col and self.amount_col in self.soa_df.columns:
            # A. Aggregate SOA
            soa_agg_df = self.soa_df.copy()
            # Must clean keys again from source (since we modified df_result but better safe)
            soa_clean_key_temp = f"_clean_key_{self.soa_match}"
            soa_agg_df[soa_clean_key_temp] = soa_agg_df[self.soa_match].astype(str).apply(clean_match_value)
            
            # Helper to clean amount for summing
            def clean_amt(x):
                f = self._to_float(x)
                return f if f is not None else 0.0
            
            soa_agg_df['__amt__'] = soa_agg_df[self.amount_col].apply(clean_amt)
            
            grouped_soa = soa_agg_df.groupby(soa_clean_key_temp).agg(
                Total_SOA_Amount=('__amt__', 'sum')
            ).reset_index().rename(columns={soa_clean_key_temp: 'key'})

            # B. Aggregate Refs
            df_ref_agg = pd.DataFrame(all_ref_entries)
            if not df_ref_agg.empty:
                grouped_ref = df_ref_agg.groupby('key').agg(
                    Total_Ref_Amount=('amount', 'sum'),
                    Ref_Sources=('source', lambda x: ', '.join(sorted(set(x)))),
                    Ref_Count=('source', 'count')
                ).reset_index()
            else:
                grouped_ref = pd.DataFrame(columns=['key', 'Total_Ref_Amount', 'Ref_Sources', 'Ref_Count'])

            # C. Merge (Left for SOA, Outer for MULTI)
            merge_how = 'left' if self.mode == "SOA" else 'outer'
            df_merged = pd.merge(grouped_soa, grouped_ref, on='key', how=merge_how)
            
            # Label adjustment
            base_label = "SOA Amount" if self.mode == "SOA" else "Master Amount"
            invoice_label = "Invoice #" if self.mode == "SOA" else "ID / Key"
            df_merged['Total_Ref_Amount'] = df_merged['Total_Ref_Amount'].fillna(0.0)
            df_merged['Ref_Count'] = df_merged['Ref_Count'].fillna(0).astype(int)
            df_merged['Ref_Sources'] = df_merged['Ref_Sources'].fillna('-')
            
            # D. Calc Delta and Status
            df_merged['Total_SOA_Amount'] = df_merged['Total_SOA_Amount'].round(2)
            df_merged['Total_Ref_Amount'] = df_merged['Total_Ref_Amount'].round(2)
            df_merged['Delta'] = (df_merged['Total_SOA_Amount'] - df_merged['Total_Ref_Amount']).round(2)
            
            def classify(row):
                d = row['Delta']
                s_amt = row['Total_SOA_Amount']
                r_amt = row['Total_Ref_Amount']
                
                # Tolerance
                if abs(d) < 0.01: return "MATCH"
                
                if s_amt == 0 and r_amt > 0: return "MISSING IN SOA"
                if s_amt > 0 and r_amt == 0: return "MISSING IN REF"
                
                if d > 0: return "Underpaid (Short)"
                else: return "Overpaid (Excess)"
            
            df_merged['Status'] = df_merged.apply(classify, axis=1)
            
            # Rename for display
            df_discrepancy = df_merged.rename(columns={
                'key': invoice_label,
                'Total_SOA_Amount': base_label,
                'Total_Ref_Amount': 'Ref Total'
            })
            
            # --- FIELD-LEVEL COMPARISON ---
            if comparable_fields and all_ref_field_entries:
                df_ref_fields = pd.DataFrame(all_ref_field_entries)
                
                # For each invoice key, take the first ref entry's field values
                # (if multiples, use first; they should be consistent per invoice)
                if not df_ref_fields.empty:
                    df_ref_first = df_ref_fields.groupby('key').first().reset_index()
                    
                    # Get SOA field values (first per key)
                    soa_field_df = self.soa_df.copy()
                    soa_clean_key_temp2 = '_ckey_'
                    soa_field_df[soa_clean_key_temp2] = soa_field_df[self.soa_match].astype(str).apply(clean_match_value)
                    soa_field_first = soa_field_df.groupby(soa_clean_key_temp2).first().reset_index()
                    soa_field_first = soa_field_first.rename(columns={soa_clean_key_temp2: 'key'})
                    
                    # Add comparison columns to discrepancy report
                    mismatched_fields_list = []
                    
                    for field_key, (soa_col, ref_col) in comparable_fields.items():
                        ref_field_col = f"ref_{field_key}"
                        soa_display = f"SOA {soa_col}"
                        ref_display = f"Ref {ref_col}"
                        
                        # Merge SOA field values
                        if soa_col in soa_field_first.columns:
                            soa_vals = soa_field_first[['key', soa_col]].rename(columns={soa_col: soa_display})
                            df_discrepancy = pd.merge(df_discrepancy, soa_vals, left_on='Invoice #', right_on='key', how='left')
                            if 'key' in df_discrepancy.columns and 'Invoice #' in df_discrepancy.columns:
                                df_discrepancy.drop(columns=['key'], inplace=True, errors='ignore')
                        
                        # Merge Ref field values
                        if ref_field_col in df_ref_first.columns:
                            ref_vals = df_ref_first[['key', ref_field_col]].rename(columns={ref_field_col: ref_display})
                            df_discrepancy = pd.merge(df_discrepancy, ref_vals, left_on='Invoice #', right_on='key', how='left')
                            if 'key' in df_discrepancy.columns and 'Invoice #' in df_discrepancy.columns:
                                df_discrepancy.drop(columns=['key'], inplace=True, errors='ignore')
                    
                    # Build Mismatched Fields column
                    def find_mismatches(row):
                        mismatches = []
                        for field_key, (soa_col, ref_col) in comparable_fields.items():
                            soa_display = f"SOA {soa_col}"
                            ref_display = f"Ref {ref_col}"
                            if soa_display in row.index and ref_display in row.index:
                                soa_val = str(row[soa_display]).strip().lower() if pd.notna(row[soa_display]) else ""
                                ref_val = str(row[ref_display]).strip().lower() if pd.notna(row[ref_display]) else ""
                                # Clean date strings for comparison
                                soa_val = soa_val.replace(' 00:00:00', '').replace('nan', '').replace('nat', '')
                                ref_val = ref_val.replace(' 00:00:00', '').replace('nan', '').replace('nat', '')
                                if soa_val and ref_val and soa_val != ref_val:
                                    mismatches.append(soa_col)
                        # Also check amount
                        if abs(row.get('Delta', 0)) >= 0.01:
                            mismatches.append('Amount')
                        return ', '.join(mismatches) if mismatches else '✓ All Match'
                    
                    df_discrepancy['Mismatched Fields'] = df_discrepancy.apply(find_mismatches, axis=1)
            
            # Sort order: problems first, then matches
            df_discrepancy['__sort__'] = df_discrepancy.apply(
                lambda r: 0 if r.get('Mismatched Fields', '') != '✓ All Match' else 1, axis=1
            )
            df_discrepancy.sort_values(by=['__sort__', 'Status', 'Delta'], inplace=True)
            df_discrepancy.drop(columns=['__sort__'], inplace=True)

        # ==================================================================================
        # --- 8. SCHEMA COMPARISON / LOGICAL CHECKER (Multi-File Only) ---
        # ==================================================================================
        df_schema_report = pd.DataFrame()
        if self.mode == "MULTI" and self.schema_config:
            self.log("Running Schema Comparison Logic...")
            
            # Ensure labels are defined (might be skipped if amount_col is None)
            base_label = "SOA Amount" if self.mode == "SOA" else "Master Amount"
            invoice_label = "Invoice #" if self.mode == "SOA" else "ID / Key"

            try:
                # Initialize with Master Key
                key_col = invoice_label  # "ID / Key"
                # Find key in df_result (likely renamed or original)
                # It's usually self.soa_match (but filled)
                master_key_series = df_result[self.soa_match] if self.soa_match in df_result.columns else df_result.iloc[:, 0]
                
                schema_data = {key_col: master_key_series}
                
                # Iterate through Schema Fields
                for field in self.schema_config:
                    field_name = field["name"]
                    field_type = field.get("type", "Text")
                    mappings = field.get("mappings", {})
                    
                    values_per_ref = {}
                    
                    # 1. Extract Values
                    for ref_path, col_name in mappings.items():
                        if not col_name: continue
                        
                        ref_name = self.path_mapping.get(ref_path)
                        if not ref_name: continue
                        
                        # Look for column in df_result: {ref_name}_{col_name}
                        target_col = f"{ref_name}_{col_name}"
                        if target_col in df_result.columns:
                            # Clean values based on type
                            raw_values = df_result[target_col].fillna("")
                            if field_type == "Number" or field_type == "Currency":
                                # Try basic float cleaning
                                clean_values = raw_values.apply(lambda x: self._to_float(x) if x != "" else None)
                            else:
                                clean_values = raw_values.astype(str).str.strip()
                            
                            display_col = f"{field_name} ({ref_name})"
                            schema_data[display_col] = clean_values
                            values_per_ref[ref_name] = clean_values
                        else:
                            self.log(f"Schema Warning: Column {target_col} not found in result DF.")

                    # 2. Compare Values (Row-wise)
                    # We need to construct a comparison status column
                    if values_per_ref:
                        status_list = []
                        # Convert to DataFrame for easier row iteration
                        temp_df = pd.DataFrame(values_per_ref)
                        
                        for i, row in temp_df.iterrows():
                            # Filter empty/None values
                            vals = [v for v in row.values if v not in [None, "", np.nan]]
                            
                            if not vals:
                                status_list.append("NO DATA")
                            else:
                                # Check uniqueness
                                unique_vals = set()
                                for v in vals:
                                    if isinstance(v, float):
                                        unique_vals.add(round(v, 2))
                                    else:
                                        unique_vals.add(str(v).upper())
                                
                                if len(unique_vals) == 1:
                                    if len(vals) < len(values_per_ref):
                                        status_list.append("PARTIAL MATCH") # Some refs missing data
                                    else:
                                        status_list.append("MATCH")
                                else:
                                    status_list.append("MISMATCH")
                        
                        schema_data[f"{field_name} Status"] = status_list

                df_schema_report = pd.DataFrame(schema_data)
                
            except Exception as e:
                self.log(f"Schema Comparison Error: {e}")
                import traceback
                traceback.print_exc()

        # --- 9. Excel Generation ---
        output_dir = os.path.join(os.path.expanduser("~"), "Downloads", "apeiron_output")
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"soa_reco_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        
        try:
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                workbook  = writer.book
                header_format = workbook.add_format({'bold': True, 'fg_color': '#404040', 'font_color': '#FFFFFF', 'border': 1})
                mismatch_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
                match_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
                partial_format = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
                dup_format = workbook.add_format({'bg_color': '#E6B8AF', 'font_color': '#000000'}) # Duplicate highlight

                # SHEET 1: Main Details
                df_result.to_excel(writer, index=False, sheet_name='Detailed View')
                
                # SHEET 2: Discrepancy Report
                if not df_discrepancy.empty:
                    df_discrepancy.to_excel(writer, index=False, sheet_name='Discrepancy Report')

                # SHEET 3: Normalized Comparison (Schema)
                if not df_schema_report.empty:
                    df_schema_report.to_excel(writer, index=False, sheet_name='Normalized Comparison')
                    ws3 = writer.sheets['Normalized Comparison']
                    
                    # Format Headers
                    for col_num, value in enumerate(df_schema_report.columns.values):
                        ws3.write(0, col_num, value, header_format)
                        ws3.set_column(col_num, col_num, 20)
                    
                    # Format Status Columns
                    for col_num, col_name in enumerate(df_schema_report.columns):
                        if "Status" in col_name:
                             for row_idx, val in enumerate(df_schema_report[col_name]):
                                 cell_fmt = None
                                 if val == "MISMATCH": cell_fmt = mismatch_format
                                 elif val == "MATCH": cell_fmt = match_format
                                 elif val == "PARTIAL MATCH": cell_fmt = partial_format
                                 
                                 if cell_fmt:
                                     ws3.write(row_idx + 1, col_num, val, cell_fmt)

                # --- Format Sheet 1 (Details) ---
                ws1 = writer.sheets['Detailed View']
                for col_num, value in enumerate(df_result.columns.values):
                    ws1.write(0, col_num, value, header_format)
                
                # Highlight Duplicates
                ref_names = [cfg[3] for cfg in self.ref_configs if cfg]
                all_cols = list(df_result.columns)
                for rname in ref_names:
                    mc_col = f"{rname}_Match_Count"
                    if mc_col in all_cols:
                        mc_col_idx = all_cols.index(mc_col)
                        for row_idx in range(len(df_result)):
                            try:
                                if int(df_result.iloc[row_idx][mc_col]) > 1:
                                    ws1.write(row_idx + 1, mc_col_idx, df_result.iloc[row_idx][mc_col], dup_format)
                            except: pass

                # --- Format Sheet 2 (Discrepancies) ---
                if not df_discrepancy.empty:
                    ws2 = writer.sheets['Discrepancy Report']
                    
                    # Formats
                    fmt_currency = workbook.add_format({'num_format': '#,##0.00'})
                    fmt_red = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006', 'num_format': '#,##0.00'})
                    fmt_green = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'num_format': '#,##0.00'})
                    
                    # Columns
                    cols = df_discrepancy.columns.tolist()
                    idx_soa = cols.index(base_label) if base_label in cols else -1
                    idx_ref = cols.index('Ref Total') if 'Ref Total' in cols else -1
                    idx_delta = cols.index('Delta') if 'Delta' in cols else -1
                    idx_status = cols.index('Status') if 'Status' in cols else -1

                    # Apply Header
                    for col_num, value in enumerate(cols):
                        ws2.write(0, col_num, value, header_format)
                        ws2.set_column(col_num, col_num, 18)

                    # Apply Data Formatting
                    for row_idx, (index, row) in enumerate(df_discrepancy.iterrows()):
                        excel_row = row_idx + 1
                        if idx_soa != -1:
                            ws2.write(excel_row, idx_soa, row[base_label], fmt_currency)
                        ws2.write(excel_row, idx_ref, row['Ref Total'], fmt_currency)
                        
                        # Conditional Delta formatting
                        delta = row['Delta']
                        if delta < -0.01:
                            ws2.write(excel_row, idx_delta, delta, fmt_red)
                        elif delta > 0.01:
                            ws2.write(excel_row, idx_delta, delta, fmt_green)
                        else:
                            ws2.write(excel_row, idx_delta, delta, fmt_currency)
                            
                        # Conditional Status formatting
                        status = row['Status']
                        if "MISSING" in status or "Mismatch" in status or "Underpaid" in status or "Overpaid" in status:
                             ws2.write(excel_row, idx_status, status, mismatch_format)
                        else:
                             ws2.write(excel_row, idx_status, status)
                
                # Sheet 2 Layout - Column adjustment
                if not df_discrepancy.empty:
                    ws2.set_column(0, len(cols)-1, 20)


        except Exception as e:
            self.log(f"Excel Save Error: {e}")
            return df_result, None, df_discrepancy, df_schema_report

        return df_result, filename, df_discrepancy, df_schema_report

    def _to_float(self, val):
        try:
            if pd.isna(val): return None
            val_str = str(val).replace(',', '').replace('$', '').replace(' ', '').strip()
            # Handle accounting negative (123.45) -> -123.45
            if val_str.startswith('(') and val_str.endswith(')'):
                val_str = '-' + val_str[1:-1]
            return float(val_str)
        except:
            return None
