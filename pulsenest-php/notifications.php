<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = trim((string) ($_POST['action'] ?? 'mark_all_read'));
    $filterType = trim((string) ($_POST['filter_type'] ?? ''));
    $allowedTypes = ['post_reply', 'comment_reply', 'post_like', 'comment_like', 'comment_moderated', 'post_moderated', 'report_processed'];
    if ($filterType !== '' && !in_array($filterType, $allowedTypes, true)) {
        $filterType = '';
    }

    if ($action === 'mark_all_read') {
        db()->prepare('UPDATE notifications SET is_read = 1 WHERE recipient_user_id = :user_id AND is_read = 0')->execute([
            'user_id' => $user['id'],
        ]);
        flash_set('success', '已将当前账号下所有提醒标记为已读。');
    } elseif ($action === 'mark_filtered_read') {
        $sql = 'UPDATE notifications SET is_read = 1 WHERE recipient_user_id = :user_id AND is_read = 0';
        $params = ['user_id' => $user['id']];
        if ($filterType !== '') {
            $sql .= ' AND type = :type';
            $params['type'] = $filterType;
        }
        db()->prepare($sql)->execute($params);
        flash_set('success', $filterType !== '' ? '已将该类型未读提醒全部标为已读。' : '已将当前筛选结果中的未读提醒标为已读。');
    } elseif ($action === 'clear_type') {
        if ($filterType === '') {
            flash_set('error', '清空某一类提醒前，请先选择提醒类型。');
        } else {
            db()->prepare('DELETE FROM notifications WHERE recipient_user_id = :user_id AND type = :type')->execute([
                'user_id' => $user['id'],
                'type' => $filterType,
            ]);
            flash_set('success', '已清空“' . notification_type_label($filterType) . '”提醒。');
        }
    }

    $redirectQuery = [];
    if (!empty($_POST['redirect_only_unread'])) {
        $redirectQuery['unread'] = '1';
    }
    if ($filterType !== '') {
        $redirectQuery['type'] = $filterType;
    }
    $redirect = '/notifications.php';
    if ($redirectQuery) {
        $redirect .= '?' . http_build_query($redirectQuery);
    }
    redirect_to($redirect);
}

$flash = flash_get();
$selectedType = trim((string) ($_GET['type'] ?? ''));
$onlyUnread = (int) ($_GET['unread'] ?? 0) === 1;
$allowedTypes = ['post_reply', 'comment_reply', 'post_like', 'comment_like', 'comment_moderated', 'post_moderated', 'report_processed'];
if ($selectedType !== '' && !in_array($selectedType, $allowedTypes, true)) {
    $selectedType = '';
}

$where = ['n.recipient_user_id = :user_id'];
$params = ['user_id' => $user['id']];
if ($selectedType !== '') {
    $where[] = 'n.type = :type';
    $params['type'] = $selectedType;
}
if ($onlyUnread) {
    $where[] = 'n.is_read = 0';
}

$stmt = db()->prepare(
    'SELECT n.id, n.type, n.moderation_status, n.note, n.is_read, n.created_at,
            p.id AS post_id, p.title,
            c.content AS comment_content,
            actor.id AS actor_id, actor.nickname AS actor_nickname, actor.username AS actor_username, actor.avatar_path AS actor_avatar_path
     FROM notifications n
     INNER JOIN posts p ON p.id = n.post_id
     LEFT JOIN comments c ON c.id = n.comment_id
     INNER JOIN pulsenest_users actor ON actor.id = n.actor_user_id
     WHERE ' . implode(' AND ', $where) . '
     ORDER BY n.created_at DESC, n.id DESC'
);
$stmt->execute($params);
$notifications = $stmt->fetchAll();
$unreadCount = unread_notification_count((int) $user['id']);

$typeRowsStmt = db()->prepare(
    'SELECT type, COUNT(*) AS total_count, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread_count
     FROM notifications
     WHERE recipient_user_id = :user_id
     GROUP BY type
     ORDER BY total_count DESC, type ASC'
);
$typeRowsStmt->execute(['user_id' => $user['id']]);
$typeRows = $typeRowsStmt->fetchAll();

$todayStmt = db()->prepare('SELECT COUNT(*) FROM notifications WHERE recipient_user_id = :user_id AND created_at >= NOW() - INTERVAL 1 DAY');
$todayStmt->execute(['user_id' => $user['id']]);
$todayCount = (int) $todayStmt->fetchColumn();

$weekStmt = db()->prepare('SELECT COUNT(*) FROM notifications WHERE recipient_user_id = :user_id AND created_at >= NOW() - INTERVAL 7 DAY');
$weekStmt->execute(['user_id' => $user['id']]);
$weekCount = (int) $weekStmt->fetchColumn();

$userPostCountStmt = db()->prepare('SELECT COUNT(*) FROM posts WHERE user_id = :user_id AND status = "published"');
$userPostCountStmt->execute(['user_id' => $user['id']]);
$userPostCount = (int) $userPostCountStmt->fetchColumn();

$currentResultCount = count($notifications);
$notificationFocus = match (true) {
    $unreadCount > 0 && in_array($selectedType, ['comment_reply', 'post_reply'], true) => [
        'label' => '优先接住回复',
        'note' => '当前筛选已经聚焦到回复提醒，先把对话接住，比继续堆动作更像成熟社区里的正常节奏。',
        'cta' => '处理完回复后，再决定要不要继续发内容。',
    ],
    $unreadCount > 0 => [
        'label' => '先清掉未读压力',
        'note' => '现在更自然的动作不是四处跳转，而是先把未读提醒处理掉，让互动链路在这里收口。',
        'cta' => '可以从回复类提醒开始，再回到内容流或会员中心。',
    ],
    $todayCount > 0 || $weekCount > 0 => [
        'label' => '互动已经落地',
        'note' => '最近一段时间已经有新的点赞、回复或系统回执，提醒中心更像你的互动收纳层，而不是静态消息页。',
        'cta' => '如果这里暂时清空了，可以回主页继续观察内容反馈。',
    ],
    default => [
        'label' => '提醒还很安静',
        'note' => '现在没有太多互动压力，适合回到资料页或内容流，把下一次公开动作准备好。',
        'cta' => '先写内容或补资料，下一波提醒自然会回来。',
    ],
};
$interactionClosure = creator_loop_summary($user, [
    'post_count' => $userPostCount,
    'unread_count' => $unreadCount,
]);
render_header('PulseNest · 我的提醒', $user, [
    'searchText' => '🔎 提醒支持未读筛选、类型筛选、批量已读和按类型清空',
]);
?>
<main class="shell page-shell nebula-page-shell notifications-page">
  <?php render_breadcrumbs([
      ['label' => '首页', 'href' => '/'],
      ['label' => '提醒中心'],
  ]); ?>

  <?php if ($flash): ?>
    <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
  <?php endif; ?>

  <section class="glass nebula-hero nebula-hero-split refined-hero refined-hero-notifications">
    <div class="nebula-copy">
      <div class="brand-chip">纳达尔星项目 · 星云初始03 · 站内提醒</div>
      <h1>提醒中心已经从“消息列表”，收口成更接近成品的个人工作台。</h1>
      <p class="page-desc nebula-desc">现在这里会把回复、点赞、审核结果与举报回执统一编排成更清晰的节奏：先看未读压力，再看类型分布，最后处理具体提醒，阅读路径更稳定，状态也更好懂。</p>
      <div class="hero-stats compact-hero-stats refined-hero-stats">
        <div class="hero-stat"><div class="label">未读提醒</div><div class="num"><?= $unreadCount ?></div><div class="note">头部导航同步显示</div></div>
        <div class="hero-stat"><div class="label">当前结果</div><div class="num"><?= $currentResultCount ?></div><div class="note"><?= $onlyUnread ? '当前仅看未读' : '当前为全部状态' ?></div></div>
        <div class="hero-stat"><div class="label">24 小时</div><div class="num"><?= $todayCount ?></div><div class="note">最近一天新增提醒</div></div>
        <div class="hero-stat"><div class="label">7 天</div><div class="num"><?= $weekCount ?></div><div class="note">最近七天互动节奏</div></div>
      </div>
    </div>
    <aside class="glass side-card nebula-side-panel ops-side-panel">
      <div class="section-kicker">Quick Action</div>
      <form method="get" class="form compact-form">
        <input type="hidden" name="type" value="<?= e($selectedType) ?>">
        <label class="muted"><input type="checkbox" name="unread" value="1" <?= $onlyUnread ? 'checked' : '' ?>> 只看未读</label>
        <button class="submit" type="submit">应用筛选</button>
      </form>
      <form method="post" class="form compact-form">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <input type="hidden" name="action" value="mark_all_read">
        <button class="submit" type="submit">全部标记为已读</button>
      </form>
      <div class="quick-links compact-link-stack">
        <a class="quick-link" href="/posts.php"><strong>去看帖子流</strong><span>回到公开内容流，看看互动是从哪些内容线接进来的。</span></a>
        <a class="quick-link" href="/create-post.php"><strong>继续发帖</strong><span>当提醒已经接稳后，再顺着当前节奏补一篇新内容。</span></a>
        <a class="quick-link" href="/account.php"><strong>回会员中心</strong><span>查看资料完成度、成员阶段和最近内容反馈。</span></a>
      </div>
    </aside>
  </section>

  <section class="glass panel-card surface-section notification-route-strip">
    <div class="creator-route-copy">
      <div class="section-kicker">Response Rhythm</div>
      <h3><?= e($notificationFocus['label']) ?></h3>
      <p class="muted"><?= e($notificationFocus['note']) ?></p>
    </div>
    <div class="creator-route-meta">
      <div class="route-mini-card"><strong><?= $unreadCount ?></strong><span>当前未读</span></div>
      <div class="route-mini-card"><strong><?= e($selectedType !== '' ? notification_type_label($selectedType) : '全部提醒') ?></strong><span>当前视角</span></div>
      <div class="route-mini-card"><strong><?= e($notificationFocus['cta']) ?></strong><span>下一步建议</span></div>
    </div>
  </section>

  <section class="glass panel-card surface-section interaction-closure-strip">
    <div class="creator-route-copy">
      <div class="section-kicker">After Interaction</div>
      <h3><?= e($interactionClosure['label']) ?></h3>
      <p class="muted"><?= e($interactionClosure['note']) ?></p>
    </div>
    <div class="creator-route-meta">
      <div class="route-mini-card"><strong><?= e($interactionClosure['next']) ?></strong><span>自然下一步</span></div>
      <div class="route-mini-card"><strong><?= $todayCount ?></strong><span>24h 内回流</span></div>
      <div class="route-mini-card"><strong><?= $weekCount ?></strong><span>7 天内互动</span></div>
    </div>
  </section>

  <section class="glass panel-card admin-panel-card surface-section surface-section-tight">
    <div class="section-kicker">Filter</div>
    <div class="side-head admin-head-row"><h3>提醒筛选与批量操作</h3><span class="muted">先筛，再一键处理当前类型。</span></div>
    <form class="admin-filter-row" method="get" action="/notifications.php">
      <select class="input admin-filter-input" name="type">
        <option value="">全部类型</option>
        <?php foreach ($allowedTypes as $type): ?>
          <option value="<?= e($type) ?>" <?= $selectedType === $type ? 'selected' : '' ?>><?= e(notification_type_label($type)) ?></option>
        <?php endforeach; ?>
      </select>
      <label class="muted"><input type="checkbox" name="unread" value="1" <?= $onlyUnread ? 'checked' : '' ?>> 只看未读</label>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="/notifications.php">清空</a>
    </form>
    <div class="admin-bulk-bar">
      <form method="post" class="inline-form">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <input type="hidden" name="action" value="mark_filtered_read">
        <input type="hidden" name="filter_type" value="<?= e($selectedType) ?>">
        <input type="hidden" name="redirect_only_unread" value="<?= $onlyUnread ? '1' : '0' ?>">
        <button class="pill-btn solid" type="submit">将当前筛选结果设为已读</button>
      </form>
      <form method="post" class="inline-form" onsubmit="return confirm('确认清空当前所选类型的全部通知？此操作不可撤销。');">
        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
        <input type="hidden" name="action" value="clear_type">
        <input type="hidden" name="filter_type" value="<?= e($selectedType) ?>">
        <input type="hidden" name="redirect_only_unread" value="<?= $onlyUnread ? '1' : '0' ?>">
        <button class="pill-btn danger" type="submit" <?= $selectedType === '' ? 'disabled' : '' ?>>清空当前类型</button>
      </form>
    </div>
  </section>

  <section class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">Type Snapshot</div>
    <div class="side-head admin-head-row"><h3>提醒类型分布</h3><span class="muted">你能快速看出最近更多是被回复，还是被点赞。</span></div>
    <div class="admin-table-wrap">
      <table class="admin-table compact-table">
        <thead><tr><th>类型</th><th>总量</th><th>未读</th><th>说明</th></tr></thead>
        <tbody>
          <?php foreach ($typeRows as $row): ?>
            <tr>
              <td><span class="tiny-badge"><?= e(notification_type_label($row['type'])) ?></span><div class="muted"><?= e($row['type']) ?></div></td>
              <td><?= (int) $row['total_count'] ?></td>
              <td><?= (int) $row['unread_count'] ?></td>
              <td><?= e(match ($row['type']) {
                'post_like' => '有人点赞你的帖子',
                'comment_like' => '有人点赞你的评论',
                'comment_reply' => '有人回复你的评论',
                'comment_moderated' => '你的评论被审核后，会明确告诉你当前是已通过还是已隐藏',
                'post_moderated' => '你的帖子被审核后，会明确告诉你当前是已发布、待审核还是已隐藏',
                'report_processed' => '你提交的举报进入处理中、已处理或已驳回时，会收到明确回执，并尽量附带联动处置说明',
                default => '有人回复你的帖子',
              }) ?></td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$typeRows): ?>
            <tr><td colspan="4" class="muted">还没有任何提醒统计，等第一波互动来点亮这里。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
  </section>

  <section class="glass panel-card surface-section notification-feed-section">
    <div class="section-kicker">Notification Feed</div>
    <div class="side-head admin-head-row"><h3>提醒列表</h3><span class="muted">评论审核通知会直接标出“已通过 / 已隐藏”，不再只给一个模糊的状态更新。</span></div>
    <div class="list-stack notification-stack curated-stack">
      <?php if (!$notifications): ?>
        <div class="empty-inline nebula-empty">当前筛选条件下没有提醒。换个类型，或者等下一次互动把这里点亮。</div>
      <?php else: ?>
        <?php foreach ($notifications as $item): ?>
          <?php $moderationCopy = match ($item['type'] ?? '') {
            'comment_moderated' => notification_moderation_copy($item['moderation_status'] ?? null, 'comment'),
            'post_moderated' => notification_moderation_copy($item['moderation_status'] ?? null, 'post'),
            'report_processed' => notification_report_copy($item['moderation_status'] ?? null, $item['note'] ?? null),
            default => null,
          }; ?>
          <article class="notification-card <?= (int) $item['is_read'] === 0 ? 'unread' : '' ?>">
            <div class="post-head">
              <div class="user">
                <?= render_avatar([
                  'avatar_path' => $item['actor_avatar_path'],
                  'nickname' => $item['actor_nickname'],
                  'username' => $item['actor_username'],
                ], 'user-avatar') ?>
                <div>
                  <div class="user-name-line"><?= e($item['actor_nickname']) ?> <span class="tiny-badge">@<?= e($item['actor_username']) ?></span></div>
                  <div class="muted"><?= e(human_time($item['created_at'])) ?> · <?= e(notification_type_label($item['type'])) ?><?= $moderationCopy ? ' · ' . e($moderationCopy['label']) : '' ?></div>
                </div>
              </div>
              <span class="small-chip <?= (int) $item['is_read'] === 0 ? 'a' : 'b' ?>"><?= (int) $item['is_read'] === 0 ? '未读' : '已读' ?></span>
            </div>
            <div class="comment-body">
              <?= e(match ($item['type']) {
                'comment_reply' => '回复了你的评论：',
                'post_like' => '点赞了你的帖子：',
                'comment_like' => '点赞了你在这篇帖子下的评论：',
                'comment_moderated' => ($moderationCopy['summary'] ?? '你的评论审核状态已更新') . '，关联帖子：',
                'post_moderated' => ($moderationCopy['summary'] ?? '你的帖子审核状态已更新') . '：',
                'report_processed' => ($moderationCopy['summary'] ?? '你提交的举报状态已更新') . '：',
                default => '回复了你的帖子：',
              }) ?>
              <a class="inline-link" href="/post.php?id=<?= (int) $item['post_id'] ?>"><?= e($item['title']) ?></a>
            </div>
            <?php if ($moderationCopy): ?>
              <div class="chips" style="margin-top: 10px; gap: 6px;">
                <span class="chip"><?= e(($item['type'] ?? '') === 'report_processed' ? '处理结果' : '审核结果') ?> · <?= e($moderationCopy['label']) ?></span>
                <?php if (!empty($item['comment_content'])): ?><span class="chip">评论已留痕</span><?php endif; ?>
              </div>
              <div class="muted" style="margin-top: 8px;"><?= e($moderationCopy['description']) ?></div>
            <?php endif; ?>
            <?php if (!empty($item['comment_content'])): ?>
              <div class="muted" style="margin-top: 8px;">关联评论：<?= e(excerpt($item['comment_content'], 72)) ?></div>
            <?php endif; ?>
            <div class="notification-followup-note"><?= e(notification_follow_up_hint($item)) ?></div>
          </article>
        <?php endforeach; ?>
      <?php endif; ?>
    </div>
  </section>
</main>
<?php render_footer(); ?>
