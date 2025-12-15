# strategies/atr_trail_trend.py
from strategies.base_lot_strategy import BaseLotStrategy
import pandas as pd
import numpy as np


class ATRTrailTrendStrategy(BaseLotStrategy):
    trend_ma_period = 100
    atr_period = 14
    atr_mult = 3.0
    risk_per_trade = 1.0
    use_reverse = False

    def init(self):
        close = self.data.Close

        self.trend_ma = self.I(
            lambda x: pd.Series(x).rolling(self.trend_ma_period).mean().values,
            close,
            name="trend_ma"
        )

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
            lambda o, h, l, c: atr_series(o, h, l, c, self.atr_period),
            self.data.Open, self.data.High, self.data.Low, self.data.Close,
            name="atr"
        )

        # Храним трейлинг-стоп вручную (для лонга/шорта)
        self.trailing_sl_long = None
        self.trailing_sl_short = None

    def next(self):
        price = self.data.Close[-1]
        ma_val = self.trend_ma[-1]
        atr_val = self.atr[-1]

        if np.isnan(ma_val) or np.isnan(atr_val):
            return

        up_trend = price > ma_val
        down_trend = price < ma_val

        # Управление открытой позицией
        if self.position:
            if self.position.is_long:
                # Обновление трейлинг-стопа для лонга
                new_sl = price - self.atr_mult * atr_val
                if self.trailing_sl_long is None or new_sl > self.trailing_sl_long:
                    self.trailing_sl_long = new_sl

                # Проверка закрытия по стопу
                if price <= self.trailing_sl_long:
                    self.position.close()
                    self.trailing_sl_long = None
                    return

                # Разворот по тренду (если включён)
                if self.use_reverse and down_trend:
                    self.position.close()
                    self.trailing_sl_long = None

                    # Открываем шорт
                    sl_short = price + self.atr_mult * atr_val
                    shares = self.calc_shares_by_risk(
                        price=price,
                        sl_price=sl_short,
                        risk_pct=self.risk_per_trade
                    )
                    if shares > 0:
                        self.sell(size=shares)
                        self.trailing_sl_short = sl_short
                    return

            elif self.position.is_short:
                # Обновление трейлинг-стопа для шорта
                new_sl = price + self.atr_mult * atr_val
                if self.trailing_sl_short is None or new_sl < self.trailing_sl_short:
                    self.trailing_sl_short = new_sl

                # Проверка закрытия по стопу
                if price >= self.trailing_sl_short:
                    self.position.close()
                    self.trailing_sl_short = None
                    return

                # Разворот по тренду (если включён)
                if self.use_reverse and up_trend:
                    self.position.close()
                    self.trailing_sl_short = None

                    # Открываем лонг
                    sl_long = price - self.atr_mult * atr_val
                    shares = self.calc_shares_by_risk(
                        price=price,
                        sl_price=sl_long,
                        risk_pct=self.risk_per_trade
                    )
                    if shares > 0:
                        self.buy(size=shares)
                        self.trailing_sl_long = sl_long
                    return

            return

        # Входы (только если нет открытой позиции)
        if up_trend:
            sl = price - self.atr_mult * atr_val
            shares = self.calc_shares_by_risk(
                price=price,
                sl_price=sl,
                risk_pct=self.risk_per_trade
            )
            if shares > 0:
                self.buy(size=shares)
                self.trailing_sl_long = sl
                self.trailing_sl_short = None

        elif down_trend:
            sl = price + self.atr_mult * atr_val
            shares = self.calc_shares_by_risk(
                price=price,
                sl_price=sl,
                risk_pct=self.risk_per_trade
            )
            if shares > 0:
                self.sell(size=shares)
                self.trailing_sl_short = sl
                self.trailing_sl_long = None
