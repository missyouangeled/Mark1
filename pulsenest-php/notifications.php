<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    db()->prepare('UPDATE notifications SET is_read = 1 WHERE recipient_user_id = :user_id AND is_read = 0')->execute([
        'user_id' => $user['id'],
    ]);
    flash_set('success', '已将所有提醒标记为已读。');
    redirect_to('/notifications.php');
}

$flash = flash_get();
$stmt = db()->prepare(
    'SELECT n.id, n.type, n.is_read, n.created_at,
            p.id AS post_id, p.title,
            c.content AS comment_content,
            actor.id AS actor_id, actor.nickname AS actor_nickname, actor.username AS actor_username, actor.avatar_path AS actor_avatar_path
     FROM notifications n
     INNER JOIN posts p ON p.id = n.post_id
     LEFT JOIN comments c ON c.id = n.comment_id
     INNER JOIN pulsenest_users actor ON actor.id = n.actor_user_id
     WHERE n.recipient_user_id = :user_id
     ORDER BY n.created_at DESC, n.id DESC'
);
$stmt->execute(['user_id' => $user['id']]);
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

render_header('PulseNest · 我的提醒', $user, [
    'searchText' => '🔎 回复 / 帖子点赞 / 评论点赞提醒都在这里聚合',
]);
?>
<main class="shell page-shell nebula-page-shell notifications-page">
  <?php if ($flash): ?>
    <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
  <?php endif; ?>

  <section class="glass nebula-hero nebula-hero-split">
    <div class="nebula-copy">
      <div class="brand-chip">纳达尔星项目 · 星云初始01 · 站内提醒</div>
      <h1>回复、帖子点赞、评论点赞，都会在这里汇成一条可回看的提醒流。</h1>
      <p class="page-desc nebula-desc">通知系统已经从“只有回复提醒”升级到多类型提醒：现在不只是别人回帖 / 回复评论，有人点赞你的帖子或评论，也会在这里出现，并保留未读状态与类型分布。</p>
      <div class="hero-stats compact-hero-stats">
        <div class="hero-stat"><div class="label">未读提醒</div><div class="num"><?= $unreadCount ?></div><div class="note">头部导航同步显示</div></div>
        <div class="hero-stat"><div class="label">24 小时</div><div class="num"><?= $todayCount ?></div><div class="note">最近一天新增提醒</div></div>
        <div class="hero-stat"><div class="label">7 天</div><div class="num"><?= $weekCount ?></div><div class="note">最近七天互动节奏</div></div>
      </div>
    </div>
    <aside class="glass side-card nebula-side-panel">
      <div class="section-kicker">Quick Action</div>
      <form method="post" class="form compact-form">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
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
        <div class="empty-inline nebula-empty">还没有任何提醒。等别人回复或点赞你的内容，这里就会亮起来。</div>
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
