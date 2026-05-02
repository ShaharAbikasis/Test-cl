import logging
from dataclasses import dataclass

import pandas as pd

from bot.config import (
    ML_CONFIDENCE_THRESHOLD, ML_SHORT_THRESHOLD, ADX_MIN_STRENGTH
)
from bot.indicators import compute_indicators, get_last_row
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

    adx_val  = float(cur.get("ADX_14", 0) or 0)
    ema200   = float(cur["EMA_200"])
    trend_up = price > ema200
    trending = adx_val >= ADX_MIN_STRENGTH

    # ML prediction
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

    # Entry conditions
    go_long  = prob > ML_CONFIDENCE_THRESHOLD and trend_up  and trending
    go_short = prob < ML_SHORT_THRESHOLD       and not trend_up and trending

    if go_long:
        return SignalResult(symbol, "long",  prob,       factors, price, atr)
    if go_short:
        return SignalResult(symbol, "short", 1.0 - prob, factors, price, atr)
    return SignalResult(symbol, "none", prob, factors, price, atr)
