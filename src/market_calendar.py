from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from pandas.errors import EmptyDataError


TIMEZONE = ZoneInfo("Asia/Shanghai")
CALENDAR_FILE = Path("data/trade_calendar.csv")


def get_today_shanghai_date() -> str:
    return datetime.now(TIMEZONE).date().isoformat()


def load_cached_calendar(path: Path = CALENDAR_FILE) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    if path.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(path, dtype={"date": str})
    except EmptyDataError:
        return pd.DataFrame()


def save_cached_calendar(df: pd.DataFrame, path: Path = CALENDAR_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)

    df = df.copy()
    df = df.drop_duplicates(subset=["date"], keep="last")
    df = df.sort_values("date")

    df.to_csv(path, index=False)


def build_exchange_calendar_for_year(year: int) -> pd.DataFrame:
    """
    使用 exchange_calendars 生成指定年份的 A 股交易日历。
    XSHG = Shanghai Stock Exchange。
    """
    import exchange_calendars as xcals

    calendar = xcals.get_calendar("XSHG")

    start = f"{year}-01-01"
    end = f"{year}-12-31"

    schedule = calendar.schedule.loc[start:end]
    open_dates = set(schedule.index.strftime("%Y-%m-%d"))

    all_days = pd.date_range(start=start, end=end, freq="D")

    rows = []

    for day in all_days:
        day_str = day.strftime("%Y-%m-%d")
        is_open = 1 if day_str in open_dates else 0

        rows.append(
            {
                "date": day_str,
                "is_open": is_open,
                "source": "exchange_calendars",
            }
        )

    return pd.DataFrame(rows)


def ensure_calendar_for_year(year: int) -> pd.DataFrame:
    cached = load_cached_calendar()

    if not cached.empty and "date" in cached.columns:
        cached_years = set(cached["date"].astype(str).str[:4].astype(int))

        if year in cached_years:
            return cached

    new_calendar = build_exchange_calendar_for_year(year)

    if cached.empty:
        combined = new_calendar
    else:
        combined = pd.concat([cached, new_calendar], ignore_index=True)

    save_cached_calendar(combined)

    return combined


def is_a_share_trading_day(day: str | None = None) -> tuple[bool, str]:
    """
    判断某天是否为 A 股交易日。

    返回：
    (True, "交易日")
    (False, "交易日历休市")
    """
    if day is None:
        day = get_today_shanghai_date()

    current_date = date.fromisoformat(day)

    calendar_df = ensure_calendar_for_year(current_date.year)

    matched = calendar_df[calendar_df["date"] == day]

    if matched.empty:
        raise RuntimeError(f"交易日历中找不到日期：{day}")

    is_open = int(matched.iloc[0]["is_open"])

    if is_open == 1:
        return True, "交易日"

    return False, "交易日历休市"