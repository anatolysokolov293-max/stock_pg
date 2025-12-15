"""
batch_optimize.py - Батчевая оптимизация стратегий
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import List
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from strategy_optimizer import optimize_strategy, DBCFG

TIMEFRAMES: List[str] = [
    'candles_1m',
    'candles_5m',
    'candles_15m',
    'candles_30m',
    'candles_1h',
    'candles_4h',
    'candles_1d',
]

STRATEGY_CODES: List[str] = [
    'SMA_TREND1',
    'EMA_RSI_PULLBACK',
    'BREAKOUT_DONCHIAN',
    'BOLL_MFI_REVERSAL',
    'ATR_TRAIL_TREND',
]

START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2024, 11, 14)
N_TRIALS = 50

# НАСТРОЙКА ПАРАЛЛЕЛИЗМА
# Вариант 1: Агрессивный (все ядра)
# MAX_WORKERS = os.cpu_count()  # 12

# Вариант 2: Оптимальный (оставляем запас для системы)
MAX_WORKERS = os.cpu_count() - 2  # 10

# Вариант 3: Консервативный (половина)
# MAX_WORKERS = os.cpu_count() // 2  # 6

# Вариант 4: Ручная настройка
# MAX_WORKERS = 8

print(f"CPU cores: {os.cpu_count()}, MAX_WORKERS: {MAX_WORKERS}")

def setup_logger() -> logging.Logger:
    """Настраивает логгер"""
    logger = logging.getLogger('batch_optimize')
    logger.setLevel(logging.INFO)

    log_path = os.path.join(os.path.dirname(__file__), 'batch_optimize.log')
    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%Y-%m-%d %H:%M:%S')
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(fh_formatter)
    logger.addHandler(sh)

    return logger

def get_symbols() -> list:
    """Получает список символов из БД"""
    conn = psycopg2.connect(**DBCFG)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, ticker FROM symbols ORDER BY id")
            rows = cur.fetchall()
            return rows

    finally:
        conn.close()

def run_single_optimization(symbol_id: int, ticker: str, tf: str, code: str) -> dict:
    """Запускает одну оптимизацию"""
    window = (START_DATE, END_DATE)

    try:
        study = optimize_strategy(
            strategy_code=code,
            symbol_id=symbol_id,
            timeframe_table=tf,
            window=window,
            n_trials=N_TRIALS,
            storage_url=None,
            study_name=None
        )

        return {
            'symbol_id': symbol_id,
            'ticker': ticker,
            'tf': tf,
            'code': code,
            'success': True,
            'best_value': study.best_value,
            'best_params': study.best_params
        }

    except Exception as e:
        return {
            'symbol_id': symbol_id,
            'ticker': ticker,
            'tf': tf,
            'code': code,
            'success': False,
            'error': str(e)
        }

def main():
    """Основная функция батчевой оптимизации"""
    logger = setup_logger()

    symbols = get_symbols()
    if not symbols:
        logger.error("No symbols found")
        return

    logger.info(f"Batch optimization from {START_DATE.date()} to {END_DATE.date()}")
    logger.info(f"Strategies: {STRATEGY_CODES}")
    logger.info(f"Timeframes: {TIMEFRAMES}")
    logger.info(f"Trials per combo: {N_TRIALS}")
    logger.info(f"CPU cores: {os.cpu_count()}, MAX_WORKERS: {MAX_WORKERS}")

    tasks = []
    for sym in symbols:
        for tf in TIMEFRAMES:
            for code in STRATEGY_CODES:
                tasks.append((sym['id'], sym['ticker'], tf, code))

    logger.info(f"Total combinations: {len(tasks)}")

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(run_single_optimization, symbol_id, ticker, tf, code): (symbol_id, ticker, tf, code)
            for symbol_id, ticker, tf, code in tasks
        }

        completed = 0
        total = len(futures)

        for future in as_completed(futures):
            symbol_id, ticker, tf, code = futures[future]
            completed += 1
            try:
                result = future.result()
                if result['success']:
                    logger.info(
                        f"[{completed}/{total}] {ticker} | {tf} | {code} → "
                        f"best_value={result['best_value']:.4f}, "
                        f"best_params={result['best_params']}"
                    )
                else:
                    logger.error(f"[{completed}/{total}] {ticker} | {tf} | {code} → ERROR: {result['error']}")
            except Exception as e:
                logger.exception(f"[{completed}/{total}] {ticker} | {tf} | {code} → EXCEPTION: {e}")

    logger.info("Batch optimization finished.")

if __name__ == '__main__':
    main()
