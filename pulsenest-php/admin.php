<?php
require __DIR__ . '/layout.php';
$user = ensure_staff();
$flash = flash_get();
$canManageUsers = can_manage_users($user);
$canManageStructure = can_manage_forum_structure($user);
$role = user_role($user);

function admin_url(array $overrides = [], string $hash = ''): string {
    $query = [
        'post_id' => (int) ($_GET['post_id'] ?? 0),
        'author_id' => (int) ($_GET['author_id'] ?? 0),
        'post_title_keyword' => trim((string) ($_GET['post_title_keyword'] ?? '')),
        'author_keyword' => trim((string) ($_GET['author_keyword'] ?? '')),
        'content_keyword' => trim((string) ($_GET['content_keyword'] ?? '')),
        'comment_status' => trim((string) ($_GET['comment_status'] ?? '')),
        'post_recommend_group' => trim((string) ($_GET['post_recommend_group'] ?? '')),
        'post_recommend_priority' => trim((string) ($_GET['post_recommend_priority'] ?? '')),
        'post_is_sticky' => trim((string) ($_GET['post_is_sticky'] ?? '')),
        'post_is_featured' => trim((string) ($_GET['post_is_featured'] ?? '')),
        'post_home_slot' => trim((string) ($_GET['post_home_slot'] ?? '')),
        'post_page' => (int) ($_GET['post_page'] ?? 1),
        'comment_page' => (int) ($_GET['comment_page'] ?? 1),
        'log_action' => trim((string) ($_GET['log_action'] ?? '')),
        'log_target_type' => trim((string) ($_GET['log_target_type'] ?? '')),
        'log_actor_id' => (int) ($_GET['log_actor_id'] ?? 0),
        'log_page' => (int) ($_GET['log_page'] ?? 1),
    ];

    foreach ($overrides as $key => $value) {
        $query[$key] = $value;
    }

    foreach ($query as $key => $value) {
        if ($value === null || $value === '' || $value === 0 || $value === '0') {
            unset($query[$key]);
        }
    }

    $url = '/admin.php';
    if ($query) {
        $url .= '?' . http_build_query($query);
    }
    if ($hash !== '') {
        $url .= $hash;
    }
    return $url;
}

function admin_notification_copy(string $type): string {
    return match ($type) {
        'post_like' => '有人点赞帖子',
        'comment_like' => '有人点赞评论',
        'comment_reply' => '有人回复评论',
        'comment_moderated' => '评论审核结果通知作者（区分已通过 / 已隐藏）',
        default => '有人回复帖子',
    };
}

function site_setting_field_name(string $settingKey): string {
    return 'setting_' . str_replace('.', '__', $settingKey);
}

function admin_pagination(array $baseQuery, string $pageKey, int $page, int $totalPages, string $hash = ''): string {
    $buildUrl = static function (int $targetPage) use ($baseQuery, $pageKey, $hash): string {
        $query = array_merge($baseQuery, [$pageKey => $targetPage]);
        return admin_url($query, $hash);
    };

    return '<div class="admin-pagination">'
        . '<a class="pill-btn ' . ($page <= 1 ? 'is-disabled' : '') . '" ' . ($page <= 1 ? 'aria-disabled="true"' : 'href="' . e($buildUrl($page - 1)) . '"') . '>上一页</a>'
        . '<div class="pagination-status">第 <strong>' . $page . '</strong> 页 / 共 <strong>' . $totalPages . '</strong> 页</div>'
        . '<a class="pill-btn ' . ($page >= $totalPages ? 'is-disabled' : '') . '" ' . ($page >= $totalPages ? 'aria-disabled="true"' : 'href="' . e($buildUrl($page + 1)) . '"') . '>下一页</a>'
        . '</div>';
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = $_POST['action'] ?? '';

    if ($action === 'toggle_user_active') {
        if (!$canManageUsers) {
            http_response_code(403);
            exit('Forbidden');
        }
        $targetUserId = (int) ($_POST['user_id'] ?? 0);
        $targetStatus = (int) ($_POST['target_status'] ?? 0);
        $stmt = db()->prepare('SELECT id, nickname, username, role FROM pulsenest_users WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $targetUserId]);
        $targetUser = $stmt->fetch();

        if (!$targetUser) {
            flash_set('error', '没有找到目标用户。');
        } elseif ($targetUserId === (int) $user['id'] && $targetStatus === 0) {
            flash_set('error', '不能把当前自己停用。');
        } else {
            $stmt = db()->prepare('UPDATE pulsenest_users SET is_active = :is_active WHERE id = :id LIMIT 1');
            $stmt->execute(['is_active' => $targetStatus ? 1 : 0, 'id' => $targetUserId]);
            log_moderation_action((int) $user['id'], $targetStatus ? 'user_enabled' : 'user_disabled', 'user', $targetUserId, ($targetUser['nickname'] ?: $targetUser['username']) . ' · ' . role_label($targetUser['role'] ?? 'member'));
            flash_set('success', $targetStatus ? '用户已启用。' : '用户已停用。');
        }
        redirect_to('/admin.php#users');
    }

    if ($action === 'set_user_role') {
        if (!$canManageUsers) {
            http_response_code(403);
            exit('Forbidden');
        }
        $targetUserId = (int) ($_POST['user_id'] ?? 0);
        $targetRole = trim((string) ($_POST['role'] ?? 'member'));
        $allowedRoles = ['member', 'moderator', 'admin'];
        if (!in_array($targetRole, $allowedRoles, true)) {
            flash_set('error', '角色值无效。');
            redirect_to('/admin.php#users');
        }

        $stmt = db()->prepare('SELECT id, nickname, username, role FROM pulsenest_users WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $targetUserId]);
        $targetUser = $stmt->fetch();

        if (!$targetUser) {
            flash_set('error', '没有找到目标用户。');
        } elseif ($targetUserId === (int) $user['id'] && $targetRole !== 'admin') {
            flash_set('error', '当前管理员自己的角色不能降级。');
        } else {
            $stmt = db()->prepare('UPDATE pulsenest_users SET role = :role, is_admin = :is_admin WHERE id = :id LIMIT 1');
            $stmt->execute([
                'role' => $targetRole,
                'is_admin' => $targetRole === 'admin' ? 1 : 0,
                'id' => $targetUserId,
            ]);
            log_moderation_action((int) $user['id'], 'user_role_updated', 'user', $targetUserId, ($targetUser['nickname'] ?: $targetUser['username']) . ' → ' . role_label($targetRole));
            flash_set('success', '用户角色已更新为“' . role_label($targetRole) . '”。');
        }
        redirect_to('/admin.php#users');
    }

    if ($action === 'update_home_copy') {
        $settings = [];
        foreach (array_keys(default_home_copy_settings()) as $settingKey) {
            $fieldName = site_setting_field_name($settingKey);
            $settings[$settingKey] = trim((string) ($_POST[$fieldName] ?? ''));
        }
        set_site_settings($settings);
        log_moderation_action((int) $user['id'], 'home_copy_updated', 'site_settings', null, '首页 Hero / Focus 文案已更新');
        flash_set('success', '首页运营卡文案已更新。');
        redirect_to('/admin.php#home-copy');
    }

    if ($action === 'update_post_ops') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $stmt = db()->prepare('SELECT p.id, p.title, p.home_slot, p.recommend_group, p.recommend_priority, u.nickname, u.username FROM posts p INNER JOIN pulsenest_users u ON u.id = p.user_id WHERE p.id = :id LIMIT 1');
        $stmt->execute(['id' => $postId]);
        $post = $stmt->fetch();

        if (!$post) {
            flash_set('error', '没有找到目标帖子。');
            redirect_to('/admin.php#posts');
        }

        $isSticky = isset($_POST['is_sticky']) ? 1 : 0;
        $isFeatured = isset($_POST['is_featured']) ? 1 : 0;
        $recommendLevel = max(0, min(9, (int) ($_POST['recommend_level'] ?? 0)));
        $homeSlot = trim((string) ($_POST['home_slot'] ?? ''));
        $recommendGroup = trim((string) ($_POST['recommend_group'] ?? 'general'));
        $recommendPriority = max(0, min(999, (int) ($_POST['recommend_priority'] ?? 0)));
        $allowedSlots = array_keys(home_slot_definitions());
        $allowedGroups = array_keys(recommend_group_definitions());
        if ($homeSlot !== '' && !in_array($homeSlot, $allowedSlots, true)) {
            $homeSlot = '';
        }
        if (!in_array($recommendGroup, $allowedGroups, true)) {
            $recommendGroup = 'general';
        }

        if ($homeSlot !== '') {
            db()->prepare('UPDATE posts SET home_slot = NULL WHERE home_slot = :home_slot AND id <> :id')->execute([
                'home_slot' => $homeSlot,
                'id' => $postId,
            ]);
        }

        db()->prepare('UPDATE posts SET is_sticky = :is_sticky, is_featured = :is_featured, recommend_level = :recommend_level, home_slot = :home_slot, recommend_group = :recommend_group, recommend_priority = :recommend_priority WHERE id = :id LIMIT 1')->execute([
            'is_sticky' => $isSticky,
            'is_featured' => $isFeatured,
            'recommend_level' => $recommendLevel,
            'home_slot' => $homeSlot !== '' ? $homeSlot : null,
            'recommend_group' => $recommendGroup,
            'recommend_priority' => $recommendPriority,
            'id' => $postId,
        ]);

        $slotLabel = $homeSlot !== '' ? (home_slot_definitions()[$homeSlot]['label'] ?? $homeSlot) : '未绑定';
        $groupLabel = recommend_group_definitions()[$recommendGroup]['label'] ?? $recommendGroup;
        log_moderation_action((int) $user['id'], 'post_ops_updated', 'post', $postId, '《' . $post['title'] . '》 · 置顶:' . $isSticky . ' · 精华:' . $isFeatured . ' · 推荐位:' . $recommendLevel . ' · 分组:' . $groupLabel . ' · 优先级:' . $recommendPriority . ' · 首页卡:' . $slotLabel);
        flash_set('success', '帖子运营位已更新。');
        redirect_to('/admin.php#posts');
    }

    if ($action === 'delete_post_admin') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $stmt = db()->prepare('SELECT p.id, p.title, p.image_path, u.nickname, u.username FROM posts p INNER JOIN pulsenest_users u ON u.id = p.user_id WHERE p.id = :id LIMIT 1');
        $stmt->execute(['id' => $postId]);
        $post = $stmt->fetch();
        if ($post) {
            $delete = db()->prepare('DELETE FROM posts WHERE id = :id LIMIT 1');
            $delete->execute(['id' => $postId]);
            delete_uploaded_asset($post['image_path'] ?? null);
            log_moderation_action((int) $user['id'], 'post_deleted', 'post', $postId, '《' . $post['title'] . '》 by ' . ($post['nickname'] ?: $post['username']));
            flash_set('success', '帖子已删除。');
        }
        redirect_to('/admin.php#posts');
    }

    if ($action === 'delete_comment_admin') {
        $commentId = (int) ($_POST['comment_id'] ?? 0);
        $stmt = db()->prepare('SELECT c.id, c.content, c.post_id, c.status, p.title, u.nickname, u.username FROM comments c INNER JOIN posts p ON p.id = c.post_id INNER JOIN pulsenest_users u ON u.id = c.user_id WHERE c.id = :id LIMIT 1');
        $stmt->execute(['id' => $commentId]);
        $comment = $stmt->fetch();
        if ($comment) {
            $delete = db()->prepare('DELETE FROM comments WHERE id = :id LIMIT 1');
            $delete->execute(['id' => $commentId]);
            log_moderation_action((int) $user['id'], 'comment_deleted', 'comment', $commentId, ($comment['nickname'] ?: $comment['username']) . ' · 《' . $comment['title'] . '》 · ' . excerpt($comment['content'], 80));
            flash_set('success', '评论已删除。');
        }
        redirect_to(admin_url([], '#comments'));
    }

    if ($action === 'bulk_comment_status') {
        $commentIds = array_values(array_unique(array_filter(array_map('intval', $_POST['comment_ids'] ?? []))));
        $targetStatus = trim((string) ($_POST['target_status'] ?? ''));
        $allowedStatuses = ['approved', 'hidden', 'pending'];
        if (!$commentIds) {
            flash_set('error', '请先勾选要处理的评论。');
            redirect_to(admin_url([], '#comments'));
        }
        if (!in_array($targetStatus, $allowedStatuses, true)) {
            flash_set('error', '目标状态无效。');
            redirect_to(admin_url([], '#comments'));
        }

        $placeholders = implode(',', array_fill(0, count($commentIds), '?'));
        $stmt = db()->prepare(
            'SELECT c.id, c.post_id, c.user_id, c.content, c.status, p.title, u.nickname, u.username
             FROM comments c
             INNER JOIN posts p ON p.id = c.post_id
             INNER JOIN pulsenest_users u ON u.id = c.user_id
             WHERE c.id IN (' . $placeholders . ')'
        );
        $stmt->execute($commentIds);
        $rows = $stmt->fetchAll();

        if (!$rows) {
            flash_set('error', '没有找到可处理的评论。');
            redirect_to(admin_url([], '#comments'));
        }

        $update = db()->prepare('UPDATE comments SET status = ? WHERE id IN (' . $placeholders . ')');
        $update->execute(array_merge([$targetStatus], $commentIds));
        foreach ($rows as $row) {
            log_moderation_action((int) $user['id'], 'comment_status_updated', 'comment', (int) $row['id'], ($row['nickname'] ?: $row['username']) . ' · ' . comment_status_label($row['status']) . ' → ' . comment_status_label($targetStatus) . ' · 《' . $row['title'] . '》');
            if (($row['status'] ?? '') !== $targetStatus) {
                create_comment_moderation_notification($row, ['id' => (int) $row['post_id']], (int) $user['id'], $targetStatus);
            }
        }
        flash_set('success', '已批量更新 ' . count($rows) . ' 条评论为“' . comment_status_label($targetStatus) . '”。');
        redirect_to(admin_url(['comment_status' => $targetStatus], '#comments'));
    }

    if ($action === 'move_category' && $canManageStructure) {
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $direction = trim((string) ($_POST['direction'] ?? ''));
        $stmt = db()->prepare('SELECT id, name, sort_order FROM forum_categories WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $categoryId]);
        $category = $stmt->fetch();
        if ($category && in_array($direction, ['up', 'down'], true)) {
            $operator = $direction === 'up' ? '<' : '>';
            $order = $direction === 'up' ? 'DESC' : 'ASC';
            $swapStmt = db()->prepare('SELECT id, name, sort_order FROM forum_categories WHERE sort_order ' . $operator . ' :sort_order ORDER BY sort_order ' . $order . ', id ' . $order . ' LIMIT 1');
            $swapStmt->execute(['sort_order' => (int) $category['sort_order']]);
            $swap = $swapStmt->fetch();
            if ($swap) {
                db()->prepare('UPDATE forum_categories SET sort_order = :sort_order WHERE id = :id')->execute(['sort_order' => (int) $swap['sort_order'], 'id' => $categoryId]);
                db()->prepare('UPDATE forum_categories SET sort_order = :sort_order WHERE id = :id')->execute(['sort_order' => (int) $category['sort_order'], 'id' => (int) $swap['id']]);
                log_moderation_action((int) $user['id'], 'category_reordered', 'category', $categoryId, $category['name'] . ' · ' . ($direction === 'up' ? '上移' : '下移'));
                flash_set('success', '分类顺序已调整。');
            }
        }
        redirect_to('/admin.php#categories');
    }

    if ($action === 'create_category' && $canManageStructure) {
        $name = trim((string) ($_POST['name'] ?? ''));
        $slug = trim((string) ($_POST['slug'] ?? ''));
        $description = trim((string) ($_POST['description'] ?? ''));
        $sortOrder = (int) ($_POST['sort_order'] ?? 0);
        if ($name === '' || $slug === '') {
            flash_set('error', '分类名称和 slug 不能为空。');
        } else {
            $stmt = db()->prepare('INSERT INTO forum_categories (name, slug, description, sort_order) VALUES (:name, :slug, :description, :sort_order)');
            $stmt->execute(['name' => $name, 'slug' => $slug, 'description' => $description ?: null, 'sort_order' => $sortOrder]);
            $id = (int) db()->lastInsertId();
            log_moderation_action((int) $user['id'], 'category_created', 'category', $id, $name . ' · ' . $slug);
            flash_set('success', '分类已新增。');
        }
        redirect_to('/admin.php#categories');
    }

    if ($action === 'update_category' && $canManageStructure) {
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $name = trim((string) ($_POST['name'] ?? ''));
        $slug = trim((string) ($_POST['slug'] ?? ''));
        $description = trim((string) ($_POST['description'] ?? ''));
        $sortOrder = (int) ($_POST['sort_order'] ?? 0);
        if ($name === '' || $slug === '') {
            flash_set('error', '分类名称和 slug 不能为空。');
        } else {
            $stmt = db()->prepare('UPDATE forum_categories SET name = :name, slug = :slug, description = :description, sort_order = :sort_order WHERE id = :id LIMIT 1');
            $stmt->execute(['name' => $name, 'slug' => $slug, 'description' => $description ?: null, 'sort_order' => $sortOrder, 'id' => $categoryId]);
            log_moderation_action((int) $user['id'], 'category_updated', 'category', $categoryId, $name . ' · ' . $slug);
            flash_set('success', '分类已更新。');
        }
        redirect_to('/admin.php#categories');
    }

    if ($action === 'delete_category' && $canManageStructure) {
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $targetCategoryId = (int) ($_POST['target_category_id'] ?? 0);
        $stmt = db()->prepare('SELECT id, name, slug FROM forum_categories WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $categoryId]);
        $category = $stmt->fetch();
        if (!$category) {
            flash_set('error', '没有找到要删除的分类。');
            redirect_to('/admin.php#categories');
        }
        $boardCountStmt = db()->prepare('SELECT COUNT(*) FROM forum_boards WHERE category_id = :id');
        $boardCountStmt->execute(['id' => $categoryId]);
        $boardCount = (int) $boardCountStmt->fetchColumn();
        if ($boardCount > 0 && $targetCategoryId <= 0) {
            flash_set('error', '该分类下还有 ' . $boardCount . ' 个版块，请先选择一个目标分类迁移版块。');
            redirect_to('/admin.php#categories');
        }
        if ($boardCount > 0 && $targetCategoryId === $categoryId) {
            flash_set('error', '迁移目标分类不能是当前分类本身。');
            redirect_to('/admin.php#categories');
        }
        $targetCategory = null;
        if ($targetCategoryId > 0) {
            $targetStmt = db()->prepare('SELECT id, name FROM forum_categories WHERE id = :id LIMIT 1');
            $targetStmt->execute(['id' => $targetCategoryId]);
            $targetCategory = $targetStmt->fetch();
            if (!$targetCategory) {
                flash_set('error', '迁移目标分类不存在。');
                redirect_to('/admin.php#categories');
            }
        }
        if ($boardCount > 0) {
            db()->prepare('UPDATE forum_boards SET category_id = :target_category_id WHERE category_id = :category_id')->execute(['target_category_id' => $targetCategoryId, 'category_id' => $categoryId]);
        }
        db()->prepare('DELETE FROM forum_categories WHERE id = :id LIMIT 1')->execute(['id' => $categoryId]);
        $details = $category['name'] . ' · ' . $category['slug'];
        if ($boardCount > 0 && $targetCategory) {
            $details .= ' · 迁移 ' . $boardCount . ' 个版块到 ' . $targetCategory['name'];
        }
        log_moderation_action((int) $user['id'], 'category_deleted', 'category', $categoryId, $details);
        flash_set('success', $boardCount > 0 ? '分类已删除，版块已迁移。' : '分类已删除。');
        redirect_to('/admin.php#categories');
    }

    if ($action === 'move_board' && $canManageStructure) {
        $boardId = (int) ($_POST['board_id'] ?? 0);
        $direction = trim((string) ($_POST['direction'] ?? ''));
        $stmt = db()->prepare('SELECT id, name, category_id, sort_order FROM forum_boards WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $boardId]);
        $board = $stmt->fetch();
        if ($board && in_array($direction, ['up', 'down'], true)) {
            $operator = $direction === 'up' ? '<' : '>';
            $order = $direction === 'up' ? 'DESC' : 'ASC';
            $swapStmt = db()->prepare('SELECT id, name, sort_order FROM forum_boards WHERE category_id = :category_id AND sort_order ' . $operator . ' :sort_order ORDER BY sort_order ' . $order . ', id ' . $order . ' LIMIT 1');
            $swapStmt->execute(['category_id' => (int) $board['category_id'], 'sort_order' => (int) $board['sort_order']]);
            $swap = $swapStmt->fetch();
            if ($swap) {
                db()->prepare('UPDATE forum_boards SET sort_order = :sort_order WHERE id = :id')->execute(['sort_order' => (int) $swap['sort_order'], 'id' => $boardId]);
                db()->prepare('UPDATE forum_boards SET sort_order = :sort_order WHERE id = :id')->execute(['sort_order' => (int) $board['sort_order'], 'id' => (int) $swap['id']]);
                log_moderation_action((int) $user['id'], 'board_reordered', 'board', $boardId, $board['name'] . ' · ' . ($direction === 'up' ? '上移' : '下移'));
                flash_set('success', '版块顺序已调整。');
            }
        }
        redirect_to('/admin.php#boards');
    }

    if ($action === 'create_board' && $canManageStructure) {
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $name = trim((string) ($_POST['name'] ?? ''));
        $slug = trim((string) ($_POST['slug'] ?? ''));
        $description = trim((string) ($_POST['description'] ?? ''));
        $accentColor = trim((string) ($_POST['accent_color'] ?? ''));
        $sortOrder = (int) ($_POST['sort_order'] ?? 0);
        if ($categoryId <= 0 || $name === '' || $slug === '') {
            flash_set('error', '版块所属分类、名称和 slug 不能为空。');
        } else {
            $stmt = db()->prepare('INSERT INTO forum_boards (category_id, name, slug, description, accent_color, sort_order) VALUES (:category_id, :name, :slug, :description, :accent_color, :sort_order)');
            $stmt->execute([
                'category_id' => $categoryId,
                'name' => $name,
                'slug' => $slug,
                'description' => $description ?: null,
                'accent_color' => $accentColor ?: null,
                'sort_order' => $sortOrder,
            ]);
            $id = (int) db()->lastInsertId();
            log_moderation_action((int) $user['id'], 'board_created', 'board', $id, $name . ' · ' . $slug);
            flash_set('success', '版块已新增。');
        }
        redirect_to('/admin.php#boards');
    }

    if ($action === 'update_board' && $canManageStructure) {
        $boardId = (int) ($_POST['board_id'] ?? 0);
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $name = trim((string) ($_POST['name'] ?? ''));
        $slug = trim((string) ($_POST['slug'] ?? ''));
        $description = trim((string) ($_POST['description'] ?? ''));
        $accentColor = trim((string) ($_POST['accent_color'] ?? ''));
        $sortOrder = (int) ($_POST['sort_order'] ?? 0);
        if ($boardId <= 0 || $categoryId <= 0 || $name === '' || $slug === '') {
            flash_set('error', '版块信息不完整。');
        } else {
            $stmt = db()->prepare('UPDATE forum_boards SET category_id = :category_id, name = :name, slug = :slug, description = :description, accent_color = :accent_color, sort_order = :sort_order WHERE id = :id LIMIT 1');
            $stmt->execute([
                'category_id' => $categoryId,
                'name' => $name,
                'slug' => $slug,
                'description' => $description ?: null,
                'accent_color' => $accentColor ?: null,
                'sort_order' => $sortOrder,
                'id' => $boardId,
            ]);
            log_moderation_action((int) $user['id'], 'board_updated', 'board', $boardId, $name . ' · ' . $slug);
            flash_set('success', '版块已更新。');
        }
        redirect_to('/admin.php#boards');
    }

    if ($action === 'delete_board' && $canManageStructure) {
        $boardId = (int) ($_POST['board_id'] ?? 0);
        $targetBoardId = (int) ($_POST['target_board_id'] ?? 0);
        $stmt = db()->prepare('SELECT id, name, slug FROM forum_boards WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $boardId]);
        $board = $stmt->fetch();
        if (!$board) {
            flash_set('error', '没有找到要删除的版块。');
            redirect_to('/admin.php#boards');
        }
        $countStmt = db()->prepare('SELECT COUNT(*) FROM posts WHERE board_id = :id');
        $countStmt->execute(['id' => $boardId]);
        $postCount = (int) $countStmt->fetchColumn();
        if ($postCount > 0 && $targetBoardId <= 0) {
            flash_set('error', '该版块下还有 ' . $postCount . ' 篇帖子，请先选择迁移目标版块。');
            redirect_to('/admin.php#boards');
        }
        if ($postCount > 0 && $targetBoardId === $boardId) {
            flash_set('error', '迁移目标版块不能是当前版块本身。');
            redirect_to('/admin.php#boards');
        }
        $targetBoard = null;
        if ($targetBoardId > 0) {
            $targetStmt = db()->prepare('SELECT id, name FROM forum_boards WHERE id = :id LIMIT 1');
            $targetStmt->execute(['id' => $targetBoardId]);
            $targetBoard = $targetStmt->fetch();
            if (!$targetBoard) {
                flash_set('error', '迁移目标版块不存在。');
                redirect_to('/admin.php#boards');
            }
        }
        if ($postCount > 0) {
            db()->prepare('UPDATE posts SET board_id = :target_board_id WHERE board_id = :board_id')->execute(['target_board_id' => $targetBoardId, 'board_id' => $boardId]);
        }
        db()->prepare('DELETE FROM forum_boards WHERE id = :id LIMIT 1')->execute(['id' => $boardId]);
        $details = $board['name'] . ' · ' . $board['slug'];
        if ($postCount > 0 && $targetBoard) {
            $details .= ' · 迁移 ' . $postCount . ' 篇帖子到 ' . $targetBoard['name'];
        }
        log_moderation_action((int) $user['id'], 'board_deleted', 'board', $boardId, $details);
        flash_set('success', $postCount > 0 ? '版块已删除，帖子已迁移。' : '版块已删除。');
        redirect_to('/admin.php#boards');
    }
}

$postFilterId = (int) ($_GET['post_id'] ?? 0);
$authorFilterId = (int) ($_GET['author_id'] ?? 0);
$postTitleKeyword = trim((string) ($_GET['post_title_keyword'] ?? ''));
$authorKeyword = trim((string) ($_GET['author_keyword'] ?? ''));
$contentKeyword = trim((string) ($_GET['content_keyword'] ?? ''));
$commentStatusFilter = trim((string) ($_GET['comment_status'] ?? ''));
$postRecommendGroupFilter = trim((string) ($_GET['post_recommend_group'] ?? ''));
$postRecommendPriorityFilterRaw = trim((string) ($_GET['post_recommend_priority'] ?? ''));
$postStickyFilter = trim((string) ($_GET['post_is_sticky'] ?? ''));
$postFeaturedFilter = trim((string) ($_GET['post_is_featured'] ?? ''));
$postHomeSlotFilter = trim((string) ($_GET['post_home_slot'] ?? ''));
$postPage = max(1, (int) ($_GET['post_page'] ?? 1));
$commentPage = max(1, (int) ($_GET['comment_page'] ?? 1));
$postPageSize = 12;
$commentPageSize = 40;

$commentWhere = [];
$commentParams = [];
if ($postFilterId > 0) {
    $commentWhere[] = 'c.post_id = :post_id';
    $commentParams['post_id'] = $postFilterId;
}
if ($authorFilterId > 0) {
    $commentWhere[] = 'c.user_id = :author_id';
    $commentParams['author_id'] = $authorFilterId;
}
if ($postTitleKeyword !== '') {
    $commentWhere[] = 'p.title LIKE :post_title_keyword';
    $commentParams['post_title_keyword'] = '%' . $postTitleKeyword . '%';
}
if ($authorKeyword !== '') {
    $commentWhere[] = '(u.username LIKE :author_keyword OR u.nickname LIKE :author_keyword)';
    $commentParams['author_keyword'] = '%' . $authorKeyword . '%';
}
if ($contentKeyword !== '') {
    $commentWhere[] = 'c.content LIKE :content_keyword';
    $commentParams['content_keyword'] = '%' . $contentKeyword . '%';
}
if ($commentStatusFilter !== '' && in_array($commentStatusFilter, ['approved', 'hidden', 'pending'], true)) {
    $commentWhere[] = 'c.status = :comment_status';
    $commentParams['comment_status'] = $commentStatusFilter;
}
$commentWhereSql = $commentWhere ? ' WHERE ' . implode(' AND ', $commentWhere) : '';
$commentCountStmt = db()->prepare(
    'SELECT COUNT(*)
     FROM comments c
     INNER JOIN posts p ON p.id = c.post_id
     INNER JOIN pulsenest_users u ON u.id = c.user_id
     INNER JOIN pulsenest_users owner ON owner.id = p.user_id'
    . $commentWhereSql
);
$commentCountStmt->execute($commentParams);
$commentTotal = (int) $commentCountStmt->fetchColumn();
$commentTotalPages = max(1, (int) ceil($commentTotal / $commentPageSize));
$commentPage = min($commentPage, $commentTotalPages);
$commentOffset = ($commentPage - 1) * $commentPageSize;
$commentSql =
    'SELECT c.id, c.post_id, c.user_id, c.content, c.status, c.created_at,
            p.title AS post_title,
            u.nickname, u.username,
            owner.nickname AS post_owner_nickname, owner.username AS post_owner_username
     FROM comments c
     INNER JOIN posts p ON p.id = c.post_id
     INNER JOIN pulsenest_users u ON u.id = c.user_id
     INNER JOIN pulsenest_users owner ON owner.id = p.user_id'
    . $commentWhereSql
    . ' ORDER BY c.created_at DESC, c.id DESC LIMIT :limit OFFSET :offset';
$commentStmt = db()->prepare($commentSql);
foreach ($commentParams as $key => $value) {
    $commentStmt->bindValue(':' . $key, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
}
$commentStmt->bindValue(':limit', $commentPageSize, PDO::PARAM_INT);
$commentStmt->bindValue(':offset', $commentOffset, PDO::PARAM_INT);
$commentStmt->execute();
$commentRows = $commentStmt->fetchAll();
$commentCount = count($commentRows);
$commentStatusStats = db()->query('SELECT status, COUNT(*) AS total_count FROM comments GROUP BY status ORDER BY total_count DESC, status ASC')->fetchAll();

$userRows = db()->query(
    'SELECT u.id, u.username, u.nickname, u.email, u.role, u.is_admin, u.is_active, u.created_at,
            COALESCE(p.post_count, 0) AS post_count,
            COALESCE(c.comment_count, 0) AS comment_count
     FROM pulsenest_users u
     LEFT JOIN (
        SELECT user_id, COUNT(*) AS post_count FROM posts GROUP BY user_id
     ) p ON p.user_id = u.id
     LEFT JOIN (
        SELECT user_id, COUNT(*) AS comment_count FROM comments GROUP BY user_id
     ) c ON c.user_id = u.id
     ORDER BY FIELD(u.role, "admin", "moderator", "member"), u.created_at DESC, u.id DESC'
)->fetchAll();

$recommendGroups = recommend_group_definitions();
$homeSlotDefinitions = home_slot_definitions();
$postWhere = [];
$postParams = [];
if ($postRecommendGroupFilter !== '' && isset($recommendGroups[$postRecommendGroupFilter])) {
    $postWhere[] = 'p.recommend_group = :post_recommend_group';
    $postParams['post_recommend_group'] = $postRecommendGroupFilter;
}
if ($postRecommendPriorityFilterRaw !== '' && is_numeric($postRecommendPriorityFilterRaw)) {
    $postWhere[] = 'p.recommend_priority = :post_recommend_priority';
    $postParams['post_recommend_priority'] = (int) $postRecommendPriorityFilterRaw;
}
if (in_array($postStickyFilter, ['1', '0'], true)) {
    $postWhere[] = 'p.is_sticky = :post_is_sticky';
    $postParams['post_is_sticky'] = (int) $postStickyFilter;
}
if (in_array($postFeaturedFilter, ['1', '0'], true)) {
    $postWhere[] = 'p.is_featured = :post_is_featured';
    $postParams['post_is_featured'] = (int) $postFeaturedFilter;
}
if ($postHomeSlotFilter === '__bound__') {
    $postWhere[] = 'p.home_slot IS NOT NULL AND p.home_slot <> ""';
} elseif ($postHomeSlotFilter === '__unbound__') {
    $postWhere[] = '(p.home_slot IS NULL OR p.home_slot = "")';
} elseif ($postHomeSlotFilter !== '' && isset($homeSlotDefinitions[$postHomeSlotFilter])) {
    $postWhere[] = 'p.home_slot = :post_home_slot';
    $postParams['post_home_slot'] = $postHomeSlotFilter;
}
$postWhereSql = $postWhere ? ' WHERE ' . implode(' AND ', $postWhere) : '';
$postCountStmt = db()->prepare('SELECT COUNT(*) FROM posts p' . $postWhereSql);
foreach ($postParams as $key => $value) {
    $postCountStmt->bindValue(':' . $key, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
}
$postCountStmt->execute();
$postCountTotal = (int) $postCountStmt->fetchColumn();
$postTotalPages = max(1, (int) ceil($postCountTotal / $postPageSize));
$postPage = min($postPage, $postTotalPages);
$postOffset = ($postPage - 1) * $postPageSize;
$postStmt = db()->prepare(
    'SELECT p.id, p.title, p.created_at, p.is_sticky, p.is_featured, p.recommend_level, p.home_slot, p.recommend_group, p.recommend_priority,
            u.nickname, u.username,
            fb.name AS board_name,
            fc.name AS category_name,
            COALESCE(c.comment_count, 0) AS comment_count,
            COALESCE(l.like_count, 0) AS like_count
     FROM posts p
     INNER JOIN pulsenest_users u ON u.id = p.user_id
     LEFT JOIN forum_boards fb ON fb.id = p.board_id
     LEFT JOIN forum_categories fc ON fc.id = fb.category_id
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
     ) c ON c.post_id = p.id
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
     ) l ON l.post_id = p.id'
     . $postWhereSql .
    ' ORDER BY p.is_sticky DESC, p.recommend_priority DESC, p.recommend_level DESC, p.is_featured DESC, p.created_at DESC, p.id DESC
     LIMIT :limit OFFSET :offset'
);
foreach ($postParams as $key => $value) {
    $postStmt->bindValue(':' . $key, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
}
$postStmt->bindValue(':limit', $postPageSize, PDO::PARAM_INT);
$postStmt->bindValue(':offset', $postOffset, PDO::PARAM_INT);
$postStmt->execute();
$postRows = $postStmt->fetchAll();

$categoryRows = db()->query(
    'SELECT c.id, c.name, c.slug, c.description, c.sort_order,
            COUNT(b.id) AS board_count
     FROM forum_categories c
     LEFT JOIN forum_boards b ON b.category_id = c.id
     GROUP BY c.id
     ORDER BY c.sort_order ASC, c.id ASC'
)->fetchAll();

$boardRows = db()->query(
    'SELECT b.id, b.category_id, b.name, b.slug, b.description, b.sort_order, b.accent_color,
            c.name AS category_name,
            COALESCE(p.post_count, 0) AS post_count
     FROM forum_boards b
     INNER JOIN forum_categories c ON c.id = b.category_id
     LEFT JOIN (
        SELECT board_id, COUNT(*) AS post_count FROM posts GROUP BY board_id
     ) p ON p.board_id = b.id
     ORDER BY c.sort_order ASC, c.id ASC, b.sort_order ASC, b.id ASC'
)->fetchAll();

$homeCopy = home_copy_config();
$boundSlotRows = db()->query('SELECT id, title, home_slot FROM posts WHERE home_slot IS NOT NULL AND home_slot <> ""')->fetchAll();
$boundSlots = [];
foreach ($boundSlotRows as $row) {
    $boundSlots[$row['home_slot']] = $row;
}

$notificationTotals = db()->query('SELECT COUNT(*) AS total_notifications, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread_notifications FROM notifications')->fetch();
$notificationTypeRows = db()->query('SELECT type, COUNT(*) AS total_count, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread_count FROM notifications GROUP BY type ORDER BY total_count DESC, type ASC')->fetchAll();
$notificationTodayCount = (int) db()->query('SELECT COUNT(*) FROM notifications WHERE created_at >= NOW() - INTERVAL 1 DAY')->fetchColumn();
$notificationSevenDayCount = (int) db()->query('SELECT COUNT(*) FROM notifications WHERE created_at >= NOW() - INTERVAL 7 DAY')->fetchColumn();

$logActionFilter = trim((string) ($_GET['log_action'] ?? ''));
$logTargetTypeFilter = trim((string) ($_GET['log_target_type'] ?? ''));
$logActorIdFilter = (int) ($_GET['log_actor_id'] ?? 0);
$logPage = max(1, (int) ($_GET['log_page'] ?? 1));
$logPageSize = 20;
$logWhere = [];
$logParams = [];
if ($logActionFilter !== '') {
    $logWhere[] = 'l.action_type = :log_action';
    $logParams['log_action'] = $logActionFilter;
}
if ($logTargetTypeFilter !== '') {
    $logWhere[] = 'l.target_type = :log_target_type';
    $logParams['log_target_type'] = $logTargetTypeFilter;
}
if ($logActorIdFilter > 0) {
    $logWhere[] = 'l.actor_user_id = :log_actor_id';
    $logParams['log_actor_id'] = $logActorIdFilter;
}
$logWhereSql = $logWhere ? ' WHERE ' . implode(' AND ', $logWhere) : '';
$countStmt = db()->prepare('SELECT COUNT(*) FROM moderation_logs l' . $logWhereSql);
$countStmt->execute($logParams);
$logTotal = (int) $countStmt->fetchColumn();
$logTotalPages = max(1, (int) ceil($logTotal / $logPageSize));
$logPage = min($logPage, $logTotalPages);
$logOffset = ($logPage - 1) * $logPageSize;
$logStmt = db()->prepare(
    'SELECT l.id, l.action_type, l.target_type, l.target_id, l.details, l.created_at,
            u.nickname, u.username, u.id AS actor_id
     FROM moderation_logs l
     INNER JOIN pulsenest_users u ON u.id = l.actor_user_id'
    . $logWhereSql .
    ' ORDER BY l.created_at DESC, l.id DESC LIMIT :limit OFFSET :offset'
);
foreach ($logParams as $key => $value) {
    $logStmt->bindValue(':' . $key, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
}
$logStmt->bindValue(':limit', $logPageSize, PDO::PARAM_INT);
$logStmt->bindValue(':offset', $logOffset, PDO::PARAM_INT);
$logStmt->execute();
$logRows = $logStmt->fetchAll();

$logActionOptions = db()->query('SELECT DISTINCT action_type FROM moderation_logs ORDER BY action_type ASC')->fetchAll(PDO::FETCH_COLUMN);
$logTargetTypeOptions = db()->query('SELECT DISTINCT target_type FROM moderation_logs ORDER BY target_type ASC')->fetchAll(PDO::FETCH_COLUMN);
$logActorOptions = db()->query(
    'SELECT DISTINCT u.id, u.nickname, u.username
     FROM moderation_logs l
     INNER JOIN pulsenest_users u ON u.id = l.actor_user_id
     ORDER BY u.nickname ASC, u.username ASC'
)->fetchAll();

$availableCategoryTargets = $categoryRows;
$availableBoardTargets = $boardRows;
$staffCount = 0;
foreach ($userRows as $row) {
    if (can_access_admin($row)) {
        $staffCount++;
    }
}

render_header('PulseNest · 后台管理', $user, [
    'searchText' => '🔎 后台：运营位、评论状态、角色边界、结构迁移、操作日志',
]);
?>
<main class="shell page-shell nebula-page-shell admin-page">
  <?php if ($flash): ?>
    <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
  <?php endif; ?>

  <section class="glass nebula-hero nebula-hero-split create-post-hero">
    <div class="nebula-copy">
      <div class="brand-chip">纳达尔星项目 · 星云初始01 · 后台增强版</div>
      <h1>运营位、评论审核流和通知概况，现在都能在后台闭环。</h1>
      <p class="page-desc nebula-desc">这一版把后台继续往真运营场景补：帖子可做置顶 / 精华 / 推荐位 / 首页卡绑定；评论不再只有删除，补成可审核、隐藏、恢复；提醒系统也保留多类型概况，前台再配合做未读和类型筛选。</p>
      <div class="hero-stats compact-hero-stats admin-hero-stats">
        <div class="hero-stat"><div class="label">当前身份</div><div class="num small-num"><?= e(role_label($role)) ?></div><div class="note"><?= $role === 'admin' ? '全量后台权限已解锁' : '当前仅开放内容管理范围' ?></div></div>
        <div class="hero-stat"><div class="label">后台人员</div><div class="num small-num"><?= $staffCount ?></div><div class="note">管理员 + 版主共同维护</div></div>
        <div class="hero-stat"><div class="label">操作日志</div><div class="num small-num"><?= $logTotal ?></div><div class="note">运营动作 / 状态变更都会留痕</div></div>
      </div>
    </div>
    <aside class="glass side-card nebula-side-panel">
      <div class="section-kicker">Admin Scope</div>
      <div class="quick-links">
        <a class="quick-link" href="#permission-map"><strong>权限边界</strong><span>先看自己能动什么</span></a>
        <a class="quick-link" href="#posts"><strong>帖子运营</strong><span>置顶 / 精华 / 推荐位 / 首页卡</span></a>
        <a class="quick-link" href="#comments"><strong>评论管理</strong><span>批量审核 / 隐藏 / 恢复</span></a>
        <?php if ($canManageUsers): ?><a class="quick-link" href="#users"><strong>角色 / 用户</strong><span>仅管理员可见</span></a><?php endif; ?>
        <?php if ($canManageStructure): ?><a class="quick-link" href="#categories"><strong>分类 / 版块</strong><span>仅管理员可见</span></a><?php endif; ?>
        <a class="quick-link" href="#notifications-overview"><strong>通知概况</strong><span>类型分布 / 未读 / 7 日统计</span></a>
        <a class="quick-link" href="#logs"><strong>操作日志</strong><span>支持筛选与分页</span></a>
      </div>
    </aside>
  </section>

  <section id="permission-map" class="glass panel-card admin-panel-card">
    <div class="section-kicker">Permission Map</div>
    <div class="side-head admin-head-row">
      <h3>角色权限边界</h3>
      <span class="muted">普通用户不显示后台入口；版主只处理内容巡检与日志；管理员才可改用户和论坛结构。</span>
    </div>
    <div class="permission-grid">
      <article class="permission-card <?= $role === 'admin' ? 'is-current' : '' ?>">
        <div class="permission-card-head"><strong>管理员</strong><span class="tiny-badge badge-ok">全量</span></div>
        <p class="muted">负责用户权限、论坛结构、内容巡检、运营位和日志留痕。</p>
        <ul class="permission-list">
          <li>可调用户角色 / 启停账号</li>
          <li>可改帖子运营位、首页卡绑定</li>
          <li>可批量审核 / 隐藏评论</li>
          <li>可调整分类 / 版块及回看日志</li>
        </ul>
      </article>
      <article class="permission-card <?= $role === 'moderator' ? 'is-current' : '' ?>">
        <div class="permission-card-head"><strong>版主</strong><span class="tiny-badge">内容管理</span></div>
        <p class="muted">专注内容巡检与评论流，不碰用户权限和社区结构。</p>
        <ul class="permission-list">
          <li>可改帖子运营标记</li>
          <li>可批量审核 / 隐藏 / 恢复评论</li>
          <li>可删帖、删评、看日志</li>
          <li>不可调整用户角色与论坛结构</li>
        </ul>
      </article>
      <article class="permission-card">
        <div class="permission-card-head"><strong>普通用户</strong><span class="tiny-badge">前台</span></div>
        <p class="muted">只保留发帖、评论、提醒、资料维护等前台能力。</p>
        <ul class="permission-list">
          <li>可发帖、评论、看提醒</li>
          <li>可维护头像与简介</li>
          <li>不可进入后台管理页面</li>
          <li>不可操作日志、角色和结构</li>
        </ul>
      </article>
    </div>
  </section>

  <section id="posts" class="glass panel-card admin-panel-card">
    <div class="section-kicker">Posts</div>
    <div class="side-head admin-head-row"><h3>帖子运营工具</h3><span class="muted">支持置顶、精华、推荐分组、显示优先级、推荐位等级、首页运营卡绑定。首页卡会自动保持唯一绑定。</span></div>
    <form class="admin-filter-row" method="get" action="/admin.php#posts">
      <input type="hidden" name="post_id" value="<?= $postFilterId > 0 ? (int) $postFilterId : '' ?>">
      <input type="hidden" name="author_id" value="<?= $authorFilterId > 0 ? (int) $authorFilterId : '' ?>">
      <input type="hidden" name="post_title_keyword" value="<?= e($postTitleKeyword) ?>">
      <input type="hidden" name="author_keyword" value="<?= e($authorKeyword) ?>">
      <input type="hidden" name="content_keyword" value="<?= e($contentKeyword) ?>">
      <input type="hidden" name="comment_status" value="<?= e($commentStatusFilter) ?>">
      <input type="hidden" name="comment_page" value="<?= $commentPage ?>">
      <input type="hidden" name="log_action" value="<?= e($logActionFilter) ?>">
      <input type="hidden" name="log_target_type" value="<?= e($logTargetTypeFilter) ?>">
      <input type="hidden" name="log_actor_id" value="<?= $logActorIdFilter ?>">
      <input type="hidden" name="log_page" value="<?= $logPage ?>">
      <select class="input admin-filter-input" name="post_recommend_group">
        <option value="">全部推荐分组</option>
        <?php foreach ($recommendGroups as $groupKey => $groupMeta): ?>
          <option value="<?= e($groupKey) ?>" <?= $postRecommendGroupFilter === $groupKey ? 'selected' : '' ?>><?= e($groupMeta['label']) ?></option>
        <?php endforeach; ?>
      </select>
      <input class="input admin-filter-input" type="number" min="0" max="999" name="post_recommend_priority" placeholder="推荐优先级（精确值）" value="<?= e($postRecommendPriorityFilterRaw) ?>">
      <select class="input admin-filter-input" name="post_is_sticky">
        <option value="">是否置顶：全部</option>
        <option value="1" <?= $postStickyFilter === '1' ? 'selected' : '' ?>>仅看置顶</option>
        <option value="0" <?= $postStickyFilter === '0' ? 'selected' : '' ?>>仅看未置顶</option>
      </select>
      <select class="input admin-filter-input" name="post_is_featured">
        <option value="">是否精华：全部</option>
        <option value="1" <?= $postFeaturedFilter === '1' ? 'selected' : '' ?>>仅看精华</option>
        <option value="0" <?= $postFeaturedFilter === '0' ? 'selected' : '' ?>>仅看非精华</option>
      </select>
      <select class="input admin-filter-input" name="post_home_slot">
        <option value="">首页位：全部</option>
        <option value="__bound__" <?= $postHomeSlotFilter === '__bound__' ? 'selected' : '' ?>>仅看已绑定首页位</option>
        <option value="__unbound__" <?= $postHomeSlotFilter === '__unbound__' ? 'selected' : '' ?>>仅看未绑定首页位</option>
        <?php foreach ($homeSlotDefinitions as $slotKey => $slotMeta): ?>
          <option value="<?= e($slotKey) ?>" <?= $postHomeSlotFilter === $slotKey ? 'selected' : '' ?>><?= e($slotMeta['label']) ?></option>
        <?php endforeach; ?>
      </select>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="<?= e(admin_url(['post_recommend_group' => null, 'post_recommend_priority' => null, 'post_is_sticky' => null, 'post_is_featured' => null, 'post_home_slot' => null, 'post_page' => null], '#posts')) ?>">清空</a>
    </form>
    <div class="admin-log-meta muted">当前筛选命中 <?= count($postRows) ?> 篇帖子 · 共 <?= $postCountTotal ?> 篇 · 第 <?= $postPage ?> / <?= $postTotalPages ?> 页</div>
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th>ID</th><th>标题</th><th>作者</th><th>版块</th><th>热度</th><th>运营位</th><th>操作</th></tr></thead>
        <tbody>
          <?php foreach ($postRows as $row): ?>
            <tr>
              <td>#<?= (int) $row['id'] ?></td>
              <td>
                <a class="inline-link" href="/post.php?id=<?= (int) $row['id'] ?>"><?= e($row['title']) ?></a>
                <div class="chips" style="margin-top:8px; gap:6px;">
                  <?php if ((int) $row['is_sticky'] === 1): ?><span class="chip">置顶</span><?php endif; ?>
                  <?php if ((int) $row['is_featured'] === 1): ?><span class="chip">精华</span><?php endif; ?>
                  <?php if ((int) $row['recommend_level'] > 0): ?><span class="chip">推荐位 <?= (int) $row['recommend_level'] ?></span><?php endif; ?>
                  <span class="chip"><?= e($recommendGroups[$row['recommend_group']]['label'] ?? ($row['recommend_group'] ?? '综合推荐')) ?></span>
                  <span class="chip">优先级 <?= (int) ($row['recommend_priority'] ?? 0) ?></span>
                  <?php if (!empty($row['home_slot'])): ?><span class="chip">首页卡 · <?= e($homeSlotDefinitions[$row['home_slot']]['label'] ?? $row['home_slot']) ?></span><?php endif; ?>
                </div>
              </td>
              <td><?= e($row['nickname']) ?><div class="muted">@<?= e($row['username']) ?></div></td>
              <td><?= e(trim(($row['category_name'] ?? '公共区') . ' / ' . ($row['board_name'] ?? '未分区'))) ?></td>
              <td><?= (int) $row['like_count'] ?> 赞 · <?= (int) $row['comment_count'] ?> 评</td>
              <td>
                <form method="post" class="admin-inline-stack" style="align-items:flex-start;">
                  <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                  <input type="hidden" name="action" value="update_post_ops">
                  <input type="hidden" name="post_id" value="<?= (int) $row['id'] ?>">
                  <label class="muted"><input type="checkbox" name="is_sticky" value="1" <?= (int) $row['is_sticky'] === 1 ? 'checked' : '' ?>> 置顶</label>
                  <label class="muted"><input type="checkbox" name="is_featured" value="1" <?= (int) $row['is_featured'] === 1 ? 'checked' : '' ?>> 精华</label>
                  <select class="input slim-input" name="recommend_group">
                    <?php foreach ($recommendGroups as $groupKey => $groupMeta): ?>
                      <option value="<?= e($groupKey) ?>" <?= ($row['recommend_group'] ?? 'general') === $groupKey ? 'selected' : '' ?>><?= e($groupMeta['label']) ?></option>
                    <?php endforeach; ?>
                  </select>
                  <input class="input slim-input" type="number" min="0" max="999" name="recommend_priority" value="<?= (int) ($row['recommend_priority'] ?? 0) ?>" placeholder="优先级">
                  <select class="input slim-input" name="recommend_level">
                    <?php for ($level = 0; $level <= 5; $level++): ?>
                      <option value="<?= $level ?>" <?= (int) $row['recommend_level'] === $level ? 'selected' : '' ?>>推荐位 <?= $level ?></option>
                    <?php endfor; ?>
                  </select>
                  <select class="input slim-input" name="home_slot">
                    <option value="">不绑定首页卡</option>
                    <?php foreach ($homeSlotDefinitions as $slotKey => $slotMeta): ?>
                      <option value="<?= e($slotKey) ?>" <?= ($row['home_slot'] ?? '') === $slotKey ? 'selected' : '' ?>><?= e($slotMeta['label']) ?></option>
                    <?php endforeach; ?>
                  </select>
                  <button class="pill-btn solid" type="submit">保存运营位</button>
                </form>
              </td>
              <td>
                <div class="admin-action-stack">
                  <a class="pill-btn" href="/edit-post.php?id=<?= (int) $row['id'] ?>">编辑</a>
                  <a class="pill-btn" href="<?= e(admin_url(['post_id' => (int) $row['id']], '#comments')) ?>">看评论</a>
                  <form method="post" class="inline-form" onsubmit="return confirm('确认删除这篇帖子？帖子下评论也会一起删除，并写入日志。');">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="delete_post_admin">
                    <input type="hidden" name="post_id" value="<?= (int) $row['id'] ?>">
                    <button class="pill-btn danger" type="submit">删除</button>
                  </form>
                </div>
              </td>
            </tr>
          <?php endforeach; ?>
        </tbody>
      </table>
    </div>

    <?= admin_pagination([
      'post_id' => $postFilterId,
      'author_id' => $authorFilterId,
      'post_title_keyword' => $postTitleKeyword,
      'author_keyword' => $authorKeyword,
      'content_keyword' => $contentKeyword,
      'comment_status' => $commentStatusFilter,
      'post_recommend_group' => $postRecommendGroupFilter,
      'post_recommend_priority' => $postRecommendPriorityFilterRaw,
      'post_is_sticky' => $postStickyFilter,
      'post_is_featured' => $postFeaturedFilter,
      'post_home_slot' => $postHomeSlotFilter,
      'comment_page' => $commentPage,
      'log_action' => $logActionFilter,
      'log_target_type' => $logTargetTypeFilter,
      'log_actor_id' => $logActorIdFilter,
      'log_page' => $logPage,
    ], 'post_page', $postPage, $postTotalPages, '#posts') ?>

    <div class="permission-grid" style="margin-top:20px;">
      <?php foreach ($homeSlotDefinitions as $slotKey => $slotMeta): ?>
        <article class="permission-card">
          <div class="permission-card-head"><strong><?= e($slotMeta['label']) ?></strong><span class="tiny-badge">首页卡</span></div>
          <p class="muted"><?= e($slotMeta['desc']) ?></p>
          <?php if (isset($boundSlots[$slotKey])): ?>
            <div><a class="inline-link" href="/post.php?id=<?= (int) $boundSlots[$slotKey]['id'] ?>"><?= e($boundSlots[$slotKey]['title']) ?></a></div>
          <?php else: ?>
            <div class="muted">当前未绑定帖子</div>
          <?php endif; ?>
        </article>
      <?php endforeach; ?>
    </div>
  </section>

  <section id="home-copy" class="glass panel-card admin-panel-card">
    <div class="section-kicker">Home Copy</div>
    <div class="side-head admin-head-row"><h3>首页运营卡文案</h3><span class="muted">Hero / Focus 三张卡的标题、副文案、标签都可直接编辑，前台首页会实时读取配置。</span></div>
    <form class="admin-list-card" method="post">
      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
      <input type="hidden" name="action" value="update_home_copy">
      <div class="permission-grid">
        <div>
          <div class="admin-list-card-head"><strong>Hero 主视觉</strong><span class="tiny-badge">首页顶部</span></div>
          <div class="notice subtle-notice" style="margin-bottom: 12px;">混合模式：Hero 绑定帖子后，可继续单独决定主标题 / 副文案是否覆盖帖子的标题 / 摘要。</div>
          <input class="input" name="<?= e(site_setting_field_name('home.hero.eyebrow')) ?>" value="<?= e($homeCopy['home.hero.eyebrow']) ?>" placeholder="眉标">
          <input class="input" name="<?= e(site_setting_field_name('home.hero.title')) ?>" value="<?= e($homeCopy['home.hero.title']) ?>" placeholder="主标题">
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('home.hero.use_custom_title')) ?>" value="1" <?= hero_uses_custom_title($homeCopy) ? 'checked' : '' ?>> 绑定帖子后仍使用上面这条自定义主标题</label>
          <textarea class="input" name="<?= e(site_setting_field_name('home.hero.body')) ?>" rows="4" placeholder="Hero 副文案"><?= e($homeCopy['home.hero.body']) ?></textarea>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('home.hero.use_custom_body')) ?>" value="1" <?= hero_uses_custom_body($homeCopy) ? 'checked' : '' ?>> 绑定帖子后仍使用上面这条自定义副文案</label>
          <div class="admin-inline-stack">
            <input class="input" name="<?= e(site_setting_field_name('home.hero.tag_primary')) ?>" value="<?= e($homeCopy['home.hero.tag_primary']) ?>" placeholder="标签 1">
            <input class="input" name="<?= e(site_setting_field_name('home.hero.tag_secondary')) ?>" value="<?= e($homeCopy['home.hero.tag_secondary']) ?>" placeholder="标签 2">
          </div>
        </div>
        <?php foreach (['focus_one' => '焦点卡 1', 'focus_two' => '焦点卡 2', 'focus_three' => '焦点卡 3'] as $slotKey => $slotLabel): ?>
          <div>
            <div class="admin-list-card-head"><strong><?= e($slotLabel) ?></strong><span class="tiny-badge"><?= e($slotKey) ?></span></div>
            <input class="input" name="<?= e(site_setting_field_name('home.' . $slotKey . '.badge')) ?>" value="<?= e($homeCopy['home.' . $slotKey . '.badge']) ?>" placeholder="顶部标签">
            <input class="input" name="<?= e(site_setting_field_name('home.' . $slotKey . '.title')) ?>" value="<?= e($homeCopy['home.' . $slotKey . '.title']) ?>" placeholder="标题">
            <textarea class="input" name="<?= e(site_setting_field_name('home.' . $slotKey . '.body')) ?>" rows="3" placeholder="副文案"><?= e($homeCopy['home.' . $slotKey . '.body']) ?></textarea>
            <input class="input" name="<?= e(site_setting_field_name('home.' . $slotKey . '.tag')) ?>" value="<?= e($homeCopy['home.' . $slotKey . '.tag']) ?>" placeholder="标签">
          </div>
        <?php endforeach; ?>
      </div>
      <div class="admin-action-stack" style="margin-top:16px;"><button class="pill-btn solid" type="submit">保存首页文案</button></div>
    </form>
  </section>

  <section id="comments" class="glass panel-card admin-panel-card">
    <div class="section-kicker">Comments</div>
    <div class="side-head admin-head-row"><h3>评论管理</h3><span class="muted">支持按帖子 / 作者 / 关键词 / 状态筛选，并可批量审核、隐藏、恢复。</span></div>
    <form class="admin-filter-row" method="get">
      <input class="input admin-filter-input" type="number" min="0" name="post_id" placeholder="按帖子 ID 查看" value="<?= $postFilterId > 0 ? (int) $postFilterId : '' ?>">
      <input class="input admin-filter-input" type="number" min="0" name="author_id" placeholder="按作者 ID 查看" value="<?= $authorFilterId > 0 ? (int) $authorFilterId : '' ?>">
      <input class="input admin-filter-input" type="text" name="post_title_keyword" placeholder="帖子标题关键词" value="<?= e($postTitleKeyword) ?>">
      <input class="input admin-filter-input" type="text" name="author_keyword" placeholder="作者昵称 / 用户名关键词" value="<?= e($authorKeyword) ?>">
      <input class="input admin-filter-input" type="text" name="content_keyword" placeholder="评论内容关键词" value="<?= e($contentKeyword) ?>">
      <select class="input admin-filter-input" name="comment_status">
        <option value="">全部状态</option>
        <?php foreach (['approved', 'pending', 'hidden'] as $status): ?>
          <option value="<?= e($status) ?>" <?= $commentStatusFilter === $status ? 'selected' : '' ?>><?= e(comment_status_label($status)) ?></option>
        <?php endforeach; ?>
      </select>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="/admin.php#comments">清空</a>
    </form>
    <div class="hero-stats compact-hero-stats admin-hero-stats" style="margin-top: 16px;">
      <?php foreach ($commentStatusStats as $stat): ?>
        <div class="hero-stat"><div class="label"><?= e(comment_status_label($stat['status'])) ?></div><div class="num small-num"><?= (int) $stat['total_count'] ?></div><div class="note">全站评论状态计数</div></div>
      <?php endforeach; ?>
    </div>
    <div class="admin-log-meta muted">当前页命中 <?= $commentCount ?> 条评论 · 共 <?= $commentTotal ?> 条 · 第 <?= $commentPage ?> / <?= $commentTotalPages ?> 页</div>
    <form id="bulk-comments-form" method="post">
      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
      <input type="hidden" name="action" value="bulk_comment_status">
      <input type="hidden" name="target_status" id="bulk-comment-status" value="approved">
    </form>
    <div class="admin-bulk-bar">
      <button class="pill-btn solid" type="submit" form="bulk-comments-form" onclick="document.getElementById('bulk-comment-status').value='approved'; return confirm('确认批量通过已勾选评论？');">批量审核通过</button>
      <button class="pill-btn" type="submit" form="bulk-comments-form" onclick="document.getElementById('bulk-comment-status').value='pending'; return confirm('确认批量恢复到待审核？');">批量恢复待审核</button>
      <button class="pill-btn danger" type="submit" form="bulk-comments-form" onclick="document.getElementById('bulk-comment-status').value='hidden'; return confirm('确认批量隐藏已勾选评论？');">批量隐藏</button>
    </div>
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th><input type="checkbox" onclick="document.querySelectorAll('.comment-select').forEach(el => el.checked = this.checked)"></th><th>ID</th><th>评论内容</th><th>状态</th><th>作者</th><th>所属帖子</th><th>时间</th><th>操作</th></tr></thead>
        <tbody>
          <?php foreach ($commentRows as $row): ?>
            <tr>
              <td><input class="comment-select" type="checkbox" name="comment_ids[]" value="<?= (int) $row['id'] ?>" form="bulk-comments-form"></td>
              <td>#<?= (int) $row['id'] ?></td>
              <td><?= e(excerpt($row['content'], 88)) ?></td>
              <td><span class="tiny-badge"><?= e(comment_status_label($row['status'] ?? 'approved')) ?></span></td>
              <td>
                <strong><?= e($row['nickname']) ?></strong>
                <div class="muted">@<?= e($row['username']) ?></div>
                <div><a class="inline-link" href="<?= e(admin_url(['author_id' => (int) $row['user_id'], 'author_keyword' => null], '#comments')) ?>">看该作者评论</a></div>
              </td>
              <td>
                <a class="inline-link" href="/post.php?id=<?= (int) $row['post_id'] ?>"><?= e($row['post_title']) ?></a>
                <div class="muted">楼主：<?= e($row['post_owner_nickname']) ?> @<?= e($row['post_owner_username']) ?></div>
                <div><a class="inline-link" href="<?= e(admin_url(['post_id' => (int) $row['post_id'], 'post_title_keyword' => null], '#comments')) ?>">看该帖子评论</a></div>
              </td>
              <td><?= e(substr($row['created_at'], 0, 16)) ?></td>
              <td>
                <div class="admin-action-stack">
                  <a class="pill-btn" href="/post.php?id=<?= (int) $row['post_id'] ?>">前往原帖</a>
                  <form method="post" class="inline-form">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="bulk_comment_status">
                    <input type="hidden" name="comment_ids[]" value="<?= (int) $row['id'] ?>">
                    <input type="hidden" name="target_status" value="approved">
                    <button class="pill-btn solid" type="submit">通过</button>
                  </form>
                  <form method="post" class="inline-form">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="bulk_comment_status">
                    <input type="hidden" name="comment_ids[]" value="<?= (int) $row['id'] ?>">
                    <input type="hidden" name="target_status" value="hidden">
                    <button class="pill-btn" type="submit">隐藏</button>
                  </form>
                  <form method="post" class="inline-form">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="bulk_comment_status">
                    <input type="hidden" name="comment_ids[]" value="<?= (int) $row['id'] ?>">
                    <input type="hidden" name="target_status" value="pending">
                    <button class="pill-btn" type="submit">待审</button>
                  </form>
                  <form method="post" class="inline-form" onsubmit="return confirm('确认删除这条评论？此操作会写入日志。');">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="delete_comment_admin">
                    <input type="hidden" name="comment_id" value="<?= (int) $row['id'] ?>">
                    <button class="pill-btn danger" type="submit">删除</button>
                  </form>
                </div>
              </td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$commentRows): ?>
            <tr><td colspan="8" class="muted">当前筛选条件下没有评论记录。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
    <?= admin_pagination([
      'post_id' => $postFilterId,
      'author_id' => $authorFilterId,
      'post_title_keyword' => $postTitleKeyword,
      'author_keyword' => $authorKeyword,
      'content_keyword' => $contentKeyword,
      'comment_status' => $commentStatusFilter,
      'post_page' => $postPage,
      'log_action' => $logActionFilter,
      'log_target_type' => $logTargetTypeFilter,
      'log_actor_id' => $logActorIdFilter,
      'log_page' => $logPage,
    ], 'comment_page', $commentPage, $commentTotalPages, '#comments') ?>
  </section>

  <section id="notifications-overview" class="glass panel-card admin-panel-card">
    <div class="section-kicker">Notifications</div>
    <div class="side-head admin-head-row"><h3>站内通知概况</h3><span class="muted">前台已支持未读筛选、按类型筛选和批量处理，这里保留全站分布看板。</span></div>
    <div class="hero-stats compact-hero-stats admin-hero-stats">
      <div class="hero-stat"><div class="label">通知总数</div><div class="num small-num"><?= (int) ($notificationTotals['total_notifications'] ?? 0) ?></div><div class="note">全站累计站内提醒</div></div>
      <div class="hero-stat"><div class="label">全站未读</div><div class="num small-num"><?= (int) ($notificationTotals['unread_notifications'] ?? 0) ?></div><div class="note">尚未被用户消化</div></div>
      <div class="hero-stat"><div class="label">24 小时</div><div class="num small-num"><?= $notificationTodayCount ?></div><div class="note">最近一天新增提醒</div></div>
      <div class="hero-stat"><div class="label">7 天</div><div class="num small-num"><?= $notificationSevenDayCount ?></div><div class="note">最近七天新增提醒</div></div>
    </div>
    <div class="admin-table-wrap">
      <table class="admin-table compact-table">
        <thead><tr><th>提醒类型</th><th>总量</th><th>未读</th><th>说明</th></tr></thead>
        <tbody>
          <?php foreach ($notificationTypeRows as $row): ?>
            <tr>
              <td><span class="tiny-badge"><?= e(notification_type_label($row['type'])) ?></span><div class="muted"><?= e($row['type']) ?></div></td>
              <td><?= (int) $row['total_count'] ?></td>
              <td><?= (int) $row['unread_count'] ?></td>
              <td><?= e(admin_notification_copy($row['type'])) ?></td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$notificationTypeRows): ?>
            <tr><td colspan="4" class="muted">当前还没有任何站内通知数据。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
  </section>

  <?php if ($canManageUsers): ?>
    <section id="users" class="glass panel-card admin-panel-card">
      <div class="section-kicker">Users</div>
      <div class="side-head"><h3>用户 / 角色管理</h3></div>
      <div class="notice subtle-notice">只有管理员可以调整用户角色与启停状态；版主进入后台时，这一整块不会显示。</div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>ID</th><th>用户</th><th>邮箱</th><th>角色</th><th>状态</th><th>内容量</th><th>操作</th></tr></thead>
          <tbody>
            <?php foreach ($userRows as $row): ?>
              <tr>
                <td>#<?= (int) $row['id'] ?></td>
                <td><strong><?= e($row['nickname']) ?></strong><div class="muted">@<?= e($row['username']) ?></div></td>
                <td><?= e($row['email']) ?></td>
                <td><span class="tiny-badge"><?= e(role_label($row['role'] ?? 'member')) ?></span></td>
                <td><span class="tiny-badge <?= (int) $row['is_active'] === 1 ? 'badge-ok' : 'badge-danger' ?>"><?= (int) $row['is_active'] === 1 ? '启用中' : '已停用' ?></span></td>
                <td><?= (int) $row['post_count'] ?> 帖 / <?= (int) $row['comment_count'] ?> 评</td>
                <td>
                  <div class="admin-inline-stack">
                    <form method="post" class="inline-form inline-select-form">
                      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                      <input type="hidden" name="action" value="set_user_role">
                      <input type="hidden" name="user_id" value="<?= (int) $row['id'] ?>">
                      <select class="input slim-input" name="role">
                        <?php foreach (['member' => '成员', 'moderator' => '版主', 'admin' => '管理员'] as $roleValue => $roleName): ?>
                          <option value="<?= e($roleValue) ?>" <?= ($row['role'] ?? 'member') === $roleValue ? 'selected' : '' ?>><?= e($roleName) ?></option>
                        <?php endforeach; ?>
                      </select>
                      <button class="pill-btn solid" type="submit">设为</button>
                    </form>
                    <?php if ((int) $row['id'] === (int) $user['id']): ?>
                      <span class="muted">当前账号</span>
                    <?php else: ?>
                      <form method="post" class="inline-form">
                        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                        <input type="hidden" name="action" value="toggle_user_active">
                        <input type="hidden" name="user_id" value="<?= (int) $row['id'] ?>">
                        <input type="hidden" name="target_status" value="<?= (int) $row['is_active'] === 1 ? 0 : 1 ?>">
                        <button class="pill-btn <?= (int) $row['is_active'] === 1 ? 'danger' : 'solid' ?>" type="submit"><?= (int) $row['is_active'] === 1 ? '停用' : '启用' ?></button>
                      </form>
                    <?php endif; ?>
                  </div>
                </td>
              </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    </section>
  <?php endif; ?>

  <?php if ($canManageStructure): ?>
    <div class="nebula-section-grid admin-grid-two">
      <section id="categories" class="glass panel-card admin-panel-card">
        <div class="section-kicker">Categories</div>
        <div class="side-head"><h3>分类管理</h3></div>
        <div class="notice subtle-notice">删除分类时，如果下面还有版块，可直接选择目标分类迁移后再删；同时支持上移 / 下移快速调序。</div>
        <form class="admin-crud-form" method="post">
          <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
          <input type="hidden" name="action" value="create_category">
          <input class="input" name="name" placeholder="分类名称">
          <input class="input" name="slug" placeholder="slug，例如 strategy-hub">
          <input class="input" name="description" placeholder="分类描述">
          <input class="input" type="number" name="sort_order" value="0" placeholder="排序">
          <button class="pill-btn solid" type="submit">新增分类</button>
        </form>
        <div class="admin-list-stack">
          <?php foreach ($categoryRows as $row): ?>
            <form class="admin-list-card" method="post">
              <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
              <input type="hidden" name="category_id" value="<?= (int) $row['id'] ?>">
              <div class="admin-list-card-head"><strong>#<?= (int) $row['id'] ?> · <?= e($row['name']) ?></strong><span class="tiny-badge"><?= (int) $row['board_count'] ?> 个版块</span></div>
              <input class="input" name="name" value="<?= e($row['name']) ?>">
              <input class="input" name="slug" value="<?= e($row['slug']) ?>">
              <input class="input" name="description" value="<?= e($row['description']) ?>">
              <input class="input" type="number" name="sort_order" value="<?= (int) $row['sort_order'] ?>">
              <select class="input" name="target_category_id">
                <option value="0">删除时不迁移（仅空分类可直接删）</option>
                <?php foreach ($availableCategoryTargets as $target): ?>
                  <?php if ((int) $target['id'] === (int) $row['id']) { continue; } ?>
                  <option value="<?= (int) $target['id'] ?>">迁移版块到：<?= e($target['name']) ?></option>
                <?php endforeach; ?>
              </select>
              <div class="admin-action-stack">
                <button class="pill-btn" type="submit" name="action" value="move_category" onclick="this.form.direction.value='up'">上移</button>
                <button class="pill-btn" type="submit" name="action" value="move_category" onclick="this.form.direction.value='down'">下移</button>
                <input type="hidden" name="direction" value="up">
                <button class="pill-btn solid" type="submit" name="action" value="update_category">保存分类</button>
                <button class="pill-btn danger" type="submit" name="action" value="delete_category" onclick="return confirm('确认删除这个分类？若已选迁移目标，会先迁移版块再删除。');">删除 / 迁移删除</button>
              </div>
            </form>
          <?php endforeach; ?>
        </div>
      </section>

      <section id="boards" class="glass panel-card admin-panel-card">
        <div class="section-kicker">Boards</div>
        <div class="side-head"><h3>版块管理</h3></div>
        <div class="notice subtle-notice">删除版块时，可把原帖整体迁移到其他版块；同分类内还支持上移 / 下移调序。</div>
        <form class="admin-crud-form" method="post">
          <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
          <input type="hidden" name="action" value="create_board">
          <select class="input" name="category_id">
            <?php foreach ($categoryRows as $category): ?>
              <option value="<?= (int) $category['id'] ?>"><?= e($category['name']) ?></option>
            <?php endforeach; ?>
          </select>
          <input class="input" name="name" placeholder="版块名称">
          <input class="input" name="slug" placeholder="slug，例如 pvp-lab">
          <input class="input" name="description" placeholder="版块描述">
          <input class="input" name="accent_color" placeholder="#23d3a2">
          <input class="input" type="number" name="sort_order" value="0" placeholder="排序">
          <button class="pill-btn solid" type="submit">新增版块</button>
        </form>
        <div class="admin-list-stack">
          <?php foreach ($boardRows as $row): ?>
            <form class="admin-list-card" method="post">
              <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
              <input type="hidden" name="board_id" value="<?= (int) $row['id'] ?>">
              <div class="admin-list-card-head"><strong>#<?= (int) $row['id'] ?> · <?= e($row['name']) ?></strong><span class="tiny-badge"><?= (int) $row['post_count'] ?> 帖</span></div>
              <select class="input" name="category_id">
                <?php foreach ($categoryRows as $category): ?>
                  <option value="<?= (int) $category['id'] ?>" <?= (int) $row['category_id'] === (int) $category['id'] ? 'selected' : '' ?>><?= e($category['name']) ?></option>
                <?php endforeach; ?>
              </select>
              <input class="input" name="name" value="<?= e($row['name']) ?>">
              <input class="input" name="slug" value="<?= e($row['slug']) ?>">
              <input class="input" name="description" value="<?= e($row['description']) ?>">
              <input class="input" name="accent_color" value="<?= e($row['accent_color']) ?>">
              <input class="input" type="number" name="sort_order" value="<?= (int) $row['sort_order'] ?>">
              <select class="input" name="target_board_id">
                <option value="0">删除时不迁移（仅空版块可直接删）</option>
                <?php foreach ($availableBoardTargets as $target): ?>
                  <?php if ((int) $target['id'] === (int) $row['id']) { continue; } ?>
                  <option value="<?= (int) $target['id'] ?>">迁移帖子到：<?= e($target['category_name']) ?> / <?= e($target['name']) ?></option>
                <?php endforeach; ?>
              </select>
              <div class="admin-action-stack">
                <button class="pill-btn" type="submit" name="action" value="move_board" onclick="this.form.direction.value='up'">上移</button>
                <button class="pill-btn" type="submit" name="action" value="move_board" onclick="this.form.direction.value='down'">下移</button>
                <input type="hidden" name="direction" value="up">
                <button class="pill-btn solid" type="submit" name="action" value="update_board">保存版块</button>
                <button class="pill-btn danger" type="submit" name="action" value="delete_board" onclick="return confirm('确认删除这个版块？若已选迁移目标，会先迁移帖子再删除。');">删除 / 迁移删除</button>
              </div>
            </form>
          <?php endforeach; ?>
        </div>
      </section>
    </div>
  <?php endif; ?>

  <section id="logs" class="glass panel-card admin-panel-card">
    <div class="section-kicker">Logs</div>
    <div class="side-head admin-head-row"><h3>操作日志</h3><span class="muted">支持按动作、目标类型、操作者筛选，并做分页回看。</span></div>
    <form class="admin-filter-row admin-log-filter-row" method="get">
      <input type="hidden" name="post_id" value="<?= $postFilterId > 0 ? (int) $postFilterId : '' ?>">
      <input type="hidden" name="author_id" value="<?= $authorFilterId > 0 ? (int) $authorFilterId : '' ?>">
      <input type="hidden" name="post_title_keyword" value="<?= e($postTitleKeyword) ?>">
      <input type="hidden" name="author_keyword" value="<?= e($authorKeyword) ?>">
      <input type="hidden" name="content_keyword" value="<?= e($contentKeyword) ?>">
      <input type="hidden" name="comment_status" value="<?= e($commentStatusFilter) ?>">
      <select class="input admin-filter-input" name="log_action">
        <option value="">全部动作</option>
        <?php foreach ($logActionOptions as $actionType): ?>
          <option value="<?= e($actionType) ?>" <?= $logActionFilter === $actionType ? 'selected' : '' ?>><?= e($actionType) ?></option>
        <?php endforeach; ?>
      </select>
      <select class="input admin-filter-input" name="log_target_type">
        <option value="">全部对象</option>
        <?php foreach ($logTargetTypeOptions as $targetType): ?>
          <option value="<?= e($targetType) ?>" <?= $logTargetTypeFilter === $targetType ? 'selected' : '' ?>><?= e($targetType) ?></option>
        <?php endforeach; ?>
      </select>
      <select class="input admin-filter-input" name="log_actor_id">
        <option value="0">全部操作者</option>
        <?php foreach ($logActorOptions as $actor): ?>
          <option value="<?= (int) $actor['id'] ?>" <?= $logActorIdFilter === (int) $actor['id'] ? 'selected' : '' ?>><?= e($actor['nickname']) ?> @<?= e($actor['username']) ?></option>
        <?php endforeach; ?>
      </select>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="<?= e(admin_url(['log_action' => null, 'log_target_type' => null, 'log_actor_id' => null, 'log_page' => null], '#logs')) ?>">清空</a>
    </form>
    <div class="admin-log-meta muted">共 <?= $logTotal ?> 条记录 · 第 <?= $logPage ?> / <?= $logTotalPages ?> 页</div>
    <div class="admin-table-wrap">
      <table class="admin-table compact-table">
        <thead><tr><th>时间</th><th>执行人</th><th>动作</th><th>对象</th><th>详情</th></tr></thead>
        <tbody>
          <?php foreach ($logRows as $row): ?>
            <tr>
              <td><?= e(substr($row['created_at'], 0, 16)) ?></td>
              <td><?= e($row['nickname']) ?><div class="muted">@<?= e($row['username']) ?> · #<?= (int) $row['actor_id'] ?></div></td>
              <td><span class="tiny-badge"><?= e($row['action_type']) ?></span></td>
              <td><?= e($row['target_type']) ?> #<?= (int) $row['target_id'] ?></td>
              <td><?= e($row['details']) ?></td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$logRows): ?>
            <tr><td colspan="5" class="muted">当前筛选条件下没有操作日志。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
    <?= admin_pagination([
      'post_id' => $postFilterId,
      'author_id' => $authorFilterId,
      'post_title_keyword' => $postTitleKeyword,
      'author_keyword' => $authorKeyword,
      'content_keyword' => $contentKeyword,
      'comment_status' => $commentStatusFilter,
      'post_page' => $postPage,
      'comment_page' => $commentPage,
      'log_action' => $logActionFilter,
      'log_target_type' => $logTargetTypeFilter,
      'log_actor_id' => $logActorIdFilter,
    ], 'log_page', $logPage, $logTotalPages, '#logs') ?>
  </section>
</main>
<?php render_footer(); ?>
