#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
strategy_runner.py

Назначение:

Демон запуска стратегий по событиям BAR_CLOSE и записи сигналов в live_signals.

Цели:

- Периодически опрашивать таблицы агрегированных свечей (candles_5m, candles_15m, ...),
  находить новые закрытые бары (по timestamp > last_bar_timestamp для каждого ТФ).

- Для каждого нового бара:
  * определить тикер (symbol) по symbol_id (через таблицу symbols).
  * найти в strategy_universe все стратегии для (symbol, timeframe)
    с enabled = true и mode IN ('paper', 'live').
  * через strategy_catalog по strategy_universe.strategy_id (code) найти
    live_py_module/live_py_class (или py_module/py_class как fallback), импортировать модуль,
    создать экземпляр класса.
  * построить контекст (StrategyContext) для каждой стратегии:
    - symbol, timeframe, bar_timestamp;
    - текущий бар и N предыдущих баров (история из candles_xx);
    - текущая позиция по этой стратегии/инструменту (live_positions);
    - активные ордера (live_orders);
    - параметры стратегии (params_json);
    - риск-поля (risk_per_trade, max_drawdown_fraction, gap_threshold_fraction).
  * вызвать метод on_bar(context) у экземпляра стратегии.
  * корректно обработать ошибки стратегии (не уронить цикл).

- Любые валидные сигналы (dict) писать в live_signals:
  - strategy_universe_id, symbol, timeframe, bar_timestamp,
    signal_timestamp, signal_type, signal_source, signal_json, gap_flag, processed=false.

- Обновлять:
  - bar_state(service_name='strategy_runner', timeframe, last_bar_timestamp);
  - service_status(service_name='strategy_runner') — heartbeat и статус.
"""

import importlib
import logging
import sys
import time
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import DictCursor, Json

# --- Конфиг подключения к PostgreSQL (под твою БД) ---

PG_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "stock_db",
    "user": "postgres",
    "password": "123",
}

# --- Таймфреймы и соответствующие таблицы свечей ---

TF_CONFIG = {
    "5m": {"table": "candles_5m"},
    "15m": {"table": "candles_15m"},
    "30m": {"table": "candles_30m"},
    "1h": {"table": "candles_1h"},
    "4h": {"table": "candles_4h"},
    "1d": {"table": "candles_1d"},
}

# Сколько баров истории загружать в Context
HISTORY_BARS = 500

# Пауза между итерациями опроса свечей (секунд)
POLL_INTERVAL_SECONDS = 3

# --- Логирование ---

logger = logging.getLogger("strategy_runner")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Вспомогательные структуры данных ---


@dataclass
class PositionInfo:
    size: float
    avg_price: float
    direction: str  # 'LONG' / 'SHORT' / 'FLAT'
    gap_mode: bool


@dataclass
class OrderInfo:
    id: int
    side: str  # 'BUY' / 'SELL'
    status: str  # 'NEW' / 'PARTIALLY_FILLED' / 'FILLED' / ...
    quantity: float
    price: Optional[float]


@dataclass
class BarInfo:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_gap: bool
    gap_dir: Optional[str]


@dataclass
class StrategyContext:
    symbol: str
    timeframe: str
    bar: BarInfo
    history: List[BarInfo]  # N последних баров до текущего
    position: Optional[PositionInfo]
    orders: List[OrderInfo]
    params: Dict[str, Any]
    risk_per_trade: Optional[float]
    max_drawdown_fraction: Optional[float]
    gap_threshold_fraction: Optional[float]


# --- Работа с БД ---


def get_connection():
    return psycopg2.connect(
        host=PG_CONFIG["host"],
        port=PG_CONFIG["port"],
        dbname=PG_CONFIG["dbname"],
        user=PG_CONFIG["user"],
        password=PG_CONFIG["password"],
    )


def log_error(
    conn,
    message,
    severity: str = "error",
    source: str = "strategy_runner",
    strategy_universe_id=None,
    symbol=None,
    timeframe=None,
    details=None,
):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO live_errors (
                    timestamp, source, severity,
                    strategy_universe_id, symbol, timeframe,
                    message, details_json
                )
                VALUES (now(), %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    source,
                    severity,
                    strategy_universe_id,
                    symbol,
                    timeframe,
                    message,
                    Json(details) if details is not None else None,
                ),
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Не удалось записать ошибку в live_errors: {e}")


def update_service_heartbeat(conn):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO service_status (service_name, last_heartbeat, status)
                VALUES ('strategy_runner', now(), 'ok')
                ON CONFLICT (service_name)
                DO UPDATE SET last_heartbeat = EXCLUDED.last_heartbeat,
                              status = EXCLUDED.status
                """
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Не удалось обновить heartbeat strategy_runner: {e}")


def get_last_bar_timestamp(conn, timeframe: str) -> Optional[datetime]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT last_bar_timestamp
            FROM bar_state
            WHERE service_name = 'strategy_runner'
              AND timeframe = %s
            """,
            (timeframe,),
        )
        row = cur.fetchone()
    return row["last_bar_timestamp"] if row else None


def save_last_bar_timestamp(conn, timeframe: str, ts: datetime):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bar_state (service_name, timeframe, last_bar_timestamp, updated_at)
            VALUES ('strategy_runner', %s, %s, now())
            ON CONFLICT (service_name, timeframe)
            DO UPDATE SET last_bar_timestamp = EXCLUDED.last_bar_timestamp,
                          updated_at = EXCLUDED.updated_at
            """,
            (timeframe, ts),
        )
    conn.commit()


def resolve_symbol_ticker(conn, symbol_id: int) -> Optional[str]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT ticker FROM symbols WHERE id = %s", (symbol_id,))
        row = cur.fetchone()
    return row["ticker"] if row else None


def load_bar_history(
    conn, tf_table: str, symbol_id: int, ts: datetime, limit: int
) -> List[BarInfo]:
    """
    Загружает последние 'limit' баров до ts (НЕ включая ts) для символа.
    """
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            f"""
            SELECT timestamp, open, high, low, close, volume, is_gap, gap_dir
            FROM {tf_table}
            WHERE symbol_id = %s AND timestamp < %s
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (symbol_id, ts, limit),
        )
        rows = cur.fetchall()

    history: List[BarInfo] = []
    for r in reversed(rows):
        t = r["timestamp"]
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        history.append(
            BarInfo(
                timestamp=t,
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"]),
                is_gap=bool(r["is_gap"]),
                gap_dir=r["gap_dir"],
            )
        )
    return history


def load_position(conn, strategy_universe_id: int, symbol: str) -> Optional[PositionInfo]:
    """
    Позиция одна на связку (strategy_universe_id, symbol).
    При необходимости можно добавить фильтр по timeframe.
    """
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT id, direction, quantity, avg_price, gap_mode
            FROM live_positions
            WHERE strategy_universe_id = %s AND symbol = %s
            """,
            (strategy_universe_id, symbol),
        )
        row = cur.fetchone()

    if not row:
        return None

    direction = row["direction"]
    qty = float(row["quantity"])
    avg_price = float(row["avg_price"])
    return PositionInfo(
        size=qty,
        avg_price=avg_price,
        direction=direction,
        gap_mode=bool(row["gap_mode"]),
    )


def load_orders(conn, strategy_universe_id: int, symbol: str) -> List[OrderInfo]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT id, side, status, quantity, price
            FROM live_orders
            WHERE strategy_universe_id = %s
              AND symbol = %s
              AND status IN ('NEW', 'PARTIALLY_FILLED')
            """,
            (strategy_universe_id, symbol),
        )
        rows = cur.fetchall()

    orders: List[OrderInfo] = []
    for r in rows:
        orders.append(
            OrderInfo(
                id=r["id"],
                side=r["side"],
                status=r["status"],
                quantity=float(r["quantity"]),
                price=float(r["price"]) if r["price"] is not None else None,
            )
        )
    return orders


def load_strategies_for_symbol_tf(conn, symbol: str, timeframe: str):
    """
    Возвращает список строк strategy_universe для данного символа и ТФ,
    включенных и в режиме paper/live, с join на strategy_catalog.
    """
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT su.*,
                   sc.py_module,
                   sc.py_class,
                   sc.live_py_module,
                   sc.live_py_class
            FROM strategy_universe su
            JOIN strategy_catalog sc
              ON su.strategy_id::integer = sc.id
            WHERE su.symbol = %s
              AND su.timeframe = %s
              AND su.enabled = true
              AND su.mode IN ('paper', 'live')
              AND sc.enabled = 1
            """,
            (symbol, timeframe),
        )
        rows = cur.fetchall()
    return rows


def insert_signal(
    conn,
    strategy_universe_id: int,
    symbol: str,
    timeframe: str,
    bar: BarInfo,
    signal: Dict[str, Any],
    signal_source: str = "strategy",
):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO live_signals (
                strategy_universe_id,
                symbol,
                timeframe,
                bar_timestamp,
                signal_timestamp,
                signal_type,
                signal_source,
                signal_json,
                gap_flag,
                processed,
                created_at
            )
            VALUES (%s, %s, %s, %s, now(), %s, %s, %s, %s, false, now())
            """,
            (
                strategy_universe_id,
                symbol,
                timeframe,
                bar.timestamp,
                signal.get("type"),
                signal_source,
                Json(signal),
                bar.is_gap,
            ),
        )
    conn.commit()


# --- Загрузка/исполнение стратегий через strategy_catalog ---

# _strategy_instances[(strategy_universe_id)] = instance of strategy class
_strategy_instances: Dict[int, Any] = {}


def get_strategy_instance(su_row) -> Optional[Any]:
    """
    Возвращает экземпляр стратегии для конкретной строки strategy_universe.
    Использует strategy_catalog.live_py_module/live_py_class,
    а при их отсутствии — py_module/py_class (fallback).
    Кеширует инстансы по strategy_universe.id.
    """
    su_id = su_row["id"]
    if su_id in _strategy_instances:
        return _strategy_instances[su_id]

    # сначала пробуем live_py_*
    live_py_module = su_row.get("live_py_module")
    live_py_class = su_row.get("live_py_class")

    if live_py_module and live_py_class:
        py_module = live_py_module
        py_class = live_py_class
    else:
        # fallback на bt-описание, чтобы не ломать существующие стратегии
        py_module = su_row["py_module"]
        py_class = su_row["py_class"]

    logger.info(
    f"strategy_universe_id={su_id}: using {py_module}.{py_class} "
    f"(strategy_id={su_row['strategy_id']})"
    )

    if not py_module or not py_class:
        logger.error(
            f"Для strategy_universe_id={su_id} не заданы py_module/py_class "
            f"(live_py_module/live_py_class и py_module/py_class пусты)"
        )
        _strategy_instances[su_id] = None
        return None

    try:
        module = importlib.import_module(py_module)
    except ImportError as e:
        logger.error(f"Не удалось импортировать модуль стратегии {py_module}: {e}")
        _strategy_instances[su_id] = None
        return None

    if not hasattr(module, py_class):
        logger.error(f"Модуль {py_module} не содержит класс {py_class}")
        _strategy_instances[su_id] = None
        return None

    cls = getattr(module, py_class)
    try:
        instance = cls()
    except Exception as e:
        logger.error(
            f"Не удалось создать экземпляр {py_class} из {py_module}: {e}"
        )
        _strategy_instances[su_id] = None
        return None

    _strategy_instances[su_id] = instance
    return instance


# --- Основная логика обработки баров и запуск стратегий ---


def process_bar_for_timeframe(
    conn, timeframe: str, tf_table: str, last_ts: Optional[datetime]
) -> Optional[datetime]:
    """
    Обрабатывает все новые бары для указанного timeframe.
    Возвращает новый last_bar_timestamp (если есть новые бары) или исходный.
    """
    logger.info(f"Проверка новых баров для {timeframe}")

    with conn.cursor(cursor_factory=DictCursor) as cur:
        if last_ts is None:
            # берём все бары (для оффлайн-прогона истории)
            cur.execute(
                f"""
                SELECT symbol_id, timestamp, open, high, low, close, volume, is_gap, gap_dir
                FROM {tf_table}
                ORDER BY timestamp, symbol_id
                """
            )
        else:
            cur.execute(
                f"""
                SELECT symbol_id, timestamp, open, high, low, close, volume, is_gap, gap_dir
                FROM {tf_table}
                WHERE timestamp > %s
                ORDER BY timestamp, symbol_id
                """,
                (last_ts,),
            )

        rows = cur.fetchall()

    if not rows:
        logger.info(f"Новых баров для {timeframe} нет")
        return last_ts

    logger.info(f"Новых баров для {timeframe}: {len(rows)}")

    new_last_ts = last_ts

    for r in rows:
        symbol_id = r["symbol_id"]
        ts = r["timestamp"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        bar = BarInfo(
            timestamp=ts,
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
            is_gap=bool(r["is_gap"]),
            gap_dir=r["gap_dir"],
        )

        ticker = resolve_symbol_ticker(conn, symbol_id)
        if not ticker:
            logger.warning(
                f"Не найден ticker для symbol_id={symbol_id}, пропускаем бар."
            )
            continue

        strategies = load_strategies_for_symbol_tf(conn, ticker, timeframe)
        if not strategies:
            # нет активных стратегий для этой связки — просто обновим last_ts
            new_last_ts = ts if (new_last_ts is None or ts > new_last_ts) else new_last_ts
            continue

        history = load_bar_history(conn, tf_table, symbol_id, ts, HISTORY_BARS)

        for s_row in strategies:
            su_id = s_row["id"]
            strategy_id_code = s_row["strategy_id"]
            params = s_row["params_json"] or {}
            risk_per_trade = s_row.get("risk_per_trade")
            max_dd = s_row.get("max_drawdown_fraction")
            gap_thr = s_row.get("gap_threshold_fraction")

            position = load_position(conn, su_id, ticker)
            orders = load_orders(conn, su_id, ticker)

            ctx = StrategyContext(
                symbol=ticker,
                timeframe=timeframe,
                bar=bar,
                history=history,
                position=position,
                orders=orders,
                params=params,
                risk_per_trade=risk_per_trade,
                max_drawdown_fraction=max_dd,
                gap_threshold_fraction=gap_thr,
            )

            strategy_instance = get_strategy_instance(s_row)
            if strategy_instance is None:
                log_error(
                    conn,
                    message=f"Стратегия {strategy_id_code} не найдена/не загружена",
                    severity="error",
                    source="strategy",
                    strategy_universe_id=su_id,
                    symbol=ticker,
                    timeframe=timeframe,
                    details={
                        "strategy_id": strategy_id_code,
                        "py_module": s_row["py_module"],
                        "py_class": s_row["py_class"],
                        "live_py_module": s_row.get("live_py_module"),
                        "live_py_class": s_row.get("live_py_class"),
                    },
                )
                continue

            if not hasattr(strategy_instance, "on_bar"):
                log_error(
                    conn,
                    message=f"Стратегия {strategy_id_code} не имеет метода on_bar",
                    severity="error",
                    source="strategy",
                    strategy_universe_id=su_id,
                    symbol=ticker,
                    timeframe=timeframe,
                    details={
                        "strategy_id": strategy_id_code,
                        "py_module": s_row["py_module"],
                        "py_class": s_row["py_class"],
                        "live_py_module": s_row.get("live_py_module"),
                        "live_py_class": s_row.get("live_py_class"),
                    },
                )
                continue

            try:
                signal = strategy_instance.on_bar(ctx)
            except Exception as e:
                logger.exception(
                    f"Ошибка в стратегии {strategy_id_code} (strategy_universe_id={su_id})"
                )
                log_error(
                    conn,
                    message=f"Ошибка выполнения стратегии {strategy_id_code}",
                    severity="error",
                    source="strategy",
                    strategy_universe_id=su_id,
                    symbol=ticker,
                    timeframe=timeframe,
                    details={
                        "strategy_id": strategy_id_code,
                        "py_module": s_row["py_module"],
                        "py_class": s_row["py_class"],
                        "live_py_module": s_row.get("live_py_module"),
                        "live_py_class": s_row.get("live_py_class"),
                        "error": str(e),
                    },
                )
                continue

            if not signal:
                # стратегия вернула None или пустой dict — нет сигнала
                continue

            # простая валидация
            if not isinstance(signal, dict) or "type" not in signal:
                log_error(
                    conn,
                    message="Некорректный формат сигнала от стратегии",
                    severity="warning",
                    source="strategy",
                    strategy_universe_id=su_id,
                    symbol=ticker,
                    timeframe=timeframe,
                    details={
                        "strategy_id": strategy_id_code,
                        "signal": str(signal),
                        "py_module": s_row["py_module"],
                        "py_class": s_row["py_class"],
                        "live_py_module": s_row.get("live_py_module"),
                        "live_py_class": s_row.get("live_py_class"),
                    },
                )
                continue

            insert_signal(conn, su_id, ticker, timeframe, bar, signal, signal_source="strategy")

        # обновляем новый last_ts
        new_last_ts = ts if (new_last_ts is None or ts > new_last_ts) else new_last_ts

    return new_last_ts


# --- Основной цикл демона ---


def main_loop():
    conn = get_connection()
    conn.autocommit = False
    logger.info("Старт strategy_runner")

    try:
        while True:
            try:
                for timeframe, cfg in TF_CONFIG.items():
                    tf_table = cfg["table"]
                    last_ts = get_last_bar_timestamp(conn, timeframe)
                    new_last_ts = process_bar_for_timeframe(conn, timeframe, tf_table, last_ts)
                    if new_last_ts and (last_ts is None or new_last_ts > last_ts):
                        save_last_bar_timestamp(conn, timeframe, new_last_ts)

                update_service_heartbeat(conn)
                conn.commit()

            except Exception as e:
                conn.rollback()
                logger.exception(f"Ошибка в основном цикле strategy_runner: {e}")
                log_error(
                    conn,
                    message="Ошибка в основном цикле strategy_runner",
                    severity="error",
                    source="strategy_runner",
                    details={"error": str(e)},
                )
                time.sleep(5)

            time.sleep(POLL_INTERVAL_SECONDS)

    finally:
        conn.close()
        logger.info("strategy_runner остановлен")


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Остановка strategy_runner по Ctrl+C")
