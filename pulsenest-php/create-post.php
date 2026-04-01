<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();
$error = '';
$form = ['title' => '', 'content' => ''];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $form['title'] = trim($_POST['title'] ?? '');
    $form['content'] = trim($_POST['content'] ?? '');

    if ($form['title'] === '' || $form['content'] === '') {
        $error = '标题和正文都要填写。';
    } elseif (mb_strlen($form['title']) < 4 || mb_strlen($form['title']) > 120) {
        $error = '标题长度请控制在 4 到 120 个字符之间。';
    } elseif (mb_strlen($form['content']) < 10) {
        $error = '正文至少写满 10 个字，帖子才像回事。';
    } else {
        try {
            $imagePath = handle_image_upload($_FILES['cover_image'] ?? [], POST_UPLOAD_DIR);
            $stmt = db()->prepare('INSERT INTO posts (user_id, title, content, image_path) VALUES (:user_id, :title, :content, :image_path)');
            $stmt->execute([
                'user_id' => $user['id'],
                'title' => $form['title'],
                'content' => $form['content'],
                'image_path' => $imagePath,
            ]);
            $postId = (int) db()->lastInsertId();
            flash_set('success', '帖子发布成功，已经写入数据库。');
            redirect_to('/post.php?id=' . $postId);
        } catch (RuntimeException $e) {
            $error = $e->getMessage();
        }
    }
}

render_header('PulseNest · 发帖', $user, [
    'searchText' => '🔎 搜索灵感、发帖目标、内容流入口',
]);
?>
  <main class="shell page-shell nebula-page-shell create-post-page">
    <section class="glass nebula-hero nebula-hero-split create-post-hero">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始01 · 发帖页</div>
        <h1>把你的内容直接抛进这片星云，发布后立即进入真实帖子链路。</h1>
        <p class="page-desc nebula-desc">这一页继续走原本的登录保护与 MySQL 入库逻辑，但现在支持顺手上传一张帖子图片，让列表卡、首页卡和详情页都更像真社区。</p>
        <div class="hero-stats compact-hero-stats">
          <div class="hero-stat"><div class="label">发布后</div><div class="num small-num">跳详情页</div><div class="note">成功即重定向到 /post.php?id=xx</div></div>
          <div class="hero-stat"><div class="label">配图支持</div><div class="num small-num">单图上传</div><div class="note">保存到 uploads/posts，首页与列表同步显示</div></div>
          <div class="hero-stat"><div class="label">当前用户</div><div class="num small-num"><?= e($user['nickname']) ?></div><div class="note">@<?= e($user['username']) ?></div></div>
        </div>
      </div>

      <aside class="glass side-card nebula-side-panel">
        <div class="section-kicker">Posting Guide</div>
        <div class="quick-links">
          <div class="quick-link static-link">标题建议 4~120 字，能一眼看懂重点。</div>
          <div class="quick-link static-link">正文至少 10 字，方便在列表页展示摘要。</div>
          <div class="quick-link static-link">帖子图片支持 JPG / PNG / GIF / WEBP，大小 5MB 内。</div>
        </div>
      </aside>
    </section>

    <section class="glass auth-panel standalone-panel nebula-compose-panel">
      <div class="kicker">Create Post</div>
      <h2>发布一篇新帖子</h2>
      <p class="desc">继续使用现有标题 + 正文链路，并新增帖子图片上传。提交后真实入库，并立刻能在内容流里验证结果。</p>

      <?php if ($error): ?><div class="notice error"><?= e($error) ?></div><?php endif; ?>

      <form class="form" method="post" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <div class="field">
          <label>标题</label>
          <input class="input" name="title" value="<?= e($form['title']) ?>" placeholder="给这篇帖子起个吸引人点开的标题" />
        </div>
        <div class="field">
          <label>正文</label>
          <textarea class="textarea compose-textarea" name="content" placeholder="写下你想分享的内容、感受或推荐理由"><?= e($form['content']) ?></textarea>
        </div>
        <div class="field">
          <label>帖子图片（可选）</label>
          <input class="input file-input" type="file" name="cover_image" accept="image/jpeg,image/png,image/gif,image/webp" />
          <div class="field-tip">上传后会在首页、列表页和详情页显示。</div>
        </div>
        <div class="compose-actions">
          <a class="pill-btn" href="/posts.php">先看看帖子列表</a>
          <button class="submit" type="submit">发布到 PulseNest</button>
        </div>
      </form>
    </section>
  </main>
<?php render_footer(); ?>
