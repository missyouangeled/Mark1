<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$user = refresh_current_user();
$error = '';
$success = '';
$token = trim($_GET['token'] ?? $_POST['token'] ?? '');
$record = null;

if ($token !== '') {
    $stmt = db()->prepare('SELECT id, email, expires_at, used_at FROM password_resets WHERE token_hash = :token_hash LIMIT 1');
    $stmt->execute(['token_hash' => hash('sha256', $token)]);
    $record = $stmt->fetch();
    if ($record && ($record['used_at'] !== null || strtotime($record['expires_at']) < time())) {
        $record = null;
        $error = '这个重置链接已失效，请重新发起找回密码。';
    }
} else {
    $error = '缺少重置 token，请从找回密码页重新生成。';
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && $record) {
    $password = (string) ($_POST['password'] ?? '');
    $confirm = (string) ($_POST['confirm_password'] ?? '');

    if ($password === '' || $confirm === '') {
        $error = '请完整填写新密码和确认密码。';
    } elseif (mb_strlen($password) < 6) {
        $error = '新密码至少需要 6 位。';
    } elseif ($password !== $confirm) {
        $error = '两次输入的新密码不一致。';
    } else {
        db()->prepare('UPDATE pulsenest_users SET password_hash = :hash WHERE email = :email')->execute([
            'hash' => password_hash($password, PASSWORD_DEFAULT),
            'email' => $record['email'],
        ]);
        db()->prepare('UPDATE password_resets SET used_at = NOW() WHERE id = :id')->execute(['id' => $record['id']]);
        flash_set('success', '密码重置成功，请使用新密码登录。');
        redirect_to('/login.php?reset=1');
    }
}

render_header('PulseNest · 重置密码', $user);
?>
  <main class="shell auth-shell nebula-auth-shell auth-page-shell">
    <section class="auth-ambient-panel">
      <div class="auth-ambient-copy">
        <div class="auth-badge">纳达尔星项目 · 星云初始03 · 密码更新</div>
        <h1>把密码更新这一步，也收进同一套安静、清晰的入口体验里。</h1>
        <p>链接有效时，你可以直接在这里完成密码更新；更新完成后，这条链接会立即失效，避免重复使用。</p>
        <div class="auth-meta-strip">
          <span>重置链接一次有效</span>
          <span>更新后立即失效</span>
          <span>完成后返回登录入口</span>
        </div>
      </div>
    </section>

    <section class="card auth-panel standalone-panel auth-form-panel">
      <div class="kicker">更新密码</div>
      <h2>重置密码</h2>
      <p class="desc">只要这条重置链接仍然有效，就可以在这里安全完成密码更新。</p>

      <?php if ($error): ?><div class="notice error"><?= e($error) ?></div><?php endif; ?>
      <?php if ($record): ?>
        <div class="notice success">正在为邮箱 <?= e($record['email']) ?> 更新密码。</div>
        <form class="form" method="post">
          <input type="hidden" name="token" value="<?= e($token) ?>" />
          <div class="grid-2">
            <div class="field"><label>新密码</label><input class="input" type="password" name="password" placeholder="输入新密码" /></div>
            <div class="field"><label>确认新密码</label><input class="input" type="password" name="confirm_password" placeholder="再次输入新密码" /></div>
          </div>
          <button class="submit" type="submit">完成密码更新</button>
        </form>
      <?php else: ?>
        <div class="bottom-tip">先去 <a class="link" href="/forgot-password.php">忘记密码</a> 页面重新生成一条新的重置链接。</div>
      <?php endif; ?>
    </section>
  </main>
<?php render_footer(); ?>