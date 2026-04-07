<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$staff = ensure_staff();
$userId = (int) ($_GET['id'] ?? 0);
$flash = flash_get();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = trim((string) ($_POST['action'] ?? ''));
    $targetUserId = (int) ($_POST['user_id'] ?? 0);
    if ($targetUserId !== $userId || $targetUserId <= 0) {
        flash_set('error', '治理档案目标用户不匹配。');
        redirect_to('/user-governance.php?id=' . max(0, $userId));
    }

    if ($action === 'add_governance_note') {
        $noteType = trim((string) ($_POST['note_type'] ?? 'warning'));
        $severity = trim((string) ($_POST['severity'] ?? 'medium'));
        $reason = trim((string) ($_POST['reason'] ?? ''));
        $detail = trim((string) ($_POST['detail'] ?? ''));
        if (!in_array($noteType, ['warning', 'watch', 'ban'], true) || !in_array($severity, ['low', 'medium', 'high'], true) || $reason === '') {
            flash_set('error', '治理记录参数不完整。');
        } else {
            db()->prepare('INSERT INTO user_governance_notes (user_id, actor_user_id, note_type, severity, reason, detail) VALUES (:user_id, :actor_user_id, :note_type, :severity, :reason, :detail)')->execute([
                'user_id' => $targetUserId,
                'actor_user_id' => (int) $staff['id'],
                'note_type' => $noteType,
                'severity' => $severity,
                'reason' => mb_substr($reason, 0, 255),
                'detail' => $detail !== '' ? $detail : null,
            ]);
            if ($noteType === 'ban') {
                db()->prepare('UPDATE pulsenest_users SET is_active = 0 WHERE id = :id LIMIT 1')->execute(['id' => $targetUserId]);
            }
            log_moderation_action((int) $staff['id'], 'user_governance_note_added', 'user', $targetUserId, governance_note_type_label($noteType) . ' · 风险等级 ' . governance_severity_label($severity));
            flash_set('success', '治理记录已添加。');
        }
        redirect_to('/user-governance.php?id=' . $targetUserId);
    }

    if ($action === 'update_governance_note_status') {
        $noteId = (int) ($_POST['note_id'] ?? 0);
        $targetStatus = trim((string) ($_POST['target_status'] ?? 'resolved'));
        if (!in_array($targetStatus, ['open', 'resolved', 'dismissed'], true)) {
            flash_set('error', '治理记录状态无效。');
        } else {
            $stmt = db()->prepare('SELECT id, user_id, note_type, status FROM user_governance_notes WHERE id = :id AND user_id = :user_id LIMIT 1');
            $stmt->execute(['id' => $noteId, 'user_id' => $targetUserId]);
            $note = $stmt->fetch();
            if (!$note) {
                flash_set('error', '没有找到目标治理记录。');
            } else {
                db()->prepare('UPDATE user_governance_notes SET status = :status WHERE id = :id LIMIT 1')->execute([
                    'status' => $targetStatus,
                    'id' => $noteId,
                ]);
                if (($note['note_type'] ?? '') === 'ban' && $targetStatus !== 'open') {
                    db()->prepare('UPDATE pulsenest_users SET is_active = 1 WHERE id = :id LIMIT 1')->execute(['id' => $targetUserId]);
                }
                log_moderation_action((int) $staff['id'], 'user_governance_note_status_updated', 'user', $targetUserId, '治理记录 #' . $noteId . ' → ' . governance_status_label($targetStatus));
                flash_set('success', '治理记录状态已更新。');
            }
        }
        redirect_to('/user-governance.php?id=' . $targetUserId);
    }

    if ($action === 'toggle_user_active') {
        $targetStatus = (int) ($_POST['target_status'] ?? 0);
        if ($targetUserId === (int) $staff['id'] && $targetStatus === 0) {
            flash_set('error', '不能停用当前自己。');
        } else {
            db()->prepare('UPDATE pulsenest_users SET is_active = :is_active WHERE id = :id LIMIT 1')->execute([
                'is_active' => $targetStatus ? 1 : 0,
                'id' => $targetUserId,
            ]);
            log_moderation_action((int) $staff['id'], $targetStatus ? 'user_enabled' : 'user_disabled', 'user', $targetUserId, '治理档案页直接操作');
            flash_set('success', $targetStatus ? '用户已启用。' : '用户已停用。');
        }
        redirect_to('/user-governance.php?id=' . $targetUserId);
    }
}

$stmt = db()->prepare(
    'SELECT u.id, u.username, u.nickname, u.email, u.avatar_path, u.bio, u.created_at, u.is_active, u.role,
            COUNT(p.id) AS post_count
     FROM pulsenest_users u
     LEFT JOIN posts p ON p.user_id = u.id AND p.status = "published"
     WHERE u.id = :id
     GROUP BY u.id, u.username, u.nickname, u.email, u.avatar_path, u.bio, u.created_at, u.is_active, u.role
     LIMIT 1'
);
$stmt->execute(['id' => $userId]);
$profile = $stmt->fetch();
if (!$profile) {
    http_response_code(404);
}

$governanceSummary = null;
$governanceRows = [];
$reportSummary = null;
$recentReportedContent = [];
$recentComments = [];
$recentPosts = [];
if ($profile) {
    $govStmt = db()->prepare(
        'SELECT COUNT(*) AS total_notes,
                SUM(CASE WHEN status = "open" THEN 1 ELSE 0 END) AS open_notes,
                SUM(CASE WHEN severity = "high" THEN 1 ELSE 0 END) AS high_risk_notes
         FROM user_governance_notes
         WHERE user_id = :id'
    );
    $govStmt->execute(['id' => $profile['id']]);
    $governanceSummary = $govStmt->fetch() ?: [];

    $govRowsStmt = db()->prepare(
        'SELECT g.id, g.note_type, g.severity, g.status, g.reason, g.detail, g.created_at,
                actor.nickname AS actor_nickname, actor.username AS actor_username
         FROM user_governance_notes g
         INNER JOIN pulsenest_users actor ON actor.id = g.actor_user_id
         WHERE g.user_id = :id
         ORDER BY g.created_at DESC, g.id DESC'
    );
    $govRowsStmt->execute(['id' => $profile['id']]);
    $governanceRows = $govRowsStmt->fetchAll();

    $reportSummaryStmt = db()->prepare(
        'SELECT COUNT(*) AS total_reports,
                SUM(CASE WHEN r.status = "open" THEN 1 ELSE 0 END) AS open_reports,
                SUM(CASE WHEN r.status = "resolved" THEN 1 ELSE 0 END) AS resolved_reports,
                SUM(CASE WHEN r.status = "dismissed" THEN 1 ELSE 0 END) AS dismissed_reports
         FROM reports r
         LEFT JOIN posts p ON p.id = r.post_id
         LEFT JOIN comments c ON c.id = r.comment_id
         WHERE (r.target_type = "post" AND p.user_id = :id)
            OR (r.target_type = "comment" AND c.user_id = :id)'
    );
    $reportSummaryStmt->execute(['id' => $profile['id']]);
    $reportSummary = $reportSummaryStmt->fetch() ?: [];

    $recentReportedStmt = db()->prepare(
        'SELECT r.id, r.target_type, r.reason, r.status, r.created_at, r.post_id, p.title AS post_title, c.content AS comment_content
         FROM reports r
         LEFT JOIN posts p ON p.id = r.post_id
         LEFT JOIN comments c ON c.id = r.comment_id
         WHERE (r.target_type = "post" AND p.user_id = :id)
            OR (r.target_type = "comment" AND c.user_id = :id)
         ORDER BY r.created_at DESC, r.id DESC
         LIMIT 10'
    );
    $recentReportedStmt->execute(['id' => $profile['id']]);
    $recentReportedContent = $recentReportedStmt->fetchAll();

    $recentPostStmt = db()->prepare(
        'SELECT p.id, p.title, p.status, p.view_count, p.created_at,
                COALESCE(l.like_count, 0) AS like_count,
                COALESCE(c.comment_count, 0) AS comment_count
         FROM posts p
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
         ) l ON l.post_id = p.id
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count FROM comments GROUP BY post_id
         ) c ON c.post_id = p.id
         WHERE p.user_id = :id
         ORDER BY p.created_at DESC, p.id DESC
         LIMIT 8'
    );
    $recentPostStmt->execute(['id' => $profile['id']]);
    $recentPosts = $recentPostStmt->fetchAll();

    $recentCommentStmt = db()->prepare(
        'SELECT c.id, c.content, c.status, c.created_at, c.post_id, p.title AS post_title
         FROM comments c
         INNER JOIN posts p ON p.id = c.post_id
         WHERE c.user_id = :id
         ORDER BY c.created_at DESC, c.id DESC
         LIMIT 8'
    );
    $recentCommentStmt->execute(['id' => $profile['id']]);
    $recentComments = $recentCommentStmt->fetchAll();
}

render_header($profile ? ('PulseNest · 治理档案 · ' . $profile['nickname']) : 'PulseNest · 治理档案', $staff, [
    'searchText' => '🔎 staff 视角：用户治理档案、被举报记录、最近治理动作',
]);
?>
<main class="shell page-shell nebula-page-shell user-page governance-page">
  <?php if ($profile): ?>
    <?php render_breadcrumbs([
        ['label' => '后台', 'href' => '/admin.php#users'],
        ['label' => '用户治理'],
        ['label' => $profile['nickname']],
    ]); ?>
  <?php endif; ?>

  <?php if ($flash): ?>
    <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
  <?php endif; ?>
  <?php if (!$profile): ?>
    <section class="glass panel-card empty-inline nebula-empty">没有找到这个用户治理档案。<a class="link" href="/admin.php#users">返回用户管理</a></section>
  <?php else: ?>
    <section class="glass nebula-hero nebula-hero-split user-hero refined-hero refined-hero-governance">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始03 · Staff 档案</div>
        <h1><?= e($profile['nickname']) ?> 的治理档案</h1>
        <p class="page-desc nebula-desc">这里把账号状态、风险记录、被举报情况与近期内容轨迹收束为一张更易读的档案页，staff 不需要在多个表之间来回跳，就能先看风险，再读上下文，再决定动作。</p>
        <div class="hero-stats compact-hero-stats refined-hero-stats">
          <div class="hero-stat"><div class="label">账号状态</div><div class="num small-num"><?= (int) ($profile['is_active'] ?? 1) === 1 ? '启用' : '停用' ?></div><div class="note">角色：<?= e(role_label($profile['role'] ?? 'member')) ?></div></div>
          <div class="hero-stat"><div class="label">治理记录</div><div class="num small-num"><?= (int) ($governanceSummary['total_notes'] ?? 0) ?></div><div class="note">开放中 <?= (int) ($governanceSummary['open_notes'] ?? 0) ?></div></div>
          <div class="hero-stat"><div class="label">高风险</div><div class="num small-num"><?= (int) ($governanceSummary['high_risk_notes'] ?? 0) ?></div><div class="note">累计高风险治理记录</div></div>
          <div class="hero-stat"><div class="label">被举报</div><div class="num small-num"><?= (int) ($reportSummary['total_reports'] ?? 0) ?></div><div class="note">未结 <?= (int) ($reportSummary['open_reports'] ?? 0) ?> · 已处理 <?= (int) ($reportSummary['resolved_reports'] ?? 0) ?></div></div>
        </div>
      </div>
      <aside class="profile-chip nebula-profile-chip user-profile-chip ops-side-panel governance-profile-panel">
        <?= render_avatar($profile, 'user-avatar large') ?>
        <div>
          <strong><?= e($profile['nickname']) ?></strong>
          <span>@<?= e($profile['username']) ?></span>
          <span><?= e($profile['email']) ?></span>
          <span><?= e($profile['bio'] ?: '暂无个性签名') ?></span>
          <span>加入时间：<?= e(substr((string) $profile['created_at'], 0, 16)) ?></span>
        </div>
        <div class="admin-action-stack" style="margin-top:14px;">
          <?php if ((int) $profile['id'] !== (int) $staff['id']): ?>
            <form method="post" class="inline-form">
              <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
              <input type="hidden" name="action" value="toggle_user_active">
              <input type="hidden" name="user_id" value="<?= (int) $profile['id'] ?>">
              <input type="hidden" name="target_status" value="<?= (int) $profile['is_active'] === 1 ? 0 : 1 ?>">
              <button class="pill-btn <?= (int) $profile['is_active'] === 1 ? 'danger' : 'solid' ?>" type="submit"><?= (int) $profile['is_active'] === 1 ? '停用账号' : '恢复账号' ?></button>
            </form>
          <?php endif; ?>
          <a class="pill-btn" href="/user.php?id=<?= (int) $profile['id'] ?>">普通主页视图</a>
        </div>
      </aside>
    </section>

    <div class="nebula-section-grid admin-grid-two">
      <section class="glass panel-card admin-panel-card surface-section">
        <div class="section-kicker">快速操作</div>
        <div class="side-head admin-head-row"><h3>直接追加治理记录</h3><span class="muted">在这个档案页内就能补警告、观察、封禁记录。</span></div>
        <form method="post" class="admin-inline-stack" style="align-items:flex-start; flex-wrap:wrap;">
          <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
          <input type="hidden" name="action" value="add_governance_note">
          <input type="hidden" name="user_id" value="<?= (int) $profile['id'] ?>">
          <select class="input slim-input" name="note_type">
            <option value="warning">警告</option>
            <option value="watch">观察</option>
            <option value="ban">封禁记录</option>
          </select>
          <select class="input slim-input" name="severity">
            <option value="low">低风险</option>
            <option value="medium">中风险</option>
            <option value="high">高风险</option>
          </select>
          <input class="input slim-input" name="reason" placeholder="原因摘要">
          <input class="input slim-input" name="detail" placeholder="补充说明（可选）">
          <button class="pill-btn solid" type="submit">添加记录</button>
        </form>
      </section>

      <section class="glass panel-card admin-panel-card surface-section">
        <div class="section-kicker">最近帖子</div>
        <div class="side-head admin-head-row"><h3>最近帖子</h3><span class="muted">直接看用户最近发了什么，配合治理记录判断上下文。</span></div>
        <div class="list-stack">
          <?php foreach ($recentPosts as $row): ?>
            <div class="list-item">
              <strong><a class="inline-link" href="/post.php?id=<?= (int) $row['id'] ?>"><?= e($row['title']) ?></a> · <?= e(post_status_label($row['status'] ?? 'published')) ?></strong>
              <span><?= (int) ($row['like_count'] ?? 0) ?> 赞 · <?= (int) ($row['comment_count'] ?? 0) ?> 回复 · <?= (int) ($row['view_count'] ?? 0) ?> 浏览</span>
              <span class="muted"><a class="inline-link" href="/admin.php?post_id=<?= (int) $row['id'] ?>#posts">后台帖子定位</a></span>
              <span class="muted"><?= e(substr((string) $row['created_at'], 0, 16)) ?></span>
            </div>
          <?php endforeach; ?>
          <?php if (!$recentPosts): ?><div class="empty-inline nebula-empty">当前用户还没有帖子记录。</div><?php endif; ?>
        </div>
      </section>
    </div>

    <div class="nebula-section-grid admin-grid-two">
      <section class="glass panel-card admin-panel-card surface-section">
        <div class="section-kicker">最近评论</div>
        <div class="side-head admin-head-row"><h3>最近评论</h3><span class="muted">补齐用户最近评论上下文，方便判断问题是否持续发生。</span></div>
        <div class="list-stack">
          <?php foreach ($recentComments as $row): ?>
            <div class="list-item">
              <strong><a class="inline-link" href="/post.php?id=<?= (int) $row['post_id'] ?>"><?= e($row['post_title']) ?></a> · <?= e(comment_status_label($row['status'] ?? 'approved')) ?></strong>
              <span><?= e(excerpt((string) $row['content'], 110)) ?></span>
              <span class="muted"><a class="inline-link" href="/admin.php?post_id=<?= (int) $row['post_id'] ?>#comments">后台评论定位</a></span>
              <span class="muted"><?= e(substr((string) $row['created_at'], 0, 16)) ?></span>
            </div>
          <?php endforeach; ?>
          <?php if (!$recentComments): ?><div class="empty-inline nebula-empty">当前用户还没有评论记录。</div><?php endif; ?>
        </div>
      </section>
    </div>

    <div class="nebula-section-grid admin-grid-two">
      <section class="glass panel-card admin-panel-card surface-section">
        <div class="section-kicker">治理记录</div>
        <div class="side-head admin-head-row"><h3>完整治理记录</h3><span class="muted">这里按时间倒序列出当前用户的所有治理动作，并可直接更新状态。</span></div>
        <div class="admin-table-wrap">
          <table class="admin-table compact-table">
            <thead><tr><th>ID</th><th>类型</th><th>风险</th><th>状态</th><th>原因</th><th>记录人</th><th>操作</th></tr></thead>
            <tbody>
              <?php foreach ($governanceRows as $row): ?>
                <tr>
                  <td>#<?= (int) $row['id'] ?></td>
                  <td><?= e(governance_note_type_label($row['note_type'] ?? 'warning')) ?></td>
                  <td><?= e(governance_severity_label($row['severity'] ?? 'medium')) ?></td>
                  <td><?= e(governance_status_label($row['status'] ?? 'open')) ?></td>
                  <td><?= e($row['reason']) ?><div class="muted"><?= e(excerpt((string) ($row['detail'] ?? ''), 100)) ?></div></td>
                  <td><?= e($row['actor_nickname']) ?><div class="muted">@<?= e($row['actor_username']) ?> · <?= e(substr((string) $row['created_at'], 0, 16)) ?></div></td>
                  <td>
                    <form method="post" class="admin-inline-stack">
                      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                      <input type="hidden" name="action" value="update_governance_note_status">
                      <input type="hidden" name="user_id" value="<?= (int) $profile['id'] ?>">
                      <input type="hidden" name="note_id" value="<?= (int) $row['id'] ?>">
                      <select class="input slim-input" name="target_status">
                        <?php foreach (['open' => '开放中', 'resolved' => '已处理', 'dismissed' => '已关闭'] as $statusKey => $statusLabel): ?>
                          <option value="<?= e($statusKey) ?>" <?= ($row['status'] ?? 'open') === $statusKey ? 'selected' : '' ?>><?= e($statusLabel) ?></option>
                        <?php endforeach; ?>
                      </select>
                      <button class="pill-btn" type="submit">更新</button>
                    </form>
                  </td>
                </tr>
              <?php endforeach; ?>
              <?php if (!$governanceRows): ?><tr><td colspan="7" class="muted">当前用户还没有治理记录。</td></tr><?php endif; ?>
            </tbody>
          </table>
        </div>
      </section>

      <section class="glass panel-card admin-panel-card surface-section">
        <div class="section-kicker">被举报内容</div>
        <div class="side-head admin-head-row"><h3>最近被举报内容</h3><span class="muted">帖子举报与评论举报统一收口在这里，方便 staff 快速回看。</span></div>
        <div class="admin-table-wrap">
          <table class="admin-table compact-table">
            <thead><tr><th>ID</th><th>对象</th><th>理由</th><th>状态</th><th>时间</th></tr></thead>
            <tbody>
              <?php foreach ($recentReportedContent as $row): ?>
                <tr>
                  <td>#<?= (int) $row['id'] ?></td>
                  <td>
                    <span class="tiny-badge"><?= e(($row['target_type'] ?? '') === 'comment' ? '评论' : '帖子') ?></span>
                    <div class="muted"><a class="inline-link" href="/post.php?id=<?= (int) ($row['post_id'] ?? 0) ?>">前台查看</a> · <a class="inline-link" href="/admin.php?post_id=<?= (int) ($row['post_id'] ?? 0) ?>#reports">后台定位</a> · <?= e(($row['target_type'] ?? '') === 'comment' ? excerpt((string) ($row['comment_content'] ?? ''), 72) : ($row['post_title'] ?? '')) ?></div>
                  </td>
                  <td><?= e(report_reason_label($row['reason'] ?? 'other')) ?></td>
                  <td><?= e(report_status_label($row['status'] ?? 'open')) ?></td>
                  <td><?= e(substr((string) $row['created_at'], 0, 16)) ?></td>
                </tr>
              <?php endforeach; ?>
              <?php if (!$recentReportedContent): ?><tr><td colspan="5" class="muted">当前用户还没有被举报内容记录。</td></tr><?php endif; ?>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <section class="glass panel-card surface-section">
      <div class="section-kicker">相关入口</div>
      <div class="quick-links curated-stack">
        <a class="quick-link" href="/admin.php#users"><strong>返回用户管理</strong><span>回到后台用户列表，继续处理账号与权限相关工作。</span></a>
        <a class="quick-link" href="/user.php?id=<?= (int) $profile['id'] ?>"><strong>切回普通主页视图</strong><span>从公开侧重新查看这位成员的资料、内容和对外承接面。</span></a>
        <a class="quick-link" href="/posts.php"><strong>查看全部帖子</strong><span>回到公开内容流，继续顺着帖子和互动看社区状态。</span></a>
      </div>
    </section>
  <?php endif; ?>
</main>
<?php render_footer(); ?>
