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
        add_action('wp_head', [$this, 'inject_brand_assets'], 5);
        add_filter('body_class', [$this, 'add_body_classes']);
        add_filter('gettext', [$this, 'translate_forum_strings'], 20, 3);
        add_filter('the_content', [$this, 'inject_forum_hero'], 8);
    }

    public function enqueue_assets(): void {
        if (!is_page('forum') && !is_front_page()) {
            return;
        }

        wp_enqueue_style(
            'forum-ux-bridge',
            plugin_dir_url(__FILE__) . 'assets/forum-ux.css',
            [],
            '0.1.1'
        );
    }

    public function add_body_classes(array $classes): array {
        if (is_page('forum') || is_front_page()) {
            $classes[] = 'forum-ux-active';
        }

        return $classes;
    }

    public function inject_brand_assets(): void {
        $brand_url = home_url('/branding/night-talk-mark.svg');
        echo '<link rel="icon" type="image/svg+xml" href="' . esc_url($brand_url) . '">';
    }

    public function inject_forum_hero(string $content): string {
        if (!(is_page('forum') || is_front_page()) || !in_the_loop() || !is_main_query()) {
            return $content;
        }

        $hero = implode('', [
            '<section class="forum-hero-card">',
            '<div class="forum-hero-copy">',
            '<div class="forum-brand-row"><img class="forum-brand-mark" src="/wordpress/branding/night-talk-mark.svg" alt="夜谈论坛标志"><span class="forum-hero-kicker">夜谈论坛</span></div>',
            '<h2>公开浏览，登录后即可参与讨论</h2>',
            '<p>这里适合发起交流、提问求助、结识同好。游客可以先看内容，注册登录后再发帖和回复，逻辑更清爽，也更适合长期运营。</p>',
            '<div class="forum-hero-actions">',
            '<a class="forum-hero-button forum-hero-button-primary" href="/wordpress/index.php/register/">立即注册</a>',
            '<a class="forum-hero-button forum-hero-button-secondary" href="/wordpress/index.php/login/">已有账号，去登录</a>',
            '</div>',
            '</div>',
            '<div class="forum-hero-side">',
            '<div class="forum-hero-stat"><strong>3</strong><span>公开版块</span></div>',
            '<div class="forum-hero-stat"><strong>游客可看</strong><span>未登录也能浏览内容</span></div>',
            '<div class="forum-hero-stat"><strong>注册后参与</strong><span>发帖、回复、互动一步到位</span></div>',
            '</div>',
            '</section>'
        ]);

        $footer = implode('', [
            '<section class="forum-home-footer">',
            '<div class="forum-home-footer-grid">',
            '<div class="forum-home-footer-card">',
            '<h3>社区说明</h3>',
            '<p>这是一个面向公开浏览的讨论社区。游客可以先了解内容与氛围，注册登录后再发帖、回复、参与互动。</p>',
            '</div>',
            '<div class="forum-home-footer-card">',
            '<h3>参与规则</h3>',
            '<ul><li>先搜索，再提问</li><li>标题尽量明确</li><li>保持友善交流</li></ul>',
            '<p><a href="/wordpress/index.php/community-rules/">查看完整社区规则</a></p>',
            '</div>',
            '<div class="forum-home-footer-card">',
            '<h3>快速入口</h3>',
            '<p><a href="/wordpress/index.php/register/">注册账号</a><br><a href="/wordpress/index.php/login/">登录论坛</a><br><a href="/wordpress/index.php/member-center/">会员中心</a><br><a href="/wordpress/index.php/community-announcements/">社区公告</a></p>',
            '</div>',
            '</div>',
            '</section>'
        ]);

        return $hero . $content . $footer;
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
            'Last post:' => '最后回复：',
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
            'Menu' => '菜单',
            'New Topic' => '发布新主题',
            'Subject:' => '标题：',
            'Cancel' => '取消',
            'Submit' => '提交',
            'By' => '作者',
            'Replies' => '回复',
            'Reply' => '回复',
            'Views' => '浏览',
            'Topic' => '主题',
            'Edit Post' => '编辑回复',
            'New Reply' => '发表回复',
            'Search' => '搜索',
        ];

        return $map[$text] ?? $translated;
    }
}

new Forum_UX_Bridge();
