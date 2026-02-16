import pandas as pd
from rapidfuzz import process, fuzz, utils

class MatchingEngine:
    """
    Core engine for comparing and reconciling data between a Base dataframe
    and multiple Reference dataframes.
    """
    def __init__(self):
        self.base_df = None
        self.reference_dfs = {}  # Dict[str, pd.DataFrame]
        self.mappings = {}       # Dict[str, Dict] -> map ref_name to column mapping rules

    def set_base_data(self, df: pd.DataFrame):
        """Sets the primary dataframe (e.g., SOA)."""
        self.base_df = df

    def add_reference_data(self, name: str, df: pd.DataFrame):
        """Adds a reference dataframe (e.g., Bank Statement, Ledger)."""
        self.reference_dfs[name] = df

    def set_mapping(self, ref_name: str, base_col: str, ref_col: str, match_type: str = "exact"):
        """
        Defines how a reference file matches against the base file.
        match_type: 'exact' or 'fuzzy'
        """
        self.mappings[ref_name] = {
            "base_col": base_col,
            "ref_col": ref_col,
            "match_type": match_type
        }

    def _apply_exact_match(self, result_df, ref_df, ref_name, base_col, ref_col):
        """
        Applies exact matching using Pandas merge.
        """
        # Rename columns in ref to avoid collision
        ref_df_renamed = ref_df.add_prefix(f"{ref_name}_")
        ref_key = f"{ref_name}_{ref_col}"
        
        merged = pd.merge(
            result_df,
            ref_df_renamed,
            left_on=base_col,
            right_on=ref_key,
            how="left"
        )
        
        return merged

    def _apply_fuzzy_match(self, result_df, ref_df, ref_name, base_col, ref_col):
        """
        Applies fuzzy matching using RapidFuzz.
        WARNING: This can be slow for large datasets.
        """
        # Rename columns in ref to avoid collision
        ref_df_renamed = ref_df.add_prefix(f"{ref_name}_")
        ref_key = f"{ref_name}_{ref_col}"
        
        # Get unique values to match
        base_values = result_df[base_col].dropna().unique()
        ref_values = ref_df_renamed[ref_key].dropna().unique()
        # Pre-calculate best matches for unique values
        matches = {}
        for val in base_values:
             # score_cutoff=60 is reasonable with default_process (handles case/trim)
            match = process.extractOne(
                str(val), 
                [str(x) for x in ref_values], 
                scorer=fuzz.WRatio, 
                processor=utils.default_process, 
                score_cutoff=60
            )
            if match:
                best_match_val, score, _ = match
                matches[val] = best_match_val
        
        # Map back to result_df
        # create a temporary match column
        match_col_name = f"{ref_name}_Match_Key"
        result_df[match_col_name] = result_df[base_col].map(matches).fillna("No Match") 
        # Filling with "No Match" or casting to str prevents mixed type errors (float NaN vs str)

        
        # Now merge based on the fuzzy match key
        merged = pd.merge(
            result_df,
            ref_df_renamed,
            left_on=match_col_name,
            right_on=ref_key,
            how="left"
        )
        
        return merged

    def run_matching(self) -> pd.DataFrame:
        """
        Executes the matching process.
        Returns a new DataFrame with results appended to the Base data.
        """
        if self.base_df is None:
            raise ValueError("Base DataFrame is not set.")

        result_df = self.base_df.copy()

        for ref_name, df in self.reference_dfs.items():
            if ref_name not in self.mappings:
                continue
            
            mapping = self.mappings[ref_name]
            base_col = mapping["base_col"]
            ref_col = mapping["ref_col"]
            match_type = mapping["match_type"]

            if match_type == "exact":
                result_df = self._apply_exact_match(result_df, df, ref_name, base_col, ref_col)
            elif match_type == "fuzzy":
                result_df = self._apply_fuzzy_match(result_df, df, ref_name, base_col, ref_col)

        return result_df
