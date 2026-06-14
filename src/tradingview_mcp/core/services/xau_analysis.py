from __future__ import annotations

import statistics
from typing import Optional

from .indicators_calc import calc_ema, calc_sma


# ---------------------------------------------------------------------------
# Swing high / low detection
# ---------------------------------------------------------------------------

def find_swings(candles: list[dict], lookback: int = 2,
                max_candles: Optional[int] = None) -> dict:
    """
    Returns the most recent swing high and swing low from a list of candles.

    Swing high: candle[i].high is the highest within ±lookback candles.
    Swing low : candle[i].low  is the lowest  within ±lookback candles.

    Also returns body_high / body_low (wick extremity — uses candle open/close
    to isolate the body from the extreme), enabling Liquidity Swings style
    equilibrium calculation.

    Expects candles in *descending* order (newest first), same as
    fetch_ohlc() returns.

    Parameters:
        candles     : OHLC list (descending)
        lookback    : candles to look on each side (default 2)
        max_candles : if set, only scan the first N newest candles.
                      Prevents EQ from being dominated by year-old extremes.
    """
    if max_candles is not None:
        candles = candles[:max_candles]

    if len(candles) < lookback * 2 + 1:
        return {"high": None, "low": None}

    highs  = [float(c["high"])  for c in candles]
    lows   = [float(c["low"])   for c in candles]

    swing_high = None
    swing_low  = None
    swing_high_idx = None
    swing_low_idx  = None

    for i in range(lookback, len(candles) - lookback):
        segment_h = highs[i - lookback : i + lookback + 1]
        segment_l = lows[i  - lookback : i + lookback + 1]

        if highs[i] == max(segment_h):
            if swing_high is None or highs[i] > swing_high:
                swing_high = highs[i]
                swing_high_idx = i

        if lows[i] == min(segment_l):
            if swing_low is None or lows[i] < swing_low:
                swing_low = lows[i]
                swing_low_idx = i

    result: dict = {"high": swing_high, "low": swing_low}

    if swing_high_idx is not None:
        c = candles[swing_high_idx]
        result["body_high"] = max(float(c["open"]), float(c["close"]))
    if swing_low_idx is not None:
        c = candles[swing_low_idx]
        result["body_low"] = min(float(c["open"]), float(c["close"]))

    return result


# ---------------------------------------------------------------------------
# ICT Equilibrium
# ---------------------------------------------------------------------------

def calc_equilibrium(swing_high: float, swing_low: float,
                     body_high: Optional[float] = None,
                     body_low: Optional[float] = None,
                     mode: str = "extreme") -> tuple[float, str]:
    """
    Compute ICT Equilibrium from a swing range.

    Mode 'extreme': EQ = (high + low) / 2 — full wick range (standard ICT).
    Mode 'body':    EQ = (body_high + body_low) / 2 — body-only (non-standard,
                    retained for reference / comparison).

    Returns (eq_value, mode_used).
    """
    if mode == "body" and body_high is not None and body_low is not None:
        return (body_high + body_low) / 2, "body"
    return (swing_high + swing_low) / 2, "extreme"


def label_premium_discount(price: float, eq: float) -> str:
    """Returns PREMIUM (price > EQ), DISCOUNT (price < EQ), or AT_EQ."""
    if price > eq:
        return "PREMIUM"
    if price < eq:
        return "DISCOUNT"
    return "AT_EQ"


# ---------------------------------------------------------------------------
# Trend detection (from sequence of swing highs/lows)
# ---------------------------------------------------------------------------

def detect_trend(candles: list[dict], lookback: int = 5) -> str:
    """
    Determines trend direction from the most recent N candles.

    Compares the first half vs the second half of the recent window:
      - Higher average highs & higher average lows → BULLISH
      - Lower average highs & lower average lows → BEARISH
      - Otherwise → SIDEWAYS

    Parameters:
        candles  : OHLC list (descending)
        lookback : number of candles to analyse (default 5)
    """
    if len(candles) < lookback + 1:
        return "SIDEWAYS"

    segment = candles[:lookback]
    half = len(segment) // 2

    recent  = segment[:half]
    earlier = segment[half:]

    avg_high_recent  = sum(float(c["high"]) for c in recent)  / max(len(recent), 1)
    avg_low_recent   = sum(float(c["low"])  for c in recent)  / max(len(recent), 1)
    avg_high_earlier = sum(float(c["high"]) for c in earlier) / max(len(earlier), 1)
    avg_low_earlier  = sum(float(c["low"])  for c in earlier) / max(len(earlier), 1)

    if avg_high_recent > avg_high_earlier and avg_low_recent > avg_low_earlier:
        return "BULLISH"
    if avg_high_recent < avg_high_earlier and avg_low_recent < avg_low_earlier:
        return "BEARISH"
    return "SIDEWAYS"


# ---------------------------------------------------------------------------
# EMA 200
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

def calc_atr(candles_desc: list[dict], period: int = 14) -> Optional[float]:
    """
    Returns the latest ATR(period) value from descending OHLC data.
    """
    if len(candles_desc) < period + 1:
        return None

    # Work with ascending order for sequential calculation
    asc = list(reversed(candles_desc))
    tr_values: list[float] = []

    for i, c in enumerate(asc):
        if i == 0:
            tr = float(c["high"]) - float(c["low"])
        else:
            h = float(c["high"])
            l = float(c["low"])
            pc = float(asc[i - 1]["close"])
            tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_values.append(tr)

    # First ATR is SMA of first `period` TRs
    atr = sum(tr_values[:period]) / period
    for i in range(period, len(tr_values)):
        atr = (atr * (period - 1) + tr_values[i]) / period
    return atr


def get_latest_ema_200(candles: list[dict]) -> Optional[float]:
    """
    Calculates EMA 200 from OHLC data.

    Expects candles in *descending* order but calc_ema needs ascending,
    so we reverse internally.
    """
    if len(candles) < 200:
        return None

    closes = [float(c["close"]) for c in reversed(candles)]
    ema_values = calc_ema(closes, 200)
    # Last element in ema_values corresponds to the oldest candle.
    # We want the value for the *newest* candle.
    return ema_values[-1]


# ---------------------------------------------------------------------------
# Pivot points — 5 methods
# ---------------------------------------------------------------------------

def calc_pivot_classic(high: float, low: float, close: float) -> dict:
    P = (high + low + close) / 3
    return {
        "P":  round(P, 2),
        "R1": round(2 * P - low, 2),
        "R2": round(P + (high - low), 2),
        "R3": round(high + 2 * (P - low), 2),
        "S1": round(2 * P - high, 2),
        "S2": round(P - (high - low), 2),
        "S3": round(low - 2 * (high - P), 2),
    }


def calc_pivot_fibonacci(high: float, low: float, close: float) -> dict:
    P = (high + low + close) / 3
    r = high - low
    return {
        "P":  round(P, 2),
        "R1": round(P + 0.382 * r, 2),
        "R2": round(P + 0.618 * r, 2),
        "R3": round(P + 1.000 * r, 2),
        "S1": round(P - 0.382 * r, 2),
        "S2": round(P - 0.618 * r, 2),
        "S3": round(P - 1.000 * r, 2),
    }


def calc_pivot_camarilla(high: float, low: float, close: float) -> dict:
    r = high - low
    return {
        "R1": round(close + r * 1.1 / 12, 2),
        "R2": round(close + r * 1.1 / 6, 2),
        "R3": round(close + r * 1.1 / 4, 2),
        "R4": round(close + r * 1.1 / 2, 2),
        "S1": round(close - r * 1.1 / 12, 2),
        "S2": round(close - r * 1.1 / 6, 2),
        "S3": round(close - r * 1.1 / 4, 2),
        "S4": round(close - r * 1.1 / 2, 2),
    }


def calc_pivot_woodie(high: float, low: float, close: float) -> dict:
    P = (high + low + 2 * close) / 4
    return {
        "P":  round(P, 2),
        "R1": round(2 * P - low, 2),
        "R2": round(P + (high - low), 2),
        "R3": round(high + 2 * (P - low), 2),
        "S1": round(2 * P - high, 2),
        "S2": round(P - (high - low), 2),
        "S3": round(low - 2 * (high - P), 2),
    }


def calc_pivot_demark(open_p: float, high: float, low: float, close: float) -> dict:
    if close < open_p:
        X = high + 2 * low + close
    elif close > open_p:
        X = 2 * high + low + close
    else:
        X = high + low + 2 * close

    return {
        "R1": round(X / 2 - low, 2),
        "S1": round(X / 2 - high, 2),
    }


def calc_all_pivots(high: float, low: float, close: float,
                    open_p: Optional[float] = None) -> dict:
    return {
        "classic":   calc_pivot_classic(high, low, close),
        "fibonacci": calc_pivot_fibonacci(high, low, close),
        "camarilla": calc_pivot_camarilla(high, low, close),
        "woodie":    calc_pivot_woodie(high, low, close),
        "demark":    calc_pivot_demark(open_p or close, high, low, close),
    }


# ---------------------------------------------------------------------------
# Multi-pivot confluence scoring
# ---------------------------------------------------------------------------

def score_pivot_confluence(all_pivots: dict, current_price: float) -> dict:
    """
    Counts how many of the 5 methods agree on a resistance/support zone
    near the current price.

    Returns:
        nearest_resistance: (avg_price, count)  — highest-confluence level above
        nearest_support:    (avg_price, count)  — highest-confluence level below
        score: percentage of methods aligned on the dominant zone
    """
    resistance_levels = []
    support_levels = []

    for method, p in all_pivots.items():
        for key, val in p.items():
            if key.startswith("R") and val > current_price:
                resistance_levels.append((val, method, key))
            elif key.startswith("S") and val < current_price:
                support_levels.append((val, method, key))

    def _find_cluster(levels, reverse=False):
        if not levels:
            return None, 0
        levels_sorted = sorted(levels, key=lambda x: x[0])
        if reverse:
            levels_sorted = levels_sorted[::-1]

        # Simple clustering: find the tightest group of 3+ levels
        best_cluster = None
        best_count = 0
        for i in range(len(levels_sorted)):
            cluster = [levels_sorted[i]]
            for j in range(i + 1, len(levels_sorted)):
                if abs(levels_sorted[j][0] - levels_sorted[i][0]) <= (levels_sorted[i][0] * 0.005):
                    cluster.append(levels_sorted[j])
            if len(cluster) > best_count:
                best_count = len(cluster)
                avg_px = round(statistics.mean(x[0] for x in cluster), 2)
                best_cluster = avg_px

        return best_cluster, best_count

    res_avg, res_cnt = _find_cluster(resistance_levels, reverse=False)
    sup_avg, sup_cnt = _find_cluster(support_levels, reverse=True)

    total = 5
    score = round(max(res_cnt, sup_cnt) / total * 100)

    return {
        "nearest_resistance": res_avg,
        "resistance_count":   res_cnt,
        "nearest_support":    sup_avg,
        "support_count":      sup_cnt,
        "confluence_score":   score,
    }


# ---------------------------------------------------------------------------
# Confluence engine
# ---------------------------------------------------------------------------

def confluence_bias(trend: str, ema_position: str, premium_discount: str) -> str:
    """
    Determines overall bias from 3 primary filters.
    Returns SELL, BUY, or NEUTRAL.
    """
    score = 0

    if trend == "BULLISH":
        score += 1
    elif trend == "BEARISH":
        score -= 1

    if "ABOVE" in ema_position:
        score += 1
    elif "BELOW" in ema_position:
        score -= 1

    if premium_discount == "PREMIUM":
        score -= 1
    elif premium_discount == "DISCOUNT":
        score += 1

    if score >= 2:
        return "BUY"
    if score <= -2:
        return "SELL"
    return "NEUTRAL"


def confluence_score(trend: str, ema_position: str,
                     premium_discount: str, pivot_score: int) -> int:
    """
    Calculates overall confidence percentage (0–100).

    Scoring breakdown (max 90 raw, scaled to 100):
      - Trend clear       : 25  (SIDEWAYS → 10)
      - EMA position clear : 25  (NO_DATA → 10)
      - PD not AT_EQ       : 20
      - Pivot confluence   : 20  (= pivot_score × 0.2)
    """
    pts = 0

    if trend in ("BULLISH", "BEARISH"):
        pts += 25
    else:
        pts += 10

    if "ABOVE" in ema_position or "BELOW" in ema_position:
        pts += 25
    else:
        pts += 10

    if premium_discount != "AT_EQ":
        pts += 20

    pts += int(pivot_score * 0.2)

    # Scale from max 90 → 100
    return min(round(pts / 90 * 100), 100)


# ---------------------------------------------------------------------------
# Confluence status (MTF alignment)
# ---------------------------------------------------------------------------

def calc_confluence_status(daily_trend: str, layer_4h_trend: str,
                           layer_1h_trend: str) -> str:
    """
    ALIGNED  → 3 TF searah
    PULLBACK → 1H beda dari D/4H
    WARNING  → 4H beda dari Daily (struktur konflik)
    """
    if daily_trend == "SIDEWAYS":
        from_daily = layer_4h_trend if layer_4h_trend != "SIDEWAYS" else layer_1h_trend
        if from_daily in ("BULLISH", "BEARISH"):
            return "PULLBACK"
        return "SIDEWAYS"

    if layer_4h_trend != daily_trend:
        return "WARNING"
    if layer_1h_trend != daily_trend:
        return "PULLBACK"
    return "ALIGNED"


# ---------------------------------------------------------------------------
# Master analysis function
# ---------------------------------------------------------------------------

def analyze_xau(ohlc_daily: list[dict], ohlc_4h: list[dict],
                ohlc_1h: list[dict],
                current_price: Optional[float] = None,
                zone_width_mode: str = "atr",
                atr_multiplier: float = 0.2,
                atr_period: int = 14) -> dict:
    """
    Main entry point. Runs the full analysis pipeline and returns a
    structured result dict.

    Parameters:
        ohlc_daily    : Daily candles (descending)
        ohlc_4h       : 4H candles (descending)
        ohlc_1h       : 1H candles (descending)
        current_price : User-provided price for context.
                        If None, uses ohlc_1h[0]["close"] as fallback.

    Returns:
        dict with trend, bias, confidence, pivot zones, etc.
    """
    if current_price is None:
        current_price = float(ohlc_1h[0]["close"]) if ohlc_1h else (
            float(ohlc_daily[0]["close"]) if ohlc_daily else 0
        )
        price_source = "ohlc_1h"
    else:
        price_source = "user"

    # ── Daily layer (direction bias) ───────────────────────────────────────
    daily_swings = find_swings(ohlc_daily, lookback=3, max_candles=30)
    daily_trend  = detect_trend(ohlc_daily, lookback=10)
    daily_ema200 = get_latest_ema_200(ohlc_daily)

    # SMA200
    daily_closes_asc = [float(c["close"]) for c in reversed(ohlc_daily)]
    sma200_all = calc_sma(daily_closes_asc, 200)
    daily_sma200 = sma200_all[-1] if sma200_all else None
    sma_pos = "ABOVE" if (daily_sma200 and current_price > daily_sma200) else \
              "BELOW" if (daily_sma200 and current_price < daily_sma200) else \
              "NO_DATA"

    sw_h  = daily_swings["high"] or float(ohlc_daily[0]["high"])
    sw_l  = daily_swings["low"]  or float(ohlc_daily[0]["low"])
    b_h   = daily_swings.get("body_high", sw_h)
    b_l   = daily_swings.get("body_low", sw_l)
    daily_eq, daily_eq_mode = calc_equilibrium(sw_h, sw_l, b_h, b_l, mode="extreme")

    daily_pd = label_premium_discount(current_price, daily_eq)

    ema_pos = "ABOVE" if (daily_ema200 and current_price > daily_ema200) else \
              "BELOW" if (daily_ema200 and current_price < daily_ema200) else \
              "NO_DATA"

    # ── 4H layer (analytical confirmation + equilibrium) ───────────────────
    layer_4h_swings = find_swings(ohlc_4h, lookback=3, max_candles=30)
    layer_4h_trend  = detect_trend(ohlc_4h, lookback=10)

    sw_4h_h  = layer_4h_swings.get("high") or float(ohlc_4h[0]["high"])
    sw_4h_l  = layer_4h_swings.get("low")  or float(ohlc_4h[0]["low"])
    b_4h_h   = layer_4h_swings.get("body_high", sw_4h_h)
    b_4h_l   = layer_4h_swings.get("body_low", sw_4h_l)
    layer_4h_eq, layer_4h_eq_mode = calc_equilibrium(sw_4h_h, sw_4h_l,
                                                      b_4h_h, b_4h_l,
                                                      mode="extreme")
    layer_4h_pd = label_premium_discount(current_price, layer_4h_eq)

    # ── 1H layer (retrace / context only) ──────────────────────────────────
    layer_1h_trend = detect_trend(ohlc_1h, lookback=10)

    # ── Pivot calculation (from last closed daily candle) ──────────────────
    last = ohlc_daily[1] if len(ohlc_daily) > 1 else ohlc_daily[0]
    LH   = float(last["high"])
    LL   = float(last["low"])
    LC   = float(last["close"])
    LO   = float(last["open"])

    pivots = calc_all_pivots(LH, LL, LC, LO)
    pivot_conf = score_pivot_confluence(pivots, current_price)

    # ── Confluence ─────────────────────────────────────────────────────────
    bias = confluence_bias(daily_trend, ema_pos, daily_pd)
    conf = confluence_score(daily_trend, ema_pos, daily_pd,
                            pivot_conf["confluence_score"])

    confluence_status = calc_confluence_status(daily_trend, layer_4h_trend,
                                               layer_1h_trend)

    # ── Entry zones ────────────────────────────────────────────────────────
    buy_zones  = []
    sell_zones = []

    # Determine half-width for zones
    if zone_width_mode == "atr":
        atr_val = calc_atr(ohlc_daily, atr_period)
        half = atr_val * atr_multiplier if atr_val and atr_val > 0 else current_price * 0.005
    else:
        half = current_price * 0.005

    if pivot_conf["nearest_support"]:
        p = pivot_conf["nearest_support"]
        buy_zones.append({
            "zone": [round(p - half, 2), round(p + half, 2)],
            "source": "pivot_confluence",
            "strength": "HIGH" if pivot_conf["support_count"] >= 4 else
                        "MEDIUM" if pivot_conf["support_count"] >= 3 else "LOW",
            "stop_loss": round(p - 14.00, 2),
            "take_profit": round(p + 42.00, 2),
            "note": "SL=1400pips, TP=4200pips (1:3)",
        })

    if pivot_conf["nearest_resistance"]:
        p = pivot_conf["nearest_resistance"]
        sell_zones.append({
            "zone": [round(p - half, 2), round(p + half, 2)],
            "source": "pivot_confluence",
            "strength": "HIGH" if pivot_conf["resistance_count"] >= 4 else
                        "MEDIUM" if pivot_conf["resistance_count"] >= 3 else "LOW",
            "stop_loss": round(p + 14.00, 2),
            "take_profit": round(p - 42.00, 2),
            "note": "SL=1400pips, TP=4200pips (1:3)",
        })

    if daily_pd == "DISCOUNT" and bias == "BUY":
        eq_zone = round(daily_eq * 0.98, 2), round(daily_eq, 2)
        buy_zones.append({
            "zone": [eq_zone[0], eq_zone[1]],
            "source": "ict_equilibrium",
            "strength": "MEDIUM",
        })
    elif daily_pd == "PREMIUM" and bias == "SELL":
        eq_zone = round(daily_eq, 2), round(daily_eq * 1.02, 2)
        sell_zones.append({
            "zone": [eq_zone[0], eq_zone[1]],
            "source": "ict_equilibrium",
            "strength": "MEDIUM",
        })

    # ── Assemble result ────────────────────────────────────────────────────
    return {
        "current_price": current_price,
        "current_price_source": price_source,
        "bias": bias,
        "confidence": conf,
        "confluence": {
            "status": confluence_status,
            "note": _confluence_note(confluence_status, daily_trend,
                                     layer_4h_trend, layer_1h_trend),
            "daily_trend": daily_trend,
            "layer_4h_trend": layer_4h_trend,
            "layer_1h_trend": layer_1h_trend,
        },
        "daily_layer": {
            "trend": daily_trend,
            "ema_200": round(daily_ema200, 2) if daily_ema200 else None,
            "price_vs_ema": ema_pos,
            "sma_200": round(daily_sma200, 2) if daily_sma200 else None,
            "price_vs_sma": sma_pos,
            "equilibrium": round(daily_eq, 2),
            "equilibrium_mode": daily_eq_mode,
            "premium_discount": daily_pd,
            "swing_high": round(sw_h, 2),
            "swing_low": round(sw_l, 2),
            "swing_high_body": round(b_h, 2),
            "swing_low_body": round(b_l, 2),
            "swing_area_high": [round(b_h, 2), round(sw_h, 2)],   # LuxAlgo Wick Extremity
            "swing_area_low":  [round(sw_l, 2), round(b_l, 2)],   # liquidity zone
        },
        "layer_4h": {
            "trend": layer_4h_trend,
            "equilibrium": round(layer_4h_eq, 2),
            "equilibrium_mode": layer_4h_eq_mode,
            "premium_discount": layer_4h_pd,
            "swing_high": round(sw_4h_h, 2),
            "swing_low": round(sw_4h_l, 2),
            "swing_area_high": [round(b_4h_h, 2), round(sw_4h_h, 2)],
            "swing_area_low":  [round(sw_4h_l, 2), round(b_4h_l, 2)],
        },
        "layer_1h": {
            "trend": layer_1h_trend,
        },
        "pivot_layer": {
            "all_pivots": pivots,
            "confluence_score": pivot_conf["confluence_score"],
            "nearest_resistance": pivot_conf["nearest_resistance"],
            "nearest_support": pivot_conf["nearest_support"],
        },
        "entry_zones": {
            "buy_zones": buy_zones,
            "sell_zones": sell_zones,
        },
    }


def _confluence_note(status: str, daily: str, layer_4h: str,
                     layer_1h: str) -> str:
    notes = {
        "ALIGNED": (
            f"Daily {daily}, 4H {layer_4h}, 1H {layer_1h} — "
            f"all timeframes searah."
        ),
        "PULLBACK": (
            f"Daily {daily}, 4H {layer_4h}, 1H {layer_1h} — "
            f"1H retrace against HTF bias. "
            f"Harga pullback ke EQ atau PD 4H bisa jadi entry."
        ),
        "WARNING": (
            f"Daily {daily}, 4H {layer_4h} — konflik struktur. "
            f"Tunggu konfirmasi 4H searah daily sebelum entry."
        ),
        "SIDEWAYS": "Daily SIDEWAYS. Tidak ada bias strong.",
    }
    return notes.get(status, "")
