<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$flash = flash_get();
$forum = fetch_forum_structure();

$search = trim($_GET['q'] ?? '');
$categorySlug = trim($_GET['category'] ?? '');
$boardSlug = trim($_GET['board'] ?? '');

$where = [];
$params = [];

if ($search !== '') {
    $where[] = '(p.title LIKE :search OR p.content LIKE :search)';
    $params['search'] = '%' . $search . '%';
}
if ($categorySlug !== '') {
    $where[] = 'fc.slug = :category_slug';
    $params['category_slug'] = $categorySlug;
}
if ($boardSlug !== '') {
    $where[] = 'fb.slug = :board_slug';
    $params['board_slug'] = $boardSlug;
}

$sql = 'SELECT p.id, p.user_id, p.title, p.content, p.image_path, p.created_at,
               u.nickname, u.username, u.avatar_path,
               fb.id AS board_id, fb.name AS board_name, fb.slug AS board_slug,
               fc.id AS category_id, fc.name AS category_name, fc.slug AS category_slug,
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

$sql .= ' ORDER BY p.created_at DESC, p.id DESC';
$stmt = db()->prepare($sql);
$stmt->execute($params);
$posts = $stmt->fetchAll();

$postCount = count($posts);
$authorCount = count(array_unique(array_map(static fn ($post) => $post['username'], $posts)));
$latestPost = $posts[0] ?? null;
$currentBoardLabel = '全站帖子';
if ($boardSlug !== '') {
    foreach ($forum as $category) {
        foreach ($category['boards'] as $board) {
            if ($board['slug'] === $boardSlug) {
                $currentBoardLabel = $category['name'] . ' / ' . $board['name'];
                break 2;
            }
        }
    }
} elseif ($categorySlug !== '') {
    foreach ($forum as $category) {
        if ($category['slug'] === $categorySlug) {
            $currentBoardLabel = $category['name'];
            break;
        }
    }
}

render_header('PulseNest · 帖子列表', $user, [
    'searchText' => $search !== '' ? '🔎 正在搜索：' . $search : '🔎 可按标题 / 正文搜索，也可按分类 / 版块浏览',
]);
?>
  <main class="shell page-shell nebula-page-shell posts-page">
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>

    <section class="glass nebula-hero nebula-hero-split">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始01 · 内容流列表页</div>
        <h1>按分类 / 版块浏览，也能直接搜标题和正文，把内容流做成真正的论坛面。</h1>
        <p class="page-desc nebula-desc">现在列表页已经不只是倒序发帖流：支持按论坛分类、版块筛选，也支持标题 / 正文关键词搜索。</p>
        <form class="filter-form" method="get" action="/posts.php">
          <div class="filter-grid two-up">
            <div class="field grow-field">
              <label>搜索帖子</label>
              <input class="input" name="q" value="<?= e($search) ?>" placeholder="搜标题或正文关键词" />
            </div>
            <div class="field grow-field">
              <label>分类</label>
              <select class="input" name="category">
                <option value="">全部分类</option>
                <?php foreach ($forum as $category): ?>
                  <option value="<?= e($category['slug']) ?>" <?= $categorySlug === $category['slug'] ? 'selected' : '' ?>><?= e($category['name']) ?></option>
                <?php endforeach; ?>
              </select>
            </div>
            <div class="field grow-field">
              <label>版块</label>
              <select class="input" name="board">
                <option value="">全部版块</option>
                <?php foreach ($forum as $category): ?>
                  <?php foreach ($category['boards'] as $board): ?>
                    <option value="<?= e($board['slug']) ?>" <?= $boardSlug === $board['slug'] ? 'selected' : '' ?>><?= e($category['name']) ?> / <?= e($board['name']) ?></option>
                  <?php endforeach; ?>
                <?php endforeach; ?>
              </select>
            </div>
            <div class="filter-actions">
              <button class="pill-btn solid" type="submit">筛选 / 搜索</button>
              <a class="pill-btn" href="/posts.php">清空条件</a>
            </div>
          </div>
        </form>
        <div class="hero-stats compact-hero-stats">
          <div class="hero-stat"><div class="label">当前视图</div><div class="num small-num"><?= e($currentBoardLabel) ?></div><div class="note">支持分类或版块钻取</div></div>
          <div class="hero-stat"><div class="label">结果数</div><div class="num"><?= $postCount ?></div><div class="note">符合当前筛选 / 搜索条件</div></div>
          <div class="hero-stat"><div class="label">活跃作者</div><div class="num"><?= $authorCount ?></div><div class="note">当前结果里出现的成员</div></div>
        </div>
      </div>

      <aside class="glass side-card nebula-side-panel">
        <div class="section-kicker">Forum Map</div>
        <div class="forum-pills">
          <?php foreach ($forum as $category): ?>
            <a class="forum-pill" href="/posts.php?category=<?= e($category['slug']) ?>"><?= e($category['name']) ?></a>
          <?php endforeach; ?>
        </div>
        <div class="feed-list dense-feed-list">
          <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">检索维度</div><div class="text">标题 / 正文全文关键词搜索已启用。</div></div></div>
          <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">浏览维度</div><div class="text">可先看分类，再落到具体版块。</div></div></div>
          <div class="feed-item"><div class="pulse-dot"></div><div><div class="time">最新帖子</div><div class="text"><?= e($latestPost['title'] ?? '还没有任何帖子，等第一篇把这里点亮。') ?></div></div></div>
        </div>
      </aside>
    </section>

    <section class="nebula-section-grid posts-layout-grid">
      <div class="list-stack posts-list-page">
        <?php if (!$posts): ?>
          <div class="glass panel-card empty-inline nebula-empty">没有搜到符合条件的帖子，换个关键词或切换版块试试。</div>
        <?php else: ?>
          <?php foreach ($posts as $index => $post): ?>
            <article class="glass panel-card list-card nebula-list-card">
              <div class="list-card-topline">
                <span class="small-chip a">#<?= $index + 1 ?> 内容位</span>
                <span class="small-chip b"><?= e(human_time($post['created_at'])) ?></span>
              </div>
              <div class="post-head">
                <div class="user">
                  <?= render_avatar($post, 'user-avatar') ?>
                  <div>
                    <div class="user-name-line"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>"><?= e($post['nickname']) ?></a> <span class="tiny-badge">@<?= e($post['username']) ?></span></div>
                    <div class="muted" style="margin-top: 4px; font-size: 14px;"><?= e(board_badge($post)) ?> · 发布于 <?= e(substr($post['created_at'], 0, 16)) ?></div>
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
                  <span class="chip"><?= e(board_badge($post)) ?></span>
                </div>
                <a class="link" href="/post.php?id=<?= (int) $post['id'] ?>">继续阅读 →</a>
              </div>
            </article>
          <?php endforeach; ?>
        <?php endif; ?>
      </div>

      <aside class="right-col-stack">
        <?php foreach ($forum as $category): ?>
          <section class="glass section-card">
            <div class="section-kicker">Category</div>
            <div class="section-title small-section-title"><?= e($category['name']) ?></div>
            <div class="list-stack compact-link-stack">
              <?php foreach ($category['boards'] as $board): ?>
                <a class="quick-link" href="/posts.php?board=<?= e($board['slug']) ?>">
                  <strong><?= e($board['name']) ?></strong>
                  <span><?= e($board['description']) ?> · <?= (int) $board['post_count'] ?> 帖</span>
                </a>
              <?php endforeach; ?>
            </div>
          </section>
        <?php endforeach; ?>
      </aside>
    </section>
  </main>
<?php render_footer(); ?>