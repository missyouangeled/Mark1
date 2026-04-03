<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();
$error = '';
$boards = fetch_board_options();
$postTitleMin = max(1, site_int_setting('site.post_title_min_length', 4));
$postTitleMax = max($postTitleMin, site_int_setting('site.post_title_max_length', 120));
$postContentMin = max(1, site_int_setting('site.post_content_min_length', 10));
if (site_setting_enabled('site.readonly_mode_enabled', false) && !can_moderate_content($user)) {
    $error = '当前站点处于只读模式，暂时关闭普通用户发帖编辑。';
}
$postId = (int) ($_GET['id'] ?? 0);

$stmt = db()->prepare('SELECT id, user_id, board_id, title, content, image_path, status FROM posts WHERE id = :id LIMIT 1');
$stmt->execute(['id' => $postId]);
$post = $stmt->fetch();
if (!$post) {
    http_response_code(404);
    exit('Post not found.');
}
if (!can_manage_post($user, $post)) {
    http_response_code(403);
    exit('Forbidden');
}

$form = [
    'title' => $post['title'],
    'content' => $post['content'],
    'board_id' => (int) $post['board_id'],
    'remove_image' => false,
];

if ($_SERVER['REQUEST_METHOD'] === 'POST' && !(site_setting_enabled('site.readonly_mode_enabled', false) && !can_moderate_content($user))) {
    verify_csrf();
    $form['title'] = trim($_POST['title'] ?? '');
    $form['content'] = trim($_POST['content'] ?? '');
    $form['board_id'] = (int) ($_POST['board_id'] ?? 0);
    $form['remove_image'] = isset($_POST['remove_image']);

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
            $imagePath = $post['image_path'] ?: null;
            $newUpload = handle_image_upload($_FILES['cover_image'] ?? [], POST_UPLOAD_DIR);
            if ($newUpload) {
                delete_uploaded_asset($imagePath);
                $imagePath = $newUpload;
            } elseif ($form['remove_image']) {
                delete_uploaded_asset($imagePath);
                $imagePath = null;
            }

            $nextStatus = can_moderate_content($user) ? ($post['status'] ?? 'published') : 'pending';
            $update = db()->prepare('UPDATE posts SET board_id = :board_id, title = :title, content = :content, image_path = :image_path, status = :status WHERE id = :id');
            $update->execute([
                'board_id' => $form['board_id'],
                'title' => $form['title'],
                'content' => $form['content'],
                'image_path' => $imagePath,
                'status' => $nextStatus,
                'id' => $postId,
            ]);

            flash_set('success', $nextStatus === 'published' ? '帖子已更新。' : '帖子已更新，并重新进入审核队列。');
            redirect_to('/post.php?id=' . $postId);
        } catch (RuntimeException $e) {
            $error = $e->getMessage();
        }
    }
}

render_header('PulseNest · 编辑帖子', $user, [
    'searchText' => '🔎 正在编辑帖子，可切换版块、标题、正文与配图',
]);
?>
  <main class="shell page-shell nebula-page-shell create-post-page">
    <section class="glass nebula-hero nebula-hero-split create-post-hero">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始03 · 帖子编辑页</div>
        <h1>不重做视觉外壳，直接把帖子编辑链路补齐。</h1>
        <p class="page-desc nebula-desc">这里沿用发帖页的玻璃卡和深色氛围，但动作从“创建”切到“维护”：作者本人或管理员可以改标题、正文、版块和配图。</p>
        <div class="hero-stats compact-hero-stats">
          <div class="hero-stat"><div class="label">当前动作</div><div class="num small-num">编辑帖子</div><div class="note">作者本人 / 管理员可操作</div></div>
          <div class="hero-stat"><div class="label">原帖入口</div><div class="num small-num">#<?= (int) $postId ?></div><div class="note"><a class="inline-link" href="/post.php?id=<?= (int) $postId ?>">返回详情页</a></div></div>
          <div class="hero-stat"><div class="label">当前用户</div><div class="num small-num"><?= e($user['nickname']) ?></div><div class="note">@<?= e($user['username']) ?></div></div>
        </div>
      </div>

      <aside class="glass side-card nebula-side-panel">
        <div class="section-kicker">Editing Guide</div>
        <div class="quick-links">
          <div class="quick-link static-link">可以调整版块归属，但不会打断原有详情页链接。</div>
          <div class="quick-link static-link">可替换原图，或勾选移除配图。</div>
          <div class="quick-link static-link">删帖入口仍放在详情页，避免误触。</div>
        </div>
      </aside>
    </section>

    <section class="glass auth-panel standalone-panel nebula-compose-panel">
      <div class="kicker">Edit Post</div>
      <h2>编辑当前帖子</h2>
      <p class="desc">继续沿用星云初始03的轻玻璃语言，把“可维护”补到内容生产链路里。</p>

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
        <?php if (!empty($post['image_path'])): ?>
          <div class="field">
            <label>当前配图</label>
            <div class="post-cover-wrap"><img class="post-cover-image" src="<?= e(image_variant_public_path($post['image_path'], 'detail')) ?>" alt="<?= e($post['title']) ?>" decoding="async" fetchpriority="low"></div>
            <label class="checkbox-inline"><input type="checkbox" name="remove_image" value="1"> <span>移除当前配图</span></label>
          </div>
        <?php endif; ?>
        <div class="field">
          <label>替换帖子图片（可选）</label>
          <input class="input file-input" type="file" name="cover_image" accept="image/jpeg,image/png,image/gif,image/webp" />
          <div class="field-tip">若上传新图，将覆盖旧图；也可只改文字不换图。</div>
        </div>
        <div class="compose-actions">
          <a class="pill-btn" href="/post.php?id=<?= (int) $postId ?>">返回帖子详情</a>
          <button class="submit" type="submit">保存修改</button>
        </div>
      </form>
    </section>
  </main>
<?php render_footer(); ?>
