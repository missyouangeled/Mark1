<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$posts = db()->query(
    'SELECT p.id, p.title, p.content, p.created_at, u.nickname, u.username
     FROM posts p
     INNER JOIN pulsenest_users u ON u.id = p.user_id
     ORDER BY p.created_at DESC, p.id DESC'
)->fetchAll();

render_header('PulseNest · 帖子列表', $user);
?>
  <div class="shell page-shell">
    <section class="card page-hero">
      <div>
        <div class="kicker">Posts Feed</div>
        <h1>帖子列表</h1>
        <p class="page-desc">这里直接从 MySQL 读取帖子数据，按发布时间倒序展示。</p>
      </div>
      <a class="follow-btn" href="<?= $user ? '/create-post.php' : '/login.php' ?>"><?= $user ? '去发帖' : '登录后发帖' ?></a>
    </section>

    <section class="list-stack posts-list-page">
      <?php if (!$posts): ?>
        <div class="card panel-card empty-inline">现在还没有帖子，先去发布第一篇。</div>
      <?php else: ?>
        <?php foreach ($posts as $post): ?>
          <article class="card panel-card list-card">
            <div class="post-head">
              <div class="user">
                <div class="user-avatar"></div>
                <div>
                  <div style="font-weight: 700;"><?= e($post['nickname']) ?></div>
                  <div class="muted" style="margin-top: 4px; font-size: 14px;">@<?= e($post['username']) ?> · <?= e(human_time($post['created_at'])) ?></div>
                </div>
              </div>
              <a class="pill-btn" href="/post.php?id=<?= (int) $post['id'] ?>">查看详情</a>
            </div>
            <h2 class="post-title small"><a href="/post.php?id=<?= (int) $post['id'] ?>"><?= e($post['title']) ?></a></h2>
            <p class="post-text compact"><?= nl2br(e(excerpt($post['content'], 220))) ?></p>
          </article>
        <?php endforeach; ?>
      <?php endif; ?>
    </section>
  </div>
<?php render_footer(); ?>