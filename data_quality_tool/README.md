# Data Quality Tool

A Python + Streamlit tool that scans a CSV dataset for common data quality
issues and produces a scored report, charts, and plain-language fix suggestions.

## What it checks
- Missing values (nulls + blank strings)
- Duplicate records
- Data type validation
- Email / phone / date format validation
- Range validation (e.g. age 0–120)
- Negative / invalid values
- Consistency (same ID → same value, e.g. customer_id → name)
- Uniqueness (primary key columns)
- Completeness score + overall weighted quality score

## Project structure
```
data_quality_tool/
├── quality_checker.py   # Core DataQualityChecker class (all check logic + scoring)
├── app.py               # Streamlit UI
├── sample_data.csv      # Sample dataset with seeded issues, for demo
└── requirements.txt
```

## Run it locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Then upload `sample_data.csv` (or your own CSV) in the browser UI.

## How the score works
Each check contributes a "penalty" equal to the % of rows it flagged
(capped at 100). The overall score is `100 - average penalty across all
checks run`. This keeps the score interpretable: a check that flags 1% of
rows barely moves the needle, one flagging 50% tanks it.

## Extending it
- `quality_checker.py` is UI-agnostic — you can import `DataQualityChecker`
  into a Jupyter notebook, a scheduled script, or a FastAPI backend.
- `auto_fix()` currently handles duplicate removal and simple missing-value
  imputation (mean/median/mode/constant). Add more strategies as needed.
- Natural next steps: schema-based type checking (Pandera), scheduled runs
  with alerts, and a history table (SQLite) to track score drift over time.
