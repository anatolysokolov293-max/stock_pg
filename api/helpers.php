<?php
// api/helpers.php

function json_response($data, $status_code = 200) {
    http_response_code($status_code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    exit;
}

function json_error($message, $status_code = 400) {
    json_response(['error' => $message], $status_code);
}
