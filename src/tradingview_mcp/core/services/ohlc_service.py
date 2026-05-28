from __future__ import annotations

import os, time, requests
from datetime import datetime, date, timedelta, timezone

os.environ["TZ"] = "UTC"
time.tzset()

today = date.today()
monday = today - timedelta(days=today.weekday())
friday = monday + timedelta(days=5)

all_time = {'current': today, 'start': monday, 'end': friday}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def is_weekday(date_str: str) -> bool:
    """
    Returns True if the given date string falls on a weekday (Monday to Friday).
    Supports two formats: "YYYY-MM-DD HH:MM:SS" and "YYYY-MM-DD".

    Parameters:
        date_str : date string to evaluate

    Raises:
        ValueError if the format is not recognised.
    """
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).weekday() < 5
        except ValueError:
            continue
    raise ValueError(f"Format tidak dikenali: {date_str}")


def get_previous_closed_candle(ohlc_data: list[dict], tf_minutes: int) -> dict:
    """
    Returns the most recently fully closed candle from a descending OHLC list.

    Compares the close time of the first candle (ohlc_data[0]) against the
    current UTC time. If the candle has closed, returns it. Otherwise returns
    the second candle (ohlc_data[1]).

    Parameters:
        ohlc_data  : list of candles, descending order (newest first)
        tf_minutes : candle duration in minutes (e.g. 1440 for Daily, 240 for 4H)

    Returns:
        dict — the most recently closed candle
    """
    now_utc = datetime.now(timezone.utc)

    dt_str = ohlc_data[0]["datetime"]

    if len(dt_str) == 10:  # Daily: "2026-05-22"
        candle_open = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:  # 4H/1H: "2026-05-22 23:00:00"
        candle_open = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    candle_close = candle_open + timedelta(minutes=tf_minutes)

    if now_utc >= candle_close:
        return ohlc_data[0]
    else:
        return ohlc_data[1]


def get_last_closed_candle_time(now_utc: datetime, tf_minutes: int) -> datetime:
    """
    Returns the open time of the most recently closed candle for a given timeframe.

    Calculated by subtracting the elapsed seconds within the current candle period
    from the current UTC time. Used as end_date in API queries to exclude the
    currently open (partial) candle.

    Parameters:
        now_utc    : current UTC datetime
        tf_minutes : candle duration in minutes (e.g. 15 for M15, 5 for M5)

    Returns:
        datetime — UTC datetime of the last fully closed candle's open time
    """
    elapsed = int(now_utc.timestamp()) % (tf_minutes * 60)
    return now_utc - timedelta(seconds=elapsed)


# ---------------------------------------------------------------------------
# OHLC fetch
# ---------------------------------------------------------------------------

def fetch_ohlc(timeframe: str) -> list[dict]:
    """
    Fetches OHLC candles from Twelve Data for a given timeframe.
    Returns up to 300 candles in descending order (newest first).
    Weekend candles are excluded.

    Parameters:
        timeframe : Twelve Data interval string (e.g. "1day", "4h", "1h")

    Returns:
        list of dict — weekday-only candles, descending (newest first)
    """
    url = 'https://api.twelvedata.com/time_series'
    query_params = {
        'symbol': 'XAU/USD',
        'interval': timeframe,
        'outputsize': 300,
        'apikey': 'fddf27722a3c42c8873eabd35b1e3f59',
        'timezone': 'UTC'
    }

    response = requests.get(url, params=query_params)
    response.raise_for_status()
    data = response.json()
    cleaned_values = []

    for val in data.get('values'):
        if not is_weekday(val.get('datetime')):
            continue
        cleaned_values.append(val)

    return cleaned_values


# ---------------------------------------------------------------------------
# Pivot points
# ---------------------------------------------------------------------------

def calculate_pivot(ohlc_data: list[dict], tf_label: str, tf_minutes: int) -> dict:
    """
    Calculates Classic and Fibonacci pivot points from the most recently
    closed candle of the given timeframe.

    Parameters:
        ohlc_data  : list of candles, descending (newest first)
        tf_label   : label for output ("daily", "4h", "1h")
        tf_minutes : candle duration in minutes, used to determine closed candle

    Returns:
        dict with keys: tf, based_on, classic, fibonacci
    """
    prev = get_previous_closed_candle(ohlc_data, tf_minutes)

    H = float(prev["high"])
    L = float(prev["low"])
    C = float(prev["close"])

    P = (H + L + C) / 3
    range_ = H - L

    classic = {
        "P":  round(P, 3),
        "R1": round((2 * P) - L, 3),
        "R2": round(P + range_, 3),
        "R3": round(H + 2 * (P - L), 3),
        "S1": round((2 * P) - H, 3),
        "S2": round(P - range_, 3),
        "S3": round(L - 2 * (H - P), 3),
    }

    fibonacci = {
        "P":  round(P, 3),
        "R1": round(P + 0.382 * range_, 3),
        "R2": round(P + 0.618 * range_, 3),
        "R3": round(P + 1.000 * range_, 3),
        "S1": round(P - 0.382 * range_, 3),
        "S2": round(P - 0.618 * range_, 3),
        "S3": round(P - 1.000 * range_, 3),
    }

    return {
        "tf": tf_label,
        "based_on": prev["datetime"],
        "classic": classic,
        "fibonacci": fibonacci,
    }


def calculate_all_pivots(ohlc: dict) -> dict:
    """
    Calculates pivot points for Daily, 4H, and 1H timeframes.

    Parameters:
        ohlc : dict with keys "daily", "4h", "1h", each containing a
               descending list of OHLC candles

    Returns:
        dict with keys "daily", "4h", "1h", each containing pivot data
    """
    return {
        "daily": calculate_pivot(ohlc["daily"], "daily", 1440),
        "4h":    calculate_pivot(ohlc["4h"], "4h", 240),
        "1h":    calculate_pivot(ohlc["1h"], "1h", 60),
    }


def get_pivots() -> dict:
    """
    Fetches OHLC data for Daily, 4H, and 1H timeframes and calculates
    Classic and Fibonacci pivot points for each.

    Returns:
        dict with keys "daily", "4h", "1h", each containing pivot data
    """
    ohlc = {
        "daily": fetch_ohlc("1day"),
        "4h":    fetch_ohlc("4h"),
        "1h":    fetch_ohlc("1h"),
    }
    return calculate_all_pivots(ohlc)


# ---------------------------------------------------------------------------
# Session OHLC
# ---------------------------------------------------------------------------

def is_market_session_valid() -> bool:
    """
    Returns True if the current UTC time falls within a valid XAUUSD trading window.

    Invalid conditions (returns False):
    - Saturday (weekday 5): market closed all day
    - Sunday (weekday 6): market closed all day
    - Monday (weekday 0) before 23:00 UTC: Monday Asia session has not yet opened;
      window start would be Sunday 23:00 UTC which is still market-closed time

    Valid conditions (returns True):
    - Monday >= 23:00 UTC through Friday (standard forex market hours)
    """
    now_utc = datetime.now(timezone.utc)
    weekday = now_utc.weekday()  # 0=Monday, 5=Saturday, 6=Sunday

    if weekday in (5, 6):
        return False

    if weekday == 0:
        asia_open_monday = now_utc.replace(hour=23, minute=0, second=0, microsecond=0)
        if now_utc < asia_open_monday:
            return False

    return True


def get_window_start() -> datetime:
    """
    Returns the start of the OHLC fetch window based on the current UTC weekday.

    Rules:
    - Monday  : start = Sunday 23:00 UTC (Asia open of the current week)
    - Tuesday : start = Sunday 23:00 UTC (same as Monday — Sunday 23:00 UTC is the weekly open)
    - Wednesday: start = Monday 23:00 UTC (~48 hours back)
    - Thursday : start = Tuesday 23:00 UTC (~48 hours back)
    - Friday   : start = Wednesday 23:00 UTC (~48 hours back)

    "2 weekdays back" skips weekend days — for Mon/Tue this always lands on Sunday,
    so the anchor is pinned to Sunday 23:00 UTC (start of the trading week).

    Returns:
        datetime — timezone-aware UTC datetime at 23:00:00
    """
    now_utc = datetime.now(timezone.utc)
    weekday = now_utc.weekday()  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri

    if weekday in (0, 1):
        # Monday or Tuesday — anchor to Sunday 23:00 UTC (start of trading week)
        days_since_sunday = weekday + 1
        sunday = now_utc - timedelta(days=days_since_sunday)
        return sunday.replace(hour=23, minute=0, second=0, microsecond=0)
    else:
        # Wednesday, Thursday, Friday — go back 2 weekdays
        # Wed -> Mon, Thu -> Tue, Fri -> Wed
        two_weekdays_back = now_utc - timedelta(days=2)
        return two_weekdays_back.replace(hour=23, minute=0, second=0, microsecond=0)


def fetch_ohlc_session(timeframe: str, tf_minutes: int) -> list[dict]:
    """
    Fetches OHLC candles from the window start (get_window_start()) up to
    the most recently closed candle, using Twelve Data time_series endpoint.

    Time range filtering is handled server-side via start_date and end_date
    query parameters, avoiding manual post-fetch filtering. Only weekday
    candles are returned — weekend entries are excluded.

    Parameters:
        timeframe  : Twelve Data interval string (e.g. "15min", "5min")
        tf_minutes : candle duration in minutes, used to calculate end_date
                     by excluding the currently open partial candle

    Returns:
        list of dict — OHLC candles in ascending order (oldest first),
        each with keys: datetime, open, high, low, close
    """
    now_utc = datetime.now(timezone.utc)
    start_dt = get_window_start()
    end_dt = get_last_closed_candle_time(now_utc, tf_minutes)

    url = "https://api.twelvedata.com/time_series"
    query_params = {
        "symbol":     "XAU/USD",
        "interval":   timeframe,
        "start_date": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "end_date":   end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "order":      "ASC",
        "apikey":     "fddf27722a3c42c8873eabd35b1e3f59",
        "timezone":   "UTC",
    }

    response = requests.get(url, params=query_params)
    response.raise_for_status()
    data = response.json()

    return [
        val for val in data.get("values", [])
        if is_weekday(val.get("datetime"))
    ]


def get_session_ohlc() -> dict | None:
    """
    Returns M15 and M5 OHLC candles from the window start up to the most
    recently closed candle at the time of the call.

    Window start is determined by get_window_start():
    - Monday / Tuesday : Sunday 23:00 UTC (start of trading week)
    - Wednesday        : Monday 23:00 UTC (~48 hours back)
    - Thursday         : Tuesday 23:00 UTC (~48 hours back)
    - Friday           : Wednesday 23:00 UTC (~48 hours back)

    Returns None if called outside valid market hours (weekend or Monday
    before 23:00 UTC). Callers must handle the None case before processing
    the result.

    The window_start and fetched_at fields are included for traceability —
    they document the exact time window used for this fetch.

    Returns:
        None if market session is not valid, otherwise:
        {
            "window_start" : str  — window start, format "YYYY-MM-DD HH:MM:SS UTC"
            "fetched_at"   : str  — time of this call, format "YYYY-MM-DD HH:MM:SS UTC"
            "m15"          : list[dict] — M15 candles, ascending (oldest first)
            "m5"           : list[dict] — M5 candles, ascending (oldest first)
        }
    """
    if not is_market_session_valid():
        return None

    now_utc = datetime.now(timezone.utc)

    return {
        "window_start": get_window_start().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "fetched_at":   now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "m15":          fetch_ohlc_session("15min", 15),
        "m5":           fetch_ohlc_session("5min",  5),
    }