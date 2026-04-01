<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$flash = flash_get();
$posts = db()->query(
    'SELECT p.id, p.user_id, p.title, p.content, p.image_path, p.created_at,
            u.nickname, u.username, u.avatar_path,
            COALESCE(l.like_count, 0) AS like_count,
            COALESCE(c.comment_count, 0) AS comment_count
     FROM posts p
     INNER JOIN pulsenest_users u ON u.id = p.user_id
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
     ) l ON l.post_id = p.id
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS comment_count FROM comments GROUP BY post_id
     ) c ON c.post_id = p.id
     ORDER BY p.created_at DESC, p.id DESC'
)->fetchAll();

$postCount = count($posts);
$authorCount = count(array_unique(array_map(static fn ($post) => $post['username'], $posts)));
$latestPost = $posts[0] ?? null;

render_header('PulseNest · 帖子列表', $user, [
    'searchText' => '🔎 搜索帖子标题、作者昵称、最近讨论',
]);
?>
  <main class="shell page-shell nebula-page-shell posts-page">
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>

    <section class="glass nebula-hero nebula-hero-split">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始01 · 内容流列表页</div>
        <h1>把全站帖子压进一条更像社区首页延展面的星云内容流。</h1>
        <p class="page-desc nebula-desc">这里现在除了实时读取帖子，还会把作者头像、帖子配图、点赞数、回复数一起带出来，让列表页更像真论坛内容流。</p>
        <div class="hero-actions-row">
          <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/register.php' ?>"><?= $user ? '写一篇新帖子' : '注册后参与讨论' ?></a>
          <a class="pill-btn" href="/">返回首页</a>
        </div>
        <div class="hero-stats compact-hero-stats">
          <div class="hero-stat"><div class="label">帖子总数</div><div class="num"><?= $postCount ?></div><div class="note">按发布时间倒序刷新</div></div>
          <div class="hero-stat"><div class="label">活跃作者</div><div class="num"><?= $authorCount ?></div><div class="note">当前列表内已出现的成员</div></div>
          <div class="hero-stat"><div class="label">当前身份</div><div class="num"><?= $user ? '已登录' : '访客' ?></div><div class="note"><?= $user ? '可直接发帖、点赞、评论' : '登录后可写入真实内容' ?></div></div>
        </div>
      </div>

      <aside class="glass side-card nebula-side-panel">
        <div class="section-kicker">Feed Snapshot</div>
        <div class="section-title">列表页速览</div>
        <div class="feed-list dense-feed-list">
          <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">实时数据</div><div class="text">帖子、点赞、评论都直接来自 MySQL 联表结果。</div></div></div>
          <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">互动入口</div><div class="text"><?= $user ? '你已具备发帖 / 点赞 / 评论权限。' : '访客可先注册 / 登录，再参与讨论。' ?></div></div></div>
          <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">最新帖子</div><div class="text"><?= e($latestPost['title'] ?? '还没有任何帖子，等第一篇把这里点亮。') ?></div></div></div>
        </div>
      </aside>
    </section>

    <section class="nebula-section-grid">
      <div class="list-stack posts-list-page">
        <?php if (!$posts): ?>
          <div class="glass panel-card empty-inline nebula-empty">现在还没有帖子，先去发布第一篇。</div>
        <?php else: ?>
          <?php foreach ($posts as $index => $post): ?>
            <article class="glass panel-card list-card nebula-list-card">
              <div class="list-card-topline">
                <span class="small-chip a">#<?= $index + 1 ?> 热度位</span>
                <span class="small-chip b"><?= e(human_time($post['created_at'])) ?></span>
              </div>
              <div class="post-head">
                <div class="user">
                  <?= render_avatar($post, 'user-avatar') ?>
                  <div>
                    <div class="user-name-line"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>"><?= e($post['nickname']) ?></a> <span class="tiny-badge">@<?= e($post['username']) ?></span></div>
                    <div class="muted" style="margin-top: 4px; font-size: 14px;">发布于 <?= e(substr($post['created_at'], 0, 16)) ?></div>
                  </div>
                </div>
                <a class="pill-btn" href="/post.php?id=<?= (int) $post['id'] ?>">查看详情</a>
              </div>
              <?php if (!empty($post['image_path'])): ?>
                <div class="post-cover-wrap"><img class="post-cover-image" src="<?= e(asset_url($post['image_path'])) ?>" alt="<?= e($post['title']) ?>"></div>
              <?php endif; ?>
              <h2 class="post-title small"><a href="/post.php?id=<?= (int) $post['id'] ?>"><?= e($post['title']) ?></a></h2>
              <p class="post-text compact"><?= nl2br(e(excerpt($post['content'], 220))) ?></p>
              <div class="list-card-footer">
                <div class="chips">
                  <span class="chip"><?= (int) $post['like_count'] ?> 赞</span>
                  <span class="chip"><?= (int) $post['comment_count'] ?> 回复</span>
                  <span class="chip">详情可跳转</span>
                </div>
                <a class="link" href="/post.php?id=<?= (int) $post['id'] ?>">继续阅读 →</a>
              </div>
            </article>
          <?php endforeach; ?>
        <?php endif; ?>
      </div>

      <aside class="right-col-stack">
        <section class="glass section-card">
          <div class="section-kicker">Board Signals</div>
          <div class="section-title">内容流状态</div>
          <div class="rank-list compact-rank-list">
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#1</div><div class="rank-main"><div class="rank-name">访问地址稳定</div><div class="meta">继续使用 /posts.php</div></div><div class="score">LIVE</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#2</div><div class="rank-main"><div class="rank-name">互动已接通</div><div class="meta">支持点赞、评论、回复</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#3</div><div class="rank-main"><div class="rank-name">视觉已统一</div><div class="meta">深色星云 + 玻璃卡 + 信息面板</div></div><div class="score">NEW</div></div></div>
          </div>
        </section>

        <section class="glass section-card">
          <div class="section-kicker">Quick Jump</div>
          <div class="quick-links">
            <a class="quick-link" href="<?= $user ? '/create-post.php' : '/login.php' ?>"><?= $user ? '直接去发帖' : '登录后发帖' ?></a>
            <a class="quick-link" href="/account.php">会员中心</a>
            <a class="quick-link" href="/">首页热榜</a>
          </div>
        </section>
      </aside>
    </section>
  </main>
<?php render_footer(); ?>
