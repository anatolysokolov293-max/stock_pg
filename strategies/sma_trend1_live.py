# strategies/sma_trend1_live.py

from typing import Any, Dict, Optional, List

from demons.strategy_runner import StrategyContext, BarInfo  # путь тот же, что у демона


class SMATrend1LiveStrategy:
    """
    Live‑адаптер для SMA_TREND1.

    Логика:
    - Вход LONG при пересечении fast SMA сверху через slow SMA.
    - Выход по обратному пересечению (fast вниз через slow), если есть LONG.
    - Стоп/тейк в процентах от цены (sl_pct / tp_pct).
    - Размер рассчитывает execution_engine по risk_per_trade и size_value.
    """

    def __init__(self) -> None:
        # Состояние внутри стратегии не храним: всё берём из контекста.
        pass

    @staticmethod
    def _calc_sma(values: List[float], period: int) -> Optional[float]:
        if period <= 0 or len(values) < period:
            return None
        return sum(values[-period:]) / period

    def on_bar(self, ctx: StrategyContext) -> Optional[Dict[str, Any]]:
        # Актуальная цена
        price = ctx.bar.close

        # Параметры стратегии: берём из params_json с дефолтами как в SMATrend1Strategy
        params = ctx.params or {}
        fast_period = int(params.get("fast_period", 20))
        slow_period = int(params.get("slow_period", 100))
        sl_pct = float(params.get("sl_pct", 2.0))
        tp_pct = float(params.get("tp_pct", 4.0))
        risk_per_trade = ctx.risk_per_trade if ctx.risk_per_trade is not None else 1.0

        # История закрытий: history (до текущего бара) + текущий бар
        closes: List[float] = [b.close for b in ctx.history] + [price]

        sma_fast_prev = self._calc_sma(closes[:-1], fast_period)
        sma_slow_prev = self._calc_sma(closes[:-1], slow_period)
        sma_fast_cur = self._calc_sma(closes, fast_period)
        sma_slow_cur = self._calc_sma(closes, slow_period)

        # Недостаточно истории — сигнала нет
        if (
            sma_fast_prev is None
            or sma_slow_prev is None
            or sma_fast_cur is None
            or sma_slow_cur is None
        ):
            return None

        position = ctx.position
        has_long = (
            position is not None
            and position.direction == "LONG"
            and position.size > 0
        )

        # --- Выход: обратное пересечение (fast сверху → вниз через slow) ---
        if has_long and sma_fast_prev > sma_slow_prev and sma_fast_cur <= sma_slow_cur:
            return {
                "type": "CLOSE",
                "comment": "sma_trend1_live: close on fast<slow",
            }

        # Если уже есть активный LONG или есть незакрытые ордера — новых входов не даём
        if has_long or ctx.orders:
            return None

        # --- Вход: пересечение fast снизу вверх через slow ---
        if sma_fast_prev < sma_slow_prev and sma_fast_cur >= sma_slow_cur:
            sl_price = price * (1.0 - sl_pct / 100.0)
            tp_price = price * (1.0 + tp_pct / 100.0)

            # В backtest размер считался внутри стратегии; в live его считает execution_engine
            # из risk_per_trade и расстояния до стопа.
            return {
                "type": "OPEN",
                "direction": "LONG",
                "entry_type": "MARKET",
                "entry_price": float(price),
                "stop_loss": float(sl_price),
                "take_profit": float(tp_price),
                "size_mode": "RISK_FRACTION",
                "size_value": float(risk_per_trade),  # % капитала на сделку
                "comment": "sma_trend1_live: open long on fast>slow",
            }

        return None
