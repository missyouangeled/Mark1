<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
ensure_guest_only();

$error = '';
if (!site_setting_enabled('site.registration_enabled', true)) {
    $error = '当前站点暂时关闭新用户注册。';
}
$form = [
    'nickname' => '',
    'username' => '',
    'email' => '',
];

if ($_SERVER['REQUEST_METHOD'] === 'POST' && site_setting_enabled('site.registration_enabled', true)) {
    $form['nickname'] = trim($_POST['nickname'] ?? '');
    $form['username'] = trim($_POST['username'] ?? '');
    $form['email'] = trim($_POST['email'] ?? '');
    $password = (string) ($_POST['password'] ?? '');
    $confirm = (string) ($_POST['confirm_password'] ?? '');

    if ($form['nickname'] === '' || $form['username'] === '' || $form['email'] === '' || $password === '' || $confirm === '') {
        $error = '请把所有字段填写完整。';
    } elseif (!preg_match('/^[a-zA-Z0-9_]{3,24}$/', $form['username'])) {
        $error = '用户名需为 3-24 位字母、数字或下划线。';
    } elseif (!filter_var($form['email'], FILTER_VALIDATE_EMAIL)) {
        $error = '邮箱格式不正确。';
    } elseif ($password !== $confirm) {
        $error = '两次输入的密码不一致。';
    } elseif (mb_strlen($password) < 6) {
        $error = '密码至少需要 6 位。';
    } else {
        $stmt = db()->prepare('SELECT id FROM pulsenest_users WHERE email = :email OR username = :username LIMIT 1');
        $stmt->execute(['email' => $form['email'], 'username' => $form['username']]);
        if ($stmt->fetch()) {
            $error = '这个邮箱或用户名已经被使用了。';
        } else {
            $insert = db()->prepare('INSERT INTO pulsenest_users (username, nickname, email, password_hash, is_admin, is_active) VALUES (:username, :nickname, :email, :hash, 0, 1)');
            $insert->execute([
                'username' => $form['username'],
                'nickname' => $form['nickname'],
                'email' => $form['email'],
                'hash' => password_hash($password, PASSWORD_DEFAULT),
            ]);

            $userId = (int) db()->lastInsertId();
            $select = db()->prepare('SELECT id, username, nickname, email, avatar_path, bio, is_admin, is_active, role, created_at FROM pulsenest_users WHERE id = :id LIMIT 1');
            $select->execute(['id' => $userId]);
            $user = $select->fetch();
            login_user($user);
            flash_set('success', '注册完成，已经自动帮你登录。');
            redirect_to('/');
        }
    }
}

render_header('PulseNest · 注册', null, ['showSearch' => false, 'headerMode' => 'auth']);
?>
  <div class="shell auth-wrap nebula-auth-wrap">
    <section class="glass auth-hero register nebula-panel">
      <div class="auth-hero-inner">
        <div>
          <div class="auth-badge">纳达尔星项目 · 星云初始03 · 注册入口</div>
          <div class="auth-copy auth-copy-wide">
            <h1>用一个新的账号，正式进入这个会让你停留的社区。</h1>
            <p>注册页也按当前整站标准重新对齐：不是单纯堆表单，而是把身份建立、进入讨论和后续使用路径讲清楚。提交后会直接写入数据库并自动登录。</p>
          </div>
        </div>

        <div class="feature-list">
          <div class="feature"><div class="dot">01</div><div><strong>建立身份</strong><span>昵称、用户名、邮箱和密码都在这里一次完成，注册后可直接进入会员中心维护资料。</span></div></div>
          <div class="feature"><div class="dot">02</div><div><strong>加入讨论</strong><span>注册完成即自动登录，内容流、提醒中心、发帖入口会立刻切到你的身份状态。</span></div></div>
          <div class="feature"><div class="dot">03</div><div><strong>平滑进入</strong><span>注册页现在和首页、登录页共用同一套排版节奏，观感更像完整产品，而不是孤立表单。</span></div></div>
        </div>
      </div>
    </section>

    <section class="glass auth-panel nebula-form-panel">
      <div class="section-kicker">Create Account</div>
      <h2>创建你的 PulseNest 账号</h2>
      <p class="desc">注册成功后会自动建立 session 并跳回首页。顶部导航、首页主行动、提醒中心和会员中心会立刻切换到你的登录态。</p>

      <div class="tabs-auth">
        <a class="tab" href="/login.php">登录</a>
        <a class="tab active" href="/register.php">注册</a>
      </div>

      <?php if ($error): ?><div class="notice error"><?= e($error) ?></div><?php endif; ?>

      <form class="form" method="post">
        <div class="grid-2">
          <div class="field"><label>昵称</label><input class="input" name="nickname" value="<?= e($form['nickname']) ?>" placeholder="输入你想展示的昵称" /></div>
          <div class="field"><label>用户名</label><input class="input" name="username" value="<?= e($form['username']) ?>" placeholder="设置唯一用户名" /></div>
        </div>
        <div class="field"><label>邮箱地址</label><input class="input" name="email" value="<?= e($form['email']) ?>" placeholder="输入常用邮箱" /></div>
        <div class="grid-2">
          <div class="field"><label>密码</label><input class="input" type="password" name="password" placeholder="设置密码" /></div>
          <div class="field"><label>确认密码</label><input class="input" type="password" name="confirm_password" placeholder="再次输入密码" /></div>
        </div>
        <div class="agreement">注册即表示你同意 PulseNest 的<a class="link" href="#">用户协议</a>与<a class="link" href="#">隐私政策</a>，并接受论坛社区规则。</div>
        <button class="submit" type="submit">立即创建账号</button>
      </form>

      <div class="bottom-tip">已经有账号了？<a class="link" href="/login.php">去登录</a>。</div>
    </section>
  </div>
<?php render_footer(); ?>
