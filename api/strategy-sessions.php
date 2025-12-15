<?php
require_once __DIR__ . '/helpers.php';
// public/api/strategy-sessions.php
require_once __DIR__ . '/db.php';

$symbolId       = isset($_GET['symbol_id']) ? (int)$_GET['symbol_id'] : 0;
$strategyId     = isset($_GET['strategy_id']) ? (int)$_GET['strategy_id'] : 0;
$timeframeTable = isset($_GET['timeframe_table']) ? trim($_GET['timeframe_table']) : '';

if ($symbolId <= 0 || $strategyId <= 0 || $timeframeTable === '') {
    json_response(['error' => 'symbol_id, strategy_id, timeframe_table are required'], 400);
}

$allowed_timeframes = [
    'candles_1m',
    'candles_5m',
    'candles_15m',
    'candles_30m',
    'candles_1h',
    'candles_4h',
    'candles_1d',
];
if (!in_array($timeframeTable, $allowed_timeframes, true)) {
    json_response(['error' => 'Invalid timeframe_table'], 400);
}

try {
    $pdo = get_db_connection();

    $sql = "
        SELECT
            o.id,
            o.window_start,
            o.window_end,
            o.best_value,
            o.best_params,
            o.n_trials,
            o.status
        FROM optimization_sessions o
        WHERE o.symbol_id = :symbol_id
          AND o.strategy_id = :strategy_id
          AND o.timeframe_table = :tf
        ORDER BY o.window_start DESC
    ";

    $stmt = $pdo->prepare($sql);
    $stmt->execute([
        'symbol_id'   => $symbolId,
        'strategy_id' => $strategyId,
        'tf'          => $timeframeTable,
    ]);
    $sessions = $stmt->fetchAll();

    json_response([
        'symbol_id'       => $symbolId,
        'strategy_id'     => $strategyId,
        'timeframe_table' => $timeframeTable,
        'sessions'        => $sessions,
    ]);
} catch (Throwable $e) {
    json_response(['error' => $e->getMessage()], 500);
}
