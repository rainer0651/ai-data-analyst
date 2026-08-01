"""
AI Data Analyst — Streamlit app.

Takes plain-English data requests, writes read-only Snowflake SQL with Claude, runs it,
shows the formatted result plus the assumptions made and notable insights, and offers a
one-click export to Google Sheets. Each data pull has a "Report a problem" control whose
feedback is appended to context/database_context.md. The full conversation is kept so
follow-up questions ("now the same for the last 6 months") work.

Run with:  streamlit run app.py
See directives/ai_data_analyst.md for the full SOP.
"""

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="AI Data Analyst", page_icon="📊", layout="wide")

from dotenv import load_dotenv

# Config resolution: locally from .env; on Streamlit Community Cloud from st.secrets.
# Mirror any st.secrets into the environment BEFORE importing the execution modules,
# which read os.environ at import time (the Anthropic client is built on import).
load_dotenv()
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass  # no secrets.toml locally — .env already handled it

# Make execution/ importable when Streamlit runs this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from execution import feedback_log, nl_to_sql, sheets_export, snowflake_client

REQUIRED_ENV = ["ANTHROPIC_API_KEY", "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER"]


def missing_config() -> list[str]:
    return [k for k in REQUIRED_ENV if not os.environ.get(k)]


def build_history() -> list[dict]:
    """Prior successful data turns, as {question, sql}, for follow-up context."""
    return [
        {"question": m["question"], "sql": m["sql"]}
        for m in st.session_state.messages
        if m["role"] == "assistant" and m["kind"] == "data"
    ]


def run_request(question: str) -> dict:
    """Generate SQL, run it, and summarize — returning an assistant message dict."""
    result = nl_to_sql.generate_sql(question, history=build_history())

    if result.get("needs_clarification"):
        return {
            "role": "assistant",
            "kind": "clarification",
            "question": question,
            "sql": "",
            "clarification_question": result.get("clarification_question", ""),
            "assumptions": [],
        }

    sql = result["sql"]
    try:
        df = snowflake_client.run_query(sql)
    except snowflake_client.UnsafeQueryError as e:
        return {
            "role": "assistant", "kind": "error", "question": question,
            "sql": sql, "error": f"Blocked a non-read-only query: {e}", "assumptions": [],
        }
    except Exception as e:  # surface Snowflake/connection errors to the user
        return {
            "role": "assistant", "kind": "error", "question": question,
            "sql": sql, "error": str(e), "assumptions": result.get("assumptions", []),
        }

    insights = nl_to_sql.summarize_results(question, sql, df)
    return {
        "role": "assistant", "kind": "data", "question": question, "sql": sql,
        "assumptions": result.get("assumptions", []), "df": df, "insights": insights,
        "money_columns": result.get("money_columns", []),
        "sheet_url": None, "feedback_sent": False,
    }


def _money_column_config(df: pd.DataFrame, money_columns: list[str]) -> dict:
    """Map dollar-amount columns to a $-formatted display (commas, 2 decimals).

    Matches column names case-insensitively (Snowflake upper-cases aliases) and coerces
    those columns to numeric so the formatter applies.
    """
    by_lower = {c.lower(): c for c in df.columns}
    config = {}
    for name in money_columns:
        col = by_lower.get(str(name).lower())
        if col is not None:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            config[col] = st.column_config.NumberColumn(format="dollar")
    return config


def _chart_columns(df: pd.DataFrame, money_columns: list[str]):
    """Pick (label_col, value_col) for charting, or (None, None) if not chartable.

    Value column prefers a dollar column, else the first numeric column; label column is
    the first non-numeric column that isn't the value column.
    """
    if df.shape[1] < 2 or len(df) < 1:
        return None, None
    numeric = [c for c in df.columns if pd.to_numeric(df[c], errors="coerce").notna().all()]
    if not numeric:
        return None, None
    by_lower = {c.lower(): c for c in df.columns}
    value_col = next(
        (by_lower[str(n).lower()] for n in money_columns if str(n).lower() in by_lower), None
    )
    if value_col is None:
        value_col = numeric[0]
    label_col = next((c for c in df.columns if c not in numeric and c != value_col), None)
    if label_col is None:
        label_col = next((c for c in df.columns if c != value_col), None)
    return label_col, value_col


def _render_chart(df: pd.DataFrame, label_col: str, value_col: str, chart_type: str) -> None:
    data = df[[label_col, value_col]].copy()
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
    data = data.dropna(subset=[value_col])
    if chart_type == "Bar":
        st.bar_chart(data, x=label_col, y=value_col)
    elif chart_type == "Line":
        st.line_chart(data, x=label_col, y=value_col)
    else:  # Pie — Streamlit has no native pie, so use its bundled Altair
        import altair as alt

        chart = (
            alt.Chart(data)
            .mark_arc()
            .encode(
                theta=alt.Theta(field=value_col, type="quantitative"),
                color=alt.Color(field=label_col, type="nominal"),
                tooltip=[label_col, value_col],
            )
        )
        st.altair_chart(chart, use_container_width=True)


def render_assistant(msg: dict, idx: int) -> None:
    with st.chat_message("assistant"):
        if msg["kind"] == "clarification":
            st.info("I need a bit more detail before pulling data:")
            st.markdown(f"**{msg['clarification_question']}**")
            return

        if msg["kind"] == "error":
            st.error(msg["error"])
            if msg["sql"]:
                with st.expander("Query that was attempted"):
                    st.code(msg["sql"], language="sql")
            _feedback_control(msg, idx)
            return

        # kind == "data"
        df = msg["df"]
        st.markdown(f"**Result** — {len(df):,} row(s)")
        column_config = _money_column_config(df, msg.get("money_columns", []))
        st.dataframe(df, use_container_width=True, column_config=column_config)

        if msg["assumptions"]:
            with st.expander("Assumptions I made", expanded=True):
                for a in msg["assumptions"]:
                    st.markdown(f"- {a}")

        if msg["insights"]:
            with st.expander("Trends & insights", expanded=True):
                st.markdown(msg["insights"])

        label_col, value_col = _chart_columns(df, msg.get("money_columns", []))
        if label_col and value_col:
            chart_type = st.radio(
                "Chart", ["Pie", "Bar", "Line"], horizontal=True, key=f"chart_{idx}"
            )
            _render_chart(df, label_col, value_col, chart_type)

        with st.expander("SQL"):
            st.code(msg["sql"], language="sql")

        col1, col2 = st.columns([1, 1])
        with col1:
            if msg["sheet_url"]:
                st.markdown(f"✅ [Open in Google Sheets]({msg['sheet_url']})")
            elif st.button("📤 Export to Google Sheets", key=f"export_{idx}"):
                with st.spinner("Creating Google Sheet…"):
                    try:
                        url = sheets_export.export_dataframe(
                            df, title=f"Data pull — {msg['question'][:80]}",
                            money_columns=msg.get("money_columns", []),
                            chart_type=st.session_state.get(f"chart_{idx}", "Pie"),
                        )
                        st.session_state.messages[idx]["sheet_url"] = url
                        st.rerun()
                    except Exception as e:
                        st.error(f"Export failed: {e}")
        with col2:
            _feedback_control(msg, idx)


def _feedback_control(msg: dict, idx: int) -> None:
    """Per-pull 'Report a problem' control that appends to the context file."""
    if msg.get("feedback_sent"):
        st.markdown("🗒️ Feedback recorded — thanks.")
        return
    with st.popover("🐞 Report a problem"):
        with st.form(f"feedback_form_{idx}"):
            note = st.text_area(
                "What went wrong? (wrong numbers, misread request, bad assumption…)",
                key=f"feedback_text_{idx}",
            )
            if st.form_submit_button("Send feedback") and note.strip():
                try:
                    feedback_log.record_feedback(
                        question=msg["question"], sql=msg.get("sql", ""), feedback=note
                    )
                    st.session_state.messages[idx]["feedback_sent"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not record feedback: {e}")


# ---- Page ----------------------------------------------------------------

st.title("📊 AI Data Analyst")
st.caption("Ask for data in plain English. I write read-only SQL, run it on Snowflake, "
           "and explain what I did.")

with st.sidebar:
    st.header("Status")
    gaps = missing_config()
    if gaps:
        st.error("Missing configuration in `.env`:\n\n" + "\n".join(f"- `{g}`" for g in gaps))
        st.caption("Fill these in, plus the Snowflake role/warehouse/database, then reload.")
    else:
        st.success("Configuration looks set.")
    st.caption("Database context lives in `context/database_context.md`. "
               "The better that file, the better the queries.")
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for i, m in enumerate(st.session_state.messages):
    if m["role"] == "user":
        with st.chat_message("user"):
            st.markdown(m["content"])
    else:
        render_assistant(m, i)

if prompt := st.chat_input("e.g. How many orders did we get last month by store?"):
    if missing_config():
        st.warning("Set the required `.env` values (see sidebar) before asking.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.spinner("Thinking, writing SQL, and running it…"):
            assistant_msg = run_request(prompt)
        st.session_state.messages.append(assistant_msg)
        st.rerun()
