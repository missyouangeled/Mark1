<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$postId = (int) ($_GET['id'] ?? 0);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = $_POST['action'] ?? '';
    $actor = ensure_logged_in();

    if ($action === 'comment') {
        $content = trim($_POST['content'] ?? '');
        $parentId = (int) ($_POST['parent_id'] ?? 0);
        if ($content === '') {
            flash_set('error', '回复内容不能为空。');
        } elseif (mb_strlen($content) < 2) {
            flash_set('error', '回复至少写 2 个字。');
        } else {
            $validParentId = null;
            if ($parentId > 0) {
                $parentStmt = db()->prepare('SELECT id FROM comments WHERE id = :id AND post_id = :post_id LIMIT 1');
                $parentStmt->execute(['id' => $parentId, 'post_id' => $postId]);
                $validParentId = $parentStmt->fetchColumn() ? $parentId : null;
            }

            $stmt = db()->prepare('INSERT INTO comments (post_id, user_id, parent_id, content) VALUES (:post_id, :user_id, :parent_id, :content)');
            $stmt->execute([
                'post_id' => $postId,
                'user_id' => $actor['id'],
                'parent_id' => $validParentId,
                'content' => $content,
            ]);
            flash_set('success', $validParentId ? '回复已发送。' : '评论已发布。');
        }
    }

    if ($action === 'toggle_like') {
        $checkStmt = db()->prepare('SELECT id FROM post_likes WHERE post_id = :post_id AND user_id = :user_id LIMIT 1');
        $checkStmt->execute(['post_id' => $postId, 'user_id' => $actor['id']]);
        $likeId = $checkStmt->fetchColumn();
        if ($likeId) {
            $deleteStmt = db()->prepare('DELETE FROM post_likes WHERE id = :id');
            $deleteStmt->execute(['id' => $likeId]);
            flash_set('success', '已取消点赞。');
        } else {
            $insertStmt = db()->prepare('INSERT INTO post_likes (post_id, user_id) VALUES (:post_id, :user_id)');
            $insertStmt->execute(['post_id' => $postId, 'user_id' => $actor['id']]);
            flash_set('success', '点赞成功，热度 +1。');
        }
    }

    redirect_to('/post.php?id=' . $postId);
}

$flash = flash_get();
$stmt = db()->prepare(
    'SELECT p.id, p.user_id, p.title, p.content, p.image_path, p.created_at,
            u.nickname, u.username, u.email, u.avatar_path, u.bio,
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
     WHERE p.id = :id
     LIMIT 1'
);
$stmt->execute(['id' => $postId]);
$post = $stmt->fetch();

$likedByCurrentUser = false;
if ($post && $user) {
    $likedStmt = db()->prepare('SELECT 1 FROM post_likes WHERE post_id = :post_id AND user_id = :user_id LIMIT 1');
    $likedStmt->execute(['post_id' => $postId, 'user_id' => $user['id']]);
    $likedByCurrentUser = (bool) $likedStmt->fetchColumn();
}

$comments = [];
if ($post) {
    $commentsStmt = db()->prepare(
        'SELECT c.id, c.parent_id, c.content, c.created_at,
                u.id AS user_id, u.nickname, u.username, u.avatar_path
         FROM comments c
         INNER JOIN pulsenest_users u ON u.id = c.user_id
         WHERE c.post_id = :post_id
         ORDER BY c.created_at ASC, c.id ASC'
    );
    $commentsStmt->execute(['post_id' => $postId]);
    $comments = $commentsStmt->fetchAll();
}

$commentTree = [];
$commentLookup = [];
foreach ($comments as $comment) {
    $comment['children'] = [];
    $commentLookup[$comment['id']] = $comment;
}
$rootIds = [];
foreach (array_keys($commentLookup) as $commentId) {
    $parentId = (int) ($commentLookup[$commentId]['parent_id'] ?? 0);
    if ($parentId > 0 && isset($commentLookup[$parentId])) {
        $commentLookup[$parentId]['children'][] = &$commentLookup[$commentId];
    } else {
        $rootIds[] = $commentId;
    }
}
foreach ($rootIds as $rootId) {
    $commentTree[] = $commentLookup[$rootId];
}

if (!$post) {
    http_response_code(404);
}

render_header('PulseNest · 帖子详情', $user, [
    'searchText' => '🔎 搜索详情上下文、作者、返回相关帖子',
]);
?>
  <main class="shell page-shell nebula-page-shell narrow-post-shell">
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>

    <?php if (!$post): ?>
      <section class="glass panel-card empty-inline nebula-empty">没有找到这篇帖子。<a class="link" href="/posts.php">返回帖子列表</a></section>
    <?php else: ?>
      <section class="glass nebula-hero detail-hero">
        <div class="detail-hero-head">
          <div>
            <div class="brand-chip">纳达尔星项目 · 星云初始01 · 帖子详情页</div>
            <h1><?= e($post['title']) ?></h1>
            <p class="page-desc nebula-desc">详情页已经接上真实互动：可以点赞、评论、回复，也能顺着作者信息进入用户主页。</p>
          </div>
          <div class="hero-actions-row detail-hero-actions">
            <a class="pill-btn" href="/posts.php">返回列表</a>
            <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/login.php' ?>"><?= $user ? '继续发帖' : '登录后发帖' ?></a>
          </div>
        </div>
        <div class="hero-stats compact-hero-stats detail-stats">
          <div class="hero-stat"><div class="label">作者</div><div class="num small-num"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>"><?= e($post['nickname']) ?></a></div><div class="note">@<?= e($post['username']) ?></div></div>
          <div class="hero-stat"><div class="label">点赞</div><div class="num small-num"><?= (int) $post['like_count'] ?></div><div class="note">已有成员为这篇内容加热</div></div>
          <div class="hero-stat"><div class="label">回复</div><div class="num small-num"><?= (int) $post['comment_count'] ?></div><div class="note"><?= $user ? '你现在可以直接参与讨论' : '登录后可评论和点赞' ?></div></div>
        </div>
      </section>

      <div class="nebula-section-grid detail-grid detail-grid-wide">
        <div class="detail-main-stack">
          <article class="glass detail-card nebula-detail-card">
            <div class="post-head">
              <div class="user">
                <?= render_avatar($post, 'user-avatar large') ?>
                <div>
                  <div class="user-name-line"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>"><?= e($post['nickname']) ?></a> <span class="tiny-badge">@<?= e($post['username']) ?></span></div>
                  <div class="muted" style="margin-top: 6px; font-size: 14px;">发布于 <?= e(substr($post['created_at'], 0, 16)) ?></div>
                </div>
              </div>
              <span class="small-chip a">文章详情</span>
            </div>
            <?php if (!empty($post['image_path'])): ?>
              <div class="post-cover-wrap"><img class="post-cover-image detail-cover" src="<?= e(asset_url($post['image_path'])) ?>" alt="<?= e($post['title']) ?>"></div>
            <?php endif; ?>
            <div class="article-meta">作者邮箱：<?= e($post['email']) ?></div>
            <?php if (!empty($post['bio'])): ?><div class="article-meta">作者简介：<?= e($post['bio']) ?></div><?php endif; ?>
            <div class="article-body"><?= nl2br(e($post['content'])) ?></div>
            <div class="action-bar">
              <?php if ($user): ?>
                <form method="post" class="inline-form">
                  <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                  <input type="hidden" name="action" value="toggle_like">
                  <button class="pill-btn <?= $likedByCurrentUser ? 'solid' : '' ?>" type="submit"><?= e(like_button_label($likedByCurrentUser, (int) $post['like_count'])) ?></button>
                </form>
              <?php else: ?>
                <a class="pill-btn" href="/login.php">登录后点赞 · <?= (int) $post['like_count'] ?></a>
              <?php endif; ?>
              <span class="meta-pill"><?= (int) $post['comment_count'] ?> 条评论</span>
            </div>
          </article>

          <section class="glass panel-card comment-panel">
            <div class="section-kicker">Discussion</div>
            <div class="side-head"><h3>评论区 / 回复区</h3></div>

            <?php if ($user): ?>
              <form class="form" method="post">
                <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                <input type="hidden" name="action" value="comment">
                <input type="hidden" name="parent_id" value="0">
                <div class="field">
                  <label>写下你的回复</label>
                  <textarea class="textarea small-textarea" name="content" placeholder="聊聊你的看法、补充或反驳"></textarea>
                </div>
                <button class="submit" type="submit">发布评论</button>
              </form>
            <?php else: ?>
              <div class="notice">登录后就能参与评论和回复。<a class="link" href="/login.php">去登录</a></div>
            <?php endif; ?>

            <div class="comment-list">
              <?php if (!$commentTree): ?>
                <div class="empty-inline nebula-empty">还没有人回复，来做第一个把讨论点亮的人。</div>
              <?php else: ?>
                <?php foreach ($commentTree as $comment): ?>
                  <article class="comment-card">
                    <div class="comment-head">
                      <div class="user">
                        <?= render_avatar($comment, 'avatar') ?>
                        <div>
                          <div class="user-name-line"><a class="inline-link" href="/user.php?id=<?= (int) $comment['user_id'] ?>"><?= e($comment['nickname']) ?></a> <span class="tiny-badge">@<?= e($comment['username']) ?></span></div>
                          <div class="muted"><?= e(human_time($comment['created_at'])) ?></div>
                        </div>
                      </div>
                    </div>
                    <div class="comment-body"><?= nl2br(e($comment['content'])) ?></div>
                    <?php if ($user): ?>
                      <details class="reply-box">
                        <summary>回复这条评论</summary>
                        <form class="form reply-form" method="post">
                          <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                          <input type="hidden" name="action" value="comment">
                          <input type="hidden" name="parent_id" value="<?= (int) $comment['id'] ?>">
                          <textarea class="textarea small-textarea" name="content" placeholder="继续展开聊"></textarea>
                          <button class="submit" type="submit">发送回复</button>
                        </form>
                      </details>
                    <?php endif; ?>

                    <?php if (!empty($comment['children'])): ?>
                      <div class="reply-list">
                        <?php foreach ($comment['children'] as $reply): ?>
                          <article class="comment-card reply-card">
                            <div class="comment-head">
                              <div class="user">
                                <?= render_avatar($reply, 'avatar-sm') ?>
                                <div>
                                  <div class="user-name-line"><a class="inline-link" href="/user.php?id=<?= (int) $reply['user_id'] ?>"><?= e($reply['nickname']) ?></a> <span class="tiny-badge">@<?= e($reply['username']) ?></span></div>
                                  <div class="muted"><?= e(human_time($reply['created_at'])) ?></div>
                                </div>
                              </div>
                            </div>
                            <div class="comment-body"><?= nl2br(e($reply['content'])) ?></div>
                          </article>
                        <?php endforeach; ?>
                      </div>
                    <?php endif; ?>
                  </article>
                <?php endforeach; ?>
              <?php endif; ?>
            </div>
          </section>
        </div>

        <aside class="right-col-stack">
          <section class="glass section-card">
            <div class="section-kicker">Author Snapshot</div>
            <div class="author-item detail-author-card">
              <div class="author-row">
                <div class="author-badge">🌌</div>
                <div class="author-main">
                  <div class="author-name"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>"><?= e($post['nickname']) ?></a></div>
                  <div class="meta">@<?= e($post['username']) ?></div>
                </div>
                <div class="score">LIVE</div>
              </div>
              <p><?= e($post['bio'] ?: '这个作者还没有写简介，但主页已经可以点进去看最近帖子。') ?></p>
            </div>
          </section>

          <section class="glass section-card">
            <div class="section-kicker">Quick Jump</div>
            <div class="quick-links">
              <a class="quick-link" href="/posts.php">返回帖子列表</a>
              <a class="quick-link" href="/account.php">会员中心</a>
              <a class="quick-link" href="/user.php?id=<?= (int) $post['user_id'] ?>">作者主页</a>
            </div>
          </section>
        </aside>
      </div>
    <?php endif; ?>
  </main>
<?php render_footer(); ?>
