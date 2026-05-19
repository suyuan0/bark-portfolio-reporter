import os

import pandas as pd
from pandas.errors import EmptyDataError


def load_trades(path: str = "trades.csv") -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "side",
                "quantity",
                "price",
                "fee",
                "note",
            ]
        )

    if os.path.getsize(path) == 0:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "side",
                "quantity",
                "price",
                "fee",
                "note",
            ]
        )

    try:
        df = pd.read_csv(path, dtype={"date": str, "symbol": str})
    except EmptyDataError:
        return pd.DataFrame(
            columns=[
                "date",
                "symbol",
                "side",
                "quantity",
                "price",
                "fee",
                "note",
            ]
        )

    required_columns = {"date", "symbol", "side", "quantity", "price", "fee"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"trades.csv 缺少字段：{sorted(missing_columns)}")

    df["date"] = df["date"].astype(str).str.strip()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.zfill(6)
    df["side"] = df["side"].astype(str).str.strip().str.lower()

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["fee"] = pd.to_numeric(df["fee"], errors="coerce").fillna(0)

    if df["quantity"].isna().any():
        raise ValueError("trades.csv 中存在无法识别的 quantity")

    if df["price"].isna().any():
        raise ValueError("trades.csv 中存在无法识别的 price")

    invalid_side = df[~df["side"].isin(["buy", "sell"])]
    if not invalid_side.empty:
        raise ValueError(
            f"trades.csv 中 side 只能是 buy 或 sell，错误行：{invalid_side.to_dict('records')}"
        )

    return df


def get_today_trades(
    trade_date: str,
    path: str = "trades.csv",
) -> pd.DataFrame:
    df = load_trades(path)

    if df.empty:
        return df

    return df[df["date"] == trade_date].copy()


def calculate_trade_cash_flow(trades_df: pd.DataFrame) -> float:
    """
    计算当天交易净投入。

    买入：
        现金流出 = quantity * price + fee
        记为正数

    卖出：
        现金流入 = quantity * price - fee
        记为负数

    返回值：
        > 0 表示当天净买入
        < 0 表示当天净卖出
        = 0 表示无交易或买卖抵消
    """
    if trades_df.empty:
        return 0.0

    net_cash_flow = 0.0

    for _, row in trades_df.iterrows():
        amount = float(row["quantity"]) * float(row["price"])
        fee = float(row.get("fee", 0))

        if row["side"] == "buy":
            net_cash_flow += amount + fee
        elif row["side"] == "sell":
            net_cash_flow -= amount - fee

    return net_cash_flow