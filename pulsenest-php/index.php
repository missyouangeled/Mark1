<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$flash = flash_get();

$postCount = (int) db()->query('SELECT COUNT(*) FROM posts')->fetchColumn();
$userCount = (int) db()->query('SELECT COUNT(*) FROM pulsenest_users')->fetchColumn();

$posts = db()->query(
    'SELECT p.id, p.title, p.content, p.created_at, u.nickname, u.username
     FROM posts p
     INNER JOIN pulsenest_users u ON u.id = p.user_id
     ORDER BY p.created_at DESC, p.id DESC
     LIMIT 12'
)->fetchAll();

render_header('PulseNest', $user);
?>
  <div class="shell layout">
    <aside class="left">
      <div class="sticky-col">
        <div class="left-section">
          <div class="menu-list">
            <a class="menu-item" href="/"><span class="icon">T</span><span>首页</span></a>
            <a class="menu-item" href="/posts.php"><span class="icon">榜</span><span>帖子列表</span></a>
            <a class="menu-item" href="/create-post.php"><span class="icon">发</span><span>发布帖子</span></a>
            <a class="menu-item" href="/account.php"><span class="icon">我</span><span>会员中心</span></a>
            <a class="menu-item" href="/forgot-password.php"><span class="icon">锁</span><span>找回密码</span></a>
          </div>
        </div>
        <div class="left-section">
          <h4 class="side-title">热门分区</h4>
          <div class="forum-list">
            <a class="forum-item active" href="/posts.php"><span class="icon">热</span><span>精选内容流</span></a>
            <a class="forum-item" href="/create-post.php"><span class="icon">新</span><span>发布你的发现</span></a>
            <a class="forum-item" href="/account.php"><span class="icon">会</span><span>会员中心</span></a>
          </div>
        </div>
      </div>
    </aside>

    <main class="center">
      <?php if ($flash): ?>
        <div class="notice <?= e($flash['type']) ?>"><?= e($flash['message']) ?></div>
      <?php endif; ?>

      <section class="card hero-card">
        <div class="hero-banner">
          <div class="hero-top">
            <div class="hero-brand">
              <div class="hero-brand-mark">PN</div>
              <div>
                <div style="font-size: 34px; font-weight: 800; line-height: 1.08;">PulseNest</div>
                <div style="margin-top: 8px; color: rgba(255,255,255,0.74);">灵感社区站 · <?= $userCount ?> 位成员 · <?= $postCount ?> 篇帖子</div>
              </div>
            </div>
            <a class="follow-btn" href="<?= $user ? '/create-post.php' : '/register.php' ?>"><?= $user ? '开始分享' : '立即加入' ?></a>
          </div>
        </div>
        <div class="quick-icons">
          <a class="quick-icon" href="/posts.php"><div class="bubble">📚</div>最新帖子</a>
          <a class="quick-icon" href="/create-post.php"><div class="bubble">📝</div>发图文</a>
          <a class="quick-icon" href="/account.php"><div class="bubble">👤</div>会员中心</a>
          <a class="quick-icon" href="/forgot-password.php"><div class="bubble">🔐</div>重置密码</a>
          <a class="quick-icon" href="/register.php"><div class="bubble">✨</div>加入社区</a>
        </div>
        <div class="tabs">
          <div class="tab active">全部</div>
          <a class="tab" href="/posts.php">最新</a>
          <a class="tab" href="/create-post.php">发布</a>
          <a class="tab" href="/account.php">我的</a>
        </div>
        <div class="topics">
          <div class="topic-row">
            <span class="topic-chip">帮助中心</span>
            <span class="topic-chip">官方公告</span>
            <span class="topic-chip">最新活动</span>
            <span class="topic-chip">玩家说</span>
            <span class="topic-chip">组队招募</span>
          </div>

          <?php if (!$posts): ?>
            <article class="post empty-state">
              <h2 class="post-title">内容流还很新，等你来发第一篇。</h2>
              <p class="post-text">数据库已经接通，本地可以直接发帖、看列表、看详情。如果你已经登录，现在就能发布第一条内容。</p>
            </article>
          <?php else: ?>
            <?php foreach ($posts as $post): ?>
              <article class="post">
                <div class="post-head">
                  <div class="user">
                    <div class="user-avatar"></div>
                    <div>
                      <div style="font-weight: 700;"><?= e($post['nickname']) ?></div>
                      <div class="muted" style="margin-top: 4px; font-size: 14px;">@<?= e($post['username']) ?> · <?= e(human_time($post['created_at'])) ?></div>
                    </div>
                  </div>
                  <a class="muted" href="/post.php?id=<?= (int) $post['id'] ?>">查看详情</a>
                </div>
                <h2 class="post-title"><a href="/post.php?id=<?= (int) $post['id'] ?>"><?= e($post['title']) ?></a></h2>
                <p class="post-text"><?= nl2br(e(excerpt($post['content'], 180))) ?></p>
                <div class="post-actions"><span>🧾 来自数据库</span><span>👀 可查看详情</span><span><a href="/post.php?id=<?= (int) $post['id'] ?>">↗ 继续阅读</a></span></div>
              </article>
            <?php endforeach; ?>
          <?php endif; ?>
        </div>
      </section>
    </main>

    <aside class="right">
      <div class="sticky-col side-stack">
        <section class="card side-card">
          <div class="side-head"><h3>发布到论坛</h3></div>
          <div class="tool-grid">
            <a class="tool-item" href="/create-post.php"><div class="tool-bubble">🖼️</div>发图文</a>
            <a class="tool-item" href="/posts.php"><div class="tool-bubble">🎬</div>看帖子</a>
            <a class="tool-item" href="/account.php"><div class="tool-bubble">📄</div>会员页</a>
            <a class="tool-item" href="/forgot-password.php"><div class="tool-bubble">🗓️</div>找回密码</a>
          </div>
        </section>
        <section class="card side-card">
          <div class="side-head"><h3>社区概况</h3><span class="muted">实时</span></div>
          <div class="stat-grid compact">
            <div class="mini-stat"><strong><?= $postCount ?></strong><span>总帖子</span></div>
            <div class="mini-stat"><strong><?= $userCount ?></strong><span>总成员</span></div>
          </div>
        </section>
        <section class="card side-card">
          <div class="side-head"><h3>现在适合做什么</h3></div>
          <div class="mod-list">
            <div class="info-line">1. 注册后会自动登录并回到首页</div>
            <div class="info-line">2. 会员中心可看个人资料和统计</div>
            <div class="info-line">3. 忘记密码支持 token 流程完整走通</div>
          </div>
        </section>
      </div>
    </aside>
  </div>
<?php render_footer(); ?>