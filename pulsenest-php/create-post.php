<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();
$error = '';
$boards = fetch_board_options();
$postTitleMin = max(1, site_int_setting('site.post_title_min_length', 4));
$postTitleMax = max($postTitleMin, site_int_setting('site.post_title_max_length', 120));
$postContentMin = max(1, site_int_setting('site.post_content_min_length', 10));
if (site_setting_enabled('site.readonly_mode_enabled', false)) {
    $error = '当前站点处于只读模式，暂时关闭发帖。';
}
$defaultBoardId = (int) ($boards[0]['id'] ?? 0);
$form = ['title' => '', 'content' => '', 'board_id' => $defaultBoardId];

if ($_SERVER['REQUEST_METHOD'] === 'POST' && !site_setting_enabled('site.readonly_mode_enabled', false)) {
    verify_csrf();
    $form['title'] = trim($_POST['title'] ?? '');
    $form['content'] = trim($_POST['content'] ?? '');
    $form['board_id'] = (int) ($_POST['board_id'] ?? 0);

    $selectedBoard = null;
    foreach ($boards as $board) {
        if ((int) $board['id'] === (int) $form['board_id']) {
            $selectedBoard = $board;
            break;
        }
    }

    if (!$selectedBoard) {
        $error = '请选择一个有效版块。';
    } elseif ($form['title'] === '' || $form['content'] === '') {
        $error = '标题和正文都要填写。';
    } elseif (mb_strlen($form['title']) < $postTitleMin || mb_strlen($form['title']) > $postTitleMax) {
        $error = '标题长度请控制在 ' . $postTitleMin . ' 到 ' . $postTitleMax . ' 个字符之间。';
    } elseif (mb_strlen($form['content']) < $postContentMin) {
        $error = '正文至少写满 ' . $postContentMin . ' 个字，帖子才像回事。';
    } else {
        try {
            $imagePath = handle_image_upload($_FILES['cover_image'] ?? [], POST_UPLOAD_DIR);
            $requiresModeration = site_setting_enabled('site.post_moderation_enabled', true);
            $initialStatus = (can_moderate_content($user) || !$requiresModeration) ? 'published' : 'pending';
            $stmt = db()->prepare('INSERT INTO posts (user_id, board_id, title, content, image_path, status) VALUES (:user_id, :board_id, :title, :content, :image_path, :status)');
            $stmt->execute([
                'user_id' => $user['id'],
                'board_id' => $form['board_id'],
                'title' => $form['title'],
                'content' => $form['content'],
                'image_path' => $imagePath,
                'status' => $initialStatus,
            ]);
            $postId = (int) db()->lastInsertId();
            flash_set('success', $initialStatus === 'published' ? '帖子发布成功，已经写入对应版块。' : '帖子已提交审核，审核通过后会对外显示。');
            redirect_to('/post.php?id=' . $postId);
        } catch (RuntimeException $e) {
            $error = $e->getMessage();
        }
    }
}

render_header('PulseNest · 发帖', $user, [
    'searchText' => '🔎 搜索灵感、版块入口、社区热门话题',
]);
?>
  <main class="shell page-shell nebula-page-shell create-post-page">
    <section class="glass nebula-hero nebula-hero-split create-post-hero">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始03 · 发帖页</div>
        <h1>把你的内容准确投进对应版块，发出去就能进入真实论坛链路。</h1>
        <p class="page-desc nebula-desc">现在发帖除了标题、正文和配图，还必须归属到版块。首页、列表页、搜索和通知都会围着这条论坛骨架联动。</p>
        <div class="hero-stats compact-hero-stats">
          <div class="hero-stat"><div class="label">版块归属</div><div class="num small-num">必选</div><div class="note">帖子会挂到分类 / 版块体系里</div></div>
          <div class="hero-stat"><div class="label">配图支持</div><div class="num small-num">单图上传</div><div class="note">保存到 uploads/posts，首页与列表同步显示</div></div>
          <div class="hero-stat"><div class="label">当前用户</div><div class="num small-num"><?= e($user['nickname']) ?></div><div class="note">@<?= e($user['username']) ?></div></div>
        </div>
      </div>

      <aside class="glass side-card nebula-side-panel">
        <div class="section-kicker">Posting Guide</div>
        <div class="quick-links">
          <div class="quick-link static-link">先选版块，再写标题和正文，内容结构会更像真论坛。</div>
          <div class="quick-link static-link">标题建议 4~120 字，正文至少 10 字。</div>
          <div class="quick-link static-link">图片支持 JPG / PNG / GIF / WEBP，大小 5MB 内。</div>
        </div>
      </aside>
    </section>

    <section class="glass auth-panel standalone-panel nebula-compose-panel">
      <div class="kicker">Create Post</div>
      <h2>发布一篇新帖子</h2>
      <p class="desc">继续沿用星云初始03的轻玻璃面板，但帖子已正式接入分类 / 版块系统。</p>

      <?php if ($error): ?><div class="notice error"><?= e($error) ?></div><?php endif; ?>

      <form class="form" method="post" enctype="multipart/form-data">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <div class="field">
          <label>发布到哪个版块</label>
          <select class="input" name="board_id">
            <?php foreach ($boards as $board): ?>
              <option value="<?= (int) $board['id'] ?>" <?= (int) $form['board_id'] === (int) $board['id'] ? 'selected' : '' ?>><?= e($board['category_name']) ?> / <?= e($board['name']) ?></option>
            <?php endforeach; ?>
          </select>
        </div>
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
          <div class="field-tip">上传后会自动压到更适合前台展示的尺寸，并生成列表 / 详情所需版本。</div>
        </div>
        <div class="compose-actions">
          <a class="pill-btn" href="/posts.php">先看看帖子列表</a>
          <button class="submit" type="submit">发布到 PulseNest</button>
        </div>
      </form>
    </section>
  </main>
<?php render_footer(); ?>