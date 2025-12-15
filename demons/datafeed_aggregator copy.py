#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
datafeed_aggregator.py

Назначение:
    Демон агрегации минутных свечей в старшие таймфреймы и детектор гэпов.

Цели:
    - Читать новые минутные свечи из таблицы candles_1m (UTC).
    - В режиме онлайн собирать агрегированные бары 5m/15m/30m/1h/4h/1d
      и записывать их в соответствующие таблицы candles_5m, candles_15m, ... .
    - Для каждого нового закрытого бара считать относительное изменение цены
      относительно предыдущего бара данного таймфрейма и отмечать гэпы:
        * is_gap = true, если |close_t - close_{t-1}| / close_{t-1} >= gap_threshold.
        * gap_dir = 'UP' / 'DOWN' в зависимости от направления.
    - При обнаружении гэпа против открытой позиции:
        * находить позиции по инструменту в live_positions;
        * если LONG и gap DOWN, либо SHORT и gap UP, ставить gap_mode = true.
    - Вести состояние:
        * datafeed_state.last_1m_timestamp — последний обработанный timestamp из candles_1m.
        * service_status(service_name='data_feed') — heartbeat и статус сервиса.
    - Логировать ошибки в stdout/файл и в таблицу live_errors (source='data_feed').

Ключевые допущения:
    - Все timestamp в свечах — в UTC.
    - Таблицы свечей имеют схему:
        candles_1m(symbol_id, timestamp, open, high, low, close, volume, ...)
        candles_5m/... аналогично + поля is_gap boolean, gap_dir text.
    - Таблица live_positions содержит хотя бы:
        (id, symbol, direction, gap_mode, updated_at, ...).
    - Таблицы datafeed_state, service_status, live_errors уже созданы миграцией.

Архитектура:
    - Один процесс с бесконечным циклом:
        1. Читает новые записи из candles_1m после datafeed_state.last_1m_timestamp.
        2. Для каждой минутки обновляет in-memory агрегаты по всем нужным ТФ.
        3. При закрытии бара:
            - пишет бар в candles_xx с is_gap/gap_dir;
            - при is_gap=true вызывает обновление live_positions.gap_mode (если гэп против позиции).
        4. Обновляет datafeed_state и heartbeat в service_status.
        5. Спит заданный интервал и повторяет.
    - Любые ошибки ловятся, пишутся в live_errors и лог, цикл не падает насмерть.
"""

import logging
import sys
import time
from datetime import datetime, timedelta, timezone

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

# --- Конфиг таймфреймов ---

TIMEFRAMES = {
    "5m":  {"minutes": 5,   "table": "candles_5m"},
    "15m": {"minutes": 15,  "table": "candles_15m"},
    "30m": {"minutes": 30,  "table": "candles_30m"},
    "1h":  {"minutes": 60,  "table": "candles_1h"},
    "4h":  {"minutes": 240, "table": "candles_4h"},
    "1d":  {"minutes": 1440, "table": "candles_1d"},
}

# Порог гэпа: если относительное изменение цены >= 20%
DEFAULT_GAP_THRESHOLD = 0.20

# Пауза между итерациями чтения минуток (секунд)
POLL_INTERVAL_SECONDS = 3

# --- Логирование ---

logger = logging.getLogger("datafeed_aggregator")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)


# --- Вспомогательные структуры in-memory ---


class AggregatedBar:
    """Строящийся бар агрегированного таймфрейма."""

    __slots__ = (
        "symbol_id",
        "start_ts",
        "end_ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )

    def __init__(self, symbol_id, start_ts, end_ts, open_, high_, low_, close_, volume_):
        self.symbol_id = symbol_id
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.open = open_
        self.high = high_
        self.low = low_
        self.close = close_
        self.volume = volume_

    def update_with_minute(self, open_, high_, low_, close_, volume_):
        if self.open is None:
            self.open = open_
        self.high = max(self.high, high_)
        self.low = min(self.low, low_)
        self.close = close_
        self.volume += volume_


# current_bars[tf_name][symbol_id] = AggregatedBar(...)
current_bars = {
    tf_name: {} for tf_name in TIMEFRAMES.keys()
}

# last_closed_close[tf_name][symbol_id] = last_close_price
last_closed_close = {
    tf_name: {} for tf_name in TIMEFRAMES.keys()
}


# --- Работа с БД ---


def get_connection():
    return psycopg2.connect(
        host=PG_CONFIG["host"],
        port=PG_CONFIG["port"],
        dbname=PG_CONFIG["dbname"],
        user=PG_CONFIG["user"],
        password=PG_CONFIG["password"],
    )


def log_error(conn, message, severity="error", source="data_feed",
              strategy_universe_id=None, symbol=None, timeframe=None, details=None):
    """Запись ошибки/события в live_errors."""
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
    """Обновление heartbeat сервиса data_feed в service_status."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO service_status (service_name, last_heartbeat, status)
                VALUES ('data_feed', now(), 'ok')
                ON CONFLICT (service_name)
                DO UPDATE SET last_heartbeat = EXCLUDED.last_heartbeat,
                              status = EXCLUDED.status
                """
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Не удалось обновить heartbeat в service_status: {e}")


def get_gap_threshold(conn):
    """Пока используем глобальный порог гэпа; дальше можно сделать конфигурируемым."""
    return DEFAULT_GAP_THRESHOLD


def load_last_state(conn):
    """Загрузка последнего обработанного timestamp 1m и последних close для агрегатов."""
    last_1m_ts = None
    with conn.cursor(cursor_factory=DictCursor) as cur:
        # datafeed_state
        cur.execute("SELECT last_1m_timestamp FROM datafeed_state WHERE id = 1")
        row = cur.fetchone()
        if row and row["last_1m_timestamp"] is not None:
            last_1m_ts = row["last_1m_timestamp"]

        # последние close по каждому TF и symbol_id
        for tf_name, cfg in TIMEFRAMES.items():
            table = cfg["table"]
            cur.execute(
                f"""
                SELECT DISTINCT ON (symbol_id) symbol_id, close
                FROM {table}
                ORDER BY symbol_id, timestamp DESC
                """
            )
            rows = cur.fetchall()
            for r in rows:
                last_closed_close[tf_name][r["symbol_id"]] = float(r["close"])

    return last_1m_ts


def save_last_1m_timestamp(conn, ts):
    """Сохраняем последний обработанный минутный timestamp в datafeed_state."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO datafeed_state (id, last_1m_timestamp, updated_at)
            VALUES (1, %s, now())
            ON CONFLICT (id)
            DO UPDATE SET last_1m_timestamp = EXCLUDED.last_1m_timestamp,
                          updated_at = EXCLUDED.updated_at
            """,
            (ts,),
        )
    conn.commit()


# --- Логика агрегации и гэпов ---


def floor_timestamp_to_bucket(ts: datetime, minutes: int) -> datetime:
    """
    Округление timestamp вниз до начала интервала длиной minutes.
    Предполагается, что ts в UTC (aware).
    """
    if minutes >= 1440:
        # дневной бар: начало дня по UTC
        return datetime(ts.year, ts.month, ts.day, tzinfo=timezone.utc)
    total_minutes = ts.hour * 60 + ts.minute
    bucket_start_minutes = (total_minutes // minutes) * minutes
    hour = bucket_start_minutes // 60
    minute = bucket_start_minutes % 60
    return datetime(ts.year, ts.month, ts.day, hour, minute, tzinfo=timezone.utc)


def get_bucket_end(start_ts: datetime, minutes: int) -> datetime:
    """Вычислить конец интервала (исключительная правая граница) для таймфрейма."""
    return start_ts + timedelta(minutes=minutes)


def process_closed_bar(conn, tf_name, cfg, bar: AggregatedBar, gap_threshold):
    """
    Обработка закрытого агрегированного бара:
    - вычисление гэпа;
    - запись в таблицу candles_xx;
    - при необходимости обновление live_positions.gap_mode.
    """
    table = cfg["table"]
    symbol_id = bar.symbol_id
    close_price = bar.close
    prev_close = last_closed_close[tf_name].get(symbol_id)

    is_gap = False
    gap_dir = None

    if prev_close is not None and prev_close > 0:
        change = abs(close_price - prev_close) / prev_close
        if change >= gap_threshold:
            is_gap = True
            gap_dir = "UP" if close_price > prev_close else "DOWN"

    # записываем бар в таблицу candles_xx (timestamp = bar.end_ts)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {table} (
                symbol_id, timestamp,
                open, high, low, close, volume,
                is_gap, gap_dir
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                symbol_id,
                bar.end_ts,  # timestamp закрытия бара
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                is_gap,
                gap_dir,
            ),
        )

    last_closed_close[tf_name][symbol_id] = close_price

    if is_gap:
        mark_gap_positions(conn, symbol_id, gap_dir)


def mark_gap_positions(conn, symbol_id, gap_dir):
    """
    При гэпе против позиции помечаем gap_mode = true в live_positions.

    Предполагается:
      - live_positions.symbol хранит тикер;
      - candles_xx.symbol_id -> symbols.id, так что нужен маппинг id -> ticker.
    """
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # находим тикер по symbol_id
            cur.execute("SELECT ticker FROM symbols WHERE id = %s", (symbol_id,))
            row = cur.fetchone()
            if not row:
                return
            ticker = row["ticker"]

            # выбираем позиции по этому тикеру
            cur.execute(
                """
                SELECT id, direction
                FROM live_positions
                WHERE symbol = %s
                """,
                (ticker,),
            )
            rows = cur.fetchall()
            if not rows:
                return

            to_mark = []
            for r in rows:
                direction = r["direction"]
                # LONG и gap DOWN, либо SHORT и gap UP
                if (direction == "LONG" and gap_dir == "DOWN") or (
                    direction == "SHORT" and gap_dir == "UP"
                ):
                    to_mark.append(r["id"])

            if to_mark:
                cur.execute(
                    """
                    UPDATE live_positions
                    SET gap_mode = true,
                        updated_at = now()
                    WHERE id = ANY(%s)
                    """,
                    (to_mark,),
                )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при обновлении gap_mode в live_positions: {e}")
        log_error(
            conn,
            message="Ошибка mark_gap_positions",
            severity="error",
            source="data_feed",
            details={"symbol_id": symbol_id, "gap_dir": gap_dir, "error": str(e)},
        )


def process_minute_bar(conn, row, gap_threshold):
    """
    Обработка одной минутной свечи:
    - обновление агрегатов по всем TF;
    - закрытие баров, если нужно.

    row: DictRow из candles_1m (symbol_id, timestamp, open, high, low, close, volume).
    """
    symbol_id = row["symbol_id"]
    ts = row["timestamp"]
    # гарантируем UTC-aware
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    o = float(row["open"])
    h = float(row["high"])
    l = float(row["low"])
    c = float(row["close"])
    v = float(row["volume"])

    for tf_name, cfg in TIMEFRAMES.items():
        minutes = cfg["minutes"]
        bucket_start = floor_timestamp_to_bucket(ts, minutes)
        bucket_end = get_bucket_end(bucket_start, minutes)

        current = current_bars[tf_name].get(symbol_id)

        # если нет текущего бара — создаём
        if current is None:
            current = AggregatedBar(
                symbol_id=symbol_id,
                start_ts=bucket_start,
                end_ts=bucket_end,
                open_=o,
                high_=h,
                low_=l,
                close_=c,
                volume_=v,
            )
            current_bars[tf_name][symbol_id] = current
        else:
            # если пришла минутка уже в следующем/дальнейшем интервале — закрываем и создаём новый
            if ts >= current.end_ts:
                process_closed_bar(conn, tf_name, cfg, current, gap_threshold)
                current = AggregatedBar(
                    symbol_id=symbol_id,
                    start_ts=bucket_start,
                    end_ts=bucket_end,
                    open_=o,
                    high_=h,
                    low_=l,
                    close_=c,
                    volume_=v,
                )
                current_bars[tf_name][symbol_id] = current
            else:
                # всё ещё внутри текущего интервала — просто обновляем
                current.update_with_minute(o, h, l, c, v)


# --- Основной цикл демона ---


def main_loop():
    conn = get_connection()
    conn.autocommit = False

    try:
        logger.info("Старт datafeed_aggregator")
        gap_threshold = get_gap_threshold(conn)

        last_1m_ts = load_last_state(conn)
        # приводим last_1m_ts к UTC-aware, чтобы не было сравнения naive/aware
        if last_1m_ts is not None and last_1m_ts.tzinfo is None:
            last_1m_ts = last_1m_ts.replace(tzinfo=timezone.utc)

        if last_1m_ts is None:
            # если ещё не обрабатывали ничего — берём минимум из candles_1m - 1 минуту (чтобы не пропустить)
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT min(timestamp) AS min_ts FROM candles_1m")
                row = cur.fetchone()
                if row and row["min_ts"] is not None:
                    ts0 = row["min_ts"]
                    if ts0.tzinfo is None:
                        ts0 = ts0.replace(tzinfo=timezone.utc)
                    last_1m_ts = ts0 - timedelta(minutes=1)
                else:
                    last_1m_ts = datetime.now(timezone.utc) - timedelta(days=1)

        logger.info(f"Начальный last_1m_timestamp = {last_1m_ts}")

        save_last_1m_timestamp(conn, last_1m_ts)
        update_service_heartbeat(conn)

        while True:
            try:
                # читаем новые минутки
                with conn.cursor(cursor_factory=DictCursor) as cur:
                    cur.execute(
                        """
                        SELECT symbol_id, timestamp, open, high, low, close, volume
                        FROM candles_1m
                        WHERE timestamp > %s
                        ORDER BY timestamp, symbol_id
                        """,
                        (last_1m_ts,),
                    )
                    rows = cur.fetchall()

                if rows:
                    logger.info(f"Новых минутных свечей: {len(rows)}")
                    for row in rows:
                        ts = row["timestamp"]
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)

                        # обновляем last_1m_ts (оба aware)
                        if last_1m_ts is None or ts > last_1m_ts:
                            last_1m_ts = ts

                        process_minute_bar(conn, row, gap_threshold)

                    # сохраняем прогресс и heartbeat
                    save_last_1m_timestamp(conn, last_1m_ts)
                    update_service_heartbeat(conn)
                else:
                    # если нет новых данных — просто обновим heartbeat
                    update_service_heartbeat(conn)

                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.exception(f"Ошибка в основном цикле обработки минуток: {e}")
                log_error(
                    conn,
                    message="Ошибка в основном цикле datafeed_aggregator",
                    severity="error",
                    source="data_feed",
                    details={"error": str(e)},
                )
                time.sleep(5)

            time.sleep(POLL_INTERVAL_SECONDS)

    finally:
        conn.close()
        logger.info("datafeed_aggregатор остановлен")


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C")
