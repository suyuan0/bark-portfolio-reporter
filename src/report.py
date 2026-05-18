import pandas as pd


def money(value: float, show_sign: bool = False) -> str:
    if show_sign:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:,.2f} 元"

    return f"{value:,.2f} 元"


def percent(value: float, show_sign: bool = False) -> str:
    if show_sign:
        sign = "+" if value > 0 else ""
        return f"{sign}{value * 100:.2f}%"

    return f"{value * 100:.2f}%"


def build_report(positions_df: pd.DataFrame) -> str:
    quote_date = positions_df["quote_date"].iloc[0]
    quote_time = positions_df["quote_time"].iloc[0]

    total_cost = positions_df["cost_amount"].sum()
    total_value = positions_df["market_value"].sum()
    total_pnl = total_value - total_cost
    total_return = total_pnl / total_cost if total_cost else 0

    lines = [
        f"日期：{quote_date} {quote_time}",
        "",
        f"持仓成本：{money(total_cost)}",
        f"当前市值：{money(total_value)}",
        f"累计盈亏：{money(total_pnl, show_sign=True)}",
        f"累计收益率：{percent(total_return, show_sign=True)}",
        "",
        "持仓明细：",
        "",
    ]

    sorted_df = positions_df.sort_values("pnl", ascending=False)

    for _, row in sorted_df.iterrows():
        lines.extend(
            [
                f"{row['name']}",
                f"  现价：{row['price']:.3f}",
                f"  涨跌幅：{row['pct_change']:.2f}%",
                f"  盈亏：{money(row['pnl'], show_sign=True)}",
                f"  收益率：{percent(row['return_rate'], show_sign=True)}",
                "",
            ]
        )

    return "\n".join(lines).strip()