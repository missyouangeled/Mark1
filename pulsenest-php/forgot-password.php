<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$error = '';
$success = '';
$resetToken = '';
$email = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = trim($_POST['email'] ?? '');
    if ($email === '') {
        $error = '请输入注册邮箱。';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = '邮箱格式不正确。';
    } else {
        $stmt = db()->prepare('SELECT id, email, nickname FROM pulsenest_users WHERE email = :email LIMIT 1');
        $stmt->execute(['email' => $email]);
        $found = $stmt->fetch();

        if (!$found) {
            $error = '这个邮箱还没有注册过。';
        } else {
            $token = password_reset_token();
            $tokenHash = hash('sha256', $token);
            db()->prepare('UPDATE password_resets SET used_at = NOW() WHERE email = :email AND used_at IS NULL')->execute(['email' => $email]);
            $insert = db()->prepare('INSERT INTO password_resets (email, token_hash, expires_at) VALUES (:email, :token_hash, DATE_ADD(NOW(), INTERVAL 1 HOUR))');
            $insert->execute(['email' => $email, 'token_hash' => $tokenHash]);
            $resetToken = $token;
            $success = '重置请求已生成。当前是本地原型，所以不发真实邮件，直接给你一个可访问的重置链接。';
        }
    }
}

render_header('PulseNest · 找回密码', $user);
?>
  <div class="shell page-shell narrow">
    <section class="card auth-panel standalone-panel">
      <div class="kicker">Reset Password</div>
      <h2>忘记密码</h2>
      <p class="desc">输入注册邮箱，系统会生成一个本地可用的重置 token，并写入数据库。原型阶段不发真实邮件，但整个流程可以完整走通。</p>

      <?php if ($error): ?><div class="notice error"><?= e($error) ?></div><?php endif; ?>
      <?php if ($success): ?><div class="notice success"><?= e($success) ?></div><?php endif; ?>

      <form class="form" method="post">
        <div class="field">
          <label>注册邮箱</label>
          <input class="input" name="email" value="<?= e($email) ?>" placeholder="输入注册时使用的邮箱" />
        </div>
        <button class="submit" type="submit">生成重置链接</button>
      </form>

      <?php if ($resetToken): ?>
        <div class="result-box">
          <div><strong>本地重置链接：</strong></div>
          <div class="token-box"><a class="link" href="/reset-password.php?token=<?= e($resetToken) ?>">/reset-password.php?token=<?= e($resetToken) ?></a></div>
          <div class="muted" style="margin-top:10px;">token 已以哈希形式写入 `password_resets` 表，有效期 1 小时。</div>
        </div>
      <?php endif; ?>
    </section>
  </div>
<?php render_footer(); ?>