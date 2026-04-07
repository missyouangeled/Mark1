<?php
require __DIR__ . '/layout.php';
$user = ensure_staff();
$flash = flash_get();
$canManageUsers = can_manage_users($user);
$canManageStructure = can_manage_forum_structure($user);
$role = user_role($user);

function admin_url(array $overrides = [], string $hash = ''): string {
    $query = [
        'post_id' => (int) ($_GET['post_id'] ?? 0),
        'author_id' => (int) ($_GET['author_id'] ?? 0),
        'post_title_keyword' => trim((string) ($_GET['post_title_keyword'] ?? '')),
        'author_keyword' => trim((string) ($_GET['author_keyword'] ?? '')),
        'content_keyword' => trim((string) ($_GET['content_keyword'] ?? '')),
        'comment_status' => trim((string) ($_GET['comment_status'] ?? '')),
        'post_recommend_group' => trim((string) ($_GET['post_recommend_group'] ?? '')),
        'post_recommend_priority' => trim((string) ($_GET['post_recommend_priority'] ?? '')),
        'post_is_sticky' => trim((string) ($_GET['post_is_sticky'] ?? '')),
        'post_is_featured' => trim((string) ($_GET['post_is_featured'] ?? '')),
        'post_home_slot' => trim((string) ($_GET['post_home_slot'] ?? '')),
        'post_status' => trim((string) ($_GET['post_status'] ?? '')),
        'post_page' => (int) ($_GET['post_page'] ?? 1),
        'comment_page' => (int) ($_GET['comment_page'] ?? 1),
        'report_status' => trim((string) ($_GET['report_status'] ?? '')),
        'report_target_type' => trim((string) ($_GET['report_target_type'] ?? '')),
        'report_reason' => trim((string) ($_GET['report_reason'] ?? '')),
        'report_page' => (int) ($_GET['report_page'] ?? 1),
        'governance_status' => trim((string) ($_GET['governance_status'] ?? '')),
        'governance_high_risk_only' => trim((string) ($_GET['governance_high_risk_only'] ?? '')),
        'log_action' => trim((string) ($_GET['log_action'] ?? '')),
        'log_target_type' => trim((string) ($_GET['log_target_type'] ?? '')),
        'log_actor_id' => (int) ($_GET['log_actor_id'] ?? 0),
        'log_page' => (int) ($_GET['log_page'] ?? 1),
    ];

    foreach ($overrides as $key => $value) {
        $query[$key] = $value;
    }

    foreach ($query as $key => $value) {
        if ($value === null || $value === '' || $value === 0 || $value === '0') {
            unset($query[$key]);
        }
    }

    $url = '/admin.php';
    if ($query) {
        $url .= '?' . http_build_query($query);
    }
    if ($hash !== '') {
        $url .= $hash;
    }
    return $url;
}

function admin_notification_copy(string $type): string {
    return match ($type) {
        'post_like' => '有人点赞帖子',
        'comment_like' => '有人点赞评论',
        'comment_reply' => '有人回复评论',
        'comment_moderated' => '评论审核结果通知作者（区分已通过 / 已隐藏）',
        'post_moderated' => '帖子审核结果通知作者（发布 / 待审 / 隐藏）',
        'report_processed' => '举报回执通知举报人（处理中 / 已处理 / 已驳回，并尽量写明联动处置）',
        default => '有人回复帖子',
    };
}

function site_setting_field_name(string $settingKey): string {
    return 'setting_' . str_replace('.', '__', $settingKey);
}

function admin_pagination(array $baseQuery, string $pageKey, int $page, int $totalPages, string $hash = ''): string {
    $buildUrl = static function (int $targetPage) use ($baseQuery, $pageKey, $hash): string {
        $query = array_merge($baseQuery, [$pageKey => $targetPage]);
        return admin_url($query, $hash);
    };

    return '<div class="admin-pagination">'
        . '<a class="pill-btn ' . ($page <= 1 ? 'is-disabled' : '') . '" ' . ($page <= 1 ? 'aria-disabled="true"' : 'href="' . e($buildUrl($page - 1)) . '"') . '>上一页</a>'
        . '<div class="pagination-status">第 <strong>' . $page . '</strong> 页 / 共 <strong>' . $totalPages . '</strong> 页</div>'
        . '<a class="pill-btn ' . ($page >= $totalPages ? 'is-disabled' : '') . '" ' . ($page >= $totalPages ? 'aria-disabled="true"' : 'href="' . e($buildUrl($page + 1)) . '"') . '>下一页</a>'
        . '</div>';
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    verify_csrf();
    $action = $_POST['action'] ?? '';

    if ($action === 'toggle_user_active') {
        if (!$canManageUsers) {
            http_response_code(403);
            exit('Forbidden');
        }
        $targetUserId = (int) ($_POST['user_id'] ?? 0);
        $targetStatus = (int) ($_POST['target_status'] ?? 0);
        $stmt = db()->prepare('SELECT id, nickname, username, role FROM pulsenest_users WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $targetUserId]);
        $targetUser = $stmt->fetch();

        if (!$targetUser) {
            flash_set('error', '没有找到目标用户。');
        } elseif ($targetUserId === (int) $user['id'] && $targetStatus === 0) {
            flash_set('error', '不能把当前自己停用。');
        } else {
            $stmt = db()->prepare('UPDATE pulsenest_users SET is_active = :is_active WHERE id = :id LIMIT 1');
            $stmt->execute(['is_active' => $targetStatus ? 1 : 0, 'id' => $targetUserId]);
            log_moderation_action((int) $user['id'], $targetStatus ? 'user_enabled' : 'user_disabled', 'user', $targetUserId, ($targetUser['nickname'] ?: $targetUser['username']) . ' · ' . role_label($targetUser['role'] ?? 'member'));
            flash_set('success', $targetStatus ? '用户已启用。' : '用户已停用。');
        }
        redirect_to('/admin.php#users');
    }

    if ($action === 'add_governance_note') {
        if (!$canManageUsers) {
            http_response_code(403);
            exit('Forbidden');
        }
        $targetUserId = (int) ($_POST['user_id'] ?? 0);
        $noteType = trim((string) ($_POST['note_type'] ?? 'warning'));
        $severity = trim((string) ($_POST['severity'] ?? 'medium'));
        $reason = trim((string) ($_POST['reason'] ?? ''));
        $detail = trim((string) ($_POST['detail'] ?? ''));
        if (!in_array($noteType, ['warning', 'watch', 'ban'], true) || !in_array($severity, ['low', 'medium', 'high'], true) || $reason === '') {
            flash_set('error', '治理记录参数不完整。');
            redirect_to('/admin.php#users');
        }
        $stmt = db()->prepare('SELECT id, nickname, username FROM pulsenest_users WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $targetUserId]);
        $targetUser = $stmt->fetch();
        if (!$targetUser) {
            flash_set('error', '没有找到目标用户。');
            redirect_to('/admin.php#users');
        }
        db()->prepare('INSERT INTO user_governance_notes (user_id, actor_user_id, note_type, severity, reason, detail) VALUES (:user_id, :actor_user_id, :note_type, :severity, :reason, :detail)')->execute([
            'user_id' => $targetUserId,
            'actor_user_id' => (int) $user['id'],
            'note_type' => $noteType,
            'severity' => $severity,
            'reason' => mb_substr($reason, 0, 255),
            'detail' => $detail !== '' ? $detail : null,
        ]);
        if ($noteType === 'ban') {
            db()->prepare('UPDATE pulsenest_users SET is_active = 0 WHERE id = :id LIMIT 1')->execute(['id' => $targetUserId]);
        }
        log_moderation_action((int) $user['id'], 'user_governance_note_added', 'user', $targetUserId, ($targetUser['nickname'] ?: $targetUser['username']) . ' · ' . governance_note_type_label($noteType) . ' · 风险等级 ' . governance_severity_label($severity));
        flash_set('success', '用户治理记录已添加。');
        redirect_to('/admin.php#users');
    }

    if ($action === 'update_governance_note_status') {
        if (!$canManageUsers) {
            http_response_code(403);
            exit('Forbidden');
        }
        $noteId = (int) ($_POST['note_id'] ?? 0);
        $targetStatus = trim((string) ($_POST['target_status'] ?? 'resolved'));
        if (!in_array($targetStatus, ['open', 'resolved', 'dismissed'], true)) {
            flash_set('error', '治理记录状态无效。');
            redirect_to('/admin.php#users');
        }
        $stmt = db()->prepare('SELECT id, user_id, note_type, severity, reason, status FROM user_governance_notes WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $noteId]);
        $note = $stmt->fetch();
        if (!$note) {
            flash_set('error', '没有找到目标治理记录。');
            redirect_to('/admin.php#users');
        }
        db()->prepare('UPDATE user_governance_notes SET status = :status WHERE id = :id LIMIT 1')->execute([
            'status' => $targetStatus,
            'id' => $noteId,
        ]);
        if (($note['note_type'] ?? '') === 'ban' && $targetStatus !== 'open') {
            db()->prepare('UPDATE pulsenest_users SET is_active = 1 WHERE id = :id LIMIT 1')->execute(['id' => (int) $note['user_id']]);
        }
        log_moderation_action((int) $user['id'], 'user_governance_note_status_updated', 'user', (int) $note['user_id'], governance_note_type_label($note['note_type'] ?? 'warning') . ' · ' . governance_status_label($note['status'] ?? 'open') . ' → ' . governance_status_label($targetStatus));
        flash_set('success', '治理记录状态已更新。');
        redirect_to('/admin.php#users');
    }

    if ($action === 'set_user_role') {
        if (!$canManageUsers) {
            http_response_code(403);
            exit('Forbidden');
        }
        $targetUserId = (int) ($_POST['user_id'] ?? 0);
        $targetRole = trim((string) ($_POST['role'] ?? 'member'));
        $allowedRoles = ['member', 'moderator', 'admin'];
        if (!in_array($targetRole, $allowedRoles, true)) {
            flash_set('error', '角色值无效。');
            redirect_to('/admin.php#users');
        }

        $stmt = db()->prepare('SELECT id, nickname, username, role FROM pulsenest_users WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $targetUserId]);
        $targetUser = $stmt->fetch();

        if (!$targetUser) {
            flash_set('error', '没有找到目标用户。');
        } elseif ($targetUserId === (int) $user['id'] && $targetRole !== 'admin') {
            flash_set('error', '当前管理员自己的角色不能降级。');
        } else {
            $stmt = db()->prepare('UPDATE pulsenest_users SET role = :role, is_admin = :is_admin WHERE id = :id LIMIT 1');
            $stmt->execute([
                'role' => $targetRole,
                'is_admin' => $targetRole === 'admin' ? 1 : 0,
                'id' => $targetUserId,
            ]);
            log_moderation_action((int) $user['id'], 'user_role_updated', 'user', $targetUserId, ($targetUser['nickname'] ?: $targetUser['username']) . ' → ' . role_label($targetRole));
            flash_set('success', '用户角色已更新为“' . role_label($targetRole) . '”。');
        }
        redirect_to('/admin.php#users');
    }

    if ($action === 'update_site_settings') {
        $settings = [];
        foreach (array_keys(default_site_settings()) as $settingKey) {
            $fieldName = site_setting_field_name($settingKey);
            if (str_ends_with($settingKey, '_enabled')) {
                $settings[$settingKey] = isset($_POST[$fieldName]) ? '1' : '0';
            } else {
                $settings[$settingKey] = trim((string) ($_POST[$fieldName] ?? ''));
            }
        }
        set_site_settings($settings);
        log_moderation_action((int) $user['id'], 'site_settings_updated', 'site_settings', null, '站点运营开关与公告已更新');
        flash_set('success', '站点设置已更新。');
        redirect_to('/admin.php#site-settings');
    }

    if ($action === 'update_home_copy') {
        $settings = [];
        foreach (array_keys(default_home_copy_settings()) as $settingKey) {
            $fieldName = site_setting_field_name($settingKey);
            $settings[$settingKey] = trim((string) ($_POST[$fieldName] ?? ''));
        }
        set_site_settings($settings);
        log_moderation_action((int) $user['id'], 'home_copy_updated', 'site_settings', null, '首页 Hero / Focus 文案已更新');
        flash_set('success', '首页运营卡文案已更新。');
        redirect_to('/admin.php#home-copy');
    }

    if ($action === 'bulk_post_status') {
        $postIds = array_values(array_unique(array_filter(array_map('intval', $_POST['post_ids'] ?? []))));
        $targetStatus = trim((string) ($_POST['target_status'] ?? ''));
        $allowedStatuses = ['published', 'pending', 'hidden', 'draft'];
        if (!$postIds) {
            flash_set('error', '请先勾选要处理的帖子。');
            redirect_to(admin_url([], '#posts'));
        }
        if (!in_array($targetStatus, $allowedStatuses, true)) {
            flash_set('error', '目标帖子状态无效。');
            redirect_to(admin_url([], '#posts'));
        }

        $placeholders = implode(',', array_fill(0, count($postIds), '?'));
        $stmt = db()->prepare(
            'SELECT p.id, p.user_id, p.title, p.status, u.nickname, u.username
             FROM posts p
             INNER JOIN pulsenest_users u ON u.id = p.user_id
             WHERE p.id IN (' . $placeholders . ')'
        );
        $stmt->execute($postIds);
        $rows = $stmt->fetchAll();

        if (!$rows) {
            flash_set('error', '没有找到可处理的帖子。');
            redirect_to(admin_url([], '#posts'));
        }

        $update = db()->prepare('UPDATE posts SET status = ? WHERE id IN (' . $placeholders . ')');
        $update->execute(array_merge([$targetStatus], $postIds));
        foreach ($rows as $row) {
            log_moderation_action((int) $user['id'], 'post_status_updated', 'post', (int) $row['id'], ($row['nickname'] ?: $row['username']) . ' · ' . ($row['title'] ?: ('帖子 #' . (int) $row['id'])) . ' · ' . post_status_label($row['status'] ?? 'published') . ' → ' . post_status_label($targetStatus));
            if (($row['status'] ?? 'published') !== $targetStatus) {
                create_post_moderation_notification($row, (int) $user['id'], $targetStatus);
            }
        }
        flash_set('success', '已批量更新 ' . count($rows) . ' 篇帖子为“' . post_status_label($targetStatus) . '”。');
        redirect_to(admin_url(['post_status' => $targetStatus], '#posts'));
    }

    if ($action === 'update_post_ops') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $stmt = db()->prepare('SELECT p.id, p.user_id, p.title, p.status, p.home_slot, p.recommend_group, p.recommend_priority, u.nickname, u.username FROM posts p INNER JOIN pulsenest_users u ON u.id = p.user_id WHERE p.id = :id LIMIT 1');
        $stmt->execute(['id' => $postId]);
        $post = $stmt->fetch();

        if (!$post) {
            flash_set('error', '没有找到目标帖子。');
            redirect_to('/admin.php#posts');
        }

        $isSticky = isset($_POST['is_sticky']) ? 1 : 0;
        $isFeatured = isset($_POST['is_featured']) ? 1 : 0;
        $recommendLevel = max(0, min(9, (int) ($_POST['recommend_level'] ?? 0)));
        $homeSlot = trim((string) ($_POST['home_slot'] ?? ''));
        $recommendGroup = trim((string) ($_POST['recommend_group'] ?? 'general'));
        $recommendPriority = max(0, min(999, (int) ($_POST['recommend_priority'] ?? 0)));
        $postStatus = trim((string) ($_POST['status'] ?? 'published'));
        $allowedSlots = array_keys(home_slot_definitions());
        $allowedGroups = array_keys(recommend_group_definitions());
        if ($homeSlot !== '' && !in_array($homeSlot, $allowedSlots, true)) {
            $homeSlot = '';
        }
        if (!in_array($recommendGroup, $allowedGroups, true)) {
            $recommendGroup = 'general';
        }
        if (!in_array($postStatus, ['published', 'pending', 'hidden', 'draft'], true)) {
            $postStatus = 'published';
        }

        if ($homeSlot !== '') {
            db()->prepare('UPDATE posts SET home_slot = NULL WHERE home_slot = :home_slot AND id <> :id')->execute([
                'home_slot' => $homeSlot,
                'id' => $postId,
            ]);
        }

        db()->prepare('UPDATE posts SET status = :status, is_sticky = :is_sticky, is_featured = :is_featured, recommend_level = :recommend_level, home_slot = :home_slot, recommend_group = :recommend_group, recommend_priority = :recommend_priority WHERE id = :id LIMIT 1')->execute([
            'status' => $postStatus,
            'is_sticky' => $isSticky,
            'is_featured' => $isFeatured,
            'recommend_level' => $recommendLevel,
            'home_slot' => $homeSlot !== '' ? $homeSlot : null,
            'recommend_group' => $recommendGroup,
            'recommend_priority' => $recommendPriority,
            'id' => $postId,
        ]);

        if (($post['status'] ?? 'published') !== $postStatus) {
            create_post_moderation_notification($post, (int) $user['id'], $postStatus);
        }

        $slotLabel = $homeSlot !== '' ? (home_slot_definitions()[$homeSlot]['label'] ?? $homeSlot) : '未绑定';
        $groupLabel = recommend_group_definitions()[$recommendGroup]['label'] ?? $recommendGroup;
        log_moderation_action((int) $user['id'], 'post_ops_updated', 'post', $postId, '《' . $post['title'] . '》 · 状态:' . post_status_label($postStatus) . ' · 置顶:' . $isSticky . ' · 精华:' . $isFeatured . ' · 推荐位:' . $recommendLevel . ' · 分组:' . $groupLabel . ' · 优先级:' . $recommendPriority . ' · 首页卡:' . $slotLabel);
        flash_set('success', '帖子运营位已更新。');
        redirect_to('/admin.php#posts');
    }

    if ($action === 'delete_post_admin') {
        $postId = (int) ($_POST['post_id'] ?? 0);
        $stmt = db()->prepare('SELECT p.id, p.title, p.image_path, u.nickname, u.username FROM posts p INNER JOIN pulsenest_users u ON u.id = p.user_id WHERE p.id = :id LIMIT 1');
        $stmt->execute(['id' => $postId]);
        $post = $stmt->fetch();
        if ($post) {
            $delete = db()->prepare('DELETE FROM posts WHERE id = :id LIMIT 1');
            $delete->execute(['id' => $postId]);
            delete_uploaded_asset($post['image_path'] ?? null);
            log_moderation_action((int) $user['id'], 'post_deleted', 'post', $postId, '《' . $post['title'] . '》 by ' . ($post['nickname'] ?: $post['username']));
            flash_set('success', '帖子已删除。');
        }
        redirect_to('/admin.php#posts');
    }

    if ($action === 'resolve_report') {
        $reportId = (int) ($_POST['report_id'] ?? 0);
        $targetStatus = trim((string) ($_POST['target_status'] ?? 'resolved'));
        $resolutionNote = trim((string) ($_POST['resolution_note'] ?? ''));
        $contentAction = trim((string) ($_POST['content_action'] ?? 'none'));
        if (!in_array($targetStatus, ['reviewing', 'resolved', 'dismissed'], true)) {
            flash_set('error', '举报状态无效。');
            redirect_to('/admin.php#reports');
        }
        if (!in_array($contentAction, ['none', 'hide_post', 'restore_post', 'hide_comment', 'approve_comment', 'delete_comment'], true)) {
            $contentAction = 'none';
        }
        $stmt = db()->prepare('SELECT id, reporter_user_id, target_type, target_id, post_id, comment_id, reason, status FROM reports WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $reportId]);
        $report = $stmt->fetch();
        if (!$report) {
            flash_set('error', '没有找到目标举报。');
            redirect_to('/admin.php#reports');
        }

        if ($contentAction === 'hide_post') {
            $postOwnerStmt = db()->prepare('SELECT id, user_id FROM posts WHERE id = :id LIMIT 1');
            $postOwnerStmt->execute(['id' => (int) $report['post_id']]);
            $postRow = $postOwnerStmt->fetch();
            db()->prepare('UPDATE posts SET status = "hidden" WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['post_id']]);
            if ($postRow) {
                create_post_moderation_notification($postRow, (int) $user['id'], 'hidden');
            }
            log_moderation_action((int) $user['id'], 'post_hidden_via_report', 'post', (int) $report['post_id'], '举报 #' . $reportId . ' 联动隐藏帖子');
        }
        if ($contentAction === 'restore_post') {
            $postOwnerStmt = db()->prepare('SELECT id, user_id FROM posts WHERE id = :id LIMIT 1');
            $postOwnerStmt->execute(['id' => (int) $report['post_id']]);
            $postRow = $postOwnerStmt->fetch();
            db()->prepare('UPDATE posts SET status = "published" WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['post_id']]);
            if ($postRow) {
                create_post_moderation_notification($postRow, (int) $user['id'], 'published');
            }
            log_moderation_action((int) $user['id'], 'post_restored_via_report', 'post', (int) $report['post_id'], '举报 #' . $reportId . ' 联动恢复帖子');
        }
        if ($contentAction === 'hide_comment' && (int) ($report['comment_id'] ?? 0) > 0) {
            $commentOwnerStmt = db()->prepare('SELECT id, user_id FROM comments WHERE id = :id LIMIT 1');
            $commentOwnerStmt->execute(['id' => (int) $report['comment_id']]);
            $commentRow = $commentOwnerStmt->fetch();
            db()->prepare('UPDATE comments SET status = "hidden" WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['comment_id']]);
            if ($commentRow) {
                create_comment_moderation_notification($commentRow, ['id' => (int) $report['post_id']], (int) $user['id'], 'hidden');
            }
            log_moderation_action((int) $user['id'], 'comment_hidden_via_report', 'comment', (int) $report['comment_id'], '举报 #' . $reportId . ' 联动隐藏评论');
        }
        if ($contentAction === 'approve_comment' && (int) ($report['comment_id'] ?? 0) > 0) {
            $commentOwnerStmt = db()->prepare('SELECT id, user_id FROM comments WHERE id = :id LIMIT 1');
            $commentOwnerStmt->execute(['id' => (int) $report['comment_id']]);
            $commentRow = $commentOwnerStmt->fetch();
            db()->prepare('UPDATE comments SET status = "approved" WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['comment_id']]);
            if ($commentRow) {
                create_comment_moderation_notification($commentRow, ['id' => (int) $report['post_id']], (int) $user['id'], 'approved');
            }
            log_moderation_action((int) $user['id'], 'comment_approved_via_report', 'comment', (int) $report['comment_id'], '举报 #' . $reportId . ' 联动恢复评论');
        }
        if ($contentAction === 'delete_comment' && (int) ($report['comment_id'] ?? 0) > 0) {
            db()->prepare('DELETE FROM comments WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['comment_id']]);
            log_moderation_action((int) $user['id'], 'comment_deleted_via_report', 'comment', (int) $report['comment_id'], '举报 #' . $reportId . ' 联动删除评论');
        }

        db()->prepare('UPDATE reports SET status = :status, resolution_note = :resolution_note, resolved_by_user_id = :resolved_by_user_id, resolved_at = :resolved_at WHERE id = :id LIMIT 1')->execute([
            'status' => $targetStatus,
            'resolution_note' => $resolutionNote !== '' ? mb_substr($resolutionNote, 0, 255) : null,
            'resolved_by_user_id' => (int) $user['id'],
            'resolved_at' => $targetStatus === 'reviewing' ? null : date('Y-m-d H:i:s'),
            'id' => $reportId,
        ]);
        $reportNotificationNote = report_content_action_note($contentAction);
        if ($resolutionNote !== '') {
            $reportNotificationNote = trim(($reportNotificationNote ? $reportNotificationNote . ' ' : '') . '处理备注：' . mb_substr($resolutionNote, 0, 120));
        }
        create_report_resolution_notification((int) ($report['reporter_user_id'] ?? 0), (int) $user['id'], (int) $report['post_id'], !empty($report['comment_id']) ? (int) $report['comment_id'] : null, $targetStatus, $reportNotificationNote);
        log_moderation_action((int) $user['id'], 'report_status_updated', 'report', $reportId, ($report['target_type'] ?? 'content') . ' #' . (int) ($report['target_id'] ?? 0) . ' · ' . report_reason_label($report['reason'] ?? 'other') . ' · ' . report_status_label($report['status'] ?? 'open') . ' → ' . report_status_label($targetStatus) . ($contentAction !== 'none' ? ' · 联动:' . $contentAction : ''));
        flash_set('success', '举报状态已更新为“' . report_status_label($targetStatus) . '”。');
        redirect_to('/admin.php#reports');
    }

    if ($action === 'bulk_report_status') {
        $reportIds = array_values(array_unique(array_filter(array_map('intval', $_POST['report_ids'] ?? []))));
        $targetStatus = trim((string) ($_POST['target_status'] ?? 'resolved'));
        $resolutionNote = trim((string) ($_POST['resolution_note'] ?? ''));
        $contentAction = trim((string) ($_POST['content_action'] ?? 'none'));
        if (!$reportIds) {
            flash_set('error', '请先勾选要处理的举报。');
            redirect_to('/admin.php#reports');
        }
        if (!in_array($targetStatus, ['reviewing', 'resolved', 'dismissed'], true)) {
            flash_set('error', '举报状态无效。');
            redirect_to('/admin.php#reports');
        }
        if (!in_array($contentAction, ['none', 'hide_post', 'restore_post', 'hide_comment', 'approve_comment', 'delete_comment'], true)) {
            $contentAction = 'none';
        }

        $placeholders = implode(',', array_fill(0, count($reportIds), '?'));
        $stmt = db()->prepare('SELECT id, reporter_user_id, target_type, target_id, post_id, comment_id, reason, status FROM reports WHERE id IN (' . $placeholders . ')');
        $stmt->execute($reportIds);
        $reports = $stmt->fetchAll();
        if (!$reports) {
            flash_set('error', '没有找到可处理的举报。');
            redirect_to('/admin.php#reports');
        }

        foreach ($reports as $report) {
            if ($contentAction === 'hide_post' && ($report['target_type'] ?? '') === 'post') {
                $postOwnerStmt = db()->prepare('SELECT id, user_id FROM posts WHERE id = :id LIMIT 1');
                $postOwnerStmt->execute(['id' => (int) $report['post_id']]);
                $postRow = $postOwnerStmt->fetch();
                db()->prepare('UPDATE posts SET status = "hidden" WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['post_id']]);
                if ($postRow) {
                    create_post_moderation_notification($postRow, (int) $user['id'], 'hidden');
                }
            }
            if ($contentAction === 'restore_post' && ($report['target_type'] ?? '') === 'post') {
                $postOwnerStmt = db()->prepare('SELECT id, user_id FROM posts WHERE id = :id LIMIT 1');
                $postOwnerStmt->execute(['id' => (int) $report['post_id']]);
                $postRow = $postOwnerStmt->fetch();
                db()->prepare('UPDATE posts SET status = "published" WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['post_id']]);
                if ($postRow) {
                    create_post_moderation_notification($postRow, (int) $user['id'], 'published');
                }
            }
            if ($contentAction === 'hide_comment' && ($report['target_type'] ?? '') === 'comment' && (int) ($report['comment_id'] ?? 0) > 0) {
                $commentOwnerStmt = db()->prepare('SELECT id, user_id FROM comments WHERE id = :id LIMIT 1');
                $commentOwnerStmt->execute(['id' => (int) $report['comment_id']]);
                $commentRow = $commentOwnerStmt->fetch();
                db()->prepare('UPDATE comments SET status = "hidden" WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['comment_id']]);
                if ($commentRow) {
                    create_comment_moderation_notification($commentRow, ['id' => (int) $report['post_id']], (int) $user['id'], 'hidden');
                }
            }
            if ($contentAction === 'approve_comment' && ($report['target_type'] ?? '') === 'comment' && (int) ($report['comment_id'] ?? 0) > 0) {
                $commentOwnerStmt = db()->prepare('SELECT id, user_id FROM comments WHERE id = :id LIMIT 1');
                $commentOwnerStmt->execute(['id' => (int) $report['comment_id']]);
                $commentRow = $commentOwnerStmt->fetch();
                db()->prepare('UPDATE comments SET status = "approved" WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['comment_id']]);
                if ($commentRow) {
                    create_comment_moderation_notification($commentRow, ['id' => (int) $report['post_id']], (int) $user['id'], 'approved');
                }
            }
            if ($contentAction === 'delete_comment' && ($report['target_type'] ?? '') === 'comment' && (int) ($report['comment_id'] ?? 0) > 0) {
                db()->prepare('DELETE FROM comments WHERE id = :id LIMIT 1')->execute(['id' => (int) $report['comment_id']]);
            }

            db()->prepare('UPDATE reports SET status = :status, resolution_note = :resolution_note, resolved_by_user_id = :resolved_by_user_id, resolved_at = :resolved_at WHERE id = :id LIMIT 1')->execute([
                'status' => $targetStatus,
                'resolution_note' => $resolutionNote !== '' ? mb_substr($resolutionNote, 0, 255) : null,
                'resolved_by_user_id' => (int) $user['id'],
                'resolved_at' => $targetStatus === 'reviewing' ? null : date('Y-m-d H:i:s'),
                'id' => (int) $report['id'],
            ]);
            $reportNotificationNote = report_content_action_note($contentAction);
            if ($resolutionNote !== '') {
                $reportNotificationNote = trim(($reportNotificationNote ? $reportNotificationNote . ' ' : '') . '处理备注：' . mb_substr($resolutionNote, 0, 120));
            }
            create_report_resolution_notification((int) ($report['reporter_user_id'] ?? 0), (int) $user['id'], (int) $report['post_id'], !empty($report['comment_id']) ? (int) $report['comment_id'] : null, $targetStatus, $reportNotificationNote);
            log_moderation_action((int) $user['id'], 'report_status_updated', 'report', (int) $report['id'], ($report['target_type'] ?? 'content') . ' #' . (int) ($report['target_id'] ?? 0) . ' · ' . report_reason_label($report['reason'] ?? 'other') . ' · ' . report_status_label($report['status'] ?? 'open') . ' → ' . report_status_label($targetStatus) . ($contentAction !== 'none' ? ' · 联动:' . $contentAction : ''));
        }

        flash_set('success', '已批量处理 ' . count($reports) . ' 条举报。');
        redirect_to(admin_url(['report_status' => $targetStatus], '#reports'));
    }

    if ($action === 'delete_comment_admin') {
        $commentId = (int) ($_POST['comment_id'] ?? 0);
        $stmt = db()->prepare('SELECT c.id, c.content, c.post_id, c.status, p.title, u.nickname, u.username FROM comments c INNER JOIN posts p ON p.id = c.post_id INNER JOIN pulsenest_users u ON u.id = c.user_id WHERE c.id = :id LIMIT 1');
        $stmt->execute(['id' => $commentId]);
        $comment = $stmt->fetch();
        if ($comment) {
            $delete = db()->prepare('DELETE FROM comments WHERE id = :id LIMIT 1');
            $delete->execute(['id' => $commentId]);
            log_moderation_action((int) $user['id'], 'comment_deleted', 'comment', $commentId, ($comment['nickname'] ?: $comment['username']) . ' · 《' . $comment['title'] . '》 · ' . excerpt($comment['content'], 80));
            flash_set('success', '评论已删除。');
        }
        redirect_to(admin_url([], '#comments'));
    }

    if ($action === 'bulk_comment_status') {
        $commentIds = array_values(array_unique(array_filter(array_map('intval', $_POST['comment_ids'] ?? []))));
        $targetStatus = trim((string) ($_POST['target_status'] ?? ''));
        $allowedStatuses = ['approved', 'hidden', 'pending'];
        if (!$commentIds) {
            flash_set('error', '请先勾选要处理的评论。');
            redirect_to(admin_url([], '#comments'));
        }
        if (!in_array($targetStatus, $allowedStatuses, true)) {
            flash_set('error', '目标状态无效。');
            redirect_to(admin_url([], '#comments'));
        }

        $placeholders = implode(',', array_fill(0, count($commentIds), '?'));
        $stmt = db()->prepare(
            'SELECT c.id, c.post_id, c.user_id, c.content, c.status, p.title, u.nickname, u.username
             FROM comments c
             INNER JOIN posts p ON p.id = c.post_id
             INNER JOIN pulsenest_users u ON u.id = c.user_id
             WHERE c.id IN (' . $placeholders . ')'
        );
        $stmt->execute($commentIds);
        $rows = $stmt->fetchAll();

        if (!$rows) {
            flash_set('error', '没有找到可处理的评论。');
            redirect_to(admin_url([], '#comments'));
        }

        $update = db()->prepare('UPDATE comments SET status = ? WHERE id IN (' . $placeholders . ')');
        $update->execute(array_merge([$targetStatus], $commentIds));
        foreach ($rows as $row) {
            log_moderation_action((int) $user['id'], 'comment_status_updated', 'comment', (int) $row['id'], ($row['nickname'] ?: $row['username']) . ' · ' . comment_status_label($row['status']) . ' → ' . comment_status_label($targetStatus) . ' · 《' . $row['title'] . '》');
            if (($row['status'] ?? '') !== $targetStatus) {
                create_comment_moderation_notification($row, ['id' => (int) $row['post_id']], (int) $user['id'], $targetStatus);
            }
        }
        flash_set('success', '已批量更新 ' . count($rows) . ' 条评论为“' . comment_status_label($targetStatus) . '”。');
        redirect_to(admin_url(['comment_status' => $targetStatus], '#comments'));
    }

    if ($action === 'move_category' && $canManageStructure) {
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $direction = trim((string) ($_POST['direction'] ?? ''));
        $stmt = db()->prepare('SELECT id, name, sort_order FROM forum_categories WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $categoryId]);
        $category = $stmt->fetch();
        if ($category && in_array($direction, ['up', 'down'], true)) {
            $operator = $direction === 'up' ? '<' : '>';
            $order = $direction === 'up' ? 'DESC' : 'ASC';
            $swapStmt = db()->prepare('SELECT id, name, sort_order FROM forum_categories WHERE sort_order ' . $operator . ' :sort_order ORDER BY sort_order ' . $order . ', id ' . $order . ' LIMIT 1');
            $swapStmt->execute(['sort_order' => (int) $category['sort_order']]);
            $swap = $swapStmt->fetch();
            if ($swap) {
                db()->prepare('UPDATE forum_categories SET sort_order = :sort_order WHERE id = :id')->execute(['sort_order' => (int) $swap['sort_order'], 'id' => $categoryId]);
                db()->prepare('UPDATE forum_categories SET sort_order = :sort_order WHERE id = :id')->execute(['sort_order' => (int) $category['sort_order'], 'id' => (int) $swap['id']]);
                log_moderation_action((int) $user['id'], 'category_reordered', 'category', $categoryId, $category['name'] . ' · ' . ($direction === 'up' ? '上移' : '下移'));
                flash_set('success', '分类顺序已调整。');
            }
        }
        redirect_to('/admin.php#categories');
    }

    if ($action === 'create_category' && $canManageStructure) {
        $name = trim((string) ($_POST['name'] ?? ''));
        $slug = trim((string) ($_POST['slug'] ?? ''));
        $description = trim((string) ($_POST['description'] ?? ''));
        $sortOrder = (int) ($_POST['sort_order'] ?? 0);
        if ($name === '' || $slug === '') {
            flash_set('error', '分类名称和 slug 不能为空。');
        } else {
            $stmt = db()->prepare('INSERT INTO forum_categories (name, slug, description, sort_order) VALUES (:name, :slug, :description, :sort_order)');
            $stmt->execute(['name' => $name, 'slug' => $slug, 'description' => $description ?: null, 'sort_order' => $sortOrder]);
            $id = (int) db()->lastInsertId();
            log_moderation_action((int) $user['id'], 'category_created', 'category', $id, $name . ' · ' . $slug);
            flash_set('success', '分类已新增。');
        }
        redirect_to('/admin.php#categories');
    }

    if ($action === 'update_category' && $canManageStructure) {
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $name = trim((string) ($_POST['name'] ?? ''));
        $slug = trim((string) ($_POST['slug'] ?? ''));
        $description = trim((string) ($_POST['description'] ?? ''));
        $sortOrder = (int) ($_POST['sort_order'] ?? 0);
        if ($name === '' || $slug === '') {
            flash_set('error', '分类名称和 slug 不能为空。');
        } else {
            $stmt = db()->prepare('UPDATE forum_categories SET name = :name, slug = :slug, description = :description, sort_order = :sort_order WHERE id = :id LIMIT 1');
            $stmt->execute(['name' => $name, 'slug' => $slug, 'description' => $description ?: null, 'sort_order' => $sortOrder, 'id' => $categoryId]);
            log_moderation_action((int) $user['id'], 'category_updated', 'category', $categoryId, $name . ' · ' . $slug);
            flash_set('success', '分类已更新。');
        }
        redirect_to('/admin.php#categories');
    }

    if ($action === 'delete_category' && $canManageStructure) {
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $targetCategoryId = (int) ($_POST['target_category_id'] ?? 0);
        $stmt = db()->prepare('SELECT id, name, slug FROM forum_categories WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $categoryId]);
        $category = $stmt->fetch();
        if (!$category) {
            flash_set('error', '没有找到要删除的分类。');
            redirect_to('/admin.php#categories');
        }
        $boardCountStmt = db()->prepare('SELECT COUNT(*) FROM forum_boards WHERE category_id = :id');
        $boardCountStmt->execute(['id' => $categoryId]);
        $boardCount = (int) $boardCountStmt->fetchColumn();
        if ($boardCount > 0 && $targetCategoryId <= 0) {
            flash_set('error', '该分类下还有 ' . $boardCount . ' 个版块，请先选择一个目标分类迁移版块。');
            redirect_to('/admin.php#categories');
        }
        if ($boardCount > 0 && $targetCategoryId === $categoryId) {
            flash_set('error', '迁移目标分类不能是当前分类本身。');
            redirect_to('/admin.php#categories');
        }
        $targetCategory = null;
        if ($targetCategoryId > 0) {
            $targetStmt = db()->prepare('SELECT id, name FROM forum_categories WHERE id = :id LIMIT 1');
            $targetStmt->execute(['id' => $targetCategoryId]);
            $targetCategory = $targetStmt->fetch();
            if (!$targetCategory) {
                flash_set('error', '迁移目标分类不存在。');
                redirect_to('/admin.php#categories');
            }
        }
        if ($boardCount > 0) {
            db()->prepare('UPDATE forum_boards SET category_id = :target_category_id WHERE category_id = :category_id')->execute(['target_category_id' => $targetCategoryId, 'category_id' => $categoryId]);
        }
        db()->prepare('DELETE FROM forum_categories WHERE id = :id LIMIT 1')->execute(['id' => $categoryId]);
        $details = $category['name'] . ' · ' . $category['slug'];
        if ($boardCount > 0 && $targetCategory) {
            $details .= ' · 迁移 ' . $boardCount . ' 个版块到 ' . $targetCategory['name'];
        }
        log_moderation_action((int) $user['id'], 'category_deleted', 'category', $categoryId, $details);
        flash_set('success', $boardCount > 0 ? '分类已删除，版块已迁移。' : '分类已删除。');
        redirect_to('/admin.php#categories');
    }

    if ($action === 'move_board' && $canManageStructure) {
        $boardId = (int) ($_POST['board_id'] ?? 0);
        $direction = trim((string) ($_POST['direction'] ?? ''));
        $stmt = db()->prepare('SELECT id, name, category_id, sort_order FROM forum_boards WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $boardId]);
        $board = $stmt->fetch();
        if ($board && in_array($direction, ['up', 'down'], true)) {
            $operator = $direction === 'up' ? '<' : '>';
            $order = $direction === 'up' ? 'DESC' : 'ASC';
            $swapStmt = db()->prepare('SELECT id, name, sort_order FROM forum_boards WHERE category_id = :category_id AND sort_order ' . $operator . ' :sort_order ORDER BY sort_order ' . $order . ', id ' . $order . ' LIMIT 1');
            $swapStmt->execute(['category_id' => (int) $board['category_id'], 'sort_order' => (int) $board['sort_order']]);
            $swap = $swapStmt->fetch();
            if ($swap) {
                db()->prepare('UPDATE forum_boards SET sort_order = :sort_order WHERE id = :id')->execute(['sort_order' => (int) $swap['sort_order'], 'id' => $boardId]);
                db()->prepare('UPDATE forum_boards SET sort_order = :sort_order WHERE id = :id')->execute(['sort_order' => (int) $board['sort_order'], 'id' => (int) $swap['id']]);
                log_moderation_action((int) $user['id'], 'board_reordered', 'board', $boardId, $board['name'] . ' · ' . ($direction === 'up' ? '上移' : '下移'));
                flash_set('success', '版块顺序已调整。');
            }
        }
        redirect_to('/admin.php#boards');
    }

    if ($action === 'create_board' && $canManageStructure) {
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $name = trim((string) ($_POST['name'] ?? ''));
        $slug = trim((string) ($_POST['slug'] ?? ''));
        $description = trim((string) ($_POST['description'] ?? ''));
        $accentColor = trim((string) ($_POST['accent_color'] ?? ''));
        $sortOrder = (int) ($_POST['sort_order'] ?? 0);
        if ($categoryId <= 0 || $name === '' || $slug === '') {
            flash_set('error', '版块所属分类、名称和 slug 不能为空。');
        } else {
            $stmt = db()->prepare('INSERT INTO forum_boards (category_id, name, slug, description, accent_color, sort_order) VALUES (:category_id, :name, :slug, :description, :accent_color, :sort_order)');
            $stmt->execute([
                'category_id' => $categoryId,
                'name' => $name,
                'slug' => $slug,
                'description' => $description ?: null,
                'accent_color' => $accentColor ?: null,
                'sort_order' => $sortOrder,
            ]);
            $id = (int) db()->lastInsertId();
            log_moderation_action((int) $user['id'], 'board_created', 'board', $id, $name . ' · ' . $slug);
            flash_set('success', '版块已新增。');
        }
        redirect_to('/admin.php#boards');
    }

    if ($action === 'update_board' && $canManageStructure) {
        $boardId = (int) ($_POST['board_id'] ?? 0);
        $categoryId = (int) ($_POST['category_id'] ?? 0);
        $name = trim((string) ($_POST['name'] ?? ''));
        $slug = trim((string) ($_POST['slug'] ?? ''));
        $description = trim((string) ($_POST['description'] ?? ''));
        $accentColor = trim((string) ($_POST['accent_color'] ?? ''));
        $sortOrder = (int) ($_POST['sort_order'] ?? 0);
        if ($boardId <= 0 || $categoryId <= 0 || $name === '' || $slug === '') {
            flash_set('error', '版块信息不完整。');
        } else {
            $stmt = db()->prepare('UPDATE forum_boards SET category_id = :category_id, name = :name, slug = :slug, description = :description, accent_color = :accent_color, sort_order = :sort_order WHERE id = :id LIMIT 1');
            $stmt->execute([
                'category_id' => $categoryId,
                'name' => $name,
                'slug' => $slug,
                'description' => $description ?: null,
                'accent_color' => $accentColor ?: null,
                'sort_order' => $sortOrder,
                'id' => $boardId,
            ]);
            log_moderation_action((int) $user['id'], 'board_updated', 'board', $boardId, $name . ' · ' . $slug);
            flash_set('success', '版块已更新。');
        }
        redirect_to('/admin.php#boards');
    }

    if ($action === 'delete_board' && $canManageStructure) {
        $boardId = (int) ($_POST['board_id'] ?? 0);
        $targetBoardId = (int) ($_POST['target_board_id'] ?? 0);
        $stmt = db()->prepare('SELECT id, name, slug FROM forum_boards WHERE id = :id LIMIT 1');
        $stmt->execute(['id' => $boardId]);
        $board = $stmt->fetch();
        if (!$board) {
            flash_set('error', '没有找到要删除的版块。');
            redirect_to('/admin.php#boards');
        }
        $countStmt = db()->prepare('SELECT COUNT(*) FROM posts WHERE board_id = :id');
        $countStmt->execute(['id' => $boardId]);
        $postCount = (int) $countStmt->fetchColumn();
        if ($postCount > 0 && $targetBoardId <= 0) {
            flash_set('error', '该版块下还有 ' . $postCount . ' 篇帖子，请先选择迁移目标版块。');
            redirect_to('/admin.php#boards');
        }
        if ($postCount > 0 && $targetBoardId === $boardId) {
            flash_set('error', '迁移目标版块不能是当前版块本身。');
            redirect_to('/admin.php#boards');
        }
        $targetBoard = null;
        if ($targetBoardId > 0) {
            $targetStmt = db()->prepare('SELECT id, name FROM forum_boards WHERE id = :id LIMIT 1');
            $targetStmt->execute(['id' => $targetBoardId]);
            $targetBoard = $targetStmt->fetch();
            if (!$targetBoard) {
                flash_set('error', '迁移目标版块不存在。');
                redirect_to('/admin.php#boards');
            }
        }
        if ($postCount > 0) {
            db()->prepare('UPDATE posts SET board_id = :target_board_id WHERE board_id = :board_id')->execute(['target_board_id' => $targetBoardId, 'board_id' => $boardId]);
        }
        db()->prepare('DELETE FROM forum_boards WHERE id = :id LIMIT 1')->execute(['id' => $boardId]);
        $details = $board['name'] . ' · ' . $board['slug'];
        if ($postCount > 0 && $targetBoard) {
            $details .= ' · 迁移 ' . $postCount . ' 篇帖子到 ' . $targetBoard['name'];
        }
        log_moderation_action((int) $user['id'], 'board_deleted', 'board', $boardId, $details);
        flash_set('success', $postCount > 0 ? '版块已删除，帖子已迁移。' : '版块已删除。');
        redirect_to('/admin.php#boards');
    }
}

$postFilterId = (int) ($_GET['post_id'] ?? 0);
$authorFilterId = (int) ($_GET['author_id'] ?? 0);
$postTitleKeyword = trim((string) ($_GET['post_title_keyword'] ?? ''));
$authorKeyword = trim((string) ($_GET['author_keyword'] ?? ''));
$contentKeyword = trim((string) ($_GET['content_keyword'] ?? ''));
$commentStatusFilter = trim((string) ($_GET['comment_status'] ?? ''));
$postRecommendGroupFilter = trim((string) ($_GET['post_recommend_group'] ?? ''));
$postRecommendPriorityFilterRaw = trim((string) ($_GET['post_recommend_priority'] ?? ''));
$postStickyFilter = trim((string) ($_GET['post_is_sticky'] ?? ''));
$postFeaturedFilter = trim((string) ($_GET['post_is_featured'] ?? ''));
$postHomeSlotFilter = trim((string) ($_GET['post_home_slot'] ?? ''));
$postStatusFilter = trim((string) ($_GET['post_status'] ?? ''));
$postPage = max(1, (int) ($_GET['post_page'] ?? 1));
$commentPage = max(1, (int) ($_GET['comment_page'] ?? 1));
$postPageSize = 12;
$commentPageSize = 40;

$commentWhere = [];
$commentParams = [];
if ($postFilterId > 0) {
    $commentWhere[] = 'c.post_id = :post_id';
    $commentParams['post_id'] = $postFilterId;
}
if ($authorFilterId > 0) {
    $commentWhere[] = 'c.user_id = :author_id';
    $commentParams['author_id'] = $authorFilterId;
}
if ($postTitleKeyword !== '') {
    $commentWhere[] = 'p.title LIKE :post_title_keyword';
    $commentParams['post_title_keyword'] = '%' . $postTitleKeyword . '%';
}
if ($authorKeyword !== '') {
    $commentWhere[] = '(u.username LIKE :author_keyword OR u.nickname LIKE :author_keyword)';
    $commentParams['author_keyword'] = '%' . $authorKeyword . '%';
}
if ($contentKeyword !== '') {
    $commentWhere[] = 'c.content LIKE :content_keyword';
    $commentParams['content_keyword'] = '%' . $contentKeyword . '%';
}
if ($commentStatusFilter !== '' && in_array($commentStatusFilter, ['approved', 'hidden', 'pending'], true)) {
    $commentWhere[] = 'c.status = :comment_status';
    $commentParams['comment_status'] = $commentStatusFilter;
}
$commentWhereSql = $commentWhere ? ' WHERE ' . implode(' AND ', $commentWhere) : '';
$commentCountStmt = db()->prepare(
    'SELECT COUNT(*)
     FROM comments c
     INNER JOIN posts p ON p.id = c.post_id
     INNER JOIN pulsenest_users u ON u.id = c.user_id
     INNER JOIN pulsenest_users owner ON owner.id = p.user_id'
    . $commentWhereSql
);
$commentCountStmt->execute($commentParams);
$commentTotal = (int) $commentCountStmt->fetchColumn();
$commentTotalPages = max(1, (int) ceil($commentTotal / $commentPageSize));
$commentPage = min($commentPage, $commentTotalPages);
$commentOffset = ($commentPage - 1) * $commentPageSize;
$commentSql =
    'SELECT c.id, c.post_id, c.user_id, c.content, c.status, c.created_at,
            p.title AS post_title,
            u.nickname, u.username,
            owner.nickname AS post_owner_nickname, owner.username AS post_owner_username
     FROM comments c
     INNER JOIN posts p ON p.id = c.post_id
     INNER JOIN pulsenest_users u ON u.id = c.user_id
     INNER JOIN pulsenest_users owner ON owner.id = p.user_id'
    . $commentWhereSql
    . ' ORDER BY c.created_at DESC, c.id DESC LIMIT :limit OFFSET :offset';
$commentStmt = db()->prepare($commentSql);
foreach ($commentParams as $key => $value) {
    $commentStmt->bindValue(':' . $key, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
}
$commentStmt->bindValue(':limit', $commentPageSize, PDO::PARAM_INT);
$commentStmt->bindValue(':offset', $commentOffset, PDO::PARAM_INT);
$commentStmt->execute();
$commentRows = $commentStmt->fetchAll();
$commentCount = count($commentRows);
$commentStatusStats = db()->query('SELECT status, COUNT(*) AS total_count FROM comments GROUP BY status ORDER BY total_count DESC, status ASC')->fetchAll();
$dashboardStats = [
    'posts_today' => (int) db()->query('SELECT COUNT(*) FROM posts WHERE created_at >= NOW() - INTERVAL 1 DAY')->fetchColumn(),
    'comments_today' => (int) db()->query('SELECT COUNT(*) FROM comments WHERE created_at >= NOW() - INTERVAL 1 DAY')->fetchColumn(),
    'reports_today' => (int) db()->query('SELECT COUNT(*) FROM reports WHERE created_at >= NOW() - INTERVAL 1 DAY')->fetchColumn(),
    'notifications_today' => (int) db()->query('SELECT COUNT(*) FROM notifications WHERE created_at >= NOW() - INTERVAL 1 DAY')->fetchColumn(),
    'pending_posts' => (int) db()->query('SELECT COUNT(*) FROM posts WHERE status = "pending"')->fetchColumn(),
    'pending_comments' => (int) db()->query('SELECT COUNT(*) FROM comments WHERE status = "pending"')->fetchColumn(),
    'open_reports' => (int) db()->query('SELECT COUNT(*) FROM reports WHERE status = "open"')->fetchColumn(),
    'reviewing_reports' => (int) db()->query('SELECT COUNT(*) FROM reports WHERE status = "reviewing"')->fetchColumn(),
    'reports_resolved_today' => (int) db()->query('SELECT COUNT(*) FROM reports WHERE status = "resolved" AND resolved_at IS NOT NULL AND resolved_at >= NOW() - INTERVAL 1 DAY')->fetchColumn(),
    'reports_dismissed_today' => (int) db()->query('SELECT COUNT(*) FROM reports WHERE status = "dismissed" AND resolved_at IS NOT NULL AND resolved_at >= NOW() - INTERVAL 1 DAY')->fetchColumn(),
];
$operationsFocus = operations_focus_summary($dashboardStats);
$activeBoards = db()->query(
    'SELECT fb.name AS board_name, fc.name AS category_name, COUNT(p.id) AS post_count
     FROM posts p
     INNER JOIN forum_boards fb ON fb.id = p.board_id
     INNER JOIN forum_categories fc ON fc.id = fb.category_id
     WHERE p.created_at >= NOW() - INTERVAL 7 DAY
     GROUP BY fb.id, fb.name, fc.name
     ORDER BY post_count DESC, fb.name ASC
     LIMIT 5'
)->fetchAll();
$activeAuthors = db()->query(
    'SELECT u.id, u.nickname, u.username,
            COUNT(p.id) AS post_count,
            COALESCE(SUM(COALESCE(p.view_count, 0)), 0) AS total_views
     FROM posts p
     INNER JOIN pulsenest_users u ON u.id = p.user_id
     WHERE p.created_at >= NOW() - INTERVAL 7 DAY
     GROUP BY u.id, u.nickname, u.username
     ORDER BY post_count DESC, total_views DESC, u.nickname ASC
     LIMIT 5'
)->fetchAll();
$reportReasonStats = db()->query(
    'SELECT reason, COUNT(*) AS total_count
     FROM reports
     GROUP BY reason
     ORDER BY total_count DESC, reason ASC'
)->fetchAll();
$governanceStatusFilter = trim((string) ($_GET['governance_status'] ?? ''));
$governanceHighRiskOnly = trim((string) ($_GET['governance_high_risk_only'] ?? '')) === '1';
$governanceWhere = [];
if ($governanceStatusFilter !== '' && in_array($governanceStatusFilter, ['open', 'resolved', 'dismissed'], true)) {
    $governanceWhere[] = 'g.status = ' . db()->quote($governanceStatusFilter);
}
if ($governanceHighRiskOnly) {
    $governanceWhere[] = 'g.severity = "high"';
}
$governanceWhereSql = $governanceWhere ? ' WHERE ' . implode(' AND ', $governanceWhere) : '';
$governanceRows = db()->query(
    'SELECT g.id, g.note_type, g.severity, g.status, g.reason, g.detail, g.created_at,
            u.id AS user_id, u.nickname, u.username,
            actor.nickname AS actor_nickname, actor.username AS actor_username
     FROM user_governance_notes g
     INNER JOIN pulsenest_users u ON u.id = g.user_id
     INNER JOIN pulsenest_users actor ON actor.id = g.actor_user_id'
     . $governanceWhereSql .
    ' ORDER BY FIELD(g.status, "open", "resolved", "dismissed"), FIELD(g.severity, "high", "medium", "low"), g.created_at DESC, g.id DESC
      LIMIT 20'
)->fetchAll();
$highRiskUsers = db()->query(
    'SELECT u.id, u.nickname, u.username, u.is_active,
            COUNT(g.id) AS note_count,
            SUM(CASE WHEN g.status = "open" THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE WHEN g.severity = "high" THEN 1 ELSE 0 END) AS high_count,
            COALESCE(r.report_count, 0) AS report_count
     FROM pulsenest_users u
     INNER JOIN user_governance_notes g ON g.user_id = u.id
     LEFT JOIN (
        SELECT owner_user_id AS user_id, COUNT(*) AS report_count
        FROM (
            SELECT p.user_id AS owner_user_id
            FROM reports r
            INNER JOIN posts p ON p.id = r.post_id
            WHERE r.target_type = "post"
            UNION ALL
            SELECT c.user_id AS owner_user_id
            FROM reports r
            INNER JOIN comments c ON c.id = r.comment_id
            WHERE r.target_type = "comment"
        ) rr
        GROUP BY owner_user_id
     ) r ON r.user_id = u.id
     GROUP BY u.id, u.nickname, u.username, u.is_active, r.report_count
     HAVING high_count > 0 OR open_count > 0
     ORDER BY high_count DESC, open_count DESC, note_count DESC, u.nickname ASC
     LIMIT 10'
)->fetchAll();
$weeklyTrend = db()->query(
    'SELECT day_label,
            SUM(post_count) AS post_count,
            SUM(comment_count) AS comment_count,
            SUM(report_count) AS report_count
     FROM (
        SELECT DATE_FORMAT(created_at, "%m-%d") AS day_label, COUNT(*) AS post_count, 0 AS comment_count, 0 AS report_count
        FROM posts
        WHERE created_at >= NOW() - INTERVAL 7 DAY
        GROUP BY DATE(created_at)
        UNION ALL
        SELECT DATE_FORMAT(created_at, "%m-%d") AS day_label, 0 AS post_count, COUNT(*) AS comment_count, 0 AS report_count
        FROM comments
        WHERE created_at >= NOW() - INTERVAL 7 DAY
        GROUP BY DATE(created_at)
        UNION ALL
        SELECT DATE_FORMAT(created_at, "%m-%d") AS day_label, 0 AS post_count, 0 AS comment_count, COUNT(*) AS report_count
        FROM reports
        WHERE created_at >= NOW() - INTERVAL 7 DAY
        GROUP BY DATE(created_at)
     ) t
     GROUP BY day_label
     ORDER BY day_label ASC'
)->fetchAll();

$userRows = db()->query(
    'SELECT u.id, u.username, u.nickname, u.email, u.role, u.is_admin, u.is_active, u.created_at,
            COALESCE(p.post_count, 0) AS post_count,
            COALESCE(c.comment_count, 0) AS comment_count,
            COALESCE(g.note_count, 0) AS governance_note_count,
            COALESCE(g.open_note_count, 0) AS governance_open_count,
            COALESCE(g.high_risk_count, 0) AS governance_high_risk_count
     FROM pulsenest_users u
     LEFT JOIN (
        SELECT user_id, COUNT(*) AS post_count FROM posts GROUP BY user_id
     ) p ON p.user_id = u.id
     LEFT JOIN (
        SELECT user_id, COUNT(*) AS comment_count FROM comments GROUP BY user_id
     ) c ON c.user_id = u.id
     LEFT JOIN (
        SELECT user_id,
               COUNT(*) AS note_count,
               SUM(CASE WHEN status = "open" THEN 1 ELSE 0 END) AS open_note_count,
               SUM(CASE WHEN severity = "high" THEN 1 ELSE 0 END) AS high_risk_count
        FROM user_governance_notes
        GROUP BY user_id
     ) g ON g.user_id = u.id
     ORDER BY g.high_risk_count DESC, g.open_note_count DESC, FIELD(u.role, "admin", "moderator", "member"), u.created_at DESC, u.id DESC'
)->fetchAll();

$recommendGroups = recommend_group_definitions();
$homeSlotDefinitions = home_slot_definitions();
$postWhere = [];
$postParams = [];
if ($postRecommendGroupFilter !== '' && isset($recommendGroups[$postRecommendGroupFilter])) {
    $postWhere[] = 'p.recommend_group = :post_recommend_group';
    $postParams['post_recommend_group'] = $postRecommendGroupFilter;
}
if ($postRecommendPriorityFilterRaw !== '' && is_numeric($postRecommendPriorityFilterRaw)) {
    $postWhere[] = 'p.recommend_priority = :post_recommend_priority';
    $postParams['post_recommend_priority'] = (int) $postRecommendPriorityFilterRaw;
}
if (in_array($postStickyFilter, ['1', '0'], true)) {
    $postWhere[] = 'p.is_sticky = :post_is_sticky';
    $postParams['post_is_sticky'] = (int) $postStickyFilter;
}
if (in_array($postFeaturedFilter, ['1', '0'], true)) {
    $postWhere[] = 'p.is_featured = :post_is_featured';
    $postParams['post_is_featured'] = (int) $postFeaturedFilter;
}
if ($postHomeSlotFilter === '__bound__') {
    $postWhere[] = 'p.home_slot IS NOT NULL AND p.home_slot <> ""';
} elseif ($postHomeSlotFilter === '__unbound__') {
    $postWhere[] = '(p.home_slot IS NULL OR p.home_slot = "")';
} elseif ($postHomeSlotFilter !== '' && isset($homeSlotDefinitions[$postHomeSlotFilter])) {
    $postWhere[] = 'p.home_slot = :post_home_slot';
    $postParams['post_home_slot'] = $postHomeSlotFilter;
}
if ($postStatusFilter !== '' && in_array($postStatusFilter, ['published', 'pending', 'hidden', 'draft'], true)) {
    $postWhere[] = 'p.status = :post_status';
    $postParams['post_status'] = $postStatusFilter;
}
$postWhereSql = $postWhere ? ' WHERE ' . implode(' AND ', $postWhere) : '';
$postCountStmt = db()->prepare('SELECT COUNT(*) FROM posts p' . $postWhereSql);
foreach ($postParams as $key => $value) {
    $postCountStmt->bindValue(':' . $key, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
}
$postCountStmt->execute();
$postCountTotal = (int) $postCountStmt->fetchColumn();
$postTotalPages = max(1, (int) ceil($postCountTotal / $postPageSize));
$postPage = min($postPage, $postTotalPages);
$postOffset = ($postPage - 1) * $postPageSize;
$postStmt = db()->prepare(
    'SELECT p.id, p.title, p.status, p.view_count, p.created_at, p.is_sticky, p.is_featured, p.recommend_level, p.home_slot, p.recommend_group, p.recommend_priority,
            u.nickname, u.username,
            fb.name AS board_name,
            fc.name AS category_name,
            COALESCE(c.comment_count, 0) AS comment_count,
            COALESCE(l.like_count, 0) AS like_count
     FROM posts p
     INNER JOIN pulsenest_users u ON u.id = p.user_id
     LEFT JOIN forum_boards fb ON fb.id = p.board_id
     LEFT JOIN forum_categories fc ON fc.id = fb.category_id
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS comment_count FROM comments WHERE status = "approved" GROUP BY post_id
     ) c ON c.post_id = p.id
     LEFT JOIN (
        SELECT post_id, COUNT(*) AS like_count FROM post_likes GROUP BY post_id
     ) l ON l.post_id = p.id'
     . $postWhereSql .
    ' ORDER BY p.is_sticky DESC, p.recommend_priority DESC, p.recommend_level DESC, p.is_featured DESC, p.created_at DESC, p.id DESC
     LIMIT :limit OFFSET :offset'
);
foreach ($postParams as $key => $value) {
    $postStmt->bindValue(':' . $key, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
}
$postStmt->bindValue(':limit', $postPageSize, PDO::PARAM_INT);
$postStmt->bindValue(':offset', $postOffset, PDO::PARAM_INT);
$postStmt->execute();
$postRows = $postStmt->fetchAll();

$postStatusStats = db()->query('SELECT status, COUNT(*) AS total_count FROM posts GROUP BY status ORDER BY total_count DESC, status ASC')->fetchAll();
$pendingPostCount = 0;
foreach ($postStatusStats as $stat) {
    if (($stat['status'] ?? '') === 'pending') {
        $pendingPostCount = (int) $stat['total_count'];
        break;
    }
}

$categoryRows = db()->query(
    'SELECT c.id, c.name, c.slug, c.description, c.sort_order,
            COUNT(b.id) AS board_count
     FROM forum_categories c
     LEFT JOIN forum_boards b ON b.category_id = c.id
     GROUP BY c.id
     ORDER BY c.sort_order ASC, c.id ASC'
)->fetchAll();

$boardRows = db()->query(
    'SELECT b.id, b.category_id, b.name, b.slug, b.description, b.sort_order, b.accent_color,
            c.name AS category_name,
            COALESCE(p.post_count, 0) AS post_count
     FROM forum_boards b
     INNER JOIN forum_categories c ON c.id = b.category_id
     LEFT JOIN (
        SELECT board_id, COUNT(*) AS post_count FROM posts WHERE status = "published" GROUP BY board_id
     ) p ON p.board_id = b.id
     ORDER BY c.sort_order ASC, c.id ASC, b.sort_order ASC, b.id ASC'
)->fetchAll();

$siteConfig = site_config();
$homeCopy = home_copy_config();
$boundSlotRows = db()->query('SELECT id, title, home_slot FROM posts WHERE home_slot IS NOT NULL AND home_slot <> ""')->fetchAll();
$boundSlots = [];
foreach ($boundSlotRows as $row) {
    $boundSlots[$row['home_slot']] = $row;
}

$reportStatusFilter = trim((string) ($_GET['report_status'] ?? ''));
$reportTargetTypeFilter = trim((string) ($_GET['report_target_type'] ?? ''));
$reportReasonFilter = trim((string) ($_GET['report_reason'] ?? ''));
$reportPage = max(1, (int) ($_GET['report_page'] ?? 1));
$reportPageSize = 12;
$reportWhere = [];
$reportParams = [];
if ($reportStatusFilter !== '' && in_array($reportStatusFilter, ['open', 'reviewing', 'resolved', 'dismissed'], true)) {
    $reportWhere[] = 'r.status = :report_status';
    $reportParams['report_status'] = $reportStatusFilter;
}
if ($reportTargetTypeFilter !== '' && in_array($reportTargetTypeFilter, ['post', 'comment'], true)) {
    $reportWhere[] = 'r.target_type = :report_target_type';
    $reportParams['report_target_type'] = $reportTargetTypeFilter;
}
if ($reportReasonFilter !== '' && isset(report_reason_options()[$reportReasonFilter])) {
    $reportWhere[] = 'r.reason = :report_reason';
    $reportParams['report_reason'] = $reportReasonFilter;
}
$reportWhereSql = $reportWhere ? ' WHERE ' . implode(' AND ', $reportWhere) : '';
$reportCountStmt = db()->prepare('SELECT COUNT(*) FROM reports r' . $reportWhereSql);
foreach ($reportParams as $key => $value) {
    $reportCountStmt->bindValue(':' . $key, $value, PDO::PARAM_STR);
}
$reportCountStmt->execute();
$reportTotal = (int) $reportCountStmt->fetchColumn();
$reportTotalPages = max(1, (int) ceil($reportTotal / $reportPageSize));
$reportPage = min($reportPage, $reportTotalPages);
$reportOffset = ($reportPage - 1) * $reportPageSize;
$reportStmt = db()->prepare(
    'SELECT r.id, r.target_type, r.target_id, r.post_id, r.comment_id, r.reason, r.detail, r.status, r.resolution_note, r.created_at, r.resolved_at,
            reporter.nickname AS reporter_nickname, reporter.username AS reporter_username,
            resolver.nickname AS resolver_nickname, resolver.username AS resolver_username,
            p.title AS post_title,
            c.content AS comment_content
     FROM reports r
     INNER JOIN pulsenest_users reporter ON reporter.id = r.reporter_user_id
     LEFT JOIN pulsenest_users resolver ON resolver.id = r.resolved_by_user_id
     INNER JOIN posts p ON p.id = r.post_id
     LEFT JOIN comments c ON c.id = r.comment_id'
     . $reportWhereSql .
    ' ORDER BY FIELD(r.status, "open", "reviewing", "resolved", "dismissed"), r.created_at DESC, r.id DESC
      LIMIT :limit OFFSET :offset'
);
foreach ($reportParams as $key => $value) {
    $reportStmt->bindValue(':' . $key, $value, PDO::PARAM_STR);
}
$reportStmt->bindValue(':limit', $reportPageSize, PDO::PARAM_INT);
$reportStmt->bindValue(':offset', $reportOffset, PDO::PARAM_INT);
$reportStmt->execute();
$reportRows = $reportStmt->fetchAll();
$openReportCount = (int) db()->query('SELECT COUNT(*) FROM reports WHERE status = "open"')->fetchColumn();

$notificationTotals = db()->query('SELECT COUNT(*) AS total_notifications, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread_notifications FROM notifications')->fetch();
$notificationTypeRows = db()->query('SELECT type, COUNT(*) AS total_count, SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) AS unread_count FROM notifications GROUP BY type ORDER BY total_count DESC, type ASC')->fetchAll();
$notificationTodayCount = (int) db()->query('SELECT COUNT(*) FROM notifications WHERE created_at >= NOW() - INTERVAL 1 DAY')->fetchColumn();
$notificationSevenDayCount = (int) db()->query('SELECT COUNT(*) FROM notifications WHERE created_at >= NOW() - INTERVAL 7 DAY')->fetchColumn();

$logActionFilter = trim((string) ($_GET['log_action'] ?? ''));
$logTargetTypeFilter = trim((string) ($_GET['log_target_type'] ?? ''));
$logActorIdFilter = (int) ($_GET['log_actor_id'] ?? 0);
$logPage = max(1, (int) ($_GET['log_page'] ?? 1));
$logPageSize = 20;
$logWhere = [];
$logParams = [];
if ($logActionFilter !== '') {
    $logWhere[] = 'l.action_type = :log_action';
    $logParams['log_action'] = $logActionFilter;
}
if ($logTargetTypeFilter !== '') {
    $logWhere[] = 'l.target_type = :log_target_type';
    $logParams['log_target_type'] = $logTargetTypeFilter;
}
if ($logActorIdFilter > 0) {
    $logWhere[] = 'l.actor_user_id = :log_actor_id';
    $logParams['log_actor_id'] = $logActorIdFilter;
}
$logWhereSql = $logWhere ? ' WHERE ' . implode(' AND ', $logWhere) : '';
$countStmt = db()->prepare('SELECT COUNT(*) FROM moderation_logs l' . $logWhereSql);
$countStmt->execute($logParams);
$logTotal = (int) $countStmt->fetchColumn();
$logTotalPages = max(1, (int) ceil($logTotal / $logPageSize));
$logPage = min($logPage, $logTotalPages);
$logOffset = ($logPage - 1) * $logPageSize;
$logStmt = db()->prepare(
    'SELECT l.id, l.action_type, l.target_type, l.target_id, l.details, l.created_at,
            u.nickname, u.username, u.id AS actor_id
     FROM moderation_logs l
     INNER JOIN pulsenest_users u ON u.id = l.actor_user_id'
    . $logWhereSql .
    ' ORDER BY l.created_at DESC, l.id DESC LIMIT :limit OFFSET :offset'
);
foreach ($logParams as $key => $value) {
    $logStmt->bindValue(':' . $key, $value, is_int($value) ? PDO::PARAM_INT : PDO::PARAM_STR);
}
$logStmt->bindValue(':limit', $logPageSize, PDO::PARAM_INT);
$logStmt->bindValue(':offset', $logOffset, PDO::PARAM_INT);
$logStmt->execute();
$logRows = $logStmt->fetchAll();

$logActionOptions = db()->query('SELECT DISTINCT action_type FROM moderation_logs ORDER BY action_type ASC')->fetchAll(PDO::FETCH_COLUMN);
$logTargetTypeOptions = db()->query('SELECT DISTINCT target_type FROM moderation_logs ORDER BY target_type ASC')->fetchAll(PDO::FETCH_COLUMN);
$logActorOptions = db()->query(
    'SELECT DISTINCT u.id, u.nickname, u.username
     FROM moderation_logs l
     INNER JOIN pulsenest_users u ON u.id = l.actor_user_id
     ORDER BY u.nickname ASC, u.username ASC'
)->fetchAll();

$availableCategoryTargets = $categoryRows;
$availableBoardTargets = $boardRows;
$staffCount = 0;
foreach ($userRows as $row) {
    if (can_access_admin($row)) {
        $staffCount++;
    }
}

render_header('PulseNest · 后台管理', $user, [
    'searchText' => '🔎 后台：运营位、评论状态、角色边界、结构迁移、操作日志',
]);
?>
<main class="shell page-shell nebula-page-shell admin-page">
  <?php render_breadcrumbs([
      ['label' => '首页', 'href' => '/'],
      ['label' => '后台中枢'],
  ]); ?>

  <?php if ($flash): ?>
    <div class="notice <?= e($flash['type']) ?> floating-notice"><?= e($flash['message']) ?></div>
  <?php endif; ?>

  <section class="glass nebula-hero nebula-hero-split create-post-hero refined-hero refined-hero-admin">
    <div class="nebula-copy">
      <div class="brand-chip">纳达尔星项目 · 星云初始03 · 后台中枢</div>
      <h1>后台收口成更成熟的运营中枢：先判断，再处理，再留痕。</h1>
      <p class="page-desc nebula-desc">这一轮不加新功能，只把已有能力做成更像成品的界面秩序：运营位、审核流、举报队列、通知概况与治理记录统一为同一套层级语言，读起来更稳，处理起来也更有节奏。</p>
      <div class="hero-stats compact-hero-stats admin-hero-stats refined-hero-stats">
        <div class="hero-stat"><div class="label">当前身份</div><div class="num small-num"><?= e(role_label($role)) ?></div><div class="note"><?= $role === 'admin' ? '全量后台权限已解锁' : '当前仅开放内容管理范围' ?></div></div>
        <div class="hero-stat"><div class="label">后台人员</div><div class="num small-num"><?= $staffCount ?></div><div class="note">管理员 + 版主共同维护</div></div>
        <div class="hero-stat"><div class="label">操作日志</div><div class="num small-num"><?= $logTotal ?></div><div class="note">运营动作 / 状态变更都会留痕</div></div>
      </div>
    </div>
    <aside class="glass side-card nebula-side-panel ops-side-panel admin-side-rail">
      <div class="section-kicker">后台导览</div>
      <div class="quick-links curated-stack">
        <a class="quick-link" href="#permission-map"><strong>权限边界</strong><span>先看自己能动什么</span></a>
        <a class="quick-link" href="#site-settings"><strong>站点设置</strong><span>注册 / 举报 / 审核规则</span></a>
        <a class="quick-link" href="#posts"><strong>帖子运营</strong><span>置顶 / 精华 / 推荐位 / 首页卡</span></a>
        <a class="quick-link" href="<?= e(admin_url(['post_status' => 'pending', 'post_page' => 1], '#posts')) ?>"><strong>待审核队列</strong><span>当前 <?= $pendingPostCount ?> 篇待处理</span></a>
        <a class="quick-link" href="#comments"><strong>评论管理</strong><span>批量审核 / 隐藏 / 恢复</span></a>
        <a class="quick-link" href="#reports"><strong>举报队列</strong><span>帖子 / 评论举报统一处理</span></a>
        <?php if ($canManageUsers): ?><a class="quick-link" href="#users"><strong>角色 / 用户</strong><span>仅管理员可见</span></a><?php endif; ?>
        <?php if ($canManageStructure): ?><a class="quick-link" href="#categories"><strong>分类 / 版块</strong><span>仅管理员可见</span></a><?php endif; ?>
        <a class="quick-link" href="#notifications-overview"><strong>通知概况</strong><span>类型分布 / 未读 / 7 日统计</span></a>
        <a class="quick-link" href="#logs"><strong>操作日志</strong><span>支持筛选与分页</span></a>
      </div>
    </aside>
  </section>

  <section class="glass panel-card admin-panel-card surface-section admin-dashboard-section">
    <div class="section-kicker">运营看板</div>
    <div class="side-head admin-head-row"><h3>运营数据看板</h3><span class="muted">先看新增量、积压量和今日处理量，再决定优先清哪一块。</span></div>
    <div class="hero-stats compact-hero-stats admin-hero-stats">
      <div class="hero-stat"><div class="label">今日新帖</div><div class="num small-num"><?= $dashboardStats['posts_today'] ?></div><div class="note">最近 24 小时新增帖子</div></div>
      <div class="hero-stat"><div class="label">今日新评</div><div class="num small-num"><?= $dashboardStats['comments_today'] ?></div><div class="note">最近 24 小时新增评论</div></div>
      <div class="hero-stat"><div class="label">今日新举报</div><div class="num small-num"><?= $dashboardStats['reports_today'] ?></div><div class="note">最近 24 小时新增举报</div></div>
      <div class="hero-stat"><div class="label">今日提醒</div><div class="num small-num"><?= $dashboardStats['notifications_today'] ?></div><div class="note">最近 24 小时新增站内通知</div></div>
      <div class="hero-stat"><div class="label">待审帖子</div><div class="num small-num"><?= $dashboardStats['pending_posts'] ?></div><div class="note">内容发布积压</div></div>
      <div class="hero-stat"><div class="label">待审评论</div><div class="num small-num"><?= $dashboardStats['pending_comments'] ?></div><div class="note">评论审核积压</div></div>
      <div class="hero-stat"><div class="label">待处理举报</div><div class="num small-num"><?= $dashboardStats['open_reports'] ?></div><div class="note">尚未进入处理流程</div></div>
      <div class="hero-stat"><div class="label">处理中举报</div><div class="num small-num"><?= $dashboardStats['reviewing_reports'] ?></div><div class="note">已经在队列中推进</div></div>
      <div class="hero-stat"><div class="label">今日已处理</div><div class="num small-num"><?= $dashboardStats['reports_resolved_today'] ?></div><div class="note">24 小时内处理完成的举报</div></div>
      <div class="hero-stat"><div class="label">今日已驳回</div><div class="num small-num"><?= $dashboardStats['reports_dismissed_today'] ?></div><div class="note">24 小时内驳回的举报</div></div>
    </div>
  </section>

  <section class="glass panel-card surface-section notification-mix-strip admin-focus-strip">
    <div class="creator-route-copy">
      <div class="section-kicker">当前焦点</div>
      <h3><?= e($operationsFocus['label']) ?></h3>
      <p class="muted"><?= e($operationsFocus['note']) ?></p>
    </div>
    <div class="creator-route-meta">
      <div class="route-mini-card"><strong><?= $dashboardStats['pending_posts'] + $dashboardStats['pending_comments'] ?></strong><span>内容积压</span></div>
      <div class="route-mini-card"><strong><?= $dashboardStats['open_reports'] + $dashboardStats['reviewing_reports'] ?></strong><span>举报队列</span></div>
      <div class="route-mini-card"><strong><?= e($operationsFocus['cta']) ?></strong><span>当前处理顺序</span></div>
    </div>
  </section>

  <div class="nebula-section-grid admin-grid-two surface-grid-row" style="margin-top:24px;">
    <section class="glass panel-card admin-panel-card surface-section">
      <div class="section-kicker">活跃版块</div>
      <div class="side-head admin-head-row"><h3>最近 7 天最活跃版块</h3><span class="muted">按近 7 天发帖量排序，帮助判断社区讨论中心。</span></div>
      <div class="rank-list">
        <?php foreach ($activeBoards as $index => $row): ?>
          <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= $index + 1 ?></div><div class="rank-main"><div class="rank-name"><?= e($row['category_name']) ?> / <?= e($row['board_name']) ?></div><div class="meta">近 7 天发帖活跃度</div></div><div class="score"><?= (int) $row['post_count'] ?>帖</div></div></div>
        <?php endforeach; ?>
        <?php if (!$activeBoards): ?><div class="rank-item"><div class="rank-row"><div class="rank-index">#0</div><div class="rank-main"><div class="rank-name">活跃版块还在形成中</div><div class="meta">等近 7 天公开内容继续累起来后会自然出现</div></div><div class="score">--</div></div></div><?php endif; ?>
      </div>
    </section>

    <section class="glass panel-card admin-panel-card surface-section">
      <div class="section-kicker">活跃作者</div>
      <div class="side-head admin-head-row"><h3>最近 7 天最活跃作者</h3><span class="muted">按近 7 天发帖数 + 浏览量排序。</span></div>
      <div class="rank-list">
        <?php foreach ($activeAuthors as $index => $row): ?>
          <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= $index + 1 ?></div><div class="rank-main"><div class="rank-name"><a class="inline-link" href="/user.php?id=<?= (int) $row['id'] ?>"><?= e($row['nickname']) ?></a></div><div class="meta">@<?= e($row['username']) ?> · 近 7 天累计浏览 <?= (int) $row['total_views'] ?></div></div><div class="score"><?= (int) $row['post_count'] ?>帖</div></div></div>
        <?php endforeach; ?>
        <?php if (!$activeAuthors): ?><div class="rank-item"><div class="rank-row"><div class="rank-index">#0</div><div class="rank-main"><div class="rank-name">活跃作者还在形成中</div><div class="meta">等近 7 天内容与浏览继续累起来后会自然出现</div></div><div class="score">--</div></div></div><?php endif; ?>
      </div>
    </section>
  </div>

  <div class="nebula-section-grid admin-grid-two surface-grid-row" style="margin-top:24px;">
    <section class="glass panel-card admin-panel-card surface-section">
      <div class="section-kicker">举报结构</div>
      <div class="side-head admin-head-row"><h3>举报理由分布</h3><span class="muted">帮助判断当前社区主要风险类型。</span></div>
      <div class="rank-list">
        <?php foreach ($reportReasonStats as $index => $row): ?>
          <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= $index + 1 ?></div><div class="rank-main"><div class="rank-name"><?= e(report_reason_label($row['reason'] ?? 'other')) ?></div><div class="meta">原始值：<?= e($row['reason'] ?? 'other') ?></div></div><div class="score"><?= (int) $row['total_count'] ?></div></div></div>
        <?php endforeach; ?>
        <?php if (!$reportReasonStats): ?><div class="rank-item"><div class="rank-row"><div class="rank-index">#0</div><div class="rank-main"><div class="rank-name">举报结构还没有形成</div><div class="meta">等后续举报进入队列后，这里会自动汇总出主要风险类型</div></div><div class="score">--</div></div></div><?php endif; ?>
      </div>
    </section>

    <section class="glass panel-card admin-panel-card surface-section">
      <div class="section-kicker">七日趋势</div>
      <div class="side-head admin-head-row"><h3>最近 7 天新增趋势</h3><span class="muted">帖子、评论、举报的每日新增量。</span></div>
      <div class="admin-table-wrap">
        <table class="admin-table compact-table">
          <thead><tr><th>日期</th><th>新帖</th><th>新评</th><th>新举报</th></tr></thead>
          <tbody>
            <?php foreach ($weeklyTrend as $row): ?>
              <tr>
                <td><?= e($row['day_label']) ?></td>
                <td><?= (int) $row['post_count'] ?></td>
                <td><?= (int) $row['comment_count'] ?></td>
                <td><?= (int) $row['report_count'] ?></td>
              </tr>
            <?php endforeach; ?>
            <?php if (!$weeklyTrend): ?><tr><td colspan="4" class="muted">最近 7 天还没有新增数据。</td></tr><?php endif; ?>
          </tbody>
        </table>
      </div>
    </section>
  </div>

  <section id="permission-map" class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">权限边界</div>
    <div class="side-head admin-head-row">
      <h3>角色权限边界</h3>
      <span class="muted">普通用户不显示后台入口；版主只处理内容巡检与日志；管理员才可改用户和论坛结构。</span>
    </div>
    <div class="permission-grid">
      <article class="permission-card <?= $role === 'admin' ? 'is-current' : '' ?>">
        <div class="permission-card-head"><strong>管理员</strong><span class="tiny-badge badge-ok">全量</span></div>
        <p class="muted">负责用户权限、论坛结构、内容巡检、运营位和日志留痕。</p>
        <ul class="permission-list">
          <li>可调用户角色 / 启停账号</li>
          <li>可改帖子运营位、首页卡绑定</li>
          <li>可批量审核 / 隐藏评论</li>
          <li>可调整分类 / 版块及回看日志</li>
        </ul>
      </article>
      <article class="permission-card <?= $role === 'moderator' ? 'is-current' : '' ?>">
        <div class="permission-card-head"><strong>版主</strong><span class="tiny-badge">内容管理</span></div>
        <p class="muted">专注内容巡检与评论流，不碰用户权限和社区结构。</p>
        <ul class="permission-list">
          <li>可改帖子运营标记</li>
          <li>可批量审核 / 隐藏 / 恢复评论</li>
          <li>可删帖、删评、看日志</li>
          <li>不可调整用户角色与论坛结构</li>
        </ul>
      </article>
      <article class="permission-card">
        <div class="permission-card-head"><strong>普通用户</strong><span class="tiny-badge">前台</span></div>
        <p class="muted">只保留发帖、评论、提醒、资料维护等前台能力。</p>
        <ul class="permission-list">
          <li>可发帖、评论、看提醒</li>
          <li>可维护头像与简介</li>
          <li>不可进入后台管理页面</li>
          <li>不可操作日志、角色和结构</li>
        </ul>
      </article>
    </div>
  </section>

  <section id="site-settings" class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">站点设置</div>
    <div class="side-head admin-head-row"><h3>站点设置中心</h3><span class="muted">把开放策略、审核阈值和首页展示规则收进一处，不让后台变成四散的开关堆。</span></div>
    <form class="admin-list-card" method="post">
      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
      <input type="hidden" name="action" value="update_site_settings">
      <div class="permission-grid">
        <div>
          <div class="admin-list-card-head"><strong>站点基础信息</strong><span class="tiny-badge">基础</span></div>
          <input class="input" name="<?= e(site_setting_field_name('site.name')) ?>" value="<?= e($siteConfig['site.name'] ?? 'PulseNest') ?>" placeholder="站点名称">
          <input class="input" name="<?= e(site_setting_field_name('site.tagline')) ?>" value="<?= e($siteConfig['site.tagline'] ?? '') ?>" placeholder="站点副标题">
          <textarea class="input" name="<?= e(site_setting_field_name('site.announcement')) ?>" rows="4" placeholder="站点公告（可选）"><?= e($siteConfig['site.announcement'] ?? '') ?></textarea>
        </div>
        <div>
          <div class="admin-list-card-head"><strong>开放策略</strong><span class="tiny-badge">开放</span></div>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('site.registration_enabled')) ?>" value="1" <?= ($siteConfig['site.registration_enabled'] ?? '1') === '1' ? 'checked' : '' ?>> 开放新用户注册</label>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('site.login_enabled')) ?>" value="1" <?= ($siteConfig['site.login_enabled'] ?? '1') === '1' ? 'checked' : '' ?>> 开放用户登录</label>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('site.reporting_enabled')) ?>" value="1" <?= ($siteConfig['site.reporting_enabled'] ?? '1') === '1' ? 'checked' : '' ?>> 开放举报入口</label>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('site.readonly_mode_enabled')) ?>" value="1" <?= ($siteConfig['site.readonly_mode_enabled'] ?? '0') === '1' ? 'checked' : '' ?>> 开启只读模式（普通用户禁发帖/评论/编辑）</label>
        </div>
        <div>
          <div class="admin-list-card-head"><strong>审核策略</strong><span class="tiny-badge">审核</span></div>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('site.post_moderation_enabled')) ?>" value="1" <?= ($siteConfig['site.post_moderation_enabled'] ?? '1') === '1' ? 'checked' : '' ?>> 普通用户发帖默认进入审核</label>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('site.comment_moderation_enabled')) ?>" value="1" <?= ($siteConfig['site.comment_moderation_enabled'] ?? '0') === '1' ? 'checked' : '' ?>> 普通用户评论默认进入审核</label>
          <div class="admin-inline-stack" style="margin-top:12px; align-items:flex-start;">
            <input class="input slim-input" type="number" min="1" name="<?= e(site_setting_field_name('site.post_title_min_length')) ?>" value="<?= e($siteConfig['site.post_title_min_length'] ?? '4') ?>" placeholder="标题最小字数">
            <input class="input slim-input" type="number" min="1" name="<?= e(site_setting_field_name('site.post_title_max_length')) ?>" value="<?= e($siteConfig['site.post_title_max_length'] ?? '120') ?>" placeholder="标题最大字数">
            <input class="input slim-input" type="number" min="1" name="<?= e(site_setting_field_name('site.post_content_min_length')) ?>" value="<?= e($siteConfig['site.post_content_min_length'] ?? '10') ?>" placeholder="正文字数下限">
            <input class="input slim-input" type="number" min="1" name="<?= e(site_setting_field_name('site.comment_content_min_length')) ?>" value="<?= e($siteConfig['site.comment_content_min_length'] ?? '2') ?>" placeholder="评论字数下限">
          </div>
        </div>
        <div>
          <div class="admin-list-card-head"><strong>首页模块与热度权重</strong><span class="tiny-badge">首页 / 热度</span></div>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('home.module.recommended_authors_enabled')) ?>" value="1" <?= ($siteConfig['home.module.recommended_authors_enabled'] ?? '1') === '1' ? 'checked' : '' ?>> 显示推荐作者模块</label>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('home.module.top_viewed_enabled')) ?>" value="1" <?= ($siteConfig['home.module.top_viewed_enabled'] ?? '1') === '1' ? 'checked' : '' ?>> 显示最高浏览模块</label>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('home.module.time_hotlist_enabled')) ?>" value="1" <?= ($siteConfig['home.module.time_hotlist_enabled'] ?? '1') === '1' ? 'checked' : '' ?>> 显示时间窗口热榜</label>
          <div class="admin-inline-stack" style="margin-top:12px; align-items:flex-start;">
            <input class="input slim-input" type="number" min="0" name="<?= e(site_setting_field_name('ranking.weight_like')) ?>" value="<?= e($siteConfig['ranking.weight_like'] ?? '3') ?>" placeholder="点赞权重">
            <input class="input slim-input" type="number" min="0" name="<?= e(site_setting_field_name('ranking.weight_comment')) ?>" value="<?= e($siteConfig['ranking.weight_comment'] ?? '4') ?>" placeholder="回复权重">
            <input class="input slim-input" type="number" min="0" name="<?= e(site_setting_field_name('ranking.weight_view')) ?>" value="<?= e($siteConfig['ranking.weight_view'] ?? '1') ?>" placeholder="浏览权重">
          </div>
        </div>
      </div>
      <div class="admin-action-stack" style="margin-top:16px;"><button class="pill-btn solid" type="submit">保存站点设置</button></div>
    </form>
  </section>

  <section id="posts" class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">帖子运营</div>
    <div class="side-head admin-head-row"><h3>帖子运营工具</h3><span class="muted">支持置顶、精华、推荐分组、显示优先级、推荐位等级、首页运营卡绑定。现在也支持帖子审核队列与批量处理。</span></div>
    <form class="admin-filter-row" method="get" action="/admin.php#posts">
      <input type="hidden" name="post_id" value="<?= $postFilterId > 0 ? (int) $postFilterId : '' ?>">
      <input type="hidden" name="author_id" value="<?= $authorFilterId > 0 ? (int) $authorFilterId : '' ?>">
      <input type="hidden" name="post_title_keyword" value="<?= e($postTitleKeyword) ?>">
      <input type="hidden" name="author_keyword" value="<?= e($authorKeyword) ?>">
      <input type="hidden" name="content_keyword" value="<?= e($contentKeyword) ?>">
      <input type="hidden" name="comment_status" value="<?= e($commentStatusFilter) ?>">
      <input type="hidden" name="comment_page" value="<?= $commentPage ?>">
      <input type="hidden" name="log_action" value="<?= e($logActionFilter) ?>">
      <input type="hidden" name="log_target_type" value="<?= e($logTargetTypeFilter) ?>">
      <input type="hidden" name="log_actor_id" value="<?= $logActorIdFilter ?>">
      <input type="hidden" name="log_page" value="<?= $logPage ?>">
      <select class="input admin-filter-input" name="post_recommend_group">
        <option value="">全部推荐分组</option>
        <?php foreach ($recommendGroups as $groupKey => $groupMeta): ?>
          <option value="<?= e($groupKey) ?>" <?= $postRecommendGroupFilter === $groupKey ? 'selected' : '' ?>><?= e($groupMeta['label']) ?></option>
        <?php endforeach; ?>
      </select>
      <input class="input admin-filter-input" type="number" min="0" max="999" name="post_recommend_priority" placeholder="推荐优先级（精确值）" value="<?= e($postRecommendPriorityFilterRaw) ?>">
      <select class="input admin-filter-input" name="post_is_sticky">
        <option value="">是否置顶：全部</option>
        <option value="1" <?= $postStickyFilter === '1' ? 'selected' : '' ?>>仅看置顶</option>
        <option value="0" <?= $postStickyFilter === '0' ? 'selected' : '' ?>>仅看未置顶</option>
      </select>
      <select class="input admin-filter-input" name="post_is_featured">
        <option value="">是否精华：全部</option>
        <option value="1" <?= $postFeaturedFilter === '1' ? 'selected' : '' ?>>仅看精华</option>
        <option value="0" <?= $postFeaturedFilter === '0' ? 'selected' : '' ?>>仅看非精华</option>
      </select>
      <select class="input admin-filter-input" name="post_home_slot">
        <option value="">首页位：全部</option>
        <option value="__bound__" <?= $postHomeSlotFilter === '__bound__' ? 'selected' : '' ?>>仅看已绑定首页位</option>
        <option value="__unbound__" <?= $postHomeSlotFilter === '__unbound__' ? 'selected' : '' ?>>仅看未绑定首页位</option>
        <?php foreach ($homeSlotDefinitions as $slotKey => $slotMeta): ?>
          <option value="<?= e($slotKey) ?>" <?= $postHomeSlotFilter === $slotKey ? 'selected' : '' ?>><?= e($slotMeta['label']) ?></option>
        <?php endforeach; ?>
      </select>
      <select class="input admin-filter-input" name="post_status">
        <option value="">帖子状态：全部</option>
        <?php foreach (['published', 'pending', 'hidden', 'draft'] as $status): ?>
          <option value="<?= e($status) ?>" <?= $postStatusFilter === $status ? 'selected' : '' ?>><?= e(post_status_label($status)) ?></option>
        <?php endforeach; ?>
      </select>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="<?= e(admin_url(['post_recommend_group' => null, 'post_recommend_priority' => null, 'post_is_sticky' => null, 'post_is_featured' => null, 'post_home_slot' => null, 'post_status' => null, 'post_page' => null], '#posts')) ?>">清空</a>
    </form>
    <div class="hero-stats compact-hero-stats admin-hero-stats" style="margin-top: 16px;">
      <?php foreach ($postStatusStats as $stat): ?>
        <div class="hero-stat"><div class="label"><?= e(post_status_label($stat['status'])) ?></div><div class="num small-num"><?= (int) $stat['total_count'] ?></div><div class="note"><?= ($stat['status'] ?? '') === 'pending' ? '建议优先清理审核队列' : '全站帖子状态计数' ?></div></div>
      <?php endforeach; ?>
    </div>
    <div class="admin-log-meta muted">当前筛选命中 <?= count($postRows) ?> 篇帖子 · 共 <?= $postCountTotal ?> 篇 · 第 <?= $postPage ?> / <?= $postTotalPages ?> 页<?= $postStatusFilter === 'pending' ? ' · 当前正处于待审核队列视图' : '' ?></div>
    <form id="bulk-posts-form" method="post">
      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
      <input type="hidden" name="action" value="bulk_post_status">
      <input type="hidden" name="target_status" id="bulk-post-status" value="published">
    </form>
    <div class="admin-bulk-bar">
      <button class="pill-btn solid" type="submit" form="bulk-posts-form" onclick="document.getElementById('bulk-post-status').value='published'; return confirm('确认批量发布已勾选帖子？');">批量发布</button>
      <button class="pill-btn" type="submit" form="bulk-posts-form" onclick="document.getElementById('bulk-post-status').value='pending'; return confirm('确认批量恢复到待审核？');">批量恢复待审核</button>
      <button class="pill-btn danger" type="submit" form="bulk-posts-form" onclick="document.getElementById('bulk-post-status').value='hidden'; return confirm('确认批量隐藏已勾选帖子？');">批量隐藏</button>
    </div>
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th><input type="checkbox" onclick="document.querySelectorAll('.post-select').forEach(el => el.checked = this.checked)"></th><th>ID</th><th>标题</th><th>作者</th><th>版块</th><th>热度</th><th>运营位</th><th>操作</th></tr></thead>
        <tbody>
          <?php foreach ($postRows as $row): ?>
            <tr>
              <td><input class="post-select" type="checkbox" name="post_ids[]" value="<?= (int) $row['id'] ?>" form="bulk-posts-form"></td>
              <td>#<?= (int) $row['id'] ?></td>
              <td>
                <a class="inline-link" href="/post.php?id=<?= (int) $row['id'] ?>"><?= e($row['title']) ?></a>
                <div class="chips" style="margin-top:8px; gap:6px;">
                  <span class="chip">状态 · <?= e(post_status_label($row['status'] ?? 'published')) ?></span>
                  <?php if ((int) $row['is_sticky'] === 1): ?><span class="chip">置顶</span><?php endif; ?>
                  <?php if ((int) $row['is_featured'] === 1): ?><span class="chip">精华</span><?php endif; ?>
                  <?php if ((int) $row['recommend_level'] > 0): ?><span class="chip">推荐位 <?= (int) $row['recommend_level'] ?></span><?php endif; ?>
                  <span class="chip"><?= e($recommendGroups[$row['recommend_group']]['label'] ?? ($row['recommend_group'] ?? '综合推荐')) ?></span>
                  <span class="chip">优先级 <?= (int) ($row['recommend_priority'] ?? 0) ?></span>
                  <?php if (!empty($row['home_slot'])): ?><span class="chip">首页卡 · <?= e($homeSlotDefinitions[$row['home_slot']]['label'] ?? $row['home_slot']) ?></span><?php endif; ?>
                </div>
              </td>
              <td><?= e($row['nickname']) ?><div class="muted">@<?= e($row['username']) ?></div></td>
              <td><?= e(trim(($row['category_name'] ?? '公共区') . ' / ' . ($row['board_name'] ?? '未分区'))) ?></td>
              <td><?= (int) $row['like_count'] ?> 赞 · <?= (int) $row['comment_count'] ?> 评 · <?= (int) ($row['view_count'] ?? 0) ?> 浏览</td>
              <td>
                <form method="post" class="admin-inline-stack" style="align-items:flex-start;">
                  <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                  <input type="hidden" name="action" value="update_post_ops">
                  <input type="hidden" name="post_id" value="<?= (int) $row['id'] ?>">
                  <select class="input slim-input" name="status">
                    <?php foreach (['published', 'pending', 'hidden', 'draft'] as $status): ?>
                      <option value="<?= e($status) ?>" <?= ($row['status'] ?? 'published') === $status ? 'selected' : '' ?>><?= e(post_status_label($status)) ?></option>
                    <?php endforeach; ?>
                  </select>
                  <label class="muted"><input type="checkbox" name="is_sticky" value="1" <?= (int) $row['is_sticky'] === 1 ? 'checked' : '' ?>> 置顶</label>
                  <label class="muted"><input type="checkbox" name="is_featured" value="1" <?= (int) $row['is_featured'] === 1 ? 'checked' : '' ?>> 精华</label>
                  <select class="input slim-input" name="recommend_group">
                    <?php foreach ($recommendGroups as $groupKey => $groupMeta): ?>
                      <option value="<?= e($groupKey) ?>" <?= ($row['recommend_group'] ?? 'general') === $groupKey ? 'selected' : '' ?>><?= e($groupMeta['label']) ?></option>
                    <?php endforeach; ?>
                  </select>
                  <input class="input slim-input" type="number" min="0" max="999" name="recommend_priority" value="<?= (int) ($row['recommend_priority'] ?? 0) ?>" placeholder="优先级">
                  <select class="input slim-input" name="recommend_level">
                    <?php for ($level = 0; $level <= 5; $level++): ?>
                      <option value="<?= $level ?>" <?= (int) $row['recommend_level'] === $level ? 'selected' : '' ?>>推荐位 <?= $level ?></option>
                    <?php endfor; ?>
                  </select>
                  <select class="input slim-input" name="home_slot">
                    <option value="">不绑定首页卡</option>
                    <?php foreach ($homeSlotDefinitions as $slotKey => $slotMeta): ?>
                      <option value="<?= e($slotKey) ?>" <?= ($row['home_slot'] ?? '') === $slotKey ? 'selected' : '' ?>><?= e($slotMeta['label']) ?></option>
                    <?php endforeach; ?>
                  </select>
                  <button class="pill-btn solid" type="submit">保存运营位</button>
                </form>
              </td>
              <td>
                <div class="admin-action-stack">
                  <a class="pill-btn" href="/edit-post.php?id=<?= (int) $row['id'] ?>">编辑</a>
                  <a class="pill-btn" href="<?= e(admin_url(['post_id' => (int) $row['id']], '#comments')) ?>">看评论</a>
                  <?php if (($row['status'] ?? 'published') !== 'published'): ?>
                    <form method="post" class="inline-form">
                      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                      <input type="hidden" name="action" value="bulk_post_status">
                      <input type="hidden" name="post_ids[]" value="<?= (int) $row['id'] ?>">
                      <input type="hidden" name="target_status" value="published">
                      <button class="pill-btn solid" type="submit">发布</button>
                    </form>
                  <?php endif; ?>
                  <?php if (($row['status'] ?? 'published') !== 'pending'): ?>
                    <form method="post" class="inline-form">
                      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                      <input type="hidden" name="action" value="bulk_post_status">
                      <input type="hidden" name="post_ids[]" value="<?= (int) $row['id'] ?>">
                      <input type="hidden" name="target_status" value="pending">
                      <button class="pill-btn" type="submit">转待审</button>
                    </form>
                  <?php endif; ?>
                  <form method="post" class="inline-form" onsubmit="return confirm('确认删除这篇帖子？帖子下评论也会一起删除，并写入日志。');">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="delete_post_admin">
                    <input type="hidden" name="post_id" value="<?= (int) $row['id'] ?>">
                    <button class="pill-btn danger" type="submit">删除</button>
                  </form>
                </div>
              </td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$postRows): ?>
            <tr><td colspan="8" class="muted">当前筛选条件下没有帖子记录。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>

    <?= admin_pagination([
      'post_id' => $postFilterId,
      'author_id' => $authorFilterId,
      'post_title_keyword' => $postTitleKeyword,
      'author_keyword' => $authorKeyword,
      'content_keyword' => $contentKeyword,
      'comment_status' => $commentStatusFilter,
      'post_recommend_group' => $postRecommendGroupFilter,
      'post_recommend_priority' => $postRecommendPriorityFilterRaw,
      'post_is_sticky' => $postStickyFilter,
      'post_is_featured' => $postFeaturedFilter,
      'post_home_slot' => $postHomeSlotFilter,
      'post_status' => $postStatusFilter,
      'comment_page' => $commentPage,
      'log_action' => $logActionFilter,
      'log_target_type' => $logTargetTypeFilter,
      'log_actor_id' => $logActorIdFilter,
      'log_page' => $logPage,
    ], 'post_page', $postPage, $postTotalPages, '#posts') ?>

    <div class="permission-grid" style="margin-top:20px;">
      <?php foreach ($homeSlotDefinitions as $slotKey => $slotMeta): ?>
        <article class="permission-card">
          <div class="permission-card-head"><strong><?= e($slotMeta['label']) ?></strong><span class="tiny-badge">首页卡</span></div>
          <p class="muted"><?= e($slotMeta['desc']) ?></p>
          <?php if (isset($boundSlots[$slotKey])): ?>
            <div><a class="inline-link" href="/post.php?id=<?= (int) $boundSlots[$slotKey]['id'] ?>"><?= e($boundSlots[$slotKey]['title']) ?></a></div>
          <?php else: ?>
            <div class="muted">当前未绑定帖子</div>
          <?php endif; ?>
        </article>
      <?php endforeach; ?>
    </div>
  </section>

  <section id="home-copy" class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">首页文案</div>
    <div class="side-head admin-head-row"><h3>首页运营卡文案</h3><span class="muted">主视觉和三张焦点卡的标题、说明、标签都在这里统一维护，前台首页会实时读取。</span></div>
    <form class="admin-list-card" method="post">
      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
      <input type="hidden" name="action" value="update_home_copy">
      <div class="permission-grid">
        <div>
          <div class="admin-list-card-head"><strong>首页主视觉</strong><span class="tiny-badge">顶部主入口</span></div>
          <div class="notice subtle-notice" style="margin-bottom: 12px;">混合模式：主视觉绑定帖子后，仍可决定标题和说明是否继续使用这里的自定义口径。</div>
          <input class="input" name="<?= e(site_setting_field_name('home.hero.eyebrow')) ?>" value="<?= e($homeCopy['home.hero.eyebrow']) ?>" placeholder="眉标">
          <input class="input" name="<?= e(site_setting_field_name('home.hero.title')) ?>" value="<?= e($homeCopy['home.hero.title']) ?>" placeholder="主标题">
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('home.hero.use_custom_title')) ?>" value="1" <?= hero_uses_custom_title($homeCopy) ? 'checked' : '' ?>> 绑定帖子后仍使用上面这条自定义主标题</label>
          <textarea class="input" name="<?= e(site_setting_field_name('home.hero.body')) ?>" rows="4" placeholder="Hero 副文案"><?= e($homeCopy['home.hero.body']) ?></textarea>
          <label class="muted"><input type="checkbox" name="<?= e(site_setting_field_name('home.hero.use_custom_body')) ?>" value="1" <?= hero_uses_custom_body($homeCopy) ? 'checked' : '' ?>> 绑定帖子后仍使用上面这条自定义副文案</label>
          <div class="admin-inline-stack">
            <input class="input" name="<?= e(site_setting_field_name('home.hero.tag_primary')) ?>" value="<?= e($homeCopy['home.hero.tag_primary']) ?>" placeholder="标签 1">
            <input class="input" name="<?= e(site_setting_field_name('home.hero.tag_secondary')) ?>" value="<?= e($homeCopy['home.hero.tag_secondary']) ?>" placeholder="标签 2">
          </div>
        </div>
        <?php foreach (['focus_one' => '焦点卡 1', 'focus_two' => '焦点卡 2', 'focus_three' => '焦点卡 3'] as $slotKey => $slotLabel): ?>
          <div>
            <div class="admin-list-card-head"><strong><?= e($slotLabel) ?></strong><span class="tiny-badge">焦点位</span></div>
            <input class="input" name="<?= e(site_setting_field_name('home.' . $slotKey . '.badge')) ?>" value="<?= e($homeCopy['home.' . $slotKey . '.badge']) ?>" placeholder="顶部标签">
            <input class="input" name="<?= e(site_setting_field_name('home.' . $slotKey . '.title')) ?>" value="<?= e($homeCopy['home.' . $slotKey . '.title']) ?>" placeholder="标题">
            <textarea class="input" name="<?= e(site_setting_field_name('home.' . $slotKey . '.body')) ?>" rows="3" placeholder="副文案"><?= e($homeCopy['home.' . $slotKey . '.body']) ?></textarea>
            <input class="input" name="<?= e(site_setting_field_name('home.' . $slotKey . '.tag')) ?>" value="<?= e($homeCopy['home.' . $slotKey . '.tag']) ?>" placeholder="标签">
          </div>
        <?php endforeach; ?>
      </div>
      <div class="admin-action-stack" style="margin-top:16px;"><button class="pill-btn solid" type="submit">保存首页文案</button></div>
    </form>
  </section>

  <section id="comments" class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">评论管理</div>
    <div class="side-head admin-head-row"><h3>评论管理</h3><span class="muted">支持按帖子 / 作者 / 关键词 / 状态筛选，并可批量审核、隐藏、恢复。</span></div>
    <form class="admin-filter-row" method="get">
      <input class="input admin-filter-input" type="number" min="0" name="post_id" placeholder="按帖子 ID 查看" value="<?= $postFilterId > 0 ? (int) $postFilterId : '' ?>">
      <input class="input admin-filter-input" type="number" min="0" name="author_id" placeholder="按作者 ID 查看" value="<?= $authorFilterId > 0 ? (int) $authorFilterId : '' ?>">
      <input class="input admin-filter-input" type="text" name="post_title_keyword" placeholder="帖子标题关键词" value="<?= e($postTitleKeyword) ?>">
      <input class="input admin-filter-input" type="text" name="author_keyword" placeholder="作者昵称 / 用户名关键词" value="<?= e($authorKeyword) ?>">
      <input class="input admin-filter-input" type="text" name="content_keyword" placeholder="评论内容关键词" value="<?= e($contentKeyword) ?>">
      <select class="input admin-filter-input" name="comment_status">
        <option value="">全部状态</option>
        <?php foreach (['approved', 'pending', 'hidden'] as $status): ?>
          <option value="<?= e($status) ?>" <?= $commentStatusFilter === $status ? 'selected' : '' ?>><?= e(comment_status_label($status)) ?></option>
        <?php endforeach; ?>
      </select>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="/admin.php#comments">清空</a>
    </form>
    <div class="hero-stats compact-hero-stats admin-hero-stats" style="margin-top: 16px;">
      <?php foreach ($commentStatusStats as $stat): ?>
        <div class="hero-stat"><div class="label"><?= e(comment_status_label($stat['status'])) ?></div><div class="num small-num"><?= (int) $stat['total_count'] ?></div><div class="note">全站评论状态计数</div></div>
      <?php endforeach; ?>
    </div>
    <div class="admin-log-meta muted">当前页命中 <?= $commentCount ?> 条评论 · 共 <?= $commentTotal ?> 条 · 第 <?= $commentPage ?> / <?= $commentTotalPages ?> 页</div>
    <form id="bulk-comments-form" method="post">
      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
      <input type="hidden" name="action" value="bulk_comment_status">
      <input type="hidden" name="target_status" id="bulk-comment-status" value="approved">
    </form>
    <div class="admin-bulk-bar">
      <button class="pill-btn solid" type="submit" form="bulk-comments-form" onclick="document.getElementById('bulk-comment-status').value='approved'; return confirm('确认批量通过已勾选评论？');">批量审核通过</button>
      <button class="pill-btn" type="submit" form="bulk-comments-form" onclick="document.getElementById('bulk-comment-status').value='pending'; return confirm('确认批量恢复到待审核？');">批量恢复待审核</button>
      <button class="pill-btn danger" type="submit" form="bulk-comments-form" onclick="document.getElementById('bulk-comment-status').value='hidden'; return confirm('确认批量隐藏已勾选评论？');">批量隐藏</button>
    </div>
    <div class="admin-table-wrap">
      <table class="admin-table">
        <thead><tr><th><input type="checkbox" onclick="document.querySelectorAll('.comment-select').forEach(el => el.checked = this.checked)"></th><th>ID</th><th>评论内容</th><th>状态</th><th>作者</th><th>所属帖子</th><th>时间</th><th>操作</th></tr></thead>
        <tbody>
          <?php foreach ($commentRows as $row): ?>
            <tr>
              <td><input class="comment-select" type="checkbox" name="comment_ids[]" value="<?= (int) $row['id'] ?>" form="bulk-comments-form"></td>
              <td>#<?= (int) $row['id'] ?></td>
              <td><?= e(excerpt($row['content'], 88)) ?></td>
              <td><span class="tiny-badge"><?= e(comment_status_label($row['status'] ?? 'approved')) ?></span></td>
              <td>
                <strong><?= e($row['nickname']) ?></strong>
                <div class="muted">@<?= e($row['username']) ?></div>
                <div><a class="inline-link" href="<?= e(admin_url(['author_id' => (int) $row['user_id'], 'author_keyword' => null], '#comments')) ?>">看该作者评论</a></div>
              </td>
              <td>
                <a class="inline-link" href="/post.php?id=<?= (int) $row['post_id'] ?>"><?= e($row['post_title']) ?></a>
                <div class="muted">楼主：<?= e($row['post_owner_nickname']) ?> @<?= e($row['post_owner_username']) ?></div>
                <div><a class="inline-link" href="<?= e(admin_url(['post_id' => (int) $row['post_id'], 'post_title_keyword' => null], '#comments')) ?>">看该帖子评论</a></div>
              </td>
              <td><?= e(substr($row['created_at'], 0, 16)) ?></td>
              <td>
                <div class="admin-action-stack">
                  <a class="pill-btn" href="/post.php?id=<?= (int) $row['post_id'] ?>">前往原帖</a>
                  <form method="post" class="inline-form">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="bulk_comment_status">
                    <input type="hidden" name="comment_ids[]" value="<?= (int) $row['id'] ?>">
                    <input type="hidden" name="target_status" value="approved">
                    <button class="pill-btn solid" type="submit">通过</button>
                  </form>
                  <form method="post" class="inline-form">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="bulk_comment_status">
                    <input type="hidden" name="comment_ids[]" value="<?= (int) $row['id'] ?>">
                    <input type="hidden" name="target_status" value="hidden">
                    <button class="pill-btn" type="submit">隐藏</button>
                  </form>
                  <form method="post" class="inline-form">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="bulk_comment_status">
                    <input type="hidden" name="comment_ids[]" value="<?= (int) $row['id'] ?>">
                    <input type="hidden" name="target_status" value="pending">
                    <button class="pill-btn" type="submit">待审</button>
                  </form>
                  <form method="post" class="inline-form" onsubmit="return confirm('确认删除这条评论？此操作会写入日志。');">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="delete_comment_admin">
                    <input type="hidden" name="comment_id" value="<?= (int) $row['id'] ?>">
                    <button class="pill-btn danger" type="submit">删除</button>
                  </form>
                </div>
              </td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$commentRows): ?>
            <tr><td colspan="8" class="muted">当前筛选条件下没有评论记录。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
    <?= admin_pagination([
      'post_id' => $postFilterId,
      'author_id' => $authorFilterId,
      'post_title_keyword' => $postTitleKeyword,
      'author_keyword' => $authorKeyword,
      'content_keyword' => $contentKeyword,
      'comment_status' => $commentStatusFilter,
      'post_page' => $postPage,
      'log_action' => $logActionFilter,
      'log_target_type' => $logTargetTypeFilter,
      'log_actor_id' => $logActorIdFilter,
      'log_page' => $logPage,
    ], 'comment_page', $commentPage, $commentTotalPages, '#comments') ?>
  </section>

  <section id="reports" class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">举报队列</div>
    <div class="side-head admin-head-row"><h3>举报队列</h3><span class="muted">统一处理帖子 / 评论举报，先标记处理中，再决定已处理或驳回。</span></div>
    <form class="admin-filter-row" method="get" action="/admin.php#reports">
      <input type="hidden" name="post_id" value="<?= $postFilterId > 0 ? (int) $postFilterId : '' ?>">
      <input type="hidden" name="author_id" value="<?= $authorFilterId > 0 ? (int) $authorFilterId : '' ?>">
      <input type="hidden" name="post_title_keyword" value="<?= e($postTitleKeyword) ?>">
      <input type="hidden" name="author_keyword" value="<?= e($authorKeyword) ?>">
      <input type="hidden" name="content_keyword" value="<?= e($contentKeyword) ?>">
      <input type="hidden" name="comment_status" value="<?= e($commentStatusFilter) ?>">
      <input type="hidden" name="post_recommend_group" value="<?= e($postRecommendGroupFilter) ?>">
      <input type="hidden" name="post_recommend_priority" value="<?= e($postRecommendPriorityFilterRaw) ?>">
      <input type="hidden" name="post_is_sticky" value="<?= e($postStickyFilter) ?>">
      <input type="hidden" name="post_is_featured" value="<?= e($postFeaturedFilter) ?>">
      <input type="hidden" name="post_home_slot" value="<?= e($postHomeSlotFilter) ?>">
      <input type="hidden" name="post_status" value="<?= e($postStatusFilter) ?>">
      <input type="hidden" name="post_page" value="<?= $postPage ?>">
      <input type="hidden" name="comment_page" value="<?= $commentPage ?>">
      <input type="hidden" name="log_action" value="<?= e($logActionFilter) ?>">
      <input type="hidden" name="log_target_type" value="<?= e($logTargetTypeFilter) ?>">
      <input type="hidden" name="log_actor_id" value="<?= $logActorIdFilter ?>">
      <input type="hidden" name="log_page" value="<?= $logPage ?>">
      <select class="input admin-filter-input" name="report_status">
        <option value="">举报状态：全部</option>
        <?php foreach (['open' => '待处理', 'reviewing' => '处理中', 'resolved' => '已处理', 'dismissed' => '已驳回'] as $statusKey => $statusLabel): ?>
          <option value="<?= e($statusKey) ?>" <?= $reportStatusFilter === $statusKey ? 'selected' : '' ?>><?= e($statusLabel) ?></option>
        <?php endforeach; ?>
      </select>
      <select class="input admin-filter-input" name="report_target_type">
        <option value="">举报对象：全部</option>
        <option value="post" <?= $reportTargetTypeFilter === 'post' ? 'selected' : '' ?>>仅帖子举报</option>
        <option value="comment" <?= $reportTargetTypeFilter === 'comment' ? 'selected' : '' ?>>仅评论举报</option>
      </select>
      <select class="input admin-filter-input" name="report_reason">
        <option value="">举报理由：全部</option>
        <?php foreach (report_reason_options() as $reasonKey => $reasonLabel): ?>
          <option value="<?= e($reasonKey) ?>" <?= $reportReasonFilter === $reasonKey ? 'selected' : '' ?>><?= e($reasonLabel) ?></option>
        <?php endforeach; ?>
      </select>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="<?= e(admin_url(['report_status' => null, 'report_target_type' => null, 'report_reason' => null, 'report_page' => null], '#reports')) ?>">清空</a>
      <a class="pill-btn" href="<?= e(admin_url(['report_status' => 'open', 'report_page' => 1], '#reports')) ?>">只看待处理</a>
    </form>
    <div class="hero-stats compact-hero-stats admin-hero-stats" style="margin-top: 16px;">
      <div class="hero-stat"><div class="label">待处理举报</div><div class="num small-num"><?= $openReportCount ?></div><div class="note">建议优先清理开放中的举报</div></div>
      <div class="hero-stat"><div class="label">当前筛选结果</div><div class="num small-num"><?= count($reportRows) ?></div><div class="note">共 <?= $reportTotal ?> 条 · 第 <?= $reportPage ?> / <?= $reportTotalPages ?> 页</div></div>
    </div>
    <form id="bulk-reports-form" method="post">
      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
      <input type="hidden" name="action" value="bulk_report_status">
      <input type="hidden" name="target_status" id="bulk-report-status" value="reviewing">
      <input type="hidden" name="content_action" id="bulk-report-content-action" value="none">
      <input type="hidden" name="resolution_note" id="bulk-report-note" value="">
    </form>
    <div class="admin-bulk-bar">
      <button class="pill-btn solid" type="submit" form="bulk-reports-form" onclick="document.getElementById('bulk-report-status').value='reviewing'; document.getElementById('bulk-report-content-action').value='none'; return confirm('确认批量标记为处理中？');">批量处理中</button>
      <button class="pill-btn" type="submit" form="bulk-reports-form" onclick="document.getElementById('bulk-report-status').value='resolved'; document.getElementById('bulk-report-content-action').value='none'; return confirm('确认批量标记为已处理？');">批量已处理</button>
      <button class="pill-btn danger" type="submit" form="bulk-reports-form" onclick="document.getElementById('bulk-report-status').value='dismissed'; document.getElementById('bulk-report-content-action').value='none'; return confirm('确认批量驳回已勾选举报？');">批量驳回</button>
    </div>
    <div class="admin-bulk-bar" style="justify-content:flex-start; gap:12px; flex-wrap:wrap;">
      <button class="pill-btn" type="submit" form="bulk-reports-form" onclick="document.getElementById('bulk-report-status').value='resolved'; document.getElementById('bulk-report-content-action').value='hide_post'; return confirm('确认批量已处理并联动隐藏帖子？仅对帖子举报生效。');">批量隐藏帖子</button>
      <button class="pill-btn" type="submit" form="bulk-reports-form" onclick="document.getElementById('bulk-report-status').value='resolved'; document.getElementById('bulk-report-content-action').value='hide_comment'; return confirm('确认批量已处理并联动隐藏评论？仅对评论举报生效。');">批量隐藏评论</button>
      <button class="pill-btn" type="submit" form="bulk-reports-form" onclick="document.getElementById('bulk-report-status').value='resolved'; document.getElementById('bulk-report-content-action').value='delete_comment'; return confirm('确认批量已处理并联动删除评论？仅对评论举报生效。');">批量删评论</button>
    </div>
    <div class="admin-table-wrap">
      <table class="admin-table compact-table">
        <thead><tr><th><input type="checkbox" onclick="document.querySelectorAll('.report-select').forEach(el => el.checked = this.checked)"></th><th>ID</th><th>举报内容</th><th>举报人</th><th>原因</th><th>状态</th><th>处理</th></tr></thead>
        <tbody>
          <?php foreach ($reportRows as $row): ?>
            <tr>
              <td><input class="report-select" type="checkbox" name="report_ids[]" value="<?= (int) $row['id'] ?>" form="bulk-reports-form"></td>
              <td>#<?= (int) $row['id'] ?></td>
              <td>
                <span class="tiny-badge"><?= e($row['target_type'] === 'comment' ? '评论举报' : '帖子举报') ?></span>
                <div style="margin-top:8px;"><a class="inline-link" href="/post.php?id=<?= (int) $row['post_id'] ?>"><?= e($row['post_title']) ?></a></div>
                <?php if (($row['target_type'] ?? '') === 'comment' && !empty($row['comment_content'])): ?>
                  <div class="muted" style="margin-top:6px;">评论：<?= e(excerpt($row['comment_content'], 72)) ?></div>
                <?php endif; ?>
                <?php if (!empty($row['detail'])): ?>
                  <div class="muted" style="margin-top:6px;">补充：<?= e(excerpt($row['detail'], 90)) ?></div>
                <?php endif; ?>
              </td>
              <td><?= e($row['reporter_nickname']) ?><div class="muted">@<?= e($row['reporter_username']) ?></div><div class="muted"><?= e(substr($row['created_at'], 0, 16)) ?></div></td>
              <td><span class="tiny-badge"><?= e(report_reason_label($row['reason'] ?? 'other')) ?></span></td>
              <td>
                <span class="tiny-badge"><?= e(report_status_label($row['status'] ?? 'open')) ?></span>
                <?php if (!empty($row['resolver_nickname'])): ?><div class="muted" style="margin-top:6px;">处理人：<?= e($row['resolver_nickname']) ?> @<?= e($row['resolver_username']) ?></div><?php endif; ?>
                <?php if (!empty($row['resolution_note'])): ?><div class="muted" style="margin-top:6px;">备注：<?= e($row['resolution_note']) ?></div><?php endif; ?>
              </td>
              <td>
                <form method="post" class="admin-inline-stack" style="align-items:flex-start;">
                  <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                  <input type="hidden" name="action" value="resolve_report">
                  <input type="hidden" name="report_id" value="<?= (int) $row['id'] ?>">
                  <select class="input slim-input" name="target_status">
                    <?php foreach (['open' => '待处理', 'reviewing' => '处理中', 'resolved' => '已处理', 'dismissed' => '已驳回'] as $statusKey => $statusLabel): ?>
                      <?php if ($statusKey === 'open') { continue; } ?>
                      <option value="<?= e($statusKey) ?>"><?= e($statusLabel) ?></option>
                    <?php endforeach; ?>
                  </select>
                  <select class="input slim-input" name="content_action">
                    <option value="none">仅更新举报状态</option>
                    <?php if (($row['target_type'] ?? '') === 'comment'): ?>
                      <option value="hide_comment">联动隐藏评论</option>
                      <option value="approve_comment">联动恢复评论</option>
                      <option value="delete_comment">联动删除评论</option>
                    <?php else: ?>
                      <option value="hide_post">联动隐藏帖子</option>
                      <option value="restore_post">联动恢复帖子</option>
                    <?php endif; ?>
                  </select>
                  <input class="input slim-input" name="resolution_note" placeholder="处理备注（可选）">
                  <button class="pill-btn solid" type="submit">保存</button>
                </form>
              </td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$reportRows): ?>
            <tr><td colspan="7" class="muted">当前还没有任何举报记录。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
    <?= admin_pagination([
      'post_id' => $postFilterId,
      'author_id' => $authorFilterId,
      'post_title_keyword' => $postTitleKeyword,
      'author_keyword' => $authorKeyword,
      'content_keyword' => $contentKeyword,
      'comment_status' => $commentStatusFilter,
      'post_recommend_group' => $postRecommendGroupFilter,
      'post_recommend_priority' => $postRecommendPriorityFilterRaw,
      'post_is_sticky' => $postStickyFilter,
      'post_is_featured' => $postFeaturedFilter,
      'post_home_slot' => $postHomeSlotFilter,
      'post_status' => $postStatusFilter,
      'post_page' => $postPage,
      'comment_page' => $commentPage,
      'report_status' => $reportStatusFilter,
      'report_target_type' => $reportTargetTypeFilter,
      'report_reason' => $reportReasonFilter,
      'log_action' => $logActionFilter,
      'log_target_type' => $logTargetTypeFilter,
      'log_actor_id' => $logActorIdFilter,
      'log_page' => $logPage,
    ], 'report_page', $reportPage, $reportTotalPages, '#reports') ?>
  </section>

  <section id="notifications-overview" class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">通知概况</div>
    <div class="side-head admin-head-row"><h3>站内通知概况</h3><span class="muted">前台已支持未读筛选、按类型筛选和批量处理，这里保留全站分布看板。</span></div>
    <div class="hero-stats compact-hero-stats admin-hero-stats">
      <div class="hero-stat"><div class="label">通知总数</div><div class="num small-num"><?= (int) ($notificationTotals['total_notifications'] ?? 0) ?></div><div class="note">全站累计站内提醒</div></div>
      <div class="hero-stat"><div class="label">全站未读</div><div class="num small-num"><?= (int) ($notificationTotals['unread_notifications'] ?? 0) ?></div><div class="note">尚未被用户消化</div></div>
      <div class="hero-stat"><div class="label">24 小时</div><div class="num small-num"><?= $notificationTodayCount ?></div><div class="note">最近一天新增提醒</div></div>
      <div class="hero-stat"><div class="label">7 天</div><div class="num small-num"><?= $notificationSevenDayCount ?></div><div class="note">最近七天新增提醒</div></div>
    </div>
    <div class="admin-table-wrap">
      <table class="admin-table compact-table">
        <thead><tr><th>提醒类型</th><th>总量</th><th>未读</th><th>说明</th></tr></thead>
        <tbody>
          <?php foreach ($notificationTypeRows as $row): ?>
            <tr>
              <td><span class="tiny-badge"><?= e(notification_type_label($row['type'])) ?></span><div class="muted"><?= e($row['type']) ?></div></td>
              <td><?= (int) $row['total_count'] ?></td>
              <td><?= (int) $row['unread_count'] ?></td>
              <td><?= e(admin_notification_copy($row['type'])) ?></td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$notificationTypeRows): ?>
            <tr><td colspan="4" class="muted">当前还没有任何站内通知数据。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
  </section>

  <?php if ($canManageUsers): ?>
    <div class="nebula-section-grid admin-grid-two" style="margin-top:24px;">
      <section class="glass panel-card admin-panel-card surface-section">
        <div class="section-kicker">高风险用户</div>
        <div class="side-head admin-head-row"><h3>高风险用户榜单</h3><span class="muted">按高风险记录数、开放中记录数排序，帮助 staff 快速定位重点用户。</span></div>
        <div class="rank-list">
          <?php foreach ($highRiskUsers as $index => $row): ?>
            <div class="rank-item"><div class="rank-row"><div class="rank-index">#<?= $index + 1 ?></div><div class="rank-main"><div class="rank-name"><a class="inline-link" href="/user-governance.php?id=<?= (int) $row['id'] ?>"><?= e($row['nickname']) ?></a></div><div class="meta">@<?= e($row['username']) ?> · <?= (int) $row['note_count'] ?> 条记录 · <?= (int) $row['open_count'] ?> 条开放中 · 被举报 <?= (int) ($row['report_count'] ?? 0) ?> 次</div></div><div class="score"><?= (int) $row['high_count'] ?>高危</div></div></div>
          <?php endforeach; ?>
          <?php if (!$highRiskUsers): ?><div class="rank-item"><div class="rank-row"><div class="rank-index">#0</div><div class="rank-main"><div class="rank-name">暂无高风险用户</div><div class="meta">当前治理记录里没有高风险或开放中用户</div></div><div class="score">--</div></div></div><?php endif; ?>
        </div>
      </section>
    </div>

    <section class="glass panel-card admin-panel-card surface-section">
      <div class="section-kicker">治理日志</div>
      <div class="side-head admin-head-row"><h3>用户治理记录</h3><span class="muted">封禁记录会自动停用账号；这里保留最近治理动作清单。</span></div>
      <form class="admin-filter-row" method="get" action="/admin.php#users">
        <select class="input admin-filter-input" name="governance_status">
          <option value="">治理状态：全部</option>
          <?php foreach (['open' => '开放中', 'resolved' => '已处理', 'dismissed' => '已关闭'] as $statusKey => $statusLabel): ?>
            <option value="<?= e($statusKey) ?>" <?= $governanceStatusFilter === $statusKey ? 'selected' : '' ?>><?= e($statusLabel) ?></option>
          <?php endforeach; ?>
        </select>
        <label class="muted"><input type="checkbox" name="governance_high_risk_only" value="1" <?= $governanceHighRiskOnly ? 'checked' : '' ?>> 仅看高风险</label>
        <button class="pill-btn solid" type="submit">筛选</button>
        <a class="pill-btn" href="<?= e(admin_url(['governance_status' => null, 'governance_high_risk_only' => null], '#users')) ?>">清空</a>
      </form>
      <div class="admin-table-wrap">
        <table class="admin-table compact-table">
          <thead><tr><th>ID</th><th>目标用户</th><th>类型</th><th>风险等级</th><th>记录状态</th><th>原因</th><th>记录人</th><th>操作</th></tr></thead>
          <tbody>
            <?php foreach ($governanceRows as $row): ?>
              <tr>
                <td>#<?= (int) $row['id'] ?></td>
                <td><a class="inline-link" href="/user-governance.php?id=<?= (int) $row['user_id'] ?>"><?= e($row['nickname']) ?></a><div class="muted">@<?= e($row['username']) ?></div></td>
                <td><span class="tiny-badge"><?= e(governance_note_type_label($row['note_type'] ?? 'warning')) ?></span></td>
                <td><span class="tiny-badge"><?= e(governance_severity_label($row['severity'] ?? 'medium')) ?></span></td>
                <td><span class="tiny-badge"><?= e(governance_status_label($row['status'] ?? 'open')) ?></span></td>
                <td><?= e($row['reason']) ?><div class="muted"><?= e(excerpt((string) ($row['detail'] ?? ''), 72)) ?></div></td>
                <td><?= e($row['actor_nickname']) ?><div class="muted">@<?= e($row['actor_username']) ?> · <?= e(substr((string) $row['created_at'], 0, 16)) ?></div></td>
                <td>
                  <form method="post" class="admin-inline-stack">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="update_governance_note_status">
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
            <?php if (!$governanceRows): ?><tr><td colspan="8" class="muted">当前还没有任何用户治理记录。</td></tr><?php endif; ?>
          </tbody>
        </table>
      </div>
    </section>

    <section id="users" class="glass panel-card admin-panel-card surface-section">
      <div class="section-kicker">用户管理</div>
      <div class="side-head"><h3>用户 / 角色管理</h3></div>
      <div class="notice subtle-notice">只有管理员可以调整用户角色与启停状态；版主进入后台时，这一整块不会显示。</div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead><tr><th>ID</th><th>用户</th><th>邮箱</th><th>角色</th><th>状态</th><th>内容量</th><th>风险档案</th><th>操作</th></tr></thead>
          <tbody>
            <?php foreach ($userRows as $row): ?>
              <tr>
                <td>#<?= (int) $row['id'] ?></td>
                <td><strong><?= e($row['nickname']) ?></strong><div class="muted">@<?= e($row['username']) ?></div></td>
                <td><?= e($row['email']) ?></td>
                <td><span class="tiny-badge"><?= e(role_label($row['role'] ?? 'member')) ?></span></td>
                <td><span class="tiny-badge <?= (int) $row['is_active'] === 1 ? 'badge-ok' : 'badge-danger' ?>"><?= (int) $row['is_active'] === 1 ? '启用中' : '已停用' ?></span></td>
                <td><?= (int) $row['post_count'] ?> 帖 / <?= (int) $row['comment_count'] ?> 评</td>
                <td>
                  <div class="chips" style="gap:6px;">
                    <span class="chip">总记录 <?= (int) ($row['governance_note_count'] ?? 0) ?></span>
                    <span class="chip">开放中 <?= (int) ($row['governance_open_count'] ?? 0) ?></span>
                    <span class="chip">高风险 <?= (int) ($row['governance_high_risk_count'] ?? 0) ?></span>
                  </div>
                  <form method="post" class="admin-inline-stack" style="margin-top:10px; align-items:flex-start;">
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                    <input type="hidden" name="action" value="add_governance_note">
                    <input type="hidden" name="user_id" value="<?= (int) $row['id'] ?>">
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
                    <button class="pill-btn" type="submit">记一条</button>
                  </form>
                </td>
                <td>
                  <div class="admin-inline-stack">
                    <form method="post" class="inline-form inline-select-form">
                      <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                      <input type="hidden" name="action" value="set_user_role">
                      <input type="hidden" name="user_id" value="<?= (int) $row['id'] ?>">
                      <select class="input slim-input" name="role">
                        <?php foreach (['member' => '成员', 'moderator' => '版主', 'admin' => '管理员'] as $roleValue => $roleName): ?>
                          <option value="<?= e($roleValue) ?>" <?= ($row['role'] ?? 'member') === $roleValue ? 'selected' : '' ?>><?= e($roleName) ?></option>
                        <?php endforeach; ?>
                      </select>
                      <button class="pill-btn solid" type="submit">设为</button>
                    </form>
                    <?php if ((int) $row['id'] === (int) $user['id']): ?>
                      <span class="muted">当前账号</span>
                    <?php else: ?>
                      <form method="post" class="inline-form">
                        <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
                        <input type="hidden" name="action" value="toggle_user_active">
                        <input type="hidden" name="user_id" value="<?= (int) $row['id'] ?>">
                        <input type="hidden" name="target_status" value="<?= (int) $row['is_active'] === 1 ? 0 : 1 ?>">
                        <button class="pill-btn <?= (int) $row['is_active'] === 1 ? 'danger' : 'solid' ?>" type="submit"><?= (int) $row['is_active'] === 1 ? '停用' : '启用' ?></button>
                      </form>
                    <?php endif; ?>
                  </div>
                </td>
              </tr>
            <?php endforeach; ?>
          </tbody>
        </table>
      </div>
    </section>
  <?php endif; ?>

  <?php if ($canManageStructure): ?>
    <div class="nebula-section-grid admin-grid-two">
      <section id="categories" class="glass panel-card admin-panel-card surface-section">
        <div class="section-kicker">分类管理</div>
        <div class="side-head"><h3>分类管理</h3></div>
        <div class="notice subtle-notice">删除分类时，如果下面还有版块，可直接选择目标分类迁移后再删；同时支持上移 / 下移快速调序。</div>
        <form class="admin-crud-form" method="post">
          <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
          <input type="hidden" name="action" value="create_category">
          <input class="input" name="name" placeholder="分类名称">
          <input class="input" name="slug" placeholder="slug，例如 strategy-hub">
          <input class="input" name="description" placeholder="分类描述">
          <input class="input" type="number" name="sort_order" value="0" placeholder="排序">
          <button class="pill-btn solid" type="submit">新增分类</button>
        </form>
        <div class="admin-list-stack">
          <?php foreach ($categoryRows as $row): ?>
            <form class="admin-list-card" method="post">
              <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
              <input type="hidden" name="category_id" value="<?= (int) $row['id'] ?>">
              <div class="admin-list-card-head"><strong>#<?= (int) $row['id'] ?> · <?= e($row['name']) ?></strong><span class="tiny-badge"><?= (int) $row['board_count'] ?> 个版块</span></div>
              <input class="input" name="name" value="<?= e($row['name']) ?>">
              <input class="input" name="slug" value="<?= e($row['slug']) ?>">
              <input class="input" name="description" value="<?= e($row['description']) ?>">
              <input class="input" type="number" name="sort_order" value="<?= (int) $row['sort_order'] ?>">
              <select class="input" name="target_category_id">
                <option value="0">删除时不迁移（仅空分类可直接删）</option>
                <?php foreach ($availableCategoryTargets as $target): ?>
                  <?php if ((int) $target['id'] === (int) $row['id']) { continue; } ?>
                  <option value="<?= (int) $target['id'] ?>">迁移版块到：<?= e($target['name']) ?></option>
                <?php endforeach; ?>
              </select>
              <div class="admin-action-stack">
                <button class="pill-btn" type="submit" name="action" value="move_category" onclick="this.form.direction.value='up'">上移</button>
                <button class="pill-btn" type="submit" name="action" value="move_category" onclick="this.form.direction.value='down'">下移</button>
                <input type="hidden" name="direction" value="up">
                <button class="pill-btn solid" type="submit" name="action" value="update_category">保存分类</button>
                <button class="pill-btn danger" type="submit" name="action" value="delete_category" onclick="return confirm('确认删除这个分类？若已选迁移目标，会先迁移版块再删除。');">删除 / 迁移删除</button>
              </div>
            </form>
          <?php endforeach; ?>
        </div>
      </section>

      <section id="boards" class="glass panel-card admin-panel-card surface-section">
        <div class="section-kicker">版块管理</div>
        <div class="side-head"><h3>版块管理</h3></div>
        <div class="notice subtle-notice">删除版块时，可把原帖整体迁移到其他版块；同分类内还支持上移 / 下移调序。</div>
        <form class="admin-crud-form" method="post">
          <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
          <input type="hidden" name="action" value="create_board">
          <select class="input" name="category_id">
            <?php foreach ($categoryRows as $category): ?>
              <option value="<?= (int) $category['id'] ?>"><?= e($category['name']) ?></option>
            <?php endforeach; ?>
          </select>
          <input class="input" name="name" placeholder="版块名称">
          <input class="input" name="slug" placeholder="slug，例如 pvp-lab">
          <input class="input" name="description" placeholder="版块描述">
          <input class="input" name="accent_color" placeholder="#23d3a2">
          <input class="input" type="number" name="sort_order" value="0" placeholder="排序">
          <button class="pill-btn solid" type="submit">新增版块</button>
        </form>
        <div class="admin-list-stack">
          <?php foreach ($boardRows as $row): ?>
            <form class="admin-list-card" method="post">
              <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>">
              <input type="hidden" name="board_id" value="<?= (int) $row['id'] ?>">
              <div class="admin-list-card-head"><strong>#<?= (int) $row['id'] ?> · <?= e($row['name']) ?></strong><span class="tiny-badge"><?= (int) $row['post_count'] ?> 帖</span></div>
              <select class="input" name="category_id">
                <?php foreach ($categoryRows as $category): ?>
                  <option value="<?= (int) $category['id'] ?>" <?= (int) $row['category_id'] === (int) $category['id'] ? 'selected' : '' ?>><?= e($category['name']) ?></option>
                <?php endforeach; ?>
              </select>
              <input class="input" name="name" value="<?= e($row['name']) ?>">
              <input class="input" name="slug" value="<?= e($row['slug']) ?>">
              <input class="input" name="description" value="<?= e($row['description']) ?>">
              <input class="input" name="accent_color" value="<?= e($row['accent_color']) ?>">
              <input class="input" type="number" name="sort_order" value="<?= (int) $row['sort_order'] ?>">
              <select class="input" name="target_board_id">
                <option value="0">删除时不迁移（仅空版块可直接删）</option>
                <?php foreach ($availableBoardTargets as $target): ?>
                  <?php if ((int) $target['id'] === (int) $row['id']) { continue; } ?>
                  <option value="<?= (int) $target['id'] ?>">迁移帖子到：<?= e($target['category_name']) ?> / <?= e($target['name']) ?></option>
                <?php endforeach; ?>
              </select>
              <div class="admin-action-stack">
                <button class="pill-btn" type="submit" name="action" value="move_board" onclick="this.form.direction.value='up'">上移</button>
                <button class="pill-btn" type="submit" name="action" value="move_board" onclick="this.form.direction.value='down'">下移</button>
                <input type="hidden" name="direction" value="up">
                <button class="pill-btn solid" type="submit" name="action" value="update_board">保存版块</button>
                <button class="pill-btn danger" type="submit" name="action" value="delete_board" onclick="return confirm('确认删除这个版块？若已选迁移目标，会先迁移帖子再删除。');">删除 / 迁移删除</button>
              </div>
            </form>
          <?php endforeach; ?>
        </div>
      </section>
    </div>
  <?php endif; ?>

  <section id="logs" class="glass panel-card admin-panel-card surface-section">
    <div class="section-kicker">操作日志</div>
    <div class="side-head admin-head-row"><h3>操作日志</h3><span class="muted">支持按动作、目标类型、操作者筛选，并做分页回看。</span></div>
    <form class="admin-filter-row admin-log-filter-row" method="get">
      <input type="hidden" name="post_id" value="<?= $postFilterId > 0 ? (int) $postFilterId : '' ?>">
      <input type="hidden" name="author_id" value="<?= $authorFilterId > 0 ? (int) $authorFilterId : '' ?>">
      <input type="hidden" name="post_title_keyword" value="<?= e($postTitleKeyword) ?>">
      <input type="hidden" name="author_keyword" value="<?= e($authorKeyword) ?>">
      <input type="hidden" name="content_keyword" value="<?= e($contentKeyword) ?>">
      <input type="hidden" name="comment_status" value="<?= e($commentStatusFilter) ?>">
      <select class="input admin-filter-input" name="log_action">
        <option value="">全部动作</option>
        <?php foreach ($logActionOptions as $actionType): ?>
          <option value="<?= e($actionType) ?>" <?= $logActionFilter === $actionType ? 'selected' : '' ?>><?= e($actionType) ?></option>
        <?php endforeach; ?>
      </select>
      <select class="input admin-filter-input" name="log_target_type">
        <option value="">全部对象</option>
        <?php foreach ($logTargetTypeOptions as $targetType): ?>
          <option value="<?= e($targetType) ?>" <?= $logTargetTypeFilter === $targetType ? 'selected' : '' ?>><?= e($targetType) ?></option>
        <?php endforeach; ?>
      </select>
      <select class="input admin-filter-input" name="log_actor_id">
        <option value="0">全部操作者</option>
        <?php foreach ($logActorOptions as $actor): ?>
          <option value="<?= (int) $actor['id'] ?>" <?= $logActorIdFilter === (int) $actor['id'] ? 'selected' : '' ?>><?= e($actor['nickname']) ?> @<?= e($actor['username']) ?></option>
        <?php endforeach; ?>
      </select>
      <button class="pill-btn solid" type="submit">筛选</button>
      <a class="pill-btn" href="<?= e(admin_url(['log_action' => null, 'log_target_type' => null, 'log_actor_id' => null, 'log_page' => null], '#logs')) ?>">清空</a>
    </form>
    <div class="admin-log-meta muted">共 <?= $logTotal ?> 条记录 · 第 <?= $logPage ?> / <?= $logTotalPages ?> 页</div>
    <div class="admin-table-wrap">
      <table class="admin-table compact-table">
        <thead><tr><th>时间</th><th>执行人</th><th>动作</th><th>对象</th><th>详情</th></tr></thead>
        <tbody>
          <?php foreach ($logRows as $row): ?>
            <tr>
              <td><?= e(substr($row['created_at'], 0, 16)) ?></td>
              <td><?= e($row['nickname']) ?><div class="muted">@<?= e($row['username']) ?> · #<?= (int) $row['actor_id'] ?></div></td>
              <td><span class="tiny-badge"><?= e($row['action_type']) ?></span></td>
              <td><?= e($row['target_type']) ?> #<?= (int) $row['target_id'] ?></td>
              <td><?= e($row['details']) ?></td>
            </tr>
          <?php endforeach; ?>
          <?php if (!$logRows): ?>
            <tr><td colspan="5" class="muted">当前筛选条件下没有操作日志。</td></tr>
          <?php endif; ?>
        </tbody>
      </table>
    </div>
    <?= admin_pagination([
      'post_id' => $postFilterId,
      'author_id' => $authorFilterId,
      'post_title_keyword' => $postTitleKeyword,
      'author_keyword' => $authorKeyword,
      'content_keyword' => $contentKeyword,
      'comment_status' => $commentStatusFilter,
      'post_page' => $postPage,
      'comment_page' => $commentPage,
      'log_action' => $logActionFilter,
      'log_target_type' => $logTargetTypeFilter,
      'log_actor_id' => $logActorIdFilter,
    ], 'log_page', $logPage, $logTotalPages, '#logs') ?>
  </section>
</main>
<?php render_footer(); ?>
