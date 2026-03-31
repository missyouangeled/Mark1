<?php
/**
 * Plugin Name: Simple Frontend Auth
 * Description: Adds shortcode-based frontend login and registration forms for WordPress.
 * Version: 0.1.0
 * Author: 贾维斯
 * Requires at least: 6.4
 * Requires PHP: 8.0
 */

if (!defined('ABSPATH')) {
    exit;
}

final class Simple_Frontend_Auth {
    private const LOGIN_ACTION = 'sfa_login';
    private const REGISTER_ACTION = 'sfa_register';
    private const NOTICE_KEY = 'sfa_notice';
    private const LOGIN_PAGE_SLUG = 'login';
    private const REGISTER_PAGE_SLUG = 'register';
    private const MEMBER_CENTER_SLUG = 'member-center';

    public function __construct() {
        add_action('init', [$this, 'handle_form_submissions']);
        add_action('template_redirect', [$this, 'handle_page_access_rules']);
        add_action('wp_enqueue_scripts', [$this, 'enqueue_assets']);

        add_shortcode('sfa_login_form', [$this, 'render_login_shortcode']);
        add_shortcode('sfa_register_form', [$this, 'render_register_shortcode']);
        add_shortcode('sfa_auth_forms', [$this, 'render_combined_shortcode']);
        add_shortcode('sfa_member_center', [$this, 'render_member_center_shortcode']);
    }

    public function enqueue_assets(): void {
        wp_register_style(
            'simple-frontend-auth',
            plugin_dir_url(__FILE__) . 'assets/simple-frontend-auth.css',
            [],
            '0.1.0'
        );
    }

    public function handle_form_submissions(): void {
        $request_method = isset($_SERVER['REQUEST_METHOD']) ? strtoupper((string) $_SERVER['REQUEST_METHOD']) : 'GET';
        if ($request_method !== 'POST') {
            return;
        }

        $action = isset($_POST['sfa_action']) ? sanitize_text_field(wp_unslash($_POST['sfa_action'])) : '';

        if ($action === self::LOGIN_ACTION) {
            $this->handle_login();
            return;
        }

        if ($action === self::REGISTER_ACTION) {
            $this->handle_register();
        }
    }

    public function render_login_shortcode(array $atts = []): string {
        if (is_user_logged_in()) {
            return $this->render_logged_in_box();
        }

        wp_enqueue_style('simple-frontend-auth');

        $atts = shortcode_atts([
            'title' => '登录',
            'redirect' => '',
            'show_register_link' => 'false',
            'register_url' => '',
        ], $atts, 'sfa_login_form');

        return $this->wrap_card(
            esc_html($atts['title']),
            $this->render_notices('login') . $this->render_login_form($atts)
        );
    }

    public function render_register_shortcode(array $atts = []): string {
        if (is_user_logged_in()) {
            return $this->render_logged_in_box();
        }

        wp_enqueue_style('simple-frontend-auth');

        $atts = shortcode_atts([
            'title' => '注册',
            'redirect' => '',
            'auto_login' => 'true',
            'show_login_link' => 'false',
            'login_url' => '',
        ], $atts, 'sfa_register_form');

        return $this->wrap_card(
            esc_html($atts['title']),
            $this->render_notices('register') . $this->render_register_form($atts)
        );
    }

    public function render_combined_shortcode(array $atts = []): string {
        if (is_user_logged_in()) {
            return $this->render_logged_in_box();
        }

        wp_enqueue_style('simple-frontend-auth');

        $atts = shortcode_atts([
            'login_title' => '登录',
            'register_title' => '注册',
            'login_redirect' => '',
            'register_redirect' => '',
            'auto_login' => 'true',
        ], $atts, 'sfa_auth_forms');

        $login = $this->wrap_card(
            esc_html($atts['login_title']),
            $this->render_notices('login') . $this->render_login_form([
                'redirect' => $atts['login_redirect'],
                'show_register_link' => 'false',
                'register_url' => '',
            ])
        );

        $register = $this->wrap_card(
            esc_html($atts['register_title']),
            $this->render_notices('register') . $this->render_register_form([
                'redirect' => $atts['register_redirect'],
                'auto_login' => $atts['auto_login'],
                'show_login_link' => 'false',
                'login_url' => '',
            ])
        );

        return '<div class="sfa-grid">' . $login . $register . '</div>';
    }

    private function render_login_form(array $atts): string {
        $redirect = $this->normalize_redirect_target($atts['redirect'] !== '' ? $atts['redirect'] : $this->get_member_center_url());
        $register_link = '';

        if ($this->as_bool($atts['show_register_link']) && !empty($atts['register_url'])) {
            $register_link = '<p class="sfa-helper">还没有账号？<a href="' . esc_url($this->normalize_frontend_url($atts['register_url'])) . '">去注册</a></p>';
        }

        ob_start();
        ?>
        <form class="sfa-form" method="post">
            <?php wp_nonce_field(self::LOGIN_ACTION, 'sfa_nonce'); ?>
            <input type="hidden" name="sfa_action" value="<?php echo esc_attr(self::LOGIN_ACTION); ?>">
            <input type="hidden" name="sfa_context" value="login">
            <input type="hidden" name="sfa_redirect" value="<?php echo esc_url($redirect); ?>">

            <label class="sfa-label" for="sfa_login_username">用户名或邮箱</label>
            <input class="sfa-input" id="sfa_login_username" name="log" type="text" required>

            <label class="sfa-label" for="sfa_login_password">密码</label>
            <input class="sfa-input" id="sfa_login_password" name="pwd" type="password" required>

            <label class="sfa-checkbox">
                <input type="checkbox" name="rememberme" value="forever">
                <span>记住我</span>
            </label>

            <button class="sfa-button" type="submit">登录</button>
            <?php echo $register_link; ?>
        </form>
        <?php
        return (string) ob_get_clean();
    }

    private function render_register_form(array $atts): string {
        $redirect = $this->normalize_redirect_target($atts['redirect'] !== '' ? $atts['redirect'] : $this->get_member_center_url());
        $login_link = '';

        if ($this->as_bool($atts['show_login_link']) && !empty($atts['login_url'])) {
            $login_link = '<p class="sfa-helper">已经有账号？<a href="' . esc_url($this->normalize_frontend_url($atts['login_url'])) . '">去登录</a></p>';
        }

        ob_start();
        ?>
        <form class="sfa-form" method="post">
            <?php wp_nonce_field(self::REGISTER_ACTION, 'sfa_nonce'); ?>
            <input type="hidden" name="sfa_action" value="<?php echo esc_attr(self::REGISTER_ACTION); ?>">
            <input type="hidden" name="sfa_context" value="register">
            <input type="hidden" name="sfa_redirect" value="<?php echo esc_url($redirect); ?>">
            <input type="hidden" name="sfa_auto_login" value="<?php echo $this->as_bool($atts['auto_login']) ? '1' : '0'; ?>">

            <label class="sfa-label" for="sfa_register_username">用户名</label>
            <input class="sfa-input" id="sfa_register_username" name="user_login" type="text" required>

            <label class="sfa-label" for="sfa_register_email">邮箱</label>
            <input class="sfa-input" id="sfa_register_email" name="user_email" type="email" required>

            <label class="sfa-label" for="sfa_register_password">密码</label>
            <input class="sfa-input" id="sfa_register_password" name="user_pass" type="password" minlength="6" required>

            <label class="sfa-label" for="sfa_register_password_confirm">确认密码</label>
            <input class="sfa-input" id="sfa_register_password_confirm" name="user_pass_confirm" type="password" minlength="6" required>

            <button class="sfa-button" type="submit">注册</button>
            <?php echo $login_link; ?>
        </form>
        <?php
        return (string) ob_get_clean();
    }

    public function handle_page_access_rules(): void {
        if (is_admin()) {
            return;
        }

        if (is_page(self::MEMBER_CENTER_SLUG) && !is_user_logged_in()) {
            $message = '请先登录；如果还没有账号，请先完成注册。';
            $target = add_query_arg(
                'redirect_to',
                rawurlencode($this->get_member_center_url()),
                $this->get_login_page_url()
            );
            $this->redirect_with_notice('error', $message, 'login', $target);
        }

        if (is_user_logged_in() && (is_page(self::LOGIN_PAGE_SLUG) || is_page(self::REGISTER_PAGE_SLUG))) {
            $message = '你已经登录了，已为你跳转到会员中心。';
            $this->redirect_with_notice('success', $message, 'member-center', $this->get_member_center_url());
        }
    }

    private function handle_login(): void {
        if (!$this->valid_nonce(self::LOGIN_ACTION)) {
            $this->redirect_with_notice('error', '登录请求已失效，请刷新页面后重试。', 'login');
        }

        $username = isset($_POST['log']) ? sanitize_text_field(wp_unslash($_POST['log'])) : '';
        $password = isset($_POST['pwd']) ? (string) wp_unslash($_POST['pwd']) : '';
        $remember = !empty($_POST['rememberme']);

        $credentials = [
            'user_login' => $username,
            'user_password' => $password,
            'remember' => $remember,
        ];

        $user = wp_signon($credentials, is_ssl());
        if (is_wp_error($user)) {
            $this->redirect_with_notice('error', $user->get_error_message(), 'login');
        }

        wp_set_current_user($user->ID);
        $this->redirect_with_notice('success', '登录成功，正在跳转。', 'login', $this->resolve_redirect_url());
    }

    private function handle_register(): void {
        if (!$this->valid_nonce(self::REGISTER_ACTION)) {
            $this->redirect_with_notice('error', '注册请求已失效，请刷新页面后重试。', 'register');
        }

        $username = isset($_POST['user_login']) ? sanitize_user(wp_unslash($_POST['user_login'])) : '';
        $email = isset($_POST['user_email']) ? sanitize_email(wp_unslash($_POST['user_email'])) : '';
        $password = isset($_POST['user_pass']) ? (string) wp_unslash($_POST['user_pass']) : '';
        $password_confirm = isset($_POST['user_pass_confirm']) ? (string) wp_unslash($_POST['user_pass_confirm']) : '';
        $auto_login = !empty($_POST['sfa_auto_login']);

        if ($username === '' || $email === '' || $password === '') {
            $this->redirect_with_notice('error', '请完整填写注册信息。', 'register');
        }

        if (!validate_username($username)) {
            $this->redirect_with_notice('error', '用户名格式不合法。', 'register');
        }

        if (username_exists($username)) {
            $this->redirect_with_notice('error', '用户名已存在，请更换一个用户名。', 'register');
        }

        if (!is_email($email)) {
            $this->redirect_with_notice('error', '邮箱格式不正确。', 'register');
        }

        if (email_exists($email)) {
            $this->redirect_with_notice('error', '该邮箱已经注册了，请更换邮箱或直接登录。', 'register');
        }

        if ($password !== $password_confirm) {
            $this->redirect_with_notice('error', '两次输入的密码不一致。', 'register');
        }

        if (strlen($password) < 6) {
            $this->redirect_with_notice('error', '密码至少需要 6 位。', 'register');
        }

        $user_id = wp_create_user($username, $password, $email);
        if (is_wp_error($user_id)) {
            $this->redirect_with_notice('error', $user_id->get_error_message(), 'register');
        }

        if ($auto_login) {
            wp_set_auth_cookie($user_id, true);
            wp_set_current_user($user_id);
            $this->redirect_with_notice('success', '注册成功，已自动登录。', 'register', $this->resolve_redirect_url());
        }

        $this->redirect_with_notice('success', '注册成功，请登录。', 'register', $this->resolve_redirect_url());
    }

    public function render_member_center_shortcode(array $atts = []): string {
        wp_enqueue_style('simple-frontend-auth');

        if (!is_user_logged_in()) {
            $message = '请先登录后再查看会员中心。';
            $target = add_query_arg(
                'redirect_to',
                rawurlencode($this->get_member_center_url()),
                $this->get_login_page_url()
            );
            $this->redirect_with_notice('error', $message, 'login', $target);
        }

        return $this->render_logged_in_box(true);
    }

    private function render_logged_in_box(bool $include_member_links = false): string {
        $current_user = wp_get_current_user();
        $logout_url = wp_logout_url($this->get_login_page_url());
        $content = '<div class="sfa-logged-in">' .
            $this->render_notices('member-center') .
            '<p>你已登录，当前用户：<strong>' . esc_html($current_user->display_name ?: $current_user->user_login) . '</strong></p>' .
            '<p>用户名：' . esc_html($current_user->user_login) . '</p>' .
            '<p>邮箱：' . esc_html($current_user->user_email) . '</p>';

        if ($include_member_links) {
            $content .= '<p>这里是会员中心，你现在可以继续扩展资料页、订单页、权限内容。</p>';
        }

        $content .= '<p><a class="sfa-button sfa-button-secondary" href="' . esc_url($logout_url) . '">退出登录</a></p>' .
            '</div>';

        return $this->wrap_card('账户状态', $content);
    }

    private function render_notices(?string $context = null): string {
        if (empty($_GET[self::NOTICE_KEY])) {
            return '';
        }

        $payload = json_decode(base64_decode(sanitize_text_field(wp_unslash($_GET[self::NOTICE_KEY]))), true);
        if (!is_array($payload)) {
            return '';
        }

        if ($context !== null && ($payload['context'] ?? '') !== $context) {
            return '';
        }

        $type = ($payload['type'] ?? 'success') === 'error' ? 'error' : 'success';
        $message = isset($payload['message']) ? wp_kses_post($payload['message']) : '';
        if ($message === '') {
            return '';
        }

        return '<div class="sfa-notice sfa-notice-' . esc_attr($type) . '">' . $message . '</div>';
    }

    private function redirect_with_notice(string $type, string $message, string $context, ?string $redirect = null): void {
        $payload = [
            'type' => $type,
            'message' => $message,
            'context' => $context,
        ];

        $target = $redirect ?: wp_get_referer() ?: home_url('/');
        $target = add_query_arg(
            self::NOTICE_KEY,
            rawurlencode(base64_encode(wp_json_encode($payload))),
            $target
        );

        wp_safe_redirect($target);
        exit;
    }

    private function resolve_redirect_url(): string {
        $posted_redirect = isset($_POST['sfa_redirect']) ? wp_unslash($_POST['sfa_redirect']) : '';
        if (is_string($posted_redirect) && $posted_redirect !== '') {
            return $this->normalize_redirect_target($posted_redirect);
        }

        $query_redirect = isset($_GET['redirect_to']) ? wp_unslash($_GET['redirect_to']) : '';
        if (is_string($query_redirect) && $query_redirect !== '') {
            return $this->normalize_redirect_target($query_redirect);
        }

        return $this->get_member_center_url();
    }

    private function get_login_page_url(): string {
        return $this->get_page_url_by_slug(self::LOGIN_PAGE_SLUG);
    }

    private function get_register_page_url(): string {
        return $this->get_page_url_by_slug(self::REGISTER_PAGE_SLUG);
    }

    private function get_member_center_url(): string {
        return $this->get_page_url_by_slug(self::MEMBER_CENTER_SLUG);
    }

    private function get_page_url_by_slug(string $slug): string {
        $page = get_page_by_path($slug, OBJECT, 'page');
        if ($page instanceof WP_Post) {
            $url = get_permalink($page);
            if (is_string($url) && $url !== '') {
                return $url;
            }
        }

        return home_url('/');
    }

    private function normalize_frontend_url(string $value): string {
        $value = trim($value);
        if ($value === '') {
            return home_url('/');
        }

        if (filter_var($value, FILTER_VALIDATE_URL)) {
            return esc_url_raw($value);
        }

        $slug = trim((string) parse_url($value, PHP_URL_PATH), '/');
        if ($slug === self::LOGIN_PAGE_SLUG) {
            return $this->get_login_page_url();
        }
        if ($slug === self::REGISTER_PAGE_SLUG) {
            return $this->get_register_page_url();
        }
        if ($slug === self::MEMBER_CENTER_SLUG) {
            return $this->get_member_center_url();
        }

        $page = get_page_by_path($slug, OBJECT, 'page');
        if ($page instanceof WP_Post) {
            $url = get_permalink($page);
            if (is_string($url) && $url !== '') {
                return $url;
            }
        }

        return home_url('/' . ltrim($value, '/'));
    }

    private function normalize_redirect_target(string $value): string {
        $url = $this->normalize_frontend_url($value);
        return wp_validate_redirect($url, $this->get_member_center_url());
    }

    private function valid_nonce(string $action): bool {
        $nonce = isset($_POST['sfa_nonce']) ? sanitize_text_field(wp_unslash($_POST['sfa_nonce'])) : '';
        return $nonce !== '' && wp_verify_nonce($nonce, $action) === 1;
    }

    private function wrap_card(string $title, string $content): string {
        return '<section class="sfa-card"><h3 class="sfa-title">' . esc_html($title) . '</h3>' . $content . '</section>';
    }

    private function as_bool(string $value): bool {
        return in_array(strtolower($value), ['1', 'true', 'yes', 'on'], true);
    }
}

new Simple_Frontend_Auth();
