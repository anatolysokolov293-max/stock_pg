"""
optuna_helpers.py - Вспомогательные функции для Optuna оптимизации
"""
import optuna
from typing import Dict, Any
from configloader import StrategyConfig, ParamConfig

def suggest_params_from_trial(trial: optuna.Trial, cfg: StrategyConfig) -> Dict[str, Any]:
    """
    Генерирует параметры стратегии из Optuna trial на основе конфигурации

    Args:
        trial: Optuna trial объект
        cfg: Конфигурация стратегии

    Returns:
        Словарь с параметрами для стратегии
    """
    params = {}

    for p in cfg.params:
        if p.type == 'int':
            params[p.name] = trial.suggest_int(
                p.name,
                int(p.min_val),
                int(p.max_val),
                step=int(p.step) if p.step else 1,
                log=p.log_scale
            )
        elif p.type == 'float':
            params[p.name] = trial.suggest_float(
                p.name,
                p.min_val,
                p.max_val,
                step=p.step,
                log=p.log_scale
            )
        elif p.type == 'categorical':
            params[p.name] = trial.suggest_categorical(p.name, p.choices)

    return params
