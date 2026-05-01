import time as _time
import ccxt.async_support as ccxt
import pandas as pd
from bot.config import (
    BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET,
    TIMEFRAME, CANDLES_LIMIT
)


def _build_exchange() -> ccxt.binanceusdm:
    cfg = {
        "apiKey": BINANCE_API_KEY,
        "secret": BINANCE_API_SECRET,
        "adjustForTimeDifference": True,
        "options": {
            "defaultType": "future",
            "recvWindow": 60000,
        },
    }
    if BINANCE_TESTNET:
        cfg["urls"] = {
            "api": {
                "public": "https://testnet.binancefuture.com",
                "private": "https://testnet.binancefuture.com",
            }
        }
    return ccxt.binanceusdm(cfg)


exchange = _build_exchange()


async def sync_time() -> None:
    """Measure the gap between local clock and Binance server clock, then apply it."""
    before = int(_time.time() * 1000)
    server_ms = await exchange.fetch_time()
    after = int(_time.time() * 1000)
    # mid-point of the request window is our best estimate of the actual send time
    local_mid = (before + after) // 2
    exchange.options["timeDifference"] = local_mid - server_ms


async def fetch_ohlcv(symbol: str, timeframe: str = TIMEFRAME, limit: int = CANDLES_LIMIT) -> pd.DataFrame:
    raw = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.set_index("timestamp")
    return df.astype(float)


async def fetch_balance() -> dict:
    bal = await exchange.fetch_balance()
    usdt = bal.get("USDT", {})
    return {
        "total": float(usdt.get("total", 0) or 0),
        "free": float(usdt.get("free", 0) or 0),
        "used": float(usdt.get("used", 0) or 0),
    }


async def fetch_positions() -> list[dict]:
    positions = await exchange.fetch_positions()
    return [
        {
            "symbol": p["symbol"],
            "side": p["side"],
            "size": float(p["contracts"] or 0),
            "entry_price": float(p["entryPrice"] or 0),
            "unrealized_pnl": float(p["unrealizedPnl"] or 0),
            "leverage": int(p["leverage"] or 1),
            "liquidation_price": float(p.get("liquidationPrice") or 0),
            "notional": float(p.get("notional") or 0),
        }
        for p in positions
        if float(p.get("contracts") or 0) > 0
    ]


async def set_leverage(symbol: str, leverage: int) -> None:
    await exchange.set_leverage(leverage, symbol)


async def place_order(symbol: str, side: str, amount: float, price: float | None = None) -> dict:
    order_type = "market" if price is None else "limit"
    return await exchange.create_order(symbol, order_type, side, amount, price)


async def place_sl_tp(symbol: str, side: str, amount: float, sl_price: float, tp_price: float) -> tuple[dict, dict]:
    close_side = "sell" if side == "buy" else "buy"
    sl = await exchange.create_order(
        symbol, "stop_market", close_side, amount,
        params={"stopPrice": sl_price, "reduceOnly": True}
    )
    tp = await exchange.create_order(
        symbol, "take_profit_market", close_side, amount,
        params={"stopPrice": tp_price, "reduceOnly": True}
    )
    return sl, tp


async def close_exchange() -> None:
    await exchange.close()
