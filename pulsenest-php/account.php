<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();

$stmt = db()->prepare('SELECT COUNT(*) FROM posts WHERE user_id = :id');
$stmt->execute(['id' => $user['id']]);
$postCount = (int) $stmt->fetchColumn();
$totalPosts = (int) db()->query('SELECT COUNT(*) FROM posts')->fetchColumn();
$memberCount = (int) db()->query('SELECT COUNT(*) FROM pulsenest_users')->fetchColumn();
$latestPostsStmt = db()->prepare('SELECT id, title, created_at FROM posts WHERE user_id = :id ORDER BY created_at DESC, id DESC LIMIT 5');
$latestPostsStmt->execute(['id' => $user['id']]);
$latestPosts = $latestPostsStmt->fetchAll();

render_header('PulseNest · 会员中心', $user);
?>
  <div class="shell page-shell">
    <section class="card page-hero member-hero">
      <div>
        <div class="kicker">Member Center</div>
        <h1>欢迎回来，<?= e($user['nickname']) ?></h1>
        <p class="page-desc">这里是你的会员中心：看资料、看发帖数据，也能快速回到发布和内容浏览。</p>
      </div>
      <div class="profile-chip">
        <div class="user-avatar large"></div>
        <div>
          <strong><?= e($user['nickname']) ?></strong>
          <span>@<?= e($user['username']) ?></span>
          <span><?= e($user['email']) ?></span>
        </div>
      </div>
    </section>

    <section class="stat-grid page-grid-three">
      <div class="card stat-card"><strong><?= $postCount ?></strong><span>我的帖子</span></div>
      <div class="card stat-card"><strong><?= $memberCount ?></strong><span>社区成员</span></div>
      <div class="card stat-card"><strong><?= $totalPosts ?></strong><span>全站内容</span></div>
    </section>

    <div class="page-grid-two">
      <section class="card panel-card">
        <div class="side-head"><h3>当前用户信息</h3></div>
        <div class="detail-list">
          <div class="detail-row"><span>昵称</span><strong><?= e($user['nickname']) ?></strong></div>
          <div class="detail-row"><span>用户名</span><strong>@<?= e($user['username']) ?></strong></div>
          <div class="detail-row"><span>邮箱</span><strong><?= e($user['email']) ?></strong></div>
          <div class="detail-row"><span>加入时间</span><strong><?= e(substr((string) $user['created_at'], 0, 16)) ?></strong></div>
        </div>
      </section>

      <section class="card panel-card">
        <div class="side-head"><h3>快捷入口</h3></div>
        <div class="quick-links">
          <a class="quick-link" href="/create-post.php">写一篇新帖子</a>
          <a class="quick-link" href="/posts.php">查看全部帖子</a>
          <a class="quick-link" href="/forgot-password.php">发起密码重置</a>
          <a class="quick-link" href="/">返回首页内容流</a>
        </div>
      </section>
    </div>

    <section class="card panel-card">
      <div class="side-head"><h3>我最近发布的内容</h3></div>
      <?php if (!$latestPosts): ?>
        <div class="empty-inline">你还没有发帖，先去写第一篇吧。</div>
      <?php else: ?>
        <div class="list-stack">
          <?php foreach ($latestPosts as $post): ?>
            <a class="list-item" href="/post.php?id=<?= (int) $post['id'] ?>">
              <strong><?= e($post['title']) ?></strong>
              <span><?= e(human_time($post['created_at'])) ?></span>
            </a>
          <?php endforeach; ?>
        </div>
      <?php endif; ?>
    </section>
  </div>
<?php render_footer(); ?>