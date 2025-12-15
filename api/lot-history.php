<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Если это preflight запрос, отправляем правильные заголовки
if ($_SERVER['REQUEST_METHOD'] == 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Подключение к базе данных через db.php
require_once __DIR__ . '/db.php';

// Получаем symbol_id из параметра запроса
$symbol_id = isset($_GET['symbol_id']) ? intval($_GET['symbol_id']) : 0;

if ($symbol_id <= 0) {
    echo json_encode(['error' => 'Invalid symbol_id']);
    exit();
}

try {
    // Получаем соединение с БД через функцию из db.php
    $pdo = get_db_connection();

    // Запрашиваем историю лотов для указанного символа
    $stmt = $pdo->prepare("
        SELECT * FROM lot_history
        WHERE symbol_id = :symbol_id
        ORDER BY change_date ASC
    ");

    $stmt->execute([':symbol_id' => $symbol_id]);
    $lotHistory = $stmt->fetchAll(PDO::FETCH_ASSOC);

    echo json_encode(['lotHistory' => $lotHistory]);

} catch (PDOException $e) {
    echo json_encode(['error' => 'Database query failed: ' . $e->getMessage()]);
    exit();
}
?>
