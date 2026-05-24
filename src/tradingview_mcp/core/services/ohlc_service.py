from __future__ import annotations

import os, time, requests
from datetime import datetime, date, timedelta, timezone

os.environ["TZ"] = "UTC"
time.tzset()

today = date.today()
monday = today - timedelta(days=today.weekday())
friday = monday + timedelta(days=5)

all_time = {'current': today, 'start': monday, 'end': friday}

import requests

def is_weekday(date_str: str) -> bool:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).weekday() < 5
        except ValueError:
            continue
    raise ValueError(f"Format tidak dikenali: {date_str}")

def get_previous_closed_candle(ohlc_data: list[dict], tf_minutes: int) -> dict:
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

def fetch_ohlc(timeframe: str):
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

def calculate_pivot(ohlc_data: list[dict], tf_label: str, tf_minutes: int) -> dict:
    """
    ohlc_data: list of candles, descending (newest first)
    tf_label: label untuk output ("daily", "4h", "1h")
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
    ohlc: {"daily": [...], "4h": [...], "1h": [...]}
    """
    return {
        "daily": calculate_pivot(ohlc["daily"], "daily", 1440),
        "4h":    calculate_pivot(ohlc["4h"], "4h", 240),
        "1h":    calculate_pivot(ohlc["1h"], "1h", 60),
    }

def get_pivots():
    ohlc = {
        "daily": fetch_ohlc("1day"),
        "4h":    fetch_ohlc("4h"),
        "1h":    fetch_ohlc("1h"),
    }
    return calculate_all_pivots(ohlc)