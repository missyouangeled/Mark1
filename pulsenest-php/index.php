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

$sql = 'SELECT p.id, p.user_id, p.title, p.content, p.image_path, p.created_at, p.is_sticky, p.is_featured, p.recommend_level, p.home_slot, p.recommend_group, p.recommend_priority,
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
           SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
        ) c ON c.post_id = p.id';
if ($where) {
    $sql .= ' WHERE ' . implode(' AND ', $where);
}
$sql .= ' ORDER BY p.is_sticky DESC, p.recommend_priority DESC, p.recommend_level DESC, p.is_featured DESC, p.created_at DESC, p.id DESC LIMIT 18';
$stmt = db()->prepare($sql);
$stmt->execute($params);
$posts = $stmt->fetchAll();

$postCount = (int) db()->query('SELECT COUNT(*) FROM posts')->fetchColumn();
$userCount = (int) db()->query('SELECT COUNT(*) FROM pulsenest_users')->fetchColumn();
$boardCount = (int) db()->query('SELECT COUNT(*) FROM forum_boards')->fetchColumn();
$homeSlotDefs = home_slot_definitions();
$recommendGroups = recommend_group_definitions();
$homeCopy = home_copy_config();
$homeSlotPosts = [];
foreach ($posts as $post) {
    if (!empty($post['home_slot'])) {
        $homeSlotPosts[$post['home_slot']] = $post;
    }
}
$heroPost = $homeSlotPosts['hero'] ?? $posts[0] ?? null;
$heroUsesCustomTitle = hero_uses_custom_title($homeCopy);
$heroUsesCustomBody = hero_uses_custom_body($homeCopy);
$heroDisplayTitle = $heroPost && !$heroUsesCustomTitle ? ($heroPost['title'] ?? $homeCopy['home.hero.title']) : $homeCopy['home.hero.title'];
$heroDisplayBody = $heroPost && !$heroUsesCustomBody ? excerpt((string) ($heroPost['content'] ?? ''), 118) : $homeCopy['home.hero.body'];
$focusPosts = [
    'focus_one' => $homeSlotPosts['focus_one'] ?? ($posts[1] ?? $posts[0] ?? null),
    'focus_two' => $homeSlotPosts['focus_two'] ?? ($posts[2] ?? $posts[1] ?? $posts[0] ?? null),
    'focus_three' => $homeSlotPosts['focus_three'] ?? ($posts[3] ?? $posts[2] ?? $posts[0] ?? null),
];
$feedPosts = array_slice($posts, 0, 3);
$trendingPosts = array_slice($posts, 0, 3);
$recommendedPools = [];
foreach (array_keys($recommendGroups) as $groupKey) {
    $recommendedPools[$groupKey] = array_values(array_filter($posts, static fn (array $post): bool => ($post['recommend_group'] ?? 'general') === $groupKey && ((int) ($post['recommend_level'] ?? 0) > 0 || (int) ($post['recommend_priority'] ?? 0) > 0)));
}
$stickyCount = (int) db()->query('SELECT COUNT(*) FROM posts WHERE is_sticky = 1')->fetchColumn();
$featuredCount = (int) db()->query('SELECT COUNT(*) FROM posts WHERE is_featured = 1')->fetchColumn();

function render_focus_card(?array $post, string $slotKey, array $homeCopy, array $recommendGroups, string $fallbackTitle, string $fallbackText): void {
    $badgeText = $homeCopy['home.' . $slotKey . '.badge'] ?? 'OPS SLOT';
    ?>
    <div class="focus-card <?= e(match ($slotKey) {
        'focus_one' => 'focus-1',
        'focus_two' => 'focus-2',
        default => 'focus-3',
    }) ?>">
      <div class="focus-top-badge"><?= e($badgeText) ?></div>
      <div class="focus-emoji"><?= $post ? '🛰️' : '✨' ?></div>
      <div class="focus-title"><?= e($post['title'] ?? ($homeCopy['home.' . $slotKey . '.title'] ?? $fallbackTitle)) ?></div>
      <div class="focus-text"><?= e($post ? excerpt($post['content'], 72) : ($homeCopy['home.' . $slotKey . '.body'] ?? $fallbackText)) ?></div>
      <?php if ($post): ?>
        <div class="chips" style="margin-top:10px; gap:6px;">
          <?php if ((int) $post['is_featured'] === 1): ?><span class="chip">精华</span><?php endif; ?>
          <?php if ((int) $post['recommend_level'] > 0): ?><span class="chip">推荐位 <?= (int) $post['recommend_level'] ?></span><?php endif; ?>
          <span class="chip"><?= e($recommendGroups[$post['recommend_group']]['label'] ?? ($post['recommend_group'] ?? '综合推荐')) ?></span>
          <span class="chip">优先级 <?= (int) ($post['recommend_priority'] ?? 0) ?></span>
        </div>
        <div style="margin-top:12px;"><a class="inline-link" href="/post.php?id=<?= (int) $post['id'] ?>">进入帖子</a></div>
      <?php endif; ?>
    </div>
    <?php
}

render_header('PulseNest', $user, [
    'searchText' => '🔎 首页已接通运营位：置顶 / 精华 / 推荐位 / 首页卡绑定 / Hero 混合文案',
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
              <div class="brand-chip"><?= e($homeCopy['home.hero.eyebrow']) ?></div>
              <h1><?= e($heroDisplayTitle) ?></h1>
              <p class="hero-text"><?= e($heroDisplayBody) ?></p>
             <?php if ($heroPost): ?>
              <div class="chips" style="margin-top: 14px; gap: 6px;">
                <span class="chip">Hero 已绑定帖子</span>
                <span class="chip">标题<?= $heroUsesCustomTitle ? '使用自定义覆盖' : '跟随帖子' ?></span>
                <span class="chip">副文案<?= $heroUsesCustomBody ? '使用自定义覆盖' : '跟随帖子摘要' ?></span>
              </div>
             <?php endif; ?>
            </div>
            <div class="hero-actions-row">
              <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/register.php' ?>"><?= $user ? '开始分享内容' : '立即加入社区' ?></a>
              <a class="pill-btn" href="/posts.php">去看内容流</a>
              <a class="pill-btn" href="/notifications.php">我的提醒</a>
            </div>
            <div class="hero-stats">
              <div class="hero-stat"><div class="label">社区成员</div><div class="num"><?= $userCount ?></div><div class="note">头像与用户主页已启用</div></div>
              <div class="hero-stat"><div class="label">置顶帖子</div><div class="num"><?= $stickyCount ?></div><div class="note">优先抬到首页前列</div></div>
              <div class="hero-stat"><div class="label">精华帖子</div><div class="num"><?= $featuredCount ?></div><div class="note">可给内容质感做背书</div></div>
              <div class="hero-stat"><div class="label">论坛版块</div><div class="num"><?= $boardCount ?></div><div class="note">首页可按分类或版块浏览</div></div>
            </div>
          </div>
          <div class="hero-art">
            <div class="hero-art-top">
              <span class="badge">Home Hero Slot</span>
              <span class="badge soft"><?= $heroPost ? ((int) ($heroPost['is_sticky'] ?? 0) === 1 ? '置顶中' : '已绑定') : '等待绑定' ?></span>
            </div>
            <div class="hero-art-bottom">
              <div class="kicker"><?= e($homeSlotDefs['hero']['label']) ?></div>
              <div class="title"><?= e($heroPost['title'] ?? 'Starfall Zero') ?></div>
              <div class="text"><?= e($heroPost ? excerpt($heroPost['content'], 56) : '沉浸式星际探索 + 高强度战斗循环') ?></div>
              <?php if ($heroPost): ?><div class="muted" style="margin-top:10px;">左侧主文案当前<?= $heroUsesCustomTitle || $heroUsesCustomBody ? '已启用部分覆盖模式' : '完全跟随绑定帖子' ?>。</div><?php endif; ?>
              <div class="chips">
                <?php if ($heroPost): ?>
                  <span class="chip"><?= e(board_badge($heroPost)) ?></span>
                  <span class="chip"><?= (int) $heroPost['like_count'] ?> 赞</span>
                  <span class="chip"><?= (int) $heroPost['comment_count'] ?> 回复</span>
                <?php else: ?>
                  <span class="chip">分类 / 版块</span>
                  <span class="chip"><?= e($homeCopy['home.hero.tag_primary']) ?></span>
                  <span class="chip"><?= e($homeCopy['home.hero.tag_secondary']) ?></span>
                <?php endif; ?>
              </div>
              <?php if ($heroPost): ?><div style="margin-top:12px;"><a class="inline-link" href="/post.php?id=<?= (int) $heroPost['id'] ?>">查看主运营帖</a></div><?php endif; ?>
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

        <section class="glass section-card pulse-feed-card">
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
        <div class="section-title">首页焦点运营卡</div>
        <div class="focus-grid">
          <?php render_focus_card($focusPosts['focus_one'], 'focus_one', $homeCopy, $recommendGroups, '焦点卡 1 待绑定', '后台可把重点帖子直接塞进这张中部卡位。'); ?>
          <?php render_focus_card($focusPosts['focus_two'], 'focus_two', $homeCopy, $recommendGroups, '焦点卡 2 待绑定', '适合放活动帖、征集帖、版本说明帖。'); ?>
          <?php render_focus_card($focusPosts['focus_three'], 'focus_three', $homeCopy, $recommendGroups, '焦点卡 3 待绑定', '维持视觉稳定，同时把中段内容改成可运营入口。'); ?>
        </div>
      </section>

      <section class="glass section-card">
        <div class="section-kicker">Recommendation Pools</div>
        <div class="section-title">推荐位分组与优先级</div>
        <div class="rank-list">
          <?php foreach ($recommendGroups as $groupKey => $groupMeta): ?>
            <?php $leadPost = $recommendedPools[$groupKey][0] ?? null; ?>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= e(strtoupper(substr($groupKey, 0, 1))) ?></div><div class="rank-main"><div class="rank-name"><?= e($groupMeta['label']) ?></div><div class="meta"><?= e($leadPost ? $leadPost['title'] . ' · 优先级 ' . (int) ($leadPost['recommend_priority'] ?? 0) : $groupMeta['desc']) ?></div></div><div class="score"><?= count($recommendedPools[$groupKey]) ?>条</div></div></div>
          <?php endforeach; ?>
        </div>
      </section>

      <section class="glass section-card">
        <div class="section-kicker">Tag Cloud</div>
        <div class="section-title">当前可直接体验的入口</div>
        <div class="tag-cloud">
          <span class="tag-cloud-item a">#星云初始01</span>
          <span class="tag-cloud-item b">#论坛分类</span>
          <span class="tag-cloud-item c">#论坛版块</span>
          <span class="tag-cloud-item a">#帖子置顶</span>
          <span class="tag-cloud-item b">#帖子精华</span>
          <span class="tag-cloud-item c">#首页运营卡</span>
          <span class="tag-cloud-item a">#通知筛选</span>
          <span class="tag-cloud-item b">#评论审核</span>
        </div>
        <div class="mood-box">
          <div class="section-kicker mood-kicker">今日社区情绪</div>
          <div class="progress"><div></div></div>
          <p><?= $user ? '现在最适合走完整运营链路：后台给一篇帖子打上置顶 / 首页卡 → 前台刷新首页确认卡位 → 用另一个账号评论 / 点赞验证提醒和审核流。' : '这版已经不只是皮肤样机，注册后能直接体验首页运营卡、帖子流、评论和提醒。' ?></p>
        </div>
      </section>
    </section>

    <section class="row-bottom">
      <section>
        <div class="section-kicker">Trending Now</div>
        <div class="section-large-head">最近讨论度最高的内容卡</div>
        <div class="section-large-desc">卡片区继续沿用“星云初始01”的首页观感，但现在会优先考虑置顶 / 推荐位 / 精华逻辑，再把帖子所属版块一起带出来。</div>
        <div class="ticker">🔥 已接通：置顶 / 精华 / 推荐位 / 首页卡绑定 / 评论审核状态 / 通知筛选 / 站内回复提醒 / 发帖 / 点赞 / 用户主页</div>
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
                <div class="game-body">
                  <p><?= e(excerpt($post['content'], 82)) ?></p>
                  <div class="chips" style="margin-bottom:10px; gap:6px;">
                    <?php if ((int) $post['is_sticky'] === 1): ?><span class="chip">置顶</span><?php endif; ?>
                    <?php if ((int) $post['is_featured'] === 1): ?><span class="chip">精华</span><?php endif; ?>
                    <?php if ((int) $post['recommend_level'] > 0): ?><span class="chip">推荐位 <?= (int) $post['recommend_level'] ?></span><?php endif; ?>
          <span class="chip"><?= e($recommendGroups[$post['recommend_group']]['label'] ?? ($post['recommend_group'] ?? '综合推荐')) ?></span>
          <span class="chip">优先级 <?= (int) ($post['recommend_priority'] ?? 0) ?></span>
                  </div>
                  <div class="game-meta"><div><?= (int) $post['like_count'] ?> 赞 · <?= (int) $post['comment_count'] ?> 回复</div><div style="color: var(--brand);"><a href="/post.php?id=<?= (int) $post['id'] ?>">查看详情</a></div></div>
                </div>
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
            <?php if (!$posts): ?>
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
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#1</div><div class="rank-main"><div class="rank-name">帖子运营位</div><div class="meta">后台支持置顶 / 精华 / 推荐位 / 首页卡 / Hero 混合文案</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#2</div><div class="rank-main"><div class="rank-name">评论管理</div><div class="meta">评论支持 approved / pending / hidden</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#3</div><div class="rank-main"><div class="rank-name">通知筛选</div><div class="meta">支持未读 / 类型筛选与批量处理</div></div><div class="score">OK</div></div></div>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#4</div><div class="rank-main"><div class="rank-name">既有功能保留</div><div class="meta">点赞、评论、用户主页、上传均未破坏</div></div><div class="score">OK</div></div></div>
          </div>
        </section>
      </div>
    </section>
  </main>
<?php render_footer(); ?>
