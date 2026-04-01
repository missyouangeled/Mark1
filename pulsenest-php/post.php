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

render_header('PulseNest · 帖子详情', $user);
?>
  <div class="shell page-shell narrow">
    <?php if (!$post): ?>
      <section class="card panel-card empty-inline">没有找到这篇帖子。<a class="link" href="/posts.php">返回帖子列表</a></section>
    <?php else: ?>
      <article class="card detail-card">
        <div class="post-head">
          <div class="user">
            <div class="user-avatar"></div>
            <div>
              <div style="font-weight: 700;"><?= e($post['nickname']) ?></div>
              <div class="muted" style="margin-top: 4px; font-size: 14px;">@<?= e($post['username']) ?> · <?= e(substr($post['created_at'], 0, 16)) ?></div>
            </div>
          </div>
          <a class="pill-btn" href="/posts.php">返回列表</a>
        </div>
        <h1 class="post-title"><?= e($post['title']) ?></h1>
        <div class="article-meta">发布邮箱：<?= e($post['email']) ?></div>
        <div class="article-body"><?= nl2br(e($post['content'])) ?></div>
      </article>
    <?php endif; ?>
  </div>
<?php render_footer(); ?>