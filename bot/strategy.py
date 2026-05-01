from dataclasses import dataclass, field
import pandas as pd
from bot.indicators import compute_indicators, get_last_row, get_prev_row


@dataclass
class SignalResult:
    symbol: str
    side: str          # "long" | "short" | "none"
    score: int
    factors: list[str]
    price: float
    atr: float


def _crossover(a_now, a_prev, b_now, b_prev) -> bool:
    return a_prev < b_prev and a_now > b_now


def _crossunder(a_now, a_prev, b_now, b_prev) -> bool:
    return a_prev > b_prev and a_now < b_now


def evaluate_signal(symbol: str, df: pd.DataFrame) -> SignalResult:
    df = compute_indicators(df)
    cur = get_last_row(df)
    prv = get_prev_row(df)

    close = cur["close"]
    ema9, ema21 = cur["EMA_9"], cur["EMA_21"]
    ema200 = cur["EMA_200"]
    rsi = cur["RSI_14"]
    macd = cur["MACD_12_26_9"]
    macd_sig = cur["MACDs_12_26_9"]
    atr = cur["ATRr_14"]
    volume = cur["volume"]
    vol_sma = cur["vol_sma20"]

    p_ema9, p_ema21 = prv["EMA_9"], prv["EMA_21"]
    p_macd, p_macd_sig = prv["MACD_12_26_9"], prv["MACDs_12_26_9"]

    long_factors: list[str] = []
    short_factors: list[str] = []

    # Factor 1: EMA200 trend
    if close > ema200:
        long_factors.append("Price above EMA200 (bullish trend)")
    else:
        short_factors.append("Price below EMA200 (bearish trend)")

    # Factor 2: EMA9/21 crossover
    if _crossover(ema9, p_ema9, ema21, p_ema21):
        long_factors.append("EMA9 crossed above EMA21")
    elif _crossunder(ema9, p_ema9, ema21, p_ema21):
        short_factors.append("EMA9 crossed below EMA21")

    # Factor 3: RSI momentum
    if rsi > 55:
        long_factors.append(f"RSI {rsi:.1f} > 55 (bullish momentum)")
    elif rsi < 45:
        short_factors.append(f"RSI {rsi:.1f} < 45 (bearish momentum)")

    # Factor 4: MACD crossover
    if _crossover(macd, p_macd, macd_sig, p_macd_sig):
        long_factors.append("MACD crossed above signal line")
    elif _crossunder(macd, p_macd, macd_sig, p_macd_sig):
        short_factors.append("MACD crossed below signal line")

    # Factor 5: Volume surge
    if volume > vol_sma * 1.5:
        surge_label = f"Volume surge {volume/vol_sma:.1f}x average"
        long_factors.append(surge_label)
        short_factors.append(surge_label)

    long_score = len(long_factors)
    short_score = len(short_factors)

    if long_score >= short_score and long_score > 0:
        return SignalResult(symbol, "long", long_score, long_factors, close, atr)
    elif short_score > long_score:
        return SignalResult(symbol, "short", short_score, short_factors, close, atr)
    return SignalResult(symbol, "none", 0, [], close, atr)
