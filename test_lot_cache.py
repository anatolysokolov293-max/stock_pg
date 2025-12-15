# test_lot_cache.py
import mysql.connector
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config_loader import DB_CFG


def load_lot_history() -> Dict[int, List[Tuple[datetime, int]]]:
    """
    Загружает всю lot_history в память.
    Возвращает {symbol_id: [(change_date, lot_size), ...] по убыванию даты}.
    """
    conn = mysql.connector.connect(**DB_CFG)
    cur = conn.cursor()

    sql = """
    SELECT symbol_id, lot_size, change_date
    FROM lot_history
    ORDER BY symbol_id, change_date DESC
    """
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    history: Dict[int, List[Tuple[datetime, int]]] = {}
    for symbol_id, lot_size, change_date in rows:
        history.setdefault(symbol_id, []).append((change_date, int(lot_size)))

    return history


class LotSizeCache:
    def __init__(self):
        self.history = load_lot_history()
        # простейший кеш последнего запроса
        self._last_key: Optional[Tuple[int, Optional[datetime]]] = None
        self._last_value: Optional[int] = None

    def get_lot_size(self, symbol_id: int,
                     as_of: Optional[datetime] = None) -> int:
        key = (symbol_id, as_of)
        if key == self._last_key:
            return self._last_value or 1

        lots = self.history.get(symbol_id)
        if not lots:
            self._last_key = key
            self._last_value = 1
            return 1

        if as_of is None:
            # самая свежая запись
            size = lots[0][1]
        else:
            size = 1
            for change_date, lot_size in lots:
                if change_date <= as_of:
                    size = lot_size
                    break

        self._last_key = key
        self._last_value = size
        return size


def main():
    cache = LotSizeCache()

    now = datetime.utcnow()
    for symbol_id in [1, 2, 3]:
        size_now = cache.get_lot_size(symbol_id, now)
        size_none = cache.get_lot_size(symbol_id, None)
        print(f"symbol {symbol_id}: as_of={now} -> {size_now}, as_of=None -> {size_none}")


if __name__ == "__main__":
    main()
