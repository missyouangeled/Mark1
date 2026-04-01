<?php
const DB_HOST = 'localhost';
const DB_NAME = 'wordpress';
const DB_USER = 'wp_user';
const DB_PASS = 'your_strong_password';

function db(): PDO {
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $pdo = new PDO(
        'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
        DB_USER,
        DB_PASS,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );

    return $pdo;
}

function start_session_if_needed(): void {
    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_start();
    }
}

function current_user(): ?array {
    start_session_if_needed();
    return $_SESSION['user'] ?? null;
}

function refresh_current_user(): ?array {
    start_session_if_needed();
    $user = current_user();
    if (!$user) {
        return null;
    }

    $stmt = db()->prepare('SELECT id, username, nickname, email, created_at FROM pulsenest_users WHERE id = :id LIMIT 1');
    $stmt->execute(['id' => $user['id']]);
    $fresh = $stmt->fetch();
    if (!$fresh) {
        unset($_SESSION['user']);
        return null;
    }

    $_SESSION['user'] = $fresh;
    return $fresh;
}

function login_user(array $user): void {
    start_session_if_needed();
    $_SESSION['user'] = [
        'id' => $user['id'],
        'username' => $user['username'],
        'nickname' => $user['nickname'],
        'email' => $user['email'],
        'created_at' => $user['created_at'] ?? null,
    ];
}

function redirect_to(string $path): void {
    header('Location: ' . $path);
    exit;
}

function ensure_guest_only(): void {
    if (current_user()) {
        redirect_to('/');
    }
}

function ensure_logged_in(): array {
    $user = refresh_current_user();
    if (!$user) {
        redirect_to('/login.php');
    }
    return $user;
}

function e(?string $value): string {
    return htmlspecialchars((string) $value, ENT_QUOTES, 'UTF-8');
}

function flash_set(string $type, string $message): void {
    start_session_if_needed();
    $_SESSION['flash'] = ['type' => $type, 'message' => $message];
}

function flash_get(): ?array {
    start_session_if_needed();
    if (!isset($_SESSION['flash'])) {
        return null;
    }
    $flash = $_SESSION['flash'];
    unset($_SESSION['flash']);
    return $flash;
}

function human_time(string $datetime): string {
    $timestamp = strtotime($datetime);
    if (!$timestamp) {
        return $datetime;
    }

    $diff = time() - $timestamp;
    if ($diff < 60) {
        return '刚刚';
    }
    if ($diff < 3600) {
        return floor($diff / 60) . ' 分钟前';
    }
    if ($diff < 86400) {
        return floor($diff / 3600) . ' 小时前';
    }
    if ($diff < 86400 * 7) {
        return floor($diff / 86400) . ' 天前';
    }
    return date('Y-m-d H:i', $timestamp);
}

function excerpt(string $text, int $length = 140): string {
    $plain = trim(preg_replace('/\s+/u', ' ', $text));
    if (mb_strlen($plain) <= $length) {
        return $plain;
    }
    return mb_substr($plain, 0, $length) . '…';
}

function password_reset_token(): string {
    return bin2hex(random_bytes(16));
}
