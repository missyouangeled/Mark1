<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();
$error = '';
$form = ['title' => '', 'content' => ''];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $form['title'] = trim($_POST['title'] ?? '');
    $form['content'] = trim($_POST['content'] ?? '');

    if ($form['title'] === '' || $form['content'] === '') {
        $error = '标题和正文都要填写。';
    } elseif (mb_strlen($form['title']) < 4 || mb_strlen($form['title']) > 120) {
        $error = '标题长度请控制在 4 到 120 个字符之间。';
    } elseif (mb_strlen($form['content']) < 10) {
        $error = '正文至少写满 10 个字，帖子才像回事。';
    } else {
        $stmt = db()->prepare('INSERT INTO posts (user_id, title, content) VALUES (:user_id, :title, :content)');
        $stmt->execute([
            'user_id' => $user['id'],
            'title' => $form['title'],
            'content' => $form['content'],
        ]);
        $postId = (int) db()->lastInsertId();
        flash_set('success', '帖子发布成功，已经写入数据库。');
        redirect_to('/post.php?id=' . $postId);
    }
}

render_header('PulseNest · 发帖', $user);
?>
  <div class="shell page-shell narrow">
    <section class="card auth-panel standalone-panel">
      <div class="kicker">Create Post</div>
      <h2>发布一篇新帖子</h2>
      <p class="desc">先做简化版，但已经是真实入库：标题、正文提交后会写进 MySQL，并出现在首页内容流和帖子列表里。</p>

      <?php if ($error): ?><div class="notice error"><?= e($error) ?></div><?php endif; ?>

      <form class="form" method="post">
        <div class="field">
          <label>标题</label>
          <input class="input" name="title" value="<?= e($form['title']) ?>" placeholder="给这篇帖子起个吸引人点开的标题" />
        </div>
        <div class="field">
          <label>正文</label>
          <textarea class="textarea" name="content" placeholder="写下你想分享的内容、感受或推荐理由"><?= e($form['content']) ?></textarea>
        </div>
        <button class="submit" type="submit">发布到 PulseNest</button>
      </form>
    </section>
  </div>
<?php render_footer(); ?>