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
CANDLES_LIMIT = 250

RISK_PER_TRADE = 0.02        # 2% of account per trade
MAX_LEVERAGE = 5
MAX_OPEN_POSITIONS = 3
MIN_SIGNAL_SCORE = 4         # out of 5
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 3.0

SCAN_INTERVAL_SECONDS = 300  # scan every 5 minutes
MONITOR_INTERVAL_SECONDS = 30
