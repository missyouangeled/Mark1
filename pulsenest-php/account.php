<?php
require __DIR__ . '/layout.php';
$user = ensure_logged_in();
$flash = flash_get();
$profileError = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $nickname = trim($_POST['nickname'] ?? '');
    $bio = trim($_POST['bio'] ?? '');
    $location = trim($_POST['location'] ?? '');
    $websiteUrlInput = trim($_POST['website_url'] ?? '');
    $removeAvatar = isset($_POST['remove_avatar']) && $_POST['remove_avatar'] === '1';

    if ($nickname === '' || mb_strlen($nickname) > 60) {
        $profileError = '昵称不能为空，且请控制在 60 字以内。';
    } elseif (mb_strlen($bio) > 280) {
        $profileError = '个性签名请控制在 280 字以内。';
    } elseif (mb_strlen($location) > 60) {
        $profileError = '所在地请控制在 60 字以内。';
    } else {
        try {
            $websiteUrl = normalize_external_url($websiteUrlInput);
            $avatarPath = $user['avatar_path'] ?? null;
            if ($removeAvatar && $avatarPath) {
                delete_uploaded_asset($avatarPath);
                $avatarPath = null;
            }

            $newAvatarPath = handle_image_upload($_FILES['avatar'] ?? [], AVATAR_UPLOAD_DIR);
            if ($newAvatarPath) {
                if ($avatarPath && $avatarPath !== $newAvatarPath) {
                    delete_uploaded_asset($avatarPath);
                }
                $avatarPath = $newAvatarPath;
            }

            $stmt = db()->prepare('UPDATE pulsenest_users SET nickname = :nickname, bio = :bio, location = :location, website_url = :website_url, avatar_path = :avatar_path WHERE id = :id');
            $stmt->execute([
                'nickname' => $nickname,
                'bio' => $bio !== '' ? $bio : null,
                'location' => $location !== '' ? $location : null,
                'website_url' => $websiteUrl,
                'avatar_path' => $avatarPath,
                'id' => $user['id'],
            ]);
            refresh_current_user();
            flash_set('success', '会员资料已更新。');
            redirect_to('/account.php#profile-studio');
        } catch (RuntimeException $e) {
            $profileError = $e->getMessage();
            $user = refresh_current_user() ?? $user;
        }
    }
}

$user = refresh_current_user() ?? $user;
$stmt = db()->prepare('SELECT COUNT(*) FROM posts WHERE user_id = :id AND status = "published"');
$stmt->execute(['id' => $user['id']]);
$postCount = (int) $stmt->fetchColumn();
$profileSummary = profile_completion_summary($user, [
    'include_post' => true,
    'post_count' => $postCount,
]);
$profileChecklist = array_map(static fn ($item) => !empty($item['done']), $profileSummary['checks']);
$profileCompletion = (int) $profileSummary['percent'];
$profileStage = $profileSummary['tone'];
$missingProfileBits = array_column($profileSummary['missing'], 'label');
$profilePrompt = $profileSummary['missing'] ? reset($profileSummary['missing']) : null;
$accountAgeDays = account_age_days($user);
$showProfileReminder = $accountAgeDays >= 3 && !empty($profileSummary['missing']);
$profileGuidance = profile_guidance_copy($user, $profileSummary);
$isFreshMember = $accountAgeDays <= 3;
$totalPosts = (int) db()->query('SELECT COUNT(*) FROM posts WHERE status = "published"')->fetchColumn();
$memberCount = (int) db()->query('SELECT COUNT(*) FROM pulsenest_users')->fetchColumn();
$creatorStatsStmt = db()->prepare(
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
$creatorStatsStmt->execute(['id' => $user['id']]);
$creatorStats = $creatorStatsStmt->fetch() ?: [];
$creatorPresence = creator_presence_summary($user, [
    'post_count' => $postCount,
    'latest_post_at' => $creatorStats['latest_post_at'] ?? null,
]);
$unreadCount = unread_notification_count((int) $user['id']);
$memberJourney = member_journey_summary($user, [
    'post_count' => $postCount,
    'unread_count' => $unreadCount,
    'profile_summary' => $profileSummary,
]);
$latestPostsStmt = db()->prepare(
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
     LIMIT 5'
);
$latestPostsStmt->execute(['id' => $user['id']]);
$latestPosts = $latestPostsStmt->fetchAll();
$latestJourneyPost = $latestPosts[0] ?? null;
$latestJourneyFeedback = $latestJourneyPost ? post_feedback_summary($latestJourneyPost) : null;
$creatorLoop = creator_loop_summary($user, [
    'post_count' => $postCount,
    'unread_count' => $unreadCount,
    'profile_summary' => $profileSummary,
    'latest_feedback' => $latestJourneyFeedback,
]);
$accountNextAction = match (true) {
    $postCount <= 0 && !empty($profileSummary['missing']) => '先把公开资料补完整，再发出第一篇内容，账号会更自然地从注册完成过渡到真正上线。',
    $postCount <= 0 => '资料层已经够用，下一步最值得做的是发出第一篇公开内容，把主页和作者卡真正点亮。',
    $unreadCount > 0 => '先回提醒中心接住已经发生的互动，再决定要不要继续发新内容，节奏会更稳。',
    $latestJourneyFeedback !== null => '最近一篇内容现在处于“' . $latestJourneyFeedback['label'] . '”阶段，最自然的动作是：' . $latestJourneyFeedback['next'],
    default => '资料和内容层都已经有基础了，接下来按自己的节奏继续更新就够了。',
};

render_header('PulseNest · 会员中心', $user, [
    'searchText' => '🔎 搜索我的帖子、账号动作、社区入口',
]);
?>
  <main class="shell page-shell nebula-page-shell account-page">
    <?php render_breadcrumbs([
      ['label' => '首页', 'href' => '/'],
      ['label' => '会员中心'],
    ]); ?>
    <?php if (isset($_GET['welcome'])): ?>
      <div id="welcome-profile-tip" class="notice success floating-notice">账号已经创建完成。现在可以顺手补上头像、昵称、简介和公开资料，让你的主页更完整。</div>
    <?php endif; ?>
    <?php if ($flash): ?>
      <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
    <?php endif; ?>
    <?php if ($profileError): ?><div class="notice error floating-notice"><?= e($profileError) ?></div><?php endif; ?>
    <?php if ($showProfileReminder): ?>
      <section class="glass panel-card surface-section profile-reminder-banner">
        <div>
          <div class="section-kicker">Profile Reminder</div>
          <h3>你的账号已经用了几天，顺手把资料再补一层会更像正式社区名片。</h3>
          <p class="muted"><?= $profilePrompt ? e($profilePrompt['hint']) : '补齐头像、简介和公开信息后，主页与作者卡会完整很多。'; ?></p>
        </div>
        <a class="pill-btn" href="#profile-studio">继续完善资料</a>
      </section>
    <?php endif; ?>

    <?php if (!empty($profileSummary['missing'])): ?>
      <section class="glass panel-card surface-section profile-guide-strip <?= $isFreshMember ? 'is-new' : 'is-returning' ?>">
        <div class="profile-guide-copy">
          <div class="section-kicker"><?= $isFreshMember ? 'New Member Route' : 'Profile Nudge' ?></div>
          <h3><?= e($profileGuidance['header']) ?></h3>
          <p class="muted"><?= e($profileGuidance['subtle']) ?></p>
        </div>
        <div class="profile-guide-pills">
          <?php foreach (array_slice($missingProfileBits, 0, 3) as $missingLabel): ?>
            <span class="chip"><?= e($missingLabel) ?></span>
          <?php endforeach; ?>
        </div>
      </section>
    <?php endif; ?>

    <section class="glass nebula-hero nebula-hero-split member-hero nebula-member-hero refined-hero refined-hero-profile">
      <div class="nebula-copy">
        <div class="brand-chip">纳达尔星项目 · 星云初始03 · 会员中心</div>
        <h1>欢迎回来，<?= e($user['nickname']) ?></h1>
        <p class="page-desc nebula-desc">会员中心现在不只是资料页，而是更接近成品的个人工作台：资料维护、个人数据、最近内容与权限边界被整理进同一套阅读顺序里，回来之后能更快知道自己接下来该做什么。</p>
        <div class="hero-editorial-note">个人面板该像控制台，而不是一堆松散入口的堆叠。</div>
        <div class="chips" style="gap:6px; margin-top: 4px;">
          <span class="chip">资料完成度 <?= $profileCompletion ?>%</span>
          <span class="chip"><?= e($profileStage) ?></span>
          <?php if (!$profileChecklist['avatar']): ?><span class="chip">待补头像</span><?php endif; ?>
          <?php if (!$profileChecklist['bio']): ?><span class="chip">待补简介</span><?php endif; ?>
          <?php if (!$profileChecklist['location']): ?><span class="chip">待补所在地</span><?php endif; ?>
          <?php if (!$profileChecklist['website']): ?><span class="chip">待补个人链接</span><?php endif; ?>
          <?php if (!$profileChecklist['post']): ?><span class="chip">待发第一篇内容</span><?php endif; ?>
        </div>
        <div class="hero-actions-row">
          <a class="pill-btn solid" href="/create-post.php">写一篇新帖子</a>
          <a class="pill-btn" href="<?= e(profile_url($user)) ?>">查看我的主页</a>
        </div>
      </div>

      <aside class="profile-chip nebula-profile-chip ops-side-panel">
        <?= render_avatar($user, 'user-avatar large') ?>
        <div>
          <strong><?= e($user['nickname']) ?></strong>
          <span>@<?= e($user['username']) ?></span>
          <span><?= e($user['email']) ?></span>
          <span>加入时间：<?= e(substr((string) $user['created_at'], 0, 16)) ?></span>
          <?php if ($missingProfileBits): ?>
            <span class="muted">资料还有可完善的地方：<?= e(implode(' / ', $missingProfileBits)) ?></span>
          <?php endif; ?>
        </div>
      </aside>
    </section>

    <section class="glass panel-card surface-section creator-route-strip">
      <div class="creator-route-copy">
        <div class="section-kicker">Creator Route</div>
        <h3>把“注册完成 → 资料成型 → 发内容 → 接互动”收成一条更顺的个人路径。</h3>
        <p class="muted"><?= e($accountNextAction) ?></p>
      </div>
      <div class="creator-route-meta">
        <div class="route-mini-card"><strong><?= e($memberJourney['label']) ?></strong><span>成员阶段</span></div>
        <div class="route-mini-card"><strong><?= e($creatorPresence['label']) ?></strong><span>创作者状态</span></div>
        <div class="route-mini-card"><strong><?= e($latestJourneyFeedback['label'] ?? ($postCount > 0 ? '继续观察' : '准备首帖')) ?></strong><span><?= $latestJourneyPost ? '最近内容反馈' : '下一步节奏' ?></span></div>
      </div>
    </section>

    <section class="stat-grid page-grid-three nebula-stat-grid">
      <div class="glass stat-card"><strong><?= $postCount ?></strong><span>我的帖子</span></div>
      <div class="glass stat-card"><strong><?= (int) ($creatorStats['total_likes'] ?? 0) ?></strong><span>累计获赞</span></div>
      <div class="glass stat-card"><strong><?= (int) ($creatorStats['total_views'] ?? 0) ?></strong><span>累计浏览</span></div>
      <div class="glass stat-card"><strong><?= (int) ($creatorStats['total_comments'] ?? 0) ?></strong><span>累计回复</span></div>
      <div class="glass stat-card"><strong><?= $memberCount ?></strong><span>社区成员</span></div>
      <div class="glass stat-card"><strong><?= $totalPosts ?></strong><span>全站内容</span></div>
    </section>

    <div class="nebula-section-grid account-grid">
      <div class="right-col-stack">
        <section id="profile-studio" class="glass panel-card surface-section">
          <div class="section-kicker">Profile Studio</div>
          <div class="side-head"><h3>资料与头像</h3></div>
          <form class="form" method="post" enctype="multipart/form-data">
            <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
            <div class="avatar-upload-row avatar-upload-row-enhanced">
              <div class="avatar-preview-card">
                <div id="account-avatar-preview-root" data-fallback="<?= e(avatar_fallback_text($user)) ?>">
                  <?= render_avatar($user, 'user-avatar large account-avatar-preview') ?>
                </div>
                <div class="field-tip avatar-preview-tip">公开页、帖子页和提醒页都会同步使用这张头像。</div>
                <div id="avatar-preview-state" class="avatar-preview-state muted"><?= !empty($user['avatar_path']) ? '当前正在使用这张头像' : '当前为默认字母头像' ?></div>
              </div>
              <div class="field grow-field">
                <label>上传头像</label>
                <input id="avatar-input" class="input file-input" type="file" name="avatar" accept="image/jpeg,image/png,image/gif,image/webp" />
                <div class="field-tip">支持 JPG / PNG / GIF / WEBP，大小 5MB 内。上传新头像后会自动替换旧头像；本地会先显示预览，不需要先保存才能确认观感。</div>
                <div class="field-tip">建议使用居中、清晰、接近方图的头像，这样在作者卡和小尺寸列表里会更稳。</div>
                <?php if (!empty($user['avatar_path'])): ?>
                  <label class="checkbox-inline"><input type="checkbox" name="remove_avatar" value="1">移除当前头像，改用默认字母头像</label>
                <?php endif; ?>
              </div>
            </div>
            <div class="field">
              <label>显示昵称</label>
              <input class="input" name="nickname" value="<?= e($user['nickname']) ?>" maxlength="60" placeholder="别人会看到这个名字" />
              <div class="field-tip">用户名用于登录与公开身份标识，昵称用于前台显示，可随时调整。</div>
            </div>
            <div class="field">
              <label>个人简介</label>
              <textarea class="textarea small-textarea" name="bio" placeholder="写一句让别人认识你的话"><?= e($user['bio'] ?? '') ?></textarea>
            </div>
            <div class="grid-2 profile-meta-grid">
              <div class="field">
                <label>所在地</label>
                <input class="input" name="location" value="<?= e($user['location'] ?? '') ?>" maxlength="60" placeholder="例如：上海 / 成都 / Tokyo" />
                <div class="field-tip">会展示在你的公开主页和作者信息区，适合写城市、地区或线上身份。</div>
              </div>
              <div class="field">
                <label>个人链接</label>
                <input class="input" name="website_url" value="<?= e($user['website_url'] ?? '') ?>" maxlength="255" placeholder="例如：example.com / https://your.site" />
                <div class="field-tip">支持个人网站、作品集、社媒主页；未填写协议时会自动补成 https://。</div>
              </div>
            </div>
            <button class="submit" type="submit">保存资料</button>
          </form>
        </section>

        <section class="glass panel-card surface-section">
          <div class="section-kicker">Profile Completion</div>
          <div class="side-head"><h3>下一步建议</h3></div>
          <div class="profile-progress-card">
            <div class="profile-progress-head">
              <strong>资料完成度 <?= $profileCompletion ?>%</strong>
              <span><?= e($profileStage) ?></span>
            </div>
            <div class="profile-progress-bar" aria-hidden="true"><span style="width: <?= $profileCompletion ?>%"></span></div>
            <div class="profile-progress-meta">
              <span>已完成 <?= (int) $profileSummary['done'] ?> / <?= (int) $profileSummary['total'] ?> 项</span>
              <span><?= $profilePrompt ? e($profilePrompt['hint']) : '当前资料层已经足够完整。'; ?></span>
            </div>
          </div>
          <div class="profile-state-card member-journey-card">
            <div class="profile-state-head">
              <strong>成员阶段：<?= e($memberJourney['label']) ?></strong>
              <span><?= e($memberJourney['cta']) ?></span>
            </div>
            <p><?= e($memberJourney['note']) ?></p>
          </div>
          <div class="profile-state-card loop-state-card">
            <div class="profile-state-head">
              <strong>当前闭环：<?= e($creatorLoop['label']) ?></strong>
              <span><?= e($creatorLoop['next']) ?></span>
            </div>
            <p><?= e($creatorLoop['note']) ?></p>
          </div>
          <div class="profile-state-card">
            <div class="profile-state-head">
              <strong>创作者状态：<?= e($creatorPresence['label']) ?></strong>
              <span><?= e($creatorPresence['meta']) ?></span>
            </div>
            <p><?= e($creatorPresence['note']) ?></p>
          </div>
          <?php if (!empty($profileSummary['missing'])): ?>
            <div class="profile-next-step-list">
              <?php foreach (array_slice($profileSummary['missing'], 0, 3) as $missingItem): ?>
                <div class="profile-next-step-item">
                  <strong><?= e($missingItem['label']) ?></strong>
                  <span><?= e($missingItem['hint']) ?></span>
                </div>
              <?php endforeach; ?>
            </div>
          <?php else: ?>
            <div class="profile-quiet-closure">
              <strong>资料层已经安静收口。</strong>
              <span>现在不用继续折腾资料，后面更自然的动作是写内容、回互动，或者回主页看公开形象是否顺手。</span>
            </div>
          <?php endif; ?>
          <div class="detail-list">
            <div class="detail-row"><span>头像</span><strong><?= $profileChecklist['avatar'] ? '已完成' : '建议补一个头像' ?></strong></div>
            <div class="detail-row"><span>简介</span><strong><?= $profileChecklist['bio'] ? '已完成' : '建议写一句简介' ?></strong></div>
            <div class="detail-row"><span>所在地</span><strong><?= $profileChecklist['location'] ? '已完成' : '建议补一个常驻地或线上身份' ?></strong></div>
            <div class="detail-row"><span>个人链接</span><strong><?= $profileChecklist['website'] ? '已完成' : '建议补一个作品集或主页链接' ?></strong></div>
            <div class="detail-row"><span>公开内容</span><strong><?= $profileChecklist['post'] ? '已开始创作' : '建议写第一篇帖子' ?></strong></div>
          </div>
          <div class="notice subtle-notice member-role-notice"><?= e($memberJourney['accent']) ?></div>
        </section>

        <section class="glass panel-card surface-section">
          <div class="section-kicker">My Recent Posts</div>
          <div class="side-head"><h3>最近发布与当前状态</h3></div>
          <?php if (!$latestPosts): ?>
            <div class="empty-inline nebula-empty">你还没有发帖，先去写第一篇吧。</div>
          <?php else: ?>
            <div class="list-stack">
              <?php foreach ($latestPosts as $post): ?>
                <?php $postFeedback = post_feedback_summary($post); ?>
                <a class="list-item enriched-list-item" href="/post.php?id=<?= (int) $post['id'] ?>">
                  <strong><?= e($post['title']) ?></strong>
                  <span><?= e(human_time($post['created_at'])) ?> · <?= e(post_status_label($post['status'] ?? 'published')) ?> · <?= (int) $post['like_count'] ?> 赞 · <?= (int) $post['comment_count'] ?> 回复 · <?= (int) ($post['view_count'] ?? 0) ?> 浏览</span>
                  <em class="list-item-note"><?= ($post['status'] ?? 'published') === 'published' ? '这篇内容正在承接公开曝光与互动。' : '这篇内容目前还在站内流程里，公开曝光会晚一点。'; ?></em>
                  <div class="micro-feedback-line"><strong><?= e($postFeedback['label']) ?></strong><span><?= e($postFeedback['next']) ?></span></div>
                </a>
              <?php endforeach; ?>
            </div>
          <?php endif; ?>
        </section>
      </div>

      <aside class="right-col-stack">
        <section class="glass panel-card surface-section">
          <div class="section-kicker">Member Data</div>
          <div class="side-head"><h3>当前账号信息</h3></div>
          <div class="detail-list">
            <div class="detail-row"><span>昵称</span><strong><?= e($user['nickname']) ?></strong></div>
            <div class="detail-row"><span>用户名</span><strong>@<?= e($user['username']) ?></strong></div>
            <div class="detail-row"><span>邮箱</span><strong><?= e($user['email']) ?></strong></div>
            <div class="detail-row"><span>头像状态</span><strong><?= !empty($user['avatar_path']) ? '已上传头像' : '默认字母头像' ?></strong></div>
            <div class="detail-row"><span>所在地</span><strong><?= e($user['location'] ?: '还没填写所在地') ?></strong></div>
            <div class="detail-row"><span>个人链接</span><strong><?php if (!empty($user['website_url'])): ?><a class="inline-link" href="<?= e($user['website_url']) ?>" target="_blank" rel="noopener noreferrer"><?= e(profile_link_label($user['website_url'])) ?></a><?php else: ?>还没填写个人链接<?php endif; ?></strong></div>
            <div class="detail-row"><span>角色</span><strong><?= e(role_label(user_role($user))) ?></strong></div>
            <div class="detail-row"><span>签名</span><strong><?= e($user['bio'] ?: '还没写简介') ?></strong></div>
            <div class="detail-row"><span>未读提醒</span><strong><?= $unreadCount ?></strong></div>
            <div class="detail-row"><span>累计获赞</span><strong><?= (int) ($creatorStats['total_likes'] ?? 0) ?></strong></div>
            <div class="detail-row"><span>累计浏览</span><strong><?= (int) ($creatorStats['total_views'] ?? 0) ?></strong></div>
            <div class="detail-row"><span>累计回复</span><strong><?= (int) ($creatorStats['total_comments'] ?? 0) ?></strong></div>
            <div class="detail-row"><span>最近发帖</span><strong><?= !empty($creatorStats['latest_post_at']) ? e(human_time($creatorStats['latest_post_at'])) : '暂无公开帖子' ?></strong></div>
            <div class="detail-row"><span>创作者状态</span><strong><?= e($creatorPresence['label']) ?></strong></div>
          </div>
          <div class="presence-missing-line"><?= e($creatorPresence['note']) ?></div>
          <div class="author-presence-note member-journey-inline">当前阶段：<?= e($memberJourney['label']) ?> · <?= e($memberJourney['cta']) ?></div>
        </section>

        <section class="glass panel-card surface-section">
          <div class="section-kicker">Role Boundary</div>
          <div class="side-head"><h3>当前权限边界</h3></div>
          <div class="detail-list">
            <div class="detail-row"><span>普通用户</span><strong>发帖 / 评论 / 资料维护</strong></div>
            <div class="detail-row"><span>版主</span><strong>额外获得删帖删评与日志查看</strong></div>
            <div class="detail-row"><span>管理员</span><strong>额外获得用户 / 结构管理</strong></div>
          </div>
          <div class="notice subtle-notice member-role-notice">
            <?php if (can_access_admin($user)): ?>
              你当前可见后台入口；<?= is_admin($user) ? '管理员拥有全量后台权限。' : '当前为版主权限，后台里不会开放用户角色与分类 / 版块结构管理。' ?>
            <?php else: ?>
              你当前是普通用户，后台入口会被隐藏。这不是异常，而是正常的权限收口；如需协助处理内容，请联系管理员或版主。
            <?php endif; ?>
          </div>
        </section>

        <section class="glass panel-card surface-section">
          <div class="section-kicker">Quick Actions</div>
          <div class="side-head"><h3>继续操作</h3></div>
          <div class="quick-links curated-stack">
            <a class="quick-link" href="/create-post.php"><strong>写一篇新帖子</strong><span>进入发布页，继续补充你的公开内容。</span></a>
            <a class="quick-link" href="/notifications.php"><strong>查看我的提醒</strong><span>查看点赞、回复和系统通知。</span></a>
            <a class="quick-link" href="/posts.php"><strong>查看全部帖子</strong><span>回到内容流继续浏览社区动态。</span></a>
            <a class="quick-link" href="/forgot-password.php"><strong>发起密码重置</strong><span>在需要时更新当前账号密码。</span></a>
            <?php if (!$profileChecklist['avatar'] || !$profileChecklist['bio'] || !$profileChecklist['location'] || !$profileChecklist['website']): ?>
              <a class="quick-link" href="#profile-studio"><strong>完善个人资料</strong><span>继续补齐<?= e(implode(' / ', array_values(array_filter([
                !$profileChecklist['avatar'] ? '头像' : null,
                !$profileChecklist['bio'] ? '简介' : null,
                !$profileChecklist['location'] ? '所在地' : null,
                !$profileChecklist['website'] ? '个人链接' : null,
              ])))) ?>，让你的主页更完整。</span></a>
            <?php endif; ?>
            <a class="quick-link" href="/"><strong>返回首页内容流</strong><span>回到首页查看推荐内容和运营位。</span></a>
          </div>
        </section>
      </aside>
    </div>
  </main>
  <script>
    (function () {
      const input = document.getElementById('avatar-input');
      const root = document.getElementById('account-avatar-preview-root');
      const remove = document.querySelector('input[name="remove_avatar"]');
      const state = document.getElementById('avatar-preview-state');
      if (!input || !root) {
        return;
      }

      const initialMarkup = root.innerHTML;
      const fallback = root.dataset.fallback || '头像预览';

      function setState(text) {
        if (state) {
          state.textContent = text;
        }
      }

      if (remove) {
        remove.addEventListener('change', function () {
          if (this.checked) {
            root.innerHTML = '<div class="user-avatar large account-avatar-preview avatar-fallback">' + fallback + '</div>';
            setState('已切换为默认字母头像预览，保存后生效');
          } else {
            root.innerHTML = initialMarkup;
            setState('当前正在使用这张头像');
          }
        });
      }

      input.addEventListener('change', function () {
        const file = this.files && this.files[0];
        if (!file || !file.type || !file.type.startsWith('image/')) return;
        if (remove) {
          remove.checked = false;
        }
        const current = root.querySelector('img.account-avatar-preview');
        const url = URL.createObjectURL(file);
        setState('本地预览中：保存后会同步到公开页和作者卡');
        if (current) {
          current.src = url;
          current.onload = function () {
            URL.revokeObjectURL(url);
          };
          return;
        }
        root.innerHTML = '';
        const img = document.createElement('img');
        img.className = 'user-avatar large account-avatar-preview avatar-image';
        img.alt = fallback;
        img.src = url;
        img.onload = function () {
          URL.revokeObjectURL(url);
        };
        root.appendChild(img);
      });
    }());
  </script>
<?php render_footer(); ?>
