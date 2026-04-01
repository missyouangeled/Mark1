<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$postId = (int) ($_GET['id'] ?? 0);
$stmt = db()->prepare(
    'SELECT p.id, p.title, p.content, p.created_at, u.nickname, u.username, u.email
     FROM posts p
     INNER JOIN pulsenest_users u ON u.id = p.user_id
     WHERE p.id = :id
     LIMIT 1'
);
$stmt->execute(['id' => $postId]);
$post = $stmt->fetch();

if (!$post) {
    http_response_code(404);
}

render_header('PulseNest · 帖子详情', $user, [
    'searchText' => '🔎 搜索详情上下文、作者、返回相关帖子',
]);
?>
  <main class="shell page-shell nebula-page-shell narrow-post-shell">
    <?php if (!$post): ?>
      <section class="glass panel-card empty-inline nebula-empty">没有找到这篇帖子。<a class="link" href="/posts.php">返回帖子列表</a></section>
    <?php else: ?>
      <section class="glass nebula-hero detail-hero">
        <div class="detail-hero-head">
          <div>
            <div class="brand-chip">纳达尔星项目 · 星云初始01 · 帖子详情页</div>
            <h1><?= e($post['title']) ?></h1>
            <p class="page-desc nebula-desc">详情页继续保留真实内容、作者和发布时间，同时把布局升级成更沉浸的文章展示面。</p>
          </div>
          <div class="hero-actions-row detail-hero-actions">
            <a class="pill-btn" href="/posts.php">返回列表</a>
            <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/login.php' ?>"><?= $user ? '继续发帖' : '登录后发帖' ?></a>
          </div>
        </div>
        <div class="hero-stats compact-hero-stats detail-stats">
          <div class="hero-stat"><div class="label">作者</div><div class="num small-num"><?= e($post['nickname']) ?></div><div class="note">@<?= e($post['username']) ?></div></div>
          <div class="hero-stat"><div class="label">发布时间</div><div class="num small-num"><?= e(substr($post['created_at'], 0, 16)) ?></div><div class="note"><?= e(human_time($post['created_at'])) ?></div></div>
          <div class="hero-stat"><div class="label">查看状态</div><div class="num small-num"><?= $user ? '已同步登录态' : '访客浏览中' ?></div><div class="note"><?= $user ? '可回帖链路继续扩展' : '登录后可继续参与内容链路' ?></div></div>
        </div>
      </section>

      <div class="nebula-section-grid detail-grid">
        <article class="glass detail-card nebula-detail-card">
          <div class="post-head">
            <div class="user">
              <div class="user-avatar large"></div>
              <div>
                <div class="user-name-line"><?= e($post['nickname']) ?> <span class="tiny-badge">@<?= e($post['username']) ?></span></div>
                <div class="muted" style="margin-top: 6px; font-size: 14px;">发布于 <?= e(substr($post['created_at'], 0, 16)) ?></div>
              </div>
            </div>
            <span class="small-chip a">文章详情</span>
          </div>
          <div class="article-meta">发布邮箱：<?= e($post['email']) ?></div>
          <div class="article-body"><?= nl2br(e($post['content'])) ?></div>
        </article>

        <aside class="right-col-stack">
          <section class="glass section-card">
            <div class="section-kicker">Author Snapshot</div>
            <div class="author-item detail-author-card">
              <div class="author-row"><div class="author-badge">🌌</div><div class="author-main"><div class="author-name"><?= e($post['nickname']) ?></div><div class="meta">@<?= e($post['username']) ?></div></div><div class="score">LIVE</div></div>
              <p>这篇帖子已在详情页完整展开；发帖成功后会先跳到这里，再能回到列表继续查看。</p>
            </div>
          </section>

          <section class="glass section-card">
            <div class="section-kicker">Quick Jump</div>
            <div class="quick-links">
              <a class="quick-link" href="/posts.php">返回帖子列表</a>
              <a class="quick-link" href="/account.php">会员中心</a>
              <a class="quick-link" href="/">回首页热榜</a>
            </div>
          </section>
        </aside>
      </div>
    <?php endif; ?>
  </main>
<?php render_footer(); ?>