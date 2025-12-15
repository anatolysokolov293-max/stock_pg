<?php
// db.php - PostgreSQL connection

function getDbConnection(): PDO {
    $host = '127.0.0.1';
    $port = 5432;
    $db = 'stock_db';
    $user = 'postgres';
    $pass = '123';

    $dsn = "pgsql:host=$host;port=$port;dbname=$db";

    $options = [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ];

    return new PDO($dsn, $user, $pass, $options);
}

// Alias for snake_case naming
function get_db_connection() {
    return getDbConnection();
}