"""
NL Visualizer - Rule-Based Natural Language Charting
-----------------------------------------------------
Turns a plain-English prompt ("average revenue by region as a bar chart",
"top 5 products by units sold", "trend of sales over time") into a chart,
using only regex + fuzzy column-name matching (rapidfuzz). No LLM / API
calls, no external cost - everything runs locally against the dataframe
already in memory.

Public entry points:
    parse_prompt(prompt, columns)      -> spec dict
    apply_spec(df, spec)               -> (result_df, x, y)
    render_chart(result_df, x, y, spec) -> plotly Figure

Author: Dev Anand (portfolio project)
"""

import re
import pandas as pd
import plotly.express as px
from rapidfuzz import process, fuzz

CHART_KEYWORDS = {
    "bar": ["bar"],
    "line": ["line"],
    "pie": ["pie"],
    "scatter": ["scatter"],
    "histogram": ["histogram", "distribution"],
    "box": ["box", "boxplot", "spread"],
    "heatmap": ["heatmap", "correlation", "correlations"],
}

AGG_KEYWORDS = {
    "mean": ["average", "avg", "mean"],
    "sum": ["sum", "total"],
    "count": ["count", "number of", "how many", "counts"],
    "max": ["max", "maximum", "highest", "largest"],
    "min": ["min", "minimum", "lowest", "smallest"],
    "median": ["median"],
}

STOPWORDS = {"the", "a", "an", "of", "for", "in", "on", "chart", "graph", "plot", "as"}


# ---------- column matching ----------

def match_column(phrase: str, columns: list, min_score: int = 60):
    """Fuzzy-match a free-text phrase against the dataframe's real column names."""
    phrase = phrase.strip().strip(".,")
    if not phrase or not columns:
        return None
    result = process.extractOne(phrase, columns, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= min_score:
        return result[0]
    return None


def find_best_column_in_text(text: str, columns: list, min_score: int = 65):
    """Slide across word n-grams in text and return the best-matching real column, if any."""
    words = re.findall(r"[a-zA-Z0-9_]+", text)
    best = None
    best_score = 0
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            candidate = " ".join(words[i:i + n])
            if candidate.lower() in STOPWORDS:
                continue
            result = process.extractOne(candidate, columns, scorer=fuzz.token_sort_ratio)
            if result and result[1] > best_score and result[1] >= min_score:
                best, best_score = result[0], result[1]
    return best


# ---------- parsing ----------

def _detect_chart_type(prompt_lower: str):
    for chart_type, keywords in CHART_KEYWORDS.items():
        if any(kw in prompt_lower for kw in keywords):
            return chart_type
    return None


def _detect_agg(prompt_lower: str):
    for agg, keywords in AGG_KEYWORDS.items():
        if any(kw in prompt_lower for kw in keywords):
            return agg
    return None


def parse_prompt(prompt: str, columns: list) -> dict:
    """Turn a plain-English prompt into a chart spec dict, using only local rules."""
    prompt_lower = prompt.lower()

    spec = {
        "operation": "raw",
        "chart_type": _detect_chart_type(prompt_lower),
        "x": None,
        "y": None,
        "agg": _detect_agg(prompt_lower),
        "sort": None,
        "limit": None,
        "filter": None,
        "title": prompt.strip().capitalize(),
    }

    # --- top N / bottom N ---
    topn_match = re.search(r"\b(top|bottom)\s+(\d+)\b", prompt_lower)
    if topn_match:
        spec["operation"] = "top_n"
        spec["sort"] = "desc" if topn_match.group(1) == "top" else "asc"
        spec["limit"] = int(topn_match.group(2))

    # --- trend / over time ---
    if re.search(r"\btrend|\bover time\b", prompt_lower):
        spec["operation"] = "trend"
        spec["sort"] = "asc"
        if not spec["chart_type"]:
            spec["chart_type"] = "line"

    # --- "where <col> <op> <val>" filter ---
    filt_match = re.search(
        r"where\s+([a-zA-Z][a-zA-Z0-9_ ]*?)\s*(==|=|is not|!=|>=|<=|>|<|is|contains)\s*([a-zA-Z0-9_. ]+)",
        prompt_lower,
    )
    if filt_match:
        raw_col, raw_op, raw_val = filt_match.groups()
        col = match_column(raw_col, columns)
        op_map = {"=": "==", "is": "==", "is not": "!=", "==": "==", "!=": "!=",
                  ">": ">", "<": "<", ">=": ">=", "<=": "<=", "contains": "contains"}
        if col:
            spec["filter"] = {"column": col, "op": op_map.get(raw_op.strip(), "=="),
                               "value": raw_val.strip()}

    # --- "X vs Y" -> scatter with explicit axes ---
    vs_match = re.search(r"([a-zA-Z][a-zA-Z0-9_ ]*?)\s+vs\.?\s+([a-zA-Z][a-zA-Z0-9_ ]*)", prompt_lower)
    if vs_match:
        x_col = match_column(vs_match.group(1), columns)
        y_col = match_column(vs_match.group(2), columns)
        if x_col and y_col:
            spec["x"], spec["y"] = x_col, y_col
            if not spec["chart_type"]:
                spec["chart_type"] = "scatter"

    # --- "<agg> <value col> by <category col>" (or, for top/bottom N,
    # "top N <category> by <value col>" - the roles are reversed: the
    # column after "by" is what gets sorted on, the entity being counted
    # comes from the text before "by") ---
    by_match = re.search(r"\bby\s+([a-zA-Z][a-zA-Z0-9_ ]*)", prompt_lower)
    if by_match and not spec["x"]:
        after_col = match_column(by_match.group(1), columns)
        if after_col:
            if spec["operation"] == "top_n":
                spec["y"] = after_col
            else:
                spec["x"] = after_col

    if spec["operation"] == "top_n" and not spec["x"]:
        remainder = prompt_lower[:by_match.start()] if by_match else prompt_lower
        cat_col = find_best_column_in_text(remainder, [c for c in columns if c != spec["y"]])
        if cat_col:
            spec["x"] = cat_col

    if not spec["y"]:
        # look for a value column mentioned right after an agg keyword,
        # or elsewhere in the prompt (excluding whatever text matched the category)
        remainder = prompt_lower
        if by_match:
            remainder = prompt_lower[:by_match.start()]
        val_col = find_best_column_in_text(remainder, [c for c in columns if c != spec["x"]])
        if val_col:
            spec["y"] = val_col

    # If we found a category + agg but no explicit chart type, default to bar
    if spec["x"] and spec["agg"] and not spec["chart_type"]:
        spec["chart_type"] = "bar"

    if spec["x"] and spec["agg"]:
        if spec["operation"] == "raw":
            spec["operation"] = "groupby"

    # --- final fallbacks ---
    if not spec["chart_type"]:
        spec["chart_type"] = "bar" if spec["x"] else "histogram"
    if spec["chart_type"] == "heatmap":
        spec["x"], spec["y"], spec["agg"] = None, None, None
    if not spec["x"] and spec["chart_type"] in ("bar", "pie", "box") and columns:
        # last resort: pick the first non-numeric-looking column name mentioned anywhere
        spec["x"] = find_best_column_in_text(prompt_lower, columns) or columns[0]

    return spec


# ---------- execution ----------

def apply_filter(df: pd.DataFrame, filt: dict) -> pd.DataFrame:
    col, op, val = filt["column"], filt["op"], filt.get("value")
    series = df[col]
    if pd.api.types.is_numeric_dtype(series):
        try:
            val = float(val)
        except (TypeError, ValueError):
            pass
    if op == "==":
        return df[series.astype(str).str.lower() == str(val).lower()] if series.dtype == object else df[series == val]
    if op == "!=":
        return df[series.astype(str).str.lower() != str(val).lower()] if series.dtype == object else df[series != val]
    if op == ">":
        return df[series > val]
    if op == ">=":
        return df[series >= val]
    if op == "<":
        return df[series < val]
    if op == "<=":
        return df[series <= val]
    if op == "contains":
        return df[series.astype(str).str.contains(str(val), case=False, na=False)]
    return df


def apply_spec(df: pd.DataFrame, spec: dict):
    d = df.copy()

    if spec.get("filter"):
        try:
            d = apply_filter(d, spec["filter"])
        except Exception:
            pass  # ignore a bad filter rather than fail the whole chart

    if spec["chart_type"] == "heatmap":
        return d.select_dtypes(include="number").corr(), None, None

    x, y, agg = spec.get("x"), spec.get("y"), spec.get("agg")
    operation = spec.get("operation", "raw")

    if operation in ("groupby", "top_n", "trend") and x:
        if y and agg and y in d.columns:
            d = d.groupby(x, as_index=False)[y].agg(agg)
        elif agg == "count" or (not y):
            d = d.groupby(x, as_index=False).size().rename(columns={"size": "count"})
            y = "count"

    sort = spec.get("sort")
    if sort and y in d.columns:
        d = d.sort_values(y, ascending=(sort == "asc"))
    elif operation == "trend" and x in d.columns:
        d = d.sort_values(x)

    limit = spec.get("limit")
    if limit:
        d = d.head(int(limit))

    return d, x, y


def render_chart(d: pd.DataFrame, x, y, spec: dict):
    chart_type = spec["chart_type"]
    title = spec.get("title") or ""

    if chart_type == "heatmap":
        return px.imshow(d, text_auto=True, title=title or "Correlation heatmap")
    if chart_type == "bar":
        return px.bar(d, x=x, y=y, title=title)
    if chart_type == "line":
        return px.line(d, x=x, y=y, title=title)
    if chart_type == "scatter":
        return px.scatter(d, x=x, y=y, title=title)
    if chart_type == "pie":
        return px.pie(d, names=x, values=y, title=title)
    if chart_type == "histogram":
        return px.histogram(d, x=x or (d.select_dtypes(include="number").columns[0] if not d.select_dtypes(include="number").empty else d.columns[0]), title=title)
    if chart_type == "box":
        return px.box(d, x=x, y=y, title=title)
    raise ValueError(f"Unsupported chart_type: {chart_type}")
