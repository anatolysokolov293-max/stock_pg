# config_loader.py
from dataclasses import dataclass
from typing import Any, List, Optional, Dict
import json
import mysql.connector


DB_CFG: Dict[str, Any] = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "",
    "database": "stock_db",
}


@dataclass
class StrategyParamDef:
    name: str
    param_type: str          # 'int', 'float', 'bool', 'categorical'
    default: Any
    min_value: Optional[Any]
    max_value: Optional[Any]
    step: Optional[Any]
    categories: Optional[List[Any]]


@dataclass
class StrategyConfig:
    id: int
    code: str
    name: str
    description: str
    py_module: str
    py_class: str
    params: List[StrategyParamDef]


def load_strategy_config(code: str,
                         db_cfg: Dict[str, Any] = DB_CFG) -> StrategyConfig:
    conn = mysql.connector.connect(**db_cfg)
    cur = conn.cursor(dictionary=True)

    sql = """
    SELECT c.id, c.code, c.name, c.description, c.py_module, c.py_class,
           p.name AS param_name, p.param_type, p.default_value,
           p.min_value, p.max_value, p.step_value, p.category_values
    FROM strategy_catalog c
    LEFT JOIN strategy_params p ON p.strategy_id = c.id
    WHERE c.code = %s AND c.enabled = 1
    ORDER BY p.id;
    """
    cur.execute(sql, (code,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise ValueError(f"Strategy with code {code} not found")

    first = rows[0]
    cfg = StrategyConfig(
        id=first["id"],
        code=first["code"],
        name=first["name"],
        description=first["description"],
        py_module=first["py_module"],
        py_class=first["py_class"],
        params=[]
    )

    for r in rows:
        if r["param_name"] is None:
            continue
        t = r["param_type"]
        def_v = r["default_value"]
        min_v = r["min_value"]
        max_v = r["max_value"]
        step_v = r["step_value"]
        cats = r["category_values"]

        if t == "int":
            def_v = int(def_v)
            min_v = int(min_v)
            max_v = int(max_v)
            step_v = int(step_v) if step_v is not None else None
        elif t == "float":
            def_v = float(def_v)
            min_v = float(min_v)
            max_v = float(max_v)
            step_v = float(step_v) if step_v is not None else None
        elif t == "bool":
            def_v = def_v in ("1", "true", "True")
        elif t == "categorical":
            def_v = def_v
        if cats:
            cats = json.loads(cats)

        cfg.params.append(StrategyParamDef(
            name=r["param_name"],
            param_type=t,
            default=def_v,
            min_value=min_v,
            max_value=max_v,
            step=step_v,
            categories=cats
        ))

    return cfg
