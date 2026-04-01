<?php
require __DIR__ . '/layout.php';
$user = ensure_admin();
$flash = flash_get();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = $_POST['action'] ?? '';

    if ($action === 'toggle_user_active') {
        $targetUserId = (int) ($_POST['user_id'] ?? 0);
        $targetStatus = (int) ($_POST['target_status'] ?? 0);
        if ($targetUserId === (int) $user['id'] && $targetStatus === 0) {
            flash_set('error', '不能把当前管理员自己停用。');
        } else {
            $stmt = db()->prepare('UPDATE pulsenest_users SET is_active = :is_active WHERE id = :id LIMIT 1');
            $stmt->execute(['is_active' => $targetStatus ? 1 : 0, 'id' => $targetUserId]);
            flash_set('success', $targetStatus ? '用户已启用。' : '用户已停用。');
        }
        redirect_to('/admin.php#users');
    }

    if ($action === 'delete_post_admin') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $stmt = db()->prepare('SELECT id, image_path FROM posts WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $postId]);
        $post = $stmt->fetch();
        if ($post) {
            $delete = db()->prepare('DELETE FROM posts WHERE id = :id LIMIT 1');
            $delete->execute(['id' => $postId]);
            delete_uploaded_asset($post['image_path'] ?? null);
            flash_set('success', '帖子已从后台删除。');
        }
        redirect_to('/admin.php#posts');
    }
}

$userRows = db()->query(
    'SELECT u.id, u.username, u.nickname, u.email, u.is_admin, u.is_active, u.created_at,
            COALESCE(p.post_count, 0) AS post_count
     FROM pulsenest_users u
     LEFT JOIN (
        SELECT user_id, COUNT(*) AS post_count FROM posts GROUP BY user_id
     ) p ON p.user_id = u.id
     ORDER BY u.created_at DESC, u.id DESC'
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
    'SELECT b.id, b.name, b.slug, b.description, b.sort_order, b.accent_color,
            c.name AS category_name,
            COALESCE(p.post_count, 0) AS post_count
     FROM forum_boards b
     INNER JOIN forum_categories c ON c.id = b.category_id
     LEFT JOIN (
        SELECT board_id, COUNT(*) AS post_count FROM posts GROUP BY board_id
     ) p ON p.board_id = b.id
     ORDER BY c.sort_order ASC, c.id ASC, b.sort_order ASC, b.id ASC'
)->fetchAll();

render_header('PulseNest · 后台管理', $user, [
    'searchText' => '🔎 后台最小版：用户、帖子、分类、版块列表与基础操作',
]);
?>
  <main class="shell page-shell nebula-page-shell admin-page">
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>

    <section class="glass nebula-hero nebula-hero-split create-post-hero">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始01 · 最小后台管理页</div>
        <h1>先给社区一个能看的、能管的后台骨架。</h1>
        <p class="page-desc nebula-desc">这一页暂时不追求复杂权限系统，先把管理员可见的核心列表补齐：用户、帖子、分类、版块；顺手加了用户启停和帖子删除入口。</p>
        <div class="hero-stats compact-hero-stats">
          <div class="hero-stat"><div class="label">用户</div><div class="num small-num"><?= count($userRows) ?></div><div class="note">可启用 / 停用</div></div>
          <div class="hero-stat"><div class="label">帖子</div><div class="num small-num"><?= count($postRows) ?></div><div class="note">可后台删除</div></div>
          <div class="hero-stat"><div class="label">论坛结构</div><div class="num small-num"><?= count($categoryRows) ?> / <?= count($boardRows) ?></div><div class="note">分类 / 版块一页看全</div></div>
        </div>
      </div>
      <aside class="glass side-card nebula-side-panel">
        <div class="section-kicker">Admin Scope</div>
        <div class="quick-links">
          <a class="quick-link" href="#users">用户列表</a>
          <a class="quick-link" href="#posts">帖子列表</a>
          <a class="quick-link" href="#categories">分类列表</a>
          <a class="quick-link" href="#boards">版块列表</a>
        </div>
      </aside>
    </section>

    <section id="users" class="glass panel-card admin-panel-card">
      <div class="section-kicker">Users</div>
      <div class="side-head"><h3>用户列表</h3></div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>ID</th><th>用户</th><th>邮箱</th><th>角色</th><th>状态</th><th>帖子数</th><th>操作</th></tr></thead>
          <tbody>
            <?php foreach ($userRows as $row): ?>
              <tr>
                <td>#<?= (int) $row['id'] ?></td>
                <td><strong><?= e($row['nickname']) ?></strong><div class="muted">@<?= e($row['username']) ?></div></td>
                <td><?= e($row['email']) ?></td>
                <td><?= (int) $row['is_admin'] === 1 ? '管理员' : '成员' ?></td>
                <td><span class="tiny-badge <?= (int) $row['is_active'] === 1 ? 'badge-ok' : 'badge-danger' ?>"><?= (int) $row['is_active'] === 1 ? '启用中' : '已停用' ?></span></td>
                <td><?= (int) $row['post_count'] ?></td>
                <td>
                  <?php if ((int) $row['id'] === (int) $user['id']): ?>
                    <span class="muted">当前管理员</span>
                  <?php else: ?>
                    <form method="post" class="inline-form">
                      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                      <input type="hidden" name="action" value="toggle_user_active">
                      <input type="hidden" name="user_id" value="<?= (int) $row['id'] ?>">
                      <input type="hidden" name="target_status" value="<?= (int) $row['is_active'] === 1 ? 0 : 1 ?>">
                      <button class="pill-btn <?= (int) $row['is_active'] === 1 ? 'danger' : 'solid' ?>" type="submit"><?= (int) $row['is_active'] === 1 ? '停用' : '启用' ?></button>
                    </form>
                  <?php endif; ?>
                </td>
              </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    </section>

    <section id="posts" class="glass panel-card admin-panel-card">
      <div class="section-kicker">Posts</div>
      <div class="side-head"><h3>帖子列表</h3></div>
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
                    <form method="post" class="inline-form" onsubmit="return confirm('确认从后台删除这篇帖子？');">
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

    <div class="nebula-section-grid admin-grid-two">
      <section id="categories" class="glass panel-card admin-panel-card">
        <div class="section-kicker">Categories</div>
        <div class="side-head"><h3>分类列表</h3></div>
        <div class="admin-table-wrap">
          <table class="admin-table compact-table">
            <thead><tr><th>ID</th><th>名称</th><th>Slug</th><th>版块数</th></tr></thead>
            <tbody>
              <?php foreach ($categoryRows as $row): ?>
                <tr>
                  <td>#<?= (int) $row['id'] ?></td>
                  <td><strong><?= e($row['name']) ?></strong><div class="muted"><?= e($row['description']) ?></div></td>
                  <td><?= e($row['slug']) ?></td>
                  <td><?= (int) $row['board_count'] ?></td>
                </tr>
              <?php endforeach; ?>
            </tbody>
          </table>
        </div>
      </section>

      <section id="boards" class="glass panel-card admin-panel-card">
        <div class="section-kicker">Boards</div>
        <div class="side-head"><h3>版块列表</h3></div>
        <div class="admin-table-wrap">
          <table class="admin-table compact-table">
            <thead><tr><th>ID</th><th>版块</th><th>分类</th><th>帖子数</th><th>颜色</th></tr></thead>
            <tbody>
              <?php foreach ($boardRows as $row): ?>
                <tr>
                  <td>#<?= (int) $row['id'] ?></td>
                  <td><strong><?= e($row['name']) ?></strong><div class="muted"><?= e($row['slug']) ?></div></td>
                  <td><?= e($row['category_name']) ?></td>
                  <td><?= (int) $row['post_count'] ?></td>
                  <td><span class="color-dot" style="background: <?= e($row['accent_color'] ?: '#77e7ff') ?>;"></span> <?= e($row['accent_color'] ?: '未设置') ?></td>
                </tr>
              <?php endforeach; ?>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </main>
<?php render_footer(); ?>
