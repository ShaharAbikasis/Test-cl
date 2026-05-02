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

TIMEFRAME = "4h"
CANDLES_LIMIT = 1000

RISK_PER_TRADE = 0.02
MAX_LEVERAGE = 5
MAX_OPEN_POSITIONS = 3
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 3.0

# ML settings
ML_CONFIDENCE_THRESHOLD = 0.58   # min prob to go long
ML_SHORT_THRESHOLD = 0.42        # max prob to go short (1 - 0.58)
ML_LABEL_HORIZON = 4             # predict price 4 candles ahead
ML_LABEL_PCT = 0.003             # target move: >0.3%
ML_RETRAIN_HOURS = 24
ADX_MIN_STRENGTH = 20            # only trade in trending markets

SCAN_INTERVAL_SECONDS = 300
MONITOR_INTERVAL_SECONDS = 30
