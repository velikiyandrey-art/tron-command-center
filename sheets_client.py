import datetime
import requests


def push_comments(webhook_url: str, comments: list[dict]) -> int:
    """
    Push comments to Google Sheet via Apps Script web app.
    Returns number of rows added.
    """
    today = datetime.date.today().isoformat()
    rows = []
    for c in comments:
        rows.append({
            "date": today,
            "url": c.get("url", ""),
            "title": c.get("title", "")[:100],
            "author": c.get("author", ""),
            "comment": c.get("comment", ""),
            "status": c.get("status", "draft"),
            "keyword": c.get("keyword", ""),
        })

    resp = requests.post(webhook_url, json={"rows": rows}, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("added", len(rows))
    else:
        raise Exception(f"Google Sheets error: {resp.status_code} — {resp.text[:200]}")
