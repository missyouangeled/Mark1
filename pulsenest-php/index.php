<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$flash = flash_get();

$postCount = (int) db()->query('SELECT COUNT(*) FROM posts')->fetchColumn();
$userCount = (int) db()->query('SELECT COUNT(*) FROM pulsenest_users')->fetchColumn();

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
              <p class="hero-text">这一版已经从原型继续往真社区推进：登录注册、发帖、图片上传、点赞、评论 / 回复、用户主页和头像资料都已经接上真实数据库链路。</p>
            </div>
            <div class="hero-actions-row">
              <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/register.php' ?>"><?= $user ? '开始分享内容' : '立即加入社区' ?></a>
              <a class="pill-btn" href="/posts.php">去看内容流</a>
            </div>
            <div class="hero-stats">
              <div class="hero-stat"><div class="label">社区成员</div><div class="num"><?= $userCount ?></div><div class="note">头像与用户主页已启用</div></div>
              <div class="hero-stat"><div class="label">实时帖子</div><div class="num"><?= $postCount ?></div><div class="note">支持帖子配图和详情互动</div></div>
              <div class="hero-stat"><div class="label">当前状态</div><div class="num"><?= $user ? '在线' : '访客' ?></div><div class="note"><?= $user ? '可直接点赞、评论、发帖' : '注册后可完整体验社区链路' ?></div></div>
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
                <span class="chip">评论/回复</span>
                <span class="chip">帖子点赞</span>
                <span class="chip">用户主页</span>
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
                <div class="hot-item"><div class="hot-row"><div class="rank-no">#<?= $index + 1 ?></div><div class="hot-main"><div class="title"><a href="/post.php?id=<?= (int) $post['id'] ?>"><?= e($post['title']) ?></a></div><div class="heat"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>">@<?= e($post['username']) ?></a> · <?= (int) $post['like_count'] ?> 赞 · <?= (int) $post['comment_count'] ?> 回复</div></div></div></div>
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
                <div class="feed-item"><div class="pulse-dot"></div><div><div class="time"><?= e(human_time($post['created_at'])) ?></div><div class="text"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>">@<?= e($post['username']) ?></a> 发布了「<?= e($post['title']) ?>」</div></div></div>
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
          <div class="focus-card focus-1"><div class="focus-top-badge">DISCUSS</div><div class="focus-emoji">💬</div><div class="focus-title">评论 / 回复</div><div class="focus-text">帖子详情页支持评论和楼中回复，提交后直写 comments 表并实时展示。</div></div>
          <div class="focus-card focus-2"><div class="focus-top-badge">LIKE</div><div class="focus-emoji">🔥</div><div class="focus-title">帖子点赞</div><div class="focus-text">登录后即可点赞 / 取消点赞，写入 post_likes 表并回显计数。</div></div>
          <div class="focus-card focus-3"><div class="focus-top-badge">PROFILE</div><div class="focus-emoji">🪐</div><div class="focus-title">用户主页</div><div class="focus-text">昵称和头像都可点进个人主页，查看基础信息、发帖数和最近帖子。</div></div>
        </div>
      </section>

      <section class="glass section-card">
        <div class="section-kicker">Tag Cloud</div>
        <div class="section-title">当前可直接体验的入口</div>
        <div class="tag-cloud">
          <span class="tag-cloud-item a">#星云初始01</span>
          <span class="tag-cloud-item b">#登录注册</span>
          <span class="tag-cloud-item c">#发帖配图</span>
          <span class="tag-cloud-item a">#头像上传</span>
          <span class="tag-cloud-item b">#评论回复</span>
          <span class="tag-cloud-item c">#帖子点赞</span>
          <span class="tag-cloud-item a">#用户主页</span>
          <span class="tag-cloud-item b">#本地稳定访问</span>
        </div>
        <div class="mood-box">
          <div class="section-kicker mood-kicker">今日社区情绪</div>
          <div class="progress"><div></div></div>
          <p><?= $user ? '你已经在登录态里，最适合直接发一篇带图帖子，再去详情页试点赞和评论链路。' : '现在这版最适合验证完整路径：注册 → 上传头像 → 发帖配图 → 点赞 / 评论 → 查看用户主页。' ?></p>
        </div>
      </section>
    </section>

    <section class="row-bottom">
      <section>
        <div class="section-kicker">Trending Now</div>
        <div class="section-large-head">最近讨论度最高的内容卡</div>
        <div class="section-large-desc">卡片区继续沿用“星云初始01”的论坛首页观感，但内容卡已经会带真实作者、图片、点赞和回复数据。</div>
        <div class="ticker">🔥 已接通：注册 / 登录 / 登录态 / 发帖 / 发帖配图 / 会员中心 / 头像上传 / 点赞 / 评论 / 回复 / 用户主页</div>
        <div class="cards-3">
          <?php if (!$trendingPosts): ?>
            <?php for ($i = 1; $i <= 3; $i++): ?>
              <article class="glass game-card"><div class="game-cover alt<?= $i ?>"><div class="game-cover-top"><span class="small-chip a">等待新帖</span><span class="small-chip b">占位卡</span></div><div class="game-cover-bottom"><div class="game-title">等待第 <?= $i ?> 篇内容</div><div class="game-sub">现在注册后就能把这里顶起来</div></div></div><div class="game-body"><p>当前没有足够帖子，所以先展示功能占位卡。数据库一有内容，这里会立即变成真实帖子卡片。</p><div class="game-meta"><div>★ 实时读取</div><div style="color: var(--brand);">去注册</div></div></div></article>
            <?php endfor; ?>
          <?php else: ?>
            <?php foreach ($trendingPosts as $index => $post): ?>
              <article class="glass game-card">
                <?php if (!empty($post['image_path'])): ?>
                  <div class="game-cover image-cover"><img class="post-cover-image card-cover-image" src="<?= e(asset_url($post['image_path'])) ?>" alt="<?= e($post['title']) ?>"></div>
                <?php else: ?>
                  <div class="game-cover alt<?= ($index % 3) + 1 ?>"><div class="game-cover-top"><span class="small-chip a">数据库内容</span><span class="small-chip b">@<?= e($post['username']) ?></span></div><div class="game-cover-bottom"><div class="game-title"><?= e($post['title']) ?></div><div class="game-sub"><?= e(human_time($post['created_at'])) ?></div></div></div>
                <?php endif; ?>
                <div class="game-body"><p><?= e(excerpt($post['content'], 82)) ?></p><div class="game-meta"><div><?= (int) $post['like_count'] ?> 赞 · <?= (int) $post['comment_count'] ?> 回复</div><div style="color: var(--brand);"><a href="/post.php?id=<?= (int) $post['id'] ?>">查看详情</a></div></div></div>
              </article>
            <?php endforeach; ?>
          <?php endif; ?>
        </div>

        <div class="glass supplement-card">
          <div class="supplement-grid">
            <div class="supplement-block">
              <div class="section-kicker">Forum Signals</div>
              <h4>这次已经不只是纯改皮，而是真把“论坛行为”焊进页面里</h4>
              <p>首页沿用用户已确认的“星云初始01”氛围语言，同时把帖子、作者、头像、点赞和评论都接成可点击、可追踪的真实社区路径。</p>
              <div class="mini-feed">
                <div class="mini-feed-item"><i></i><div><strong>顶部头像已接真资料</strong><span>登录后头部会显示当前用户头像或昵称首字母。</span></div></div>
                <div class="mini-feed-item"><i></i><div><strong>发帖支持单图上传</strong><span>帖子图片保存到 uploads/posts，并在多个页面联动显示。</span></div></div>
                <div class="mini-feed-item"><i></i><div><strong>作者主页可追溯</strong><span>从帖子作者昵称可进入主页，查看发帖和基础资料。</span></div></div>
              </div>
            </div>

            <div class="supplement-block">
              <div class="section-kicker">Member Status</div>
              <h4><?= $user ? '当前已登录为 ' . e($user['nickname']) : '当前你还在访客态' ?></h4>
              <p><?= $user ? '现在最适合一路测试：上传头像 → 发帖配图 → 点赞 / 评论 → 打开用户主页。' : '建议先注册一个新账号，从会员中心传头像，再发布一篇带图帖子感受完整闭环。' ?></p>
              <div class="badge-row">
                <span class="soft-badge">MySQL 已连接</span>
                <span class="soft-badge">Session 生效</span>
                <span class="soft-badge">上传已启用</span>
                <span class="soft-badge">互动已启用</span>
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
                <div class="author-item">
                  <div class="author-row">
                    <div class="author-badge">🏅</div>
                    <div class="author-main">
                      <div class="author-name"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>"><?= e($post['nickname']) ?></a> <span class="tiny-badge">真实用户</span></div>
                      <div class="meta">@<?= e($post['username']) ?></div>
                    </div>
                    <div class="score"><?= (int) $post['like_count'] ?>赞</div>
                  </div>
                  <p>最近一次发帖：<?= e(excerpt($post['title'], 26)) ?></p>
                </div>
              <?php endforeach; ?>
            <?php endif; ?>
          </div>
        </section>

        <section class="glass section-card">
          <div class="section-kicker">Top Rated</div>
          <div class="section-title">功能验收清单</div>
          <div class="rank-list">
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#1</div><div class="rank-main"><div class="rank-name">评论 / 回复</div><div class="meta">帖子详情页可写入 comments</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#2</div><div class="rank-main"><div class="rank-name">帖子点赞</div><div class="meta">登录用户可写入 post_likes</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#3</div><div class="rank-main"><div class="rank-name">用户主页</div><div class="meta">从作者昵称可进入主页</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#4</div><div class="rank-main"><div class="rank-name">图片 / 头像上传</div><div class="meta">上传到项目 uploads 目录</div></div><div class="score">OK</div></div></div>
          </div>
        </section>
      </div>
    </section>
  </main>
<?php render_footer(); ?>
