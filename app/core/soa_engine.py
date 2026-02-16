import pandas as pd
import datetime
import os

class SOAEngine:
    """
    Ported logic from Oi360 RecoWorker.
    Handles exact reconciliation, age bucketing, and specific Excel formatting.
    """
    def __init__(self, soa_df, soa_match_col, soa_date_col, soa_amount_col, ref_configs):
        """
        ref_configs: List of tuples (ref_df, match_col, return_cols, ref_name)
        """
        self.soa_df = soa_df
        self.soa_match = soa_match_col
        self.soa_date_col = soa_date_col
        self.soa_amount_col = soa_amount_col
        # Ensure ref_configs matches expectations. 
        # In Oi360 it was (ref_df, match_col, return_cols, _) where _ was unused or file path
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
                # Convert to datetime for age calculation
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
                # Move to front
                df_result.insert(0, 'Age Bucket', df_result.pop('Age Bucket'))
                # Restore original date format
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
        
        # Create match dictionary for "Match Source" column
        # Clean the SOA match column for dictionary keys
        soa_match_values_cleaned = [clean_match_value(v) for v in df_result[self.soa_match].astype(str).values]
        match_sources_dict = {k: [] for k in soa_match_values_cleaned}

        # --- 3. Matching Logic ---
        total_steps = len(self.ref_configs)
        
        for idx, config in enumerate(self.ref_configs):
            # Config structure from Oi360 seems to be (ref_df, match_col, return_cols, something_else)
            # We will adapt to what we pass in. 
            # Let's assume (ref_df, ref_match_col, return_cols, ref_name)
            if not config: continue
            
            ref_df, ref_match_col, return_cols, ref_name = config
            
            self.log(f"Matching {ref_name} on {ref_match_col}")
            
            try:
                # Prepare temporary copies for merging with cleaned keys
                # We don't want to permanently alter the input DFs, but for the merge we need cleaned keys
                
                # Check if columns exist
                if ref_match_col not in ref_df.columns:
                    self.log(f"Skipping {ref_name}: Column {ref_match_col} not found.")
                    continue

                # Clean matching columns
                soa_clean_col = f"_clean_{self.soa_match}"
                ref_clean_col = f"_clean_{ref_match_col}"
                
                df_result[soa_clean_col] = df_result[self.soa_match].astype(str).apply(clean_match_value)
                ref_df = ref_df.copy() # Avoid SettingPithCopy warning on input df
                ref_df[ref_clean_col] = ref_df[ref_match_col].astype(str).apply(clean_match_value)
                
                # Prepare extraction
                # Rename return columns
                ref_extract = ref_df[[ref_clean_col] + return_cols].copy()
                rename_map = {c: f"{ref_name}_{c}" for c in return_cols}
                rename_map[ref_clean_col] = ref_clean_col # Keep key same for merge
                ref_extract = ref_extract.rename(columns=rename_map)
                
                # Merge
                df_result = pd.merge(df_result, ref_extract, left_on=soa_clean_col, right_on=ref_clean_col, how='left')
                
                # Update Match Sources
                # Check if any of the returned columns are not NaN
                # Use the first return column as proxy for existence
                first_ret_col = f"{ref_name}_{return_cols[0]}"
                if first_ret_col in df_result.columns:
                    match_mask = df_result[first_ret_col].notna()
                    # We need to iterate to update the specific keys
                    # This is slow but matches Oi360 logic which tracked sources per row
                    # Vectorized approach:
                    matched_indices = df_result.index[match_mask]
                    for i in matched_indices:
                        key = df_result.at[i, soa_clean_col]
                        if key in match_sources_dict:
                            # Avoid duplicates
                            if ref_name not in match_sources_dict[key]:
                                match_sources_dict[key].append(ref_name)
                
                # Drop temp clean columns
                if soa_clean_col in df_result.columns:
                    df_result.drop(columns=[soa_clean_col], inplace=True)
                # ref_extract key column is effectively dropped or merged? 
                # pandas merge keeps keys if names are different or 'on'
                # we merged on specific columns, check if ref_clean_col persists
                if ref_clean_col in df_result.columns:
                    df_result.drop(columns=[ref_clean_col], inplace=True)
                
                # Add separator
                if idx > 0:
                    sep_name = f"Separator{idx+1}"
                    df_result.insert(df_result.shape[1], sep_name, "")
                    
            except Exception as e:
                self.log(f"Error matching {ref_name}: {e}")

        # Construct Match Source Column
        df_result["Match Source"] = [
            ", ".join(match_sources_dict.get(clean_match_value(val), []))
            for val in df_result[self.soa_match].astype(str).values
        ]
        
        # Cleanup Separators if any (Oi360 logic removed Separator1?)
        # Logic says: if "Separator1" in df_result.columns: drop.
        if "Separator1" in df_result.columns:
             df_result.drop(columns=["Separator1"], inplace=True)

        # --- 4. Date Cleanup (remove 00:00:00) ---
        date_keywords = ['date', 'dt', 'dated']
        for col in df_result.columns:
            if any(kw in col.lower() for kw in date_keywords):
                try:
                    df_result[col] = df_result[col].astype(str).str.replace(r'\s+00:00:00$', '', regex=True)
                    df_result[col] = df_result[col].replace('nan', '')
                    df_result[col] = df_result[col].replace('NaT', '')
                except: pass

        # --- 5. Excel Generation with Formatting ---
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
                
                # --- 6. Amount Mismatch Highlighting ---
                mismatch_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
                
                soa_amt_col = self.soa_amount_col
                # Identify Ref amount columns
                amount_keywords = ['amount', 'amt', 'value', 'total', 'sum', 'price', 'cost']
                all_cols = list(df_result.columns)
                ref_amount_cols = [c for c in all_cols if any(kw in c.lower() for kw in amount_keywords) and (c.startswith('Ref') or c.startswith('Bank') or c.startswith('Ledger'))] # Generalized prefix check
                
                # Specifically simply check for prefixes added by us (RefName_)
                # In this engine, we prefixed with "{ref_name}_"
                # We need to detect them. We can scan ref_configs for ref_names.
                ref_names = [cfg[3] for cfg in self.ref_configs if cfg]
                ref_amount_cols = []
                for c in all_cols:
                     for rname in ref_names:
                         if c.startswith(f"{rname}_") and any(kw in c.lower() for kw in amount_keywords):
                             ref_amount_cols.append(c)

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
                                    if abs(diff) > 0.01:
                                        # Mismatch
                                        highlight_row = True
                                        ref_name_clean = ref_col.split('_')[0] # approximate
                                        sign = "+" if diff > 0 else ""
                                        row_diffs.append(f"{ref_name_clean}: {sign}{diff:.2f}")
                                        
                                        # Highlight Ref Cell
                                        ref_col_idx = all_cols.index(ref_col)
                                        worksheet.write(row_idx + 1, ref_col_idx, ref_val, mismatch_format)
                                    else:
                                        # Match (0.00 difference)
                                        pass 
                        
                        if highlight_row:
                            worksheet.write(row_idx + 1, soa_col_idx, soa_val, mismatch_format)
                        
                        amount_diff_data.append(", ".join(row_diffs) if row_diffs else "")
                    
                    # Add Amount Difference Column to Excel
                    diff_col_idx = len(all_cols)
                    worksheet.write(0, diff_col_idx, 'Amount Difference', header_format)
                    for row_idx, diff_val in enumerate(amount_diff_data):
                        worksheet.write(row_idx + 1, diff_col_idx, diff_val)

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
