"""
Data Quality Checker - Core Engine
-----------------------------------
A reusable class that runs a suite of data quality checks on a pandas
DataFrame and produces a structured report + an overall quality score.

Author: Dev Anand (portfolio project)
"""

import re
import pandas as pd
import numpy as np
from datetime import datetime
from rapidfuzz import fuzz


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}$")

# Common date formats we try when validating / parsing date columns
DATE_FORMATS = [
    "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y",
    "%Y/%m/%d", "%d %b %Y", "%B %d, %Y",
]


class DataQualityChecker:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.original_df = df.copy()
        self.results = {}  # check_name -> dict(status, issues_found, details)
        self.total_rows = len(df)

    # ---------- helpers ----------
    def _status(self, issue_count, warn_threshold_pct=2, fail_threshold_pct=5):
        """Turn an issue count into a ✅ / ⚠️ / ❌ status based on % of rows affected."""
        if self.total_rows == 0:
            return "✅"
        pct = (issue_count / self.total_rows) * 100
        if issue_count == 0:
            return "✅"
        elif pct <= warn_threshold_pct:
            return "⚠️"
        else:
            return "❌"

    def _try_parse_date(self, value):
        if pd.isna(value):
            return None
        value = str(value).strip()
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    # ---------- checks ----------
    def check_missing_values(self, columns=None):
        cols = columns or self.df.columns.tolist()
        missing_counts = {}
        total_missing = 0
        for col in cols:
            if col not in self.df.columns:
                continue
            n_missing = int(self.df[col].isna().sum())
            # also treat empty strings / whitespace-only strings as missing
            if self.df[col].dtype == object:
                n_missing += int(
                    self.df[col].astype(str).str.strip().eq("").sum()
                )
            missing_counts[col] = n_missing
            total_missing += n_missing

        self.results["Missing Values"] = {
            "status": self._status(total_missing),
            "issues_found": total_missing,
            "details": missing_counts,
        }
        return missing_counts

    def check_duplicates(self, subset=None):
        dup_mask = self.df.duplicated(subset=subset, keep="first")
        n_dupes = int(dup_mask.sum())
        self.results["Duplicate Records"] = {
            "status": self._status(n_dupes),
            "issues_found": n_dupes,
            "details": {"duplicate_row_indices": self.df[dup_mask].index.tolist()},
        }
        return n_dupes

    def check_data_types(self, expected_types: dict):
        """expected_types e.g. {'age': 'numeric', 'signup_date': 'date'}"""
        mismatches = {}
        total_bad = 0
        for col, expected in expected_types.items():
            if col not in self.df.columns:
                continue
            bad_rows = []
            for idx, val in self.df[col].items():
                if pd.isna(val):
                    continue
                if expected == "numeric":
                    try:
                        float(val)
                    except (ValueError, TypeError):
                        bad_rows.append(idx)
                elif expected == "date":
                    if self._try_parse_date(val) is None:
                        bad_rows.append(idx)
            if bad_rows:
                mismatches[col] = bad_rows
                total_bad += len(bad_rows)

        self.results["Data Type Validation"] = {
            "status": self._status(total_bad),
            "issues_found": total_bad,
            "details": mismatches,
        }
        return mismatches

    def check_email_format(self, column):
        if column not in self.df.columns:
            return []
        invalid = self.df[
            self.df[column].notna()
            & ~self.df[column].astype(str).str.match(EMAIL_REGEX)
        ]
        self.results["Invalid Emails"] = {
            "status": self._status(len(invalid)),
            "issues_found": len(invalid),
            "details": {"invalid_row_indices": invalid.index.tolist()},
        }
        return invalid.index.tolist()

    def check_phone_format(self, column):
        if column not in self.df.columns:
            return []
        invalid = self.df[
            self.df[column].notna()
            & ~self.df[column].astype(str).str.match(PHONE_REGEX)
        ]
        self.results["Invalid Phone Numbers"] = {
            "status": self._status(len(invalid)),
            "issues_found": len(invalid),
            "details": {"invalid_row_indices": invalid.index.tolist()},
        }
        return invalid.index.tolist()

    def check_date_format(self, column):
        if column not in self.df.columns:
            return []
        bad_rows = [
            idx for idx, val in self.df[column].items()
            if pd.notna(val) and self._try_parse_date(val) is None
        ]
        self.results["Wrong Date Format"] = {
            "status": self._status(len(bad_rows)),
            "issues_found": len(bad_rows),
            "details": {"invalid_row_indices": bad_rows},
        }
        return bad_rows

    def check_range(self, column, min_val, max_val):
        if column not in self.df.columns:
            return []
        numeric_col = pd.to_numeric(self.df[column], errors="coerce")
        out_of_range = self.df[
            numeric_col.notna() & ((numeric_col < min_val) | (numeric_col > max_val))
        ]
        self.results[f"Range Check ({column})"] = {
            "status": self._status(len(out_of_range)),
            "issues_found": len(out_of_range),
            "details": {"invalid_row_indices": out_of_range.index.tolist()},
        }
        return out_of_range.index.tolist()

    def check_negative_values(self, column):
        if column not in self.df.columns:
            return []
        numeric_col = pd.to_numeric(self.df[column], errors="coerce")
        negatives = self.df[numeric_col.notna() & (numeric_col < 0)]
        self.results[f"Negative Values ({column})"] = {
            "status": self._status(len(negatives)),
            "issues_found": len(negatives),
            "details": {"invalid_row_indices": negatives.index.tolist()},
        }
        return negatives.index.tolist()

    def check_consistency(self, id_column, value_column):
        """Same ID should always map to the same value (e.g. same customer_id -> same name)."""
        if id_column not in self.df.columns or value_column not in self.df.columns:
            return {}
        grouped = self.df.groupby(id_column)[value_column].nunique(dropna=True)
        inconsistent_ids = grouped[grouped > 1].index.tolist()
        self.results[f"Consistency ({id_column} -> {value_column})"] = {
            "status": self._status(len(inconsistent_ids)),
            "issues_found": len(inconsistent_ids),
            "details": {"inconsistent_ids": inconsistent_ids},
        }
        return inconsistent_ids

    def check_uniqueness(self, column):
        """For primary-key-like columns: every value should be unique."""
        if column not in self.df.columns:
            return []
        dup_mask = self.df[column].duplicated(keep=False) & self.df[column].notna()
        dup_values = self.df[dup_mask]
        self.results[f"Uniqueness ({column})"] = {
            "status": self._status(len(dup_values)),
            "issues_found": len(dup_values),
            "details": {"duplicate_row_indices": dup_values.index.tolist()},
        }
        return dup_values.index.tolist()

    def check_fuzzy_duplicates(self, column, similarity_threshold=85):
        """Flags near-duplicate entity names that likely refer to the same thing
        but are spelled/formatted differently — e.g. 'IBM' vs 'I.B.M.' vs
        'International Business Machines'. Uses rapidfuzz token_sort_ratio.

        Returns a list of groups, where each group is a list of (index, value)
        pairs that are considered near-duplicates of each other.
        """
        if column not in self.df.columns:
            return []

        values = self.df[column].dropna().astype(str)
        normalized = values.apply(lambda v: re.sub(r"[.\s]+", " ", v).strip().lower())

        seen = set()
        groups = []
        items = list(normalized.items())

        for i in range(len(items)):
            idx_i, val_i = items[i]
            if idx_i in seen:
                continue
            group = [(idx_i, values[idx_i])]
            for j in range(i + 1, len(items)):
                idx_j, val_j = items[j]
                if idx_j in seen:
                    continue
                score = fuzz.token_sort_ratio(val_i, val_j)
                if score >= similarity_threshold:
                    group.append((idx_j, values[idx_j]))
                    seen.add(idx_j)
            if len(group) > 1:
                seen.add(idx_i)
                groups.append(group)

        total_flagged = sum(len(g) for g in groups)
        self.results[f"Inconsistent Naming ({column})"] = {
            "status": self._status(total_flagged),
            "issues_found": total_flagged,
            "details": {"near_duplicate_groups": groups},
        }
        return groups

    def suggest_column_types(self, sample_size=50):
        """Auto-detects likely semantic type for each column by sampling values
        and testing them against known patterns. Returns a dict like:
        {'email': 'email', 'signup_date': 'date', 'age': 'numeric', 'customer_id': 'id/unique'}
        This is a heuristic aid for the UI — not a hard classification.
        """
        suggestions = {}
        for col in self.df.columns:
            sample = self.df[col].dropna().astype(str).head(sample_size)
            if sample.empty:
                suggestions[col] = "unknown"
                continue

            n = len(sample)
            email_hits = sample.str.match(EMAIL_REGEX).sum()
            phone_hits = sample.str.match(PHONE_REGEX).sum()
            date_hits = sample.apply(lambda v: self._try_parse_date(v) is not None).sum()
            numeric_hits = pd.to_numeric(sample, errors="coerce").notna().sum()

            col_lower = col.lower()
            if email_hits / n > 0.7:
                suggestions[col] = "email"
            elif phone_hits / n > 0.7:
                suggestions[col] = "phone"
            elif date_hits / n > 0.7:
                suggestions[col] = "date"
            elif numeric_hits / n > 0.9:
                suggestions[col] = "numeric"
            elif "id" in col_lower and self.df[col].is_unique:
                suggestions[col] = "id/unique"
            elif "name" in col_lower:
                suggestions[col] = "name/text"
            else:
                suggestions[col] = "text"
        return suggestions

    # ---------- scoring ----------
    def completeness_score(self):
        total_cells = self.df.size
        if total_cells == 0:
            return 100.0
        missing_cells = self.df.isna().sum().sum()
        return round(100 * (1 - missing_cells / total_cells), 2)

    def overall_score(self):
        """Weighted score: fewer issues relative to row count = higher score.
        Each check contributes based on % of rows affected, capped at 100."""
        if not self.results:
            return 100.0
        penalties = []
        for check_name, res in self.results.items():
            issues = res["issues_found"]
            pct_affected = (issues / self.total_rows * 100) if self.total_rows else 0
            penalties.append(min(pct_affected, 100))
        avg_penalty = sum(penalties) / len(penalties)
        score = max(0, 100 - avg_penalty)
        return round(score, 1)

    def score_label(self, score):
        if score >= 90:
            return "Excellent"
        elif score >= 75:
            return "Good"
        elif score >= 60:
            return "Needs Improvement"
        else:
            return "Poor"

    # ---------- report ----------
    def generate_report(self):
        rows = []
        for check_name, res in self.results.items():
            rows.append({
                "Check": check_name,
                "Status": res["status"],
                "Issues Found": res["issues_found"],
            })
        report_df = pd.DataFrame(rows)
        score = self.overall_score()
        summary = {
            "report": report_df,
            "completeness_score": self.completeness_score(),
            "overall_score": score,
            "quality_label": self.score_label(score),
        }
        return summary

    def suggestions(self):
        """Plain-language suggestions based on which checks failed."""
        tips = []
        for check_name, res in self.results.items():
            if res["issues_found"] == 0:
                continue
            if "Missing" in check_name:
                tips.append(f"'{check_name}': Consider imputing missing values (mean/median/mode) or dropping rows/columns with excessive nulls.")
            elif "Duplicate" in check_name:
                tips.append(f"'{check_name}': Remove duplicate rows using `drop_duplicates()`, keeping the most recent record.")
            elif "Email" in check_name:
                tips.append(f"'{check_name}': Flag or correct malformed emails; consider a verification step before storing.")
            elif "Phone" in check_name:
                tips.append(f"'{check_name}': Standardize phone numbers to a single format (e.g. E.164) during ingestion.")
            elif "Date" in check_name:
                tips.append(f"'{check_name}': Normalize all dates to ISO format (YYYY-MM-DD) at the source or during ETL.")
            elif "Range" in check_name or "Negative" in check_name:
                tips.append(f"'{check_name}': Add input validation at the point of entry to reject out-of-range values.")
            elif "Consistency" in check_name:
                tips.append(f"'{check_name}': Investigate records where the same ID has conflicting values; pick a source of truth.")
            elif "Uniqueness" in check_name:
                tips.append(f"'{check_name}': This column should be a primary key — remove or merge duplicate key values.")
            else:
                tips.append(f"'{check_name}': Review the {res['issues_found']} flagged rows manually.")
        return tips

    # ---------- auto-fix ----------
    def auto_fix(self, drop_duplicates=True, fill_missing_strategy=None, dedupe_subset=None):
        """Applies simple, safe automatic fixes and returns a cleaned copy of the DataFrame.
        fill_missing_strategy: dict like {'age': 'median', 'city': 'mode'} or a constant value.
        """
        fixed = self.df.copy()

        if drop_duplicates:
            fixed = fixed.drop_duplicates(subset=dedupe_subset, keep="first")

        if fill_missing_strategy:
            for col, strategy in fill_missing_strategy.items():
                if col not in fixed.columns:
                    continue
                if strategy == "median":
                    fixed[col] = fixed[col].fillna(pd.to_numeric(fixed[col], errors="coerce").median())
                elif strategy == "mean":
                    fixed[col] = fixed[col].fillna(pd.to_numeric(fixed[col], errors="coerce").mean())
                elif strategy == "mode":
                    mode_val = fixed[col].mode(dropna=True)
                    if not mode_val.empty:
                        fixed[col] = fixed[col].fillna(mode_val.iloc[0])
                else:
                    fixed[col] = fixed[col].fillna(strategy)

        return fixed
