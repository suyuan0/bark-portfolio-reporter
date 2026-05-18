import os
import sys

import pandas as pd
from dotenv import load_dotenv

from calculator import calculate_positions
from market_data import fetch_a_share_quotes
from notifier import send_bark
from report import build_report


def load_portfolio(path: str = "portfolio.csv") -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到持仓文件：{path}")

    df = pd.read_csv(path, dtype={"symbol": str})

    required_columns = {"symbol", "name", "quantity", "cost_price"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"portfolio.csv 缺少字段：{sorted(missing_columns)}")

    df["symbol"] = df["symbol"].astype(str).str.strip().str.zfill(6)

    return df


def main():
    load_dotenv()

    bark_key = os.getenv("BARK_KEY")
    bark_icon = os.getenv("BARK_ICON")
    bark_group = os.getenv("BARK_GROUP", "收益日报")

    if not bark_key:
        raise ValueError("缺少 BARK_KEY，请在 .env 中配置")

    portfolio_df = load_portfolio("portfolio.csv")
    symbols = portfolio_df["symbol"].tolist()

    quotes_df = fetch_a_share_quotes(symbols)
    positions_df = calculate_positions(portfolio_df, quotes_df)

    report = build_report(positions_df)

    print(report)

    send_bark(
        device_key=bark_key,
        title="📈 今日收益日报",
        body=report,
        icon=bark_icon,
        group=bark_group,
    )

    print("Bark 推送成功")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"程序运行失败：{exc}", file=sys.stderr)
        sys.exit(1)