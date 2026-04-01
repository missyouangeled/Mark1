<?php
require_once __DIR__ . '/config.php';

function render_header(string $title, ?array $user = null, array $options = []): void {
    $showSearch = $options['showSearch'] ?? true;
    $searchText = $options['searchText'] ?? '🔎 搜索榜单、话题、作者、游戏名';
    $headerMode = $options['headerMode'] ?? 'default';
    $unreadCount = $user ? unread_notification_count((int) $user['id']) : 0;
    $headerStripText = '今日焦点：版块浏览 / 内容搜索 / 回复提醒';
    if ($user) {
        $headerStripText = match (user_role($user)) {
            'admin' => '已登录 · ' . e($user['nickname']) . '，管理员入口已开启：内容、角色、结构与日志均可处理。',
            'moderator' => '已登录 · ' . e($user['nickname']) . '，当前为版主权限：可巡检内容与日志，不开放用户和结构调整。',
            default => '已登录 · ' . e($user['nickname']) . '，当前为普通用户：可发帖、评论、看提醒，后台入口不会显示。',
        };
    }
    ?>
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title><?= e($title) ?></title>
  <link rel="stylesheet" href="/style.css" />
</head>
<body class="mode-<?= e($headerMode) ?>">
  <header class="site-header">
    <div class="header-glow">
      <div class="shell header-strip">
        <div class="header-pill">社区热度实时刷新中</div>
        <div class="header-strip-text"><?= $headerStripText ?></div>
      </div>
    </div>
    <div class="shell site-header-main">
      <a class="brand" href="/">
        <div class="brand-mark">PN</div>
        <div>
          <div class="brand-title">PulseNest</div>
          <div class="brand-sub">像逛热门论坛一样找下一款会沉迷的游戏</div>
        </div>
      </a>
      <nav class="nav">
        <a href="/">首页</a>
        <a href="/posts.php">发现</a>
        <a href="/notifications.php">提醒<?= $user && $unreadCount ? '<span class="nav-badge">' . $unreadCount . '</span>' : '' ?></a>
        <a href="/account.php">会员中心</a>
        <?php if ($user && can_access_admin($user)): ?>
          <a href="/admin.php">后台</a>
        <?php endif; ?>
      </nav>
      <div class="header-actions">
        <?php if ($showSearch): ?>
          <div class="search"><?= $searchText ?></div>
        <?php endif; ?>

        <?php if ($user): ?>
          <?php if (can_access_admin($user)): ?>
            <a class="header-user-chip" href="/admin.php"><span><?= is_admin($user) ? '后台管理' : '版主管理' ?></span></a>
          <?php endif; ?>
          <a class="header-user-chip" href="/notifications.php">
            <span>提醒<?= $unreadCount ? ' · ' . $unreadCount : '' ?></span>
          </a>
          <a class="header-user-chip" href="/account.php">
            <?= render_avatar($user, 'mini-avatar') ?>
            <span><?= e($user['nickname']) ?></span>
          </a>
          <a class="pill-btn" href="/create-post.php">发帖</a>
          <a class="pill-btn solid" href="/logout.php">退出</a>
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
