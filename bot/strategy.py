import logging
from dataclasses import dataclass

import pandas as pd

from bot import config
from bot.indicators import compute_indicators, get_last_row, get_prev_row
from bot.ml_model import predict_proba_up

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    symbol: str
    side: str          # "long" | "short" | "none"
    score: float       # ML confidence (0.0 – 1.0)
    factors: list[str]
    price: float
    atr: float


def evaluate_signal(symbol: str, df: pd.DataFrame) -> SignalResult:
    df_ind = compute_indicators(df)
    cur = get_last_row(df_ind)

    price = float(cur["close"])
    atr   = float(cur["ATRr_14"])

    rsi14      = float(cur.get("RSI_14", 50) or 50)
    macd_hist  = float(cur.get("MACDh_12_26_9", 0) or 0)
    vol_sma20  = float(cur.get("vol_sma20", 1) or 1)
    volume     = float(cur.get("volume", 0) or 0)
    vol_ratio  = volume / vol_sma20 if vol_sma20 > 0 else 1.0
    prev       = get_prev_row(df_ind)
    macd_prev  = float(prev.get("MACDh_12_26_9", 0) or 0)
    macd_slope = macd_hist - macd_prev

    adx_val  = float(cur.get("ADX_14", 0) or 0)
    ema200   = float(cur["EMA_200"])
    trend_up = price > ema200
    trending = adx_val >= config.active["adx_min_strength"]

    prob = predict_proba_up(symbol, df)
    if prob is None:
        return SignalResult(symbol, "none", 0.0, ["Model not ready"], price, atr)

    pct = round(prob * 100, 1)
    factors: list[str] = [f"ML confidence: {pct}% UP"]

    if trend_up:
        factors.append("Price above EMA200 (bullish trend)")
    else:
        factors.append("Price below EMA200 (bearish trend)")

    factors.append(f"ADX {adx_val:.1f} — {'strong trend' if trending else 'weak trend'}")
    factors.append(f"RSI14 {rsi14:.1f}")
    factors.append(f"Vol ratio {vol_ratio:.2f} — {'ok' if vol_ratio >= 0.8 else 'low volume'}")
    factors.append(f"MACD hist {macd_hist:.5f} slope {macd_slope:.5f}")

    conf_threshold = config.active["ml_confidence_threshold"]
    short_threshold = config.active["ml_short_threshold"]

    go_long  = (prob > conf_threshold  and trend_up     and trending
                and rsi14 <= 75
                and vol_ratio >= 0.8
                and (macd_hist > 0 or macd_slope > 0))
    go_short = (prob < short_threshold and not trend_up and trending
                and rsi14 >= 25
                and vol_ratio >= 0.8
                and (macd_hist < 0 or macd_slope < 0))

    if go_long:
        return SignalResult(symbol, "long",  prob,       factors, price, atr)
    if go_short:
        return SignalResult(symbol, "short", 1.0 - prob, factors, price, atr)
    return SignalResult(symbol, "none", prob, factors, price, atr)
