from pathlib import Path
from datetime import datetime

import pandas as pd
from pandas.errors import EmptyDataError


SNAPSHOT_FILE = Path("data/snapshots.csv")
POSITION_SNAPSHOT_FILE = Path("data/position_snapshots.csv")
TRADES_FILE = Path("trades.csv")


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


def load_position_snapshots() -> pd.DataFrame:
    if not POSITION_SNAPSHOT_FILE.exists():
        return pd.DataFrame()

    if POSITION_SNAPSHOT_FILE.stat().st_size == 0:
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            POSITION_SNAPSHOT_FILE,
            dtype={"date": str, "symbol": str},
        )
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

    return reconcile_previous_snapshot(row.to_dict())


def reconcile_previous_snapshot(previous_snapshot: dict) -> dict:
    previous_date = str(previous_snapshot["date"])
    position_df = load_position_snapshots()

    if position_df.empty or "date" not in position_df.columns:
        return previous_snapshot

    previous_positions = position_df[position_df["date"] == previous_date].copy()

    if previous_positions.empty:
        return previous_snapshot

    required_columns = {"symbol", "price"}
    if not required_columns.issubset(previous_positions.columns):
        return previous_snapshot

    try:
        from trades import (
            build_portfolio_from_trades_df,
            calculate_trade_cash_flow,
            load_trades,
        )

        trades_df = load_trades(TRADES_FILE)
    except Exception:
        return previous_snapshot

    if trades_df.empty:
        return previous_snapshot

    trades_until_previous = trades_df[
        (trades_df["date"] != "")
        & (trades_df["date"] <= previous_date)
    ].copy()

    if trades_until_previous.empty:
        return previous_snapshot

    try:
        rebuilt_portfolio = build_portfolio_from_trades_df(trades_until_previous)
    except Exception:
        return previous_snapshot

    if rebuilt_portfolio.empty:
        return previous_snapshot

    previous_positions["symbol"] = (
        previous_positions["symbol"].astype(str).str.strip().str.zfill(6)
    )
    previous_positions["price"] = pd.to_numeric(
        previous_positions["price"],
        errors="coerce",
    )

    prices = previous_positions[["symbol", "price"]].drop_duplicates(
        subset=["symbol"],
        keep="last",
    )

    rebuilt_portfolio["symbol"] = (
        rebuilt_portfolio["symbol"].astype(str).str.strip().str.zfill(6)
    )

    reconciled = rebuilt_portfolio.merge(prices, on="symbol", how="left")

    if reconciled["price"].isna().any():
        return previous_snapshot

    reconciled["quantity"] = pd.to_numeric(
        reconciled["quantity"],
        errors="coerce",
    )
    reconciled["cost_price"] = pd.to_numeric(
        reconciled["cost_price"],
        errors="coerce",
    )

    if reconciled[["quantity", "cost_price"]].isna().any().any():
        return previous_snapshot

    total_cost = float((reconciled["quantity"] * reconciled["cost_price"]).sum())
    total_value = float((reconciled["quantity"] * reconciled["price"]).sum())
    total_pnl = total_value - total_cost
    total_return = total_pnl / total_cost if total_cost else 0.0

    previous_day_trades = trades_df[trades_df["date"] == previous_date].copy()
    trade_cash_flow = calculate_trade_cash_flow(previous_day_trades)

    reconciled_snapshot = dict(previous_snapshot)
    reconciled_snapshot.update(
        {
            "total_cost": total_cost,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "today_trade_cash_flow": trade_cash_flow,
        }
    )

    return reconciled_snapshot


def save_position_snapshot(positions_df: pd.DataFrame):
    POSITION_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)

    df = positions_df.copy()

    required_columns = [
        "symbol",
        "name",
        "quantity",
        "cost_price",
        "price",
        "market_value",
        "quote_date",
        "quote_time",
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(f"持仓快照缺少字段：{missing_columns}")

    snapshot_df = pd.DataFrame(
        {
            "date": df["quote_date"].astype(str),
            "quote_time": df["quote_time"].astype(str),
            "symbol": df["symbol"].astype(str).str.zfill(6),
            "name": df["name"].astype(str),
            "quantity": pd.to_numeric(df["quantity"], errors="coerce"),
            "cost_price": pd.to_numeric(df["cost_price"], errors="coerce"),
            "price": pd.to_numeric(df["price"], errors="coerce"),
            "market_value": pd.to_numeric(df["market_value"], errors="coerce"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )

    date = snapshot_df["date"].iloc[0]
    existing_df = load_position_snapshots()

    if existing_df.empty:
        combined_df = snapshot_df
    else:
        combined_df = existing_df[existing_df["date"] != date]
        combined_df = pd.concat([combined_df, snapshot_df], ignore_index=True)

    combined_df = combined_df.sort_values(["date", "symbol"])
    combined_df.to_csv(POSITION_SNAPSHOT_FILE, index=False)


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
