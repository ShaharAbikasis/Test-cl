import time as _time
import ccxt.async_support as ccxt
import httpx
import pandas as pd
from bot.config import BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET


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
    exchange.options["timeDifference"] = local_mid - server_ms
    exchange.options["adjustForTimeDifference"] = True


async def fetch_ohlcv(
    symbol: str,
    timeframe: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    from bot import config
    tf = timeframe or config.active["timeframe"]
    lim = limit or config.active["candles_limit"]
    raw = await exchange.fetch_ohlcv(symbol, timeframe=tf, limit=lim)
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


async def load_markets() -> None:
    """Load market metadata (tick sizes, lot sizes). Must be called once at startup."""
    await exchange.load_markets()


async def place_order(symbol: str, side: str, amount: float, price: float | None = None) -> dict:
    order_type = "market" if price is None else "limit"
    precise_qty = float(exchange.amount_to_precision(symbol, amount))
    return await exchange.create_order(symbol, order_type, side, precise_qty, price)


async def place_stop_loss(symbol: str, close_side: str, sl_price: float) -> dict:
    """Place a STOP_MARKET order with closePosition=true (closes entire position)."""
    precise_price = float(exchange.price_to_precision(symbol, sl_price))
    order = await exchange.create_order(
        symbol, "stop_market", close_side, 0,
        params={
            "stopPrice": precise_price,
            "closePosition": "true",
            "workingType": "MARK_PRICE",
        },
    )
    return order


async def place_take_profit(symbol: str, close_side: str, tp_price: float) -> dict:
    """Place a TAKE_PROFIT_MARKET order with closePosition=true (closes entire position)."""
    precise_price = float(exchange.price_to_precision(symbol, tp_price))
    order = await exchange.create_order(
        symbol, "take_profit_market", close_side, 0,
        params={
            "stopPrice": precise_price,
            "closePosition": "true",
            "workingType": "MARK_PRICE",
        },
    )
    return order


async def close_exchange() -> None:
    await exchange.close()
