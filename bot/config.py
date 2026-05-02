import os
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))

SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "BNB/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "DOT/USDT:USDT",
    "LINK/USDT:USDT",
    "POL/USDT:USDT",
]

# Portfolio-level constants (same across all modes)
RISK_PER_TRADE = 0.02
MAX_LEVERAGE = 5
MAX_OPEN_POSITIONS = 3
ML_RETRAIN_HOURS = 24
MONITOR_INTERVAL_SECONDS = 30

# Per-mode parameters: timeframe, ML thresholds, ATR multipliers, scan speed
TRADING_MODES: dict[str, dict] = {
    "swing_4h": {
        "label": "Swing 4H",
        "timeframe": "4h",
        "candles_limit": 1000,
        "scan_interval": 300,
        "ml_label_horizon": 4,
        "ml_label_pct": 0.003,
        "atr_sl_multiplier": 1.5,
        "atr_tp_multiplier": 3.0,
        "adx_min_strength": 20,
        "ml_confidence_threshold": 0.58,
        "ml_short_threshold": 0.42,
    },
    "swing_1h": {
        "label": "Swing 1H",
        "timeframe": "1h",
        "candles_limit": 1000,
        "scan_interval": 120,
        "ml_label_horizon": 4,
        "ml_label_pct": 0.002,
        "atr_sl_multiplier": 1.2,
        "atr_tp_multiplier": 2.5,
        "adx_min_strength": 22,
        "ml_confidence_threshold": 0.59,
        "ml_short_threshold": 0.41,
    },
    "scalp_15m": {
        "label": "Scalp 15m",
        "timeframe": "15m",
        "candles_limit": 1000,
        "scan_interval": 60,
        "ml_label_horizon": 4,
        "ml_label_pct": 0.001,
        "atr_sl_multiplier": 1.0,
        "atr_tp_multiplier": 2.0,
        "adx_min_strength": 25,
        "ml_confidence_threshold": 0.60,
        "ml_short_threshold": 0.40,
    },
}

CURRENT_MODE: str = os.getenv("TRADING_MODE", "swing_4h")
active: dict = TRADING_MODES[CURRENT_MODE].copy()


def set_mode(name: str) -> None:
    """Switch the active trading mode at runtime. New parameters take effect immediately."""
    global CURRENT_MODE, active
    if name not in TRADING_MODES:
        raise ValueError(f"Unknown trading mode '{name}'. Choose from: {list(TRADING_MODES)}")
    CURRENT_MODE = name
    active = TRADING_MODES[name].copy()
