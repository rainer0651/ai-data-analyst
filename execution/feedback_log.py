"""
Append user feedback about a data pull to the database context file.

Feedback lands in the "## Feedback Log" section of context/database_context.md, right
after the FEEDBACK_LOG_START marker, so it becomes context the model sees on future
requests. Over time these entries should be folded up into the real context sections.

See directives/ai_data_analyst.md for the full SOP.
"""

from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTEXT_PATH = PROJECT_ROOT / "context" / "database_context.md"

_MARKER = "<!-- New feedback is inserted below this line, newest last. -->"


def record_feedback(question: str, sql: str, feedback: str) -> None:
    """Append a timestamped feedback entry to the context file's Feedback Log.

    Raises FileNotFoundError if the context file is missing, or ValueError if the
    insertion marker can't be found (someone removed it from the template).
    """
    if not CONTEXT_PATH.exists():
        raise FileNotFoundError(f"Context file not found at {CONTEXT_PATH}")

    text = CONTEXT_PATH.read_text(encoding="utf-8")
    if _MARKER not in text:
        raise ValueError(
            "Feedback marker not found in context file — expected the FEEDBACK_LOG_START "
            "block from the template."
        )

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    sql_block = sql.strip() or "(no query — clarification or error stage)"
    entry = (
        f"\n\n### {timestamp}\n"
        f"- **Question:** {question.strip()}\n"
        f"- **Query that ran:**\n"
        f"  ```sql\n{_indent(sql_block, '  ')}\n  ```\n"
        f"- **Feedback:** {feedback.strip()}"
    )

    updated = text.replace(_MARKER, _MARKER + entry, 1)
    CONTEXT_PATH.write_text(updated, encoding="utf-8")


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())
