import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from bot import config, trader
from bot.exchange import fetch_balance, fetch_positions

logger = logging.getLogger(__name__)

app = FastAPI(title="Crypto Trading Bot")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)


manager = ConnectionManager()


async def _broadcast_handler(data: dict):
    await manager.broadcast(data)


@app.on_event("startup")
async def startup():
    await trader.init_db()
    trader.set_broadcast_callback(_broadcast_handler)


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
async def get_status():
    try:
        balance = await fetch_balance()
    except Exception:
        balance = {"total": 0, "free": 0, "used": 0}
    stats = await trader.get_stats()
    return {
        "running": trader.is_running(),
        "balance": balance,
        "stats": stats,
        "symbols": config.SYMBOLS,
        "config": {
            "risk_per_trade": config.RISK_PER_TRADE,
            "max_leverage": config.MAX_LEVERAGE,
            "max_open_positions": config.MAX_OPEN_POSITIONS,
            "min_signal_score": config.MIN_SIGNAL_SCORE,
            "timeframe": config.TIMEFRAME,
        },
    }


@app.get("/api/positions")
async def get_positions():
    try:
        return await fetch_positions()
    except Exception as e:
        logger.warning("fetch_positions failed: %s", e)
        return []


@app.get("/api/trades")
async def get_trades(limit: int = 50):
    return await trader.get_trades(limit)


@app.get("/api/signals")
async def get_signals(limit: int = 20):
    return await trader.get_signals(limit)


@app.post("/api/bot/start")
async def start_bot():
    if not trader.is_running():
        asyncio.create_task(trader.trading_loop())
        return {"status": "started"}
    return {"status": "already_running"}


@app.post("/api/bot/stop")
async def stop_bot():
    await trader.stop_trading()
    return {"status": "stopped"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            try:
                positions = await fetch_positions()
                balance = await fetch_balance()
            except Exception:
                positions = []
                balance = {"total": 0, "free": 0, "used": 0}

            await manager.broadcast({
                "event": "tick",
                "data": {"positions": positions, "balance": balance},
            })
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logger.warning("WS error: %s", e)
        try:
            manager.disconnect(ws)
        except ValueError:
            pass
