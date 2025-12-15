from backtesting.lib import crossover
import pandas as pd
from strategies.base_lot_strategy import BaseLotStrategy


class SMATrend1Strategy(BaseLotStrategy):
    fast_period = 20
    slow_period = 100
    sl_pct = 2.0
    tp_pct = 4.0
    risk_per_trade = 1.0  # % капитала

    def init(self):
        close = self.data.Close

        self.sma_fast = self.I(
            lambda x: pd.Series(x).rolling(self.fast_period).mean().values,
            close,
            name="sma_fast"
        )
        self.sma_slow = self.I(
            lambda x: pd.Series(x).rolling(self.slow_period).mean().values,
            close,
            name="sma_slow"
        )

    def next(self):
        price = self.data.Close[-1]

        # расчёт размера позиции по риску и лоту
        sl_price = price * (1 - self.sl_pct / 100.0)
        shares = self.calc_shares_by_risk(
            price=price,
            sl_price=sl_price,
            risk_pct=self.risk_per_trade,
        )
        if shares <= 0:
            return

        # выход по обратному пересечению
        if self.position:
            if crossover(self.sma_slow, self.sma_fast):
                self.position.close()
                return

        # вход
        if crossover(self.sma_fast, self.sma_slow):
            sl = sl_price
            tp = price * (1 + self.tp_pct / 100.0)
            self.buy(size=shares, sl=sl, tp=tp)
