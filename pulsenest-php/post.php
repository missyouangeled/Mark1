<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$postId = (int) ($_GET['id'] ?? 0);

$postStmt = db()->prepare(
    'SELECT p.id, p.user_id, p.board_id, p.title, p.content, p.image_path, p.status, p.view_count, p.created_at, p.updated_at,
            u.nickname, u.username, u.email, u.avatar_path, u.bio,
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
     ) c ON c.post_id = p.id
     WHERE p.id = :id
     LIMIT 1'
);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $commentMinLength = max(1, site_int_setting('site.comment_content_min_length', 2));
    verify_csrf();
    $action = $_POST['action'] ?? '';
    $actor = ensure_logged_in();

    $postStmt->execute(['id' => $postId]);
    $post = $postStmt->fetch();
    if (!$post) {
        http_response_code(404);
        exit('Post not found.');
    }

    if ($action === 'comment') {
        $content = trim($_POST['content'] ?? '');
        $parentId = (int) ($_POST['parent_id'] ?? 0);
        if (site_setting_enabled('site.readonly_mode_enabled', false) && !can_moderate_content($actor)) {
            flash_set('error', '当前站点处于只读模式，暂时关闭普通用户评论。');
        } elseif ($content === '') {
            flash_set('error', '回复内容不能为空。');
        } elseif (mb_strlen($content) < $commentMinLength) {
            flash_set('error', '回复至少写 ' . $commentMinLength . ' 个字。');
        } else {
            $parentComment = null;
            $validParentId = null;
            if ($parentId > 0) {
                $parentStmt = db()->prepare('SELECT id, user_id, content FROM comments WHERE id = :id AND post_id = :post_id LIMIT 1');
                $parentStmt->execute(['id' => $parentId, 'post_id' => $postId]);
                $parentComment = $parentStmt->fetch() ?: null;
                $validParentId = $parentComment ? $parentId : null;
            }

            $commentStatus = (can_moderate_content($actor) || !site_setting_enabled('site.comment_moderation_enabled', false)) ? 'approved' : 'pending';
            $stmt = db()->prepare('INSERT INTO comments (post_id, user_id, parent_id, content, status) VALUES (:post_id, :user_id, :parent_id, :content, :status)');
            $stmt->execute([
                'post_id' => $postId,
                'user_id' => $actor['id'],
                'parent_id' => $validParentId,
                'content' => $content,
                'status' => $commentStatus,
            ]);
            $newCommentId = (int) db()->lastInsertId();
            if ($commentStatus === 'approved') {
                create_reply_notifications($post, $parentComment, (int) $actor['id'], $newCommentId);
            }
            flash_set('success', $commentStatus === 'approved'
                ? ($validParentId ? '回复已发送，并已推送站内提醒。' : '评论已发布，并已推送站内提醒。')
                : '评论已提交审核，审核通过后才会公开显示。');
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
            create_post_like_notification($post, (int) $actor['id']);
            flash_set('success', '点赞成功，热度 +1，并已通知作者。');
        }
    }

    if ($action === 'toggle_comment_like') {
        $commentId = (int) ($_POST['comment_id'] ?? 0);
        $commentStmt = db()->prepare('SELECT id, user_id, content FROM comments WHERE id = :id AND post_id = :post_id LIMIT 1');
        $commentStmt->execute(['id' => $commentId, 'post_id' => $postId]);
        $comment = $commentStmt->fetch();
        if (!$comment) {
            flash_set('error', '没有找到要点赞的评论。');
        } else {
            $checkStmt = db()->prepare('SELECT id FROM comment_likes WHERE comment_id = :comment_id AND user_id = :user_id LIMIT 1');
            $checkStmt->execute(['comment_id' => $commentId, 'user_id' => $actor['id']]);
            $commentLikeId = $checkStmt->fetchColumn();
            if ($commentLikeId) {
                $deleteStmt = db()->prepare('DELETE FROM comment_likes WHERE id = :id');
                $deleteStmt->execute(['id' => $commentLikeId]);
                flash_set('success', '已取消对评论的点赞。');
            } else {
                $insertStmt = db()->prepare('INSERT INTO comment_likes (comment_id, user_id) VALUES (:comment_id, :user_id)');
                $insertStmt->execute(['comment_id' => $commentId, 'user_id' => $actor['id']]);
                create_comment_like_notification($comment, $postId, (int) $actor['id']);
                flash_set('success', '评论点赞成功，并已通知评论作者。');
            }
        }
    }

    if ($action === 'report_post') {
        if (!site_setting_enabled('site.reporting_enabled', true)) {
            flash_set('error', '当前站点暂时关闭举报入口。');
        } elseif ((int) $actor['id'] === (int) ($post['user_id'] ?? 0)) {
            flash_set('error', '不能举报自己发布的帖子。');
        } else {
            $reason = trim((string) ($_POST['reason'] ?? 'other'));
            $detail = trim((string) ($_POST['detail'] ?? ''));
            $result = create_report((int) $actor['id'], 'post', (int) $post['id'], (int) $post['id'], null, $reason, $detail);
            if ($result['ok']) {
                log_moderation_action((int) $actor['id'], 'report_created', 'post_report', (int) ($result['id'] ?? 0), '帖子《' . $post['title'] . '》 · ' . report_reason_label($reason));
                flash_set('success', $result['message']);
            } else {
                flash_set('error', $result['message']);
            }
        }
    }

    if ($action === 'delete_post') {
        if (!can_manage_post($actor, $post)) {
            http_response_code(403);
            exit('Forbidden');
        }
        $deletePost = db()->prepare('DELETE FROM posts WHERE id = :id LIMIT 1');
        $deletePost->execute(['id' => $postId]);
        delete_uploaded_asset($post['image_path'] ?? null);
        log_moderation_action((int) $actor['id'], 'post_deleted', 'post', $postId, '《' . $post['title'] . '》');
        flash_set('success', '帖子已删除。');
        redirect_to('/posts.php');
    }

    if ($action === 'update_comment') {
        $commentId = (int) ($_POST['comment_id'] ?? 0);
        $content = trim($_POST['content'] ?? '');
        $commentStmt = db()->prepare('SELECT id, post_id, user_id FROM comments WHERE id = :id AND post_id = :post_id LIMIT 1');
        $commentStmt->execute(['id' => $commentId, 'post_id' => $postId]);
        $comment = $commentStmt->fetch();
        if (!$comment) {
            flash_set('error', '没有找到要编辑的评论。');
        } elseif (!can_manage_comment($actor, $comment)) {
            http_response_code(403);
            exit('Forbidden');
        } elseif ($content === '' || mb_strlen($content) < 2) {
            flash_set('error', '评论至少写 2 个字。');
        } else {
            $updateStmt = db()->prepare('UPDATE comments SET content = :content WHERE id = :id');
            $updateStmt->execute(['content' => $content, 'id' => $commentId]);
            flash_set('success', '评论已更新。');
        }
    }

    if ($action === 'report_comment') {
        if (!site_setting_enabled('site.reporting_enabled', true)) {
            flash_set('error', '当前站点暂时关闭举报入口。');
        } else {
            $commentId = (int) ($_POST['comment_id'] ?? 0);
            $commentStmt = db()->prepare('SELECT id, post_id, user_id, content FROM comments WHERE id = :id AND post_id = :post_id LIMIT 1');
            $commentStmt->execute(['id' => $commentId, 'post_id' => $postId]);
            $comment = $commentStmt->fetch();
            if (!$comment) {
                flash_set('error', '没有找到要举报的评论。');
            } elseif ((int) $actor['id'] === (int) ($comment['user_id'] ?? 0)) {
                flash_set('error', '不能举报自己的评论。');
            } else {
                $reason = trim((string) ($_POST['reason'] ?? 'other'));
                $detail = trim((string) ($_POST['detail'] ?? ''));
                $result = create_report((int) $actor['id'], 'comment', (int) $comment['id'], $postId, (int) $comment['id'], $reason, $detail);
                if ($result['ok']) {
                    log_moderation_action((int) $actor['id'], 'report_created', 'comment_report', (int) ($result['id'] ?? 0), '评论 #' . (int) $comment['id'] . ' · ' . report_reason_label($reason));
                    flash_set('success', $result['message']);
                } else {
                    flash_set('error', $result['message']);
                }
            }
        }
    }

    if ($action === 'delete_comment') {
        $commentId = (int) ($_POST['comment_id'] ?? 0);
        $commentStmt = db()->prepare('SELECT id, post_id, user_id FROM comments WHERE id = :id AND post_id = :post_id LIMIT 1');
        $commentStmt->execute(['id' => $commentId, 'post_id' => $postId]);
        $comment = $commentStmt->fetch();
        if (!$comment) {
            flash_set('error', '没有找到要删除的评论。');
        } elseif (!can_manage_comment($actor, $comment)) {
            http_response_code(403);
            exit('Forbidden');
        } else {
            $deleteStmt = db()->prepare('DELETE FROM comments WHERE id = :id');
            $deleteStmt->execute(['id' => $commentId]);
            log_moderation_action((int) $actor['id'], 'comment_deleted', 'comment', $commentId, excerpt($comment['content'] ?? '', 80));
            flash_set('success', '评论已删除。');
        }
    }

    redirect_to('/post.php?id=' . $postId);
}

$flash = flash_get();
$postStmt->execute(['id' => $postId]);
$post = $postStmt->fetch();

if ($post && !can_view_post($user, $post)) {
    $post = null;
}

if ($post) {
    db()->prepare('UPDATE posts SET view_count = view_count + 1 WHERE id = :id')->execute(['id' => $postId]);
    $post['view_count'] = (int) ($post['view_count'] ?? 0) + 1;
}

$likedByCurrentUser = false;
if ($post && $user) {
    $likedStmt = db()->prepare('SELECT 1 FROM post_likes WHERE post_id = :post_id AND user_id = :user_id LIMIT 1');
    $likedStmt->execute(['post_id' => $postId, 'user_id' => $user['id']]);
    $likedByCurrentUser = (bool) $likedStmt->fetchColumn();
}

$relatedBoardPosts = [];
$relatedAuthorPosts = [];
$comments = [];
if ($post) {
    $relatedBoardStmt = db()->prepare(
        'SELECT p.id, p.title, p.created_at,
                COALESCE(l.like_count, 0) AS like_count,
                COALESCE(c.comment_count, 0) AS comment_count
         FROM posts p
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
         ) l ON l.post_id = p.id
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
         ) c ON c.post_id = p.id
         WHERE p.status = "published" AND p.board_id = :board_id AND p.id <> :post_id
         ORDER BY p.created_at DESC, p.id DESC
         LIMIT 4'
    );
    $relatedBoardStmt->execute([
        'board_id' => (int) ($post['board_id'] ?? 0),
        'post_id' => $postId,
    ]);
    $relatedBoardPosts = $relatedBoardStmt->fetchAll();

    $relatedAuthorStmt = db()->prepare(
        'SELECT p.id, p.title, p.created_at,
                COALESCE(l.like_count, 0) AS like_count,
                COALESCE(c.comment_count, 0) AS comment_count
         FROM posts p
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
         ) l ON l.post_id = p.id
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
         ) c ON c.post_id = p.id
         WHERE p.status = "published" AND p.user_id = :user_id AND p.id <> :post_id
         ORDER BY p.created_at DESC, p.id DESC
         LIMIT 4'
    );
    $relatedAuthorStmt->execute([
        'user_id' => (int) ($post['user_id'] ?? 0),
        'post_id' => $postId,
    ]);
    $relatedAuthorPosts = $relatedAuthorStmt->fetchAll();

    $commentsStmt = db()->prepare(
        'SELECT c.id, c.parent_id, c.content, c.status, c.created_at, c.updated_at,
                u.id AS user_id, u.nickname, u.username, u.avatar_path,
                COALESCE(cl.like_count, 0) AS like_count
         FROM comments c
         INNER JOIN pulsenest_users u ON u.id = c.user_id
         LEFT JOIN (
            SELECT comment_id, COUNT(*) AS like_count FROM comment_likes GROUP BY comment_id
         ) cl ON cl.comment_id = c.id
         WHERE c.post_id = :post_id AND c.status = "approved"
         ORDER BY c.created_at ASC, c.id ASC'
    );
    $commentsStmt->execute(['post_id' => $postId]);
    $comments = $commentsStmt->fetchAll();

    if ($user && $comments) {
        $commentIds = array_map(static fn(array $comment): int => (int) $comment['id'], $comments);
        $placeholders = implode(',', array_fill(0, count($commentIds), '?'));
        $likedStmt = db()->prepare('SELECT comment_id FROM comment_likes WHERE user_id = ? AND comment_id IN (' . $placeholders . ')');
        $likedStmt->execute(array_merge([(int) $user['id']], $commentIds));
        $likedCommentIds = array_map('intval', $likedStmt->fetchAll(PDO::FETCH_COLUMN));
        $likedLookup = array_fill_keys($likedCommentIds, true);
        foreach ($comments as &$commentRow) {
            $commentRow['liked_by_current_user'] = isset($likedLookup[(int) $commentRow['id']]);
        }
        unset($commentRow);
    }
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
    'searchText' => '🔎 当前帖子所在版块、作者、相关讨论',
]);

function render_comment_item(array $comment, ?array $user, int $postId, bool $isReply = false): void {
    $avatarClass = $isReply ? 'avatar-sm' : 'avatar';
    $canManage = can_manage_comment($user, $comment);
    $likedByCurrentUser = (bool) ($comment['liked_by_current_user'] ?? false);
    ?>
    <article class="comment-card <?= $isReply ? 'reply-card' : '' ?>">
      <div class="comment-head">
        <div class="user">
          <?= render_avatar($comment, $avatarClass) ?>
          <div>
            <div class="user-name-line"><a class="inline-link" href="/user.php?id=<?= (int) $comment['user_id'] ?>"><?= e($comment['nickname']) ?></a> <span class="tiny-badge">@<?= e($comment['username']) ?></span></div>
            <div class="muted"><?= e(human_time($comment['created_at'])) ?><?php if (($comment['updated_at'] ?? '') !== ($comment['created_at'] ?? '')): ?> · 已编辑<?php endif; ?></div>
          </div>
        </div>
      </div>
      <div class="comment-body"><?= nl2br(e($comment['content'])) ?></div>

      <div class="comment-meta-row">
        <span class="meta-pill">评论点赞 · <?= (int) ($comment['like_count'] ?? 0) ?></span>
      </div>

      <?php if ($user): ?>
        <div class="comment-action-row">
          <form method="post" class="inline-form">
            <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
            <input type="hidden" name="action" value="toggle_comment_like">
            <input type="hidden" name="comment_id" value="<?= (int) $comment['id'] ?>">
            <button class="pill-btn <?= $likedByCurrentUser ? 'solid' : '' ?>" type="submit"><?= e(like_button_label($likedByCurrentUser, (int) ($comment['like_count'] ?? 0))) ?></button>
          </form>
          <?php if (!$isReply): ?>
            <details class="reply-box inline-details">
              <summary>回复</summary>
              <form class="form reply-form" method="post">
                <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                <input type="hidden" name="action" value="comment">
                <input type="hidden" name="parent_id" value="<?= (int) $comment['id'] ?>">
                <textarea class="textarea small-textarea" name="content" placeholder="继续展开聊"></textarea>
                <button class="submit" type="submit">发送回复</button>
              </form>
            </details>
          <?php endif; ?>

          <?php if (!$canManage): ?>
            <details class="reply-box inline-details">
              <summary>举报</summary>
              <form class="form reply-form" method="post">
                <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                <input type="hidden" name="action" value="report_comment">
                <input type="hidden" name="comment_id" value="<?= (int) $comment['id'] ?>">
                <select class="input" name="reason">
                  <?php foreach (report_reason_options() as $reasonKey => $reasonLabel): ?>
                    <option value="<?= e($reasonKey) ?>"><?= e($reasonLabel) ?></option>
                  <?php endforeach; ?>
                </select>
                <textarea class="textarea small-textarea" name="detail" placeholder="补充说明（可选）"></textarea>
                <button class="submit" type="submit">提交举报</button>
              </form>
            </details>
          <?php endif; ?>

          <?php if ($canManage): ?>
            <details class="reply-box inline-details">
              <summary>编辑</summary>
              <form class="form reply-form" method="post">
                <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                <input type="hidden" name="action" value="update_comment">
                <input type="hidden" name="comment_id" value="<?= (int) $comment['id'] ?>">
                <textarea class="textarea small-textarea" name="content"><?= e($comment['content']) ?></textarea>
                <button class="submit" type="submit">保存评论</button>
              </form>
            </details>
            <form method="post" class="inline-form danger-inline-form" onsubmit="return confirm('确认删除这条评论？此操作会写入日志。');">
              <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
              <input type="hidden" name="action" value="delete_comment">
              <input type="hidden" name="comment_id" value="<?= (int) $comment['id'] ?>">
              <button class="pill-btn danger" type="submit">删除</button>
            </form>
          <?php endif; ?>
        </div>
      <?php endif; ?>

      <?php if (!$isReply && !empty($comment['children'])): ?>
        <div class="reply-list">
          <?php foreach ($comment['children'] as $reply): ?>
            <?php render_comment_item($reply, $user, $postId, true); ?>
          <?php endforeach; ?>
        </div>
      <?php endif; ?>
    </article>
    <?php
}
?>
  <main class="shell page-shell nebula-page-shell narrow-post-shell">
    <?php if ($post): ?>
      <?php render_breadcrumbs([
        ['label' => '首页', 'href' => '/'],
        ['label' => '发现', 'href' => '/posts.php'],
        ['label' => board_badge($post), 'href' => '/posts.php?board=' . urlencode((string) ($post['board_slug'] ?? ''))],
        ['label' => $post['title']],
      ]); ?>
    <?php endif; ?>
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>

    <?php if (!$post): ?>
      <section class="glass panel-card empty-inline nebula-empty">没有找到这篇帖子。<a class="link" href="/posts.php">返回帖子列表</a></section>
    <?php else: ?>
      <section class="glass nebula-hero detail-hero refined-hero refined-hero-post">
        <div class="detail-hero-head">
          <div>
            <div class="brand-chip">纳达尔星项目 · 星云初始03 · 帖子详情</div>
            <h1><?= e($post['title']) ?></h1>
            <p class="page-desc nebula-desc">查看正文、参与讨论，并在同一页完成点赞、回复与内容管理。</p>
            <div class="hero-editorial-note">把一篇内容真正变成作品，不只是把正文贴出来，还要让上下文、作者与讨论都站得住。</div>
            <?php if (($post['status'] ?? 'published') !== 'published'): ?>
              <div class="chips" style="margin-top:12px; gap:6px;">
                <span class="chip">当前状态：<?= e(post_status_label($post['status'])) ?></span>
                <span class="chip">仅作者 / 管理人员可见</span>
              </div>
            <?php endif; ?>
          </div>
          <div class="hero-actions-row detail-hero-actions">
            <a class="pill-btn" href="/posts.php?board=<?= e($post['board_slug']) ?>">返回版块</a>
            <a class="pill-btn solid" href="<?= $user ? '/create-post.php' : '/login.php' ?>"><?= $user ? '继续发帖' : '登录后发帖' ?></a>
          </div>
        </div>
        <div class="hero-stats compact-hero-stats detail-stats">
          <div class="hero-stat"><div class="label">版块</div><div class="num small-num"><?= e(board_badge($post)) ?></div><div class="note">论坛归属已正式接入</div></div>
          <div class="hero-stat"><div class="label">点赞</div><div class="num small-num"><?= (int) $post['like_count'] ?></div><div class="note">已有成员为这篇内容加热</div></div>
          <div class="hero-stat"><div class="label">回复</div><div class="num small-num"><?= (int) $post['comment_count'] ?></div><div class="note"><?= $user ? '你现在可以直接参与讨论' : '登录后可评论和点赞' ?></div></div>
          <div class="hero-stat"><div class="label">浏览</div><div class="num small-num"><?= (int) ($post['view_count'] ?? 0) ?></div><div class="note">帖子访问量累计</div></div>
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
                  <div class="muted" style="margin-top: 6px; font-size: 14px;">发布于 <?= e(substr($post['created_at'], 0, 16)) ?> · <?= e(board_badge($post)) ?><?php if (($post['updated_at'] ?? '') !== ($post['created_at'] ?? '')): ?> · 已编辑<?php endif; ?></div>
                </div>
              </div>
              <span class="small-chip a">文章详情</span>
            </div>
            <?php if (!empty($post['image_path'])): ?>
              <div class="post-cover-wrap"><img class="post-cover-image detail-cover" src="<?= e(asset_url($post['image_path'])) ?>" alt="<?= e($post['title']) ?>"></div>
            <?php endif; ?>
            <div class="article-meta"><span>作者邮箱：<?= e($post['email']) ?></span><span><a class="inline-link" href="/posts.php?board=<?= e($post['board_slug']) ?>">查看同版块更多帖子</a></span></div>
            <?php if (!empty($post['bio'])): ?><div class="article-meta">作者简介：<?= e($post['bio']) ?></div><?php endif; ?>
            <div class="article-body"><?= nl2br(e($post['content'])) ?></div>
            <div class="action-bar action-bar-wrap">
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
              <span class="meta-pill"><?= e(board_badge($post)) ?></span>
              <?php if ($user && !can_manage_post($user, $post)): ?>
                <details class="reply-box inline-details">
                  <summary>举报帖子</summary>
                  <form class="form reply-form" method="post">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="report_post">
                    <select class="input" name="reason">
                      <?php foreach (report_reason_options() as $reasonKey => $reasonLabel): ?>
                        <option value="<?= e($reasonKey) ?>"><?= e($reasonLabel) ?></option>
                      <?php endforeach; ?>
                    </select>
                    <textarea class="textarea small-textarea" name="detail" placeholder="补充说明（可选）"></textarea>
                    <button class="submit" type="submit">提交举报</button>
                  </form>
                </details>
              <?php endif; ?>
              <?php if (can_manage_post($user, $post)): ?>
                <a class="pill-btn" href="/edit-post.php?id=<?= (int) $post['id'] ?>">编辑帖子</a>
                <form method="post" class="inline-form danger-inline-form" onsubmit="return confirm('确认删除这篇帖子？此操作不可撤销。');">
                  <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                  <input type="hidden" name="action" value="delete_post">
                  <button class="pill-btn danger" type="submit">删除帖子</button>
                </form>
              <?php endif; ?>
            </div>
          </article>

          <section class="glass panel-card surface-section">
            <div class="section-kicker">Continue Reading</div>
            <div class="side-head"><h3>继续沿着这条内容线往下看</h3></div>
            <div class="nebula-section-grid" style="grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 18px;">
              <div class="glass panel-card inner-card">
                <div class="section-kicker">Same Board</div>
                <div class="small-section-title"><?= e($post['board_name'] ?? '当前版块') ?></div>
                <div class="list-stack compact-link-stack">
                  <?php foreach ($relatedBoardPosts as $item): ?>
                    <a class="quick-link" href="/post.php?id=<?= (int) $item['id'] ?>">
                      <strong><?= e($item['title']) ?></strong>
                      <span><?= (int) $item['like_count'] ?> 赞 · <?= (int) $item['comment_count'] ?> 回复 · <?= e(human_time($item['created_at'])) ?></span>
                    </a>
                  <?php endforeach; ?>
                  <?php if (!$relatedBoardPosts): ?><div class="empty-inline nebula-empty">当前版块暂时没有更多公开帖子。</div><?php endif; ?>
                </div>
              </div>
              <div class="glass panel-card inner-card">
                <div class="section-kicker">More From Author</div>
                <div class="small-section-title"><?= e($post['nickname']) ?> 的更多内容</div>
                <div class="list-stack compact-link-stack">
                  <?php foreach ($relatedAuthorPosts as $item): ?>
                    <a class="quick-link" href="/post.php?id=<?= (int) $item['id'] ?>">
                      <strong><?= e($item['title']) ?></strong>
                      <span><?= (int) $item['like_count'] ?> 赞 · <?= (int) $item['comment_count'] ?> 回复 · <?= e(human_time($item['created_at'])) ?></span>
                    </a>
                  <?php endforeach; ?>
                  <?php if (!$relatedAuthorPosts): ?><div class="empty-inline nebula-empty">这个作者暂时没有更多公开内容。</div><?php endif; ?>
                </div>
              </div>
            </div>
          </section>

          <section class="glass panel-card comment-panel surface-section">
            <div class="section-kicker">Discussion</div>
            <div class="side-head"><h3>评论区与回复区</h3></div>

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
                  <?php render_comment_item($comment, $user, $postId); ?>
                <?php endforeach; ?>
              <?php endif; ?>
            </div>
          </section>
        </div>

        <aside class="right-col-stack">
          <section class="glass section-card surface-section post-side-card">
            <div class="section-kicker">Author Snapshot</div>
            <div class="side-head"><h3>作者名片</h3></div>
            <div class="author-item detail-author-card">
              <div class="author-row">
                <div class="author-badge">🌌</div>
                <div class="author-main">
                  <div class="author-name"><a class="inline-link" href="/user.php?id=<?= (int) $post['user_id'] ?>"><?= e($post['nickname']) ?></a></div>
                  <div class="meta">@<?= e($post['username']) ?> · <?= e(board_badge($post)) ?></div>
                </div>
                <div class="score">作者</div>
              </div>
              <p><?= e($post['bio'] ?: '这个作者还没有写简介，但你已经可以继续查看他的公开内容。') ?></p>
              <div class="chips" style="margin-top: 12px; gap: 6px;">
                <span class="chip"><?= (int) $post['like_count'] ?> 赞</span>
                <span class="chip"><?= (int) $post['comment_count'] ?> 回复</span>
                <span class="chip"><?= e(human_time($post['created_at'])) ?></span>
              </div>
            </div>
          </section>

          <section class="glass section-card surface-section post-side-card">
            <div class="section-kicker">Quick Jump</div>
            <div class="side-head"><h3>相关入口</h3></div>
            <div class="quick-links compact-link-stack">
              <a class="quick-link" href="/posts.php?board=<?= e($post['board_slug']) ?>"><strong>同版块帖子</strong><span>继续浏览当前版块的相关讨论。</span></a>
              <a class="quick-link" href="/user.php?id=<?= (int) $post['user_id'] ?>"><strong>作者主页</strong><span>查看作者的公开资料与更多内容。</span></a>
              <a class="quick-link" href="/notifications.php"><strong>我的提醒</strong><span>回到通知页处理互动消息。</span></a>
              <?php if (can_manage_post($user, $post)): ?>
                <a class="quick-link" href="/edit-post.php?id=<?= (int) $post['id'] ?>"><strong>编辑当前帖子</strong><span>继续维护标题、正文与封面。</span></a>
              <?php endif; ?>
            </div>
          </section>
        </aside>
      </div>
    <?php endif; ?>
  </main>
<?php render_footer(); ?>
