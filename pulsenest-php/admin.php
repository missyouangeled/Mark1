<?php
require __DIR__ . '/layout.php';
$user = ensure_staff();
$flash = flash_get();
$canManageUsers = can_manage_users($user);
$canManageStructure = can_manage_forum_structure($user);

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
        $stmt = db()->prepare('SELECT c.id, c.content, c.post_id, p.title, u.nickname, u.username FROM comments c INNER JOIN posts p ON p.id = c.post_id INNER JOIN pulsenest_users u ON u.id = c.user_id WHERE c.id = :id LIMIT 1');
        $stmt->execute(['id' => $commentId]);
        $comment = $stmt->fetch();
        if ($comment) {
            $delete = db()->prepare('DELETE FROM comments WHERE id = :id LIMIT 1');
            $delete->execute(['id' => $commentId]);
            log_moderation_action((int) $user['id'], 'comment_deleted', 'comment', $commentId, ($comment['nickname'] ?: $comment['username']) . ' · 《' . $comment['title'] . '》 · ' . excerpt($comment['content'], 80));
            flash_set('success', '评论已删除。');
        }
        $query = [];
        if (!empty($_POST['filter_post_id'])) {
            $query['post_id'] = (int) $_POST['filter_post_id'];
        }
        if (!empty($_POST['filter_author_id'])) {
            $query['author_id'] = (int) $_POST['filter_author_id'];
        }
        $redirect = '/admin.php' . ($query ? '?' . http_build_query($query) : '') . '#comments';
        redirect_to($redirect);
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
        $stmt = db()->prepare('SELECT id, name, slug FROM forum_categories WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $categoryId]);
        $category = $stmt->fetch();
        if (!$category) {
            flash_set('error', '没有找到要删除的分类。');
        } else {
            $countStmt = db()->prepare('SELECT COUNT(*) FROM forum_boards WHERE category_id = :id');
            $countStmt->execute(['id' => $categoryId]);
            $boardCount = (int) $countStmt->fetchColumn();
            if ($boardCount > 0) {
                flash_set('error', '该分类下还有 ' . $boardCount . ' 个版块，先清空或迁移版块后才能删除。');
            } else {
                $delete = db()->prepare('DELETE FROM forum_categories WHERE id = :id LIMIT 1');
                $delete->execute(['id' => $categoryId]);
                log_moderation_action((int) $user['id'], 'category_deleted', 'category', $categoryId, $category['name'] . ' · ' . $category['slug']);
                flash_set('success', '分类已删除。');
            }
        }
        redirect_to('/admin.php#categories');
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
        $stmt = db()->prepare('SELECT id, name, slug FROM forum_boards WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $boardId]);
        $board = $stmt->fetch();
        if (!$board) {
            flash_set('error', '没有找到要删除的版块。');
        } else {
            $countStmt = db()->prepare('SELECT COUNT(*) FROM posts WHERE board_id = :id');
            $countStmt->execute(['id' => $boardId]);
            $postCount = (int) $countStmt->fetchColumn();
            if ($postCount > 0) {
                flash_set('error', '该版块下还有 ' . $postCount . ' 篇帖子，先迁移或删除帖子后才能删版块。');
            } else {
                $delete = db()->prepare('DELETE FROM forum_boards WHERE id = :id LIMIT 1');
                $delete->execute(['id' => $boardId]);
                log_moderation_action((int) $user['id'], 'board_deleted', 'board', $boardId, $board['name'] . ' · ' . $board['slug']);
                flash_set('success', '版块已删除。');
            }
        }
        redirect_to('/admin.php#boards');
    }
}

$postFilterId = (int) ($_GET['post_id'] ?? 0);
$authorFilterId = (int) ($_GET['author_id'] ?? 0);
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
$commentSql =
    'SELECT c.id, c.post_id, c.user_id, c.content, c.created_at,
            p.title AS post_title,
            u.nickname, u.username,
            owner.nickname AS post_owner_nickname, owner.username AS post_owner_username
     FROM comments c
     INNER JOIN posts p ON p.id = c.post_id
     INNER JOIN pulsenest_users u ON u.id = c.user_id
     INNER JOIN pulsenest_users owner ON owner.id = p.user_id'
    . ($commentWhere ? ' WHERE ' . implode(' AND ', $commentWhere) : '')
    . ' ORDER BY c.created_at DESC, c.id DESC LIMIT 120';
$commentStmt = db()->prepare($commentSql);
$commentStmt->execute($commentParams);
$commentRows = $commentStmt->fetchAll();

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

$postRows = db()->query(
    'SELECT p.id, p.title, p.created_at,
            u.nickname, u.username,
            fb.name AS board_name,
            fc.name AS category_name,
            COALESCE(c.comment_count, 0) AS comment_count
     FROM posts p
     INNER JOIN pulsenest_users u ON u.id = p.user_id
     LEFT JOIN forum_boards fb ON fb.id = p.board_id
     LEFT JOIN forum_categories fc ON fc.id = fb.category_id
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS comment_count FROM comments GROUP BY post_id
     ) c ON c.post_id = p.id
     ORDER BY p.created_at DESC, p.id DESC'
)->fetchAll();

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

$logRows = db()->query(
    'SELECT l.id, l.action_type, l.target_type, l.target_id, l.details, l.created_at,
            u.nickname, u.username
     FROM moderation_logs l
     INNER JOIN pulsenest_users u ON u.id = l.actor_user_id
     ORDER BY l.created_at DESC, l.id DESC
     LIMIT 30'
)->fetchAll();

render_header('PulseNest · 后台管理', $user, [
    'searchText' => '🔎 后台：评论、帖子、角色、分类、版块、操作日志',
]);
?>
  <main class="shell page-shell nebula-page-shell admin-page">
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>

    <section class="glass nebula-hero nebula-hero-split create-post-hero">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始01 · 后台增强版</div>
        <h1>把管理能力补到能真正在社区里用。</h1>
        <p class="page-desc nebula-desc">现在后台已经能做评论巡检、删帖删评、用户角色拆分、分类 / 版块增删改，以及最近操作日志留痕。版主只能管内容，管理员才能动用户和论坛结构。</p>
        <div class="hero-stats compact-hero-stats">
          <div class="hero-stat"><div class="label">当前身份</div><div class="num small-num"><?= e(role_label(user_role($user))) ?></div><div class="note"><?= is_admin($user) ? '拥有全量后台权限' : '仅限内容管理范围' ?></div></div>
          <div class="hero-stat"><div class="label">评论</div><div class="num small-num"><?= count($commentRows) ?></div><div class="note">支持按帖子 / 作者筛选</div></div>
          <div class="hero-stat"><div class="label">操作日志</div><div class="num small-num"><?= count($logRows) ?></div><div class="note">至少记录删帖删评与结构调整</div></div>
        </div>
      </div>
      <aside class="glass side-card nebula-side-panel">
        <div class="section-kicker">Admin Scope</div>
        <div class="quick-links">
          <a class="quick-link" href="#comments">评论管理</a>
          <a class="quick-link" href="#posts">帖子管理</a>
          <?php if ($canManageUsers): ?><a class="quick-link" href="#users">角色 / 用户</a><?php endif; ?>
          <?php if ($canManageStructure): ?><a class="quick-link" href="#categories">分类 / 版块</a><?php endif; ?>
          <a class="quick-link" href="#logs">操作日志</a>
        </div>
      </aside>
    </section>

    <section id="comments" class="glass panel-card admin-panel-card">
      <div class="section-kicker">Comments</div>
      <div class="side-head admin-head-row"><h3>评论管理</h3><span class="muted">支持直接按帖子或作者回看评论流</span></div>
      <form class="admin-filter-row" method="get">
        <input class="input admin-filter-input" type="number" min="0" name="post_id" placeholder="按帖子 ID 查看" value="<?= $postFilterId > 0 ? (int) $postFilterId : '' ?>">
        <input class="input admin-filter-input" type="number" min="0" name="author_id" placeholder="按作者 ID 查看" value="<?= $authorFilterId > 0 ? (int) $authorFilterId : '' ?>">
        <button class="pill-btn solid" type="submit">筛选</button>
        <a class="pill-btn" href="/admin.php#comments">清空</a>
      </form>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>ID</th><th>评论内容</th><th>作者</th><th>所属帖子</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <?php foreach ($commentRows as $row): ?>
              <tr>
                <td>#<?= (int) $row['id'] ?></td>
                <td><?= e(excerpt($row['content'], 88)) ?></td>
                <td>
                  <strong><?= e($row['nickname']) ?></strong>
                  <div class="muted">@<?= e($row['username']) ?></div>
                  <div><a class="inline-link" href="/admin.php?author_id=<?= (int) $row['user_id'] ?>#comments">看该作者评论</a></div>
                </td>
                <td>
                  <a class="inline-link" href="/post.php?id=<?= (int) $row['post_id'] ?>"><?= e($row['post_title']) ?></a>
                  <div class="muted">楼主：<?= e($row['post_owner_nickname']) ?> @<?= e($row['post_owner_username']) ?></div>
                  <div><a class="inline-link" href="/admin.php?post_id=<?= (int) $row['post_id'] ?>#comments">看该帖子评论</a></div>
                </td>
                <td><?= e(substr($row['created_at'], 0, 16)) ?></td>
                <td>
                  <div class="admin-action-stack">
                    <a class="pill-btn" href="/post.php?id=<?= (int) $row['post_id'] ?>">前往原帖</a>
                    <form method="post" class="inline-form" onsubmit="return confirm('确认删除这条评论？此操作会写入日志。');">
                      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                      <input type="hidden" name="action" value="delete_comment_admin">
                      <input type="hidden" name="comment_id" value="<?= (int) $row['id'] ?>">
                      <input type="hidden" name="filter_post_id" value="<?= (int) $postFilterId ?>">
                      <input type="hidden" name="filter_author_id" value="<?= (int) $authorFilterId ?>">
                      <button class="pill-btn danger" type="submit">删除</button>
                    </form>
                  </div>
                </td>
              </tr>
            <?php endforeach; ?>
            <?php if (!$commentRows): ?>
              <tr><td colspan="6" class="muted">当前筛选条件下没有评论记录。</td></tr>
            <?php endif; ?>
          </tbody>
        </table>
      </div>
    </section>

    <section id="posts" class="glass panel-card admin-panel-card">
      <div class="section-kicker">Posts</div>
      <div class="side-head"><h3>帖子管理</h3></div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>ID</th><th>标题</th><th>作者</th><th>版块</th><th>回复</th><th>时间</th><th>操作</th></tr></thead>
          <tbody>
            <?php foreach ($postRows as $row): ?>
              <tr>
                <td>#<?= (int) $row['id'] ?></td>
                <td><a class="inline-link" href="/post.php?id=<?= (int) $row['id'] ?>"><?= e($row['title']) ?></a></td>
                <td><?= e($row['nickname']) ?><div class="muted">@<?= e($row['username']) ?></div></td>
                <td><?= e(trim(($row['category_name'] ?? '公共区') . ' / ' . ($row['board_name'] ?? '未分区'))) ?></td>
                <td><?= (int) $row['comment_count'] ?></td>
                <td><?= e(substr($row['created_at'], 0, 16)) ?></td>
                <td>
                  <div class="admin-action-stack">
                    <a class="pill-btn" href="/edit-post.php?id=<?= (int) $row['id'] ?>">编辑</a>
                    <a class="pill-btn" href="/admin.php?post_id=<?= (int) $row['id'] ?>#comments">看评论</a>
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
    </section>

    <?php if ($canManageUsers): ?>
      <section id="users" class="glass panel-card admin-panel-card">
        <div class="section-kicker">Users</div>
        <div class="side-head"><h3>用户 / 角色管理</h3></div>
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
                <div class="admin-action-stack">
                  <button class="pill-btn solid" type="submit" name="action" value="update_category">保存分类</button>
                  <button class="pill-btn danger" type="submit" name="action" value="delete_category" onclick="return confirm('确认删除这个分类？只有空分类才能删除。');">删除</button>
                </div>
              </form>
            <?php endforeach; ?>
          </div>
        </section>

        <section id="boards" class="glass panel-card admin-panel-card">
          <div class="section-kicker">Boards</div>
          <div class="side-head"><h3>版块管理</h3></div>
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
                <div class="admin-action-stack">
                  <button class="pill-btn solid" type="submit" name="action" value="update_board">保存版块</button>
                  <button class="pill-btn danger" type="submit" name="action" value="delete_board" onclick="return confirm('确认删除这个版块？只有空版块才能删除。');">删除</button>
                </div>
              </form>
            <?php endforeach; ?>
          </div>
        </section>
      </div>
    <?php endif; ?>

    <section id="logs" class="glass panel-card admin-panel-card">
      <div class="section-kicker">Logs</div>
      <div class="side-head"><h3>最近操作日志</h3></div>
      <div class="admin-table-wrap">
        <table class="admin-table compact-table">
          <thead><tr><th>时间</th><th>执行人</th><th>动作</th><th>对象</th><th>详情</th></tr></thead>
          <tbody>
            <?php foreach ($logRows as $row): ?>
              <tr>
                <td><?= e(substr($row['created_at'], 0, 16)) ?></td>
                <td><?= e($row['nickname']) ?><div class="muted">@<?= e($row['username']) ?></div></td>
                <td><?= e($row['action_type']) ?></td>
                <td><?= e($row['target_type']) ?> #<?= (int) $row['target_id'] ?></td>
                <td><?= e($row['details']) ?></td>
              </tr>
            <?php endforeach; ?>
            <?php if (!$logRows): ?>
              <tr><td colspan="5" class="muted">还没有操作日志。</td></tr>
            <?php endif; ?>
          </tbody>
        </table>
      </div>
    </section>
  </main>
<?php render_footer(); ?>