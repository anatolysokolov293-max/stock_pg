from strategies.base_lot_strategy import BaseLotStrategy
import pandas as pd


class EMARSIPullbackStrategy(BaseLotStrategy):
    ema_period = 50
    rsi_period = 14
    rsi_oversold = 30
    rsi_overbought = 70
    sl_pct = 1.5
    tp_pct = 3.0
    risk_per_trade = 1.0

    def init(self):
        close = self.data.Close

        self.ema = self.I(
            lambda x: pd.Series(x).ewm(span=self.ema_period, adjust=False).mean().values,
            close,
            name='ema'
        )

        def rsi_series(x, period):
            s = pd.Series(x)
            delta = s.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(period).mean()
            avg_loss = loss.rolling(period).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-8)
            rsi = 100 - (100 / (1 + rs))
            return rsi.values

        self.rsi = self.I(lambda x: rsi_series(x, self.rsi_period), close, name='rsi')

    def next(self):
        price = self.data.Close[-1]
        ema_val = self.ema[-1]
        rsi_val = self.rsi[-1]

        if self.position:
            if self.position.is_long and (price > ema_val and rsi_val > self.rsi_overbought):
                self.position.close()
                return
            if self.position.is_short and (price < ema_val and rsi_val < self.rsi_oversold):
                self.position.close()
                return

        # лонг
        if not self.position and price <= ema_val and rsi_val <= self.rsi_oversold:
            sl = price * (1 - self.sl_pct / 100.0)
            shares = self.calc_shares_by_risk(price=price, sl_price=sl, risk_pct=self.risk_per_trade)
            if shares <= 0:
                return
            tp = price * (1 + self.tp_pct / 100.0)
            self.buy(size=shares, sl=sl, tp=tp)
            return

        # шорт
        if not self.position and price >= ema_val and rsi_val >= self.rsi_overbought:
            sl = price * (1 + self.sl_pct / 100.0)
            shares = self.calc_shares_by_risk(price=price, sl_price=sl, risk_pct=self.risk_per_trade)
            if shares <= 0:
                return
            tp = price * (1 - self.tp_pct / 100.0)
            self.sell(size=shares, sl=sl, tp=tp)
