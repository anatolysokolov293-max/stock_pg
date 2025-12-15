"""
strategy_optimizer.py - Оптимизация стратегий с использованием Optuna
"""
from typing import Tuple, Dict, Any, Optional
from datetime import datetime
import json
import optuna
import psycopg2
from psycopg2.extras import RealDictCursor
import math
from configloader import load_strategy_config, DBCFG
from optuna_helpers import suggest_params_from_trial
from backtest_runner import run_backtest

def create_optimization_session(
    strategy_code: str,
    symbol_id: int,
    timeframe_table: str,
    window: Tuple[datetime, datetime],
    target_metric: str,
    direction: str,
    n_trials: int,
    storage_url: Optional[str],
    study_name: Optional[str]
) -> int:
    """Создает сессию оптимизации в БД"""
    cfg = load_strategy_config(strategy_code, DBCFG)
    conn = psycopg2.connect(**DBCFG)

    try:
        with conn.cursor() as cur:
            # ИСПРАВЛЕНИЕ: Используем правильные имена колонок с подчёркиваниями
            sql = """
                INSERT INTO optimization_sessions
                (strategy_id, symbol_id, timeframe_table, window_start, window_end,
                 study_name, storage_url, target_metric, direction, n_trials, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'created')
                RETURNING id
            """
            cur.execute(sql, (
                cfg.id, symbol_id, timeframe_table, window[0], window[1],
                study_name, storage_url, target_metric, direction, n_trials
            ))
            opt_id = cur.fetchone()[0]
            conn.commit()
            return opt_id

    finally:
        conn.close()

def update_optimization_session_finished(opt_id: int, best_value: float, best_params: Dict[str, Any]):
    """Обновляет сессию оптимизации после завершения"""
    conn = psycopg2.connect(**DBCFG)

    try:
        with conn.cursor() as cur:
            # ИСПРАВЛЕНИЕ: Используем правильные имена колонок
            sql = """
                UPDATE optimization_sessions
                SET status = 'finished', best_value = %s, best_params = %s, finished_at = NOW()
                WHERE id = %s
            """
            cur.execute(sql, (best_value, json.dumps(best_params), opt_id))
            conn.commit()

    finally:
        conn.close()

def nan_to_none(v):
    """Конвертирует NaN в None для PostgreSQL"""
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    return v

def insert_backtest_run(
    optimization_id: int,
    cfg_id: int,
    symbol_id: int,
    timeframe_table: str,
    window: Tuple[datetime, datetime],
    trial_number: int,
    params: Dict[str, Any],
    metrics: Dict[str, Any],
    is_best: bool
):
    """Сохраняет результат одного прогона бэктеста"""
    conn = psycopg2.connect(**DBCFG)

    try:
        with conn.cursor() as cur:
            # ИСПРАВЛЕНИЕ: Используем правильные имена колонок с подчёркиваниями
            sql = """
                INSERT INTO backtest_runs
                (optimization_id, strategy_id, symbol_id, timeframe_table, window_start, window_end,
                 trial_number, is_best, params_json, cagr, sharpe, max_dd, profit_factor,
                 trades_count, target_metric_value, trades_json, indicators_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cagr = nan_to_none(metrics.get('CAGR'))
            sharpe = nan_to_none(metrics.get('Sharpe'))
            maxdd = nan_to_none(metrics.get('MaxDD'))
            profitfactor = nan_to_none(metrics.get('ProfitFactor'))
            tradescount = metrics.get('Trades')
            targetmetric = nan_to_none(metrics.get('target_metric'))

            if is_best:
                tradesjson = metrics.get('trades_json')
                indicatorsjson = metrics.get('indicators_json')
            else:
                tradesjson = None
                indicatorsjson = None

            cur.execute(sql, (
                optimization_id, cfg_id, symbol_id, timeframe_table, window[0], window[1],
                trial_number, 1 if is_best else 0, json.dumps(params),
                cagr, sharpe, maxdd, profitfactor, tradescount, targetmetric,
                tradesjson, indicatorsjson
            ))
            conn.commit()

    finally:
        conn.close()

def make_objective(
    strategy_code: str,
    symbol_id: int,
    timeframe_table: str,
    window: Tuple[datetime, datetime],
    optimization_id: int,
    min_trades: int = 10,
    max_dd_limit: float = -30.0
):
    """Создает функцию цели для Optuna"""

    def objective(trial: optuna.Trial) -> float:
        cfg = load_strategy_config(strategy_code, DBCFG)
        opt_params = suggest_params_from_trial(trial, cfg)

        metrics = run_backtest(
            cfg,
            symbol_id,
            timeframe_table,
            window,
            opt_params,
            DBCFG,
            extract_details=False
        )

        value = metrics['target_metric']

        if metrics['Trades'] < min_trades or metrics['MaxDD'] < max_dd_limit:
            value = -1.0

        insert_backtest_run(
            optimization_id=optimization_id,
            cfg_id=cfg.id,
            symbol_id=symbol_id,
            timeframe_table=timeframe_table,
            window=window,
            trial_number=trial.number,
            params=opt_params,
            metrics=metrics,
            is_best=False
        )

        return value

    return objective

def optimize_strategy(
    strategy_code: str,
    symbol_id: int,
    timeframe_table: str,
    window: Tuple[datetime, datetime],
    n_trials: int = 50,
    storage_url: Optional[str] = None,
    study_name: Optional[str] = None,
    target_metric: str = 'Sharpe',
    direction: str = 'maximize'
) -> optuna.Study:
    """Оптимизирует стратегию"""
    opt_id = create_optimization_session(
        strategy_code=strategy_code,
        symbol_id=symbol_id,
        timeframe_table=timeframe_table,
        window=window,
        target_metric=target_metric,
        direction=direction,
        n_trials=n_trials,
        storage_url=storage_url,
        study_name=study_name
    )

    study_kwargs: Dict[str, Any] = {'direction': direction}

    if storage_url is not None:
        study_kwargs['storage'] = storage_url
        study_kwargs['load_if_exists'] = True

    if study_name is not None:
        study_kwargs['study_name'] = study_name

    study = optuna.create_study(**study_kwargs)

    objective = make_objective(
        strategy_code=strategy_code,
        symbol_id=symbol_id,
        timeframe_table=timeframe_table,
        window=window,
        optimization_id=opt_id
    )

    study.optimize(objective, n_trials=n_trials)

    best_trial = study.best_trial
    cfg = load_strategy_config(strategy_code, DBCFG)

    best_metrics = run_backtest(
        cfg,
        symbol_id,
        timeframe_table,
        window,
        best_trial.params,
        DBCFG,
        extract_details=True
    )

    insert_backtest_run(
        optimization_id=opt_id,
        cfg_id=cfg.id,
        symbol_id=symbol_id,
        timeframe_table=timeframe_table,
        window=window,
        trial_number=best_trial.number,
        params=best_trial.params,
        metrics=best_metrics,
        is_best=True
    )

    update_optimization_session_finished(
        opt_id,
        best_value=study.best_value,
        best_params=study.best_params
    )

    return study

def main():
    """Пример использования из командной строки"""
    from sys import argv

    if len(argv) < 7:
        print("Usage: python strategy_optimizer.py <strategy_code> <symbol_id> <timeframe_table> <start_date> <end_date> <n_trials>")
        return

    strategy_code = argv[1]
    symbol_id = int(argv[2])
    timeframe_table = argv[3]
    start_date = datetime.fromisoformat(argv[4])
    end_date = datetime.fromisoformat(argv[5])
    n_trials = int(argv[6])

    study = optimize_strategy(
        strategy_code=strategy_code,
        symbol_id=symbol_id,
        timeframe_table=timeframe_table,
        window=(start_date, end_date),
        n_trials=n_trials
    )

    print(f"\nBest trial: {study.best_trial.number}")
    print(f"Best value: {study.best_value:.4f}")
    print(f"Best params: {study.best_params}")

if __name__ == '__main__':
    main()
