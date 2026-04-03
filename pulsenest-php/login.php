<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
ensure_guest_only();

$error = '';
$success = isset($_GET['reset']) ? '密码已更新，现在可以直接登录。' : '';
if (!site_setting_enabled('site.login_enabled', true)) {
    $error = '当前站点暂时关闭登录入口。';
}
$identifier = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && site_setting_enabled('site.login_enabled', true)) {
    $identifier = trim($_POST['identifier'] ?? '');
    $password = (string) ($_POST['password'] ?? '');

    if ($identifier === '' || $password === '') {
        $error = '请先填写账号和密码。';
    } else {
        $stmt = db()->prepare('SELECT id, username, nickname, email, password_hash, avatar_path, bio, is_admin, is_active, role, created_at FROM pulsenest_users WHERE email = :id OR username = :id LIMIT 1');
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
          <div class="auth-badge">纳达尔星项目 · 星云初始03 · 登录入口</div>
          <div class="auth-copy auth-copy-wide">
            <h1>回来就好，继续从你上次停下的地方开始。</h1>
            <p>登录页现在也按整站统一标准收口：标题层级、说明文字、表单节奏和左侧导览信息都更像正式产品，不再只是一个能提交账号密码的原型页。</p>
          </div>
        </div>

        <div class="hero-points">
          <div class="hero-point"><strong>同步身份</strong><span>登录后会立即恢复你的个人状态、提醒入口和内容权限，不再需要额外跳转确认。</span></div>
          <div class="hero-point"><strong>继续参与</strong><span>回到内容流、帖子详情和会员中心时，所有主操作都会直接进入可用状态。</span></div>
          <div class="hero-point"><strong>保持一致</strong><span>这一页和首页、提醒中心、会员中心共用同一套成品化语言，不再有“入口页掉档”的感觉。</span></div>
        </div>
      </div>
    </section>

    <section class="glass auth-panel nebula-form-panel">
      <div class="section-kicker">Sign In</div>
      <h2>登录你的 PulseNest 账号</h2>
      <p class="desc">支持邮箱或用户名登录。登录成功后会立即回到首页，并同步你在内容流、提醒中心与会员中心的身份状态。</p>

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
        <div class="row compact-row auth-utility-row">
          <div class="checkbox"><span class="box"></span><span>记住当前设备（原型展示）</span></div>
          <a class="link" href="/forgot-password.php">忘记密码？</a>
        </div>
        <button class="submit" type="submit">立即登录</button>
      </form>

      <div class="bottom-tip">还没有账号？<a class="link" href="/register.php">去注册</a>。</div>
    </section>
  </div>
<?php render_footer(); ?>
