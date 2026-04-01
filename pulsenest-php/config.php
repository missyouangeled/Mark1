<?php
const DB_HOST = 'localhost';
const DB_NAME = 'wordpress';
const DB_USER = 'wp_user';
const DB_PASS = 'your_strong_password';
const UPLOAD_ROOT = __DIR__ . '/uploads';
const AVATAR_UPLOAD_DIR = 'avatars';
const POST_UPLOAD_DIR = 'posts';
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

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

    $stmt = db()->prepare('SELECT id, username, nickname, email, avatar_path, bio, created_at FROM pulsenest_users WHERE id = :id LIMIT 1');
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
        'avatar_path' => $user['avatar_path'] ?? null,
        'bio' => $user['bio'] ?? null,
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

function csrf_token(): string {
    start_session_if_needed();
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(24));
    }
    return $_SESSION['csrf_token'];
}

function verify_csrf(): void {
    start_session_if_needed();
    $token = (string) ($_POST['csrf_token'] ?? '');
    if (!$token || !hash_equals($_SESSION['csrf_token'] ?? '', $token)) {
        http_response_code(422);
        exit('CSRF token invalid.');
    }
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

function ensure_upload_directories(): void {
    foreach ([UPLOAD_ROOT, UPLOAD_ROOT . '/' . AVATAR_UPLOAD_DIR, UPLOAD_ROOT . '/' . POST_UPLOAD_DIR] as $dir) {
        if (!is_dir($dir)) {
            mkdir($dir, 0775, true);
        }
    }
}

function normalize_uploaded_relative_path(?string $path): ?string {
    if (!$path) {
        return null;
    }
    return 'uploads/' . ltrim(str_replace('\\', '/', $path), '/');
}

function upload_relative_path(string $subDir, string $filename): string {
    return trim($subDir, '/') . '/' . $filename;
}

function handle_image_upload(array $file, string $subDir): ?string {
    if (($file['error'] ?? UPLOAD_ERR_NO_FILE) === UPLOAD_ERR_NO_FILE) {
        return null;
    }

    if (($file['error'] ?? UPLOAD_ERR_OK) !== UPLOAD_ERR_OK) {
        throw new RuntimeException('上传失败，请换一张图片再试。');
    }

    if (($file['size'] ?? 0) <= 0 || ($file['size'] ?? 0) > MAX_UPLOAD_BYTES) {
        throw new RuntimeException('图片大小需控制在 5MB 以内。');
    }

    $tmp = $file['tmp_name'] ?? '';
    if (!is_uploaded_file($tmp)) {
        throw new RuntimeException('未识别到有效上传文件。');
    }

    $mime = mime_content_type($tmp) ?: '';
    $ext = match ($mime) {
        'image/jpeg' => 'jpg',
        'image/png' => 'png',
        'image/gif' => 'gif',
        'image/webp' => 'webp',
        default => null,
    };

    if (!$ext) {
        throw new RuntimeException('当前只支持 JPG、PNG、GIF、WEBP 图片。');
    }

    ensure_upload_directories();
    $filename = date('YmdHis') . '-' . bin2hex(random_bytes(5)) . '.' . $ext;
    $relative = upload_relative_path($subDir, $filename);
    $target = UPLOAD_ROOT . '/' . $relative;

    if (!move_uploaded_file($tmp, $target)) {
        throw new RuntimeException('图片保存失败，请稍后重试。');
    }

    return normalize_uploaded_relative_path($relative);
}

function asset_url(?string $path): ?string {
    if (!$path) {
        return null;
    }
    return '/' . ltrim(str_replace('\\', '/', $path), '/');
}

function avatar_url(?array $user): ?string {
    return asset_url($user['avatar_path'] ?? null);
}

function profile_url(array $user): string {
    return '/user.php?id=' . (int) $user['id'];
}

function avatar_fallback_text(?array $user): string {
    $name = trim((string) ($user['nickname'] ?? $user['username'] ?? 'PN'));
    return mb_strtoupper(mb_substr($name, 0, 1));
}

function render_avatar(?array $user, string $class = 'user-avatar'): string {
    $url = avatar_url($user);
    $fallback = e(avatar_fallback_text($user));
    if ($url) {
        return '<img class="' . e($class) . ' avatar-image" src="' . e($url) . '" alt="' . $fallback . '">';
    }
    return '<div class="' . e($class) . ' avatar-fallback">' . $fallback . '</div>';
}

function like_button_label(bool $liked, int $count): string {
    return ($liked ? '已赞' : '点赞') . ' · ' . $count;
}
