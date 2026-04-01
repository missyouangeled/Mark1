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
    static $schemaEnsured = false;

    if (!$pdo instanceof PDO) {
        $pdo = new PDO(
            'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
            DB_USER,
            DB_PASS,
            [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            ]
        );
    }

    if (!$schemaEnsured) {
        ensure_database_schema($pdo);
        $schemaEnsured = true;
    }

    return $pdo;
}

function ensure_database_schema(PDO $pdo): void {
    if (!column_exists($pdo, 'pulsenest_users', 'is_admin')) {
        $pdo->exec("ALTER TABLE pulsenest_users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0 AFTER password_hash");
    }
    if (!column_exists($pdo, 'pulsenest_users', 'is_active')) {
        $pdo->exec("ALTER TABLE pulsenest_users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1 AFTER is_admin");
    }

    $pdo->exec("CREATE TABLE IF NOT EXISTS forum_categories (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        name VARCHAR(80) NOT NULL,
        slug VARCHAR(80) NOT NULL,
        description VARCHAR(255) DEFAULT NULL,
        sort_order INT NOT NULL DEFAULT 0,
        created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uniq_forum_categories_slug (slug)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS forum_boards (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        category_id INT UNSIGNED NOT NULL,
        name VARCHAR(80) NOT NULL,
        slug VARCHAR(80) NOT NULL,
        description VARCHAR(255) DEFAULT NULL,
        accent_color VARCHAR(20) DEFAULT NULL,
        sort_order INT NOT NULL DEFAULT 0,
        created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uniq_forum_boards_slug (slug),
        KEY idx_forum_boards_category_id (category_id),
        CONSTRAINT fk_forum_boards_category FOREIGN KEY (category_id) REFERENCES forum_categories(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS notifications (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        recipient_user_id INT UNSIGNED NOT NULL,
        actor_user_id INT UNSIGNED NOT NULL,
        post_id INT UNSIGNED NOT NULL,
        comment_id INT UNSIGNED DEFAULT NULL,
        type VARCHAR(40) NOT NULL,
        is_read TINYINT(1) NOT NULL DEFAULT 0,
        created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        KEY idx_notifications_recipient_read (recipient_user_id, is_read),
        KEY idx_notifications_post_id (post_id),
        KEY idx_notifications_comment_id (comment_id),
        CONSTRAINT fk_notifications_recipient FOREIGN KEY (recipient_user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE,
        CONSTRAINT fk_notifications_actor FOREIGN KEY (actor_user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE,
        CONSTRAINT fk_notifications_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
        CONSTRAINT fk_notifications_comment FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    if (!column_exists($pdo, 'posts', 'board_id')) {
        $pdo->exec('ALTER TABLE posts ADD COLUMN board_id INT UNSIGNED DEFAULT NULL AFTER user_id');
    }
    if (!index_exists($pdo, 'posts', 'idx_posts_board_id')) {
        $pdo->exec('ALTER TABLE posts ADD KEY idx_posts_board_id (board_id)');
    }
    if (!foreign_key_exists($pdo, 'posts', 'fk_posts_board')) {
        $pdo->exec('ALTER TABLE posts ADD CONSTRAINT fk_posts_board FOREIGN KEY (board_id) REFERENCES forum_boards(id) ON DELETE SET NULL');
    }

    seed_forum_structure($pdo);

    $defaultBoardId = (int) $pdo->query("SELECT id FROM forum_boards ORDER BY sort_order ASC, id ASC LIMIT 1")->fetchColumn();
    if ($defaultBoardId > 0) {
        $stmt = $pdo->prepare('UPDATE posts SET board_id = :board_id WHERE board_id IS NULL');
        $stmt->execute(['board_id' => $defaultBoardId]);
    }

    $adminCount = (int) $pdo->query('SELECT COUNT(*) FROM pulsenest_users WHERE is_admin = 1')->fetchColumn();
    if ($adminCount === 0) {
        $firstUserId = (int) $pdo->query('SELECT id FROM pulsenest_users ORDER BY id ASC LIMIT 1')->fetchColumn();
        if ($firstUserId > 0) {
            $stmt = $pdo->prepare('UPDATE pulsenest_users SET is_admin = 1 WHERE id = :id');
            $stmt->execute(['id' => $firstUserId]);
        }
    }
}

function column_exists(PDO $pdo, string $table, string $column): bool {
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND COLUMN_NAME = :column');
    $stmt->execute(['table' => $table, 'column' => $column]);
    return (bool) $stmt->fetchColumn();
}

function index_exists(PDO $pdo, string $table, string $index): bool {
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND INDEX_NAME = :index');
    $stmt->execute(['table' => $table, 'index' => $index]);
    return (bool) $stmt->fetchColumn();
}

function foreign_key_exists(PDO $pdo, string $table, string $constraint): bool {
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table AND CONSTRAINT_NAME = :constraint');
    $stmt->execute(['table' => $table, 'constraint' => $constraint]);
    return (bool) $stmt->fetchColumn();
}

function seed_forum_structure(PDO $pdo): void {
    $categories = [
        [
            'name' => '星港大厅',
            'slug' => 'starport',
            'description' => '社区总览、每日热聊和新人最容易进入的公共区。',
            'sort_order' => 10,
            'boards' => [
                ['name' => '综合讨论', 'slug' => 'general', 'description' => '随时抛观点、晒近况、接住当天热帖。', 'accent_color' => '#23d3a2', 'sort_order' => 10],
                ['name' => '新手报到', 'slug' => 'introductions', 'description' => '第一次来 PulseNest，就从这里露个面。', 'accent_color' => '#77e7ff', 'sort_order' => 20],
            ],
        ],
        [
            'name' => '深空回路',
            'slug' => 'deep-space',
            'description' => '更偏内容深聊、攻略拆解、世界观和评测。',
            'sort_order' => 20,
            'boards' => [
                ['name' => '攻略 / 评测', 'slug' => 'guides-reviews', 'description' => '打法、体验、长文评测都丢来这里。', 'accent_color' => '#b06df0', 'sort_order' => 10],
                ['name' => '截图 / 作品', 'slug' => 'screenshots-creations', 'description' => '发图、晒搭配、丢创作，视觉内容集中展示。', 'accent_color' => '#ff8bc2', 'sort_order' => 20],
            ],
        ],
    ];

    $categoryStmt = $pdo->prepare('INSERT INTO forum_categories (name, slug, description, sort_order) VALUES (:name, :slug, :description, :sort_order) ON DUPLICATE KEY UPDATE name = VALUES(name), description = VALUES(description), sort_order = VALUES(sort_order)');
    $boardStmt = $pdo->prepare('INSERT INTO forum_boards (category_id, name, slug, description, accent_color, sort_order) VALUES (:category_id, :name, :slug, :description, :accent_color, :sort_order) ON DUPLICATE KEY UPDATE category_id = VALUES(category_id), name = VALUES(name), description = VALUES(description), accent_color = VALUES(accent_color), sort_order = VALUES(sort_order)');
    $categoryIdStmt = $pdo->prepare('SELECT id FROM forum_categories WHERE slug = :slug LIMIT 1');

    foreach ($categories as $category) {
        $categoryStmt->execute([
            'name' => $category['name'],
            'slug' => $category['slug'],
            'description' => $category['description'],
            'sort_order' => $category['sort_order'],
        ]);
        $categoryIdStmt->execute(['slug' => $category['slug']]);
        $categoryId = (int) $categoryIdStmt->fetchColumn();
        foreach ($category['boards'] as $board) {
            $boardStmt->execute([
                'category_id' => $categoryId,
                'name' => $board['name'],
                'slug' => $board['slug'],
                'description' => $board['description'],
                'accent_color' => $board['accent_color'],
                'sort_order' => $board['sort_order'],
            ]);
        }
    }
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

    $stmt = db()->prepare('SELECT id, username, nickname, email, avatar_path, bio, is_admin, is_active, created_at FROM pulsenest_users WHERE id = :id LIMIT 1');
    $stmt->execute(['id' => $user['id']]);
    $fresh = $stmt->fetch();
    if (!$fresh || (int) ($fresh['is_active'] ?? 1) !== 1) {
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
        'is_admin' => (int) ($user['is_admin'] ?? 0),
        'is_active' => (int) ($user['is_active'] ?? 1),
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
    if (!$user || (int) ($user['is_active'] ?? 1) !== 1) {
        start_session_if_needed();
        unset($_SESSION['user']);
        redirect_to('/login.php');
    }
    return $user;
}

function is_admin(?array $user): bool {
    return (int) ($user['is_admin'] ?? 0) === 1;
}

function ensure_admin(): array {
    $user = ensure_logged_in();
    if (!is_admin($user)) {
        http_response_code(403);
        exit('Forbidden');
    }
    return $user;
}

function can_manage_post(?array $user, array $post): bool {
    return $user && (is_admin($user) || (int) $user['id'] === (int) ($post['user_id'] ?? 0));
}

function can_manage_comment(?array $user, array $comment): bool {
    return $user && (is_admin($user) || (int) $user['id'] === (int) ($comment['user_id'] ?? 0));
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

function delete_uploaded_asset(?string $path): void {
    if (!$path) {
        return;
    }
    $normalized = ltrim(str_replace('\\', '/', $path), '/');
    if (!str_starts_with($normalized, 'uploads/')) {
        return;
    }
    $target = __DIR__ . '/' . $normalized;
    if (is_file($target)) {
        @unlink($target);
    }
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

function board_badge(array $post): string {
    $boardName = trim((string) ($post['board_name'] ?? '未分区'));
    $categoryName = trim((string) ($post['category_name'] ?? '公共区'));
    return $categoryName . ' / ' . $boardName;
}

function fetch_forum_structure(): array {
    $categories = db()->query(
        'SELECT c.id, c.name, c.slug, c.description, c.sort_order,
                b.id AS board_id, b.name AS board_name, b.slug AS board_slug, b.description AS board_description, b.accent_color, b.sort_order AS board_sort_order,
                COALESCE(pc.post_count, 0) AS post_count
         FROM forum_categories c
         LEFT JOIN forum_boards b ON b.category_id = c.id
         LEFT JOIN (
            SELECT board_id, COUNT(*) AS post_count FROM posts GROUP BY board_id
         ) pc ON pc.board_id = b.id
         ORDER BY c.sort_order ASC, c.id ASC, b.sort_order ASC, b.id ASC'
    )->fetchAll();

    $grouped = [];
    foreach ($categories as $row) {
        $categoryId = (int) $row['id'];
        if (!isset($grouped[$categoryId])) {
            $grouped[$categoryId] = [
                'id' => $categoryId,
                'name' => $row['name'],
                'slug' => $row['slug'],
                'description' => $row['description'],
                'boards' => [],
            ];
        }
        if (!empty($row['board_id'])) {
            $grouped[$categoryId]['boards'][] = [
                'id' => (int) $row['board_id'],
                'name' => $row['board_name'],
                'slug' => $row['board_slug'],
                'description' => $row['board_description'],
                'accent_color' => $row['accent_color'],
                'post_count' => (int) $row['post_count'],
            ];
        }
    }

    return array_values($grouped);
}

function fetch_board_options(): array {
    return db()->query(
        'SELECT b.id, b.name, b.slug, b.description, c.name AS category_name, c.slug AS category_slug
         FROM forum_boards b
         INNER JOIN forum_categories c ON c.id = b.category_id
         ORDER BY c.sort_order ASC, c.id ASC, b.sort_order ASC, b.id ASC'
    )->fetchAll();
}

function unread_notification_count(?int $userId): int {
    if (!$userId) {
        return 0;
    }
    $stmt = db()->prepare('SELECT COUNT(*) FROM notifications WHERE recipient_user_id = :user_id AND is_read = 0');
    $stmt->execute(['user_id' => $userId]);
    return (int) $stmt->fetchColumn();
}

function create_notification(int $recipientUserId, int $actorUserId, string $type, int $postId, ?int $commentId = null): void {
    if ($recipientUserId === $actorUserId) {
        return;
    }

    $stmt = db()->prepare('INSERT INTO notifications (recipient_user_id, actor_user_id, post_id, comment_id, type) VALUES (:recipient_user_id, :actor_user_id, :post_id, :comment_id, :type)');
    $stmt->execute([
        'recipient_user_id' => $recipientUserId,
        'actor_user_id' => $actorUserId,
        'post_id' => $postId,
        'comment_id' => $commentId,
        'type' => $type,
    ]);
}

function create_reply_notifications(array $post, ?array $parentComment, int $actorUserId, int $newCommentId): void {
    $recipients = [];

    if ((int) ($post['user_id'] ?? 0) > 0 && (int) $post['user_id'] !== $actorUserId) {
        $recipients[(int) $post['user_id']] = 'post_reply';
    }

    if ($parentComment && (int) $parentComment['user_id'] > 0 && (int) $parentComment['user_id'] !== $actorUserId) {
        $recipients[(int) $parentComment['user_id']] = 'comment_reply';
    }

    foreach ($recipients as $recipientId => $type) {
        create_notification($recipientId, $actorUserId, $type, (int) $post['id'], $newCommentId);
    }
}
