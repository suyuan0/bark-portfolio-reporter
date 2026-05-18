import pandas as pd


def calculate_positions(
    portfolio_df: pd.DataFrame,
    quotes_df: pd.DataFrame,
) -> pd.DataFrame:
    portfolio_df = portfolio_df.copy()
    quotes_df = quotes_df.copy()

    portfolio_df["symbol"] = portfolio_df["symbol"].astype(str).str.zfill(6)
    quotes_df["symbol"] = quotes_df["symbol"].astype(str).str.zfill(6)

    portfolio_df["quantity"] = pd.to_numeric(
        portfolio_df["quantity"],
        errors="coerce",
    )

    portfolio_df["cost_price"] = pd.to_numeric(
        portfolio_df["cost_price"],
        errors="coerce",
    )

    if portfolio_df["quantity"].isna().any():
        raise ValueError("portfolio.csv 中存在无法识别的 quantity")

    if portfolio_df["cost_price"].isna().any():
        raise ValueError("portfolio.csv 中存在无法识别的 cost_price")

    df = portfolio_df.merge(quotes_df, on="symbol", how="left")

    if df["price"].isna().any():
        missing = df[df["price"].isna()]["symbol"].tolist()
        raise ValueError(f"没有获取到行情的代码：{missing}")

    df["cost_amount"] = df["quantity"] * df["cost_price"]
    df["market_value"] = df["quantity"] * df["price"]
    df["pnl"] = df["market_value"] - df["cost_amount"]
    df["return_rate"] = df["pnl"] / df["cost_amount"]

    return df


def calculate_summary(
    positions_df: pd.DataFrame,
    previous_snapshot: dict | None = None,
) -> dict:
    quote_date = positions_df["quote_date"].iloc[0]
    quote_time = positions_df["quote_time"].iloc[0]

    total_cost = positions_df["cost_amount"].sum()
    total_value = positions_df["market_value"].sum()
    total_pnl = total_value - total_cost
    total_return = total_pnl / total_cost if total_cost else 0

    summary = {
        "quote_date": quote_date,
        "quote_time": quote_time,
        "total_cost": total_cost,
        "total_value": total_value,
        "total_pnl": total_pnl,
        "total_return": total_return,
        "daily_pnl": None,
        "daily_return": None,
        "previous_date": None,
        "previous_total_value": None,
    }

    if previous_snapshot:
        previous_total_value = float(previous_snapshot["total_value"])

        daily_pnl = total_value - previous_total_value
        daily_return = daily_pnl / previous_total_value if previous_total_value else 0

        summary["daily_pnl"] = daily_pnl
        summary["daily_return"] = daily_return
        summary["previous_date"] = previous_snapshot["date"]
        summary["previous_total_value"] = previous_total_value

    return summary