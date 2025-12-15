<?php
require_once 'db.php'; // getDbConnection()

$pdo = getDbConnection();

// входные параметры (даты в формате dd-mm-YYYY)
$dateFromStr = isset($_GET['date_from']) ? trim($_GET['date_from']) : '';
$dateToStr   = isset($_GET['date_to'])   ? trim($_GET['date_to'])   : '';

function parseDateOrNull(?string $s): ?string {
    if (!$s) return null;
    // ожидаем формат dd-mm-YYYY
    $parts = explode('-', $s);
    if (count($parts) !== 3) return null;
    [$d, $m, $y] = $parts;
    if (!checkdate((int)$m, (int)$d, (int)$y)) return null;
    // приводим к формату YYYY-MM-DD для PostgreSQL
    return sprintf('%04d-%02d-%02d', (int)$y, (int)$m, (int)$d);
}

$dateFrom = parseDateOrNull($dateFromStr);
$dateTo   = parseDateOrNull($dateToStr);

// Пороговые значения (можно менять из фронта)
$minSharpe       = isset($_GET['min_sharpe'])  ? (float)$_GET['min_sharpe']  : 1.8;
$minProfitFactor = isset($_GET['min_pf'])      ? (float)$_GET['min_pf']      : 1.3;
$maxMaxDD        = isset($_GET['max_dd'])      ? (float)$_GET['max_dd']      : 30.0; // проценты
$minTrades       = isset($_GET['min_trades'])  ? (int)$_GET['min_trades']    : 10;
$minCagr         = isset($_GET['min_cagr'])    ? (float)$_GET['min_cagr']    : 5.0; // проценты

// 1. Тянем кандидатов из backtest_runs, только лучшие (is_best = 1) и с JSON
$sql = "
    SELECT
        br.id              AS backtest_run_id,
        br.optimization_id,
        br.strategy_id,
        br.symbol_id,
        br.timeframe_table,
        br.window_start,
        br.window_end,
        br.params_json,
        br.cagr,
        br.sharpe,
        br.max_dd,
        br.profit_factor,
        br.trades_count,
        br.created_at
    FROM backtest_runs br
    WHERE br.is_best = 1
      AND br.trades_json IS NOT NULL
      AND br.indicators_json IS NOT NULL
";

$params = [];

// Фильтр по дате created_at (по дате без времени)
if ($dateFrom && $dateTo) {
    $sql .= " AND br.created_at::date BETWEEN :date_from AND :date_to";
    $params[':date_from'] = $dateFrom;
    $params[':date_to']   = $dateTo;
} elseif ($dateFrom) {
    $sql .= " AND br.created_at::date >= :date_from";
    $params[':date_from'] = $dateFrom;
} elseif ($dateTo) {
    $sql .= " AND br.created_at::date <= :date_to";
    $params[':date_to'] = $dateTo;
}

// Пороговая фильтрация (max_dd в БД отрицательный)
$sql .= "
  AND br.sharpe        >= :min_sharpe
  AND br.profit_factor >= :min_pf
  AND (-br.max_dd)     <= :max_dd
  AND br.trades_count  >= :min_trades
  AND br.cagr          >= :min_cagr
";

$params += [
    ':min_sharpe'  => $minSharpe,
    ':min_pf'      => $minProfitFactor,
    ':max_dd'      => $maxMaxDD,
    ':min_trades'  => $minTrades,
    ':min_cagr'    => $minCagr,
];

$stmt = $pdo->prepare($sql);
$stmt->execute($params);
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);

// 2. Веса таймфреймов
$tfWeights = [];
$twStmt = $pdo->query("SELECT timeframe, tf_weight FROM timeframe_weights");
foreach ($twStmt->fetchAll(PDO::FETCH_ASSOC) as $tfRow) {
    $tfWeights[$tfRow['timeframe']] = (float)$tfRow['tf_weight'];
}

// 3. Символы (ticker), figi пока null
$symbols = [];
$syStmt = $pdo->query("SELECT id, ticker FROM symbols");
foreach ($syStmt->fetchAll(PDO::FETCH_ASSOC) as $srow) {
    $symbols[$srow['id']] = [
        'ticker' => $srow['ticker'],
        'figi'   => null,
    ];
}

// Скоринг
function compute_scores(array $r, float $tfWeight): array {
    $sharpe  = (float)$r['sharpe'];
    $pf      = (float)$r['profit_factor'];
    $cagr    = (float)$r['cagr'];
    $trades  = (int)$r['trades_count'];

    $max_dd_db = (float)$r['max_dd'];
    $max_dd    = -$max_dd_db; // -25 → 25

    $sharpe_norm = max(0.0, min($sharpe / 3.0, 1.0));
    $pf_norm     = max(0.0, min(($pf - 1.0) / 2.0, 1.0));
    $cagr_norm   = max(0.0, min($cagr / 40.0, 1.0));
    $trades_norm = max(0.0, min($trades / 300.0, 1.0));
    $maxdd_raw   = max(0.0, min($max_dd / 30.0, 1.0));
    $maxdd_norm  = 1.0 - $maxdd_raw;

    $base = 0.3 * $sharpe_norm +
            0.3 * $pf_norm +
            0.1 * $cagr_norm +
            0.1 * $trades_norm +
            0.2 * $maxdd_norm;

    $final = $base * ($tfWeight ?: 1.0);

    return [$base, $final];
}

// 4. Группировка по symbol+timeframe+strategy_id
$candidatesGrouped = [];

foreach ($rows as $r) {
    $symbolId   = (int)$r['symbol_id'];
    $strategyId = (int)$r['strategy_id'];
    $timeframe  = str_replace('candles_', '', $r['timeframe_table']);

    $sym = $symbols[$symbolId] ?? ['ticker' => (string)$symbolId, 'figi' => null];
    $symbolTicker = $sym['ticker'];

    $tfWeight = $tfWeights[$timeframe] ?? 1.0;

    [$baseScore, $finalScore] = compute_scores($r, $tfWeight);

    $key = $symbolTicker . '|' . $timeframe . '|' . $strategyId;

    if (!isset($candidatesGrouped[$key]) || $finalScore > $candidatesGrouped[$key]['final_score']) {
        $max_dd_display = -(float)$r['max_dd'];

        $candidatesGrouped[$key] = [
            'backtest_run_id' => (int)$r['backtest_run_id'],
            'optimization_id' => (int)$r['optimization_id'],
            'strategy_id'     => $strategyId,
            'symbol_id'       => $symbolId,
            'symbol'          => $symbolTicker,
            'figi'            => $sym['figi'],
            'timeframe'       => $timeframe,
            'timeframe_table' => $r['timeframe_table'],
            'params_json'     => $r['params_json'],
            'metrics' => [
                'sharpe'       => (float)$r['sharpe'],
                'max_dd'       => $max_dd_display,
                'pf'           => (float)$r['profit_factor'],
                'trades'       => (int)$r['trades_count'],
                'cagr'         => (float)$r['cagr'],
                'base_score'   => $baseScore,
                'final_score'  => $finalScore,
            ],
            'window_start'    => $r['window_start'],
            'window_end'      => $r['window_end'],
            'created_at'      => $r['created_at'],
        ];
    }
}

// 5. Сравнение с strategy_universe
$out = [];
$selUniverse = $pdo->prepare("
    SELECT *
    FROM strategy_universe
    WHERE symbol      = :symbol
      AND timeframe   = :timeframe
      AND strategy_id = :strategy_id
");

foreach ($candidatesGrouped as $cand) {
    $selUniverse->execute([
        ':symbol'      => $cand['symbol'],
        ':timeframe'   => $cand['timeframe'],
        ':strategy_id' => $cand['strategy_id'],
    ]);
    $existing = $selUniverse->fetch(PDO::FETCH_ASSOC);

    if (!$existing) {
        $out[] = [
            'action' => 'insert',
            'symbol' => $cand['symbol'],
            'figi'   => $cand['figi'],
            'timeframe'   => $cand['timeframe'],
            'strategy_id' => $cand['strategy_id'],
            'params_json' => $cand['params_json'],
            'metrics'     => $cand['metrics'],
            'backtest_run_id' => $cand['backtest_run_id'],
            'optimization_id' => $cand['optimization_id'],
            'window_start'    => $cand['window_start'],
            'window_end'      => $cand['window_end'],
        ];
    } else {
        $existingMaxDD = isset($existing['max_dd']) ? (float)$existing['max_dd'] : null;

        $out[] = [
            'action' => 'update_candidate',
            'symbol' => $cand['symbol'],
            'figi'   => $cand['figi'],
            'timeframe'   => $cand['timeframe'],
            'strategy_id' => $cand['strategy_id'],
            'existing' => [
                'id'              => (int)$existing['id'],
                'backtest_run_id' => $existing['backtest_run_id'],
                'sharpe'          => (float)$existing['sharpe'],
                'max_dd'          => $existingMaxDD,
                'pf'              => (float)$existing['pf'],
                'trades'          => (int)$existing['trades'],
                'cagr'            => (float)$existing['cagr'],
                'score'           => (float)$existing['score'],
                'mode'            => $existing['mode'],
                'enabled'         => (bool)$existing['enabled'],
            ],
            'new' => [
                'backtest_run_id' => $cand['backtest_run_id'],
                'optimization_id' => $cand['optimization_id'],
                'sharpe'          => $cand['metrics']['sharpe'],
                'max_dd'          => $cand['metrics']['max_dd'],
                'pf'              => $cand['metrics']['pf'],
                'trades'          => $cand['metrics']['trades'],
                'cagr'            => $cand['metrics']['cagr'],
                'final_score'     => $cand['metrics']['final_score'],
            ],
        ];
    }
}

header('Content-Type: application/json; charset=utf-8');
echo json_encode(array_values($out), JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
