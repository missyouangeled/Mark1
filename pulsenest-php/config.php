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
    if (!column_exists($pdo, 'pulsenest_users', 'role')) {
        $pdo->exec("ALTER TABLE pulsenest_users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'member' AFTER is_active");
        $pdo->exec("UPDATE pulsenest_users SET role = CASE WHEN is_admin = 1 THEN 'admin' ELSE 'member' END");
    }
    $pdo->exec("UPDATE pulsenest_users SET role = CASE WHEN role = '' OR role IS NULL THEN CASE WHEN is_admin = 1 THEN 'admin' ELSE 'member' END ELSE role END");
    $pdo->exec("UPDATE pulsenest_users SET is_admin = CASE WHEN role = 'admin' THEN 1 ELSE 0 END");

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
        moderation_status VARCHAR(20) DEFAULT NULL,
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

    $pdo->exec("CREATE TABLE IF NOT EXISTS site_settings (
        setting_key VARCHAR(80) NOT NULL,
        setting_value TEXT DEFAULT NULL,
        updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (setting_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS comment_likes (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        comment_id INT UNSIGNED NOT NULL,
        user_id INT UNSIGNED NOT NULL,
        created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        UNIQUE KEY uniq_comment_likes_comment_user (comment_id, user_id),
        KEY idx_comment_likes_user_id (user_id),
        CONSTRAINT fk_comment_likes_comment FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
        CONSTRAINT fk_comment_likes_user FOREIGN KEY (user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    $pdo->exec("CREATE TABLE IF NOT EXISTS moderation_logs (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT,
        actor_user_id INT UNSIGNED NOT NULL,
        action_type VARCHAR(40) NOT NULL,
        target_type VARCHAR(40) NOT NULL,
        target_id INT UNSIGNED DEFAULT NULL,
        details VARCHAR(255) DEFAULT NULL,
        created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (id),
        KEY idx_moderation_logs_actor_id (actor_user_id),
        KEY idx_moderation_logs_target (target_type, target_id),
        CONSTRAINT fk_moderation_logs_actor FOREIGN KEY (actor_user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");

    if (!index_exists($pdo, 'moderation_logs', 'idx_moderation_logs_action_type')) {
        $pdo->exec('ALTER TABLE moderation_logs ADD KEY idx_moderation_logs_action_type (action_type)');
    }
    if (!index_exists($pdo, 'moderation_logs', 'idx_moderation_logs_actor_created')) {
        $pdo->exec('ALTER TABLE moderation_logs ADD KEY idx_moderation_logs_actor_created (actor_user_id, created_at)');
    }
    if (!index_exists($pdo, 'moderation_logs', 'idx_moderation_logs_target_created')) {
        $pdo->exec('ALTER TABLE moderation_logs ADD KEY idx_moderation_logs_target_created (target_type, created_at)');
    }

    if (!column_exists($pdo, 'posts', 'board_id')) {
        $pdo->exec('ALTER TABLE posts ADD COLUMN board_id INT UNSIGNED DEFAULT NULL AFTER user_id');
    }
    if (!index_exists($pdo, 'posts', 'idx_posts_board_id')) {
        $pdo->exec('ALTER TABLE posts ADD KEY idx_posts_board_id (board_id)');
    }
    if (!foreign_key_exists($pdo, 'posts', 'fk_posts_board')) {
        $pdo->exec('ALTER TABLE posts ADD CONSTRAINT fk_posts_board FOREIGN KEY (board_id) REFERENCES forum_boards(id) ON DELETE SET NULL');
    }
    if (!index_exists($pdo, 'posts', 'idx_posts_created_board')) {
        $pdo->exec('ALTER TABLE posts ADD KEY idx_posts_created_board (board_id, created_at)');
    }
    if (!column_exists($pdo, 'posts', 'is_sticky')) {
        $pdo->exec('ALTER TABLE posts ADD COLUMN is_sticky TINYINT(1) NOT NULL DEFAULT 0 AFTER image_path');
    }
    if (!column_exists($pdo, 'posts', 'is_featured')) {
        $pdo->exec('ALTER TABLE posts ADD COLUMN is_featured TINYINT(1) NOT NULL DEFAULT 0 AFTER is_sticky');
    }
    if (!column_exists($pdo, 'posts', 'recommend_level')) {
        $pdo->exec('ALTER TABLE posts ADD COLUMN recommend_level TINYINT UNSIGNED NOT NULL DEFAULT 0 AFTER is_featured');
    }
    if (!column_exists($pdo, 'posts', 'home_slot')) {
        $pdo->exec('ALTER TABLE posts ADD COLUMN home_slot VARCHAR(40) DEFAULT NULL AFTER recommend_level');
    }
    if (!column_exists($pdo, 'posts', 'recommend_group')) {
        $pdo->exec("ALTER TABLE posts ADD COLUMN recommend_group VARCHAR(40) NOT NULL DEFAULT 'general' AFTER home_slot");
    }
    if (!column_exists($pdo, 'posts', 'recommend_priority')) {
        $pdo->exec('ALTER TABLE posts ADD COLUMN recommend_priority INT NOT NULL DEFAULT 0 AFTER recommend_group');
    }
    if (!index_exists($pdo, 'posts', 'idx_posts_ops_sort')) {
        $pdo->exec('ALTER TABLE posts ADD KEY idx_posts_ops_sort (is_sticky, recommend_level, is_featured, created_at)');
    }
    if (!index_exists($pdo, 'posts', 'idx_posts_recommend_group_priority')) {
        $pdo->exec('ALTER TABLE posts ADD KEY idx_posts_recommend_group_priority (recommend_group, recommend_priority, recommend_level, created_at)');
    }
    if (!index_exists($pdo, 'posts', 'idx_posts_home_slot')) {
        $pdo->exec('ALTER TABLE posts ADD UNIQUE KEY idx_posts_home_slot (home_slot)');
    }
    if (!index_exists($pdo, 'comments', 'idx_comments_post_created')) {
        $pdo->exec('ALTER TABLE comments ADD KEY idx_comments_post_created (post_id, created_at)');
    }
    if (!index_exists($pdo, 'comments', 'idx_comments_user_created')) {
        $pdo->exec('ALTER TABLE comments ADD KEY idx_comments_user_created (user_id, created_at)');
    }
    if (!column_exists($pdo, 'comments', 'status')) {
        $pdo->exec("ALTER TABLE comments ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'approved' AFTER content");
    }
    $pdo->exec("UPDATE comments SET status = 'approved' WHERE status IS NULL OR status = ''");
    if (!index_exists($pdo, 'comments', 'idx_comments_status_created')) {
        $pdo->exec('ALTER TABLE comments ADD KEY idx_comments_status_created (status, created_at)');
    }
    if (!index_exists($pdo, 'comments', 'idx_comments_post_status_created')) {
        $pdo->exec('ALTER TABLE comments ADD KEY idx_comments_post_status_created (post_id, status, created_at)');
    }
    if (!index_exists($pdo, 'forum_categories', 'idx_forum_categories_sort')) {
        $pdo->exec('ALTER TABLE forum_categories ADD KEY idx_forum_categories_sort (sort_order, id)');
    }
    if (!index_exists($pdo, 'forum_boards', 'idx_forum_boards_category_sort')) {
        $pdo->exec('ALTER TABLE forum_boards ADD KEY idx_forum_boards_category_sort (category_id, sort_order, id)');
    }
    if (!column_exists($pdo, 'notifications', 'moderation_status')) {
        $pdo->exec('ALTER TABLE notifications ADD COLUMN moderation_status VARCHAR(20) DEFAULT NULL AFTER type');
    }
    if (!index_exists($pdo, 'notifications', 'idx_notifications_type_created')) {
        $pdo->exec('ALTER TABLE notifications ADD KEY idx_notifications_type_created (type, created_at)');
    }
    if (!index_exists($pdo, 'notifications', 'idx_notifications_recipient_created')) {
        $pdo->exec('ALTER TABLE notifications ADD KEY idx_notifications_recipient_created (recipient_user_id, created_at)');
    }

    seed_forum_structure($pdo);
    seed_site_settings($pdo);

    $defaultBoardId = (int) $pdo->query("SELECT id FROM forum_boards ORDER BY sort_order ASC, id ASC LIMIT 1")->fetchColumn();
    if ($defaultBoardId > 0) {
        $stmt = $pdo->prepare('UPDATE posts SET board_id = :board_id WHERE board_id IS NULL');
        $stmt->execute(['board_id' => $defaultBoardId]);
    }

    $adminCount = (int) $pdo->query("SELECT COUNT(*) FROM pulsenest_users WHERE role = 'admin'")->fetchColumn();
    if ($adminCount === 0) {
        $firstUserId = (int) $pdo->query('SELECT id FROM pulsenest_users ORDER BY id ASC LIMIT 1')->fetchColumn();
        if ($firstUserId > 0) {
            $stmt = $pdo->prepare("UPDATE pulsenest_users SET is_admin = 1, role = 'admin' WHERE id = :id");
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

function seed_site_settings(PDO $pdo): void {
    $defaults = default_home_copy_settings();
    $stmt = $pdo->prepare('INSERT INTO site_settings (setting_key, setting_value) VALUES (:setting_key, :setting_value) ON DUPLICATE KEY UPDATE setting_value = COALESCE(site_settings.setting_value, VALUES(setting_value))');
    foreach ($defaults as $key => $value) {
        $stmt->execute([
            'setting_key' => $key,
            'setting_value' => $value,
        ]);
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

    $stmt = db()->prepare('SELECT id, username, nickname, email, avatar_path, bio, is_admin, is_active, role, created_at FROM pulsenest_users WHERE id = :id LIMIT 1');
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
        'role' => $user['role'] ?? ((int) ($user['is_admin'] ?? 0) === 1 ? 'admin' : 'member'),
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

function user_role(?array $user): string {
    $role = trim((string) ($user['role'] ?? ''));
    if ($role !== '') {
        return $role;
    }
    return (int) ($user['is_admin'] ?? 0) === 1 ? 'admin' : 'member';
}

function is_admin(?array $user): bool {
    return user_role($user) === 'admin';
}

function is_moderator(?array $user): bool {
    return user_role($user) === 'moderator';
}

function can_access_admin(?array $user): bool {
    return is_admin($user) || is_moderator($user);
}

function can_manage_users(?array $user): bool {
    return is_admin($user);
}

function can_manage_forum_structure(?array $user): bool {
    return is_admin($user);
}

function can_moderate_content(?array $user): bool {
    return is_admin($user) || is_moderator($user);
}

function role_label(?string $role): string {
    return match ($role ?: 'member') {
        'admin' => '管理员',
        'moderator' => '版主',
        default => '成员',
    };
}

function ensure_admin(): array {
    $user = ensure_logged_in();
    if (!is_admin($user)) {
        http_response_code(403);
        exit('Forbidden');
    }
    return $user;
}

function ensure_staff(): array {
    $user = ensure_logged_in();
    if (!can_access_admin($user)) {
        http_response_code(403);
        exit('Forbidden');
    }
    return $user;
}

function can_manage_post(?array $user, array $post): bool {
    return $user && (can_moderate_content($user) || (int) $user['id'] === (int) ($post['user_id'] ?? 0));
}

function can_manage_comment(?array $user, array $comment): bool {
    return $user && (can_moderate_content($user) || (int) $user['id'] === (int) ($comment['user_id'] ?? 0));
}

function log_moderation_action(int $actorUserId, string $actionType, string $targetType, ?int $targetId = null, ?string $details = null): void {
    $stmt = db()->prepare('INSERT INTO moderation_logs (actor_user_id, action_type, target_type, target_id, details) VALUES (:actor_user_id, :action_type, :target_type, :target_id, :details)');
    $stmt->execute([
        'actor_user_id' => $actorUserId,
        'action_type' => $actionType,
        'target_type' => $targetType,
        'target_id' => $targetId,
        'details' => $details ? mb_substr($details, 0, 255) : null,
    ]);
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

function comment_status_label(string $status): string {
    return match ($status) {
        'pending' => '待审核',
        'hidden' => '已隐藏',
        default => '已通过',
    };
}

function home_slot_definitions(): array {
    return [
        'hero' => ['label' => '首页主视觉 Hero', 'desc' => '首页顶部主运营卡'],
        'focus_one' => ['label' => '首页焦点卡 1', 'desc' => '中部焦点区第一张运营卡'],
        'focus_two' => ['label' => '首页焦点卡 2', 'desc' => '中部焦点区第二张运营卡'],
        'focus_three' => ['label' => '首页焦点卡 3', 'desc' => '中部焦点区第三张运营卡'],
    ];
}

function recommend_group_definitions(): array {
    return [
        'general' => ['label' => '综合推荐', 'desc' => '默认全站推荐池'],
        'event' => ['label' => '活动 / 公告', 'desc' => '适合活动帖、征集帖、版本通知'],
        'guide' => ['label' => '攻略 / 深读', 'desc' => '更偏攻略、评测、长文'],
    ];
}

function default_home_copy_settings(): array {
    return [
        'home.hero.eyebrow' => '星云初始01 · 首页升级到可运营的论坛首页',
        'home.hero.title' => '保住这套星云观感的同时，把真正能运营的帖子位也接进来。',
        'home.hero.body' => '首页现在不只读最新帖子，而是优先吃后台运营位：支持帖子置顶、精华、推荐位排序，以及 Hero / 焦点卡绑定，既不破坏“星云初始01”的视觉锚点，也让首页有了明确运营抓手。',
        'home.hero.tag_primary' => '首页运营卡',
        'home.hero.tag_secondary' => '站内回复提醒',
        'home.hero.use_custom_title' => '1',
        'home.hero.use_custom_body' => '1',
        'home.focus_one.badge' => 'OPS SLOT',
        'home.focus_one.title' => '焦点卡 1 待绑定',
        'home.focus_one.body' => '后台可把重点帖子直接塞进这张中部卡位。',
        'home.focus_one.tag' => '焦点卡 1',
        'home.focus_two.badge' => 'OPS SLOT',
        'home.focus_two.title' => '焦点卡 2 待绑定',
        'home.focus_two.body' => '适合放活动帖、征集帖、版本说明帖。',
        'home.focus_two.tag' => '焦点卡 2',
        'home.focus_three.badge' => 'OPS SLOT',
        'home.focus_three.title' => '焦点卡 3 待绑定',
        'home.focus_three.body' => '维持视觉稳定，同时把中段内容改成可运营入口。',
        'home.focus_three.tag' => '焦点卡 3',
    ];
}

function get_site_setting(string $key, ?string $default = null): ?string {
    $stmt = db()->prepare('SELECT setting_value FROM site_settings WHERE setting_key = :setting_key LIMIT 1');
    $stmt->execute(['setting_key' => $key]);
    $value = $stmt->fetchColumn();
    return $value === false ? $default : (string) $value;
}

function set_site_settings(array $settings): void {
    if (!$settings) {
        return;
    }
    $stmt = db()->prepare('INSERT INTO site_settings (setting_key, setting_value) VALUES (:setting_key, :setting_value) ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)');
    foreach ($settings as $key => $value) {
        $stmt->execute([
            'setting_key' => $key,
            'setting_value' => $value,
        ]);
    }
}

function home_copy_config(): array {
    $defaults = default_home_copy_settings();
    $keys = array_keys($defaults);
    $placeholders = implode(',', array_fill(0, count($keys), '?'));
    $stmt = db()->prepare('SELECT setting_key, setting_value FROM site_settings WHERE setting_key IN (' . $placeholders . ')');
    $stmt->execute($keys);
    $rows = $stmt->fetchAll();
    $config = $defaults;
    foreach ($rows as $row) {
        $config[$row['setting_key']] = (string) $row['setting_value'];
    }
    return $config;
}

function render_pagination(string $basePath, int $page, int $totalPages, array $query = [], string $hash = ''): string {
    $buildUrl = static function (int $targetPage) use ($basePath, $query, $hash): string {
        $params = array_merge($query, ['page' => $targetPage]);
        foreach ($params as $key => $value) {
            if ($value === null || $value === '' || $value === 0 || $value === '0') {
                unset($params[$key]);
            }
        }
        $url = $basePath;
        if ($params) {
            $url .= '?' . http_build_query($params);
        }
        return $url . $hash;
    };

    return '<div class="admin-pagination">'
        . '<a class="pill-btn ' . ($page <= 1 ? 'is-disabled' : '') . '" ' . ($page <= 1 ? 'aria-disabled="true"' : 'href="' . e($buildUrl($page - 1)) . '"') . '>上一页</a>'
        . '<div class="pagination-status">第 <strong>' . $page . '</strong> 页 / 共 <strong>' . $totalPages . '</strong> 页</div>'
        . '<a class="pill-btn ' . ($page >= $totalPages ? 'is-disabled' : '') . '" ' . ($page >= $totalPages ? 'aria-disabled="true"' : 'href="' . e($buildUrl($page + 1)) . '"') . '>下一页</a>'
        . '</div>';
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

function create_notification(int $recipientUserId, int $actorUserId, string $type, int $postId, ?int $commentId = null, array $meta = []): void {
    if ($recipientUserId === $actorUserId) {
        return;
    }

    $stmt = db()->prepare('INSERT INTO notifications (recipient_user_id, actor_user_id, post_id, comment_id, type, moderation_status) VALUES (:recipient_user_id, :actor_user_id, :post_id, :comment_id, :type, :moderation_status)');
    $stmt->execute([
        'recipient_user_id' => $recipientUserId,
        'actor_user_id' => $actorUserId,
        'post_id' => $postId,
        'comment_id' => $commentId,
        'type' => $type,
        'moderation_status' => $meta['moderation_status'] ?? null,
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

function create_post_like_notification(array $post, int $actorUserId): void {
    $recipientUserId = (int) ($post['user_id'] ?? 0);
    if ($recipientUserId > 0) {
        create_notification($recipientUserId, $actorUserId, 'post_like', (int) $post['id']);
    }
}

function create_comment_like_notification(array $comment, int $postId, int $actorUserId): void {
    $recipientUserId = (int) ($comment['user_id'] ?? 0);
    if ($recipientUserId > 0) {
        create_notification($recipientUserId, $actorUserId, 'comment_like', $postId, (int) $comment['id']);
    }
}

function create_comment_moderation_notification(array $comment, array $post, int $actorUserId, string $targetStatus): void {
    $recipientUserId = (int) ($comment['user_id'] ?? 0);
    $commentId = (int) ($comment['id'] ?? 0);
    $postId = (int) ($post['id'] ?? 0);
    if ($recipientUserId <= 0 || $commentId <= 0 || $postId <= 0) {
        return;
    }
    if (!in_array($targetStatus, ['approved', 'hidden'], true)) {
        return;
    }
    create_notification($recipientUserId, $actorUserId, 'comment_moderated', $postId, $commentId, [
        'moderation_status' => $targetStatus,
    ]);
}

function notification_type_label(string $type): string {
    return match ($type) {
        'comment_reply' => '评论回复',
        'post_reply' => '帖子回复',
        'post_like' => '帖子点赞',
        'comment_like' => '评论点赞',
        'comment_moderated' => '评论审核',
        default => '站内提醒',
    };
}

function notification_moderation_copy(?string $status): array {
    return match ($status ?: '') {
        'approved' => [
            'label' => '已通过',
            'verb' => '已通过',
            'summary' => '你的评论已审核通过',
            'description' => '你的评论已审核通过，已重新对外展示。',
        ],
        'hidden' => [
            'label' => '已隐藏',
            'verb' => '已隐藏',
            'summary' => '你的评论已被隐藏',
            'description' => '你的评论已被隐藏，当前不会在前台公开展示。',
        ],
        default => [
            'label' => '状态更新',
            'verb' => '已更新',
            'summary' => '你的评论审核状态已更新',
            'description' => '你的评论审核状态发生变化，请前往帖子查看。',
        ],
    };
}

function hero_uses_custom_title(array $homeCopy): bool {
    return ($homeCopy['home.hero.use_custom_title'] ?? '1') === '1';
}

function hero_uses_custom_body(array $homeCopy): bool {
    return ($homeCopy['home.hero.use_custom_body'] ?? '1') === '1';
}

function notification_message(array $item): string {
    $title = '《' . trim((string) ($item['title'] ?? '这篇帖子')) . '》';
    return match ($item['type'] ?? '') {
        'comment_reply' => '回复了你的评论：' . $title,
        'post_like' => '点赞了你的帖子：' . $title,
        'comment_like' => '点赞了你在 ' . $title . ' 下的评论',
        'comment_moderated' => notification_moderation_copy($item['moderation_status'] ?? null)['summary'] . '：' . $title,
        default => '回复了你的帖子：' . $title,
    };
}
