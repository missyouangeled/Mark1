<?php
require_once __DIR__ . '/config.php';

function render_header(string $title, ?array $user = null, array $options = []): void {
    $showSearch = $options['showSearch'] ?? true;
    $searchText = $options['searchText'] ?? '🔎&nbsp;&nbsp;搜索你下一款会沉迷的游戏';
    ?>
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title><?= e($title) ?></title>
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <header class="topbar">
    <div class="shell topbar-inner">
      <a class="brand" href="/"><div class="brand-mark">PN</div><div>PulseNest</div></a>
      <?php if ($showSearch): ?>
        <div class="search"><?= $searchText ?></div>
      <?php else: ?>
        <div></div>
      <?php endif; ?>
      <div class="actions">
        <?php if ($user): ?>
          <a class="pill-btn" href="/account.php"><?= e($user['nickname']) ?></a>
          <a class="pill-btn" href="/create-post.php">发帖</a>
          <a class="pill-btn" href="/logout.php">退出登录</a>
        <?php else: ?>
          <a class="pill-btn" href="/login.php">登录</a>
          <a class="pill-btn solid" href="/register.php">注册</a>
        <?php endif; ?>
      </div>
    </div>
  </header>
<?php
}

function render_footer(): void {
    echo "\n</body>\n</html>";
}
