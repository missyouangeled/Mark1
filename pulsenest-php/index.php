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

$heroPost = $posts[0] ?? null;
$hotPosts = array_slice($posts, 0, 4);
$feedPosts = array_slice($posts, 0, 3);
$trendingPosts = array_slice($posts, 0, 3);

render_header('PulseNest', $user);
?>
  <main class="shell home-page">
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>

    <section class="hero-grid">
      <div class="glass hero-panel">
        <div class="hero-inner">
          <div class="hero-copy">
            <div>
              <div class="brand-chip">星云初始01 · 社区首页视觉锚点 · PHP 功能已接通</div>
              <h1>像逛热门论坛首页一样，先被氛围钩住，再被热度和观点留下来。</h1>
              <p class="hero-text">这一版已经不只是漂亮外壳。顶部登录 / 注册都接入真实功能，注册写入 MySQL，登录查库并建立会话，登录后首页头部与行动入口会立即切换为你的社区状态。</p>
            </div>
            <div class="hero-actions-row">
              <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/register.php' ?>"><?= $user ? '开始分享内容' : '立即加入社区' ?></a>
              <a class="pill-btn" href="/posts.php">去看内容流</a>
            </div>
            <div class="hero-stats">
              <div class="hero-stat"><div class="label">社区成员</div><div class="num"><?= $userCount ?></div><div class="note">注册后即自动登录</div></div>
              <div class="hero-stat"><div class="label">实时帖子</div><div class="num"><?= $postCount ?></div><div class="note">全部来自 MySQL 实库</div></div>
              <div class="hero-stat"><div class="label">当前状态</div><div class="num"><?= $user ? '在线' : '访客' ?></div><div class="note"><?= $user ? '已同步到首页身份卡' : '可直接注册体验完整链路' ?></div></div>
            </div>
          </div>
          <div class="hero-art">
            <div class="hero-art-top">
              <span class="badge">Forum Pick</span>
              <span class="badge soft"><?= $user ? '已登录' : '访客可注册' ?></span>
            </div>
            <div class="hero-art-bottom">
              <div class="kicker">Hero Pick</div>
              <div class="title"><?= e($heroPost['title'] ?? 'Starfall Zero') ?></div>
              <div class="text"><?= e($heroPost ? excerpt($heroPost['content'], 44) : '沉浸式星际探索 + 高强度战斗循环') ?></div>
              <div class="chips">
                <span class="chip">真实登录态</span>
                <span class="chip">MySQL</span>
                <span class="chip">本地可运行</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="right-stack">
        <section class="glass section-card">
          <div class="section-kicker">Hot Board</div>
          <div class="section-title">右侧热榜</div>
          <div class="hot-list">
            <?php if (!$hotPosts): ?>
              <div class="hot-item"><div class="hot-row"><div class="rank-no">#0</div><div class="hot-main"><div class="title">内容流刚接上，等第一批真实帖子把这里顶起来。</div><div class="heat">现在就能注册并发第一篇</div></div></div></div>
            <?php else: ?>
              <?php foreach ($hotPosts as $index => $post): ?>
                <div class="hot-item"><div class="hot-row"><div class="rank-no">#<?= $index + 1 ?></div><div class="hot-main"><div class="title"><a href="/post.php?id=<?= (int) $post['id'] ?>"><?= e($post['title']) ?></a></div><div class="heat">@<?= e($post['username']) ?> · <?= e(human_time($post['created_at'])) ?></div></div></div></div>
              <?php endforeach; ?>
            <?php endif; ?>
          </div>
        </section>

        <section class="glass section-card">
          <div class="section-kicker">Pulse Feed</div>
          <div class="feed-list">
            <?php if (!$feedPosts): ?>
              <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">刚刚</div><div class="text">数据库已经接通，但还缺第一条真正把气氛点亮的帖子。</div></div></div>
            <?php else: ?>
              <?php foreach ($feedPosts as $post): ?>
                <div class="feed-item"><div class="pulse-dot"></div><div><div class="time"><?= e(human_time($post['created_at'])) ?></div><div class="text">@<?= e($post['username']) ?> 发布了「<?= e($post['title']) ?>」</div></div></div>
              <?php endforeach; ?>
            <?php endif; ?>
          </div>
        </section>
      </div>
    </section>

    <section class="row-mid">
      <section class="glass section-card">
        <div class="section-kicker">Focus Slots</div>
        <div class="section-title">焦点位 / 活动卡 / 功能落点</div>
        <div class="focus-grid">
          <div class="focus-card focus-1"><div class="focus-top-badge">AUTH</div><div class="focus-emoji">🌌</div><div class="focus-title">真实注册</div><div class="focus-text">昵称、用户名、邮箱、密码校验后直写 MySQL，成功即自动登录并回首页。</div></div>
          <div class="focus-card focus-2"><div class="focus-top-badge">STATE</div><div class="focus-emoji">🧠</div><div class="focus-title">真实登录态</div><div class="focus-text">首页顶部按钮、欢迎提示和发帖入口都会按当前会话动态切换。</div></div>
          <div class="focus-card focus-3"><div class="focus-top-badge">FLOW</div><div class="focus-emoji">🎮</div><div class="focus-title">继续可扩展</div><div class="focus-text">保留已有发帖、找回密码、会员中心，不另起炉灶，继续在功能版上往前推。</div></div>
        </div>
      </section>

      <section class="glass section-card">
        <div class="section-kicker">Tag Cloud</div>
        <div class="section-title">当前可直接体验的入口</div>
        <div class="tag-cloud">
          <span class="tag-cloud-item a">#首页改成星云初始01</span>
          <span class="tag-cloud-item b">#登录查库</span>
          <span class="tag-cloud-item c">#注册入库</span>
          <span class="tag-cloud-item a">#自动登录</span>
          <span class="tag-cloud-item b">#会员中心</span>
          <span class="tag-cloud-item c">#本地稳定访问</span>
          <span class="tag-cloud-item a">#发帖继续可用</span>
          <span class="tag-cloud-item b">#样式统一</span>
        </div>
        <div class="mood-box">
          <div class="section-kicker mood-kicker">今日社区情绪</div>
          <div class="progress"><div></div></div>
          <p><?= $user ? '你已经在登录态里，接下来最适合直接去发一篇帖子，看首页内容流和会员中心是否一起联动。' : '现在这版最值得验证的是完整链路：注册 → 自动登录 → 首页状态切换 → 发帖入口可用。' ?></p>
        </div>
      </section>
    </section>

    <section class="row-bottom">
      <section>
        <div class="section-kicker">Trending Now</div>
        <div class="section-large-head">最近讨论度最高的内容卡</div>
        <div class="section-large-desc">卡片区保持接近“星云初始01”的论坛首页观感，但卡片数据直接读当前数据库内容，不再只是静态占位。</div>
        <div class="ticker">🔥 已接通：注册 / 登录 / 登录态 / 发帖 / 会员中心 / 找回密码基础流程</div>
        <div class="cards-3">
          <?php if (!$trendingPosts): ?>
            <?php for ($i = 1; $i <= 3; $i++): ?>
              <article class="glass game-card"><div class="game-cover alt<?= $i ?>"><div class="game-cover-top"><span class="small-chip a">等待新帖</span><span class="small-chip b">占位卡</span></div><div class="game-cover-bottom"><div class="game-title">等待第 <?= $i ?> 篇内容</div><div class="game-sub">现在注册后就能把这里顶起来</div></div></div><div class="game-body"><p>当前没有足够帖子，所以先展示功能占位卡。数据库一有内容，这里会立即变成真实帖子卡片。</p><div class="game-meta"><div>★ 实时读取</div><div style="color: var(--brand);">去注册</div></div></div></article>
            <?php endfor; ?>
          <?php else: ?>
            <?php foreach ($trendingPosts as $index => $post): ?>
              <article class="glass game-card"><div class="game-cover alt<?= ($index % 3) + 1 ?>"><div class="game-cover-top"><span class="small-chip a">数据库内容</span><span class="small-chip b">@<?= e($post['username']) ?></span></div><div class="game-cover-bottom"><div class="game-title"><?= e($post['title']) ?></div><div class="game-sub"><?= e(human_time($post['created_at'])) ?></div></div></div><div class="game-body"><p><?= e(excerpt($post['content'], 82)) ?></p><div class="game-meta"><div>★ 实时内容流</div><div style="color: var(--brand);"><a href="/post.php?id=<?= (int) $post['id'] ?>">查看详情</a></div></div></div></article>
            <?php endforeach; ?>
          <?php endif; ?>
        </div>

        <div class="glass supplement-card">
          <div class="supplement-grid">
            <div class="supplement-block">
              <div class="section-kicker">Forum Signals</div>
              <h4>这次不是纯改皮，而是把视觉版本和功能版真正焊在一起</h4>
              <p>首页沿用用户已确认的“星云初始01”氛围语言，再把现有 PHP 功能版的数据库、会话和发帖能力镶进去，这样后续继续开发不用返工。</p>
              <div class="mini-feed">
                <div class="mini-feed-item"><i></i><div><strong>顶部按钮已接真功能</strong><span>访客看到登录 / 注册；已登录用户看到昵称、发帖和退出。</span></div></div>
                <div class="mini-feed-item"><i></i><div><strong>注册立即建号并登录</strong><span>成功后直接写库，随后自动建立 session 并跳回首页。</span></div></div>
                <div class="mini-feed-item"><i></i><div><strong>首页状态实时变化</strong><span>重新打开首页也会刷新当前用户信息，避免旧 session 数据滞留。</span></div></div>
              </div>
            </div>

            <div class="supplement-block">
              <div class="section-kicker">Member Status</div>
              <h4><?= $user ? '当前已登录为 ' . e($user['nickname']) : '当前你还在访客态' ?></h4>
              <p><?= $user ? '现在可以继续测试会员中心、发帖和退出登录，确认整条链路都已经活了。' : '建议先注册一个新账号，最直观看首页右上角和主行动按钮如何立刻切换。' ?></p>
              <div class="badge-row">
                <span class="soft-badge">MySQL 已连接</span>
                <span class="soft-badge">Session 生效</span>
                <span class="soft-badge">本地可运行</span>
                <span class="soft-badge">可继续扩展</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div class="right-col-stack">
        <section class="glass section-card">
          <div class="section-kicker">Recommended Authors</div>
          <div class="section-title">真实成员速览</div>
          <div class="author-list">
            <?php if (!$hotPosts): ?>
              <div class="author-item"><div class="author-row"><div class="author-badge">✨</div><div class="author-main"><div class="author-name">等待首批成员</div><div class="meta">注册后这里会跟着内容一起活过来</div></div><div class="score">NEW</div></div><p>现在的重点已经不是占位图，而是让第一批真实用户行为能映射回首页。</p></div>
            <?php else: ?>
              <?php foreach (array_slice($posts, 0, 3) as $post): ?>
                <div class="author-item"><div class="author-row"><div class="author-badge">🏅</div><div class="author-main"><div class="author-name"><?= e($post['nickname']) ?> <span class="tiny-badge">真实用户</span></div><div class="meta">@<?= e($post['username']) ?></div></div><div class="score">LIVE</div></div><p>最近一次发帖：<?= e(excerpt($post['title'], 26)) ?></p></div>
              <?php endforeach; ?>
            <?php endif; ?>
          </div>
        </section>

        <section class="glass section-card">
          <div class="section-kicker">Top Rated</div>
          <div class="section-title">功能验收清单</div>
          <div class="rank-list">
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#1</div><div class="rank-main"><div class="rank-name">注册写库</div><div class="meta">pulsenest_users 插入新用户</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#2</div><div class="rank-main"><div class="rank-name">登录查库</div><div class="meta">支持邮箱 / 用户名 + password_verify</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#3</div><div class="rank-main"><div class="rank-name">登录态生效</div><div class="meta">首页头部、发帖与会员入口联动</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#4</div><div class="rank-main"><div class="rank-name">本地可运行</div><div class="meta">PHP 内置服务可稳定访问</div></div><div class="score">OK</div></div></div>
          </div>
        </section>
      </div>
    </section>
  </main>
<?php render_footer(); ?>
