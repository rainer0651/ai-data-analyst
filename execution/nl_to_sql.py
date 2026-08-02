"""
Plain-English -> SQL translation and result analysis via Claude.

Two model calls per request:
  1. generate_sql()      : question + conversation history + database context -> SQL,
                           the assumptions made, or a clarifying question if the ask is
                           too ambiguous to answer safely.
  2. summarize_results() : the returned data -> notable trends / anomalies / insights.

See directives/ai_data_analyst.md for the full SOP.
"""

import json
import os
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTEXT_PATH = PROJECT_ROOT / "context" / "database_context.md"

MODEL = "claude-opus-5"

_client = None


def _get_client() -> anthropic.Anthropic:
    """Build the Anthropic client lazily, reading the API key at first use.

    On hosts like Streamlit Community Cloud the key is injected via st.secrets (mirrored
    into the environment at startup); constructing the client at import time could capture
    an empty key and then fail every request with "Could not resolve authentication method".
    """
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client

# JSON schema constraining the SQL-generation response so we always get a
# predictable shape back (Claude Opus 5 supports structured outputs).
_SQL_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_clarification": {
            "type": "boolean",
            "description": "True if the request is too ambiguous to write a correct query.",
        },
        "clarification_question": {
            "type": "string",
            "description": "If needs_clarification is true, the single most useful question "
            "to ask the user. Empty otherwise.",
        },
        "sql": {
            "type": "string",
            "description": "A single read-only Snowflake SELECT/WITH query. Empty if "
            "clarification is needed.",
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Plain-English assumptions made while interpreting the request "
            "(date ranges, metric definitions, filters, tables chosen).",
        },
        "money_columns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The exact output column names/aliases in the SELECT that are US "
            "dollar amounts (revenue, price, cost, balance, order value, etc.). Empty if none. "
            "Do NOT include counts, quantities, keys, years, or percentages.",
        },
    },
    "required": [
        "needs_clarification", "clarification_question", "sql", "assumptions", "money_columns",
    ],
    "additionalProperties": False,
}

_SQL_SYSTEM = """You are a careful data analyst that writes Snowflake SQL from plain-English requests.

Rules:
- Use ONLY the tables, columns, joins, and metric definitions described in the database
  context provided. Do not invent tables or columns. If the context doesn't cover what's
  asked, set needs_clarification=true and ask.
- Write exactly ONE read-only statement (SELECT or WITH ... SELECT). Never write INSERT,
  UPDATE, DELETE, CREATE, DROP, or any other statement type.
- Add an explicit LIMIT (default 1000) to non-aggregated queries unless the user asks for
  a specific count.
- Prefer the metric and date conventions defined in the context. State every non-trivial
  interpretation in "assumptions" — date ranges, which tables you chose, filters applied,
  how you defined a business term.
- If the request is genuinely ambiguous in a way that would change the numbers (unclear
  time range, undefined term, multiple plausible tables), do NOT guess: set
  needs_clarification=true and ask the single most useful clarifying question.
- Follow-up questions refer to the previous turns; adjust the prior query accordingly.
- In "money_columns", list the exact output column names/aliases that hold US dollar
  amounts so the app can format them. Exclude counts, quantities, keys, years, percentages."""

_INSIGHTS_SYSTEM = """You are a data analyst reviewing the result of a query you just ran.
Given the user's question and a sample of the returned data, write 2-5 short bullet points
noting genuinely interesting trends, anomalies, or takeaways. Be concrete and cite numbers
from the data. If nothing stands out, say so briefly rather than inventing significance.
Do not restate the raw table; interpret it. Plain text, no preamble.
Format any dollar amounts with a $ sign, commas separating thousands, and 2 decimals
(e.g. $1,234,567.89)."""


def load_context() -> str:
    """Read the database context file the model reasons over."""
    if not CONTEXT_PATH.exists():
        return "(No database context file found — ask the user to fill in context/database_context.md.)"
    return CONTEXT_PATH.read_text(encoding="utf-8")


def _history_block(history: list[dict]) -> str:
    """Render prior turns compactly so follow-up questions have context."""
    if not history:
        return "(no prior turns)"
    lines = []
    for turn in history:
        lines.append(f"User asked: {turn['question']}")
        if turn.get("sql"):
            lines.append(f"SQL run:\n{turn['sql']}")
    return "\n".join(lines)


def generate_sql(question: str, history: list[dict] | None = None) -> dict:
    """Translate a question into SQL (or a clarifying question).

    Returns a dict matching _SQL_SCHEMA: needs_clarification, clarification_question,
    sql, assumptions.
    """
    history = history or []
    context = load_context()

    user_content = (
        f"# Database context\n{context}\n\n"
        f"# Conversation so far\n{_history_block(history)}\n\n"
        f"# New request\n{question}"
    )

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=4000,
        system=_SQL_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
        output_config={"format": {"type": "json_schema", "schema": _SQL_SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def summarize_results(question: str, sql: str, df: pd.DataFrame) -> str:
    """Ask Claude for trends/anomalies/insights over the returned data."""
    if df.empty:
        return "The query returned no rows."

    # Send a bounded sample so a wide/long result doesn't blow up the prompt.
    sample = df.head(100)
    preview = sample.to_csv(index=False)
    shape_note = f"{len(df)} row(s) returned" + (
        " (showing first 100 to the analyst)" if len(df) > 100 else ""
    )

    user_content = (
        f"User's question: {question}\n\n"
        f"Query that ran:\n{sql}\n\n"
        f"Result ({shape_note}), as CSV:\n{preview}"
    )

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=1200,
        system=_INSIGHTS_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    return next(b.text for b in response.content if b.type == "text").strip()
