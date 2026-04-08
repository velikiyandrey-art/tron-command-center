import json
import datetime
import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"  # Replace with your actual sheet ID


def _get_client(creds_json: str) -> gspread.Client:
    if isinstance(creds_json, str):
        creds_info = json.loads(creds_json)
    else:
        creds_info = creds_json
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)


def push_comments(creds_json: str, comments: list[dict], sheet_name: str = "X Replies") -> int:
    """
    Append NEW comments to Google Sheet (append-only, never erases).
    Creates sheet tab if missing. Skips duplicates by URL.
    Returns number of NEW rows added.
    """
    gc = _get_client(creds_json)
    spreadsheet = gc.open_by_key(SHEET_ID)

    try:
        ws = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
        ws.update("A1:G1", [["Date", "Tweet URL", "Tweet Text", "Author", "Our Reply", "Status", "Keyword"]])
        ws.format("A1:G1", {"textFormat": {"bold": True}})

    existing_urls = set()
    try:
        url_col = ws.col_values(2)
        existing_urls = set(url_col[1:])
    except Exception:
        pass

    today = datetime.date.today().isoformat()
    new_rows = []
    for c in comments:
        url = c.get("url", "")
        if url in existing_urls:
            continue
        new_rows.append([
            today,
            url,
            c.get("title", "")[:100],
            c.get("author", ""),
            c.get("comment", ""),
            c.get("status", "draft"),
            c.get("keyword", ""),
        ])

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")
    return len(new_rows)
