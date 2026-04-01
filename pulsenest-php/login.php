<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
ensure_guest_only();

$error = '';
$success = isset($_GET['reset']) ? '密码已更新，现在可以直接登录。' : '';
$identifier = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $identifier = trim($_POST['identifier'] ?? '');
    $password = (string) ($_POST['password'] ?? '');

    if ($identifier === '' || $password === '') {
        $error = '请先填写账号和密码。';
    } else {
        $stmt = db()->prepare('SELECT id, username, nickname, email, password_hash, avatar_path, bio, is_admin, is_active, created_at FROM pulsenest_users WHERE email = :id OR username = :id LIMIT 1');
        $stmt->execute(['id' => $identifier]);
        $user = $stmt->fetch();

        if (!$user || !password_verify($password, $user['password_hash'])) {
            $error = '账号不存在，或密码不正确。';
        } elseif ((int) ($user['is_active'] ?? 1) !== 1) {
            $error = '这个账号当前已被停用，暂时无法登录。';
        } else {
            login_user($user);
            flash_set('success', '欢迎回来，已经为你登录。');
            redirect_to('/');
        }
    }
}

render_header('PulseNest · 登录', null, ['showSearch' => false, 'headerMode' => 'auth']);
?>
  <div class="shell auth-wrap nebula-auth-wrap">
    <section class="glass auth-hero nebula-panel">
      <div class="auth-hero-inner">
        <div>
          <div class="auth-badge">社区身份同步 · 登录后继续逛论坛与内容流</div>
          <div class="auth-copy auth-copy-wide">
            <h1>回来就好，继续从你上次停下的地方开始。</h1>
            <p>登录页不再像后台入口，而是延续“星云初始01”的玻璃层次、暗色宇宙底和论坛感信息组织。你登录之后，首页右上角、主行动按钮和会员中心都会直接进入真实状态。</p>
          </div>
        </div>

        <div class="hero-points">
          <div class="hero-point"><strong>同步</strong><span>刷新当前用户资料，避免旧 session 卡住昵称和邮箱。</span></div>
          <div class="hero-point"><strong>参与</strong><span>登录后可发帖、进入会员中心，并继续完整测试功能链路。</span></div>
          <div class="hero-point"><strong>延续</strong><span>视觉贴近已确认首页，不用再在功能页和首页之间来回跳戏。</span></div>
        </div>
      </div>
    </section>

    <section class="glass auth-panel nebula-form-panel">
      <div class="section-kicker">Sign In</div>
      <h2>登录你的 PulseNest 账号</h2>
      <p class="desc">支持邮箱或用户名登录，密码使用 PHP 原生哈希校验，登录成功后回首页并立即看到登录态变化。</p>

      <div class="tabs-auth">
        <a class="tab active" href="/login.php">登录</a>
        <a class="tab" href="/register.php">注册</a>
      </div>

      <?php if ($error): ?><div class="notice error"><?= e($error) ?></div><?php endif; ?>
      <?php if ($success): ?><div class="notice success"><?= e($success) ?></div><?php endif; ?>

      <form class="form" method="post">
        <div class="field">
          <label>邮箱 / 用户名</label>
          <input class="input" name="identifier" value="<?= e($identifier) ?>" placeholder="输入你的邮箱或用户名" />
        </div>
        <div class="field">
          <label>密码</label>
          <input class="input" type="password" name="password" placeholder="输入密码" />
        </div>
        <div class="row compact-row">
          <div class="checkbox"><span class="box"></span><span>记住当前设备（原型展示）</span></div>
          <a class="link" href="/forgot-password.php">忘记密码？</a>
        </div>
        <button class="submit" type="submit">立即登录</button>
      </form>

      <div class="bottom-tip">还没有账号？<a class="link" href="/register.php">去注册</a>。</div>
    </section>
  </div>
<?php render_footer(); ?>
