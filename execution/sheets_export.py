"""
Export a query result DataFrame to a new Google Sheet.

Reuses the same Google Cloud OAuth "Desktop app" client (credentials.json) as the other
workflows in this project. Uses its own token file (token_sheets.json) scoped to Sheets +
Drive file creation, kept separate from the Gmail/YouTube tokens so this flow can't affect
them. First run triggers an interactive browser consent; the auth URL is printed for the
user to open manually (no GUI browser is reachable from the app's shell).
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token_sheets.json"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Google Sheets rejects non-JSON-native cell values; coerce everything to str/number.
_MAX_CELLS = 5_000_000  # Sheets hard limit; guard so a huge export fails clearly.


def _get_sheets_service():
    # Credentials come from the local token file (dev) or the GOOGLE_TOKEN_JSON secret
    # (hosted, e.g. Streamlit Cloud). The saved token carries client id/secret + refresh
    # token, so it can authenticate and refresh without the interactive flow.
    creds = None
    from_file = False
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        from_file = True
    elif os.environ.get("GOOGLE_TOKEN_JSON"):
        creds = Credentials.from_authorized_user_info(
            json.loads(os.environ["GOOGLE_TOKEN_JSON"]), SCOPES
        )

    if creds and not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        if from_file:  # can't persist back to a secret, only to the local file
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    if not creds:
        # No saved token: run the interactive consent flow (works on a local machine only).
        if not CREDENTIALS_PATH.exists():
            raise RuntimeError(
                "Google Sheets export isn't configured here. Set the GOOGLE_TOKEN_JSON "
                "secret (contents of token_sheets.json) to enable it on this deployment."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        creds = flow.run_local_server(
            port=0, access_type="offline", prompt="consent", open_browser=False
        )
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("sheets", "v4", credentials=creds)


def _to_cell_values(df: pd.DataFrame) -> list[list]:
    """Header row plus data rows, with values coerced to Sheets-safe types."""
    header = [str(c) for c in df.columns]
    rows = []
    for record in df.itertuples(index=False, name=None):
        row = []
        for v in record:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                row.append("")
            elif isinstance(v, (int, float, str)):
                row.append(v)
            else:
                row.append(str(v))
        rows.append(row)
    return [header] + rows


def _chart_request(
    df: pd.DataFrame, sheet_id: int, money_idx: list[int], chart_type: str = "Pie"
) -> dict | None:
    """Build an addChart request (Pie/Bar/Line) anchored below the data, or None.

    Categories come from the first label (non-numeric) column; values from a value column
    (a dollar column if present, else the first numeric column). Returns None when a chart
    doesn't fit — no label/value column, too few rows, or (for Pie) too many rows or
    negative/zero values. "Bar" renders as a vertical column chart to match the app.
    """
    n_rows, n_cols = df.shape
    if n_rows < 2 or n_cols < 2:
        return None

    numeric = [i for i in range(n_cols) if pd.to_numeric(df.iloc[:, i], errors="coerce").notna().all()]
    if not numeric:
        return None

    value_idx = money_idx[0] if money_idx else numeric[0]
    values = pd.to_numeric(df.iloc[:, value_idx], errors="coerce")
    label_idx = next((i for i in range(n_cols) if i not in numeric and i != value_idx), None)
    if label_idx is None:
        label_idx = next((i for i in range(n_cols) if i != value_idx), None)
    if label_idx is None:
        return None

    def _range(col: int) -> dict:
        return {"sources": [{
            "sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": n_rows + 1,
            "startColumnIndex": col, "endColumnIndex": col + 1,
        }]}

    title = f"{df.columns[value_idx]} by {df.columns[label_idx]}"
    position = {"overlayPosition": {"anchorCell": {
        "sheetId": sheet_id, "rowIndex": n_rows + 2, "columnIndex": 0,
    }}}

    if chart_type == "Pie":
        # A pie needs non-negative parts of a whole and stays readable only for few slices.
        if n_rows > 26 or values.min() < 0 or values.sum() <= 0:
            return None
        spec = {
            "title": title,
            "pieChart": {
                "legendPosition": "RIGHT_LEGEND",
                "domain": {"sourceRange": _range(label_idx)},
                "series": {"sourceRange": _range(value_idx)},
                "threeDimensional": False,
            },
        }
    else:
        if n_rows > 50:  # bar/line get unreadable past this many categories
            return None
        # COLUMN (vertical bars) uses LEFT_AXIS for its series; BAR (horizontal) would
        # need BOTTOM_AXIS. LINE also uses LEFT_AXIS.
        basic_type = "LINE" if chart_type == "Line" else "COLUMN"
        spec = {
            "title": title,
            "basicChart": {
                "chartType": basic_type,
                "legendPosition": "NO_LEGEND",  # basic charts use NO_LEGEND, not NONE
                "headerCount": 1,
                "axis": [
                    {"position": "BOTTOM_AXIS", "title": str(df.columns[label_idx])},
                    {"position": "LEFT_AXIS", "title": str(df.columns[value_idx])},
                ],
                "domains": [{"domain": {"sourceRange": _range(label_idx)}}],
                "series": [{"series": {"sourceRange": _range(value_idx)}, "targetAxis": "LEFT_AXIS"}],
            },
        }

    return {"addChart": {"chart": {"spec": spec, "position": position}}}


def export_dataframe(
    df: pd.DataFrame,
    title: str | None = None,
    money_columns: list[str] | None = None,
    chart_type: str = "Pie",
) -> str:
    """Create a new Google Sheet from ``df`` and return its shareable URL.

    Columns named in ``money_columns`` (matched case-insensitively) are coerced to numbers
    and given a $#,##0.00 currency format so the sheet matches the app's dollar display.
    ``chart_type`` ("Pie"/"Bar"/"Line") selects the chart drawn below the data.
    """
    if (df.shape[0] + 1) * max(df.shape[1], 1) > _MAX_CELLS:
        raise ValueError("Result is too large to export to a single Google Sheet.")

    df = df.copy()
    by_lower = {c.lower(): c for c in df.columns}
    money_idx = []
    for name in money_columns or []:
        col = by_lower.get(str(name).lower())
        if col is not None:
            df[col] = pd.to_numeric(df[col], errors="coerce")  # store as numbers, not text
            money_idx.append(df.columns.get_loc(col))

    title = title or f"Data pull — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    service = _get_sheets_service()

    spreadsheet = (
        service.spreadsheets()
        .create(
            body={"properties": {"title": title}},
            fields="spreadsheetId,sheets.properties.sheetId",
        )
        .execute()
    )
    spreadsheet_id = spreadsheet["spreadsheetId"]
    sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="RAW",
        body={"values": _to_cell_values(df)},
    ).execute()

    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,  # skip the header row
                    "startColumnIndex": i,
                    "endColumnIndex": i + 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "numberFormat": {"type": "NUMBER", "pattern": "$#,##0.00"}
                    }
                },
                "fields": "userEnteredFormat.numberFormat",
            }
        }
        for i in money_idx
    ]

    chart_request = _chart_request(df, sheet_id, money_idx, chart_type)
    if chart_request:
        requests.append(chart_request)

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
