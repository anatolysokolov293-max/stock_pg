<?php
require_once __DIR__ . '/helpers.php';
// public/api/strategy-summary.php
require_once __DIR__ . '/db.php';

$symbolId = isset($_GET['symbol_id']) ? (int)$_GET['symbol_id'] : 0;
if ($symbolId <= 0) {
    json_response(['error' => 'symbol_id is required'], 400);
}

try {
    $pdo = get_db_connection();

    $sql = "
        SELECT
            s.id              AS strategy_id,
            s.code            AS strategy_code,
            s.name            AS strategy_name,
            o.timeframe_table,
            COUNT(o.id)       AS sessions_count,
            AVG(o.best_value) AS avg_best_value,
            MIN(o.best_value) AS min_best_value,
            MAX(o.best_value) AS max_best_value
        FROM optimization_sessions o
        JOIN strategy_catalog s ON s.id = o.strategy_id
        WHERE o.symbol_id = :symbol_id
        GROUP BY s.id, o.timeframe_table
        ORDER BY s.code, o.timeframe_table
    ";

    $stmt = $pdo->prepare($sql);
    $stmt->execute(['symbol_id' => $symbolId]);
    $rows = $stmt->fetchAll();

    json_response([
        'symbol_id' => $symbolId,
        'rows'      => $rows,
    ]);
} catch (Throwable $e) {
    json_response(['error' => $e->getMessage()], 500);
}
