import time as _time
import ccxt.async_support as ccxt
import httpx
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


_TIME_URL = (
    "https://testnet.binancefuture.com/fapi/v1/time"
    if BINANCE_TESTNET
    else "https://fapi.binance.com/fapi/v1/time"
)


async def sync_time() -> None:
    """Fetch server time via raw HTTP (no ccxt signing) and store the clock offset."""
    async with httpx.AsyncClient(timeout=5) as client:
        before = int(_time.time() * 1000)
        r = await client.get(_TIME_URL)
        after = int(_time.time() * 1000)
    server_ms = r.json()["serverTime"]
    local_mid = (before + after) // 2
    # Write directly into exchange.options so ccxt's sign() picks it up
    exchange.options["timeDifference"] = local_mid - server_ms
    exchange.options["adjustForTimeDifference"] = True


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


async def place_stop_loss(symbol: str, close_side: str, amount: float, sl_price: float) -> dict:
    return await exchange.create_order(
        symbol, "stop_market", close_side, amount,
        params={"stopPrice": round(sl_price, 4), "reduceOnly": True, "workingType": "MARK_PRICE"},
    )


async def place_take_profit(symbol: str, close_side: str, amount: float, tp_price: float) -> dict:
    return await exchange.create_order(
        symbol, "take_profit_market", close_side, amount,
        params={"stopPrice": round(tp_price, 4), "reduceOnly": True, "workingType": "MARK_PRICE"},
    )


async def close_exchange() -> None:
    await exchange.close()
