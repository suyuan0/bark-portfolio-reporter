import os
import sys

import pandas as pd
from dotenv import load_dotenv

from calculator import calculate_positions, calculate_summary
from market_calendar import get_today_shanghai_date, is_a_share_trading_day
from market_data import fetch_a_share_quotes
from notifier import send_bark
from report import build_report
from storage import get_previous_snapshot, save_snapshot
from trades import (
    calculate_trade_cash_flow,
    get_today_trades,
    process_trade_input_until,
    rebuild_portfolio_from_trades,
)


def load_portfolio(path: str = "portfolio.csv") -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到持仓文件：{path}")

    df = pd.read_csv(path, dtype={"symbol": str})

    required_columns = {"symbol", "name", "quantity", "cost_price"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"portfolio.csv 缺少字段：{sorted(missing_columns)}")

    df["symbol"] = df["symbol"].astype(str).str.strip().str.zfill(6)
    df["name"] = df["name"].fillna("").astype(str).str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["cost_price"] = pd.to_numeric(df["cost_price"], errors="coerce")

    if df["quantity"].isna().any():
        raise ValueError("portfolio.csv 中存在无法识别的 quantity")

    if df["cost_price"].isna().any():
        raise ValueError("portfolio.csv 中存在无法识别的 cost_price")

    df = df[df["symbol"].notna()]
    df = df[df["symbol"].astype(str).str.strip() != ""]
    df = df[df["quantity"] > 0]

    if df.empty:
        raise ValueError("portfolio.csv 没有任何持仓，请检查文件内容")

    return df


def update_portfolio_names_from_quotes(
    portfolio_path: str,
    quotes_df: pd.DataFrame,
):
    """
    用行情接口返回的 quote_name 补全 portfolio.csv 里的名称。

    当 portfolio.csv 是从 trades.csv 自动重建时，如果 trades.csv 没有 name 字段，
    portfolio.csv 里的 name 可能只是证券代码。这里会用新浪行情返回的名称替换。
    """
    if not os.path.exists(portfolio_path):
        return

    df = pd.read_csv(portfolio_path, dtype={"symbol": str})

    if df.empty:
        return

    if "symbol" not in df.columns or "name" not in df.columns:
        return

    if "symbol" not in quotes_df.columns or "quote_name" not in quotes_df.columns:
        return

    df["symbol"] = df["symbol"].astype(str).str.strip().str.zfill(6)
    df["name"] = df["name"].fillna("").astype(str).str.strip()

    quotes = quotes_df[["symbol", "quote_name"]].copy()
    quotes["symbol"] = quotes["symbol"].astype(str).str.strip().str.zfill(6)
    quotes["quote_name"] = quotes["quote_name"].fillna("").astype(str).str.strip()

    df = df.merge(quotes, on="symbol", how="left")

    def choose_name(row):
        current_name = str(row["name"]).strip()
        quote_name = str(row.get("quote_name", "")).strip()

        # 如果当前名称为空、nan，或者只是代码，则用行情名称替换
        if (
            not current_name
            or current_name.lower() == "nan"
            or current_name == str(row["symbol"]).zfill(6)
        ):
            if quote_name and quote_name.lower() != "nan":
                return quote_name

        return current_name

    df["name"] = df.apply(choose_name, axis=1)

    df = df.drop(columns=["quote_name"], errors="ignore")

    # 保持字段顺序
    columns = ["symbol", "name", "quantity", "cost_price"]
    existing_columns = [col for col in columns if col in df.columns]
    other_columns = [col for col in df.columns if col not in existing_columns]
    df = df[existing_columns + other_columns]

    df.to_csv(portfolio_path, index=False)


def main():
    load_dotenv()

    bark_key = os.getenv("BARK_KEY")
    bark_icon = os.getenv("BARK_ICON")
    bark_group = os.getenv("BARK_GROUP", "收益日报")

    if not bark_key:
        raise ValueError("缺少 BARK_KEY，请在 .env 中配置")

    today = get_today_shanghai_date()
    is_trading_day, reason = is_a_share_trading_day(today)

    print(f"{today} A 股交易日判断：{reason}")

    if not is_trading_day:
        print(f"{today} 不是 A 股交易日：{reason}，跳过运行")
        return

    processed_count = process_trade_input_until(today)

    if processed_count > 0:
        print(f"已检查 trade_input.csv 中的 {processed_count} 条待处理交易")

    rebuilt_count = rebuild_portfolio_from_trades(today)
    print(f"已根据 trades.csv 重建 portfolio.csv，共纳入 {rebuilt_count} 条交易")

    portfolio_df = load_portfolio("portfolio.csv")
    symbols = portfolio_df["symbol"].tolist()

    quotes_df = fetch_a_share_quotes(symbols)

    update_portfolio_names_from_quotes("portfolio.csv", quotes_df)

    # 名称补全后重新读取 portfolio.csv，确保日报里用更新后的名称
    portfolio_df = load_portfolio("portfolio.csv")

    positions_df = calculate_positions(portfolio_df, quotes_df)

    quote_date = positions_df["quote_date"].iloc[0]

    previous_snapshot = get_previous_snapshot(quote_date)

    today_trades = get_today_trades(quote_date, "trades.csv")
    today_trade_cash_flow = calculate_trade_cash_flow(today_trades)

    summary = calculate_summary(
        positions_df=positions_df,
        previous_snapshot=previous_snapshot,
        today_trade_cash_flow=today_trade_cash_flow,
    )

    report = build_report(positions_df, summary)

    print(report)

    send_bark(
        device_key=bark_key,
        title="📈 今日收益日报",
        body=report,
        icon=bark_icon,
        group=bark_group,
    )

    save_snapshot(summary)

    print("Bark 推送成功")
    print("每日快照保存成功")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"程序运行失败：{exc}", file=sys.stderr)
        sys.exit(1)