import asyncio
import json
import logging
from datetime import datetime, timezone

import aiosqlite

from bot import config
from bot.exchange import (
    fetch_ohlcv, fetch_balance, fetch_positions,
    set_leverage, place_order, place_stop_loss, place_take_profit, sync_time
)
from bot.strategy import evaluate_signal
from bot.risk import calculate_trade_params
from bot.ml_model import train_model
from bot import notifications

logger = logging.getLogger(__name__)

DB_PATH = "data/trading.db"

_running = False
_broadcast_callback = None  # set by dashboard to push WS updates


def set_broadcast_callback(cb):
    global _broadcast_callback
    _broadcast_callback = cb


async def _broadcast(event: str, data: dict):
    if _broadcast_callback:
        await _broadcast_callback({"event": event, "data": data})


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, side TEXT,
                entry_price REAL, exit_price REAL,
                size REAL, leverage INTEGER,
                pnl_usdt REAL, pnl_pct REAL,
                status TEXT,
                signal_score INTEGER,
                opened_at TEXT, closed_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, side TEXT,
                score INTEGER, factors TEXT,
                price REAL, acted_on INTEGER,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                balance REAL, timestamp TEXT
            )
        """)
        await db.commit()


async def _save_signal(signal, acted_on: bool) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO signals (symbol, side, score, factors, price, acted_on, created_at) VALUES (?,?,?,?,?,?,?)",
            (signal.symbol, signal.side, signal.score,
             json.dumps(signal.factors), signal.price,
             int(acted_on), datetime.now(timezone.utc).isoformat())
        )
        await db.commit()
        return cur.lastrowid


async def _save_trade_open(symbol, side, entry, size, leverage, score) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO trades
               (symbol, side, entry_price, size, leverage, status, signal_score, opened_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (symbol, side, entry, size, leverage, "open", score,
             datetime.now(timezone.utc).isoformat())
        )
        await db.commit()
        return cur.lastrowid


async def _save_trade_close(trade_id: int, exit_price: float, pnl_usdt: float, pnl_pct: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE trades SET exit_price=?, pnl_usdt=?, pnl_pct=?, status='closed', closed_at=?
               WHERE id=?""",
            (exit_price, pnl_usdt, pnl_pct,
             datetime.now(timezone.utc).isoformat(), trade_id)
        )
        await db.commit()


async def get_open_trade_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM trades WHERE status='open'") as cur:
            rows = await cur.fetchall()
    return [r[0] for r in rows]


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*), SUM(pnl_usdt), SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END) FROM trades WHERE status='closed'"
        ) as cur:
            row = await cur.fetchone()
    total, total_pnl, wins = row
    total = total or 0
    win_rate = round((wins or 0) / total * 100, 1) if total > 0 else 0.0
    return {"total_trades": total, "total_pnl": round(total_pnl or 0, 2), "win_rate": win_rate}


async def get_trades(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_signals(limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["factors"] = json.loads(d["factors"])
        results.append(d)
    return results


async def _scan_symbols():
    try:
        await sync_time()
        balance_data = await fetch_balance()
        balance = balance_data["free"]
        positions = await fetch_positions()
        open_count = len(positions)
        open_symbols = {p["symbol"].replace("/USDT:USDT", "USDT").replace("/", "") for p in positions}

        for symbol in config.SYMBOLS:
            try:
                df = await fetch_ohlcv(symbol)
                signal = evaluate_signal(symbol, df)

                if signal.score > 0:
                    await _broadcast("signal", {
                        "symbol": signal.symbol,
                        "side": signal.side,
                        "score": signal.score,
                        "factors": signal.factors,
                        "price": signal.price,
                    })

                sym_key = symbol.replace("/USDT:USDT", "USDT").replace("/", "")
                already_open = sym_key in open_symbols
                can_trade = (
                    signal.side != "none"
                    and not already_open
                    and open_count < config.MAX_OPEN_POSITIONS
                    and balance > 10
                )

                if not can_trade:
                    if signal.score >= 2:
                        await _save_signal(signal, acted_on=False)
                    continue

                params = calculate_trade_params(balance, signal.price, signal.atr, signal.side)
                await _save_signal(signal, acted_on=True)

                await set_leverage(symbol, params["leverage"])
                order_side = "buy" if signal.side == "long" else "sell"
                close_side = "sell" if order_side == "buy" else "buy"
                order = await place_order(symbol, order_side, params["qty"])
                entry_price = float(order.get("average") or signal.price)
                filled_qty = float(order.get("filled") or params["qty"])

                try:
                    await place_stop_loss(symbol, close_side, filled_qty, params["sl_price"])
                    logger.info("SL placed for %s @ %s", symbol, params["sl_price"])
                except Exception as sl_err:
                    logger.error("SL placement failed for %s: %s", symbol, sl_err)

                try:
                    await place_take_profit(symbol, close_side, filled_qty, params["tp_price"])
                    logger.info("TP placed for %s @ %s", symbol, params["tp_price"])
                except Exception as tp_err:
                    logger.error("TP placement failed for %s: %s", symbol, tp_err)

                trade_id = await _save_trade_open(
                    symbol, signal.side, entry_price,
                    filled_qty, params["leverage"], signal.score
                )
                open_count += 1

                await notifications.notify_signal(symbol, signal.side, signal.score, entry_price)
                await notifications.notify_trade_opened(
                    symbol, signal.side, entry_price,
                    params["sl_price"], params["tp_price"], params["leverage"]
                )

                await _broadcast("trade_opened", {
                    "id": trade_id,
                    "symbol": symbol,
                    "side": signal.side,
                    "entry_price": entry_price,
                    "sl_price": params["sl_price"],
                    "tp_price": params["tp_price"],
                    "leverage": params["leverage"],
                    "score": signal.score,
                })

                logger.info("Trade opened: %s %s @ %s", signal.side, symbol, entry_price)

            except Exception as e:
                logger.error("Error processing %s: %s", symbol, e)

    except Exception as e:
        logger.error("Scan failed: %s", e)
        await notifications.notify_error(str(e))


async def trading_loop():
    global _running
    _running = True
    logger.info("Trading loop started")
    while _running:
        await _scan_symbols()
        await asyncio.sleep(config.SCAN_INTERVAL_SECONDS)


async def retrain_loop():
    """Retrain all ML models every ML_RETRAIN_HOURS hours."""
    await asyncio.sleep(config.ML_RETRAIN_HOURS * 3600)
    while _running:
        logger.info("Retraining ML models...")
        for symbol in config.SYMBOLS:
            try:
                df = await fetch_ohlcv(symbol)
                train_model(symbol, df)
            except Exception as e:
                logger.error("Retrain failed for %s: %s", symbol, e)
        await asyncio.sleep(config.ML_RETRAIN_HOURS * 3600)


async def stop_trading():
    global _running
    _running = False
    logger.info("Trading loop stopped")


def is_running() -> bool:
    return _running
