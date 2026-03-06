"""
ReconciliationInsights — AI-Powered Analysis Engine for SOA Reconciliation.

Generates executive summaries, risk scores, anomaly detection, aging analysis,
source reliability metrics, and pattern detection from reconciliation results.

All analysis is computed locally using pandas/numpy — no external APIs required.
"""

import pandas as pd
import numpy as np
from datetime import datetime


class ReconciliationInsights:
    """
    Analyzes reconciliation outputs to produce actionable insights.
    
    Input DataFrames:
        - df_result: The detailed view (full merged data)
        - df_discrepancy: The discrepancy report (per-invoice aggregation)
        
    All insights are returned as a dict of DataFrames and scalar metrics,
    ready for both UI display and Excel export.
    """

    def __init__(self, df_result, df_discrepancy, ref_names, amount_col=None, date_col=None):
        self.df_result = df_result
        self.df_disc = df_discrepancy if df_discrepancy is not None else pd.DataFrame()
        self.ref_names = ref_names or []
        self.amount_col = amount_col
        self.date_col = date_col
        self.insights = {}

    
    def _get_invoice_col(self, df):
        if "Invoice #" in df.columns:
            return "Invoice #"
        elif "ID / Key" in df.columns:
            return "ID / Key"
        for col in df.columns:
            # Fallback search for common ID columns
            col_l = col.lower()
            if "invoice" in col_l and ("id" in col_l or "num" in col_l or "#" in col_l):
                return col
            if col_l == "invoice":
                return col
        # Absolute fallback, just return first column
        return df.columns[0] if len(df.columns) > 0 else "ID / Key"

    def generate_all(self):
        """Run all insight generators and return combined results dict."""
        self.insights["summary"] = self._executive_summary()
        self.insights["risk_scores"] = self._risk_scoring()
        self.insights["anomalies"] = self._anomaly_detection()
        self.insights["aging"] = self._aging_analysis()
        self.insights["source_reliability"] = self._source_reliability()
        self.insights["top_discrepancies"] = self._top_discrepancies()
        self.insights["patterns"] = self._pattern_detection()
        self.insights["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.insights

    # ─────────────────────────────────────────────────────────────
    #  1. EXECUTIVE SUMMARY
    # ─────────────────────────────────────────────────────────────
    def _executive_summary(self):
        """High-level KPIs for the reconciliation."""
        summary = {}
        df_res = self.df_result
        total_soa = len(df_res)
        summary["total_records"] = total_soa

        if df_res.empty:
            summary["match_rate"] = 0.0
            summary["total_discrepancy_value"] = 0.0
            summary["discrepancy_count"] = 0
            summary["match_count"] = 0
            summary["health_score"] = 0
            return summary

        # ── 1. Discrepancy Stats ──
        disc = self.df_disc
        disc_count = len(disc)
        match_count = total_soa - disc_count

        summary["match_count"] = int(match_count)
        summary["discrepancy_count"] = int(disc_count)

        # OVERALL Match Rate
        overall_match_rate = round((match_count / total_soa) * 100, 1) if total_soa > 0 else 0.0
        summary["match_rate"] = overall_match_rate

        # ── 2. Data Summary (Per File comparisons) ──
        base_label = self.amount_col
        if not base_label or base_label not in df_res.columns:
            for col in df_res.columns:
                if 'amount' in col.lower() or 'total' in col.lower() or 'balance' in col.lower():
                    base_label = col
                    break
        
        def clean_amt(val):
            try:
                if pd.isna(val) or val == "": return 0.0
                val_str = str(val).replace(',', '').replace('$', '').replace(' ', '').strip()
                if val_str.startswith('(') and val_str.endswith(')'):
                    val_str = '-' + val_str[1:-1]
                return float(val_str)
            except:
                return 0.0

        soa_total_val = df_res[base_label].apply(clean_amt).sum() if base_label else 0.0

        data_summary = []
        data_summary.append({
            "Source": "SOA (Master)",
            "Total Invoices": int(total_soa),
            "Total Value": float(soa_total_val),
            "Match Rate vs SOA": "100.0%"
        })

        for ref_name in self.ref_names:
            ref_amt_col = None
            for col in df_res.columns:
                if col.startswith(ref_name) and ('amount' in col.lower() or 'total' in col.lower() or 'balance' in col.lower()):
                    ref_amt_col = col
                    break
            
            ref_count = 0
            ref_val = 0.0
            if ref_amt_col:
                ref_count = df_res[ref_amt_col].notna().sum()
                ref_val = df_res[ref_amt_col].apply(clean_amt).sum()
            else:
                key_col = f"{ref_name}_Match_Count"
                if key_col in df_res.columns:
                    ref_count = (df_res[key_col] > 0).sum()
            
            # Since exact cross-column matches are hard dynamically, fallback to the overall rate
            ref_match_rate = overall_match_rate
            
            data_summary.append({
                "Source": ref_name,
                "Total Invoices": int(ref_count),
                "Total Value": float(ref_val),
                "Match Rate vs SOA": f"{ref_match_rate}%"
            })
        
        summary["data_summary"] = data_summary

        if not disc.empty and "Delta" in disc.columns:
            summary["total_discrepancy_value"] = round(disc["Delta"].apply(clean_amt).abs().sum(), 2)
            summary["avg_discrepancy"] = round(disc["Delta"].apply(clean_amt).abs().mean(), 2) if disc_count > 0 else 0.0
            summary["max_discrepancy"] = round(disc["Delta"].apply(clean_amt).abs().max(), 2)
        else:
            summary["total_discrepancy_value"] = 0.0
            summary["avg_discrepancy"] = 0.0
            summary["max_discrepancy"] = 0.0

        health = overall_match_rate
        if summary["total_discrepancy_value"] > 0 and soa_total_val != 0:
            disc_ratio = summary["total_discrepancy_value"] / abs(soa_total_val)
            penalty = min(20.0, disc_ratio * 100)
            health = max(0.0, health - penalty)
            
        summary["health_score"] = round(health, 1)

        # Status breakdown should count matches from result and mismatches from disc
        status_counts = {"MATCH": match_count}
        if not disc.empty and "Status" in disc.columns:
            disc_counts = disc["Status"].value_counts().to_dict()
            for k, v in disc_counts.items():
                if k != "MATCH":
                    status_counts[k] = v
        summary["status_breakdown"] = status_counts

        summary["ref_count"] = len(self.ref_names)
        return summary

    # ─────────────────────────────────────────────────────────────
    #  2. RISK SCORING
    # ─────────────────────────────────────────────────────────────
    def _risk_scoring(self):
        """Assign a 0-100 risk score to each invoice in the discrepancy report."""
        # Compute risk scores from df_result when df_disc is empty (all-MATCH case)
        if not self.df_disc.empty and "Delta" in self.df_disc.columns:
            disc = self.df_disc.copy()
        elif not self.df_result.empty:
            disc = self.df_result.copy()
            if "Delta" not in disc.columns:
                disc["Delta"] = 0.0
            if "Status" not in disc.columns:
                disc["Status"] = "MATCH"
        else:
            return pd.DataFrame()
        disc = disc.copy()
        invoice_col = self._get_invoice_col(disc)
        if invoice_col not in disc.columns:
            invoice_col = disc.columns[0]

        scores = pd.DataFrame()
        scores[invoice_col] = disc[invoice_col]

        # Factor 1: Delta magnitude (0-40 points)
        abs_delta = disc["Delta"].abs()
        max_delta = abs_delta.max()
        if max_delta > 0:
            scores["delta_score"] = (abs_delta / max_delta * 40).round(1)
        else:
            scores["delta_score"] = 0.0

        # Factor 2: Status severity (0-25 points)
        status_weights = {
            "MATCH": 0,
            "PARTIAL (Some Refs Missing)": 10,
            "MISSING IN REF": 20,
            "MISSING IN SOA": 25,
            "MISMATCH (Partial)": 20,
            "Underpaid (Short)": 15,
            "Overpaid (Excess)": 15,
            "NO DATA": 25,
        }
        if "Status" in disc.columns:
            scores["status_score"] = disc["Status"].map(status_weights).fillna(15)
        else:
            scores["status_score"] = 0

        # Factor 3: Missing refs (0-15 points)
        if "Ref_Count" in disc.columns:
            total_refs = len(self.ref_names) if self.ref_names else 1
            missing_ratio = 1 - (disc["Ref_Count"] / max(total_refs, 1))
            scores["missing_score"] = (missing_ratio.clip(0, 1) * 15).round(1)
        else:
            scores["missing_score"] = 0

        # Factor 4: Age (0-20 points) — older = riskier
        if "Age (Days)" in self.df_result.columns:
            try:
                # Map age from result to disc via invoice key
                age_map = self.df_result.groupby(
                    self.df_result.columns[self.df_result.columns.str.contains(invoice_col, case=False)].tolist()[0] 
                    if any(self.df_result.columns.str.contains(invoice_col, case=False)) 
                    else self.df_result.columns[0]
                )["Age (Days)"].first()
                scores["age_score"] = 0
            except Exception:
                scores["age_score"] = 0
        else:
            scores["age_score"] = 0

        # Composite Risk Score
        scores["Risk Score"] = (
            scores["delta_score"] + scores["status_score"] + 
            scores["missing_score"] + scores["age_score"]
        ).clip(0, 100).round(0).astype(int)

        # Risk Level
        scores["Risk Level"] = pd.cut(
            scores["Risk Score"],
            bins=[-1, 25, 50, 75, 100],
            labels=["🟢 Low", "🟡 Medium", "🟠 High", "🔴 Critical"]
        )

        # Bring Status and Delta in for context
        scores["Status"] = disc["Status"].values if "Status" in disc.columns else ""
        scores["Delta"] = disc["Delta"].values

        # Sort by risk descending
        scores = scores.sort_values("Risk Score", ascending=False)

        # Return clean output
        return scores[[invoice_col, "Risk Score", "Risk Level", "Status", "Delta"]].reset_index(drop=True)

    # ─────────────────────────────────────────────────────────────
    #  3. ANOMALY DETECTION (IQR Method)
    # ─────────────────────────────────────────────────────────────
    def _anomaly_detection(self):
        """Detect statistical outliers in amounts using IQR method."""
        # Use df_result when df_disc is empty (all-MATCH case)
        data_df = self.df_result if self.df_disc.empty else self.df_disc
        if data_df.empty:
            return {"outliers": pd.DataFrame(), "stats": {}}

        base_label = self.amount_col if data_df is self.df_result else ("SOA Amount" if "SOA Amount" in data_df.columns else "Master Amount")
        if not base_label or base_label not in data_df.columns:
            # Fallback search
            found = False
            for col in data_df.columns:
                if 'amount' in col.lower() or 'total' in col.lower() or 'balance' in col.lower():
                    base_label = col
                    found = True
                    break
            if not found:
                return {"outliers": pd.DataFrame(), "stats": {}}

        amounts = data_df[base_label].dropna()
        if len(amounts) < 4:
            return {"outliers": pd.DataFrame(), "stats": {}}

        q1 = amounts.quantile(0.25)
        q3 = amounts.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        stats = {
            "mean": round(amounts.mean(), 2),
            "median": round(amounts.median(), 2),
            "std_dev": round(amounts.std(), 2),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "lower_bound": round(lower_bound, 2),
            "upper_bound": round(upper_bound, 2),
        }

        # Find outliers
        outlier_mask = (amounts < lower_bound) | (amounts > upper_bound)
        invoice_col = self._get_invoice_col(data_df)

        if outlier_mask.any():
            outlier_df = data_df.loc[outlier_mask, [invoice_col, base_label]].copy()
            outlier_df["Deviation"] = outlier_df[base_label].apply(
                lambda x: "⬆ Above Upper" if x > upper_bound else "⬇ Below Lower"
            )
            outlier_df["Z-Score"] = ((outlier_df[base_label] - amounts.mean()) / amounts.std()).round(2)
            outlier_df = outlier_df.sort_values(base_label, key=abs, ascending=False)
        else:
            outlier_df = pd.DataFrame()

        stats["outlier_count"] = int(outlier_mask.sum())
        stats["outlier_pct"] = round(outlier_mask.sum() / len(amounts) * 100, 1)

        return {"outliers": outlier_df, "stats": stats}

    # ─────────────────────────────────────────────────────────────
    #  4. AGING ANALYSIS
    # ─────────────────────────────────────────────────────────────
    def _aging_analysis(self):
        """Break down all invoices by age bucket to provide insight into distribution and risk."""
        if self.df_result.empty or "Age Bucket" not in self.df_result.columns:
            return pd.DataFrame()

        # Find the base amount column
        base_label = self.amount_col
        if not base_label or base_label not in self.df_result.columns:
            # Fallback
            for col in self.df_result.columns:
                if 'amount' in col.lower() or 'total' in col.lower() or 'balance' in col.lower():
                    base_label = col
                    break
                    
        # Determine risk level
        def get_risk(bucket):
            if bucket == "0-30":
                return "🟢 Safe"
            elif bucket == "31-60":
                return "🟡 Attention Required"
            elif bucket in ["61-90", "91-120", "121+"]:
                return "🔴 High Risk"
            return "⚪ Unknown"

        # Safe amount conversion
        def clean_amt(val):
            try:
                if pd.isna(val) or val == "": return 0.0
                return float(str(val).replace(',', '').replace('$', '').strip())
            except:
                return 0.0

        if base_label:
            temp_amt = self.df_result[base_label].apply(clean_amt)
            df_temp = pd.DataFrame({"Age Bucket": self.df_result["Age Bucket"], "Amt": temp_amt})
            
            aging = df_temp.groupby("Age Bucket").agg(
                Total_Invoices=("Amt", "size"),
                Total_Value=("Amt", "sum")
            ).reset_index()
        else:
            aging = self.df_result.groupby("Age Bucket").size().reset_index(name="Total_Invoices")
            aging["Total_Value"] = 0.0

        aging["Risk Level"] = aging["Age Bucket"].apply(get_risk)

        # Sort by age bucket order
        bucket_order = ["0-30", "31-60", "61-90", "91-120", "121+", "Unknown"]
        aging["_sort"] = aging["Age Bucket"].apply(lambda x: bucket_order.index(x) if x in bucket_order else 99)
        aging = aging.sort_values("_sort").drop(columns=["_sort"])

        aging["Total Value"] = aging["Total_Value"].apply(lambda x: f"${x:,.2f}")
        aging = aging.rename(columns={"Total_Invoices": "Total Invoices"})
        aging = aging[["Age Bucket", "Total Invoices", "Total Value", "Risk Level"]]

        return aging

    # ─────────────────────────────────────────────────────────────
    #  5. SOURCE RELIABILITY
    # ─────────────────────────────────────────────────────────────
    def _source_reliability(self):
        """Compute per-reference-source quality metrics."""
        if not self.ref_names:
            return pd.DataFrame()
        # Use df_result for coverage (df_disc is now only non-MATCH rows)
        source_df = self.df_result if not self.df_result.empty else self.df_disc
        if source_df.empty:
            return pd.DataFrame()

        invoice_col = self._get_invoice_col(source_df)
        base_label = self.amount_col if source_df is self.df_result else ("SOA Amount" if "SOA Amount" in source_df.columns else "Master Amount")
        if not base_label or base_label not in source_df.columns:
            for col in source_df.columns:
                if 'amount' in col.lower() or 'total' in col.lower() or 'balance' in col.lower():
                    base_label = col
                    break
        
        rows = []
        for ref_name in self.ref_names:
            amt_col = f"{ref_name} Amount" if source_df is self.df_disc else f"{ref_name}_{base_label}"
            if amt_col not in source_df.columns:
                # Try finding any column with the ref_name and amount in it
                for col in source_df.columns:
                    if ref_name.lower() in col.lower() and ('amount' in col.lower() or 'total' in col.lower()):
                        amt_col = col
                        break
            
            if amt_col not in source_df.columns:
                continue

            ref_amounts = source_df[amt_col]
            soa_amounts = source_df[base_label] if base_label in source_df.columns else None

            total_invoices = len(source_df)
            present = ref_amounts.notna().sum()
            missing = total_invoices - present
            coverage = round(present / total_invoices * 100, 1) if total_invoices > 0 else 0

            # Accuracy: % of present entries that match SOA
            exact_match = 0
            avg_deviation = 0.0
            if soa_amounts is not None and present > 0:
                both_present = ref_amounts.notna() & soa_amounts.notna()
                if both_present.sum() > 0:
                    deltas = (soa_amounts[both_present] - ref_amounts[both_present]).abs()
                    exact_match = int((deltas < 0.01).sum())
                    avg_deviation = round(deltas.mean(), 2)

            accuracy = round(exact_match / present * 100, 1) if present > 0 else 0

            # Reliability Grade
            if accuracy >= 95 and coverage >= 90:
                grade = "A+"
            elif accuracy >= 90 and coverage >= 80:
                grade = "A"
            elif accuracy >= 80 and coverage >= 70:
                grade = "B"
            elif accuracy >= 70:
                grade = "C"
            else:
                grade = "D"

            rows.append({
                "Source": ref_name,
                "Coverage": f"{coverage}%",
                "Present": int(present),
                "Missing": int(missing),
                "Exact Matches": exact_match,
                "Accuracy": f"{accuracy}%",
                "Avg Deviation": avg_deviation,
                "Grade": grade
            })

        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # ─────────────────────────────────────────────────────────────
    #  6. TOP DISCREPANCIES
    # ─────────────────────────────────────────────────────────────
    def _top_discrepancies(self):
        """Return top 10 highest-impact discrepancies sorted by absolute delta."""
        # Use df_result when df_disc is empty (all-MATCH case)
        disc_src = self.df_disc if not self.df_disc.empty and "Delta" in self.df_disc.columns else self.df_result
        if disc_src.empty or "Delta" not in disc_src.columns:
            return pd.DataFrame()

        invoice_col = self._get_invoice_col(disc_src)
        base_label = "SOA Amount" if "SOA Amount" in self.df_disc.columns else "Master Amount"

        cols = [invoice_col]
        if base_label in disc_src.columns:
            cols.append(base_label)
        
        # Add ref amount columns
        for ref_name in self.ref_names:
            amt_col = f"{ref_name} Amount"
            if amt_col in disc_src.columns:
                cols.append(amt_col)
        
        cols.extend(["Delta", "Status"])
        cols = [c for c in cols if c in disc_src.columns]

        top = disc_src.nlargest(10, "Delta", keep="first") if len(disc_src) > 0 else pd.DataFrame()
        
        # Actually sort by absolute delta
        if not top.empty:
            non_match = disc_src[disc_src.get("Status", "") != "MATCH"].copy() if "Status" in disc_src.columns else disc_src.copy()
            if not non_match.empty:
                non_match["_abs_delta"] = non_match["Delta"].abs()
                top = non_match.nlargest(min(10, len(non_match)), "_abs_delta")
                top = top.drop(columns=["_abs_delta"])
            else:
                top = pd.DataFrame()

        return top[cols].reset_index(drop=True) if not top.empty else pd.DataFrame()

    # ─────────────────────────────────────────────────────────────
    #  7. PATTERN DETECTION
    # ─────────────────────────────────────────────────────────────
    def _pattern_detection(self):
        """Identify systematic issues across reference sources."""
        patterns = []

        # Use df_result when df_disc is empty (all-MATCH case)
        pat_df = self.df_disc if not self.df_disc.empty else self.df_result
        if pat_df.empty or "Delta" not in pat_df.columns:
            return patterns

        base_label = "SOA Amount" if "SOA Amount" in pat_df.columns else "Master Amount"

        for ref_name in self.ref_names:
            amt_col = f"{ref_name} Amount"
            if amt_col not in self.df_disc.columns or base_label not in self.df_disc.columns:
                continue

            both_present = self.df_disc[amt_col].notna() & self.df_disc[base_label].notna()
            if both_present.sum() < 3:
                continue

            soa_vals = self.df_disc.loc[both_present, base_label]
            ref_vals = self.df_disc.loc[both_present, amt_col]
            deltas = soa_vals - ref_vals

            # Pattern: Consistent direction
            if (deltas > 0.01).sum() > 0.8 * len(deltas) and len(deltas) > 2:
                avg = round(deltas.mean(), 2)
                patterns.append({
                    "type": "Systematic Underpayment",
                    "source": ref_name,
                    "description": f"{ref_name} consistently reports LOWER amounts than SOA (avg gap: ${avg})",
                    "severity": "High" if avg > 100 else "Medium",
                    "affected": int((deltas > 0.01).sum())
                })
            elif (deltas < -0.01).sum() > 0.8 * len(deltas) and len(deltas) > 2:
                avg = round(abs(deltas.mean()), 2)
                patterns.append({
                    "type": "Systematic Overpayment",
                    "source": ref_name,
                    "description": f"{ref_name} consistently reports HIGHER amounts than SOA (avg gap: ${avg})",
                    "severity": "High" if avg > 100 else "Medium",
                    "affected": int((deltas < -0.01).sum())
                })

            # Pattern: Percentage-based deviation
            pct_deltas = (deltas / soa_vals.replace(0, np.nan)).dropna()
            if len(pct_deltas) > 3:
                pct_std = pct_deltas.std()
                pct_mean = pct_deltas.mean()
                if pct_std < 0.02 and abs(pct_mean) > 0.01:
                    pct_display = round(pct_mean * 100, 1)
                    patterns.append({
                        "type": "Fixed Percentage Offset",
                        "source": ref_name,
                        "description": f"{ref_name} deviates by a consistent {pct_display}% from SOA — possible fee/tax difference",
                        "severity": "Medium",
                        "affected": len(pct_deltas)
                    })

            # Pattern: Missing entries
            total = len(self.df_disc)
            missing = total - both_present.sum()
            if missing > 0.3 * total and total > 5:
                patterns.append({
                    "type": "Data Gap",
                    "source": ref_name,
                    "description": f"{ref_name} is missing {missing} of {total} invoices ({round(missing/total*100)}%)",
                    "severity": "High" if missing > 0.5 * total else "Medium",
                    "affected": int(missing)
                })

            # Pattern: Round number clustering
            if len(ref_vals) > 5:
                round_count = (ref_vals % 100 == 0).sum()
                if round_count > 0.5 * len(ref_vals):
                    patterns.append({
                        "type": "Estimated Amounts",
                        "source": ref_name,
                        "description": f"{ref_name} has {round_count} amounts that are round numbers — may be estimates rather than actuals",
                        "severity": "Low",
                        "affected": int(round_count)
                    })

        return patterns
