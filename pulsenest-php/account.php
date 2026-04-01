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

render_header('PulseNest · 会员中心', $user, [
    'searchText' => '🔎 搜索我的帖子、账号动作、社区入口',
]);
?>
  <main class="shell page-shell nebula-page-shell account-page">
    <section class="glass nebula-hero nebula-hero-split member-hero nebula-member-hero">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始01 · 会员中心</div>
        <h1>欢迎回来，<?= e($user['nickname']) ?>，你的社区身份卡已经并入星云主壳。</h1>
        <p class="page-desc nebula-desc">会员中心继续保留原本登录保护、数据统计和快捷入口，但信息编排更靠近首页：先看状态，再决定继续发帖、回内容流或处理账号动作。</p>
        <div class="hero-actions-row">
          <a class="pill-btn solid" href="/create-post.php">写一篇新帖子</a>
          <a class="pill-btn" href="/posts.php">查看全部帖子</a>
        </div>
      </div>

      <aside class="profile-chip nebula-profile-chip">
        <div class="user-avatar large"></div>
        <div>
          <strong><?= e($user['nickname']) ?></strong>
          <span>@<?= e($user['username']) ?></span>
          <span><?= e($user['email']) ?></span>
          <span>加入时间：<?= e(substr((string) $user['created_at'], 0, 16)) ?></span>
        </div>
      </aside>
    </section>

    <section class="stat-grid page-grid-three nebula-stat-grid">
      <div class="glass stat-card"><strong><?= $postCount ?></strong><span>我的帖子</span></div>
      <div class="glass stat-card"><strong><?= $memberCount ?></strong><span>社区成员</span></div>
      <div class="glass stat-card"><strong><?= $totalPosts ?></strong><span>全站内容</span></div>
    </section>

    <div class="nebula-section-grid account-grid">
      <div class="right-col-stack">
        <section class="glass panel-card">
          <div class="section-kicker">Member Data</div>
          <div class="side-head"><h3>当前用户信息</h3></div>
          <div class="detail-list">
            <div class="detail-row"><span>昵称</span><strong><?= e($user['nickname']) ?></strong></div>
            <div class="detail-row"><span>用户名</span><strong>@<?= e($user['username']) ?></strong></div>
            <div class="detail-row"><span>邮箱</span><strong><?= e($user['email']) ?></strong></div>
            <div class="detail-row"><span>加入时间</span><strong><?= e(substr((string) $user['created_at'], 0, 16)) ?></strong></div>
          </div>
        </section>

        <section class="glass panel-card">
          <div class="section-kicker">My Recent Posts</div>
          <div class="side-head"><h3>我最近发布的内容</h3></div>
          <?php if (!$latestPosts): ?>
            <div class="empty-inline nebula-empty">你还没有发帖，先去写第一篇吧。</div>
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

      <aside class="right-col-stack">
        <section class="glass panel-card">
          <div class="section-kicker">Quick Actions</div>
          <div class="quick-links">
            <a class="quick-link" href="/create-post.php">写一篇新帖子</a>
            <a class="quick-link" href="/posts.php">查看全部帖子</a>
            <a class="quick-link" href="/forgot-password.php">发起密码重置</a>
            <a class="quick-link" href="/">返回首页内容流</a>
          </div>
        </section>

        <section class="glass section-card">
          <div class="section-kicker">Member Status</div>
          <div class="rank-list compact-rank-list">
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#1</div><div class="rank-main"><div class="rank-name">登录保护</div><div class="meta">未登录仍会跳转到 /login.php</div></div><div class="score">SAFE</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#2</div><div class="rank-main"><div class="rank-name">数据同步</div><div class="meta">统计数字实时读取数据库</div></div><div class="score">LIVE</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#3</div><div class="rank-main"><div class="rank-name">入口完整</div><div class="meta">发帖 / 浏览 / 找回密码 / 回首页</div></div><div class="score">OK</div></div></div>
          </div>
        </section>
      </aside>
    </div>
  </main>
<?php render_footer(); ?>