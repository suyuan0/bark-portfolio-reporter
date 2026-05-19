from pathlib import Path
from datetime import datetime

import pandas as pd
from pandas.errors import EmptyDataError


SNAPSHOT_FILE = Path("data/snapshots.csv")


def load_snapshots() -> pd.DataFrame:
    if not SNAPSHOT_FILE.exists():
        return pd.DataFrame()

    if SNAPSHOT_FILE.stat().st_size == 0:
        return pd.DataFrame()

    try:
        df = pd.read_csv(SNAPSHOT_FILE, dtype={"date": str})
    except EmptyDataError:
        return pd.DataFrame()

    return df


def get_previous_snapshot(current_date: str) -> dict | None:
    df = load_snapshots()

    if df.empty:
        return None

    if "date" not in df.columns:
        return None

    previous_df = df[df["date"] < current_date]

    if previous_df.empty:
        return None

    previous_df = previous_df.sort_values("date")
    row = previous_df.iloc[-1]

    return row.to_dict()


def save_snapshot(summary: dict):
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)

    new_row = {
        "date": summary["quote_date"],
        "quote_time": summary["quote_time"],
        "total_cost": summary["total_cost"],
        "total_value": summary["total_value"],
        "total_pnl": summary["total_pnl"],
        "total_return": summary["total_return"],
        "today_trade_cash_flow": summary["today_trade_cash_flow"],
        "daily_pnl": summary["daily_pnl"],
        "daily_return": summary["daily_return"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    df = load_snapshots()

    if df.empty:
        df = pd.DataFrame([new_row])
    else:
        df = df[df["date"] != summary["quote_date"]]
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df = df.sort_values("date")
    df.to_csv(SNAPSHOT_FILE, index=False)