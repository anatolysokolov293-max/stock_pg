# backtest_runner.py - backtesting.py интеграция
from typing import Any, Dict, Tuple, Optional
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from backtesting import Backtest
from datetime import datetime
import json
from config_loader import StrategyConfig, DB_CFG
from importlib import import_module


def load_strategy_class(cfg: StrategyConfig):
    """Загружает класс стратегии из модуля"""
    module = import_module(cfg.py_module)
    return getattr(module, cfg.py_class)


def load_ohlcv_from_db(
    symbol_id: int,
    timeframe_table: str,
    start: datetime,
    end: datetime,
    db_cfg: Dict[str, Any] = DB_CFG
) -> pd.DataFrame:
    """
    Загружает OHLCV данные из PostgreSQL

    Args:
        symbol_id: ID инструмента
        timeframe_table: название таблицы (например, candles_1h)
        start: начальная дата
        end: конечная дата
        db_cfg: конфигурация подключения к БД

    Returns:
        DataFrame с колонками Open, High, Low, Close, Volume и индексом timestamp
    """
    conn = psycopg2.connect(**db_cfg)
    try:
        with conn.cursor() as cur:
            sql = f"""
                SELECT timestamp, open, high, low, close, volume
                FROM {timeframe_table}
                WHERE symbol_id = %s AND timestamp BETWEEN %s AND %s
                ORDER BY timestamp
            """
            cur.execute(sql, (symbol_id, start, end))
            rows = cur.fetchall()

            if not rows:
                raise ValueError(f"No data found for symbol_id={symbol_id} in {timeframe_table}")

            df = pd.DataFrame(rows, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df.set_index('timestamp', inplace=True)
            return df
    finally:
        conn.close()


def extract_trades_json(stats) -> str:
    """
    Извлекает сделки из результатов бэктеста и конвертирует в JSON
    Включает информацию о входе И выходе из позиции
    """
    import pandas as pd
    import json

    trades_df = None
    if hasattr(stats, '_trades'):
        trades_df = getattr(stats, '_trades')
    elif hasattr(stats, 'trades'):
        trades_df = getattr(stats, 'trades')

    if trades_df is None or len(trades_df) == 0:
        return json.dumps([])

    df = trades_df.copy()
    trades_list = []

    for _, tr in df.iterrows():
        # Получаем время входа
        entry_time = tr.get('EntryTime')
        if pd.isna(entry_time):
            continue

        # Получаем время выхода
        exit_time = tr.get('ExitTime')

        # Получаем цены
        entry_price = float(tr.get('EntryPrice', 0.0))
        exit_price = float(tr.get('ExitPrice', 0.0)) if not pd.isna(tr.get('ExitPrice')) else None

        # Определяем направление сделки
        size = float(tr.get('Size', 0.0))
        is_long = size > 0

        # P&L
        pnl = float(tr.get('PnL', 0.0))
        pnl_percent = float(tr.get('ReturnPct', 0.0)) * 100 if 'ReturnPct' in tr else 0.0

        trade_data = {
            'entry_time': entry_time.isoformat() if hasattr(entry_time, 'isoformat') else str(entry_time),
            'entry_price': entry_price,
            'exit_time': exit_time.isoformat() if exit_time and hasattr(exit_time, 'isoformat') else (str(exit_time) if exit_time else None),
            'exit_price': exit_price,
            'size': abs(size),
            'is_long': is_long,
            'pnl': pnl,
            'pnl_percent': pnl_percent
        }

        trades_list.append(trade_data)

    return json.dumps(trades_list)


def extract_indicators_json(stats, data: pd.DataFrame) -> str:
    """
    Извлекает значения индикаторов из объекта стратегии и конвертирует в JSON
    """
    import json

    series: Dict[str, Any] = {}

    strategy = getattr(stats, '_strategy', None)
    if strategy is None:
        return json.dumps({})

    for attr_name in dir(strategy):
        if attr_name.startswith('_'):
            continue

        attr = getattr(strategy, attr_name, None)
        if attr is None:
            continue

        # Проверяем, является ли атрибут индикатором (имеет len и name)
        if hasattr(attr, '__len__') and hasattr(attr, 'name'):
            indicator_data = []

            for i, val in enumerate(attr):
                if pd.isna(val):
                    continue
                if i >= len(data):
                    break

                ts = data.index[i]
                indicator_data.append({
                    'time': ts.isoformat() if hasattr(ts, 'isoformat') else str(ts),
                    'value': float(val)
                })

            if indicator_data:
                series[attr.name] = indicator_data

    return json.dumps(series)


def safe_float(v) -> float:
    """
    Безопасно конвертирует значение в float, NaN и Inf заменяет на 0.0
    """
    import math
    try:
        f = float(v)
        return f if not math.isnan(f) and not math.isinf(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def run_backtest(
    cfg: StrategyConfig,
    symbol_id: int,
    timeframe_table: str,
    window: Tuple[datetime, datetime],
    params: Dict[str, Any],
    db_cfg: Dict[str, Any] = DB_CFG,
    extract_details: bool = True
) -> Dict[str, Any]:
    """
    Запускает бэктест стратегии

    Args:
        cfg: конфигурация стратегии
        symbol_id: ID инструмента
        timeframe_table: таблица с данными
        window: кортеж (start, end) с датами
        params: параметры стратегии
        db_cfg: конфигурация БД
        extract_details: извлекать ли детали (сделки, индикаторы)

    Returns:
        Словарь с результатами: метрики + trades_json + indicators_json
    """
    # Загружаем класс стратегии
    StrategyClass = load_strategy_class(cfg)

    # Загружаем данные
    data = load_ohlcv_from_db(
        symbol_id=symbol_id,
        timeframe_table=timeframe_table,
        start=window[0],
        end=window[1],
        db_cfg=db_cfg
    )

    # Передаем symbol_id в стратегию (если нужно)
    StrategyClass.symbol_id = symbol_id

    # Запускаем бэктест
    bt = Backtest(data, StrategyClass, cash=100000, commission=0.0005)
    stats = bt.run(**params)

    # Извлекаем детали
    trades_json = None
    indicators_json = None

    if extract_details:
        trades_json = extract_trades_json(stats)
        indicators_json = extract_indicators_json(stats, data)

    # Формируем результат
    res = {
        'CAGR': safe_float(stats.get('Return [%]', 0)),
        'Sharpe': safe_float(stats.get('Sharpe Ratio', 0)),
        'MaxDD': safe_float(stats.get('Max. Drawdown [%]', 0)),
        'ProfitFactor': safe_float(stats.get('Profit Factor', 0)),
        'Trades': int(stats.get('# Trades', 0) or 0),
        'WinRate': safe_float(stats.get('Win Rate [%]', 0)),
        'AvgTrade': safe_float(stats.get('Avg. Trade [%]', 0)),
        'MaxTradeDD': safe_float(stats.get('Max. Trade Duration', 0)),
        'target_metric': safe_float(stats.get('Sharpe Ratio', 0)),
        'raw_stats': stats,
        'trades_json': trades_json,
        'indicators_json': indicators_json
    }

    return res
