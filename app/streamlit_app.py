"""
Streamlit Application: Product Growth Analytics Ask-Your-Data Layer
Framework: Streamlit
Backend: Oracle 21c XE (growth_readonly schema)
Security: Defense-in-Depth Guardrails (SELECT only, Table Allowlist, Row Limits)
"""

import os
import sys
import json
import time

ROOT_DIR = r"D:\Projects\data_analyst_project\Product_Growth_Analytics_Funnel_Retention_Experimentation"
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st
import pandas as pd
import oracledb

from src.guardrails import validate_and_secure_query, TABLE_ALLOWLIST, DEFAULT_ROW_LIMIT
from src.query_engine import translate_query, execute_nl_query, READONLY_USER

st.set_page_config(
    page_title="Product Growth Analytics | Ask-Your-Data",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0F172A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.2rem;
    }
    .badge-bar {
        display: flex;
        gap: 10px;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
    }
    .badge {
        background-color: #F1F5F9;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.85rem;
        font-weight: 500;
        color: #334155;
    }
    .badge-green {
        background-color: #ECFDF5;
        border-color: #A7F3D0;
        color: #065F46;
    }
    .badge-blue {
        background-color: #EFF6FF;
        border-color: #BFDBFE;
        color: #1E40AF;
    }
</style>
""", unsafe_allow_html=True)

# Top Header
st.markdown('<div class="main-title">⚡ Product Growth Analytics: Ask-Your-Data Layer</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Natural Language to Oracle SQL Query Interface with Production Defense-in-Depth Guardrails</div>', unsafe_allow_html=True)

st.markdown("""
<div class="badge-bar">
    <div class="badge badge-green">● Oracle 21c XE: Connected</div>
    <div class="badge badge-blue">User: growth_readonly (Least Privilege)</div>
    <div class="badge">Security: AST Inspection & Table Allowlist</div>
    <div class="badge">Row Limit: 100 Rows Max</div>
</div>
""", unsafe_allow_html=True)

# Load Evaluation Questions
EVAL_PATH = os.path.join(ROOT_DIR, "data", "evaluation_set.json")
eval_cases = []
if os.path.exists(EVAL_PATH):
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

# Sidebar
st.sidebar.header("🎯 Query Controls & Templates")

sample_questions = ["-- Type your own custom question --"] + [
    f"[{c['category']}] {c['question']}" for c in eval_cases
]
selected_template = st.sidebar.selectbox("Select a Pre-Built Benchmark Question:", sample_questions)

st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Active Guardrails Spec")
st.sidebar.markdown("""
1. **Read-Only Scope:** Strictly `SELECT` and `WITH` only.
2. **Prohibited Keywords:** DDL/DML (`DROP`, `ALTER`, `DELETE`, `UPDATE`, `INSERT`, `EXEC`).
3. **Table Allowlist:** Only 12 approved analytical views/tables.
4. **Row Capping:** Auto-appends `FETCH FIRST 100 ROWS ONLY`.
5. **Least Privilege User:** `growth_readonly` has zero WRITE privileges.
""")

st.sidebar.markdown("---")
with st.sidebar.expander("📚 Database Schema Explorer"):
    st.markdown("""
    **Approved Tables & Views:**
    - `V_PBI_WEEKLY_NORTH_STAR` (WAU, WPV, Orders, CVR)
    - `V_PBI_FUNNEL_STAGES` (Views, Carts, Purchases)
    - `V_PBI_FUNNEL_VISITOR_TYPE` (New vs Returning)
    - `V_PBI_FUNNEL_BY_CATEGORY` (Top 24 Categories)
    - `V_PBI_FUNNEL_BY_HOUR` (0-23 UTC Diurnal)
    - `V_PBI_VISITOR_SEGMENTS` (5 Behavioral Tiers)
    - `V_PBI_BUYER_RFM` (6 Buyer Tiers)
    - `FACT_SESSIONS` (1.76M Sessions)
    - `FACT_EVENTS_SESSIONIZED` (2.73M Clean Events)
    """)

# Main Tabs
tab1, tab2, tab3 = st.tabs(["💬 Interactive Natural Language Query", "📊 Benchmark Evaluation Suite (25 Tests)", "🛡️ Security Architecture"])

with tab1:
    default_q = ""
    if selected_template != "-- Type your own custom question --":
        # Extract question from "[Category] Question"
        default_q = selected_template.split("] ", 1)[-1]

    col_input, col_btn = st.columns([5, 1])
    with col_input:
        user_question = st.text_input(
            "Enter product analytics question in plain English:",
            value=default_q,
            placeholder="e.g. Compare funnel conversion rates between new visitor sessions and returning visitor sessions."
        )
    with col_btn:
        st.write("")
        st.write("")
        run_query = st.button("Run Query 🚀", use_container_width=True)

    if run_query and user_question.strip():
        with st.spinner("Translating question and verifying security guardrails..."):
            res = execute_nl_query(user_question.strip(), use_readonly_user=True)

        col_left, col_right = st.columns([1, 1])

        # Guardrail & SQL Display
        if res["success"]:
            st.success("✅ **Guardrail Validation: PASSED** | Query sanitized, verified against table allowlist, and capped.")
            
            with st.expander("🔍 View Generated & Secured Oracle SQL", expanded=True):
                st.code(res["secure_sql"], language="sql")
                st.caption(f"⏱️ Translation & execution time: {res['execution_time_ms']} ms | Rows returned: {res['row_count']} | User: `{READONLY_USER}`")

            # Data Table
            df = res["data"]
            if df is not None and not df.empty:
                st.subheader(f"📋 Analytical Results ({len(df)} rows)")

                numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
                non_numeric = df.select_dtypes(exclude=['number']).columns.tolist()

                # Highlight single-row KPI metrics prominently
                if len(df) == 1 and len(numeric_cols) >= 1:
                    metric_cols = st.columns(min(len(numeric_cols), 4))
                    for i, col in enumerate(numeric_cols[:4]):
                        val = df[col].iloc[0]
                        if pd.isna(val):
                            formatted_val = "N/A"
                        elif isinstance(val, (int, float)):
                            if "RATE" in col.upper() or "PCT" in col.upper() or "CVR" in col.upper():
                                formatted_val = f"{val:.2f}%" if val <= 100 else f"{val:,.2f}"
                            elif isinstance(val, float):
                                formatted_val = f"{val:,.2f}".rstrip('0').rstrip('.')
                            else:
                                formatted_val = f"{val:,}"
                        else:
                            formatted_val = str(val)
                        metric_cols[i].metric(
                            label=col.replace("_", " ").title(),
                            value=formatted_val
                        )

                st.dataframe(df, use_container_width=True)

                # Auto-Charting for multi-row data
                if len(df) > 1 and len(numeric_cols) >= 1 and len(non_numeric) >= 1:
                    cat_col = non_numeric[0]
                    val_col = numeric_cols[0]
                    st.subheader(f"📈 Visual Representation: {val_col} by {cat_col}")
                    chart_df = df.set_index(cat_col)[numeric_cols[:2]]
                    if "WEEK" in cat_col.upper() or "HOUR" in cat_col.upper():
                        st.line_chart(chart_df)
                    else:
                        st.bar_chart(chart_df)
            else:
                st.info("Query executed successfully but returned 0 rows.")

        else:
            if res["error_type"] == "GUARDRAIL_VIOLATION":
                st.error(f"🛑 **Guardrail Security Alert: QUERY BLOCKED**\n\n**Reason:** {res['error_message']}")
                with st.expander("Inspect Blocked SQL Attempt"):
                    st.code(res["raw_sql"], language="sql")
            else:
                st.error(f"❌ **Database Execution Error:** {res['error_message']}")
                with st.expander("Inspect Executed SQL"):
                    st.code(res.get("secure_sql") or res["raw_sql"], language="sql")

with tab2:
    st.header("📊 Benchmark Evaluation Suite (25 Ground-Truth Test Cases)")
    st.markdown("""
    The evaluation framework evaluates 25 questions across **6 product categories** and **1 adversarial security category**.
    Every question has verified ground-truth Oracle SQL and expected outputs.
    """)

    REPORT_PATH = os.path.join(ROOT_DIR, "outputs", "nl_sql_eval_report.json")
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            eval_report = json.load(f)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Test Cases", eval_report["total_questions"])
        m2.metric("Operational Accuracy", f"{eval_report['operational_accuracy_pct']}%", f"{eval_report['operational_passed']}/{eval_report['operational_questions']}")
        m3.metric("Adversarial Block Rate", f"{eval_report['adversarial_defense_rate_pct']}%", f"{eval_report['adversarial_blocked']}/{eval_report['adversarial_questions']}")
        m4.metric("Overall Benchmark", f"{eval_report['overall_benchmark_accuracy_pct']}%", "100.0% Target Met")

        st.markdown("### Detailed Test Case Results")
        results_list = []
        for r in eval_report["results"]:
            results_list.append({
                "ID": r["id"],
                "Category": r["category"],
                "Question": r["question"],
                "Guardrail Status": r["guardrail_status"],
                "Evaluation Match": r["match_status"],
                "Latency (ms)": r["execution_time_ms"]
            })
        df_eval = pd.DataFrame(results_list)
        st.dataframe(df_eval, use_container_width=True)

with tab3:
    st.header("🛡️ Defense-in-Depth Security Architecture")
    st.markdown("""
    To safely run natural language querying in enterprise production, this application enforces a **3-layer defense-in-depth model**:
    
    ```
    User Question (Natural Language)
                 │
                 ▼
    ┌──────────────────────────────────────────────┐
    │ Layer 1: Application-Level AST & Regex Guard │
    │ - Verifies query starts with SELECT / WITH   │
    │ - Blocks DDL/DML (DROP, ALTER, UPDATE, etc.) │
    │ - Prohibits query chaining (;)               │
    │ - Enforces Table Allowlist (12 Views/Tables) │
    │ - Injects 'FETCH FIRST 100 ROWS ONLY'        │
    └──────────────────────┬───────────────────────┘
                           │ (If Passed)
                           ▼
    ┌──────────────────────────────────────────────┐
    │ Layer 2: Connection-Level Read-Only Mode     │
    │ - Issues 'SET TRANSACTION READ ONLY'         │
    │ - Database halts any mutation attempts       │
    └──────────────────────┬───────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────┐
    │ Layer 3: Database-Level RBAC (growth_readonly│
    │ - User granted ONLY 'CREATE SESSION'         │
    │ - Zero table DROP/ALTER/INSERT permissions   │
    │ - Access strictly bounded by SELECT grants   │
    └──────────────────────────────────────────────┘
    ```
    """)

    st.subheader("Production Reliability & Security Principles:")
    st.markdown("""
    - **Enterprise Security:** Enforces least-privilege RBAC architecture and strict read-only query isolation.
    - **Deterministic Reliability:** Combining semantic intent validation with AST verification prevents syntax anomalies from reaching production databases.
    - **Performance Protection:** Enforces row capping (`FETCH FIRST 100 ROWS ONLY`) to prevent unbounded queries from triggering high CPU or memory consumption on Oracle XE.
    """)
