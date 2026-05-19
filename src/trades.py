import os
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError


PORTFOLIO_FILE = Path("portfolio.csv")
TRADES_FILE = Path("trades.csv")
TRADE_INPUT_FILE = Path("trade_input.csv")


PORTFOLIO_COLUMNS = ["symbol", "name", "quantity", "cost_price"]

TRADE_COLUMNS = [
    "date",
    "symbol",
    "side",
    "quantity",
    "price",
    "fee",
    "note",
]

TRADE_INPUT_COLUMNS = [
    "date",
    "symbol",
    "name",
    "side",
    "quantity",
    "price",
    "fee",
    "note",
    "processed",
]


def empty_portfolio_df() -> pd.DataFrame:
    return pd.DataFrame(columns=PORTFOLIO_COLUMNS)


def empty_trades_df() -> pd.DataFrame:
    return pd.DataFrame(columns=TRADE_COLUMNS)


def empty_trade_input_df() -> pd.DataFrame:
    return pd.DataFrame(columns=TRADE_INPUT_COLUMNS)


def calculate_fee_auto(quantity: float, price: float) -> float:
    """
    自动估算手续费。

    默认万 2.5，也就是 0.00025。
    可在 .env 中配置：

    COMMISSION_RATE=0.00025
    """
    commission_rate = float(os.getenv("COMMISSION_RATE", "0.00025"))
    amount = quantity * price
    return round(amount * commission_rate, 2)


def parse_fee(value, quantity: float, price: float) -> float:
    """
    fee 规则：

    - 空 / auto / -- / nan / none：自动计算
    - 数字：使用手动填写值
    """
    text = str(value).strip().lower()

    if text in ["", "auto", "--", "nan", "none"]:
        return calculate_fee_auto(quantity, price)

    return float(text)


def load_portfolio(path: Path = PORTFOLIO_FILE) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return empty_portfolio_df()

    df = pd.read_csv(path, dtype={"symbol": str})

    required_columns = set(PORTFOLIO_COLUMNS)
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"{path} 缺少字段：{sorted(missing_columns)}")

    df = df[PORTFOLIO_COLUMNS].copy()

    df["symbol"] = df["symbol"].astype(str).str.strip().str.zfill(6)
    df["name"] = df["name"].astype(str).str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["cost_price"] = pd.to_numeric(df["cost_price"], errors="coerce")

    if df["quantity"].isna().any():
        raise ValueError("portfolio.csv 中存在无法识别的 quantity")

    if df["cost_price"].isna().any():
        raise ValueError("portfolio.csv 中存在无法识别的 cost_price")

    return df


def save_portfolio(df: pd.DataFrame, path: Path = PORTFOLIO_FILE):
    df = df.copy()

    for col in PORTFOLIO_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[PORTFOLIO_COLUMNS].copy()

    if not df.empty:
        df["symbol"] = df["symbol"].astype(str).str.zfill(6)
        df["name"] = df["name"].astype(str).str.strip()
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
        df["cost_price"] = pd.to_numeric(df["cost_price"], errors="coerce").fillna(0)

        # 持仓为 0 的标的从 portfolio.csv 移除
        df = df[df["quantity"] > 0]

        df["quantity"] = df["quantity"].round(6)
        df["cost_price"] = df["cost_price"].round(3)
        df = df.sort_values("symbol")

    df.to_csv(path, index=False)


def load_trades(path: str | Path = TRADES_FILE) -> pd.DataFrame:
    path = Path(path)

    if not path.exists() or path.stat().st_size == 0:
        return empty_trades_df()

    try:
        df = pd.read_csv(path, dtype={"date": str, "symbol": str})
    except EmptyDataError:
        return empty_trades_df()

    for col in TRADE_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[TRADE_COLUMNS].copy()

    df["date"] = df["date"].astype(str).str.strip()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.zfill(6)
    df["side"] = df["side"].astype(str).str.strip().str.lower()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["fee"] = pd.to_numeric(df["fee"], errors="coerce").fillna(0)
    df["note"] = df["note"].fillna("").astype(str)

    return df


def save_trades(df: pd.DataFrame, path: Path = TRADES_FILE):
    df = df.copy()

    for col in TRADE_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[TRADE_COLUMNS].copy()
    df.to_csv(path, index=False)


def load_trade_input(path: Path = TRADE_INPUT_FILE) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        df = empty_trade_input_df()
        df.to_csv(path, index=False)
        return df

    try:
        df = pd.read_csv(path, dtype={"date": str, "symbol": str})
    except EmptyDataError:
        df = empty_trade_input_df()
        df.to_csv(path, index=False)
        return df

    for col in TRADE_INPUT_COLUMNS:
        if col not in df.columns:
            if col == "processed":
                df[col] = "no"
            elif col == "fee":
                df[col] = ""
            else:
                df[col] = ""

    df = df[TRADE_INPUT_COLUMNS].copy()

    # 去掉完全空白的行，避免 CSV 里多出来的空行导致报错
    df = df.dropna(how="all")

    if df.empty:
        return empty_trade_input_df()

    df["date"] = df["date"].astype(str).str.strip()
    df["symbol"] = df["symbol"].astype(str).str.strip().str.zfill(6)
    df["name"] = df["name"].fillna("").astype(str).str.strip()
    df["side"] = df["side"].astype(str).str.strip().str.lower()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    if df["quantity"].isna().any():
        raise ValueError("trade_input.csv 中存在无法识别的 quantity")

    if df["price"].isna().any():
        raise ValueError("trade_input.csv 中存在无法识别的 price")

    df["fee"] = df.apply(
        lambda row: parse_fee(
            row.get("fee", ""),
            float(row["quantity"]),
            float(row["price"]),
        ),
        axis=1,
    )

    df["note"] = df["note"].fillna("").astype(str)
    df["processed"] = df["processed"].fillna("no").astype(str).str.strip().str.lower()

    return df


def save_trade_input(df: pd.DataFrame, path: Path = TRADE_INPUT_FILE):
    df = df.copy()

    for col in TRADE_INPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[TRADE_INPUT_COLUMNS].copy()
    df.to_csv(path, index=False)

def trade_already_exists(trades_df: pd.DataFrame, row: pd.Series) -> bool:
    if trades_df.empty:
        return False

    symbol = str(row["symbol"]).zfill(6)
    side = str(row["side"]).lower()
    quantity = float(row["quantity"])
    price = float(row["price"])

    matched = trades_df[
        (trades_df["date"].astype(str) == str(row["date"]))
        & (trades_df["symbol"].astype(str).str.zfill(6) == symbol)
        & (trades_df["side"].astype(str).str.lower() == side)
        & (trades_df["quantity"].astype(float) == quantity)
        & (trades_df["price"].astype(float) == price)
    ]

    return not matched.empty

def append_trade_to_history(row: pd.Series) -> bool:
    trades_df = load_trades(TRADES_FILE)

    if trade_already_exists(trades_df, row):
        print(
            f"交易已存在，跳过追加："
            f"{row['date']} {row['symbol']} {row['side']} "
            f"{row['quantity']} @ {row['price']}"
        )
        return False

    new_row = {
        "date": str(row["date"]),
        "symbol": str(row["symbol"]).zfill(6),
        "side": str(row["side"]).lower(),
        "quantity": float(row["quantity"]),
        "price": float(row["price"]),
        "fee": float(row.get("fee", 0)),
        "note": str(row.get("note", "")),
    }

    trades_df = pd.concat([trades_df, pd.DataFrame([new_row])], ignore_index=True)
    save_trades(trades_df, TRADES_FILE)

    return True


def apply_trade_to_portfolio(portfolio: pd.DataFrame, row: pd.Series) -> pd.DataFrame:
    symbol = str(row["symbol"]).strip().zfill(6)
    name = str(row.get("name", "")).strip()
    side = str(row["side"]).strip().lower()
    quantity = float(row["quantity"])
    price = float(row["price"])
    fee = float(row.get("fee", 0))

    if side not in ["buy", "sell"]:
        raise ValueError(f"{symbol} 的 side 只能是 buy 或 sell")

    if quantity <= 0:
        raise ValueError(f"{symbol} 的 quantity 必须大于 0")

    if price <= 0:
        raise ValueError(f"{symbol} 的 price 必须大于 0")

    matched = portfolio[portfolio["symbol"] == symbol]

    if matched.empty:
        if side == "sell":
            raise ValueError(f"portfolio.csv 中没有 {symbol}，无法卖出")

        if not name or name.lower() == "nan":
            raise ValueError(f"新增持仓 {symbol} 时，trade_input.csv 的 name 必须填写")

        old_quantity = 0.0
        old_cost_price = 0.0
        display_name = name
    else:
        idx = matched.index[0]
        old_quantity = float(portfolio.loc[idx, "quantity"])
        old_cost_price = float(portfolio.loc[idx, "cost_price"])
        display_name = str(portfolio.loc[idx, "name"])

        if name and name.lower() != "nan":
            display_name = name

    if side == "buy":
        old_cost_amount = old_quantity * old_cost_price
        buy_amount = quantity * price + fee

        new_quantity = old_quantity + quantity
        new_cost_price = (old_cost_amount + buy_amount) / new_quantity

    else:
        if quantity > old_quantity:
            raise ValueError(
                f"{symbol} 卖出数量不能超过当前持仓：当前 {old_quantity}，试图卖出 {quantity}"
            )

        new_quantity = old_quantity - quantity

        # 移动加权成本法：卖出不改变剩余持仓成本价
        new_cost_price = old_cost_price if new_quantity > 0 else 0.0

    if matched.empty:
        new_row = {
            "symbol": symbol,
            "name": display_name,
            "quantity": new_quantity,
            "cost_price": new_cost_price,
        }

        portfolio = pd.concat([portfolio, pd.DataFrame([new_row])], ignore_index=True)
    else:
        idx = matched.index[0]
        portfolio.loc[idx, "name"] = display_name
        portfolio.loc[idx, "quantity"] = new_quantity
        portfolio.loc[idx, "cost_price"] = new_cost_price

    return portfolio


def process_trade_input_until(trade_date: str) -> int:
    """
    自动处理 trade_input.csv 中：
    processed != yes 且 date <= trade_date 的交易。

    每条交易会：
    1. 更新 portfolio.csv
    2. 追加到 trades.csv
    3. 把 trade_input.csv 对应行 processed 改成 yes
    """
    input_df = load_trade_input(TRADE_INPUT_FILE)

    if input_df.empty:
        return 0

    pending_mask = (
        (input_df["processed"] != "yes")
        & (input_df["date"] != "")
        & (input_df["date"] <= trade_date)
    )

    pending_df = input_df[pending_mask].copy()

    if pending_df.empty:
        return 0

    portfolio = load_portfolio(PORTFOLIO_FILE)

    processed_count = 0

    # 按日期顺序处理，避免多笔交易顺序错乱
    pending_df = pending_df.sort_values(["date", "symbol"])

    for idx, row in pending_df.iterrows():
        portfolio = apply_trade_to_portfolio(portfolio, row)
        append_trade_to_history(row)

        input_df.loc[idx, "processed"] = "yes"
        input_df.loc[idx, "fee"] = float(row["fee"])
        processed_count += 1

    save_portfolio(portfolio, PORTFOLIO_FILE)
    save_trade_input(input_df, TRADE_INPUT_FILE)

    return processed_count


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
    买入：净投入为正数
    卖出：净投入为负数
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