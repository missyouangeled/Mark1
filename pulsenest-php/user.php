<?php
require __DIR__ . '/layout.php';
start_session_if_needed();
$currentViewer = refresh_current_user();
$userId = (int) ($_GET['id'] ?? 0);

$stmt = db()->prepare(
    'SELECT u.id, u.username, u.nickname, u.email, u.avatar_path, u.bio, u.created_at,
            COUNT(p.id) AS post_count
     FROM pulsenest_users u
     LEFT JOIN posts p ON p.user_id = u.id AND p.status = "published"
     WHERE u.id = :id
     GROUP BY u.id, u.username, u.nickname, u.email, u.avatar_path, u.bio, u.created_at
     LIMIT 1'
);
$stmt->execute(['id' => $userId]);
$profile = $stmt->fetch();

$recentPosts = [];
$profileStats = [];
$governanceSummary = null;
$governanceRecentRows = [];
$reportSummary = null;
if ($profile) {
    if ($currentViewer && can_access_admin($currentViewer)) {
        $govStmt = db()->prepare(
            'SELECT COUNT(*) AS total_notes,
                    SUM(CASE WHEN status = "open" THEN 1 ELSE 0 END) AS open_notes,
                    SUM(CASE WHEN severity = "high" THEN 1 ELSE 0 END) AS high_risk_notes
             FROM user_governance_notes
             WHERE user_id = :id'
        );
        $govStmt->execute(['id' => $profile['id']]);
        $governanceSummary = $govStmt->fetch() ?: null;
        $govRecentStmt = db()->prepare(
            'SELECT g.note_type, g.severity, g.status, g.reason, g.detail, g.created_at,
                    actor.nickname AS actor_nickname, actor.username AS actor_username
             FROM user_governance_notes g
             INNER JOIN pulsenest_users actor ON actor.id = g.actor_user_id
             WHERE g.user_id = :id
             ORDER BY g.created_at DESC, g.id DESC
             LIMIT 5'
        );
        $govRecentStmt->execute(['id' => $profile['id']]);
        $governanceRecentRows = $govRecentStmt->fetchAll();
        $reportSummaryStmt = db()->prepare(
            'SELECT COUNT(*) AS total_reports,
                    SUM(CASE WHEN r.status = "open" THEN 1 ELSE 0 END) AS open_reports,
                    SUM(CASE WHEN r.status = "resolved" THEN 1 ELSE 0 END) AS resolved_reports
             FROM reports r
             LEFT JOIN posts p ON p.id = r.post_id
             LEFT JOIN comments c ON c.id = r.comment_id
             WHERE (r.target_type = "post" AND p.user_id = :id)
                OR (r.target_type = "comment" AND c.user_id = :id)'
        );
        $reportSummaryStmt->execute(['id' => $profile['id']]);
        $reportSummary = $reportSummaryStmt->fetch() ?: null;
    }
    $statsStmt = db()->prepare(
        'SELECT
            COALESCE(SUM(COALESCE(l.like_count, 0)), 0) AS total_likes,
            COALESCE(SUM(COALESCE(c.comment_count, 0)), 0) AS total_comments,
            COALESCE(SUM(COALESCE(p.view_count, 0)), 0) AS total_views,
            MAX(p.created_at) AS latest_post_at
         FROM posts p
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
         ) l ON l.post_id = p.id
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
         ) c ON c.post_id = p.id
         WHERE p.user_id = :id AND p.status = "published"'
    );
    $statsStmt->execute(['id' => $profile['id']]);
    $profileStats = $statsStmt->fetch() ?: [];
    $recentStmt = db()->prepare(
        'SELECT p.id, p.title, p.content, p.image_path, p.view_count, p.created_at,
                COALESCE(l.like_count, 0) AS like_count,
                COALESCE(c.comment_count, 0) AS comment_count
         FROM posts p
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
         ) l ON l.post_id = p.id
         LEFT JOIN (
            SELECT post_id, COUNT(*) AS comment_count FROM comments GROUP BY post_id
         ) c ON c.post_id = p.id
         WHERE p.user_id = :id AND p.status = "published"
         ORDER BY p.created_at DESC, p.id DESC
         LIMIT 6'
    );
    $recentStmt->execute(['id' => $profile['id']]);
    $recentPosts = $recentStmt->fetchAll();
}

if (!$profile) {
    http_response_code(404);
}

render_header($profile ? ('PulseNest · ' . $profile['nickname']) : 'PulseNest · 用户不存在', $currentViewer, [
    'searchText' => '🔎 搜索作者、主页、最近帖子',
]);
?>
  <main class="shell page-shell nebula-page-shell user-page">
    <?php if ($profile): ?>
      <?php render_breadcrumbs([
        ['label' => '首页', 'href' => '/'],
        ['label' => '发现', 'href' => '/posts.php'],
        ['label' => $profile['nickname'] . ' 的主页'],
      ]); ?>
    <?php endif; ?>
    <?php if (!$profile): ?>
      <section class="glass panel-card empty-inline nebula-empty">没有找到这个用户。<a class="link" href="/posts.php">返回帖子列表</a></section>
    <?php else: ?>
      <section class="glass nebula-hero nebula-hero-split user-hero refined-hero refined-hero-profile">
        <div class="nebula-copy">
          <div class="brand-chip">纳达尔星项目 · 星云初始03 · 作者主页</div>
          <h1><?= e($profile['nickname']) ?> 的社区主页</h1>
          <p class="page-desc nebula-desc"><?= e($profile['bio'] ?: '这里展示这个成员的公开发帖、社区数据与基本资料。') ?></p>
          <div class="hero-editorial-note">把一个创作者在社区里的公开痕迹，整理成一张可持续浏览的名片。</div>
          <div class="hero-stats compact-hero-stats">
            <div class="hero-stat"><div class="label">用户名</div><div class="num small-num">@<?= e($profile['username']) ?></div><div class="note">公开社区身份</div></div>
            <div class="hero-stat"><div class="label">发帖数</div><div class="num small-num"><?= (int) $profile['post_count'] ?></div><div class="note">累计公开内容</div></div>
            <div class="hero-stat"><div class="label">累计获赞</div><div class="num small-num"><?= (int) ($profileStats['total_likes'] ?? 0) ?></div><div class="note">作者公开帖累计点赞</div></div>
            <div class="hero-stat"><div class="label">累计浏览</div><div class="num small-num"><?= (int) ($profileStats['total_views'] ?? 0) ?></div><div class="note">作者公开帖累计浏览</div></div>
            <div class="hero-stat"><div class="label">累计回复</div><div class="num small-num"><?= (int) ($profileStats['total_comments'] ?? 0) ?></div><div class="note">作者公开帖收到的回复数</div></div>
            <div class="hero-stat"><div class="label">加入时间</div><div class="num small-num"><?= e(substr((string) $profile['created_at'], 0, 10)) ?></div><div class="note"><?= e(human_time($profile['created_at'])) ?></div></div>
          </div>
        </div>
        <aside class="profile-chip nebula-profile-chip user-profile-chip ops-side-panel">
          <?= render_avatar($profile, 'user-avatar large') ?>
          <div>
            <strong><?= e($profile['nickname']) ?></strong>
            <span>@<?= e($profile['username']) ?></span>
            <span><?= e($profile['email']) ?></span>
            <span><?= e($profile['bio'] ?: '暂无个性签名') ?></span>
          </div>
        </aside>
      </section>

      <div class="nebula-section-grid user-grid">
        <section class="right-col-stack">
          <div class="glass panel-card surface-section">
            <div class="section-kicker">Recent Posts</div>
            <div class="side-head"><h3>最近公开内容</h3></div>
            <?php if (!$recentPosts): ?>
              <div class="empty-inline nebula-empty">这个用户暂时还没有发过帖子。</div>
            <?php else: ?>
              <div class="list-stack profile-post-stack">
                <?php foreach ($recentPosts as $post): ?>
                  <article class="glass panel-card profile-post-card inner-card">
                    <?php if (!empty($post['image_path'])): ?>
                      <div class="post-cover-wrap"><img class="post-cover-image" src="<?= e(image_variant_public_path($post['image_path'], 'card')) ?>" alt="<?= e($post['title']) ?>" loading="lazy" decoding="async" fetchpriority="low"></div>
                    <?php endif; ?>
                    <h3 class="post-title small"><a href="/post.php?id=<?= (int) $post['id'] ?>"><?= e($post['title']) ?></a></h3>
                    <p class="post-text compact"><?= e(excerpt($post['content'], 140)) ?></p>
                    <div class="list-card-footer">
                      <div class="chips">
                        <span class="chip"><?= (int) $post['like_count'] ?> 赞</span>
                        <span class="chip"><?= (int) $post['comment_count'] ?> 回复</span>
                        <span class="chip"><?= (int) ($post['view_count'] ?? 0) ?> 浏览</span>
                      </div>
                      <a class="link" href="/post.php?id=<?= (int) $post['id'] ?>">阅读全文 →</a>
                    </div>
                  </article>
                <?php endforeach; ?>
              </div>
            <?php endif; ?>
          </div>
        </section>

        <aside class="right-col-stack">
          <section class="glass panel-card surface-section">
            <div class="section-kicker">Profile Data</div>
            <div class="side-head"><h3>作者公开资料</h3></div>
            <div class="detail-list">
              <div class="detail-row"><span>昵称</span><strong><?= e($profile['nickname']) ?></strong></div>
              <div class="detail-row"><span>用户名</span><strong>@<?= e($profile['username']) ?></strong></div>
              <div class="detail-row"><span>发帖总数</span><strong><?= (int) $profile['post_count'] ?></strong></div>
              <div class="detail-row"><span>累计获赞</span><strong><?= (int) ($profileStats['total_likes'] ?? 0) ?></strong></div>
              <div class="detail-row"><span>累计浏览</span><strong><?= (int) ($profileStats['total_views'] ?? 0) ?></strong></div>
              <div class="detail-row"><span>累计回复</span><strong><?= (int) ($profileStats['total_comments'] ?? 0) ?></strong></div>
              <div class="detail-row"><span>最近发帖</span><strong><?= !empty($profileStats['latest_post_at']) ? e(human_time($profileStats['latest_post_at'])) : '暂无公开帖子' ?></strong></div>
              <div class="detail-row"><span>加入时间</span><strong><?= e(substr((string) $profile['created_at'], 0, 16)) ?></strong></div>
            </div>
          </section>

          <?php if ($governanceSummary): ?>
            <section class="glass panel-card surface-section">
              <div class="section-kicker">Governance</div>
              <div class="side-head"><h3>治理与风险视图</h3></div>
              <div class="detail-list">
                <div class="detail-row"><span>治理记录总数</span><strong><?= (int) ($governanceSummary['total_notes'] ?? 0) ?></strong></div>
                <div class="detail-row"><span>开放中记录</span><strong><?= (int) ($governanceSummary['open_notes'] ?? 0) ?></strong></div>
                <div class="detail-row"><span>高风险记录</span><strong><?= (int) ($governanceSummary['high_risk_notes'] ?? 0) ?></strong></div>
                <div class="detail-row"><span>累计被举报</span><strong><?= (int) ($reportSummary['total_reports'] ?? 0) ?></strong></div>
                <div class="detail-row"><span>未结举报</span><strong><?= (int) ($reportSummary['open_reports'] ?? 0) ?></strong></div>
                <div class="detail-row"><span>已处理举报</span><strong><?= (int) ($reportSummary['resolved_reports'] ?? 0) ?></strong></div>
              </div>
              <div class="list-stack" style="margin-top:16px;">
                <?php foreach ($governanceRecentRows as $gov): ?>
                  <div class="list-item">
                    <strong><?= e(governance_note_type_label($gov['note_type'] ?? 'warning')) ?> · <?= e(governance_severity_label($gov['severity'] ?? 'medium')) ?>风险 · <?= e(governance_status_label($gov['status'] ?? 'open')) ?></strong>
                    <span><?= e($gov['reason']) ?> · <?= e($gov['actor_nickname']) ?> @<?= e($gov['actor_username']) ?> · <?= e(substr((string) $gov['created_at'], 0, 16)) ?></span>
                    <?php if (!empty($gov['detail'])): ?><span class="muted"><?= e(excerpt((string) $gov['detail'], 96)) ?></span><?php endif; ?>
                  </div>
                <?php endforeach; ?>
                <?php if (!$governanceRecentRows): ?><div class="empty-inline nebula-empty">当前没有可展示的治理明细。</div><?php endif; ?>
              </div>
            </section>
          <?php endif; ?>

          <section class="glass panel-card surface-section">
            <div class="section-kicker">Quick Jump</div>
            <div class="side-head"><h3>继续浏览</h3></div>
            <div class="quick-links curated-stack">
              <a class="quick-link" href="/posts.php"><strong>全部帖子</strong><span>回到公开内容流，继续浏览社区讨论。</span></a>
              <a class="quick-link" href="/"><strong>返回首页</strong><span>回到社区首页和运营推荐位。</span></a>
              <?php if ($currentViewer && (int) $currentViewer['id'] === (int) $profile['id']): ?>
                <a class="quick-link" href="/account.php"><strong>编辑我的资料</strong><span>维护头像、简介和个人主页信息。</span></a>
              <?php endif; ?>
            </div>
          </section>
        </aside>
      </div>
    <?php endif; ?>
  </main>
<?php render_footer(); ?>
