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
        self.soa_df = soa_df
        self.soa_match = soa_match_col
        self.date_col = date_col
        self.amount_col = amount_col
        self.ref_configs = ref_configs
        self.mode = mode
        self.schema_config = kwargs.get("schema_config", [])
        self.path_mapping = kwargs.get("path_mapping", {})
        
        self.log_messages = []
        self.errors = []
        self.results_dir = os.path.join(os.getcwd(), "reconciliation_results")
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Performance: progress callback and cancellation support
        self._progress_callback = None  # Set by worker: fn(pct, msg)
        self._cancel_check = None       # Set by worker: fn() -> bool

    def _report_progress(self, pct, msg):
        """Report progress if callback is set."""
        if self._progress_callback:
            self._progress_callback(pct, msg)

    def _is_cancelled(self):
        """Check if operation should be cancelled."""
        return self._cancel_check() if self._cancel_check else False

    def log(self, msg):
        print(f"[SOAEngine] {msg}")
        self.log_messages.append(msg)

    def run(self):
        """
        Executes the reconciliation logic.
        Returns: (df_result, excel_filename, df_disc, df_schema, insights)
        """
        df_result = self.soa_df.copy()
        df_schema_report = pd.DataFrame()
        insights = {}
        
        self._report_progress(10, "Preparing data...")
        
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
                    elif days <= 30: return "0-30"
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
        
        self._report_progress(15, "Matching references...")
        
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
                
                # --- DEEP ANALYSIS: Collect Amounts (VECTORIZED) ---
                if ref_amount_col:
                    amt_series = ref_subset[ref_amount_col].apply(self._to_float)
                    valid_mask = amt_series.notna()
                    if valid_mask.any():
                        keys = ref_subset.loc[valid_mask, ref_clean_col].values
                        amounts = amt_series[valid_mask].values
                        new_entries = [
                            {"key": k, "amount": a, "source": ref_name}
                            for k, a in zip(keys, amounts)
                        ]
                        all_ref_entries.extend(new_entries)

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
        # --- 7. DEEP ANALYSIS: Per-Ref Discrepancy Calculation ---
        # ==================================================================================
        self._report_progress(50, "Computing discrepancies...")
        df_discrepancy = pd.DataFrame()
        
        if self.amount_col and self.amount_col in self.soa_df.columns:
            # A. Aggregate SOA amounts per key
            soa_agg_df = self.soa_df.copy()
            soa_clean_key_temp = f"_clean_key_{self.soa_match}"
            soa_agg_df[soa_clean_key_temp] = soa_agg_df[self.soa_match].astype(str).apply(clean_match_value)
            
            def clean_amt(x):
                f = self._to_float(x)
                return f if f is not None else 0.0
            
            soa_agg_df['__amt__'] = soa_agg_df[self.amount_col].apply(clean_amt)
            
            grouped_soa = soa_agg_df.groupby(soa_clean_key_temp).agg(
                Total_SOA_Amount=('__amt__', 'sum')
            ).reset_index().rename(columns={soa_clean_key_temp: 'key'})

            # B. Aggregate Refs PER SOURCE (not summed across all refs)
            df_ref_agg = pd.DataFrame(all_ref_entries)
            
            # Label adjustment
            base_label = "SOA Amount" if self.mode == "SOA" else "Master Amount"
            invoice_label = "Invoice #" if self.mode == "SOA" else "ID / Key"
            
            # Start building discrepancy from SOA
            df_discrepancy = grouped_soa.rename(columns={
                'key': invoice_label,
                'Total_SOA_Amount': base_label
            })
            df_discrepancy[base_label] = df_discrepancy[base_label].round(2)
            
            # C. Build per-ref amount columns
            ref_amount_cols = []  # Track column names for per-ref amounts
            if not df_ref_agg.empty:
                for ref_name in ref_names_ordered:
                    ref_subset = df_ref_agg[df_ref_agg['source'] == ref_name]
                    if ref_subset.empty:
                        continue
                    
                    # Sum per key for this specific ref
                    ref_grouped = ref_subset.groupby('key').agg(
                        ref_amount=('amount', 'sum')
                    ).reset_index()
                    
                    col_name = f"{ref_name} Amount"
                    ref_amount_cols.append(col_name)
                    ref_grouped = ref_grouped.rename(columns={
                        'ref_amount': col_name,
                        'key': invoice_label
                    })
                    ref_grouped[col_name] = ref_grouped[col_name].round(2)
                    
                    # Merge into discrepancy
                    merge_how = 'left' if self.mode == "SOA" else 'outer'
                    df_discrepancy = pd.merge(df_discrepancy, ref_grouped, on=invoice_label, how=merge_how)
                
                # Build Ref Sources column
                ref_sources_agg = df_ref_agg.groupby('key').agg(
                    Ref_Sources=('source', lambda x: ', '.join(sorted(set(x)))),
                    Ref_Count=('source', 'count')
                ).reset_index().rename(columns={'key': invoice_label})
                df_discrepancy = pd.merge(df_discrepancy, ref_sources_agg, on=invoice_label, how='left')
            
            df_discrepancy['Ref_Sources'] = df_discrepancy.get('Ref_Sources', pd.Series(['-'] * len(df_discrepancy))).fillna('-')
            df_discrepancy['Ref_Count'] = df_discrepancy.get('Ref_Count', pd.Series([0] * len(df_discrepancy))).fillna(0).astype(int)
            
            # D. Calculate Delta and Status (per-ref comparison)
            def classify_per_ref(row):
                soa_amt = row[base_label] if pd.notna(row[base_label]) else 0.0
                
                # Collect all present ref amounts
                ref_amounts = {}
                for col in ref_amount_cols:
                    if col in row.index and pd.notna(row[col]):
                        ref_amounts[col] = row[col]
                
                # No refs at all
                if not ref_amounts:
                    if abs(soa_amt) < 0.01:
                        return 0.0, "NO DATA"
                    else:
                        return soa_amt, "MISSING IN REF"
                
                # SOA is zero/missing but refs have data
                if abs(soa_amt) < 0.01 and any(abs(v) >= 0.01 for v in ref_amounts.values()):
                    max_ref = max(abs(v) for v in ref_amounts.values())
                    return -max_ref, "MISSING IN SOA"
                
                # Compare each ref against SOA
                deltas = {col: round(soa_amt - amt, 2) for col, amt in ref_amounts.items()}
                max_abs_delta = max(abs(d) for d in deltas.values())
                
                # All refs match SOA
                if max_abs_delta < 0.01:
                    if len(ref_amounts) < len(ref_amount_cols):
                        return 0.0, "PARTIAL (Some Refs Missing)"
                    return 0.0, "MATCH"
                
                # Some refs disagree
                # Use the largest absolute deviation as the reported delta
                worst_delta = max(deltas.values(), key=abs)
                
                if len(ref_amounts) < len(ref_amount_cols):
                    # Some refs missing, some present disagree
                    return worst_delta, "MISMATCH (Partial)"
                
                if worst_delta > 0:
                    return worst_delta, "Underpaid (Short)"
                else:
                    return worst_delta, "Overpaid (Excess)"
            
            # Apply classification
            results = df_discrepancy.apply(classify_per_ref, axis=1)
            df_discrepancy['Delta'] = [r[0] for r in results]
            df_discrepancy['Status'] = [r[1] for r in results]
            
            # --- FIELD-LEVEL COMPARISON ---
            if self.mode == "SOA":
                def compare_fields(row):
                    mismatches = []
                    partial_matches = []
                    
                    # Check Delta first
                    if abs(row.get('Delta', 0)) >= 0.01:
                        mismatches.append('Amount')

                    # Map lowercase SOA column names to their exact casing
                    soa_cols_lower = {str(c).lower().strip(): c for c in self.soa_df.columns}
                    
                    for config in self.ref_configs:
                        if not config: continue
                        _, ref_match_col, return_cols, ref_name = config
                        
                        for ref_col in return_cols:
                            # Does this ref col have a matching SOA col?
                            ref_col_lower = str(ref_col).lower().strip()
                            if ref_col_lower in soa_cols_lower and ref_col_lower != str(ref_match_col).lower().strip():
                                soa_target_col = soa_cols_lower[ref_col_lower]
                                ref_target_col = f"{ref_name}_{ref_col}"
                                
                                if soa_target_col in row.index and ref_target_col in row.index:
                                    soa_val = str(row[soa_target_col]).strip().lower() if pd.notna(row[soa_target_col]) else ""
                                    ref_val = str(row[ref_target_col]).strip().lower() if pd.notna(row[ref_target_col]) else ""
                                    
                                    # Clean up common empty string representations
                                    soa_val = soa_val.replace(' 00:00:00', '').replace('nan', '').replace('nat', '')
                                    ref_val = ref_val.replace(' 00:00:00', '').replace('nan', '').replace('nat', '')
                                    
                                    if soa_val and ref_val and soa_val != ref_val:
                                        # Check for partial match logic (e.g. CARDINAL vs CARDINAL LOGISTICS)
                                        if ref_val in soa_val or soa_val in ref_val:
                                            if soa_target_col not in partial_matches:
                                                partial_matches.append(soa_target_col)
                                        else:
                                            if soa_target_col not in mismatches:
                                                mismatches.append(soa_target_col)
                                            
                    result_parts = []
                    if mismatches:
                        result_parts.append("Mismatch: " + ", ".join(mismatches))
                    if partial_matches:
                        result_parts.append("Partial: " + ", ".join(partial_matches))
                    
                    return " | ".join(result_parts) if result_parts else "✓ All Match"
                
                df_discrepancy['Mismatched Fields'] = df_discrepancy.apply(compare_fields, axis=1)
            
            # Sort: problems first, then matches
            df_discrepancy['__sort__'] = df_discrepancy.apply(
                lambda r: 0 if r.get('Mismatched Fields', '') != '✓ All Match' else (0 if r['Status'] != 'MATCH' else 1), axis=1
            )
            df_discrepancy.sort_values(by=['__sort__', 'Status', 'Delta'], inplace=True)
            df_discrepancy.drop(columns=['__sort__'], inplace=True)

        # ==================================================================================
        # --- 8. SCHEMA COMPARISON / LOGICAL CHECKER (Multi-File Only) ---
        # ==================================================================================
        self._report_progress(65, "Running schema comparison...")
        df_schema_report = pd.DataFrame()
        if self.schema_config: # Allow both SOA and MULTI modes to execute if user configured a Schema
            self.log("Running Schema Comparison Logic...")
            
            # Ensure labels are defined (might be skipped if amount_col is None)
            base_label = "SOA Amount" if self.mode == "SOA" else "Master Amount"
            invoice_label = "Invoice #" if self.mode == "SOA" else "ID / Key"

            try:
                # Initialize with Master Key
                key_col = invoice_label  # "ID / Key"
                # Find key in df_result (likely renamed or original)
                # It's usually self.soa_match (but filled)
                master_key_series = df_result[self.soa_match] if self.soa_match in df_result.columns else (df_result.iloc[:, 0] if not df_result.empty else pd.Series([]))
                
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
                        # Special Case: Base file (SOA) columns are usually not prefixed in df_result
                        if (ref_name == "SOA" or ref_name == "Master") and col_name in df_result.columns:
                            target_col = col_name
                        else:
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
                            # Still add an empty series to values_per_ref to keep indices aligned
                            values_per_ref[ref_name] = pd.Series([""] * len(df_result))

                    # 2. Compare Values (Row-wise)
                    # We need to construct a comparison status column
                    if values_per_ref:
                        status_list = []
                        temp_df = pd.DataFrame(values_per_ref)
                        
                        for i, row in temp_df.iterrows():
                            # Filter empty/None values
                            present_vals = {k: v for k, v in row.items() if v not in [None, "", np.nan]}
                            
                            if not present_vals:
                                status_list.append("NO DATA")
                                continue
                            
                            # Refined Status Logic (Phase 13)
                            # 1. Missing Data Check
                            if len(present_vals) < len(values_per_ref):
                                status_list.append("MISSING DATA")
                                continue
                            
                            # 2. All Data Present: Exact Match Check
                            norm_set = set()
                            for v in present_vals.values():
                                if isinstance(v, (int, float)): 
                                    norm_set.add(round(float(v), 2))
                                else: 
                                    norm_set.add(str(v).strip().upper())
                            
                            if len(norm_set) == 1:
                                status_list.append("MATCH")
                            else:
                                # Values disagree. Check for Partial Match (Substring logic, Text only)
                                is_partial = False
                                if field_type == "Text" and len(present_vals) >= 2:
                                    strs = [str(v).strip().upper() for v in present_vals.values() if v]
                                    if strs:
                                        strs.sort(key=len, reverse=True)
                                        longest = strs[0]
                                        if all(s in longest for s in strs[1:]):
                                            is_partial = True
                                
                                if is_partial:
                                    status_list.append("PARTIAL MATCH")
                                else:
                                    status_list.append("MISMATCH")
                        
                        schema_data[f"{field_name} Status"] = status_list

                df_schema_report = pd.DataFrame(schema_data)
                
            except Exception as e:
                self.log(f"Schema Comparison Error: {e}")
                import traceback
                traceback.print_exc()

        # --- 9. Excel Generation ---
        self._report_progress(70, "Generating Excel output...")
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
                    idx_delta = cols.index('Delta') if 'Delta' in cols else -1
                    idx_status = cols.index('Status') if 'Status' in cols else -1
                    
                    # Find per-ref amount column indices
                    ref_amt_indices = []
                    for col_name in cols:
                        if col_name.endswith(' Amount') and col_name != base_label:
                            ref_amt_indices.append(cols.index(col_name))

                    # Apply Header
                    for col_num, value in enumerate(cols):
                        ws2.write(0, col_num, value, header_format)
                        ws2.set_column(col_num, col_num, 18)

                    # Apply Data Formatting
                    for row_idx, (index, row) in enumerate(df_discrepancy.iterrows()):
                        excel_row = row_idx + 1
                        if idx_soa != -1:
                            ws2.write(excel_row, idx_soa, row[base_label], fmt_currency)
                        
                        # Format per-ref amount columns
                        for ref_idx in ref_amt_indices:
                            ref_col_name = cols[ref_idx]
                            val = row[ref_col_name]
                            if pd.notna(val):
                                ws2.write(excel_row, ref_idx, val, fmt_currency)
                        
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
                        if "MISSING" in status or "MISMATCH" in status or "Underpaid" in status or "Overpaid" in status:
                             ws2.write(excel_row, idx_status, status, mismatch_format)
                        elif "MATCH" in status:
                             ws2.write(excel_row, idx_status, status, match_format)
                        elif "PARTIAL" in status:
                             ws2.write(excel_row, idx_status, status, partial_format)
                
                # Sheet 2 Layout - Column adjustment
                if not df_discrepancy.empty:
                    ws2.set_column(0, len(cols)-1, 20)

                # ==========================================
                # SHEET 4: Reconciliation Insights
                # ==========================================
                self._report_progress(80, "Generating insights...")
                try:
                    from app.core.insights import ReconciliationInsights
                    ref_names_list = [cfg[3] for cfg in self.ref_configs if cfg]
                    analyzer = ReconciliationInsights(
                        df_result, df_discrepancy, ref_names_list,
                        amount_col=self.amount_col, date_col=self.date_col
                    )
                    insights = analyzer.generate_all()
                    
                    # Build Insights Summary Sheet
                    summary = insights.get("summary", {})
                    insights_rows = []
                    insights_rows.append({"Metric": "═════ EXECUTIVE SUMMARY ═════", "Value": ""})
                    insights_rows.append({"Metric": "Total Records Processed", "Value": summary.get("total_records", 0)})
                    insights_rows.append({"Metric": "Match Rate", "Value": f"{summary.get('match_rate', 0)}%"})
                    insights_rows.append({"Metric": "Matched Invoices", "Value": summary.get("match_count", 0)})
                    insights_rows.append({"Metric": "Discrepancies Found", "Value": summary.get("discrepancy_count", 0)})
                    insights_rows.append({"Metric": "Total Discrepancy Value", "Value": f"${summary.get('total_discrepancy_value', 0):,.2f}"})
                    insights_rows.append({"Metric": "Average Discrepancy", "Value": f"${summary.get('avg_discrepancy', 0):,.2f}"})
                    insights_rows.append({"Metric": "Maximum Discrepancy", "Value": f"${summary.get('max_discrepancy', 0):,.2f}"})
                    insights_rows.append({"Metric": "Reconciliation Health Score", "Value": f"{summary.get('health_score', 0)}/100"})
                    insights_rows.append({"Metric": "Reference Sources", "Value": summary.get("ref_count", 0)})
                    insights_rows.append({"Metric": "Generated At", "Value": insights.get("generated_at", "")})
                    
                    # Data Summary (Per source match and sum)
                    ds = summary.get("data_summary", [])
                    if ds:
                        insights_rows.append({"Metric": "", "Value": ""})
                        insights_rows.append({"Metric": "═════ DATA SUMMARY ═════", "Value": ""})
                        for d in ds:
                            source = d.get("Source", "Unknown")
                            val = d.get("Total Value", 0)
                            inv = d.get("Total Invoices", 0)
                            match_pct = d.get("Match Rate vs SOA", "0%")
                            insights_rows.append({"Metric": f"  [{source}] Invoices", "Value": inv})
                            insights_rows.append({"Metric": f"  [{source}] Value Sum", "Value": f"${val:,.2f}"})
                            insights_rows.append({"Metric": f"  [{source}] Match Rate", "Value": match_pct})                    
                    # Status Breakdown
                    status_bd = summary.get("status_breakdown", {})
                    if status_bd:
                        insights_rows.append({"Metric": "", "Value": ""})
                        insights_rows.append({"Metric": "═════ STATUS BREAKDOWN ═════", "Value": ""})
                        for status, count in status_bd.items():
                            insights_rows.append({"Metric": f"  {status}", "Value": count})
                    
                    # Patterns
                    patterns = insights.get("patterns", [])
                    if patterns:
                        insights_rows.append({"Metric": "", "Value": ""})
                        insights_rows.append({"Metric": "═════ DETECTED PATTERNS ═════", "Value": ""})
                        for p in patterns:
                            insights_rows.append({
                                "Metric": f"  [{p['severity']}] {p['type']}",
                                "Value": p["description"]
                            })
                    
                    # Anomaly Stats
                    anomaly_data = insights.get("anomalies", {})
                    anomaly_stats = anomaly_data.get("stats", {}) if isinstance(anomaly_data, dict) else {}
                    if anomaly_stats:
                        insights_rows.append({"Metric": "", "Value": ""})
                        insights_rows.append({"Metric": "═════ STATISTICAL ANALYSIS ═════", "Value": ""})
                        insights_rows.append({"Metric": "  Mean Amount", "Value": f"${anomaly_stats.get('mean', 0):,.2f}"})
                        insights_rows.append({"Metric": "  Median Amount", "Value": f"${anomaly_stats.get('median', 0):,.2f}"})
                        insights_rows.append({"Metric": "  Std Deviation", "Value": f"${anomaly_stats.get('std_dev', 0):,.2f}"})
                        insights_rows.append({"Metric": "  Outlier Count", "Value": anomaly_stats.get("outlier_count", 0)})
                        insights_rows.append({"Metric": "  Outlier Percentage", "Value": f"{anomaly_stats.get('outlier_pct', 0)}%"})
                    
                    df_insights_summary = pd.DataFrame(insights_rows)
                    df_insights_summary.to_excel(writer, index=False, sheet_name='Reconciliation Insights')
                    
                    # Format the insights sheet
                    ws_insights = writer.sheets['Reconciliation Insights']
                    fmt_section = workbook.add_format({'bold': True, 'fg_color': '#1565C0', 'font_color': '#FFFFFF', 'font_size': 11})
                    fmt_metric = workbook.add_format({'font_size': 10})
                    fmt_value = workbook.add_format({'font_size': 10, 'bold': True})
                    
                    ws_insights.set_column(0, 0, 35)
                    ws_insights.set_column(1, 1, 60)
                    
                    for row_idx, row_data in enumerate(insights_rows):
                        if "═════" in str(row_data.get("Metric", "")):
                            ws_insights.write(row_idx + 1, 0, row_data["Metric"], fmt_section)
                            ws_insights.write(row_idx + 1, 1, str(row_data["Value"]), fmt_section)
                        else:
                            ws_insights.write(row_idx + 1, 0, row_data["Metric"], fmt_metric)
                            ws_insights.write(row_idx + 1, 1, str(row_data["Value"]), fmt_value)
                    
                    # Write Source Reliability as separate sub-table if present
                    source_rel = insights.get("source_reliability", pd.DataFrame())
                    if not source_rel.empty:
                        start_row = len(insights_rows) + 3
                        ws_insights.write(start_row, 0, "═════ SOURCE RELIABILITY ═════", fmt_section)
                        for col_idx, col_name in enumerate(source_rel.columns):
                            ws_insights.write(start_row + 1, col_idx, col_name, header_format)
                        for r_idx, (_, r_data) in enumerate(source_rel.iterrows()):
                            for c_idx, val in enumerate(r_data.values):
                                ws_insights.write(start_row + 2 + r_idx, c_idx, str(val), fmt_metric)
                    
                    # Write Risk Scores as separate sheet
                    risk_df = insights.get("risk_scores", pd.DataFrame())
                    
                    fmt_low = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
                    fmt_med = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
                    fmt_high = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
                    fmt_crit = workbook.add_format({'bg_color': '#C00000', 'font_color': '#FFFFFF', 'bold': True})
                    
                    if not risk_df.empty:
                        risk_df.to_excel(writer, index=False, sheet_name='Risk Analysis')
                        ws_risk = writer.sheets['Risk Analysis']
                        for col_num, value in enumerate(risk_df.columns.values):
                            ws_risk.write(0, col_num, value, header_format)
                            ws_risk.set_column(col_num, col_num, 18)
                        
                        # Color-code risk levels
                        risk_col_idx = risk_df.columns.tolist().index("Risk Level") if "Risk Level" in risk_df.columns else -1
                        if risk_col_idx >= 0:
                            for r_idx in range(len(risk_df)):
                                level = str(risk_df.iloc[r_idx]["Risk Level"])
                                if "Low" in level: fmt = fmt_low
                                elif "Medium" in level: fmt = fmt_med
                                elif "High" in level: fmt = fmt_high
                                else: fmt = fmt_crit
                                ws_risk.write(r_idx + 1, risk_col_idx, level, fmt)

                    # Write Aging Analysis as separate sheet
                    aging_df = insights.get("aging", pd.DataFrame())
                    if not aging_df.empty:
                        aging_df.to_excel(writer, index=False, sheet_name='AGING ANALYSIS')
                        ws_aging = writer.sheets['AGING ANALYSIS']
                        for col_num, value in enumerate(aging_df.columns.values):
                            ws_aging.write(0, col_num, value, header_format)
                            ws_aging.set_column(col_num, col_num, 20)
                        
                        aging_col_idx = aging_df.columns.tolist().index("Risk Level") if "Risk Level" in aging_df.columns else -1
                        if aging_col_idx >= 0:
                            for r_idx in range(len(aging_df)):
                                level = str(aging_df.iloc[r_idx]["Risk Level"])
                                if "Safe" in level: fmt = fmt_low
                                elif "Attention" in level: fmt = fmt_med
                                elif "Risk" in level: fmt = fmt_high
                                else: fmt = fmt_crit
                                ws_aging.write(r_idx + 1, aging_col_idx, level, fmt)
                
                except Exception as e:
                    self.log(f"Insights sheet warning: {e}")


        except Exception as e:
            self.log(f"Excel Save Error: {e}")
            return df_result, None, df_discrepancy, df_schema_report, insights

        self._report_progress(90, "Complete.")
        return df_result, filename, df_discrepancy, df_schema_report, insights

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
