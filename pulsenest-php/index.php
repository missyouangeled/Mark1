<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$flash = flash_get();
$forum = fetch_forum_structure();
$selectedCategory = trim($_GET['category'] ?? '');
$selectedBoard = trim($_GET['board'] ?? '');

$where = [];
$params = [];
if ($selectedCategory !== '') {
    $where[] = 'fc.slug = :category_slug';
    $params['category_slug'] = $selectedCategory;
}
if ($selectedBoard !== '') {
    $where[] = 'fb.slug = :board_slug';
    $params['board_slug'] = $selectedBoard;
}

$sql = 'SELECT p.id, p.user_id, p.title, p.content, p.image_path, p.created_at,
               u.nickname, u.username, u.avatar_path,
               fb.name AS board_name, fb.slug AS board_slug,
               fc.name AS category_name, fc.slug AS category_slug,
               COALESCE(l.like_count, 0) AS like_count,
               COALESCE(c.comment_count, 0) AS comment_count
        FROM posts p
        INNER JOIN pulsenest_users u ON u.id = p.user_id
        LEFT JOIN forum_boards fb ON fb.id = p.board_id
        LEFT JOIN forum_categories fc ON fc.id = fb.category_id
        LEFT JOIN (
           SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
        ) l ON l.post_id = p.id
        LEFT JOIN (
           SELECT post_id, COUNT(*) AS comment_count FROM comments GROUP BY post_id
        ) c ON c.post_id = p.id';
if ($where) {
    $sql .= ' WHERE ' . implode(' AND ', $where);
}
$sql .= ' ORDER BY p.created_at DESC, p.id DESC LIMIT 12';
$stmt = db()->prepare($sql);
$stmt->execute($params);
$posts = $stmt->fetchAll();

$postCount = (int) db()->query('SELECT COUNT(*) FROM posts')->fetchColumn();
$userCount = (int) db()->query('SELECT COUNT(*) FROM pulsenest_users')->fetchColumn();
$boardCount = (int) db()->query('SELECT COUNT(*) FROM forum_boards')->fetchColumn();
$heroPost = $posts[0] ?? null;
$hotPosts = array_slice($posts, 0, 4);
$feedPosts = array_slice($posts, 0, 3);
$trendingPosts = array_slice($posts, 0, 3);

render_header('PulseNest', $user, [
    'searchText' => '🔎 首页支持按分类 / 版块跳转，发现页支持标题 / 正文搜索',
]);
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
              <div class="brand-chip">星云初始01 · 首页升级到论坛骨架 · PHP 功能已接通</div>
              <h1>先用星云氛围把人留下，再用分类、版块、搜索和提醒把社区真正撑起来。</h1>
              <p class="hero-text">这一版继续保留已确认的视觉锚点，但首页已经不只是展示热帖：帖子正式归属到分类 / 版块，发现页可以全文搜索，评论回复还会给帖子作者或被回复者发站内提醒。</p>
            </div>
            <div class="hero-actions-row">
              <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/register.php' ?>"><?= $user ? '开始分享内容' : '立即加入社区' ?></a>
              <a class="pill-btn" href="/posts.php">去看内容流</a>
              <a class="pill-btn" href="/notifications.php">我的提醒</a>
            </div>
            <div class="hero-stats">
              <div class="hero-stat"><div class="label">社区成员</div><div class="num"><?= $userCount ?></div><div class="note">头像与用户主页已启用</div></div>
              <div class="hero-stat"><div class="label">实时帖子</div><div class="num"><?= $postCount ?></div><div class="note">支持版块归属与搜索</div></div>
              <div class="hero-stat"><div class="label">论坛版块</div><div class="num"><?= $boardCount ?></div><div class="note">首页可按分类或版块浏览</div></div>
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
                <span class="chip">分类 / 版块</span>
                <span class="chip">标题 / 正文搜索</span>
                <span class="chip">站内回复提醒</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="right-stack">
        <section class="glass section-card">
          <div class="section-kicker">Forum Categories</div>
          <div class="section-title">首页可直接下钻版块</div>
          <div class="category-stack">
            <?php foreach ($forum as $category): ?>
              <div class="category-card">
                <div class="author-row">
                  <div class="author-main">
                    <div class="author-name"><a class="inline-link" href="/posts.php?category=<?= e($category['slug']) ?>"><?= e($category['name']) ?></a></div>
                    <div class="meta"><?= e($category['description']) ?></div>
                  </div>
                </div>
                <div class="chips board-chip-list">
                  <?php foreach ($category['boards'] as $board): ?>
                    <a class="chip board-link-chip" href="/posts.php?board=<?= e($board['slug']) ?>"><?= e($board['name']) ?> · <?= (int) $board['post_count'] ?></a>
                  <?php endforeach; ?>
                </div>
              </div>
            <?php endforeach; ?>
          </div>
        </section>

        <section class="glass section-card">
          <div class="section-kicker">Pulse Feed</div>
          <div class="feed-list">
            <?php if (!$feedPosts): ?>
              <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">刚刚</div><div class="text">数据库已经接通，但还缺第一条真正把气氛点亮的帖子。</div></div></div>
            <?php else: ?>
              <?php foreach ($feedPosts as $post): ?>
                <div class="feed-item"><div class="pulse-dot"></div><div><div class="time"><?= e(human_time($post['created_at'])) ?></div><div class="text"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>">@<?= e($post['username']) ?></a> 在 <?= e(board_badge($post)) ?> 发布了「<?= e($post['title']) ?>」</div></div></div>
              <?php endforeach; ?>
            <?php endif; ?>
          </div>
        </section>
      </div>
    </section>

    <section class="row-mid">
      <section class="glass section-card">
        <div class="section-kicker">Focus Slots</div>
        <div class="section-title">这一轮真正补上的论坛骨架</div>
        <div class="focus-grid">
          <div class="focus-card focus-1"><div class="focus-top-badge">FORUM</div><div class="focus-emoji">🛰️</div><div class="focus-title">分类 / 版块</div><div class="focus-text">帖子现在不再漂浮着存在，而是落到分类与版块体系里，首页和列表页都能按结构浏览。</div></div>
          <div class="focus-card focus-2"><div class="focus-top-badge">SEARCH</div><div class="focus-emoji">🔎</div><div class="focus-title">标题 / 正文搜索</div><div class="focus-text">发现页支持基础关键词搜索，至少能按标题和正文把帖子筛出来。</div></div>
          <div class="focus-card focus-3"><div class="focus-top-badge">NOTICE</div><div class="focus-emoji">🔔</div><div class="focus-title">站内提醒</div><div class="focus-text">别人回复你的帖子或评论时，会在提醒页聚合展示，并同步未读数。</div></div>
        </div>
      </section>

      <section class="glass section-card">
        <div class="section-kicker">Tag Cloud</div>
        <div class="section-title">当前可直接体验的入口</div>
        <div class="tag-cloud">
          <span class="tag-cloud-item a">#星云初始01</span>
          <span class="tag-cloud-item b">#论坛分类</span>
          <span class="tag-cloud-item c">#论坛版块</span>
          <span class="tag-cloud-item a">#标题正文搜索</span>
          <span class="tag-cloud-item b">#站内提醒</span>
          <span class="tag-cloud-item c">#评论回复</span>
          <span class="tag-cloud-item a">#帖子点赞</span>
          <span class="tag-cloud-item b">#用户主页</span>
        </div>
        <div class="mood-box">
          <div class="section-kicker mood-kicker">今日社区情绪</div>
          <div class="progress"><div></div></div>
          <p><?= $user ? '你现在最适合测试完整论坛链路：进一个版块发帖 → 用另一个账号评论 / 回复 → 打开提醒页确认通知。' : '这一版已经不只是皮肤样机，注册后可以完整体验分类、版块、搜索和回复提醒。' ?></p>
        </div>
      </section>
    </section>

    <section class="row-bottom">
      <section>
        <div class="section-kicker">Trending Now</div>
        <div class="section-large-head">最近讨论度最高的内容卡</div>
        <div class="section-large-desc">卡片区继续沿用“星云初始01”的首页观感，但现在会把帖子所属的分类 / 版块一起带出来。</div>
        <div class="ticker">🔥 已接通：分类 / 版块 / 标题正文搜索 / 站内回复提醒 / 发帖 / 点赞 / 评论 / 回复 / 用户主页</div>
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
                  <div class="game-cover alt<?= ($index % 3) + 1 ?>"><div class="game-cover-top"><span class="small-chip a"><?= e($post['board_name'] ?? '公共区') ?></span><span class="small-chip b">@<?= e($post['username']) ?></span></div><div class="game-cover-bottom"><div class="game-title"><?= e($post['title']) ?></div><div class="game-sub"><?= e(human_time($post['created_at'])) ?></div></div></div>
                <?php endif; ?>
                <div class="game-body"><p><?= e(excerpt($post['content'], 82)) ?></p><div class="game-meta"><div><?= (int) $post['like_count'] ?> 赞 · <?= (int) $post['comment_count'] ?> 回复</div><div style="color: var(--brand);"><a href="/post.php?id=<?= (int) $post['id'] ?>">查看详情</a></div></div></div>
              </article>
            <?php endforeach; ?>
          <?php endif; ?>
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
                      <div class="meta">@<?= e($post['username']) ?> · <?= e(board_badge($post)) ?></div>
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
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#1</div><div class="rank-main"><div class="rank-name">论坛分类 / 版块</div><div class="meta">帖子已归属到 forum_categories / forum_boards</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#2</div><div class="rank-main"><div class="rank-name">帖子搜索</div><div class="meta">posts.php 支持标题 / 正文搜索</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#3</div><div class="rank-main"><div class="rank-name">站内提醒</div><div class="meta">回复帖子 / 评论时写入 notifications</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#4</div><div class="rank-main"><div class="rank-name">既有功能保留</div><div class="meta">点赞、评论、用户主页、上传均未破坏</div></div><div class="score">OK</div></div></div>
          </div>
        </section>
      </div>
    </section>
  </main>
<?php render_footer(); ?>