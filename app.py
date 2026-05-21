import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


PORTFOLIO_FILE = PROJECT_ROOT / "portfolio.csv"
TRADES_FILE = PROJECT_ROOT / "trades.csv"
TRADE_INPUT_FILE = PROJECT_ROOT / "trade_input.csv"
SNAPSHOT_FILE = PROJECT_ROOT / "data" / "snapshots.csv"
LOG_FILE = PROJECT_ROOT / "logs" / "app.log"


st.set_page_config(
    page_title="Bark 收益日报",
    page_icon="📈",
    layout="wide",
)


def ensure_file(path: Path, columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)


def read_csv_safe(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns or [])

    try:
        return pd.read_csv(path, dtype={"date": str, "symbol": str})
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns or [])


def save_csv(path: Path, df: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def get_file_mtime(path: Path) -> str:
    if not path.exists():
        return "文件不存在"

    ts = datetime.fromtimestamp(path.stat().st_mtime)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def run_main_script() -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "src/main.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )

    return result.returncode, result.stdout, result.stderr


def update_portfolio_names_from_quotes(portfolio_path: Path, quotes_df: pd.DataFrame):
    if not portfolio_path.exists():
        return

    df = read_csv_safe(portfolio_path)

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
        symbol = str(row["symbol"]).zfill(6)

        if not current_name or current_name.lower() == "nan" or current_name == symbol:
            if quote_name and quote_name.lower() != "nan":
                return quote_name

        return current_name

    df["name"] = df.apply(choose_name, axis=1)
    df = df.drop(columns=["quote_name"], errors="ignore")

    columns = ["symbol", "name", "quantity", "cost_price"]
    existing_columns = [col for col in columns if col in df.columns]
    other_columns = [col for col in df.columns if col not in existing_columns]
    df = df[existing_columns + other_columns]

    save_csv(portfolio_path, df)


def rebuild_portfolio_only():
    from market_calendar import get_today_shanghai_date
    from market_data import fetch_a_share_quotes
    from trades import rebuild_portfolio_from_trades

    today = get_today_shanghai_date()

    count = rebuild_portfolio_from_trades(today)

    portfolio_df = read_csv_safe(
        PORTFOLIO_FILE,
        columns=["symbol", "name", "quantity", "cost_price"],
    )

    if not portfolio_df.empty:
        symbols = portfolio_df["symbol"].astype(str).str.zfill(6).tolist()
        quotes_df = fetch_a_share_quotes(symbols)
        update_portfolio_names_from_quotes(PORTFOLIO_FILE, quotes_df)

    return count


def render_overview():
    st.header("📊 总览")

    portfolio_df = read_csv_safe(
        PORTFOLIO_FILE,
        columns=["symbol", "name", "quantity", "cost_price"],
    )

    trades_df = read_csv_safe(
        TRADES_FILE,
        columns=["date", "symbol", "side", "quantity", "price", "fee", "note"],
    )

    snapshots_df = read_csv_safe(SNAPSHOT_FILE)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("当前持仓数", len(portfolio_df))

    with col2:
        st.metric("交易记录数", len(trades_df))

    with col3:
        st.metric("快照记录数", len(snapshots_df))

    with col4:
        st.metric("日志文件", "存在" if LOG_FILE.exists() else "无")

    st.divider()

    st.subheader("当前持仓")

    if portfolio_df.empty:
        st.info("暂无持仓。请先维护 trades.csv，然后重建 portfolio.csv。")
    else:
        st.dataframe(portfolio_df, width="stretch")

    st.caption(f"portfolio.csv 更新时间：{get_file_mtime(PORTFOLIO_FILE)}")
    st.caption(f"trades.csv 更新时间：{get_file_mtime(TRADES_FILE)}")
    st.caption(f"snapshots.csv 更新时间：{get_file_mtime(SNAPSHOT_FILE)}")


def render_trades_editor():
    st.header("🧾 交易记录 trades.csv")

    st.info(
        "推荐直接维护 trades.csv。程序会每天根据 trades.csv 自动重建 portfolio.csv。"
    )

    ensure_file(
        TRADES_FILE,
        ["date", "symbol", "side", "quantity", "price", "fee", "note"],
    )

    df = read_csv_safe(
        TRADES_FILE,
        columns=["date", "symbol", "side", "quantity", "price", "fee", "note"],
    )
    df = normalize_editable_text_columns(df, ["fee", "note"])

    df["fee"] = df["fee"].fillna("").astype(str)
    df["note"] = df["note"].fillna("").astype(str)

    edited_df = st.data_editor(
        df,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "date": st.column_config.TextColumn(
                "date",
                help="交易日期，例如 2026-05-19",
            ),
            "symbol": st.column_config.TextColumn(
                "symbol",
                help="证券代码，例如 510300",
            ),
            "side": st.column_config.SelectboxColumn(
                "side",
                options=["buy", "sell"],
                help="buy=买入，sell=卖出",
            ),
            "quantity": st.column_config.NumberColumn(
                "quantity",
                min_value=0.0,
                step=100.0,
            ),
            "price": st.column_config.NumberColumn(
                "price",
                min_value=0.0,
                step=0.001,
                format="%.3f",
            ),
            "fee": st.column_config.TextColumn(
                "fee",
                help="手续费，可留空，程序会自动估算",
            ),
            "note": st.column_config.TextColumn("note"),
        },
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 保存 trades.csv", type="primary"):
            save_csv(TRADES_FILE, edited_df)
            st.success("trades.csv 已保存")

    with col2:
        if st.button("🔄 根据 trades.csv 重建 portfolio.csv"):
            try:
                count = rebuild_portfolio_only()
                st.success(f"重建完成，共纳入 {count} 条交易")
            except Exception as exc:
                st.error(f"重建失败：{exc}")


def render_trade_input_editor():
    st.header("📝 待处理交易 trade_input.csv")

    st.info(
        "这是可选功能。如果你习惯直接维护 trades.csv，可以不使用这个页面。"
    )

    ensure_file(
        TRADE_INPUT_FILE,
        [
            "date",
            "symbol",
            "name",
            "side",
            "quantity",
            "price",
            "fee",
            "note",
            "processed",
        ],
    )

    df = read_csv_safe(
        TRADE_INPUT_FILE,
        columns=[
            "date",
            "symbol",
            "name",
            "side",
            "quantity",
            "price",
            "fee",
            "note",
            "processed",
        ],
    )
    df = normalize_editable_text_columns(df, ["name", "fee", "note", "processed"])

    df["fee"] = df["fee"].fillna("").astype(str)
    df["note"] = df["note"].fillna("").astype(str)
    df["name"] = df["name"].fillna("").astype(str)
    df["processed"] = df["processed"].fillna("no").astype(str)

    edited_df = st.data_editor(
        df,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "date": st.column_config.TextColumn("date"),
            "symbol": st.column_config.TextColumn("symbol"),
            "name": st.column_config.TextColumn("name"),
            "side": st.column_config.SelectboxColumn(
                "side",
                options=["buy", "sell"],
            ),
            "quantity": st.column_config.NumberColumn("quantity", min_value=0.0),
            "price": st.column_config.NumberColumn(
                "price",
                min_value=0.0,
                format="%.3f",
            ),
            "fee": st.column_config.TextColumn(
                "fee",
                help="可留空，程序会自动估算",
            ),
            "note": st.column_config.TextColumn("note"),
            "processed": st.column_config.SelectboxColumn(
                "processed",
                options=["no", "yes"],
            ),
        },
    )

    if st.button("💾 保存 trade_input.csv", type="primary"):
        save_csv(TRADE_INPUT_FILE, edited_df)
        st.success("trade_input.csv 已保存")


def render_portfolio():
    st.header("💼 当前持仓 portfolio.csv")

    st.warning(
        "portfolio.csv 是程序根据 trades.csv 自动生成的文件，一般不建议手动修改。"
    )

    df = read_csv_safe(
        PORTFOLIO_FILE,
        columns=["symbol", "name", "quantity", "cost_price"],
    )

    if df.empty:
        st.info("暂无持仓。")
    else:
        st.dataframe(df, width="stretch")

    if st.button("🔄 重新根据 trades.csv 生成持仓"):
        try:
            count = rebuild_portfolio_only()
            st.success(f"重建完成，共纳入 {count} 条交易")
            st.rerun()
        except Exception as exc:
            st.error(f"重建失败：{exc}")


def render_snapshots():
    st.header("📅 每日快照 snapshots.csv")

    df = read_csv_safe(SNAPSHOT_FILE)

    if df.empty:
        st.info("暂无快照。运行一次收益日报后会生成。")
        return

    st.dataframe(df, width="stretch")

    if "total_value" in df.columns:
        chart_df = df.copy()
        chart_df["date"] = chart_df["date"].astype(str)
        chart_df = chart_df.set_index("date")

        st.subheader("总资产曲线")
        st.line_chart(chart_df["total_value"])


def render_manual_run():
    st.header("🚀 手动运行收益日报")

    st.warning("点击后会执行 `python src/main.py`，并可能发送 Bark 推送。")

    if st.button("📨 立即运行并推送", type="primary"):
        with st.spinner("正在运行 src/main.py ..."):
            try:
                code, stdout, stderr = run_main_script()

                if code == 0:
                    st.success("运行成功")
                else:
                    st.error(f"运行失败，退出码：{code}")

                st.subheader("标准输出")
                st.code(stdout or "无输出", language="text")

                if stderr:
                    st.subheader("错误输出")
                    st.code(stderr, language="text")

            except subprocess.TimeoutExpired:
                st.error("运行超时")
            except Exception as exc:
                st.error(f"运行失败：{exc}")


def render_logs():
    st.header("📜 运行日志")

    if not LOG_FILE.exists():
        st.info("暂无日志文件。")
        return

    lines = st.slider("显示最近多少行", 20, 500, 100, step=20)

    text = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
    content = "\n".join(text.splitlines()[-lines:])

    st.code(content or "日志为空", language="text")


def normalize_editable_text_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()

    for col in columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    return df

def main():
    st.title("📈 Bark 收益日报")

    page = st.sidebar.radio(
        "菜单",
        [
            "总览",
            "交易记录",
            "待处理交易",
            "当前持仓",
            "每日快照",
            "手动运行",
            "运行日志",
        ],
    )

    if page == "总览":
        render_overview()
    elif page == "交易记录":
        render_trades_editor()
    elif page == "待处理交易":
        render_trade_input_editor()
    elif page == "当前持仓":
        render_portfolio()
    elif page == "每日快照":
        render_snapshots()
    elif page == "手动运行":
        render_manual_run()
    elif page == "运行日志":
        render_logs()


if __name__ == "__main__":
    main()