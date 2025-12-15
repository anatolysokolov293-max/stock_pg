#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
health_monitor.py

Назначение:
    Сервис мониторинга состояния компонентов (data_feed, strategy_runner,
    execution_engine, fake_broker) и качества данных (лаг минуток).
    При обнаружении проблем:
        - логирует события в live_errors;
        - при необходимости включает safe-mode (запрет новых позиций) или stop-trading.

Цели:
    - Периодически проверять:
        * service_status по service_name:
            - 'data_feed'
            - 'strategy_runner'
            - 'execution_engine'
            - 'fake_broker' (и в будущем 'broker_adapter')
        * лаг рыночных данных:
            - now - max(timestamp) в candles_1m.
    - Реагировать на события:
        * если сервис не подаёт heartbeat дольше порога:
            - записать live_errors(message='<service>_down', severity='critical');
            - для брокера (fake_broker/broker_adapter) и execution_engine при необходимости
              выставить allow_trading=false или allow_new_positions=false.
        * если лаг минуток превышает порог:
            - записать live_errors(message='bar_too_old', severity='warning');
            - включить safe-mode: allow_new_positions=false, пока лаг не вернётся в норму.
    - Гарантировать, что ни один сбой не останавливает health_monitor.

Ключевые допущения:
    - service_status(service_name, last_heartbeat, status, details_json) уже заполняется демонами.
    - trading_control(id=1) управляет глобальными флагами allow_trading и allow_new_positions.
    - candles_1m(timestamp, symbol_id, ...) хранит минутные бары в UTC.
    - Все времена сравниваются в UTC (timezone-aware datetime).

Архитектура:
    - Один процесс с циклом:
        1. Читает текущее время (UTC).
        2. Проверяет heartbeats сервисов.
        3. Проверяет лаг candles_1m.
        4. При необходимости обновляет trading_control и пишет live_errors.
        5. Спит заданный интервал и повторяет.
"""

import logging
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import psycopg2
from psycopg2.extras import DictCursor, Json

# --- Конфиг PostgreSQL ---

PG_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "stock_db",
    "user": "postgres",
    "password": "123",
}

# --- Пороговые значения (настраиваются при необходимости) ---

# Таймауты heartbeats (секунд)
TIMEOUTS = {
    "data_feed":        60,   # если > 60 сек нет heartbeat → data_feed_down
    "strategy_runner":  60,
    "execution_engine": 60,
    "fake_broker":      60,   # для реального брокера/адаптера можно сделать строже
}

# Порог safe-mode по лагу минутных свечей (секунд)
CANDLES_1M_MAX_LAG = 120  # 2 минуты

# Пауза между проверками (секунд)
POLL_INTERVAL_SECONDS = 10

# --- Логирование ---

logger = logging.getLogger("health_monitor")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)


# --- Работа с БД ---

def get_connection():
    return psycopg2.connect(
        host=PG_CONFIG["host"],
        port=PG_CONFIG["port"],
        dbname=PG_CONFIG["dbname"],
        user=PG_CONFIG["user"],
        password=PG_CONFIG["password"],
    )


def log_error(conn, message: str, severity: str, source: str,
              details: Optional[Dict[str, Any]] = None):
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO live_errors (
                    timestamp, source, severity,
                    strategy_universe_id, symbol, timeframe,
                    message, details_json
                )
                VALUES (now(), %s, %s, NULL, NULL, NULL, %s, %s)
                """,
                (
                    source,
                    severity,
                    message,
                    Json(details) if details is not None else None,
                ),
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Не удалось записать ошибку в live_errors: {e}")


def get_service_status(conn, service_name: str) -> Optional[Dict[str, Any]]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT service_name, last_heartbeat, status, details_json
            FROM service_status
            WHERE service_name = %s
            """,
            (service_name,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)


def load_trading_control(conn) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT id, allow_trading, allow_new_positions, comment
            FROM trading_control
            WHERE id = 1
            """
        )
        row = cur.fetchone()
        if not row:
            return {"id": 1, "allow_trading": True, "allow_new_positions": True, "comment": None}
        return dict(row)


def save_trading_control(conn, allow_trading: bool, allow_new_positions: bool, comment: Optional[str]):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO trading_control (id, allow_trading, allow_new_positions, comment, updated_at)
            VALUES (1, %s, %s, %s, now())
            ON CONFLICT (id)
            DO UPDATE SET allow_trading = EXCLUDED.allow_trading,
                          allow_new_positions = EXCLUDED.allow_new_positions,
                          comment = EXCLUDED.comment,
                          updated_at = EXCLUDED.updated_at
            """,
            (allow_trading, allow_new_positions, comment),
        )
    conn.commit()


def get_latest_candles_1m_ts(conn) -> Optional[datetime]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT max(timestamp) AS max_ts FROM candles_1m")
        row = cur.fetchone()
        if not row or row["max_ts"] is None:
            return None
        ts = row["max_ts"]
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts


# --- Проверки ---

def check_service_heartbeat(conn, now_utc: datetime, service_name: str, timeout_sec: int):
    status = get_service_status(conn, service_name)
    if not status:
        # сервис ещё ни разу не писал heartbeat — можно просто предупредить
        logger.warning(f"service_status для {service_name} не найден")
        log_error(
            conn,
            message=f"{service_name}_status_missing",
            severity="warning",
            source="system",
            details=None,
        )
        return

    last_hb = status["last_heartbeat"]
    if last_hb.tzinfo is None:
        last_hb = last_hb.replace(tzinfo=timezone.utc)

    lag = (now_utc - last_hb).total_seconds()
    if lag > timeout_sec:
        # критический лаг
        logger.error(f"{service_name} down: lag={lag:.1f} sec > {timeout_sec}")
        log_error(
            conn,
            message=f"{service_name}_down",
            severity="critical",
            source="system",
            details={"service_name": service_name, "lag_seconds": lag},
        )

        # реакция для брокера/исполнения: стоп-торговля
        if service_name in ("fake_broker", "broker_adapter", "execution_engine"):
            tc = load_trading_control(conn)
            if tc["allow_trading"]:
                logger.warning("Устанавливаем allow_trading=false из-за падения брокера/исполнения")
                save_trading_control(
                    conn,
                    allow_trading=False,
                    allow_new_positions=False,
                    comment=f"auto stop-trading by health_monitor: {service_name}_down",
                )


def check_candles_1m_lag(conn, now_utc: datetime):
    latest_ts = get_latest_candles_1m_ts(conn)
    if latest_ts is None:
        logger.warning("Нет данных в candles_1m, пропускаем проверку лага")
        return

    lag = (now_utc - latest_ts).total_seconds()
    if lag > CANDLES_1M_MAX_LAG:
        logger.warning(f"Лаг минутных свечей {lag:.1f} sec > {CANDLES_1M_MAX_LAG}, включаем safe-mode")
        log_error(
            conn,
            message="bar_too_old",
            severity="warning",
            source="system",
            details={"lag_seconds": lag, "latest_ts": latest_ts.isoformat()},
        )

        # включаем safe-mode: запрещаем новые позиции, но не выключаем полностью торговлю
        tc = load_trading_control(conn)
        if tc["allow_new_positions"]:
            save_trading_control(
                conn,
                allow_trading=tc["allow_trading"],
                allow_new_positions=False,
                comment="safe-mode by health_monitor: candles_1m lag too high",
            )
    else:
        # если лаг пришёл в норму, можно (опционально) автоматически снять safe-mode
        tc = load_trading_control(conn)
        if not tc["allow_new_positions"]:
            logger.info("Лаг минуток нормализовался, можно разрешить новые позиции (выключить safe-mode)")
            save_trading_control(
                conn,
                allow_trading=tc["allow_trading"],
                allow_new_positions=True,
                comment="safe-mode disabled: candles_1m lag back to normal",
            )


# --- Основной цикл демона ---

def main_loop():
    conn = get_connection()
    conn.autocommit = False
    logger.info("Старт health_monitor")

    try:
        while True:
            try:
                now_utc = datetime.now(timezone.utc)

                # Проверка сервисов по heartbeat
                for service_name, timeout_sec in TIMEOUTS.items():
                    check_service_heartbeat(conn, now_utc, service_name, timeout_sec)

                # Проверка лага минуток
                check_candles_1m_lag(conn, now_utc)

                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.exception(f"Ошибка в health_monitor: {e}")
                log_error(
                    conn,
                    message="health_monitor_exception",
                    severity="error",
                    source="system",
                    details={"error": str(e)},
                )
                time.sleep(5)

            time.sleep(POLL_INTERVAL_SECONDS)

    finally:
        conn.close()
        logger.info("health_monitor остановлен")


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Остановка health_monitor по Ctrl+C")
