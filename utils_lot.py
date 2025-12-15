"""
utils_lot.py - Утилиты для работы с размерами лотов
"""
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
import numpy as np
from configloader import DBCFG


def load_lot_history() -> Dict[int, List[Tuple[datetime, int]]]:
    """
    Загружает историю изменений размеров лотов из PostgreSQL

    Returns:
        Словарь {symbol_id: [(change_date, lot_size), ...]}
        change_date - UTC-aware datetime
    """
    conn = psycopg2.connect(**DBCFG)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = """
                SELECT symbol_id, lot_size, change_date
                FROM lot_history
                ORDER BY symbol_id, change_date DESC
            """
            cur.execute(sql)
            rows = cur.fetchall()

            history: Dict[int, List[Tuple[datetime, int]]] = {}

            for row in rows:
                symbol_id = row['symbol_id']
                lot_size = row['lot_size']
                change_date = row['change_date']

                if change_date.tzinfo is None:
                    change_date = change_date.replace(tzinfo=timezone.utc)

                history.setdefault(symbol_id, []).append((change_date, int(lot_size)))

            return history

    finally:
        conn.close()


class LotSizeCache:
    """Кэш для размеров лотов с оптимизацией повторных запросов"""

    def __init__(self):
        self.history = load_lot_history()
        self.last_key: Optional[Tuple[int, Optional[datetime]]] = None
        self.last_value: Optional[int] = None

    def get_lotsize(self, symbol_id: int, as_of: Optional[datetime] = None) -> int:
        """
        Получает размер лота для символа на определенную дату

        Args:
            symbol_id: ID символа
            as_of: Дата (если None - берется последний известный размер)

        Returns:
            Размер лота (по умолчанию 1 если не найден)
        """
        key = (symbol_id, as_of)
        if key == self.last_key:
            return self.last_value or 1

        lots = self.history.get(symbol_id)
        if not lots:
            self.last_key = key
            self.last_value = 1
            return 1

        if as_of is None:
            size = lots[0][1]
        else:
            if hasattr(as_of, 'tzinfo') and as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
            elif hasattr(as_of, 'tz') and as_of.tz is None:
                as_of = as_of.tz_localize('UTC')

            size = 1
            for change_date, lot_size in lots:
                if change_date <= as_of:
                    size = lot_size
                    break

        self.last_key = key
        self.last_value = size
        return size


# Глобальный кэш
global_lot_cache: Optional[LotSizeCache] = None


def get_lotsize(symbol_id: int, as_of: Optional[datetime] = None) -> int:
    """
    Глобальная функция для получения размера лота

    Args:
        symbol_id: ID символа
        as_of: Дата (опционально)

    Returns:
        Размер лота
    """
    global global_lot_cache
    if global_lot_cache is None:
        global_lot_cache = LotSizeCache()
    return global_lot_cache.get_lotsize(symbol_id, as_of)


def calc_shares_by_risk(
    equity: float,
    price: float,
    sl_price: float,
    risk_pct: float,
    lotsize: int
) -> int:
    """
    Рассчитывает количество акций на основе риска

    Args:
        equity: Капитал
        price: Цена входа
        sl_price: Цена стоп-лосса
        risk_pct: Процент риска (например, 2.0 для 2%)
        lotsize: Размер лота

    Returns:
        Количество акций (кратное лоту)
    """
    if lotsize <= 0:
        lotsize = 1

    per_share_risk = max(abs(price - sl_price), 1e-8)
    dollar_risk = equity * (risk_pct / 100.0)
    max_shares = dollar_risk / per_share_risk
    lots = int(np.floor(max_shares / lotsize))
    shares = lots * lotsize

    return max(shares, 0)
