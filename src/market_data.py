import re
from typing import Iterable

import pandas as pd
import requests


SINA_API = "https://hq.sinajs.cn/list={codes}"


def to_sina_code(symbol: str) -> str:
    """
    把 6 位 A 股 / ETF 代码转换成新浪行情代码。

    示例：
    600519 -> sh600519
    510300 -> sh510300
    159659 -> sz159659
    300750 -> sz300750
    """
    symbol = str(symbol).strip().zfill(6)

    if symbol.startswith(("5", "6", "9")):
        return f"sh{symbol}"

    if symbol.startswith(("0", "1", "2", "3")):
        return f"sz{symbol}"

    if symbol.startswith(("4", "8")):
        return f"bj{symbol}"

    raise ValueError(f"无法判断交易所的代码：{symbol}")


def from_sina_code(sina_code: str) -> str:
    return sina_code[-6:]


def parse_sina_response(text: str) -> pd.DataFrame:
    rows = []

    pattern = re.compile(r'var hq_str_(?P<code>\w+)="(?P<data>.*?)";')

    for match in pattern.finditer(text):
        sina_code = match.group("code")
        raw_data = match.group("data")

        symbol = from_sina_code(sina_code)

        if not raw_data:
            raise ValueError(f"{symbol} 新浪返回空数据，请检查代码是否正确")

        fields = raw_data.split(",")

        # 常见字段：
        # 0 名称
        # 1 今日开盘价
        # 2 昨日收盘价
        # 3 当前价 / 收盘后为收盘价
        # 4 今日最高价
        # 5 今日最低价
        # 8 成交量
        # 9 成交额
        # 30 日期
        # 31 时间
        if len(fields) < 32:
            raise ValueError(f"{symbol} 新浪返回字段不足：{raw_data}")

        name = fields[0]
        prev_close = float(fields[2])
        price = float(fields[3])

        # 停牌或异常情况下，当前价可能是 0，用昨收兜底
        if price <= 0:
            price = prev_close

        change = price - prev_close
        pct_change = change / prev_close * 100 if prev_close else 0

        rows.append(
            {
                "symbol": symbol,
                "quote_name": name,
                "price": price,
                "pct_change": pct_change,
                "change": change,
                "quote_date": fields[30],
                "quote_time": fields[31],
            }
        )

    if not rows:
        raise ValueError(f"新浪行情解析失败，原始返回：{text[:300]}")

    return pd.DataFrame(rows)


def fetch_a_share_quotes(symbols: Iterable[str]) -> pd.DataFrame:
    symbols = [str(symbol).strip().zfill(6) for symbol in symbols]
    sina_codes = [to_sina_code(symbol) for symbol in symbols]

    url = SINA_API.format(codes=",".join(sina_codes))

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://finance.sina.com.cn/",
    }

    print(f"正在从新浪获取行情：{', '.join(symbols)}")

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    response.encoding = "gbk"

    df = parse_sina_response(response.text)

    order = {symbol: index for index, symbol in enumerate(symbols)}
    df["sort_order"] = df["symbol"].map(order)
    df = df.sort_values("sort_order").drop(columns=["sort_order"])

    missing = set(symbols) - set(df["symbol"])
    if missing:
        raise ValueError(f"这些代码没有获取到新浪行情：{sorted(missing)}")

    return df