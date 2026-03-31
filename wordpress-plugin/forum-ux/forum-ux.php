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
}

new Forum_UX_Bridge();
