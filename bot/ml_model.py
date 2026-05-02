import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

from bot import config
from bot.indicators import compute_indicators

logger = logging.getLogger(__name__)

MODEL_DIR = Path("data")
MODEL_DIR.mkdir(exist_ok=True)


def _clean(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", symbol)


def _model_path(symbol: str, timeframe: str) -> Path:
    return MODEL_DIR / f"model_{_clean(symbol)}_{timeframe}.pkl"


def _timestamp_path(symbol: str, timeframe: str) -> Path:
    return MODEL_DIR / f"model_{_clean(symbol)}_{timeframe}_trained_at.txt"


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    d = pd.DataFrame(index=df.index)

    close = df["close"]

    # Price returns
    for n in [1, 3, 6, 12]:
        d[f"ret_{n}"] = np.log(close / close.shift(n))

    # EMA ratios
    d["close_ema9"]   = close / df["EMA_9"] - 1
    d["close_ema21"]  = close / df["EMA_21"] - 1
    d["close_ema50"]  = close / df["EMA_50"] - 1
    d["close_ema200"] = close / df["EMA_200"] - 1
    d["ema9_ema21"]   = df["EMA_9"] / df["EMA_21"] - 1
    d["ema9_ema50"]   = df["EMA_9"] / df["EMA_50"] - 1

    # EMA slope (3-candle)
    d["ema9_slope"] = (df["EMA_9"] - df["EMA_9"].shift(3)) / df["EMA_9"]

    # Momentum
    d["rsi14"] = df["RSI_14"] / 100
    d["rsi7"]  = df["RSI_7"] / 100
    d["macd_hist"] = df["MACDh_12_26_9"]
    d["macd_hist_slope"] = d["macd_hist"] - d["macd_hist"].shift(1)

    # Stochastic — pandas_ta column names
    stoch_cols = [c for c in df.columns if c.startswith("STOCHk")]
    if stoch_cols:
        d["stoch_k"] = df[stoch_cols[0]] / 100

    # ROC
    d["roc10"] = df.get("ROC_10", pd.Series(0, index=df.index))
    d["roc20"] = df.get("ROC_20", pd.Series(0, index=df.index))

    # Volatility
    d["atr_ratio"] = df["ATRr_14"] / close

    # Bollinger Bands — pandas_ta: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
    bbl = df.get("BBL_20_2.0")
    bbu = df.get("BBU_20_2.0")
    if bbl is not None and bbu is not None:
        bb_range = (bbu - bbl).replace(0, np.nan)
        d["bb_position"] = (close - bbl) / bb_range
        d["bb_width"]    = (bbu - bbl) / close

    # Volume
    d["vol_ratio"] = df["volume"] / df["vol_sma20"]

    # Trend strength
    d["adx14"] = df.get("ADX_14", pd.Series(0, index=df.index)) / 100

    return d.dropna()


def build_labels(df: pd.DataFrame) -> pd.Series:
    horizon = config.active["ml_label_horizon"]
    pct = config.active["ml_label_pct"]
    future_close = df["close"].shift(-horizon)
    return (future_close > df["close"] * (1 + pct)).astype(int)


def train_model(symbol: str, df: pd.DataFrame, timeframe: str | None = None) -> LGBMClassifier | None:
    tf = timeframe or config.active["timeframe"]
    horizon = config.active["ml_label_horizon"]
    try:
        df_ind = compute_indicators(df)
        X = build_features(df_ind)
        y = build_labels(df_ind).reindex(X.index).dropna()
        X = X.loc[y.index].iloc[:-horizon]
        y = y.iloc[:-horizon]

        if len(X) < 100:
            logger.warning("Not enough data to train model for %s (%d rows)", symbol, len(X))
            return None

        split = int(len(X) * 0.8)
        X_train, X_val = X.iloc[:split], X.iloc[split:]
        y_train, y_val = y.iloc[:split], y.iloc[split:]

        model = LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_samples=20,
            verbose=-1,
        )
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[],
        )

        from sklearn.metrics import roc_auc_score
        prob = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, prob)
        logger.info("Model trained for %s [%s] — AUC: %.3f  samples: %d", symbol, tf, auc, len(X_train))

        joblib.dump(model, _model_path(symbol, tf))
        _timestamp_path(symbol, tf).write_text(datetime.now(timezone.utc).isoformat())
        return model

    except Exception as e:
        logger.error("Training failed for %s [%s]: %s", symbol, tf, e)
        return None


def _is_stale(symbol: str, timeframe: str) -> bool:
    ts_file = _timestamp_path(symbol, timeframe)
    if not ts_file.exists():
        return True
    trained_at = datetime.fromisoformat(ts_file.read_text().strip())
    if trained_at.tzinfo is None:
        trained_at = trained_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - trained_at > timedelta(hours=config.ML_RETRAIN_HOURS)


def load_model(symbol: str, timeframe: str | None = None) -> LGBMClassifier | None:
    tf = timeframe or config.active["timeframe"]
    path = _model_path(symbol, tf)
    if not path.exists():
        return None
    if _is_stale(symbol, tf):
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


def predict_proba_up(symbol: str, df: pd.DataFrame, timeframe: str | None = None) -> float | None:
    """Return probability that price goes UP in the next N candles, or None if unavailable."""
    tf = timeframe or config.active["timeframe"]
    model = load_model(symbol, tf)
    if model is None:
        model = train_model(symbol, df, tf)
    if model is None:
        return None

    try:
        df_ind = compute_indicators(df)
        X = build_features(df_ind)
        if X.empty:
            return None
        last = X.iloc[[-1]]
        prob = float(model.predict_proba(last)[0][1])
        return prob
    except Exception as e:
        logger.error("Prediction failed for %s [%s]: %s", symbol, tf, e)
        return None
