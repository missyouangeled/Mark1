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
            actor.id AS actor_id, actor.nickname AS actor_nickname, actor.username AS actor_username, actor.avatar_path AS actor_avatar_path
     FROM notifications n
     INNER JOIN posts p ON p.id = n.post_id
     INNER JOIN pulsenest_users actor ON actor.id = n.actor_user_id
     WHERE n.recipient_user_id = :user_id
     ORDER BY n.created_at DESC, n.id DESC'
);
$stmt->execute(['user_id' => $user['id']]);
$notifications = $stmt->fetchAll();
$unreadCount = unread_notification_count((int) $user['id']);

render_header('PulseNest · 我的提醒', $user, [
    'searchText' => '🔎 回复提醒已接通，所有站内通知都在这里聚合',
]);
?>
<main class="shell page-shell nebula-page-shell notifications-page">
  <?php if ($flash): ?>
    <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
  <?php endif; ?>

  <section class="glass nebula-hero nebula-hero-split">
    <div class="nebula-copy">
      <div class="brand-chip">纳达尔星项目 · 星云初始01 · 站内提醒</div>
      <h1>别人回复了你的帖子或评论，都会在这里留下站内通知。</h1>
      <p class="page-desc nebula-desc">这一版先做最小可用通知：只处理“有人回复了我的帖子 / 评论”。但链路已经完整打通，可读、可跳转、可标记已读。</p>
      <div class="hero-stats compact-hero-stats">
        <div class="hero-stat"><div class="label">未读提醒</div><div class="num"><?= $unreadCount ?></div><div class="note">头部也会同步显示数量</div></div>
        <div class="hero-stat"><div class="label">总提醒</div><div class="num"><?= count($notifications) ?></div><div class="note">全部按时间倒序聚合</div></div>
        <div class="hero-stat"><div class="label">触发范围</div><div class="num small-num">帖子 / 评论</div><div class="note">当前仅聚焦回复提醒</div></div>
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
      </div>
    </aside>
  </section>

  <section class="glass panel-card">
    <div class="section-kicker">Notification Feed</div>
    <div class="side-head"><h3>提醒列表</h3></div>
    <div class="list-stack notification-stack">
      <?php if (!$notifications): ?>
        <div class="empty-inline nebula-empty">还没有任何提醒。等别人回复你的帖子或评论，这里就会亮起来。</div>
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
                  <div class="muted"><?= e(human_time($item['created_at'])) ?></div>
                </div>
              </div>
              <span class="small-chip <?= (int) $item['is_read'] === 0 ? 'a' : 'b' ?>"><?= (int) $item['is_read'] === 0 ? '未读' : '已读' ?></span>
            </div>
            <div class="comment-body">
              <?php if ($item['type'] === 'comment_reply'): ?>
                回复了你的评论：
              <?php else: ?>
                回复了你的帖子：
              <?php endif; ?>
              <a class="inline-link" href="/post.php?id=<?= (int) $item['post_id'] ?>"><?= e($item['title']) ?></a>
            </div>
          </article>
        <?php endforeach; ?>
      <?php endif; ?>
    </div>
  </section>
</main>
<?php render_footer(); ?>