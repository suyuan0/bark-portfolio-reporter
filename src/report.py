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


def trade_flow_text(value: float) -> str:
    if value > 0:
        return f"净买入 {money(value)}"
    if value < 0:
        return f"净卖出 {money(abs(value))}"
    return "无交易"


def build_report(
    positions_df: pd.DataFrame,
    summary: dict,
) -> str:
    lines = [
        f"日期：{summary['quote_date']} {summary['quote_time']}",
        "",
    ]

    if summary["daily_pnl"] is None:
        lines.extend(
            [
                "今日盈亏：暂无",
                "今日收益率：暂无",
                "说明：今天是第一条快照，明天开始可计算今日盈亏。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"今日盈亏：{money(summary['daily_pnl'], show_sign=True)}",
                f"今日收益率：{percent(summary['daily_return'], show_sign=True)}",
                f"对比日期：{summary['previous_date']}",
                "",
            ]
        )

    lines.extend(
        [
            f"今日交易：{trade_flow_text(summary['today_trade_cash_flow'])}",
            "",
            f"持仓成本：{money(summary['total_cost'])}",
            f"当前市值：{money(summary['total_value'])}",
            f"累计盈亏：{money(summary['total_pnl'], show_sign=True)}",
            f"累计收益率：{percent(summary['total_return'], show_sign=True)}",
            "",
            "持仓明细：",
            "",
        ]
    )

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