"""
Data Quality Tool - Streamlit App
----------------------------------
Upload a CSV, configure which checks to run, and get a quality report
with an overall score, charts, suggestions, and an optional auto-fixed
download.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from quality_checker import DataQualityChecker

st.set_page_config(page_title="Data Quality Tool", layout="wide")

st.title("🧹 Data Quality Tool")
st.caption("Upload a dataset, run automated quality checks, and get a report with a quality score.")

# ---------------- Sidebar: upload + config ----------------
st.sidebar.header("1. Upload Data")
uploaded_file = st.sidebar.file_uploader("Upload a CSV file", type=["csv"])

if uploaded_file is None:
    st.info("👈 Upload a CSV file to get started, or try the bundled sample_data.csv.")
    st.stop()

df = pd.read_csv(uploaded_file)
st.subheader("Preview of Uploaded Data")
st.dataframe(df.head(10), use_container_width=True)
st.caption(f"{len(df)} rows x {len(df.columns)} columns")

checker = DataQualityChecker(df)
columns = df.columns.tolist()

st.sidebar.header("2. Configure Checks")

# Missing values - always run on all columns
run_missing = st.sidebar.checkbox("Check missing values", value=True)
run_duplicates = st.sidebar.checkbox("Check duplicate rows", value=True)

st.sidebar.subheader("Format Checks")
email_col = st.sidebar.selectbox("Email column (optional)", ["-- none --"] + columns)
phone_col = st.sidebar.selectbox("Phone column (optional)", ["-- none --"] + columns)
date_col = st.sidebar.selectbox("Date column (optional)", ["-- none --"] + columns)

st.sidebar.subheader("Range Check")
range_col = st.sidebar.selectbox("Numeric column (optional)", ["-- none --"] + columns)
if range_col != "-- none --":
    min_val, max_val = st.sidebar.slider(
        "Valid range", 0, 1000, (0, 120)
    )

st.sidebar.subheader("Uniqueness / Consistency")
pk_col = st.sidebar.selectbox("Primary key column (optional)", ["-- none --"] + columns)
id_col = st.sidebar.selectbox("ID column for consistency (optional)", ["-- none --"] + columns)
value_col = st.sidebar.selectbox("Value that should match the ID (optional)", ["-- none --"] + columns)

run_button = st.sidebar.button("🚀 Run Quality Checks", type="primary")

# ---------------- Run checks ----------------
if run_button:
    if run_missing:
        checker.check_missing_values()
    if run_duplicates:
        checker.check_duplicates()
    if email_col != "-- none --":
        checker.check_email_format(email_col)
    if phone_col != "-- none --":
        checker.check_phone_format(phone_col)
    if date_col != "-- none --":
        checker.check_date_format(date_col)
    if range_col != "-- none --":
        checker.check_range(range_col, min_val, max_val)
        checker.check_negative_values(range_col)
    if pk_col != "-- none --":
        checker.check_uniqueness(pk_col)
    if id_col != "-- none --" and value_col != "-- none --":
        checker.check_consistency(id_col, value_col)

    summary = checker.generate_report()

    st.header("📊 Quality Report")

    col1, col2, col3 = st.columns(3)
    col1.metric("Overall Quality Score", f"{summary['overall_score']}/100", summary["quality_label"])
    col2.metric("Completeness Score", f"{summary['completeness_score']}%")
    col3.metric("Checks Run", len(checker.results))

    st.subheader("Check Results")
    st.dataframe(summary["report"], use_container_width=True, hide_index=True)

    # Charts
    if not summary["report"].empty:
        fig = px.bar(
            summary["report"], x="Check", y="Issues Found", color="Status",
            title="Issues Found per Check",
            color_discrete_map={"✅": "#2ecc71", "⚠️": "#f39c12", "❌": "#e74c3c"},
        )
        st.plotly_chart(fig, use_container_width=True)

        gauge_fig = px.pie(
            values=[summary["overall_score"], 100 - summary["overall_score"]],
            names=["Score", "Gap"],
            hole=0.7,
            color_discrete_sequence=["#2ecc71", "#eeeeee"],
            title="Overall Quality Score",
        )
        gauge_fig.update_traces(textinfo="none")
        st.plotly_chart(gauge_fig, use_container_width=True)

    st.subheader("💡 Suggestions")
    tips = checker.suggestions()
    if tips:
        for tip in tips:
            st.markdown(f"- {tip}")
    else:
        st.success("No issues found — dataset looks clean!")

    # ---------------- Auto-fix ----------------
    st.header("🔧 Auto-Fix (Optional)")
    st.caption("Applies safe, simple fixes: drop duplicate rows and fill missing values.")

    fix_col1, fix_col2 = st.columns(2)
    do_dedupe = fix_col1.checkbox("Remove duplicate rows", value=True)
    fill_strategy_choice = fix_col2.selectbox(
        "Fill missing numeric values with", ["-- leave as is --", "median", "mean"]
    )

    if st.button("Apply Auto-Fix"):
        fill_strategy = None
        if fill_strategy_choice != "-- leave as is --" and range_col != "-- none --":
            fill_strategy = {range_col: fill_strategy_choice}

        cleaned_df = checker.auto_fix(
            drop_duplicates=do_dedupe,
            fill_missing_strategy=fill_strategy,
        )
        st.success(f"Auto-fix applied. Rows before: {len(df)}, after: {len(cleaned_df)}")
        st.dataframe(cleaned_df.head(10), use_container_width=True)

        csv_bytes = cleaned_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Cleaned CSV", data=csv_bytes,
            file_name="cleaned_data.csv", mime="text/csv",
        )

    # Downloadable report
    report_csv = summary["report"].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Quality Report (CSV)", data=report_csv,
        file_name="quality_report.csv", mime="text/csv",
    )
else:
    st.info("Configure your checks in the sidebar, then click **Run Quality Checks**.")
