from bot import config


def calculate_trade_params(
    balance: float,
    entry: float,
    atr: float,
    side: str,
    min_qty: float = 0.001,
    qty_step: float = 0.001,
) -> dict:
    sl_mult = config.active["atr_sl_multiplier"]
    tp_mult = config.active["atr_tp_multiplier"]

    # Floor sl_dist to at least 0.3% of entry price so tiny ATR can't
    # produce an astronomically large position size.
    min_sl_dist = entry * 0.003
    sl_dist = max(atr * sl_mult, min_sl_dist)
    tp_dist = atr * tp_mult

    if side == "long":
        sl_price = round(entry - sl_dist, 4)
        tp_price = round(entry + tp_dist, 4)
    else:
        sl_price = round(entry + sl_dist, 4)
        tp_price = round(entry - tp_dist, 4)

    risk_usdt = balance * config.RISK_PER_TRADE
    position_usdt = risk_usdt / (sl_dist / entry)
    leverage = min(config.MAX_LEVERAGE, max(1, int(position_usdt / (balance * 0.1))))

    # Cap margin per position to balance / MAX_OPEN_POSITIONS so multiple
    # positions can coexist without exhausting available margin.
    max_margin = (balance / config.MAX_OPEN_POSITIONS) * 0.90
    max_position_usdt = max_margin * leverage
    position_usdt = min(position_usdt, max_position_usdt)

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
