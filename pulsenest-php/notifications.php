<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = trim((string) ($_POST['action'] ?? 'mark_all_read'));
    $filterType = trim((string) ($_POST['filter_type'] ?? ''));
    $allowedTypes = ['post_reply', 'comment_reply', 'post_like', 'comment_like', 'comment_moderated'];
    if ($filterType !== '' && !in_array($filterType, $allowedTypes, true)) {
        $filterType = '';
    }

    if ($action === 'mark_all_read') {
        db()->prepare('UPDATE notifications SET is_read = 1 WHERE recipient_user_id = :user_id AND is_read = 0')->execute([
            'user_id' => $user['id'],
        ]);
        flash_set('success', '已将当前账号下所有提醒标记为已读。');
    } elseif ($action === 'mark_filtered_read') {
        $sql = 'UPDATE notifications SET is_read = 1 WHERE recipient_user_id = :user_id AND is_read = 0';
        $params = ['user_id' => $user['id']];
        if ($filterType !== '') {
            $sql .= ' AND type = :type';
            $params['type'] = $filterType;
        }
        db()->prepare($sql)->execute($params);
        flash_set('success', $filterType !== '' ? '已将该类型未读提醒全部标为已读。' : '已将当前筛选结果中的未读提醒标为已读。');
    } elseif ($action === 'clear_type') {
        if ($filterType === '') {
            flash_set('error', '清空某一类提醒前，请先选择提醒类型。');
        } else {
            db()->prepare('DELETE FROM notifications WHERE recipient_user_id = :user_id AND type = :type')->execute([
                'user_id' => $user['id'],
                'type' => $filterType,
            ]);
            flash_set('success', '已清空“' . notification_type_label($filterType) . '”提醒。');
        }
    }

    $redirectQuery = [];
    if (!empty($_POST['redirect_only_unread'])) {
        $redirectQuery['unread'] = '1';
    }
    if ($filterType !== '') {
        $redirectQuery['type'] = $filterType;
    }
    $redirect = '/notifications.php';
    if ($redirectQuery) {
        $redirect .= '?' . http_build_query($redirectQuery);
    }
    redirect_to($redirect);
}

$flash = flash_get();
$selectedType = trim((string) ($_GET['type'] ?? ''));
$onlyUnread = (int) ($_GET['unread'] ?? 0) === 1;
$allowedTypes = ['post_reply', 'comment_reply', 'post_like', 'comment_like', 'comment_moderated'];
if ($selectedType !== '' && !in_array($selectedType, $allowedTypes, true)) {
    $selectedType = '';
}

$where = ['n.recipient_user_id = :user_id'];
$params = ['user_id' => $user['id']];
if ($selectedType !== '') {
    $where[] = 'n.type = :type';
    $params['type'] = $selectedType;
}
if ($onlyUnread) {
    $where[] = 'n.is_read = 0';
}

$stmt = db()->prepare(
    'SELECT n.id, n.type, n.is_read, n.created_at,
            p.id AS post_id, p.title,
            c.content AS comment_content,
            actor.id AS actor_id, actor.nickname AS actor_nickname, actor.username AS actor_username, actor.avatar_path AS actor_avatar_path
     FROM notifications n
     INNER JOIN posts p ON p.id = n.post_id
     LEFT JOIN comments c ON c.id = n.comment_id
     INNER JOIN pulsenest_users actor ON actor.id = n.actor_user_id
     WHERE ' . implode(' AND ', $where) . '
     ORDER BY n.created_at DESC, n.id DESC'
);
$stmt->execute($params);
$notifications = $stmt->fetchAll();
$unreadCount = unread_notification_count((int) $user['id']);

$typeRowsStmt = db()->prepare(
    'SELECT type, COUNT(*) AS total_count, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread_count
     FROM notifications
     WHERE recipient_user_id = :user_id
     GROUP BY type
     ORDER BY total_count DESC, type ASC'
);
$typeRowsStmt->execute(['user_id' => $user['id']]);
$typeRows = $typeRowsStmt->fetchAll();

$todayStmt = db()->prepare('SELECT COUNT(*) FROM notifications WHERE recipient_user_id = :user_id AND created_at >= NOW() - INTERVAL 1 DAY');
$todayStmt->execute(['user_id' => $user['id']]);
$todayCount = (int) $todayStmt->fetchColumn();

$weekStmt = db()->prepare('SELECT COUNT(*) FROM notifications WHERE recipient_user_id = :user_id AND created_at >= NOW() - INTERVAL 7 DAY');
$weekStmt->execute(['user_id' => $user['id']]);
$weekCount = (int) $weekStmt->fetchColumn();

$currentResultCount = count($notifications);
render_header('PulseNest · 我的提醒', $user, [
    'searchText' => '🔎 提醒支持未读筛选、类型筛选、批量已读和按类型清空',
]);
?>
<main class="shell page-shell nebula-page-shell notifications-page">
  <?php if ($flash): ?>
    <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
  <?php endif; ?>

  <section class="glass nebula-hero nebula-hero-split">
    <div class="nebula-copy">
      <div class="brand-chip">纳达尔星项目 · 星云初始01 · 站内提醒</div>
      <h1>提醒流继续细化：未读、类型、批量已读、按类型清空，都能自己收拾。</h1>
      <p class="page-desc nebula-desc">通知系统现在不只会聚合回复 / 帖子点赞 / 评论点赞，还能按未读和类型筛选；如果某一类提醒太密，也能直接按类型批量标已读或清空。</p>
      <div class="hero-stats compact-hero-stats">
        <div class="hero-stat"><div class="label">未读提醒</div><div class="num"><?= $unreadCount ?></div><div class="note">头部导航同步显示</div></div>
        <div class="hero-stat"><div class="label">当前结果</div><div class="num"><?= $currentResultCount ?></div><div class="note"><?= $onlyUnread ? '当前仅看未读' : '当前为全部状态' ?></div></div>
        <div class="hero-stat"><div class="label">24 小时</div><div class="num"><?= $todayCount ?></div><div class="note">最近一天新增提醒</div></div>
        <div class="hero-stat"><div class="label">7 天</div><div class="num"><?= $weekCount ?></div><div class="note">最近七天互动节奏</div></div>
      </div>
    </div>
    <aside class="glass side-card nebula-side-panel">
      <div class="section-kicker">Quick Action</div>
      <form method="get" class="form compact-form">
        <input type="hidden" name="type" value="<?= e($selectedType) ?>">
        <label class="muted"><input type="checkbox" name="unread" value="1" <?= $onlyUnread ? 'checked' : '' ?>> 只看未读</label>
        <button class="submit" type="submit">应用筛选</button>
      </form>
      <form method="post" class="form compact-form">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <input type="hidden" name="action" value="mark_all_read">
        <button class="submit" type="submit">全部标记为已读</button>
      </form>
      <div class="quick-links compact-link-stack">
        <a class="quick-link" href="/posts.php">去看帖子流</a>
        <a class="quick-link" href="/create-post.php">继续发帖</a>
        <a class="quick-link" href="/account.php">回会员中心</a>
      </div>
    </aside>
  </section>

  <section class="glass panel-card admin-panel-card">
    <div class="section-kicker">Filter</div>
    <div class="side-head admin-head-row"><h3>提醒筛选与批量操作</h3><span class="muted">先筛，再一键处理当前类型。</span></div>
    <form class="admin-filter-row" method="get" action="/notifications.php">
      <select class="input admin-filter-input" name="type">
        <option value="">全部类型</option>
        <?php foreach ($allowedTypes as $type): ?>
          <option value="<?= e($type) ?>" <?= $selectedType === $type ? 'selected' : '' ?>><?= e(notification_type_label($type)) ?></option>
        <?php endforeach; ?>
      </select>
      <label class="muted"><input type="checkbox" name="unread" value="1" <?= $onlyUnread ? 'checked' : '' ?>> 只看未读</label>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="/notifications.php">清空</a>
    </form>
    <div class="admin-bulk-bar">
      <form method="post" class="inline-form">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <input type="hidden" name="action" value="mark_filtered_read">
        <input type="hidden" name="filter_type" value="<?= e($selectedType) ?>">
        <input type="hidden" name="redirect_only_unread" value="<?= $onlyUnread ? '1' : '0' ?>">
        <button class="pill-btn solid" type="submit">将当前筛选结果设为已读</button>
      </form>
      <form method="post" class="inline-form" onsubmit="return confirm('确认清空当前所选类型的全部通知？此操作不可撤销。');">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <input type="hidden" name="action" value="clear_type">
        <input type="hidden" name="filter_type" value="<?= e($selectedType) ?>">
        <input type="hidden" name="redirect_only_unread" value="<?= $onlyUnread ? '1' : '0' ?>">
        <button class="pill-btn danger" type="submit" <?= $selectedType === '' ? 'disabled' : '' ?>>清空当前类型</button>
      </form>
    </div>
  </section>

  <section class="glass panel-card admin-panel-card">
    <div class="section-kicker">Type Snapshot</div>
    <div class="side-head admin-head-row"><h3>提醒类型分布</h3><span class="muted">你能快速看出最近更多是被回复，还是被点赞。</span></div>
    <div class="admin-table-wrap">
      <table class="admin-table compact-table">
        <thead><tr><th>类型</th><th>总量</th><th>未读</th><th>说明</th></tr></thead>
        <tbody>
          <?php foreach ($typeRows as $row): ?>
            <tr>
              <td><span class="tiny-badge"><?= e(notification_type_label($row['type'])) ?></span><div class="muted"><?= e($row['type']) ?></div></td>
              <td><?= (int) $row['total_count'] ?></td>
              <td><?= (int) $row['unread_count'] ?></td>
              <td><?= e(match ($row['type']) {
                'post_like' => '有人点赞你的帖子',
                'comment_like' => '有人点赞你的评论',
                'comment_reply' => '有人回复你的评论',
                'comment_moderated' => '你的评论被审核通过或隐藏时通知',
                default => '有人回复你的帖子',
              }) ?></td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$typeRows): ?>
            <tr><td colspan="4" class="muted">还没有任何提醒统计，等第一波互动来点亮这里。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
  </section>

  <section class="glass panel-card">
    <div class="section-kicker">Notification Feed</div>
    <div class="side-head"><h3>提醒列表</h3></div>
    <div class="list-stack notification-stack">
      <?php if (!$notifications): ?>
        <div class="empty-inline nebula-empty">当前筛选条件下没有提醒。换个类型，或者等下一次互动把这里点亮。</div>
      <?php else: ?>
        <?php foreach ($notifications as $item): ?>
          <article class="notification-card <?= (int) $item['is_read'] === 0 ? 'unread' : '' ?>">
            <div class="post-head">
              <div class="user">
                <?= render_avatar([
                  'avatar_path' => $item['actor_avatar_path'],
                  'nickname' => $item['actor_nickname'],
                  'username' => $item['actor_username'],
                ], 'user-avatar') ?>
                <div>
                  <div class="user-name-line"><?= e($item['actor_nickname']) ?> <span class="tiny-badge">@<?= e($item['actor_username']) ?></span></div>
                  <div class="muted"><?= e(human_time($item['created_at'])) ?> · <?= e(notification_type_label($item['type'])) ?></div>
                </div>
              </div>
              <span class="small-chip <?= (int) $item['is_read'] === 0 ? 'a' : 'b' ?>"><?= (int) $item['is_read'] === 0 ? '未读' : '已读' ?></span>
            </div>
            <div class="comment-body">
              <?= e(match ($item['type']) {
                'comment_reply' => '回复了你的评论：',
                'post_like' => '点赞了你的帖子：',
                'comment_like' => '点赞了你在这篇帖子下的评论：',
                'comment_moderated' => '你的评论审核状态已更新，关联帖子：',
                default => '回复了你的帖子：',
              }) ?>
              <a class="inline-link" href="/post.php?id=<?= (int) $item['post_id'] ?>"><?= e($item['title']) ?></a>
            </div>
            <?php if (!empty($item['comment_content'])): ?>
              <div class="muted">关联评论：<?= e(excerpt($item['comment_content'], 72)) ?></div>
            <?php endif; ?>
          </article>
        <?php endforeach; ?>
      <?php endif; ?>
    </div>
  </section>
</main>
<?php render_footer(); ?>
