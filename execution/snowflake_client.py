"""
Read-only Snowflake access for the AI data analyst app.

Two layers of read-only protection:
  1. The connection uses a role (SNOWFLAKE_ROLE) that should be granted SELECT-only
     access in Snowflake — this is the real guardrail and must be configured there.
  2. Every SQL string is validated here to be a single read-only statement before it
     runs, so a mis-scoped role can't be exploited by a generated query.

See directives/ai_data_analyst.md for the full SOP.
"""

import os
import re

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

# Statement keywords that must never appear as the leading verb of a query, plus
# a few that are dangerous anywhere. The connection role is the primary guard;
# this is defense in depth against anything the model emits.
_FORBIDDEN = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "CREATE", "DROP", "ALTER", "TRUNCATE", "RENAME",
    "GRANT", "REVOKE", "CALL", "EXECUTE",
    "COPY", "PUT", "GET", "REMOVE", "UNLOAD", "LOAD",
    "USE", "SET", "UNSET", "COMMENT",
}

_ALLOWED_LEADING = {"SELECT", "WITH"}

# Hard cap on rows pulled back into the app regardless of the query's own LIMIT,
# so a runaway result can't exhaust memory.
MAX_ROWS = 5000


class UnsafeQueryError(ValueError):
    """Raised when a query is not a single read-only statement."""


def _strip_sql_comments(sql: str) -> str:
    """Remove -- line comments and /* */ block comments so keyword checks aren't fooled."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def assert_read_only(sql: str) -> None:
    """Validate that ``sql`` is exactly one read-only statement, or raise UnsafeQueryError."""
    cleaned = _strip_sql_comments(sql).strip()
    if not cleaned:
        raise UnsafeQueryError("Empty query.")

    # Allow a single optional trailing semicolon; reject anything that chains statements.
    without_trailing = cleaned.rstrip(";").strip()
    if ";" in without_trailing:
        raise UnsafeQueryError("Only a single statement is allowed (found multiple ';').")

    first_word = re.split(r"\s+", without_trailing, maxsplit=1)[0].upper()
    if first_word not in _ALLOWED_LEADING:
        raise UnsafeQueryError(
            f"Query must start with SELECT or WITH, not {first_word!r}."
        )

    # Word-boundary scan for forbidden verbs anywhere in the statement.
    upper_tokens = set(re.findall(r"[A-Za-z_]+", without_trailing.upper()))
    hit = _FORBIDDEN & upper_tokens
    if hit:
        raise UnsafeQueryError(
            f"Query contains disallowed keyword(s): {', '.join(sorted(hit))}."
        )


def get_connection():
    """Open a Snowflake connection from environment variables.

    Supports password auth by default; set SNOWFLAKE_AUTHENTICATOR (e.g. 'externalbrowser'
    or a key-pair path via SNOWFLAKE_PRIVATE_KEY_PATH) for SSO / key-pair setups.
    """
    params = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "role": os.environ.get("SNOWFLAKE_ROLE"),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE"),
        "database": os.environ.get("SNOWFLAKE_DATABASE"),
        "schema": os.environ.get("SNOWFLAKE_SCHEMA"),
    }

    authenticator = os.environ.get("SNOWFLAKE_AUTHENTICATOR")
    if authenticator:
        params["authenticator"] = authenticator
    if os.environ.get("SNOWFLAKE_PASSWORD"):
        params["password"] = os.environ["SNOWFLAKE_PASSWORD"]

    # Drop unset optional params so the connector uses its own defaults.
    params = {k: v for k, v in params.items() if v is not None}
    return snowflake.connector.connect(**params)


def run_query(sql: str) -> pd.DataFrame:
    """Validate, run a read-only query, and return the results as a DataFrame.

    Raises UnsafeQueryError if the SQL isn't a single read-only statement, and lets
    snowflake.connector errors propagate so the caller can surface them.
    """
    assert_read_only(sql)

    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchmany(MAX_ROWS)
            columns = [c[0] for c in cur.description]
            return pd.DataFrame(rows, columns=columns)
        finally:
            cur.close()
    finally:
        conn.close()
