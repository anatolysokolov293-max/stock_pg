Правильно, сейчас расчёт идёт, значит остальной пайплайн жив.​

Идея тестового файла
Сделаем отдельный скрипт test_lot_cache.py, который:

один раз подтянет из БД все lot_size по символам;

будет отдавать get_lot_size_cached(symbol_id, as_of) без новых коннектов;

покажет, что такой подход работает, а затем эту логику можно перенести в utils_lot.py и BaseLotStrategy.​

test_lot_cache.py


Вся система делится на два уровня: Python‑движок (бэктест+оптимизация) и PHP‑фронт (отчёты и визуализация).[1][2]

## Как работает Python‑часть (фоновая)

Этого набора файлов достаточно, чтобы:

батч‑скриптом python batch_optimize.py прогнать оптимизацию по всем символам/ТФ/стратегиям;

в БД сохранялись результаты, параметры, сделки и индикаторы;

через /index.php смотреть сводные таблицы и детали сессий;

через /chart.html?session_id=... видеть свечи, линии индикаторов и маркеры сделок в LightweightCharts.​​

-------------------------
очистка таблиц после неудачных оптимизаций
TRUNCATE TABLE backtest_runs;
TRUNCATE TABLE optimization_sessions;
-------------------------


1. В БД уже есть:
   - исторические свечи `candles_*` и `symbols`;[1]
   - справочник стратегий `strategy_catalog` + `strategy_params`;
   - таблицы результатов `optimization_sessions` и `backtest_runs`.

2. Ты запускаешь оптимизацию из консоли, например:

   ```bash
   python strategy_optimizer.py SMA_TREND1 1 candles_15m 2024-01-01 2024-12-31 50
   ```

Команда:

```bash
python strategy_optimizer.py SMA_TREND1 1 candles_15m 2024-01-01 2024-12-31 50
```

передаёт в скрипт `strategy_optimizer.py` 6 аргументов:

1. `strategy_optimizer.py`
   Имя Python‑скрипта, который содержит общий контроллер оптимизации стратегий: создаёт сессию в `optimization_sessions`, запускает Optuna, пишет trial‑ы в `backtest_runs`.[1][2]

2. `SMA_TREND1`
   `strategy_code` — код стратегии из таблицы `strategy_catalog`. По нему `load_strategy_config("SMA_TREND1", DB_CFG)` находит запись со ссылкой на Python‑класс (`strategies.sma_trend1.SMATrend1Strategy`) и список оптимизируемых параметров (`fast_period`, `slow_period`, `sl_pct`, `tp_pct`, `risk_per_trade`).[2]

3. `1`
   `symbol_id` — ID инструмента из таблицы `symbols`. По нему Python‑движок выбирает нужные свечи из таблиц `candles_*` и пишет в результаты именно этот инструмент.[2]

4. `candles_15m`
   `timeframe_table` — имя таблицы свечей в БД для выбранного таймфрейма (15‑минутки). Используется в `load_ohlcv_from_db()` для запроса `SELECT ... FROM candles_15m WHERE symbol_id = ... AND timestamp BETWEEN ...`.[2]

5. `2024-01-01`
   `start_date` — начало окна истории (UTC‑дата/время в формате ISO), с которого для этого прогона подгружаются свечи и считается бэктест. В коде превращается в `datetime.fromisoformat()` и идёт как `window_start`.[2]

6. `2024-12-31`
   `end_date` — конец окна истории, до которого включительно берутся свечи для оптимизации, идёт как `window_end` в запрос к БД и в запись `optimization_sessions`.[2]

7. `50`
   `n_trials` — количество испытаний Optuna. То есть Optuna 50 раз подберёт разные комбинации параметров стратегии `SMA_TREND1`, прогонит бэктест, оценит метрику (Sharpe) и выберет лучший набор, сохранив все результаты в `optimization_sessions` и `backtest_runs`.[1][2]

[1](https://optuna.org)
[2](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/148181912/93e6f855-0088-4089-8f50-2dc90f37663d/stock_db.sql)


   Внутри `strategy_optimizer.py` происходит следующее:[3]

   - `load_strategy_config("SMA_TREND1")` читает из MySQL метаданные стратегии и её параметров;[1]
   - `create_optimization_session(...)` создаёт запись в `optimization_sessions` (связка стратегия+тикер+ТФ+окно+количество trials, статус `created`);
   - создаётся Optuna‑`Study` и функция `objective = make_objective(...)`;[3]

   - при каждом `trial` в `objective`:
     - по метаданным через `suggest_params_from_trial()` генерируются конкретные значения параметров;[3]
     - `run_backtest(...)`:
       - грузит из `candles_*` свечи по `symbol_id` и `timeframe_table` за нужное окно;[1]
       - создаёт `Backtest(data, StrategyClass, ...)` из backtesting.py и запускает `bt.run(**params)`;[2]
       - возвращает метрики (Sharpe, MaxDD, ProfitFactor, trades и т.д.);
     - считается целевая метрика (с учётом фильтров по количеству сделок/просадке);
     - `insert_backtest_run(...)` записывает trial в `backtest_runs` (params_json + все метрики, `is_best=0`).

   - после окончания оптимизации:
     - `study.best_trial` и `study.best_params` определяют лучший trial;[3]
     - для лучших параметров ещё раз вызывается `run_backtest(...)`, и результат как `is_best=1` тоже пишется в `backtest_runs`;
     - `update_optimization_session_finished(...)` обновляет `optimization_sessions`: `status='finished'`, `best_value`, `best_params`, `finished_at`.

3. Ты можешь запускать оптимизацию для любых стратегий/ТФ/окна, в том числе в cron/батч‑скриптах. Всё, что нужно фронту, сохраняется в `optimization_sessions` и `backtest_runs`.

## Как работает PHP API

Все PHP‑файлы лежат в `public/api/` и возвращают JSON.[1]

1. `db.php`
   - Функция `get_db_connection()` создаёт PDO‑подключение к `stock_db`.
   - Функция `json_response()` упрощает ответ JSON + HTTP‑код.

2. `symbols.php`
   - `SELECT id, ticker, name FROM symbols ORDER BY ticker`;[1]
   - отдаёт JSON `{symbols: [...]}` для заполнения селекта инструментов на фронте.

3. `strategy-summary.php`
   - ждёт `symbol_id`;
   - агрегирует `optimization_sessions` по (strategy_id, timeframe_table):

     ```sql
     SELECT s.id AS strategy_id, s.code, s.name,
            o.timeframe_table,
            COUNT(o.id) AS sessions_count,
            AVG(o.best_value) AS avg_best_value,
            MIN(o.best_value) AS min_best_value,
            MAX(o.best_value) AS max_best_value
     FROM optimization_sessions o
     JOIN strategy_catalog s ON s.id = o.strategy_id
     WHERE o.symbol_id = :symbol_id
     GROUP BY s.id, o.timeframe_table
     ```
   - возвращает список строк, из которых фронт строит матрицу стратегий×ТФ.

4. `strategy-sessions.php`
   - ждёт `symbol_id`, `strategy_id`, `timeframe_table`;
   - по белому списку проверяет, что `timeframe_table` допустимое;
   - выбирает все `optimization_sessions` для данной (стратегия, инструмент, ТФ), сортируя по `window_start` DESC;
   - отдаёт список сессий (id, окно, best_value, best_params, n_trials, status).

5. `optimization-session.php`
   - ждёт `id` (optimization_session.id);
   - первым запросом берёт детали сессии + название стратегии и тикер;
   - вторым запросом выбирает все записи из `backtest_runs` этой сессии (trial_number, метрики, params_json, is_best);
   - отдаёт JSON `{ session: {...}, trials: [...] }`.

## Как работает фронт (index.php + JS)

1. При открытии `/index.php` браузер получает HTML с JS‑кодом и минимальным стилем.

2. JS‑инициализация (`init()`):
   - вызывает `api/symbols.php`, заполняет `<select id="symbolSelect">` тикерами;
   - по выбранному символу вызывает `api/strategy-summary.php?symbol_id=...` и рисует матрицу.

3. Построение матрицы (`renderMatrix()`):
   - из JSON строится массив стратегий и список ТФ;
   - создаётся `<table>`:
     - первая колонка — стратегия (имя + код);
     - остальные — по одному столбцу на ТФ;
     - в каждой ячейке:
       - `avg_best_value` округляется и показывается как текст;
       - по значению выбирается класс `good`/`bad`/`neutral` для цвета;
       - tooltip показывает min/max и число сессий;
       - `onclick` вызывает `openSessionsModal(strategy, timeframe)`.

4. Модальное окно сессий (`openSessionsModal` → `renderSessionsModal`):
   - вызывает `api/strategy-sessions.php?symbol_id=...&strategy_id=...&timeframe_table=...`;
   - показывает таблицу сессий:
     - ID сессии;
     - окно дат;
     - лучшее значение;
     - кол‑во trials;
     - статус;
     - кнопка «Детали» → `openSessionDetails(id)`.

5. Детали сессии и trial‑ов (`openSessionDetails`):
   - вызывает `api/optimization-session.php?id=...`;
   - показывает:
     - стратегию, тикер, ТФ, окно, целевую метрику, направление, best_value;
     - таблицу «лучшие параметры» (распарсенный JSON `best_params`);
     - таблицу trial‑ов:
       - `Trial #`, `is_best`, `target_metric_value`, `Sharpe`, `MaxDD`, `ProfitFactor`, `Trades`, строка с параметрами (`params_json` распарсен).

6. Модальное окно (`#modalOverlay` / `#modalWindow`):
   - показывается функцией `showModal(html)`, скрывается по клику на `[X]` или фон;
   - переиспользуется как для списка сессий, так и для деталей одной сессии.

## Итоговый поток «от запуска до отчёта»

1) Python‑скриптом оптимизируешь стратегию (или пачку стратегий) для нужных символов/ТФ — в БД появляются записи в `optimization_sessions` и `backtest_runs`.[3][1]
2) Открываешь `/index.php` в браузере:
   - выбираешь инструмент;
   - видишь тепловую карту стратегий×ТФ по средней лучшей метрике;
   - кликом по ячейке смотришь список сессий оптимизации;
   - кликом по конкретной сессии видишь все trial‑ы с параметрами и метриками.

Таким образом, твой PHP‑фронт вообще не знает о backtesting.py и Optuna — он просто читает результаты из БД, которые уже подготовил Python‑движок.

[1](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/148181912/93e6f855-0088-4089-8f50-2dc90f37663d/stock_db.sql)
[2](https://kernc.github.io/backtesting.py/)
[3](https://optuna.org)
