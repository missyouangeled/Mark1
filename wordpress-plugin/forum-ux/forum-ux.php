<?php
/**
 * Plugin Name: Forum UX Bridge
 * Description: Connects Asgaros Forum with custom login/register/member-center UX and adds light forum styling.
 * Version: 0.1.0
 * Author: 贾维斯
 * Requires at least: 6.4
 * Requires PHP: 8.0
 */

if (!defined('ABSPATH')) {
    exit;
}

final class Forum_UX_Bridge {
    public function __construct() {
        add_action('wp_enqueue_scripts', [$this, 'enqueue_assets'], 30);
        add_filter('body_class', [$this, 'add_body_classes']);
        add_filter('gettext', [$this, 'translate_forum_strings'], 20, 3);
    }

    public function enqueue_assets(): void {
        if (!is_page('forum') && !is_front_page()) {
            return;
        }

        wp_enqueue_style(
            'forum-ux-bridge',
            plugin_dir_url(__FILE__) . 'assets/forum-ux.css',
            [],
            '0.1.0'
        );
    }

    public function add_body_classes(array $classes): array {
        if (is_page('forum') || is_front_page()) {
            $classes[] = 'forum-ux-active';
        }

        return $classes;
    }

    public function translate_forum_strings(string $translated, string $text, string $domain): string {
        if ($domain !== 'asgaros-forum') {
            return $translated;
        }

        $map = [
            'Forum' => '论坛',
            'Members' => '成员',
            'Activity' => '动态',
            'Login' => '登录',
            'Register' => '注册',
            'Search ...' => '搜索帖子...',
            'Please Login or Register to create posts and topics.' => '游客可以浏览论坛内容；登录或注册后才能发帖和回复。',
            'Please ' => '请',
            ' to create posts and topics.' => '后发帖和回复。',
            'Last post' => '最后回复',
            'No topics yet!' => '还没有帖子',
            'New posts' => '新帖子',
            'Nothing new' => '暂无新内容',
            'Mark All Read' => '全部标记为已读',
            'Show Unread Topics' => '查看未读主题',
            'Statistics' => '论坛统计',
            'Topics' => '主题',
            'Posts' => '回复',
            'Views' => '浏览',
            'Users' => '用户',
            'Online' => '在线',
            'Newest Member:' => '最新成员：',
            'Currently Online:' => '当前在线：',
            'Guests' => '位游客',
            'Guest' => '位游客',
        ];

        return $map[$text] ?? $translated;
    }
}

new Forum_UX_Bridge();
