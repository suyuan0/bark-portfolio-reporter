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

from cron_manager import (
    CronConfig,
    build_cron_block,
    default_cron_config,
    parse_project_cron_block,
    read_user_crontab,
    replace_project_cron_block,
    write_user_crontab,
)


PORTFOLIO_FILE = PROJECT_ROOT / "portfolio.csv"
TRADES_FILE = PROJECT_ROOT / "trades.csv"
TRADE_INPUT_FILE = PROJECT_ROOT / "trade_input.csv"
SNAPSHOT_FILE = PROJECT_ROOT / "data" / "snapshots.csv"
LOG_FILE = PROJECT_ROOT / "logs" / "app.log"

COLUMN_LABELS = {
    "date": "日期",
    "symbol": "代码",
    "name": "名称",
    "side": "方向",
    "quantity": "数量",
    "price": "价格",
    "fee": "手续费",
    "note": "备注",
    "processed": "是否已处理",
    "cost_price": "成本价",
    "quote_time": "行情时间",
    "total_cost": "持仓成本",
    "total_value": "当前市值",
    "total_pnl": "累计盈亏",
    "total_return": "累计收益率",
    "today_trade_cash_flow": "今日交易净投入",
    "daily_pnl": "今日盈亏",
    "daily_return": "今日收益率",
    "created_at": "创建时间",
}


st.set_page_config(
    page_title="Bark 收益日报",
    page_icon="📈",
    layout="wide",
)

def get_column_config(columns):
    config = {}

    for col in columns:
        label = COLUMN_LABELS.get(col, col)

        if col == "side":
            config[col] = st.column_config.SelectboxColumn(
                label,
                options=["buy", "sell"],
                help="buy=买入，sell=卖出",
            )
        elif col == "processed":
            config[col] = st.column_config.SelectboxColumn(
                label,
                options=["no", "yes"],
            )
        elif col in ["quantity", "price", "cost_price"]:
            config[col] = st.column_config.NumberColumn(
                label,
                min_value=0.0,
                format="%.3f" if col in ["price", "cost_price"] else "%.0f",
            )
        elif col == "fee":
            config[col] = st.column_config.TextColumn(
                label,
                help="手续费，可留空，程序会自动估算",
            )
        else:
            config[col] = st.column_config.TextColumn(label)

    return config

def display_df_with_chinese_columns(df: pd.DataFrame):
    display_df = df.rename(columns=COLUMN_LABELS)
    st.dataframe(display_df, width="stretch")

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

def sort_trades_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    expected_columns = ["date", "symbol", "side", "quantity", "price", "fee", "note"]

    for col in expected_columns:
        if col not in df.columns:
            df[col] = ""

    df = df[expected_columns]

    df["date"] = df["date"].fillna("").astype(str).str.strip()
    df["symbol"] = df["symbol"].fillna("").astype(str).str.strip().str.zfill(6)
    df["side"] = df["side"].fillna("").astype(str).str.strip()
    df["note"] = df["note"].fillna("").astype(str)

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    # fee 允许为空，所以不要强制转数字
    df["fee"] = df["fee"].fillna("").astype(str).str.strip()

    df = df.sort_values(
        by=["date", "symbol", "side", "price"],
        ascending=[True, True, True, True],
        na_position="last",
    )

    return df


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
        display_df_with_chinese_columns(portfolio_df)

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

    df = sort_trades_df(df)
    df["fee"] = df["fee"].fillna("").astype(str)
    df["note"] = df["note"].fillna("").astype(str)

    df = normalize_editable_text_columns(df, ["fee", "note"])

    edited_df = st.data_editor(
        df,
        width="stretch",
        num_rows="dynamic",
        column_config=get_column_config(df.columns),
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 保存 trades.csv", type="primary"):
            sorted_df = sort_trades_df(edited_df)
            save_csv(TRADES_FILE, sorted_df)
            st.success("trades.csv 已保存，并已自动排序")
            st.rerun()

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
        column_config=get_column_config(df.columns),
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


def render_cron_settings():
    st.header("⏰ 定时任务")

    st.info(
        "这里只管理本项目自己的 crontab 区块，不会编辑其他定时任务。"
        "页面必须用同一个 Linux 用户运行，才能修改该用户的 crontab。"
    )

    try:
        current_crontab = read_user_crontab()
    except Exception as exc:
        st.error(f"读取 crontab 失败：{exc}")
        return

    existing_config = parse_project_cron_block(current_crontab)
    config = existing_config or default_cron_config(PROJECT_ROOT, sys.executable)

    if existing_config is None:
        st.caption("当前 crontab 里还没有本项目的定时任务区块，将按默认值创建。")
    else:
        st.caption("已读取到本项目的定时任务配置。")

    enabled = st.checkbox("启用定时运行", value=config.enabled)

    col1, col2, col3 = st.columns(3)

    with col1:
        hour = st.number_input(
            "小时",
            min_value=0,
            max_value=23,
            value=int(config.hour),
            step=1,
        )

    with col2:
        minute = st.number_input(
            "分钟",
            min_value=0,
            max_value=59,
            value=int(config.minute),
            step=1,
        )

    weekday_options = {
        "周一到周五": "1-5",
        "每天": "*",
        "周一到周六": "1-6",
        "自定义": config.weekdays,
    }
    default_weekday_label = next(
        (
            label
            for label, value in weekday_options.items()
            if value == config.weekdays and label != "自定义"
        ),
        "自定义",
    )

    with col3:
        weekday_label = st.selectbox(
            "运行日期",
            list(weekday_options.keys()),
            index=list(weekday_options.keys()).index(default_weekday_label),
        )

    weekdays = weekday_options[weekday_label]

    if weekday_label == "自定义":
        weekdays = st.text_input(
            "cron 星期字段",
            value=str(config.weekdays),
            help="例如 1-5 表示周一到周五，* 表示每天。",
        )

    project_dir = st.text_input("项目路径", value=config.project_dir)
    python_path = st.text_input("Python 路径", value=config.python_path)
    script_path = st.text_input("脚本路径", value=config.script_path)
    log_path = st.text_input("日志路径", value=config.log_path)

    new_config = CronConfig(
        enabled=enabled,
        minute=int(minute),
        hour=int(hour),
        weekdays=str(weekdays).strip() or "1-5",
        project_dir=project_dir.strip(),
        python_path=python_path.strip(),
        script_path=script_path.strip(),
        log_path=log_path.strip(),
    )
    new_crontab = replace_project_cron_block(current_crontab, new_config)

    st.subheader("将写入的本项目 cron 区块")
    st.code(build_cron_block(new_config), language="cron")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 保存定时任务", type="primary"):
            try:
                write_user_crontab(new_crontab)
                st.success("定时任务已保存")
                st.rerun()
            except Exception as exc:
                st.error(f"保存 crontab 失败：{exc}")

    with col2:
        if st.button("🔄 重新读取 crontab"):
            st.rerun()

    with st.expander("查看当前 crontab"):
        st.code(current_crontab or "当前用户没有 crontab", language="cron")


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
            "定时任务",
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
    elif page == "定时任务":
        render_cron_settings()
    elif page == "手动运行":
        render_manual_run()
    elif page == "运行日志":
        render_logs()


if __name__ == "__main__":
    main()
