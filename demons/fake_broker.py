#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fake_broker.py

Назначение:
    Фейковый брокерский адаптер для симуляции исполнения заявок:
    читает заявки из live_orders, исполняет их по ценам из свечей,
    обновляет live_trades, live_positions, account_state и статусы заявок.

Цели:
    - Периодически опрашивать live_orders на предмет новых заявок (status='NEW').
    - Для каждой заявки:
        * определить текущую рыночную цену по инструменту (из candles_1m);
        * смоделировать исполнение (полное fill по MARKET, для LIMIT/STOP — простое правило);
        * записать сделку(и) в live_trades;
        * обновить live_positions (размер, среднюю цену, направление, last_price, unrealized/realized PnL);
        * обновить account_state (equity/free_cash/used_margin по простой модели кэша + mark-to-market);
        * изменить статус live_orders на 'FILLED' / 'REJECTED' и т.п.
    - Обрабатывать ошибки:
        * логировать в live_errors с source='broker';
        * не останавливать основной цикл.
    - Обновлять heartbeat в service_status(service_name='fake_broker').

Ключевые допущения:
    - Все timestamp в БД — UTC.
    - Для MARKET-заявок используем последнюю 1m свечу (close).
    - Для LIMIT/STOP пока тоже исполняем по market_price (упрощение).
    - Комиссия fee моделируется как FEE_RATE от объёма сделки.
"""

import logging
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

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

# Параметры работы демона
POLL_INTERVAL_SECONDS = 2
MAX_ORDERS_PER_BATCH = 100

# Простая модель комиссии (например, 0.01% от объёма сделки)
FEE_RATE = 0.0001

# --- Логирование ---

logger = logging.getLogger("fake_broker")
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


def log_error(
    conn,
    message: str,
    severity: str = "error",
    source: str = "broker",
    strategy_universe_id: Optional[int] = None,
    symbol: Optional[str] = None,
    timeframe: Optional[str] = None,
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
                VALUES ('fake_broker', now(), 'ok')
                ON CONFLICT (service_name)
                DO UPDATE SET last_heartbeat = EXCLUDED.last_heartbeat,
                              status = EXCLUDED.status
                """
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Не удалось обновить heartbeat fake_broker: {e}")


def load_account_state(conn) -> Tuple[float, float, float]:
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            "SELECT equity, free_cash, used_margin FROM account_state WHERE id = 1"
        )
        row = cur.fetchone()
    if not row:
        return 0.0, 0.0, 0.0
    return float(row["equity"]), float(row["free_cash"]), float(row["used_margin"])


def save_account_state(conn, equity: float, free_cash: float, used_margin: float):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO account_state (id, equity, free_cash, used_margin, updated_at)
            VALUES (1, %s, %s, %s, now())
            ON CONFLICT (id)
            DO UPDATE SET equity = EXCLUDED.equity,
                          free_cash = EXCLUDED.free_cash,
                          used_margin = EXCLUDED.used_margin,
                          updated_at = EXCLUDED.updated_at
            """,
            (equity, free_cash, used_margin),
        )
    conn.commit()


def load_last_price_from_candles(conn, symbol: str) -> Optional[float]:
    """
    Находим последнюю цену (close) из candles_1m по тикеру.
    """
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute("SELECT id FROM symbols WHERE ticker = %s", (symbol,))
        row = cur.fetchone()
        if not row:
            return None
        symbol_id = row["id"]

        cur.execute(
            """
            SELECT close
            FROM candles_1m
            WHERE symbol_id = %s
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (symbol_id,),
        )
        row = cur.fetchone()

    if not row:
        return None
    return float(row["close"])


def load_position(conn, strategy_universe_id: int, symbol: str):
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT id, direction, quantity, avg_price, realized_pnl
            FROM live_positions
            WHERE strategy_universe_id = %s AND symbol = %s
            """,
            (strategy_universe_id, symbol),
        )
        return cur.fetchone()


def upsert_position_after_trade(
    conn,
    strategy_universe_id: int,
    symbol: str,
    timeframe: str,
    side: str,
    quantity: float,
    price: float,
):
    """
    Обновляем live_positions по результату сделки.

    Простая модель:
    - LONG позиция: BUY увеличивает/открывает, SELL уменьшает/закрывает.
    - SHORT позиция: SELL открывает/увеличивает, BUY уменьшает/закрывает.
    """
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(
            """
            SELECT id, direction, quantity, avg_price, realized_pnl
            FROM live_positions
            WHERE strategy_universe_id = %s AND symbol = %s
            FOR UPDATE
            """,
            (strategy_universe_id, symbol),
        )
        row = cur.fetchone()

        now_ts = datetime.now(timezone.utc)

        if row is None:
            # нет позиции — открываем новую
            direction = "LONG" if side == "BUY" else "SHORT"
            qty = quantity
            avg_price = price
            realized_pnl = 0.0

            cur.execute(
                """
                INSERT INTO live_positions (
                    strategy_universe_id,
                    symbol,
                    timeframe,
                    direction,
                    quantity,
                    avg_price,
                    last_price,
                    unrealized_pnl,
                    realized_pnl,
                    gap_mode,
                    opened_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, false, %s, %s)
                """,
                (
                    strategy_universe_id,
                    symbol,
                    timeframe,
                    direction,
                    qty,
                    avg_price,
                    price,
                    realized_pnl,
                    now_ts,
                    now_ts,
                ),
            )
            return

        # существующая позиция
        pos_id = row["id"]
        direction = row["direction"]
        qty = float(row["quantity"])
        avg_price = float(row["avg_price"])
        realized_pnl = float(row["realized_pnl"])

        if direction == "LONG":
            if side == "BUY":
                # добавляем к LONG
                new_qty = qty + quantity
                new_avg = (avg_price * qty + price * quantity) / new_qty
                qty = new_qty
                avg_price = new_avg
            else:  # SELL
                # закрываем часть LONG
                close_qty = min(qty, quantity)
                pnl = (price - avg_price) * close_qty
                realized_pnl += pnl
                qty = qty - close_qty
                if qty == 0:
                    # позиция полностью закрыта
                    cur.execute(
                        """
                        UPDATE live_positions
                        SET direction = 'FLAT',
                            quantity = 0,
                            avg_price = 0,
                            last_price = %s,
                            unrealized_pnl = 0,
                            realized_pnl = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (price, realized_pnl, now_ts, pos_id),
                    )
                    return

        elif direction == "SHORT":
            if side == "SELL":
                # увеличиваем SHORT
                new_qty = qty + quantity
                new_avg = (avg_price * qty + price * quantity) / new_qty
                qty = new_qty
                avg_price = new_avg
            else:  # BUY
                close_qty = min(qty, quantity)
                pnl = (avg_price - price) * close_qty
                realized_pnl += pnl
                qty = qty - close_qty
                if qty == 0:
                    cur.execute(
                        """
                        UPDATE live_positions
                        SET direction = 'FLAT',
                            quantity = 0,
                            avg_price = 0,
                            last_price = %s,
                            unrealized_pnl = 0,
                            realized_pnl = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        (price, realized_pnl, now_ts, pos_id),
                    )
                    return
        else:
            # FLAT -> открываем новую позицию
            direction = "LONG" if side == "BUY" else "SHORT"
            qty = quantity
            avg_price = price

        # обновляем существующую позицию
        cur.execute(
            """
            UPDATE live_positions
            SET direction = %s,
                quantity = %s,
                avg_price = %s,
                last_price = %s,
                unrealized_pnl = 0,
                realized_pnl = %s,
                updated_at = %s
            WHERE id = %s
            """,
            (direction, qty, avg_price, price, realized_pnl, now_ts, pos_id),
        )


def insert_trade(
    conn,
    live_order_id: int,
    strategy_universe_id: int,
    symbol: str,
    timeframe: Optional[str],
    side: str,
    quantity: float,
    price: float,
    fee: float,
    trade_type: str,
):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO live_trades (
                live_order_id,
                strategy_universe_id,
                symbol,
                timeframe,
                side,
                quantity,
                price,
                fee,
                executed_at,
                trade_type,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s, now())
            """,
            (
                live_order_id,
                strategy_universe_id,
                symbol,
                timeframe,
                side,
                quantity,
                price,
                fee,
                trade_type,
            ),
        )


def update_order_status(
    conn, order_id: int, new_status: str, broker_order_id: Optional[str] = None
):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE live_orders
            SET status = %s,
                broker_order_id = COALESCE(%s, broker_order_id),
                updated_at = now()
            WHERE id = %s
            """,
            (new_status, broker_order_id, order_id),
        )


# --- Основная логика исполнения заявки ---


def execute_order(conn, order_row):
    """
    "Исполняет" одну заявку из live_orders.
    Простая модель: MARKET/LIMIT/STOP — исполняются по последней цене.
    """
    order_id = order_row["id"]
    su_id = order_row["strategy_universe_id"]
    symbol = order_row["symbol"]
    timeframe = order_row["timeframe"]
    side = order_row["side"]  # 'BUY' / 'SELL'
    qty = float(order_row["quantity"])
    order_type = order_row["order_type"]
    price_hint = order_row["price"]

    # текущая рыночная цена
    market_price = load_last_price_from_candles(conn, symbol)
    if market_price is None:
        log_error(
            conn,
            message="no_market_price_for_symbol",
            severity="warning",
            source="broker",
            strategy_universe_id=su_id,
            symbol=symbol,
            timeframe=timeframe,
            details={"order_id": order_id},
        )
        update_order_status(conn, order_id, "REJECTED")
        return

    # определяем цену исполнения
    if order_type == "MARKET":
        exec_price = market_price
    elif order_type in ("LIMIT", "STOP"):
        # упрощение: исполняем по market_price
        exec_price = market_price
    else:
        log_error(
            conn,
            message="unsupported_order_type",
            severity="warning",
            source="broker",
            strategy_universe_id=su_id,
            symbol=symbol,
            timeframe=timeframe,
            details={"order_id": order_id, "order_type": order_type},
        )
        update_order_status(conn, order_id, "REJECTED")
        return

    # комиссия
    notional = exec_price * qty
    fee = notional * FEE_RATE

    # обновляем позиции (важно: передаём timeframe, чтобы не было NULL)
    upsert_position_after_trade(
        conn,
        strategy_universe_id=su_id,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        quantity=qty,
        price=exec_price,
    )

    # обновляем account_state (упрощённо: кэш +/- notional -/+ fee)
    equity, free_cash, used_margin = load_account_state(conn)
    if side == "BUY":
        free_cash -= notional + fee
    else:  # SELL
        free_cash += notional - fee

    # очень грубая модель equity
    equity = free_cash + used_margin
    save_account_state(conn, equity, free_cash, used_margin)

    # записываем сделку
    insert_trade(
        conn,
        live_order_id=order_id,
        strategy_universe_id=su_id,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        quantity=qty,
        price=exec_price,
        fee=fee,
        trade_type="FILL",
    )

    # обновляем статус ордера
    update_order_status(conn, order_id, "FILLED", broker_order_id=f"fake-{order_id}")


# --- Основной цикл демона ---


def main_loop():
    conn = get_connection()
    conn.autocommit = False
    logger.info("Старт fake_broker")

    try:
        while True:
            try:
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM live_orders
                        WHERE status = 'NEW'
                        ORDER BY created_at
                        LIMIT %s
                        """,
                        (MAX_ORDERS_PER_BATCH,),
                    )
                    orders = cur.fetchall()

                if not orders:
                    update_service_heartbeat(conn)
                    conn.commit()
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                logger.info(f"Новых заявок: {len(orders)}")

                for order in orders:
                    try:
                        execute_order(conn, order)
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        logger.exception(
                            f"Ошибка при исполнении заявки id={order['id']}: {e}"
                        )
                        log_error(
                            conn,
                            message="Ошибка при исполнении заявки в fake_broker",
                            severity="error",
                            source="broker",
                            strategy_universe_id=order["strategy_universe_id"],
                            symbol=order["symbol"],
                            timeframe=order["timeframe"],
                            details={"order_id": order["id"], "error": str(e)},
                        )
                        # помечаем ордер REJECTED, чтобы не зациклиться
                        update_order_status(conn, order["id"], "REJECTED")
                        conn.commit()

                update_service_heartbeat(conn)
                conn.commit()

            except Exception as e:
                conn.rollback()
                logger.exception(f"Ошибка в основном цикле fake_broker: {e}")
                log_error(
                    conn,
                    message="Ошибка в основном цикле fake_broker",
                    severity="error",
                    source="broker",
                    details={"error": str(e)},
                )
                time.sleep(5)

            time.sleep(POLL_INTERVAL_SECONDS)

    finally:
        conn.close()
        logger.info("fake_broker остановлен")


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Остановка fake_broker по Ctrl+C")
