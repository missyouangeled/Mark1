<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();
$flash = flash_get();
$profileError = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $bio = trim($_POST['bio'] ?? '');
    if (mb_strlen($bio) > 280) {
        $profileError = '个性签名请控制在 280 字以内。';
    } else {
        try {
            $avatarPath = handle_image_upload($_FILES['avatar'] ?? [], AVATAR_UPLOAD_DIR);
            if (!$avatarPath) {
                $avatarPath = $user['avatar_path'] ?? null;
            }

            $stmt = db()->prepare('UPDATE pulsenest_users SET bio = :bio, avatar_path = :avatar_path WHERE id = :id');
            $stmt->execute([
                'bio' => $bio !== '' ? $bio : null,
                'avatar_path' => $avatarPath,
                'id' => $user['id'],
            ]);
            refresh_current_user();
            flash_set('success', '会员资料已更新。');
            redirect_to('/account.php');
        } catch (RuntimeException $e) {
            $profileError = $e->getMessage();
            $user = refresh_current_user() ?? $user;
        }
    }
}

$user = refresh_current_user() ?? $user;
$stmt = db()->prepare('SELECT COUNT(*) FROM posts WHERE user_id = :id');
$stmt->execute(['id' => $user['id']]);
$postCount = (int) $stmt->fetchColumn();
$totalPosts = (int) db()->query('SELECT COUNT(*) FROM posts')->fetchColumn();
$memberCount = (int) db()->query('SELECT COUNT(*) FROM pulsenest_users')->fetchColumn();
$latestPostsStmt = db()->prepare(
    'SELECT p.id, p.title, p.created_at,
            COALESCE(l.like_count, 0) AS like_count,
            COALESCE(c.comment_count, 0) AS comment_count
     FROM posts p
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
     ) l ON l.post_id = p.id
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS comment_count FROM comments GROUP BY post_id
     ) c ON c.post_id = p.id
     WHERE p.user_id = :id
     ORDER BY p.created_at DESC, p.id DESC
     LIMIT 5'
);
$latestPostsStmt->execute(['id' => $user['id']]);
$latestPosts = $latestPostsStmt->fetchAll();

render_header('PulseNest · 会员中心', $user, [
    'searchText' => '🔎 搜索我的帖子、账号动作、社区入口',
]);
?>
  <main class="shell page-shell nebula-page-shell account-page">
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>
    <?php if ($profileError): ?><div class="notice error floating-notice"><?= e($profileError) ?></div><?php endif; ?>

    <section class="glass nebula-hero nebula-hero-split member-hero nebula-member-hero">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始01 · 会员中心</div>
        <h1>欢迎回来，<?= e($user['nickname']) ?>，你的社区身份卡已经并入星云主壳。</h1>
        <p class="page-desc nebula-desc">会员中心现在不只是统计页：你可以上传头像、更新一句个人介绍，并从这里直接跳进自己的主页。</p>
        <div class="hero-actions-row">
          <a class="pill-btn solid" href="/create-post.php">写一篇新帖子</a>
          <a class="pill-btn" href="<?= e(profile_url($user)) ?>">查看我的主页</a>
        </div>
      </div>

      <aside class="profile-chip nebula-profile-chip">
        <?= render_avatar($user, 'user-avatar large') ?>
        <div>
          <strong><?= e($user['nickname']) ?></strong>
          <span>@<?= e($user['username']) ?></span>
          <span><?= e($user['email']) ?></span>
          <span>加入时间：<?= e(substr((string) $user['created_at'], 0, 16)) ?></span>
        </div>
      </aside>
    </section>

    <section class="stat-grid page-grid-three nebula-stat-grid">
      <div class="glass stat-card"><strong><?= $postCount ?></strong><span>我的帖子</span></div>
      <div class="glass stat-card"><strong><?= $memberCount ?></strong><span>社区成员</span></div>
      <div class="glass stat-card"><strong><?= $totalPosts ?></strong><span>全站内容</span></div>
    </section>

    <div class="nebula-section-grid account-grid">
      <div class="right-col-stack">
        <section class="glass panel-card">
          <div class="section-kicker">Profile Studio</div>
          <div class="side-head"><h3>资料与头像</h3></div>
          <form class="form" method="post" enctype="multipart/form-data">
            <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
            <div class="avatar-upload-row">
              <?= render_avatar($user, 'user-avatar large') ?>
              <div class="field grow-field">
                <label>上传头像</label>
                <input class="input file-input" type="file" name="avatar" accept="image/jpeg,image/png,image/gif,image/webp" />
                <div class="field-tip">支持 JPG / PNG / GIF / WEBP，大小 5MB 内。</div>
              </div>
            </div>
            <div class="field">
              <label>个人简介</label>
              <textarea class="textarea small-textarea" name="bio" placeholder="写一句让别人认识你的话"><?= e($user['bio'] ?? '') ?></textarea>
            </div>
            <button class="submit" type="submit">保存资料</button>
          </form>
        </section>

        <section class="glass panel-card">
          <div class="section-kicker">My Recent Posts</div>
          <div class="side-head"><h3>我最近发布的内容</h3></div>
          <?php if (!$latestPosts): ?>
            <div class="empty-inline nebula-empty">你还没有发帖，先去写第一篇吧。</div>
          <?php else: ?>
            <div class="list-stack">
              <?php foreach ($latestPosts as $post): ?>
                <a class="list-item" href="/post.php?id=<?= (int) $post['id'] ?>">
                  <strong><?= e($post['title']) ?></strong>
                  <span><?= e(human_time($post['created_at'])) ?> · <?= (int) $post['like_count'] ?> 赞 · <?= (int) $post['comment_count'] ?> 回复</span>
                </a>
              <?php endforeach; ?>
            </div>
          <?php endif; ?>
        </section>
      </div>

      <aside class="right-col-stack">
        <section class="glass panel-card">
          <div class="section-kicker">Member Data</div>
          <div class="side-head"><h3>当前用户信息</h3></div>
          <div class="detail-list">
            <div class="detail-row"><span>昵称</span><strong><?= e($user['nickname']) ?></strong></div>
            <div class="detail-row"><span>用户名</span><strong>@<?= e($user['username']) ?></strong></div>
            <div class="detail-row"><span>邮箱</span><strong><?= e($user['email']) ?></strong></div>
            <div class="detail-row"><span>签名</span><strong><?= e($user['bio'] ?: '还没写简介') ?></strong></div>
          <div class="detail-row"><span>未读提醒</span><strong><?= unread_notification_count((int) $user['id']) ?></strong></div>
          </div>
        </section>

        <section class="glass panel-card">
          <div class="section-kicker">Quick Actions</div>
          <div class="quick-links">
            <a class="quick-link" href="/create-post.php">写一篇新帖子</a>
            <a class="quick-link" href="/notifications.php">查看我的提醒</a>
            <a class="quick-link" href="/posts.php">查看全部帖子</a>
            <a class="quick-link" href="/forgot-password.php">发起密码重置</a>
            <a class="quick-link" href="/">返回首页内容流</a>
          </div>
        </section>
      </aside>
    </div>
  </main>
<?php render_footer(); ?>
