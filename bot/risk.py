from bot.config import RISK_PER_TRADE, MAX_LEVERAGE, ATR_SL_MULTIPLIER, ATR_TP_MULTIPLIER


def calculate_trade_params(
    balance: float,
    entry: float,
    atr: float,
    side: str,
    min_qty: float = 0.001,
    qty_step: float = 0.001,
) -> dict:
    sl_dist = atr * ATR_SL_MULTIPLIER
    tp_dist = atr * ATR_TP_MULTIPLIER

    if side == "long":
        sl_price = round(entry - sl_dist, 4)
        tp_price = round(entry + tp_dist, 4)
    else:
        sl_price = round(entry + sl_dist, 4)
        tp_price = round(entry - tp_dist, 4)

    risk_usdt = balance * RISK_PER_TRADE
    position_usdt = risk_usdt / (sl_dist / entry)
    leverage = min(MAX_LEVERAGE, max(1, int(position_usdt / (balance * 0.1))))
    qty = position_usdt / entry
    qty = max(min_qty, round(qty - (qty % qty_step), 8))

    return {
        "entry": entry,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "qty": qty,
        "leverage": leverage,
        "risk_usdt": round(risk_usdt, 2),
        "position_usdt": round(position_usdt, 2),
    }
