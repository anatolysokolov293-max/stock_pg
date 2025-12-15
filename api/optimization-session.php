<?php
require_once __DIR__ . '/helpers.php';
// public/api/optimization-session.php
require_once __DIR__ . '/db.php';

$sessionId = isset($_GET['id']) ? (int)$_GET['id'] : 0;
if ($sessionId <= 0) {
    json_response(['error' => 'id is required'], 400);
}

try {
    $pdo = get_db_connection();

    $sqlSession = "
        SELECT
            o.id,
            o.strategy_id,
            s.code AS strategy_code,
            s.name AS strategy_name,
            o.symbol_id,
            sy.ticker AS symbol_ticker,
            o.timeframe_table,
            o.window_start,
            o.window_end,
            o.best_value,
            o.best_params,
            o.n_trials,
            o.status,
            o.target_metric,
            o.direction
        FROM optimization_sessions o
        JOIN strategy_catalog s ON s.id = o.strategy_id
        JOIN symbols sy ON sy.id = o.symbol_id
        WHERE o.id = :id
        LIMIT 1
    ";
    $stmt = $pdo->prepare($sqlSession);
    $stmt->execute(['id' => $sessionId]);
    $session = $stmt->fetch();

    if (!$session) {
        json_response(['error' => 'Session not found'], 404);
    }

    $sqlTrials = "
        SELECT
            b.trial_number,
            b.is_best,
            b.params_json,
            b.cagr,
            b.sharpe,
            b.max_dd,
            b.profit_factor,
            b.trades_count,
            b.target_metric_value,
            b.trades_json,
            b.indicators_json
        FROM backtest_runs b
        WHERE b.optimization_id = :opt_id
        ORDER BY b.trial_number
    ";
    $stmt2 = $pdo->prepare($sqlTrials);
    $stmt2->execute(['opt_id' => $sessionId]);
    $trials = $stmt2->fetchAll();

    json_response([
        'session' => $session,
        'trials'  => $trials,
    ]);
} catch (Throwable $e) {
    json_response(['error' => $e->getMessage()], 500);
}
