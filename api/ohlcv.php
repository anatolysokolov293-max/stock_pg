<?php
require_once __DIR__ . '/helpers.php';
// public/api/ohlcv.php
require_once __DIR__ . '/db.php';

$symbolId       = isset($_GET['symbol_id']) ? (int)$_GET['symbol_id'] : 0;
$timeframeTable = isset($_GET['timeframe_table']) ? trim($_GET['timeframe_table']) : '';
$start          = isset($_GET['start']) ? $_GET['start'] : '';
$end            = isset($_GET['end']) ? $_GET['end'] : '';

if ($symbolId <= 0 || $timeframeTable === '' || $start === '' || $end === '') {
    json_response(['error' => 'symbol_id, timeframe_table, start, end are required'], 400);
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
        SELECT timestamp, open, high, low, close, volume
        FROM {$timeframeTable}
        WHERE symbol_id = :symbol_id
          AND timestamp BETWEEN :start AND :end
        ORDER BY timestamp
    ";
    $stmt = $pdo->prepare($sql);
    $stmt->execute([
        'symbol_id' => $symbolId,
        'start'     => $start,
        'end'       => $end,
    ]);
    $rows = $stmt->fetchAll();

    $candles = array_map(function($r) {
        return [
            'time'   => gmdate('c', strtotime($r['timestamp'])),
            'open'   => (float)$r['open'],
            'high'   => (float)$r['high'],
            'low'    => (float)$r['low'],
            'close'  => (float)$r['close'],
            'volume' => (int)$r['volume'],
        ];
    }, $rows);

    json_response(['candles' => $candles]);
} catch (Throwable $e) {
    json_response(['error' => $e->getMessage()], 500);
}
