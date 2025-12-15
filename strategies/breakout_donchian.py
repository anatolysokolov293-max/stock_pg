# strategies/breakout_donchian.py
from strategies.base_lot_strategy import BaseLotStrategy
import pandas as pd
import numpy as np


class BreakoutDonchianStrategy(BaseLotStrategy):
    channel_period = 55
    sl_pct = 2.0
    tp_pct = 4.0
    use_trailing = False
    trailing_atr_period = 14
    trailing_atr_mult = 3.0
    risk_per_trade = 1.0

    def init(self):
        high = self.data.High
        low = self.data.Low

        def donchian(h, l, period):
            h_s = pd.Series(h)
            l_s = pd.Series(l)
            upper = h_s.rolling(period).max()
            lower = l_s.rolling(period).min()
            mid = (upper + lower) / 2.0
            return upper.values, lower.values, mid.values

        upper, lower, mid = donchian(high, low, self.channel_period)
        self.dc_up = self.I(lambda x: upper, high, name="dc_up")
        self.dc_dn = self.I(lambda x: lower, high, name="dc_dn")
        self.dc_mid = self.I(lambda x: mid, high, name="dc_mid")

        self.atr = None
        if self.use_trailing:
            close = self.data.Close

            def atr_series(o, h, l, c, period):
                df = pd.DataFrame({"o": o, "h": h, "l": l, "c": c})
                prev_close = df["c"].shift(1)
                tr1 = df["h"] - df["l"]
                tr2 = (df["h"] - prev_close).abs()
                tr3 = (df["l"] - prev_close).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(period).mean()
                return atr.values

            self.atr = self.I(
                lambda o, h, l, c: atr_series(o, h, l, c, self.trailing_atr_period),
                self.data.Open, self.data.High, self.data.Low, self.data.Close,
                name="dc_atr"
            )

        self.trailing_sl_long = None
        self.trailing_sl_short = None
        self.fixed_tp_long = None
        self.fixed_tp_short = None

    def next(self):
        price = self.data.Close[-1]
        up = self.dc_up[-1]
        dn = self.dc_dn[-1]

        if np.isnan(up) or np.isnan(dn):
            return

        # Управление открытой позицией
        if self.position:
            if self.use_trailing and self.atr is not None:
                atr_val = self.atr[-1]
                if not np.isnan(atr_val):
                    if self.position.is_long:
                        new_sl = price - self.trailing_atr_mult * atr_val
                        if self.trailing_sl_long is None or new_sl > self.trailing_sl_long:
                            self.trailing_sl_long = new_sl
                        if price <= self.trailing_sl_long:
                            self.position.close()
                            self.trailing_sl_long = None
                            self.fixed_tp_long = None
                            return

                    elif self.position.is_short:
                        new_sl = price + self.trailing_atr_mult * atr_val
                        if self.trailing_sl_short is None or new_sl < self.trailing_sl_short:
                            self.trailing_sl_short = new_sl
                        if price >= self.trailing_sl_short:
                            self.position.close()
                            self.trailing_sl_short = None
                            self.fixed_tp_short = None
                            return
            else:
                # Если трейлинг выключен, проверяем фиксированный TP (SL уже в брокере)
                if self.position.is_long and self.fixed_tp_long is not None:
                    if price >= self.fixed_tp_long:
                        self.position.close()
                        self.fixed_tp_long = None
                        return
                elif self.position.is_short and self.fixed_tp_short is not None:
                    if price <= self.fixed_tp_short:
                        self.position.close()
                        self.fixed_tp_short = None
                        return

            return

        # Входы
        # Лонг: пробой верхней границы канала
        if price > up:
            sl = price * (1 - self.sl_pct / 100.0)
            shares = self.calc_shares_by_risk(price=price, sl_price=sl, risk_pct=self.risk_per_trade)
            if shares <= 0:
                return
            tp = price * (1 + self.tp_pct / 100.0)

            if self.use_trailing:
                # Не передаём sl/tp в брокер, управляем вручную
                self.buy(size=shares)
                self.trailing_sl_long = sl
                self.fixed_tp_long = tp
            else:
                # Фиксированный SL/TP в брокере
                self.buy(size=shares, sl=sl, tp=tp)

            self.trailing_sl_short = None
            self.fixed_tp_short = None
            return

        # Шорт: пробой нижней границы канала
        if price < dn:
            sl = price * (1 + self.sl_pct / 100.0)
            shares = self.calc_shares_by_risk(price=price, sl_price=sl, risk_pct=self.risk_per_trade)
            if shares <= 0:
                return
            tp = price * (1 - self.tp_pct / 100.0)

            if self.use_trailing:
                self.sell(size=shares)
                self.trailing_sl_short = sl
                self.fixed_tp_short = tp
            else:
                self.sell(size=shares, sl=sl, tp=tp)

            self.trailing_sl_long = None
            self.fixed_tp_long = None
