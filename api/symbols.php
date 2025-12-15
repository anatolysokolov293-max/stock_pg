<?php
require_once __DIR__ . '/helpers.php';
// public/api/symbols.php
require_once __DIR__ . '/db.php';

try {
    $pdo = get_db_connection();

    $stmt = $pdo->query("SELECT id, ticker, name FROM symbols ORDER BY ticker");
    $symbols = $stmt->fetchAll();

    json_response(['symbols' => $symbols]);
} catch (Throwable $e) {
    json_response(['error' => $e->getMessage()], 500);
}
