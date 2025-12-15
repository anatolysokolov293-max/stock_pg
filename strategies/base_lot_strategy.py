# strategies/base_lot_strategy.py
from backtesting import Strategy
from datetime import datetime
from typing import Callable, Optional

from utils_lot import get_lotsize, calc_shares_by_risk


class BaseLotStrategy(Strategy):
    """
    Базовый Strategy с поддержкой лотов.
    Требует атрибутов класса:
      - symbol_id: int
      - lot_size_getter: callable(symbol_id, dt) -> int
    """

    lot_size_getter: Callable[[int, Optional[datetime]], int] = staticmethod(get_lotsize)
    symbol_id: Optional[int] = None

    def _get_lot_size(self) -> int:
        idx = self.data.index[-1]
        if isinstance(idx, datetime):
            dt = idx
        else:
            dt = datetime.fromtimestamp(float(idx))
        if self.symbol_id is None:
            return 1
        return int(self.lot_size_getter(self.symbol_id, dt))

    def calc_shares_by_risk(self,
                            price: float,
                            sl_price: float,
                            risk_pct: float) -> int:
        lot_size = self._get_lot_size()
        return calc_shares_by_risk(
            equity=float(self.equity),
            price=price,
            sl_price=sl_price,
            risk_pct=risk_pct,
            lotsize=lot_size,
        )
