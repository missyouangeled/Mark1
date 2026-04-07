<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$flash = flash_get();
$forum = fetch_forum_structure();
$selectedCategory = trim($_GET['category'] ?? '');
$selectedBoard = trim($_GET['board'] ?? '');
$sort = normalize_post_sort($_GET['sort'] ?? 'latest');
$sortSql = post_sort_options()[$sort]['sql'];

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

$sql = 'SELECT p.id, p.user_id, p.title, p.content, p.image_path, p.status, p.view_count, p.created_at, p.is_sticky, p.is_featured, p.recommend_level, p.home_slot, p.recommend_group, p.recommend_priority,
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
$where[] = 'p.status = "published"';
if ($where) {
    $sql .= ' WHERE ' . implode(' AND ', $where);
}
$sql .= ' ORDER BY ' . $sortSql . ' LIMIT 12';
$stmt = db()->prepare($sql);
$stmt->execute($params);
$posts = $stmt->fetchAll();

$overview = db()->query(
    'SELECT
        (SELECT COUNT(*) FROM posts WHERE status = "published") AS post_count,
        (SELECT COUNT(*) FROM pulsenest_users) AS user_count,
        (SELECT COUNT(*) FROM forum_boards) AS board_count,
        (SELECT COUNT(*) FROM posts WHERE status = "published" AND is_sticky = 1) AS sticky_count,
        (SELECT COUNT(*) FROM posts WHERE status = "published" AND is_featured = 1) AS featured_count'
)->fetch();
$postCount = (int) ($overview['post_count'] ?? 0);
$userCount = (int) ($overview['user_count'] ?? 0);
$boardCount = (int) ($overview['board_count'] ?? 0);
$stickyCount = (int) ($overview['sticky_count'] ?? 0);
$featuredCount = (int) ($overview['featured_count'] ?? 0);
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
$heroTitleLength = mb_strlen(trim((string) $heroDisplayTitle));
$heroBodyLength = mb_strlen(trim((string) $heroDisplayBody));
$heroIsUnbound = !$heroPost || empty($heroPost['id']);
$heroHasLongTitle = $heroTitleLength >= 28;
$heroHasShortBody = $heroBodyLength > 0 && $heroBodyLength <= 44;
$homeHasSparseData = $postCount <= 4 && count($posts) <= 4;
$heroBalanceClasses = array_filter([
    $heroIsUnbound ? 'hero-panel--unbound' : null,
    $heroHasLongTitle ? 'hero-panel--long-title' : null,
    $heroHasShortBody ? 'hero-panel--short-copy' : null,
    $homeHasSparseData ? 'hero-panel--sparse-data' : null,
]);
$heroBalanceNote = match (true) {
    $heroIsUnbound && $heroHasShortBody => '当前首页主视觉还没有绑定专属 Hero，文案也保持得很克制，所以我把信息重心更多交给统计卡和右侧预留位，避免首屏显得空。',
    $heroIsUnbound => '当前首页主视觉还没有绑定专属 Hero，先用更稳的默认信息和右侧预留位把首页第一屏撑住，等真正的主内容接入也不会失衡。',
    $heroHasLongTitle => '这一屏已经按超长标题做了收口，标题允许更自然地换行，按钮和统计区会继续把重心往下接，不让第一屏头重脚轻。',
    $heroHasShortBody => '当前副文案偏短，所以首屏把更多说明交给状态 chips、统计卡和右侧说明层来补节奏，避免正文只剩一小截。',
    default => '把社区里最值得被看见的内容，稳定地摆在第一眼。',
};
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
$topAuthors = [];
$topPostsByViews = [];
$activeBoardsHome = [];
$showRecommendedAuthors = site_setting_enabled('home.module.recommended_authors_enabled', true);
$showTopViewed = site_setting_enabled('home.module.top_viewed_enabled', true);
$showTimeHotlist = site_setting_enabled('home.module.time_hotlist_enabled', true);

if ($showRecommendedAuthors) {
    $topAuthors = db()->query(
        'SELECT u.id, u.nickname, u.username, u.avatar_path,
                COUNT(p.id) AS post_count,
                COALESCE(SUM(COALESCE(l.like_count, 0)), 0) AS total_likes,
                COALESCE(SUM(COALESCE(c.comment_count, 0)), 0) AS total_comments,
                COALESCE(SUM(COALESCE(p.view_count, 0)), 0) AS total_views,
                MAX(p.created_at) AS latest_post_at
         FROM pulsenest_users u
         INNER JOIN posts p ON p.user_id = u.id AND p.status = "published"
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
         ) l ON l.post_id = p.id
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
         ) c ON c.post_id = p.id
         GROUP BY u.id, u.nickname, u.username, u.avatar_path
         ORDER BY total_likes DESC, total_views DESC, total_comments DESC, latest_post_at DESC
         LIMIT 3'
    )->fetchAll();
}

if ($showTopViewed) {
    $topPostsByViews = db()->query(
        'SELECT p.id, p.title, p.view_count, p.created_at,
                u.nickname, u.username,
                COALESCE(l.like_count, 0) AS like_count,
                COALESCE(c.comment_count, 0) AS comment_count
         FROM posts p
         INNER JOIN pulsenest_users u ON u.id = p.user_id
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
         ) l ON l.post_id = p.id
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
         ) c ON c.post_id = p.id
         WHERE p.status = "published"
         ORDER BY p.view_count DESC, c.comment_count DESC, l.like_count DESC, p.created_at DESC
         LIMIT 3'
    )->fetchAll();
}

$activeBoardsHome = db()->query(
    'SELECT fb.id, fb.name, fb.slug, fc.name AS category_name,
            COUNT(p.id) AS post_count,
            COALESCE(SUM(COALESCE(p.view_count, 0)), 0) AS total_views
     FROM forum_boards fb
     INNER JOIN forum_categories fc ON fc.id = fb.category_id
     LEFT JOIN posts p ON p.board_id = fb.id AND p.status = "published" AND p.created_at >= NOW() - INTERVAL 7 DAY
     GROUP BY fb.id, fb.name, fb.slug, fc.name
     ORDER BY post_count DESC, total_views DESC, fb.name ASC
     LIMIT 4'
)->fetchAll();
$timeRangeBoards = [
    '24h' => ['label' => '24 小时热榜', 'interval' => '1 DAY'],
    '7d' => ['label' => '7 天热榜', 'interval' => '7 DAY'],
    '30d' => ['label' => '30 天热榜', 'interval' => '30 DAY'],
];
$timeRangeHotPosts = [];
if ($showTimeHotlist) {
    foreach ($timeRangeBoards as $rangeKey => $rangeMeta) {
        $stmt = db()->query(
            'SELECT p.id, p.title, p.view_count, p.created_at, u.username,
                    COALESCE(l.like_count, 0) AS like_count,
                    COALESCE(c.comment_count, 0) AS comment_count
             FROM posts p
             INNER JOIN pulsenest_users u ON u.id = p.user_id
             LEFT JOIN (
                SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
             ) l ON l.post_id = p.id
             LEFT JOIN (
                SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
             ) c ON c.post_id = p.id
             WHERE p.status = "published" AND p.created_at >= NOW() - INTERVAL ' . $rangeMeta['interval'] . '
             ORDER BY ' . hot_score_sql() . ' DESC, p.created_at DESC
             LIMIT 2'
        );
        $timeRangeHotPosts[$rangeKey] = $stmt->fetchAll();
    }
}

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
    'searchText' => '🔎 首页支持推荐内容、分类下钻、排序切换与实时热榜浏览',
]);
?>
  <main class="shell home-page">
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>

    <section class="hero-grid <?= $homeHasSparseData ? 'hero-grid--sparse' : '' ?>">
      <div class="glass hero-panel <?= e(implode(' ', $heroBalanceClasses)) ?>">
        <div class="hero-inner">
          <div class="hero-copy">
            <div>
              <div class="brand-chip"><?= e($homeCopy['home.hero.eyebrow']) ?></div>
              <h1><?= e($heroDisplayTitle) ?></h1>
              <p class="hero-text"><?= e($heroDisplayBody) ?></p>
              <div class="hero-balance-note"><?= e($heroBalanceNote) ?></div>
             <?php if ($heroPost): ?>
              <div class="chips hero-status-chips" style="margin-top: 14px; gap: 6px;">
                <span class="chip">Hero 已绑定</span>
                <span class="chip">标题<?= $heroUsesCustomTitle ? '已覆盖' : '跟随帖子' ?></span>
                <span class="chip">副文案<?= $heroUsesCustomBody ? '已覆盖' : '跟随摘要' ?></span>
              </div>
             <?php endif; ?>
             <div class="hero-editorial-note">首页主视觉继续维持轻玻璃与轻说明层，优先保证不同数据状态下都能站得住。</div>
            </div>
            <div class="hero-actions-row">
              <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/register.php' ?>"><?= $user ? '发布内容' : '加入社区' ?></a>
              <a class="pill-btn" href="/posts.php?sort=<?= e($sort) ?>">浏览内容流</a>
              <a class="pill-btn" href="<?= $user ? '/notifications.php' : '/posts.php' ?>"><?= $user ? '查看提醒' : '进入社区地图' ?></a>
            </div>
            <div class="chips">
              <?php foreach (post_sort_options() as $sortKey => $sortMeta): ?>
                <a class="chip" href="/?sort=<?= e($sortKey) ?><?= $selectedCategory !== '' ? '&category=' . urlencode($selectedCategory) : '' ?><?= $selectedBoard !== '' ? '&board=' . urlencode($selectedBoard) : '' ?>"><?= $sort === $sortKey ? '● ' : '' ?><?= e($sortMeta['label']) ?></a>
              <?php endforeach; ?>
            </div>
            <div class="hero-stats">
              <div class="hero-stat"><div class="label">社区成员</div><div class="num"><?= $userCount ?></div><div class="note">公开资料与用户主页已经完整启用。</div></div>
              <div class="hero-stat"><div class="label">置顶帖子</div><div class="num"><?= $stickyCount ?></div><div class="note">优先进入首页前列与重点曝光位。</div></div>
              <div class="hero-stat"><div class="label">精华帖子</div><div class="num"><?= $featuredCount ?></div><div class="note">为更高质量的内容提供额外背书。</div></div>
              <div class="hero-stat"><div class="label">论坛版块</div><div class="num"><?= $boardCount ?></div><div class="note">支持按分类或版块继续浏览。</div></div>
            </div>
          </div>
          <div class="hero-art <?= e(implode(' ', array_filter([$heroIsUnbound ? 'hero-art--unbound' : null, $homeHasSparseData ? 'hero-art--sparse-data' : null]))) ?>">
            <div class="hero-art-top">
              <span class="badge">首页主视觉位</span>
              <span class="badge soft"><?= $heroPost ? ((int) ($heroPost['is_sticky'] ?? 0) === 1 ? '置顶中' : '已绑定') : '等待绑定' ?></span>
            </div>
            <div class="hero-art-bottom">
              <div class="kicker"><?= e($homeSlotDefs['hero']['label']) ?></div>
              <div class="title"><?= e($heroPost['title'] ?? '首页主视觉预留位') ?></div>
              <div class="text"><?= e($heroPost ? excerpt($heroPost['content'], 56) : '先把首页第一眼的内容落点稳住，等真正的重点帖子接入后再自然顶上来。') ?></div>
              <?php if ($heroPost): ?><div class="muted hero-art-note" style="margin-top:10px;">当前主视觉文案<?= $heroUsesCustomTitle || $heroUsesCustomBody ? '做了轻量覆盖' : '跟随当前绑定帖子' ?>。</div><?php else: ?><div class="muted hero-art-note" style="margin-top:10px;">当前还没有绑定专属主视觉，先保留一个更稳的首页落点，等运营位接入时不会突然失衡。</div><?php endif; ?>
              <div class="chips hero-art-chips">
                <?php if ($heroPost): ?>
                  <span class="chip"><?= e(board_badge($heroPost)) ?></span>
                  <span class="chip"><?= (int) $heroPost['like_count'] ?> 赞</span>
                  <span class="chip"><?= (int) $heroPost['comment_count'] ?> 回复</span>
                  <span class="chip"><?= (int) ($heroPost['view_count'] ?? 0) ?> 浏览</span>
                <?php else: ?>
                  <span class="chip">分类 / 版块</span>
                  <span class="chip"><?= e($homeCopy['home.hero.tag_primary']) ?></span>
                  <span class="chip"><?= e($homeCopy['home.hero.tag_secondary']) ?></span>
                <?php endif; ?>
              </div>
              <?php if ($heroPost): ?>
                <div class="hero-art-link-row" style="margin-top:12px;"><a class="inline-link" href="/post.php?id=<?= (int) $heroPost['id'] ?>">进入 Hero 帖子</a></div>
              <?php endif; ?>
            </div>
          </div>
        </div>
      </div>

      <div class="right-stack">
        <section class="glass section-card home-side-card home-forum-map-card">
          <div class="section-kicker">社区地图</div>
          <div class="section-title">从这里进入社区地图</div>
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

        <section class="glass section-card pulse-feed-card home-side-card">
          <div class="section-kicker">即时脉冲</div>
          <div class="section-title">刚刚发生了什么</div>
          <div class="feed-list">
            <?php if (!$feedPosts): ?>
              <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">刚刚</div><div class="text">这条动态位还在等第一批能把社区气氛真正带起来的内容接入。</div></div></div>
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
      <div class="row-mid-main-stack">
        <section class="glass section-card home-feature-block">
          <div class="section-kicker">首页焦点</div>
          <div class="section-title">今天最值得先看的内容</div>
          <div class="focus-grid">
            <?php render_focus_card($focusPosts['focus_one'], 'focus_one', $homeCopy, $recommendGroups, '焦点内容位 1', '适合承接当前最值得优先展示的重点帖子。'); ?>
            <?php render_focus_card($focusPosts['focus_two'], 'focus_two', $homeCopy, $recommendGroups, '焦点内容位 2', '适合放活动帖、征集帖或版本说明帖。'); ?>
            <?php render_focus_card($focusPosts['focus_three'], 'focus_three', $homeCopy, $recommendGroups, '焦点内容位 3', '适合补充首页中段的持续浏览入口。'); ?>
          </div>
        </section>

        <?php if ($showTimeHotlist): ?>
        <section class="glass section-card tag-cloud-card home-feature-block">
          <div class="section-kicker">时间热榜</div>
          <div class="section-title">热度，不只看一瞬间</div>
          <div class="tag-cloud">
            <span class="tag-cloud-item a">#24小时热榜</span>
            <span class="tag-cloud-item b">#7天热榜</span>
            <span class="tag-cloud-item c">#30天热榜</span>
            <span class="tag-cloud-item a">#热度 = 点赞 + 回复 + 浏览</span>
          </div>
          <div class="list-stack">
            <?php foreach ($timeRangeBoards as $rangeKey => $rangeMeta): ?>
              <div class="author-item">
                <div class="author-row">
                  <div class="author-badge">⏱️</div>
                  <div class="author-main">
                    <div class="author-name"><?= e($rangeMeta['label']) ?></div>
                    <div class="meta"><?= !empty($timeRangeHotPosts[$rangeKey]) ? '按时间窗口统计的实时热度结果' : '这个时间窗口里的公开互动还在慢慢形成' ?></div>
                  </div>
                </div>
                <div class="rank-list" style="margin-top:12px;">
                  <?php if (empty($timeRangeHotPosts[$rangeKey])): ?>
                    <div class="rank-item"><div class="rank-row"><div class="rank-index">#0</div><div class="rank-main"><div class="rank-name">这一档热度还在形成中</div><div class="meta">等这个时间窗口里的公开互动继续累起来</div></div><div class="score">--</div></div></div>
                  <?php else: ?>
                    <?php foreach ($timeRangeHotPosts[$rangeKey] as $index => $hotPost): ?>
                      <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= $index + 1 ?></div><div class="rank-main"><div class="rank-name"><a class="inline-link" href="/post.php?id=<?= (int) $hotPost['id'] ?>"><?= e($hotPost['title']) ?></a></div><div class="meta">@<?= e($hotPost['username']) ?> · <?= (int) $hotPost['like_count'] ?> 赞 · <?= (int) $hotPost['comment_count'] ?> 回复 · <?= (int) ($hotPost['view_count'] ?? 0) ?> 浏览</div></div><div class="score"><?= (int) ($hotPost['like_count'] * ranking_weight('like') + $hotPost['comment_count'] * ranking_weight('comment') + $hotPost['view_count'] * ranking_weight('view')) ?></div></div></div>
                    <?php endforeach; ?>
                  <?php endif; ?>
                </div>
              </div>
            <?php endforeach; ?>
          </div>
        </section>
        <?php endif; ?>
      </div>

      <div class="row-mid-side-stack">
        <section class="glass section-card home-side-card">
          <div class="section-kicker">推荐分层</div>
          <div class="section-title">运营推荐分层</div>
          <div class="rank-list">
            <?php foreach ($recommendGroups as $groupKey => $groupMeta): ?>
              <?php $leadPost = $recommendedPools[$groupKey][0] ?? null; ?>
              <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= e(strtoupper(substr($groupKey, 0, 1))) ?></div><div class="rank-main"><div class="rank-name"><?= e($groupMeta['label']) ?></div><div class="meta"><?= e($leadPost ? $leadPost['title'] . ' · 优先级 ' . (int) ($leadPost['recommend_priority'] ?? 0) : '当前暂无优先内容') ?></div></div><div class="score"><?= count($recommendedPools[$groupKey]) ?>条</div></div></div>
            <?php endforeach; ?>
          </div>
        </section>

        <section class="glass section-card home-side-card">
          <div class="section-kicker">活跃版块</div>
          <div class="section-title">近 7 天最活跃讨论区</div>
          <div class="rank-list">
            <?php foreach ($activeBoardsHome as $index => $board): ?>
              <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= $index + 1 ?></div><div class="rank-main"><div class="rank-name"><a class="inline-link" href="/posts.php?board=<?= e($board['slug']) ?>"><?= e($board['name']) ?></a></div><div class="meta"><?= e($board['category_name']) ?> · 近 7 天浏览 <?= (int) ($board['total_views'] ?? 0) ?></div></div><div class="score"><?= (int) ($board['post_count'] ?? 0) ?>帖</div></div></div>
            <?php endforeach; ?>
            <?php if (!$activeBoardsHome): ?>
              <div class="rank-item"><div class="rank-row"><div class="rank-index">#0</div><div class="rank-main"><div class="rank-name">活跃版块还在形成中</div><div class="meta">等近 7 天公开内容继续累起来后会自然出现</div></div><div class="score">--</div></div></div>
            <?php endif; ?>
          </div>
        </section>

        <section class="glass section-card home-side-card home-snapshot-card">
          <div class="section-kicker">社区快照</div>
          <div class="section-title">当前社区状态</div>
          <div class="hero-stats compact-hero-stats admin-hero-stats" style="margin-top:16px;">
            <div class="hero-stat"><div class="label">公开帖子</div><div class="num small-num"><?= $postCount ?></div><div class="note">当前首页读取的公开内容总量</div></div>
            <div class="hero-stat"><div class="label">社区成员</div><div class="num small-num"><?= $userCount ?></div><div class="note">已注册成员数</div></div>
            <div class="hero-stat"><div class="label">论坛版块</div><div class="num small-num"><?= $boardCount ?></div><div class="note">当前可浏览版块</div></div>
          </div>
          <div class="quick-links" style="margin-top:18px;">
            <a class="quick-link" href="/posts.php?sort=hot"><strong>综合热度内容流</strong><span>优先查看当前互动更强的公开内容。</span></a>
            <a class="quick-link" href="/posts.php?sort=views"><strong>最多浏览内容流</strong><span>回看已经跑出阅读量的公开内容。</span></a>
          </div>
        </section>
      </div>
    </section>

    <section class="row-bottom">
      <section class="home-trending-zone">
        <div class="section-kicker">当前讨论焦点</div>
        <div class="section-large-head">最近讨论度更高的公开内容</div>
        <div class="section-large-desc">这里会优先展示当前更值得继续浏览的帖子，并把版块、热度和运营权重一起带出来。</div>
        <div class="ticker">🔥 当前内容流会综合参考推荐权重、互动热度与公开可见状态。</div>
        <div class="cards-3">
          <?php if (!$trendingPosts): ?>
            <?php for ($i = 1; $i <= 3; $i++): ?>
              <article class="glass game-card"><div class="game-cover alt<?= $i ?>"><div class="game-cover-top"><span class="small-chip a">内容位预留</span><span class="small-chip b">社区暖场</span></div><div class="game-cover-bottom"><div class="game-title">第 <?= $i ?> 个内容位正在等真实内容接上</div><div class="game-sub">再有几篇公开帖子沉下来，这里就会自然切成真正的内容卡</div></div></div><div class="game-body"><p>先把版面节奏稳住，不急着用模板味很重的假内容去填满；等真实帖子继续累积，这里会顺着社区状态自然接上。</p><div class="game-meta"><div>★ 实时读取</div><div style="color: var(--brand);">继续浏览首页</div></div></div></article>
            <?php endfor; ?>
          <?php else: ?>
            <?php foreach ($trendingPosts as $index => $post): ?>
              <article class="glass game-card">
                <?php if (!empty($post['image_path'])): ?>
                  <div class="game-cover image-cover"><img class="post-cover-image card-cover-image" src="<?= e(image_variant_public_path($post['image_path'], 'card')) ?>" alt="<?= e($post['title']) ?>" loading="lazy" decoding="async" fetchpriority="low"></div>
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
                  <div class="game-meta"><div><?= (int) $post['like_count'] ?> 赞 · <?= (int) $post['comment_count'] ?> 回复</div><div style="color: var(--brand);"><a href="/post.php?id=<?= (int) $post['id'] ?>">继续阅读</a></div></div>
                </div>
              </article>
            <?php endforeach; ?>
          <?php endif; ?>
        </div>
      </section>

      <div class="right-col-stack">
        <?php if ($showRecommendedAuthors): ?>
        <section class="glass section-card authors-card-shell home-side-card home-people-card">
          <div class="section-kicker">推荐作者</div>
          <div class="section-title">值得继续关注的创作者</div>
          <div class="author-list">
            <?php if (!$topAuthors): ?>
              <div class="author-item"><div class="author-row"><div class="author-badge">✨</div><div class="author-main"><div class="author-name">推荐作者视图还在形成中</div><div class="meta">等公开内容和互动再多一点，这里会自然切换成真实作者名单。</div></div><div class="score">预留中</div></div><p>当前还没有足够数据支撑稳定的推荐作者视图，先把这个位置安静留住，不让侧栏节奏塌掉。</p></div>
            <?php else: ?>
              <?php foreach (array_slice($topAuthors, 0, 3) as $author): ?>
                <div class="author-item">
                  <div class="author-row">
                    <div class="author-badge">🏅</div>
                    <div class="author-main">
                      <div class="author-name"><a class="inline-link" href="/user.php?id=<?= (int) $author['id'] ?>"><?= e($author['nickname']) ?></a> <span class="tiny-badge">创作者</span></div>
                      <div class="meta">@<?= e($author['username']) ?> · <?= (int) $author['post_count'] ?> 帖 · <?= (int) $author['total_views'] ?> 浏览</div>
                    </div>
                    <div class="score"><?= (int) $author['total_likes'] ?>赞</div>
                  </div>
                  <p>累计回复 <?= (int) $author['total_comments'] ?> · 最近发帖 <?= !empty($author['latest_post_at']) ? e(human_time($author['latest_post_at'])) : '暂无' ?></p>
                </div>
              <?php endforeach; ?>
            <?php endif; ?>
          </div>
        </section>
        <?php endif; ?>

        <?php if ($showTopViewed): ?>
        <section class="glass section-card top-rated-card-shell home-side-card home-top-viewed-card">
          <div class="section-kicker">高浏览内容</div>
          <div class="section-title">被最多人点开的内容</div>
          <div class="rank-list">
            <?php if (!$topPostsByViews): ?>
              <div class="rank-item"><div class="rank-row"><div class="rank-index">#0</div><div class="rank-main"><div class="rank-name">高浏览内容还在形成中</div><div class="meta">等真实浏览量继续累起来，这里会自然切成稳定榜单</div></div><div class="score">预留中</div></div></div>
            <?php else: ?>
              <?php foreach ($topPostsByViews as $index => $topPost): ?>
                <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= $index + 1 ?></div><div class="rank-main"><div class="rank-name"><a class="inline-link" href="/post.php?id=<?= (int) $topPost['id'] ?>"><?= e($topPost['title']) ?></a></div><div class="meta">@<?= e($topPost['username']) ?> · <?= (int) $topPost['like_count'] ?> 赞 · <?= (int) $topPost['comment_count'] ?> 回复</div></div><div class="score"><?= (int) ($topPost['view_count'] ?? 0) ?>阅</div></div></div>
              <?php endforeach; ?>
            <?php endif; ?>
          </div>
        </section>
        <?php endif; ?>
      </div>
    </section>
  </main>
<?php render_footer(); ?>
