from strategies.base_lot_strategy import BaseLotStrategy
import pandas as pd
import numpy as np


class BollMFIReversalStrategy(BaseLotStrategy):
    boll_period = 20
    boll_std_mult = 2.0
    mfi_period = 14
    mfi_low = 20
    mfi_high = 80
    sl_pct = 1.5
    tp_pct = 3.0
    risk_per_trade = 1.0

    def init(self):
        high = self.data.High
        low = self.data.Low
        close = self.data.Close
        volume = self.data.Volume

        def bollinger(c, period, mult):
            s = pd.Series(c)
            ma = s.rolling(period).mean()
            std = s.rolling(period).std()
            upper = ma + mult * std
            lower = ma - mult * std
            return ma.values, upper.values, lower.values

        ma, upper, lower = bollinger(close, self.boll_period, self.boll_std_mult)
        self.boll_mid = self.I(lambda x: ma, close, name="boll_mid")
        self.boll_up = self.I(lambda x: upper, close, name="boll_up")
        self.boll_dn = self.I(lambda x: lower, close, name="boll_dn")

        def mfi_series(h, l, c, v, period):
            tp = (h + l + c) / 3.0
            mf = tp * v
            df = pd.DataFrame({"tp": tp, "mf": mf})
            delta_tp = df["tp"].diff()
            pos_mf = df["mf"].where(delta_tp > 0, 0.0)
            neg_mf = df["mf"].where(delta_tp < 0, 0.0)
            sum_pos = pos_mf.rolling(period).sum()
            sum_neg = (-neg_mf).rolling(period).sum()
            sum_neg = sum_neg.replace(0, 1e-8)
            mr = sum_pos / sum_neg
            mfi = 100 - (100 / (1 + mr))
            return mfi.values

        self.mfi = self.I(
            lambda h, l, c, v: mfi_series(h, l, c, v, self.mfi_period),
            high, low, close, volume,
            name="mfi"
        )

    def next(self):
        price = self.data.Close[-1]
        upper = self.boll_up[-1]
        lower = self.boll_dn[-1]
        mid = self.boll_mid[-1]
        mfi_val = self.mfi[-1]

        if any(np.isnan(x) for x in [upper, lower, mid, mfi_val]):
            return

        if self.position:
            if self.position.is_long and price >= mid:
                self.position.close()
                return
            if self.position.is_short and price <= mid:
                self.position.close()
                return

        if not self.position and price <= lower and mfi_val <= self.mfi_low:
            sl = price * (1 - self.sl_pct / 100.0)
            shares = self.calc_shares_by_risk(price=price, sl_price=sl, risk_pct=self.risk_per_trade)
            if shares <= 0:
                return
            tp = price * (1 + self.tp_pct / 100.0)
            self.buy(size=shares, sl=sl, tp=tp)
            return

        if not self.position and price >= upper and mfi_val >= self.mfi_high:
            sl = price * (1 + self.sl_pct / 100.0)
            shares = self.calc_shares_by_risk(price=price, sl_price=sl, risk_pct=self.risk_per_trade)
            if shares <= 0:
                return
            tp = price * (1 - self.tp_pct / 100.0)
            self.sell(size=shares, sl=sl, tp=tp)
