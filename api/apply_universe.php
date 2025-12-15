<?php
require_once 'db.php';

$pdo = getDbConnection();

// Ожидаем JSON POST
$raw = file_get_contents('php://input');
$data = json_decode($raw, true);

if (!is_array($data)) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON'], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    exit;
}

$insertCount = 0;
$updateCount = 0;

try {
    $pdo->beginTransaction();

    $insertSql = "
        INSERT INTO strategy_universe
        (
            symbol, figi, timeframe, strategy_id, params_json,
            sharpe, max_dd, pf, trades, cagr,
            backtest_run_id, backtest_started_at,
            score, grade, mode, priority, risk_per_trade,
            created_at, updated_at, comment
        )
        VALUES
        (
            :symbol, :figi, :timeframe, :strategy_id, :params_json,
            :sharpe, :max_dd, :pf, :trades, :cagr,
            :backtest_run_id, :backtest_started_at,
            :score, :grade, :mode, :priority, :risk_per_trade,
            NOW(), NOW(), :comment
        )
        ON CONFLICT (symbol, timeframe, strategy_id)
        DO UPDATE SET
            params_json         = EXCLUDED.params_json,
            sharpe              = EXCLUDED.sharpe,
            max_dd              = EXCLUDED.max_dd,
            pf                  = EXCLUDED.pf,
            trades              = EXCLUDED.trades,
            cagr                = EXCLUDED.cagr,
            backtest_run_id     = EXCLUDED.backtest_run_id,
            backtest_started_at = EXCLUDED.backtest_started_at,
            score               = EXCLUDED.score,
            grade               = EXCLUDED.grade,
            mode                = EXCLUDED.mode,
            priority            = EXCLUDED.priority,
            risk_per_trade      = EXCLUDED.risk_per_trade,
            updated_at          = NOW()
    ";

    $updateSql = "
        UPDATE strategy_universe
        SET
            params_json         = :params_json,
            sharpe              = :sharpe,
            max_dd              = :max_dd,
            pf                  = :pf,
            trades              = :trades,
            cagr                = :cagr,
            backtest_run_id     = :backtest_run_id,
            backtest_started_at = :backtest_started_at,
            score               = :score,
            grade               = :grade,
            updated_at          = NOW()
        WHERE id = :id
    ";

    $insertStmt = $pdo->prepare($insertSql);
    $updateStmt = $pdo->prepare($updateSql);

    foreach ($data as $item) {
        if (!isset($item['action'])) {
            continue;
        }

        $action = $item['action'];

        if ($action === 'insert') {
            $m = $item['metrics'];

            $insertStmt->execute([
                ':symbol'           => $item['symbol'],
                ':figi'             => $item['figi'] ?? null,
                ':timeframe'        => $item['timeframe'],
                ':strategy_id'      => $item['strategy_id'],
                ':params_json'      => $item['params_json'],
                ':sharpe'           => $m['sharpe'],
                ':max_dd'           => $m['max_dd'],
                ':pf'               => $m['pf'],
                ':trades'           => $m['trades'],
                ':cagr'             => $m['cagr'],
                ':backtest_run_id'  => $item['backtest_run_id'],
                ':backtest_started_at' => $item['window_start'],
                ':score'            => $m['final_score'],
                ':grade'            => null,
                ':mode'             => 'backtest',
                ':priority'         => 0,
                ':risk_per_trade'   => null,
                ':comment'          => null,
            ]);

            $insertCount++;

        } elseif ($action === 'update_candidate' && isset($item['existing']['id'])) {
            $m = $item['new'];

            $updateStmt->execute([
                ':id'               => $item['existing']['id'],
                ':params_json'      => $item['params_json'] ?? null,
                ':sharpe'           => $m['sharpe'],
                ':max_dd'           => $m['max_dd'],
                ':pf'               => $m['pf'],
                ':trades'           => $m['trades'],
                ':cagr'             => $m['cagr'],
                ':backtest_run_id'  => $m['backtest_run_id'],
                ':backtest_started_at' => $item['window_start'] ?? null,
                ':score'            => $m['final_score'],
                ':grade'            => null,
            ]);

            $updateCount++;
        }
    }

    $pdo->commit();

    echo json_encode([
        'status'   => 'ok',
        'inserted' => $insertCount,
        'updated'  => $updateCount,
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);

} catch (Exception $e) {
    $pdo->rollBack();
    http_response_code(500);
    echo json_encode([
        'error' => $e->getMessage(),
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
}
