#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
execution_engine.py

Назначение:
    Модуль риск- и execution-логики: преобразует сигналы стратегий в заявки (live_orders)
    с учётом риск-профиля, глобальных флагов и текущего состояния счёта/позиций.

Цели:
    - Периодически опрашивать live_signals на предмет новых сигналов (processed = false).
    - Для каждого сигнала:
        * подтянуть strategy_universe (risk_per_trade, max_drawdown_fraction, mode, priority, symbol, timeframe, strategy_id);
        * проверить глобальные флаги trading_control (allow_trading, allow_new_positions);
        * подтянуть состояние счёта (account_state: equity, free_cash);
        * подтянуть позицию по стратегии/инструменту (live_positions) и lot_size инструмента (symbols);
        * применить риск-логику:
            - обработка типов сигналов (OPEN/CLOSE/REVERSE/ADD/MANUAL_CLOSE/FORCED_CLOSE);
            - проверка стопа: risk_span = |entry_price - stop_loss| / entry_price;
              если risk_span > max_drawdown_fraction (по умолчанию ~0.2) → отказ (too_wide_stop);
            - допустимая потеря: max_loss_money = risk_per_trade * equity (2% по умолчанию);
            - размер позиции: size_money = max_loss_money * size_value / risk_span;
              size_lots = floor(size_money / (entry_price * lot_size));
        * проверить глобальные лимиты:
            - allow_trading / allow_new_positions;
            - при желании — max_total_positions/max_positions_per_strategy (если заданы в strategy_universe);
            - достаточность free_cash.
        * сформировать заявку в live_orders (side, quantity, price, order_type, стоп/тейк как meta),
          со статусом 'NEW' или 'NOT_SENT' (если политика не отправлять автоматически).
    - Обновлять:
        * флаг processed / processed_at в live_signals;
        * service_status(service_name='execution_engine') — heartbeat и статус.
    - Любые ошибки и отказы записывать в live_errors с source='execution' или 'risk'.

Ключевые допущения:
    - Все timestamp в БД — UTC.
    - Пока не отправляем заявки реальному брокеру из этого модуля: он только пишет в live_orders,
      а брокерский адаптер (FakeBroker/Tinkoff) читает эти заявки отдельно.
    - MANUAL_CLOSE и FORCED_CLOSE проходят даже при allow_trading=false (ручной/форс-мажорный контроль).

Архитектура:
    - Один процесс с циклом:
        1. Читает пачку сигналов из live_signals (processed=false, отсортированных по времени).
        2. Для каждого сигнала применяет risk/execution-логику.
        3. Пишет заявки в live_orders и помечает сигнал как processed.
        4. Обновляет heartbeat в service_status.
        5. Спит заданный интервал и повторяет.
"""

import logging
import math
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import psycopg2
from psycopg2.extras import DictCursor, Json

# --- Конфиг подключения к PostgreSQL ---

PG_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "stock_db",
    "user": "postgres",
    "password": "123",
}

# Максимальное количество сигналов за одну итерацию
MAX_SIGNALS_PER_BATCH = 100

# Пауза между итерациями (секунд)
POLL_INTERVAL_SECONDS = 2

# --- Логирование ---

logger = logging.getLogger("execution_engine")
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


def log_error(conn, message: str, severity: str = "error", source: str = "execution",
              strategy_universe_id: Optional[int] = None,
              symbol: Optional[str] = None,
              timeframe: Optional[str] = None,
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
                VALUES ('execution_engine', now(), 'ok')
                ON CONFLICT (service_name)
                DO UPDATE SET last_heartbeat = EXCLUDED.last_heartbeat,
                              status = EXCLUDED.status
                """
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Не удалось обновить heartbeat execution_engine: {e}")


def load_trading_control(conn) -> Tuple[bool, bool]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT allow_trading, allow_new_positions FROM trading_control WHERE id = 1")
        row = cur.fetchone()
        if not row:
            return True, True
        return bool(row["allow_trading"]), bool(row["allow_new_positions"])


def load_account_state(conn) -> Tuple[float, float]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT equity, free_cash FROM account_state WHERE id = 1")
        row = cur.fetchone()
        if not row:
            # default
            return 0.0, 0.0
        return float(row["equity"]), float(row["free_cash"])


def load_symbol_info(conn, symbol: str) -> Tuple[Optional[int], int]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT id, lot_size FROM symbols WHERE ticker = %s", (symbol,))
        row = cur.fetchone()
        if not row:
            return None, 1
        return int(row["id"]), int(row["lot_size"])


def load_strategy_universe_row(conn, su_id: int):
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM strategy_universe
            WHERE id = %s
            """,
            (su_id,),
        )
        return cur.fetchone()


def load_position_for_strategy(conn, strategy_universe_id: int, symbol: str):
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT id, direction, quantity, avg_price, gap_mode
            FROM live_positions
            WHERE strategy_universe_id = %s
              AND symbol = %s
            """,
            (strategy_universe_id, symbol),
        )
        return cur.fetchone()


def count_open_positions(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM live_positions
            """
        )
        (cnt,) = cur.fetchone()
        return int(cnt)


def count_open_positions_for_strategy(conn, strategy_universe_id: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM live_positions
            WHERE strategy_universe_id = %s
            """,
            (strategy_universe_id,),
        )
        (cnt,) = cur.fetchone()
        return int(cnt)


def mark_signal_processed(conn, signal_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE live_signals
            SET processed = true,
                processed_at = now()
            WHERE id = %s
            """,
            (signal_id,),
        )


def insert_order(conn, live_signal_id: int, strategy_universe_id: int,
                 symbol: str, timeframe: str,
                 side: str, quantity: float, price: Optional[float],
                 order_type: str, status: str = "NEW"):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO live_orders (
                live_signal_id,
                strategy_universe_id,
                symbol,
                timeframe,
                side,
                quantity,
                price,
                order_type,
                status,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            """,
            (
                live_signal_id,
                strategy_universe_id,
                symbol,
                timeframe,
                side,
                quantity,
                price,
                order_type,
                status,
            ),
        )


# --- Основная логика обработки сигнала ---


def compute_order_size(equity: float,
                       free_cash: float,
                       risk_per_trade: float,
                       max_drawdown_fraction: float,
                       lot_size: int,
                       entry_price: float,
                       stop_loss: Optional[float],
                       size_mode: str,
                       size_value: float) -> Tuple[bool, str, Optional[int]]:
    """
    Возвращает (ok, reason, size_lots|None).
    ok = False → сигнал отклоняется с reason.
    """
    if size_mode != "RISK_FRACTION":
        return False, "unsupported_size_mode", None

    if entry_price is None or entry_price <= 0:
        return False, "invalid_entry_price", None

    if stop_loss is None or stop_loss <= 0:
        return False, "stop_loss_required", None

    risk_span = abs(entry_price - stop_loss) / entry_price
    if risk_span <= 0:
        return False, "invalid_risk_span", None

    # Проверка "слишком широкий стоп": используем max_drawdown_fraction
    if max_drawdown_fraction is not None and risk_span > max_drawdown_fraction:
        return False, "too_wide_stop", None

    if risk_per_trade is None or risk_per_trade <= 0:
        return False, "invalid_risk_per_trade", None

    max_loss_money = equity * risk_per_trade
    # доля от risk_per_trade, заданная сигналом (0..1)
    size_fraction = max(0.0, min(size_value, 1.0))
    effective_loss = max_loss_money * size_fraction

    size_money = effective_loss / risk_span
    if size_money <= 0:
        return False, "size_money_non_positive", None

    # размер позиции в бумагах
    size_units = size_money / entry_price
    # и в лотах, с округлением вниз
    size_lots = math.floor(size_units / lot_size) if lot_size > 0 else math.floor(size_units)

    if size_lots <= 0:
        return False, "size_too_small", None

    # проверка по free_cash: простой: на покупку должно хватить денег
    # (для продажи/SHORT логика может отличаться)
    required_cash = size_lots * lot_size * entry_price
    if required_cash > free_cash:
        return False, "insufficient_cash", None

    return True, "ok", size_lots


def process_signal(conn, signal_row):
    """
    Обработка одного сигнала из live_signals.
    """
    signal_id = signal_row["id"]
    su_id = signal_row["strategy_universe_id"]
    symbol = signal_row["symbol"]
    timeframe = signal_row["timeframe"]
    signal_type = signal_row["signal_type"]
    signal_source = signal_row["signal_source"]
    signal_json = signal_row["signal_json"]

    # MANUAL_CLOSE / FORCED_CLOSE должны работать всегда,
    # даже при allow_trading=false, но надо проверить allow_trading позже
    allow_trading, allow_new_positions = load_trading_control(conn)

    su_row = load_strategy_universe_row(conn, su_id)
    if not su_row:
        log_error(
            conn,
            message="strategy_universe row not found",
            severity="error",
            source="execution",
            strategy_universe_id=su_id,
            symbol=symbol,
            timeframe=timeframe,
            details={"live_signal_id": signal_id},
        )
        mark_signal_processed(conn, signal_id)
        return

    mode = su_row["mode"]
    risk_per_trade = su_row.get("risk_per_trade")
    max_dd_frac = su_row.get("max_drawdown_fraction")
    max_positions_per_strategy = su_row.get("max_positions_per_strategy")
    max_total_positions = su_row.get("max_total_positions")

    equity, free_cash = load_account_state(conn)
    symbol_id, lot_size = load_symbol_info(conn, symbol)
    pos_row = load_position_for_strategy(conn, su_id, symbol)

    # Глобальные лимиты new positions
    total_open_positions = count_open_positions(conn)
    open_for_strategy = count_open_positions_for_strategy(conn, su_id)

    # Разбор сигнала
    signal_data = signal_json or {}
    s_type = signal_data.get("type") or signal_type
    direction = signal_data.get("direction")
    entry_type = signal_data.get("entry_type", "MARKET")
    entry_price = signal_data.get("entry_price")
    stop_loss = signal_data.get("stop_loss")
    take_profit = signal_data.get("take_profit")
    size_mode = signal_data.get("size_mode", "RISK_FRACTION")
    size_value = float(signal_data.get("size_value", 1.0))

    is_manual_close = s_type in ("MANUAL_CLOSE",)
    is_forced_close = s_type in ("FORCED_CLOSE",)

    # Проверка allow_trading / allow_new_positions
    if not allow_trading and not (is_manual_close or is_forced_close):
        log_error(
            conn,
            message="trading_disabled_by_control",
            severity="info",
            source="execution",
            strategy_universe_id=su_id,
            symbol=symbol,
            timeframe=timeframe,
            details={"live_signal_id": signal_id},
        )
        mark_signal_processed(conn, signal_id)
        return

    if not allow_new_positions and s_type in ("OPEN", "ADD", "REVERSE") and not (is_manual_close or is_forced_close):
        log_error(
            conn,
            message="new_positions_disabled_by_control",
            severity="info",
            source="execution",
            strategy_universe_id=su_id,
            symbol=symbol,
            timeframe=timeframe,
            details={"live_signal_id": signal_id, "signal_type": s_type},
        )
        mark_signal_processed(conn, signal_id)
        return

    # Ветки по типу сигнала
    if s_type in ("OPEN", "ADD", "REVERSE"):
        # Лимиты по позициям
        if max_total_positions is not None and total_open_positions >= max_total_positions:
            log_error(
                conn,
                message="max_total_positions_reached",
                severity="warning",
                source="risk",
                strategy_universe_id=su_id,
                symbol=symbol,
                timeframe=timeframe,
                details={"live_signal_id": signal_id},
            )
            mark_signal_processed(conn, signal_id)
            return

        if max_positions_per_strategy is not None and open_for_strategy >= max_positions_per_strategy:
            log_error(
                conn,
                message="max_positions_per_strategy_reached",
                severity="warning",
                source="risk",
                strategy_universe_id=su_id,
                symbol=symbol,
                timeframe=timeframe,
                details={"live_signal_id": signal_id},
            )
            mark_signal_processed(conn, signal_id)
            return

        ok, reason, size_lots = compute_order_size(
            equity=equity,
            free_cash=free_cash,
            risk_per_trade=risk_per_trade or 0.0,
            max_drawdown_fraction=max_dd_frac or 0.2,
            lot_size=lot_size,
            entry_price=entry_price,
            stop_loss=stop_loss,
            size_mode=size_mode,
            size_value=size_value,
        )
        if not ok or size_lots is None:
            log_error(
                conn,
                message=f"signal_rejected: {reason}",
                severity="warning",
                source="risk",
                strategy_universe_id=su_id,
                symbol=symbol,
                timeframe=timeframe,
                details={
                    "live_signal_id": signal_id,
                    "reason": reason,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                },
            )
            mark_signal_processed(conn, signal_id)
            return

        # side из direction
        if direction == "LONG":
            side = "BUY"
        elif direction == "SHORT":
            side = "SELL"
        else:
            log_error(
                conn,
                message="invalid_direction_for_open",
                severity="warning",
                source="execution",
                strategy_universe_id=su_id,
                symbol=symbol,
                timeframe=timeframe,
                details={"live_signal_id": signal_id, "direction": direction},
            )
            mark_signal_processed(conn, signal_id)
            return

        insert_order(
            conn,
            live_signal_id=signal_id,
            strategy_universe_id=su_id,
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            quantity=size_lots * lot_size,
            price=entry_price if entry_type != "MARKET" else None,
            order_type=entry_type,
            status="NEW",
        )
        mark_signal_processed(conn, signal_id)

    elif s_type in ("CLOSE", "MANUAL_CLOSE", "FORCED_CLOSE"):
        # закрытие позиции (полное)
        if not pos_row:
            # нет позиции — нечего закрывать
            log_error(
                conn,
                message="close_without_position",
                severity="info",
                source="execution",
                strategy_universe_id=su_id,
                symbol=symbol,
                timeframe=timeframe,
                details={"live_signal_id": signal_id, "signal_type": s_type},
            )
            mark_signal_processed(conn, signal_id)
            return

        pos_direction = pos_row["direction"]
        pos_qty = float(pos_row["quantity"])
        if pos_qty <= 0:
            mark_signal_processed(conn, signal_id)
            return

        if pos_direction == "LONG":
            side = "SELL"
        elif pos_direction == "SHORT":
            side = "BUY"
        else:
            mark_signal_processed(conn, signal_id)
            return

        # закрываем по MARKET, цену может выставить брокер/фейк-брокер
        insert_order(
            conn,
            live_signal_id=signal_id,
            strategy_universe_id=su_id,
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            quantity=pos_qty,
            price=None,
            order_type="MARKET",
            status="NEW",
        )
        mark_signal_processed(conn, signal_id)

    else:
        # неизвестный тип сигнала
        log_error(
            conn,
            message="unknown_signal_type",
            severity="warning",
            source="execution",
            strategy_universe_id=su_id,
            symbol=symbol,
            timeframe=timeframe,
            details={"live_signal_id": signal_id, "signal_type": s_type},
        )
        mark_signal_processed(conn, signal_id)


# --- Основной цикл демона ---

def main_loop():
    conn = get_connection()
    conn.autocommit = False
    logger.info("Старт execution_engine")

    try:
        while True:
            try:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM live_signals
                        WHERE processed = false
                        ORDER BY signal_timestamp
                        LIMIT %s
                        """,
                        (MAX_SIGNALS_PER_BATCH,),
                    )
                    signals = cur.fetchall()

                if not signals:
                    update_service_heartbeat(conn)
                    conn.commit()
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                logger.info(f"Новых сигналов: {len(signals)}")

                for s in signals:
                    try:
                        process_signal(conn, s)
                    except Exception as e:
                        conn.rollback()
                        logger.exception(f"Ошибка при обработке сигнала id={s['id']}: {e}")
                        log_error(
                            conn,
                            message="Ошибка при обработке сигнала в execution_engine",
                            severity="error",
                            source="execution",
                            strategy_universe_id=s["strategy_universe_id"],
                            symbol=s["symbol"],
                            timeframe=s["timeframe"],
                            details={"live_signal_id": s["id"], "error": str(e)},
                        )
                        # после rollback надо пометить сигнал processed, чтобы не зациклиться
                        mark_signal_processed(conn, s["id"])

                update_service_heartbeat(conn)
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.exception(f"Ошибка в основном цикле execution_engine: {e}")
                log_error(
                    conn,
                    message="Ошибка в основном цикле execution_engine",
                    severity="error",
                    source="execution",
                    details={"error": str(e)},
                )
                time.sleep(5)

            time.sleep(POLL_INTERVAL_SECONDS)

    finally:
        conn.close()
        logger.info("execution_engine остановлен")


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Остановка execution_engine по Ctrl+C")
