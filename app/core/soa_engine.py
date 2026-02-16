import pandas as pd
import datetime
import os

class SOAEngine:
    """
    Ported logic from Oi360 RecoWorker.
    Handles exact reconciliation, age bucketing, duplicate detection,
    amount mismatch highlighting, and specific Excel formatting.
    """
    def __init__(self, soa_df, soa_match_col, soa_date_col, soa_amount_col, ref_configs):
        """
        ref_configs: List of tuples (ref_df, match_col, return_cols, ref_name)
        """
        self.soa_df = soa_df
        self.soa_match = soa_match_col
        self.soa_date_col = soa_date_col
        self.soa_amount_col = soa_amount_col
        self.ref_configs = ref_configs
        
        self.log_messages = []

    def log(self, msg):
        print(f"[SOAEngine] {msg}")
        self.log_messages.append(msg)

    def run(self):
        """
        Executes the reconciliation logic.
        Returns: (df_result, excel_filename)
        """
        df_result = self.soa_df.copy()
        
        # --- 1. Age Bucket Logic ---
        original_date_col_values = None
        if self.soa_date_col and self.soa_date_col in df_result.columns:
            original_date_col_values = df_result[self.soa_date_col].copy()
            try:
                today = pd.to_datetime(datetime.datetime.today())
                temp_dates = pd.to_datetime(
                    df_result[self.soa_date_col], errors='coerce', format='mixed', dayfirst=True
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
                df_result[self.soa_date_col] = original_date_col_values
            except Exception as e:
                self.log(f"Age Bucket Warning: {e}")
                if original_date_col_values is not None:
                    df_result[self.soa_date_col] = original_date_col_values
        
        # --- 2. Cleaning Helper ---
        def clean_match_value(val):
            s = str(val).strip()
            if s.startswith("'"):
                s = s[1:]
            if s.isdigit() or (s and s.lstrip('0').isdigit()):
                s = s.lstrip('0') or '0'
            return s
        
        # Track match sources per SOA row
        soa_match_values_cleaned = [clean_match_value(v) for v in df_result[self.soa_match].astype(str).values]
        match_sources_dict = {k: [] for k in soa_match_values_cleaned}
        
        # Track duplicate counts per ref for the Duplicate Summary column
        # Structure: {ref_name: {cleaned_soa_val: count}}
        duplicate_counts = {}
        ref_names_ordered = []

        # --- 3. Matching Logic ---
        for idx, config in enumerate(self.ref_configs):
            if not config: continue
            
            ref_df, ref_match_col, return_cols, ref_name = config
            ref_names_ordered.append(ref_name)
            
            self.log(f"Matching {ref_name} on {ref_match_col}")
            
            try:
                if ref_match_col not in ref_df.columns:
                    self.log(f"Skipping {ref_name}: Column {ref_match_col} not found.")
                    continue

                # Clean matching columns
                soa_clean_col = f"_clean_{self.soa_match}"
                ref_clean_col = f"_clean_{ref_match_col}"
                
                df_result[soa_clean_col] = df_result[self.soa_match].astype(str).apply(clean_match_value)
                ref_df = ref_df.copy()
                ref_df[ref_clean_col] = ref_df[ref_match_col].astype(str).apply(clean_match_value)
                
                # --- Always include the ref match column in extraction ---
                # This ensures the user can always see which ref entry matched
                extract_cols = list(return_cols)  # copy
                if ref_match_col not in extract_cols:
                    extract_cols.insert(0, ref_match_col)
                
                # --- Count duplicates BEFORE merge ---
                # Count how many times each SOA match value appears in this ref file
                ref_value_counts = ref_df[ref_clean_col].value_counts().to_dict()
                ref_dup_counts = {}
                for soa_val in soa_match_values_cleaned:
                    ref_dup_counts[soa_val] = ref_value_counts.get(soa_val, 0)
                duplicate_counts[ref_name] = ref_dup_counts
                
                # Prepare extraction with renamed columns
                ref_extract = ref_df[[ref_clean_col] + extract_cols].copy()
                rename_map = {c: f"{ref_name}_{c}" for c in extract_cols}
                rename_map[ref_clean_col] = ref_clean_col  # Keep key same for merge
                ref_extract = ref_extract.rename(columns=rename_map)
                
                # Merge (left join preserves all SOA rows; duplicates in ref create multiple rows)
                df_result = pd.merge(df_result, ref_extract, left_on=soa_clean_col, right_on=ref_clean_col, how='left')
                
                # Update Match Sources
                first_ret_col = f"{ref_name}_{extract_cols[0]}"
                if first_ret_col in df_result.columns:
                    match_mask = df_result[first_ret_col].notna()
                    matched_indices = df_result.index[match_mask]
                    for i in matched_indices:
                        key = df_result.at[i, soa_clean_col]
                        if key in match_sources_dict:
                            if ref_name not in match_sources_dict[key]:
                                match_sources_dict[key].append(ref_name)
                
                # Add Match Count column for this ref
                match_count_col = f"{ref_name}_Match_Count"
                df_result[match_count_col] = df_result[soa_clean_col].map(
                    lambda v: ref_dup_counts.get(v, 0)
                )
                
                # Drop temp clean columns
                if soa_clean_col in df_result.columns:
                    df_result.drop(columns=[soa_clean_col], inplace=True)
                if ref_clean_col in df_result.columns:
                    df_result.drop(columns=[ref_clean_col], inplace=True)
                
                # Add separator between ref blocks
                if idx > 0:
                    sep_name = f"Separator{idx+1}"
                    df_result.insert(df_result.shape[1], sep_name, "")
                    
            except Exception as e:
                self.log(f"Error matching {ref_name}: {e}")

        # --- 4. Construct Match Source Column ---
        df_result["Match Source"] = [
            ", ".join(match_sources_dict.get(clean_match_value(val), []))
            for val in df_result[self.soa_match].astype(str).values
        ]
        
        # --- 5. Duplicate Summary Column ---
        # e.g., "Ref1: 2x, Ref2: 0x, Ref3: 1x"
        if ref_names_ordered:
            dup_summary_data = []
            soa_vals_for_summary = [clean_match_value(v) for v in df_result[self.soa_match].astype(str).values]
            for soa_val in soa_vals_for_summary:
                parts = []
                for rname in ref_names_ordered:
                    count = duplicate_counts.get(rname, {}).get(soa_val, 0)
                    if count == 0:
                        parts.append(f"{rname}: no entry")
                    elif count == 1:
                        parts.append(f"{rname}: 1x")
                    else:
                        parts.append(f"{rname}: {count}x")
                dup_summary_data.append(", ".join(parts))
            df_result["Duplicate Summary"] = dup_summary_data
        
        # Cleanup Separators
        if "Separator1" in df_result.columns:
             df_result.drop(columns=["Separator1"], inplace=True)

        # --- 6. Date Cleanup (remove 00:00:00) ---
        date_keywords = ['date', 'dt', 'dated']
        for col in df_result.columns:
            if any(kw in col.lower() for kw in date_keywords):
                try:
                    df_result[col] = df_result[col].astype(str).str.replace(r'\s+00:00:00$', '', regex=True)
                    df_result[col] = df_result[col].replace('nan', '')
                    df_result[col] = df_result[col].replace('NaT', '')
                except: pass

        # --- 7. Excel Generation with Formatting ---
        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, f"soa_reco_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        
        try:
            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                df_result.to_excel(writer, index=False, sheet_name='Sheet1')
                workbook  = writer.book
                worksheet = writer.sheets['Sheet1']
                
                # Header Format
                header_format = workbook.add_format({
                    'bold': True, 'text_wrap': True, 'valign': 'top',
                    'fg_color': '#404040', 'font_color': '#FFFFFF', 'border': 1
                })
                for col_num, value in enumerate(df_result.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # --- 8. Amount Mismatch Highlighting ---
                mismatch_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
                
                # Duplicate highlight format (for rows with count > 1)
                dup_format = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})  # Yellow/amber
                
                soa_amt_col = self.soa_amount_col
                all_cols = list(df_result.columns)
                
                self.log(f"Amount comparison: SOA amount col = '{soa_amt_col}'")
                self.log(f"All columns in result: {all_cols}")
                
                # Find ref amount columns by checking prefixes from our ref_configs
                ref_names = [cfg[3] for cfg in self.ref_configs if cfg]
                amount_keywords = ['amount', 'amt', 'value', 'total', 'sum', 'price', 'cost']
                ref_amount_cols = []
                for c in all_cols:
                    for rname in ref_names:
                        if c.startswith(f"{rname}_") and any(kw in c.lower() for kw in amount_keywords):
                            ref_amount_cols.append(c)
                
                self.log(f"Ref amount columns found: {ref_amount_cols}")

                if soa_amt_col and soa_amt_col in all_cols and ref_amount_cols:
                    soa_col_idx = all_cols.index(soa_amt_col)
                    amount_diff_data = []
                    
                    for row_idx in range(len(df_result)):
                        soa_val = df_result.iloc[row_idx][soa_amt_col]
                        soa_num = self._to_float(soa_val)
                        
                        row_diffs = []
                        highlight_row = False
                        
                        if soa_num is not None:
                            for ref_col in ref_amount_cols:
                                ref_val = df_result.iloc[row_idx][ref_col]
                                ref_num = self._to_float(ref_val)
                                
                                if ref_num is not None:
                                    diff = soa_num - ref_num
                                    ref_name_clean = ref_col.split('_')[0]
                                    if abs(diff) > 0.01:
                                        highlight_row = True
                                        sign = "+" if diff > 0 else ""
                                        row_diffs.append(f"{ref_name_clean}: {sign}{diff:.2f}")
                                        
                                        # Highlight Ref Cell
                                        ref_col_idx = all_cols.index(ref_col)
                                        worksheet.write(row_idx + 1, ref_col_idx, ref_val, mismatch_format)
                                    else:
                                        row_diffs.append(f"{ref_name_clean}: 0.00")
                        
                        if highlight_row:
                            worksheet.write(row_idx + 1, soa_col_idx, soa_val, mismatch_format)
                        
                        amount_diff_data.append(", ".join(row_diffs) if row_diffs else "")
                    
                    # Add Amount Difference Column to Excel
                    diff_col_idx = len(all_cols)
                    worksheet.write(0, diff_col_idx, 'Amount Difference', header_format)
                    for row_idx, diff_val in enumerate(amount_diff_data):
                        worksheet.write(row_idx + 1, diff_col_idx, diff_val)
                
                # --- 9. Highlight duplicate match count cells ---
                for rname in ref_names:
                    mc_col = f"{rname}_Match_Count"
                    if mc_col in all_cols:
                        mc_col_idx = all_cols.index(mc_col)
                        for row_idx in range(len(df_result)):
                            count_val = df_result.iloc[row_idx][mc_col]
                            try:
                                if int(count_val) > 1:
                                    worksheet.write(row_idx + 1, mc_col_idx, int(count_val), dup_format)
                            except (ValueError, TypeError):
                                pass

        except Exception as e:
            self.log(f"Excel Save Error: {e}")
            return df_result, None

        return df_result, filename

    def _to_float(self, val):
        try:
            if pd.isna(val): return None
            return float(str(val).replace(',', '').replace('$', '').strip())
        except:
            return None
