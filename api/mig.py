#!/usr/bin/env python3
import logging
import os
import sys

import psycopg2
from psycopg2.extras import DictCursor

logger = logging.getLogger("migration_live_schema")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
handler.setFormatter(formatter)
logger.addHandler(handler)


MIGRATION_SQL = r"""
BEGIN;

ALTER TABLE strategy_universe
    ADD COLUMN IF NOT EXISTS max_drawdown_fraction      double precision NOT NULL DEFAULT 0.2,
    ADD COLUMN IF NOT EXISTS gap_threshold_fraction     double precision NOT NULL DEFAULT 0.2,
    ADD COLUMN IF NOT EXISTS max_positions_per_strategy integer,
    ADD COLUMN IF NOT EXISTS max_total_positions        integer;

UPDATE strategy_universe
SET risk_per_trade = 0.02
WHERE risk_per_trade IS NULL;

CREATE TABLE IF NOT EXISTS trading_control (
    id                   bigint PRIMARY KEY DEFAULT 1,
    allow_trading        boolean NOT NULL DEFAULT true,
    allow_new_positions  boolean NOT NULL DEFAULT true,
    comment              text,
    updated_at           timestamptz NOT NULL DEFAULT now()
);

INSERT INTO trading_control (id, allow_trading, allow_new_positions, comment)
VALUES (1, true, true, 'initial setup')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS live_positions (
    id                   bigserial PRIMARY KEY,
    strategy_universe_id bigint NOT NULL REFERENCES strategy_universe(id) ON DELETE CASCADE,
    symbol               text    NOT NULL,
    timeframe            text    NOT NULL,
    direction            text    NOT NULL,
    quantity             numeric(20, 6) NOT NULL,
    avg_price            numeric(20, 6) NOT NULL,
    realized_pnl         numeric(20, 6) NOT NULL DEFAULT 0,
    unrealized_pnl       numeric(20, 6) NOT NULL DEFAULT 0,
    drawdown_fraction    double precision NOT NULL DEFAULT 0,
    gap_mode             boolean NOT NULL DEFAULT false,
    manual_block_until   timestamptz,
    opened_at            timestamptz NOT NULL,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT live_positions_unq UNIQUE (strategy_universe_id, symbol, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_live_positions_symbol_tf
    ON live_positions (symbol, timeframe);

CREATE TABLE IF NOT EXISTS live_signals (
    id                   bigserial PRIMARY KEY,
    strategy_universe_id bigint NOT NULL REFERENCES strategy_universe(id) ON DELETE CASCADE,
    symbol               text    NOT NULL,
    timeframe            text    NOT NULL,
    bar_timestamp        timestamptz NOT NULL,
    signal_timestamp     timestamptz NOT NULL DEFAULT now(),
    signal_type          text    NOT NULL,
    signal_source        text    NOT NULL DEFAULT 'strategy',
    signal_json          jsonb   NOT NULL,
    gap_flag             boolean NOT NULL DEFAULT false,
    processed            boolean NOT NULL DEFAULT false,
    processed_at         timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_signals_processed
    ON live_signals (processed, signal_timestamp);

CREATE INDEX IF NOT EXISTS idx_live_signals_symbol_tf_time
    ON live_signals (symbol, timeframe, bar_timestamp);

CREATE TABLE IF NOT EXISTS live_orders (
    id                   bigserial PRIMARY KEY,
    live_signal_id       bigint REFERENCES live_signals(id) ON DELETE SET NULL,
    strategy_universe_id bigint NOT NULL REFERENCES strategy_universe(id) ON DELETE CASCADE,
    symbol               text NOT NULL,
    timeframe            text,
    side                 text NOT NULL,
    quantity             numeric(20, 6) NOT NULL,
    price                numeric(20, 6),
    order_type           text NOT NULL,
    time_in_force        text,
    status               text NOT NULL,
    broker_order_id      text,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_orders_status
    ON live_orders (status, created_at);

CREATE INDEX IF NOT EXISTS idx_live_orders_symbol_time
    ON live_orders (symbol, created_at);

CREATE TABLE IF NOT EXISTS live_trades (
    id                   bigserial PRIMARY KEY,
    live_order_id        bigint REFERENCES live_orders(id) ON DELETE SET NULL,
    strategy_universe_id bigint NOT NULL REFERENCES strategy_universe(id) ON DELETE CASCADE,
    symbol               text NOT NULL,
    timeframe            text,
    side                 text NOT NULL,
    quantity             numeric(20, 6) NOT NULL,
    price                numeric(20, 6) NOT NULL,
    fee                  numeric(20, 6) NOT NULL DEFAULT 0,
    executed_at          timestamptz NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_trades_symbol_time
    ON live_trades (symbol, executed_at);

CREATE INDEX IF NOT EXISTS idx_live_trades_strategy_time
    ON live_trades (strategy_universe_id, executed_at);

CREATE TABLE IF NOT EXISTS live_errors (
    id                   bigserial PRIMARY KEY,
    timestamp            timestamptz NOT NULL DEFAULT now(),
    source               text NOT NULL,
    severity             text NOT NULL,
    strategy_universe_id bigint REFERENCES strategy_universe(id) ON DELETE SET NULL,
    symbol               text,
    timeframe            text,
    message              text NOT NULL,
    details_json         jsonb
);

CREATE INDEX IF NOT EXISTS idx_live_errors_time
    ON live_errors (timestamp);

CREATE INDEX IF NOT EXISTS idx_live_errors_strategy
    ON live_errors (strategy_universe_id, timestamp);

COMMIT;
"""


def get_cfg_from_env():
    host = os.environ.get("PG_HOST", "127.0.0.1")
    port = os.environ.get("PG_PORT", "5432")
    dbname = os.environ.get("PG_DBNAME")
    user = os.environ.get("PG_USER")
    password = os.environ.get("PG_PASSWORD")

    if not all([dbname, user, password]):
        raise RuntimeError(
            "Нужно задать PG_DBNAME, PG_USER, PG_PASSWORD (и при необходимости PG_HOST, PG_PORT)"
        )

    logger.info(f"Параметры БД из окружения: host={host}, port={port}, dbname={dbname}, user={user}")
    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
    }


def main():
    try:
        cfg = get_cfg_from_env()
    except Exception as e:
        logger.exception(f"Ошибка чтения параметров подключения из окружения: {e}")
        sys.exit(1)

    logger.info("Подключаемся к PostgreSQL...")
    conn = psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
    )
    conn.autocommit = False

    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            logger.info("Начинаем выполнение миграции live‑схемы...")
            cur.execute(MIGRATION_SQL)
        conn.commit()
        logger.info("Миграция выполнена успешно, транзакция закоммичена.")
    except Exception as e:
        conn.rollback()
        logger.exception(f"Ошибка при выполнении миграции, транзакция откатена: {e}")
        sys.exit(1)
    finally:
        conn.close()
        logger.info("Соединение с БД закрыто.")


if __name__ == "__main__":
    main()
