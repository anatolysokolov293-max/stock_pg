# strategies/test_always_long.py

from typing import Dict, Any


class TestAlwaysLongStrategy:
    """
    Тестовая стратегия:
    - если нет позиции и нет активных ордеров, даёт сигнал на открытие LONG по рынку.
    """

    def on_bar(self, ctx) -> Dict[str, Any] | None:
        bar = ctx.bar
        price = bar.close

        # если уже есть позиция или висят ордера — ничего не делаем
        if ctx.position and ctx.position.direction == "LONG":
            return None
        if ctx.orders:
            return None

        # для risk-движка:
        # type: OPEN/ADD/REVERSE/CLOSE/MANUAL_CLOSE/FORCED_CLOSE
        # direction: LONG/SHORT
        # entry_type: MARKET/LIMIT
        # entry_price: цена входа (для MARKET всё равно нужна для risk)
        # stop_loss / take_profit: цены стопа/тейка
        # size_mode: RISK_FRACTION (поддерживаемый режим)
        # size_value: доля от risk_per_trade (0..1)
        sl_price = price * 0.98  # условный стоп 2% ниже рынка
        tp_price = price * 1.04  # условный тейк 4% выше

        return {
            "type": "OPEN",
            "direction": "LONG",
            "entry_type": "MARKET",
            "entry_price": float(price),
            "stop_loss": float(sl_price),
            "take_profit": float(tp_price),
            "size_mode": "RISK_FRACTION",
            "size_value": 1.0,
            "comment": "test_always_long",
        }
