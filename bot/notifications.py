import logging
from bot.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

_app = None


async def _get_app():
    global _app
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return None
    if _app is None:
        from telegram.ext import ApplicationBuilder
        _app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        await _app.initialize()
    return _app


async def send(message: str) -> None:
    try:
        app = await _get_app()
        if app is None:
            return
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="HTML")
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


async def notify_signal(symbol: str, side: str, score: int, price: float) -> None:
    emoji = "🟢" if side == "long" else "🔴"
    sym = symbol.replace("/USDT:USDT", "")
    await send(f"{emoji} <b>SIGNAL: {sym} {side.upper()}</b>\nScore: {score}/5 | Price: ${price:,.4f}")


async def notify_trade_opened(symbol: str, side: str, entry: float, sl: float, tp: float, leverage: int) -> None:
    emoji = "✅"
    sym = symbol.replace("/USDT:USDT", "")
    await send(
        f"{emoji} <b>TRADE OPENED: {sym} {side.upper()}</b>\n"
        f"Entry: ${entry:,.4f} | Leverage: {leverage}x\n"
        f"SL: ${sl:,.4f} | TP: ${tp:,.4f}"
    )


async def notify_trade_closed(symbol: str, side: str, pnl_usdt: float, pnl_pct: float) -> None:
    if pnl_usdt >= 0:
        emoji = "💰"
        label = "PROFIT"
    else:
        emoji = "❌"
        label = "LOSS"
    sym = symbol.replace("/USDT:USDT", "")
    sign = "+" if pnl_usdt >= 0 else ""
    await send(
        f"{emoji} <b>{label}: {sym} {side.upper()}</b>\n"
        f"PnL: {sign}${pnl_usdt:.2f} ({sign}{pnl_pct:.2f}%)"
    )


async def notify_error(message: str) -> None:
    await send(f"⚠️ <b>BOT ERROR</b>\n{message}")
