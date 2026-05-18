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