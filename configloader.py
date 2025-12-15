"""
configloader.py - Конфигурация подключения к БД и загрузка стратегий
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import psycopg2
from psycopg2.extras import RealDictCursor

DBCFG: Dict[str, Any] = {
    'host': 'localhost',
    'port': 5432,
    'database': 'stock_db',
    'user': 'postgres',
    'password': '123'
}

@dataclass
class ParamConfig:
    """Конфигурация параметра стратегии для оптимизации"""
    name: str
    type: str
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    choices: Optional[List[Any]] = None
    log_scale: bool = False

@dataclass
class StrategyConfig:
    """Конфигурация стратегии"""
    id: int
    code: str
    name: str
    py_module: str
    py_class: str
    params: List[ParamConfig]

def load_strategy_config(strategy_code: str, dbcfg: Dict[str, Any] = DBCFG) -> StrategyConfig:
    """Загружает конфигурацию стратегии из БД PostgreSQL"""
    conn = psycopg2.connect(**dbcfg)

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, code, name, py_module, py_class
                FROM strategy_catalog
                WHERE code = %s
            """, (strategy_code,))

            row = cur.fetchone()
            if not row:
                raise ValueError(f"Strategy '{strategy_code}' not found in database")

            strategy_id = row['id']

            cur.execute("""
                SELECT name, param_type, min_value, max_value, step_value, category_values, description
                FROM strategy_params
                WHERE strategy_id = %s
                ORDER BY name
            """, (strategy_id,))

            params_rows = cur.fetchall()

            params = []
            for p in params_rows:
                # Парсим category_values для categorical/bool параметров
                choices = None
                if p['category_values']:
                    try:
                        if isinstance(p['category_values'], str):
                            choices = json.loads(p['category_values'])
                        else:
                            choices = p['category_values']

                        # Для bool параметров конвертируем в Python bool
                        if p['param_type'] == 'bool':
                            choices = [bool(int(x)) for x in choices]
                    except (json.JSONDecodeError, ValueError):
                        # Если не JSON, разделяем по запятой
                        choices = [x.strip() for x in p['category_values'].split(',')]

                # Определяем log_scale (по умолчанию False)
                log_scale = False
                if p['description'] and 'log' in p['description'].lower():
                    log_scale = True

                # Конвертируем min/max/step в числа (если они есть)
                min_val = None
                max_val = None
                step = None

                if p['min_value']:
                    try:
                        min_val = float(p['min_value'])
                    except (ValueError, TypeError):
                        pass

                if p['max_value']:
                    try:
                        max_val = float(p['max_value'])
                    except (ValueError, TypeError):
                        pass

                if p['step_value']:
                    try:
                        step = float(p['step_value'])
                    except (ValueError, TypeError):
                        pass

                param = ParamConfig(
                    name=p['name'],
                    type=p['param_type'],
                    min_val=min_val,
                    max_val=max_val,
                    step=step,
                    choices=choices,
                    log_scale=log_scale
                )
                params.append(param)

            return StrategyConfig(
                id=strategy_id,
                code=row['code'],
                name=row['name'],
                py_module=row['py_module'],
                py_class=row['py_class'],
                params=params
            )

    finally:
        conn.close()
