"""
Data Quality Tool - Streamlit App (v2)
-----------------------------------------
Upload a CSV/Excel/JSON file, configure or auto-detect checks, run a full
quality scan (including fuzzy near-duplicate name detection), view a
scored report + charts, track score history over time, and export a
PDF report.

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from quality_checker import DataQualityChecker
from rule_config import load_rules, run_checks_from_rules, DEFAULT_RULES
from history_tracker import log_run, get_history, clear_history
from pdf_report import generate_pdf_report
import tempfile
import os

st.set_page_config(page_title="Data Quality Tool", layout="wide")

st.title("🧹 Data Quality Tool")
st.caption("Upload a dataset, run automated quality checks, track score history, and export a PDF report.")

tab_check, tab_history = st.tabs(["🔍 Run Checks", "📈 Score History"])

# =========================================================
# TAB 2: HISTORY (kept at top so it can be built independent of upload)
# =========================================================
with tab_history:
    st.subheader("Quality Score Trend Over Time")
    history_df = get_history()
    if history_df.empty:
        st.info("No runs logged yet. Run a check in the 'Run Checks' tab — each run is automatically saved here.")
    else:
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        trend_fig = px.line(
            history_df, x="timestamp", y="overall_score", color="dataset_name",
            markers=True, title="Overall Quality Score Over Time",
        )
        trend_fig.update_yaxes(range=[0, 100])
        st.plotly_chart(trend_fig, use_container_width=True)

        if st.button("🗑️ Clear History"):
            clear_history()
            st.rerun()

# =========================================================
# TAB 1: RUN CHECKS
# =========================================================
with tab_check:
    st.sidebar.header("1. Upload Data")
    uploaded_file = st.sidebar.file_uploader(
        "Upload a file", type=["csv", "xlsx", "xls", "json"]
    )

    if uploaded_file is None:
        st.info("👈 Upload a CSV, Excel, or JSON file to get started, or try the bundled sample_data.csv.")
        st.stop()

    # ---- read file based on extension ----
    fname = uploaded_file.name
    ext = fname.split(".")[-1].lower()
    try:
        if ext == "csv":
            df = pd.read_csv(uploaded_file)
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(uploaded_file)
        elif ext == "json":
            df = pd.read_json(uploaded_file)
        else:
            st.error(f"Unsupported file type: {ext}")
            st.stop()
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    st.subheader("Preview of Uploaded Data")
    st.dataframe(df.head(10), use_container_width=True)
    st.caption(f"{len(df)} rows x {len(df.columns)} columns")

    checker = DataQualityChecker(df)
    columns = df.columns.tolist()

    # ---- auto-detect column types ----
    st.sidebar.header("2. Auto-Detected Column Types")
    auto_types = checker.suggest_column_types()
    with st.sidebar.expander("View auto-detected types"):
        for col, t in auto_types.items():
            st.write(f"**{col}** → `{t}`")

    def best_guess(target_type):
        matches = [c for c, t in auto_types.items() if t == target_type]
        return matches[0] if matches else "-- none --"

    st.sidebar.header("3. Configure Checks")

    config_mode = st.sidebar.radio("Configuration mode", ["Manual (sidebar)", "Upload rules.yaml"])

    rules = None
    if config_mode == "Upload rules.yaml":
        rules_file = st.sidebar.file_uploader("Upload rules.yaml", type=["yaml", "yml"], key="rules_uploader")
        if rules_file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as tmp:
                tmp.write(rules_file.read())
                tmp_path = tmp.name
            rules = load_rules(tmp_path)
            os.unlink(tmp_path)
            st.sidebar.success("Rules loaded from file.")
        else:
            st.sidebar.info("Upload a rules.yaml to run config-driven checks, or switch back to Manual mode.")

    if config_mode == "Manual (sidebar)":
        run_missing = st.sidebar.checkbox("Check missing values", value=True)
        run_duplicates = st.sidebar.checkbox("Check duplicate rows", value=True)

        st.sidebar.subheader("Format Checks")
        options = ["-- none --"] + columns
        email_col = st.sidebar.selectbox("Email column", options, index=options.index(best_guess("email")) if best_guess("email") in options else 0)
        phone_col = st.sidebar.selectbox("Phone column", options, index=options.index(best_guess("phone")) if best_guess("phone") in options else 0)
        date_col = st.sidebar.selectbox("Date column", options, index=options.index(best_guess("date")) if best_guess("date") in options else 0)

        st.sidebar.subheader("Range Check")
        range_col = st.sidebar.selectbox("Numeric column (optional)", options)
        if range_col != "-- none --":
            min_val, max_val = st.sidebar.slider("Valid range", 0, 1000, (0, 120))

        st.sidebar.subheader("Uniqueness / Consistency")
        pk_col = st.sidebar.selectbox("Primary key column", options, index=options.index(best_guess("id/unique")) if best_guess("id/unique") in options else 0)
        id_col = st.sidebar.selectbox("ID column for consistency", options)
        value_col = st.sidebar.selectbox("Value that should match the ID", options)

        st.sidebar.subheader("Inconsistent Naming (Fuzzy Match)")
        text_like_cols = [c for c, t in auto_types.items() if t in ("name/text", "text")]
        fuzzy_cols = st.sidebar.multiselect(
            "Column(s) to check for near-duplicate names",
            columns,
            default=text_like_cols,
        )
        fuzzy_threshold = st.sidebar.slider("Similarity threshold (%)", 50, 100, 85)

    run_button = st.sidebar.button("🚀 Run Quality Checks", type="primary")

    if run_button:
        if config_mode == "Upload rules.yaml" and rules:
            run_checks_from_rules(checker, rules)
        elif config_mode == "Manual (sidebar)":
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
            if fuzzy_cols:
                for fcol in fuzzy_cols:
                    checker.check_fuzzy_duplicates(fcol, fuzzy_threshold)
        else:
            st.warning("No rules loaded — nothing to run.")
            st.stop()

        summary = checker.generate_report()

        # log this run to history
        log_run(
            dataset_name=fname,
            row_count=len(df),
            completeness_score=summary["completeness_score"],
            overall_score=summary["overall_score"],
            quality_label=summary["quality_label"],
        )

        st.header("📊 Quality Report")
        col1, col2, col3 = st.columns(3)
        col1.metric("Overall Quality Score", f"{summary['overall_score']}/100", summary["quality_label"])
        col2.metric("Completeness Score", f"{summary['completeness_score']}%")
        col3.metric("Checks Run", len(checker.results))

        st.subheader("Check Results")
        st.dataframe(summary["report"], use_container_width=True, hide_index=True)

        if not summary["report"].empty:
            fig = px.bar(
                summary["report"], x="Check", y="Issues Found", color="Status",
                title="Issues Found per Check",
                color_discrete_map={"✅": "#2ecc71", "⚠️": "#f39c12", "❌": "#e74c3c"},
            )
            st.plotly_chart(fig, use_container_width=True)

        # Fuzzy name matching detail view (one section per checked column)
        fuzzy_keys = [k for k in checker.results if k.startswith("Inconsistent Naming")]
        for fuzzy_key in fuzzy_keys:
            if checker.results[fuzzy_key]["issues_found"] > 0:
                st.subheader(f"🔤 {fuzzy_key} — Near-Duplicate Groups")
                st.caption("These distinct values look like they refer to the same entity but are spelled/formatted differently.")
                for group in checker.results[fuzzy_key]["details"]["near_duplicate_groups"]:
                    labels = []
                    for idxs, val in group:
                        # idxs is normally a list of row indices; be defensive in case
                        # an older/newer version of quality_checker.py returns a single index
                        count = len(idxs) if isinstance(idxs, (list, tuple, set)) else 1
                        labels.append(f"{val} ({count} rows)")
                    st.write("• " + "  ≈  ".join(labels))

        st.subheader("💡 Suggestions")
        tips = checker.suggestions()
        if tips:
            for tip in tips:
                st.markdown(f"- {tip}")
        else:
            st.success("No issues found — dataset looks clean!")

        # ---------------- Auto-fix ----------------
        st.header("🔧 Auto-Fix (Optional)")
        fix_col1, fix_col2 = st.columns(2)
        do_dedupe = fix_col1.checkbox("Remove duplicate rows", value=True)
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        fill_col_choice = fix_col2.selectbox("Column to fill missing values", ["-- none --"] + numeric_cols)
        fill_strategy_choice = fix_col2.selectbox("Fill strategy", ["median", "mean"])

        if st.button("Apply Auto-Fix"):
            fill_strategy = None
            if fill_col_choice != "-- none --":
                fill_strategy = {fill_col_choice: fill_strategy_choice}
            cleaned_df = checker.auto_fix(drop_duplicates=do_dedupe, fill_missing_strategy=fill_strategy)
            st.success(f"Auto-fix applied. Rows before: {len(df)}, after: {len(cleaned_df)}")
            st.dataframe(cleaned_df.head(10), use_container_width=True)
            csv_bytes = cleaned_df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Cleaned CSV", data=csv_bytes, file_name="cleaned_data.csv", mime="text/csv")

        # ---------------- Downloads ----------------
        st.header("⬇️ Export Report")
        dl_col1, dl_col2 = st.columns(2)

        report_csv = summary["report"].to_csv(index=False).encode("utf-8")
        dl_col1.download_button(
            "Download Report (CSV)", data=report_csv,
            file_name="quality_report.csv", mime="text/csv",
        )

        pdf_path = os.path.join(tempfile.gettempdir(), "quality_report.pdf")
        generate_pdf_report(summary, tips, dataset_name=fname, output_path=pdf_path)
        with open(pdf_path, "rb") as f:
            dl_col2.download_button(
                "Download Report (PDF)", data=f.read(),
                file_name="quality_report.pdf", mime="application/pdf",
            )
    else:
        st.info("Configure your checks in the sidebar, then click **Run Quality Checks**.")
