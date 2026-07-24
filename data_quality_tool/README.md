# Data Quality Tool

A Python + Streamlit tool that scans a dataset (CSV, Excel, or JSON) for
common data quality issues and produces a scored report, charts, a
downloadable PDF, and plain-language fix suggestions. Includes score
history tracking and config-driven (YAML) rule definitions.

## What it checks
- Missing values (nulls + blank strings)
- Duplicate records
- Data type validation
- Email / phone / date format validation
- Range validation (e.g. age 0–120)
- Negative / invalid values
- Consistency (same ID → same value, e.g. customer_id → name)
- Uniqueness (primary key columns)
- **Inconsistent naming / fuzzy near-duplicates** (e.g. "IBM" vs "I.B.M." vs "International Business Machines") using rapidfuzz
- **Auto-detected column types** (email/phone/date/numeric/id) to pre-fill the UI
- Completeness score + overall weighted quality score

## Project structure
```
data_quality_tool/
├── quality_checker.py   # Core DataQualityChecker class (all check logic, scoring, fuzzy match, auto-detect)
├── history_tracker.py   # SQLite-backed score history (tracks quality drift over time)
├── rule_config.py       # YAML-based rule config loader (config-driven checks, no UI clicking needed)
├── pdf_report.py         # Generates a polished PDF report from a run's results
├── rules.yaml           # Example rule config file
├── app.py               # Streamlit UI (2 tabs: Run Checks, Score History)
├── sample_data.csv      # Sample dataset with seeded issues, for demo
└── requirements.txt
```

## New in this version
- **Multi-format input**: upload CSV, Excel (.xlsx/.xls), or JSON
- **Auto column-type detection**: the tool samples each column and guesses
  its type, pre-selecting likely email/phone/date/ID columns in the sidebar
- **Fuzzy inconsistent-naming check**: flags near-duplicate text entries
  (e.g. company or customer names spelled/formatted differently)
- **Config-driven mode**: upload a `rules.yaml` instead of clicking through
  the sidebar each time — mirrors how real tools like Great Expectations/dbt
  separate "what to check" from "how to check it"
- **Score history (SQLite)**: every run is logged with a timestamp; a
  second tab charts your quality score over time across multiple uploads
- **PDF export**: download a formatted PDF report alongside the CSV report

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
