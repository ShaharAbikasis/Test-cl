import pandas as pd
import pandas_ta as ta


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.ta.ema(length=9, append=True)
    df.ta.ema(length=21, append=True)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.rsi(length=7, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.atr(length=14, append=True)
    df.ta.adx(length=14, append=True)
    df.ta.bbands(length=20, std=2, append=True)
    df.ta.stoch(k=14, d=3, append=True)
    df.ta.roc(length=10, append=True)
    df.ta.roc(length=20, append=True)
    df["vol_sma20"] = df["volume"].rolling(20).mean()
    return df.dropna()


def get_last_row(df: pd.DataFrame) -> pd.Series:
    return df.iloc[-1]


def get_prev_row(df: pd.DataFrame) -> pd.Series:
    return df.iloc[-2]
