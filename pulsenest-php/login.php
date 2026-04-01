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
        $stmt = db()->prepare('SELECT id, username, nickname, email, password_hash, created_at FROM pulsenest_users WHERE email = :id OR username = :id LIMIT 1');
        $stmt->execute(['id' => $identifier]);
        $user = $stmt->fetch();

        if (!$user || !password_verify($password, $user['password_hash'])) {
            $error = '账号不存在，或密码不正确。';
        } else {
            login_user($user);
            flash_set('success', '欢迎回来，已经为你登录。');
            redirect_to('/');
        }
    }
}

render_header('PulseNest · 登录', null, ['showSearch' => false]);
?>
  <div class="shell auth-wrap">
    <section class="auth-hero">
      <div class="auth-hero-inner">
        <div class="auth-badge">社区身份同步 · 登录后继续逛论坛与内容流</div>
        <div class="auth-copy">
          <h1>回来就好，继续从你上次停下的地方开始。</h1>
          <p>PulseNest 的登录页继续保持首页那种带氛围、有层次、但不拧巴的质感。你不是进入后台，而是重新回到自己的社区位置。</p>
        </div>
        <div class="hero-points">
          <div class="hero-point"><strong>同步</strong><span>继续查看关注的论坛、收藏内容和最近浏览。</span></div>
          <div class="hero-point"><strong>参与</strong><span>登录后可以发帖、回复、点赞，也能发布动态。</span></div>
          <div class="hero-point"><strong>发现</strong><span>系统会根据你的偏好推荐更多值得点开的内容。</span></div>
        </div>
      </div>
    </section>

    <section class="auth-panel">
      <div class="kicker">Sign In</div>
      <h2>登录你的 PulseNest 账号</h2>
      <p class="desc">继续查看论坛、游戏内容流、收藏和动态记录。视觉和首页一致，但把注意力收束到“快速进入”这件事上。</p>

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
        <div class="row">
          <div class="checkbox"><span class="box"></span><span>记住当前设备（原型展示）</span></div>
          <a class="link" href="/forgot-password.php">忘记密码？</a>
        </div>
        <button class="submit" type="submit">立即登录</button>
      </form>

      <div class="bottom-tip">还没有账号？<a class="link" href="/register.php">去注册</a>。</div>
    </section>
  </div>
<?php render_footer(); ?>