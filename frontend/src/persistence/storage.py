"""File-based persistence for watchlist and last-visit state."""
import json
from pathlib import Path

_FRONTEND_DIR = Path(__file__).parent.parent.parent

WATCHLIST_PATH = _FRONTEND_DIR / "watchlist.json"
LAST_VISIT_PATH = _FRONTEND_DIR / "last_visit.json"


def load_watchlist() -> list[str]:
    try:
        if WATCHLIST_PATH.exists():
            return json.loads(WATCHLIST_PATH.read_text())
    except Exception:
        pass
    return []


def save_watchlist(products: list[str]) -> None:
    try:
        WATCHLIST_PATH.write_text(json.dumps(products))
    except Exception:
        pass


def load_last_visit() -> str | None:
    try:
        if LAST_VISIT_PATH.exists():
            return json.loads(LAST_VISIT_PATH.read_text()).get("date")
    except Exception:
        pass
    return None


def save_last_visit(iso_date: str) -> None:
    try:
        LAST_VISIT_PATH.write_text(json.dumps({"date": iso_date}))
    except Exception:
        pass
