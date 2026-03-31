<?php
$_SERVER['HTTP_HOST'] = '127.0.0.1';
$_SERVER['REQUEST_METHOD'] = 'GET';
$_SERVER['REQUEST_URI'] = '/wordpress/wp-admin/';
require '/var/www/html/wordpress/wp-load.php';
AsgarosForumContent::initialize_taxonomy();

global $wpdb;
$taxonomy = 'asgarosforum-category';
$forums_table = $wpdb->prefix . 'forum_forums';
$topics_table = $wpdb->prefix . 'forum_topics';
$posts_table = $wpdb->prefix . 'forum_posts';

function ntf_ensure_term(string $name, int $order): int {
    $taxonomy = 'asgarosforum-category';
    $existing = term_exists($name, $taxonomy);
    if ($existing && is_array($existing)) {
        $term_id = (int) $existing['term_id'];
    } else {
        $created = wp_insert_term($name, $taxonomy);
        if (is_wp_error($created)) {
            throw new RuntimeException($created->get_error_message());
        }
        $term_id = (int) $created['term_id'];
    }

    update_term_meta($term_id, 'order', $order);
    update_term_meta($term_id, 'category_access', 'everyone');
    return $term_id;
}

$categories = [
    [
        'name' => '社区广场',
        'order' => 1,
        'forums' => [
            [101, '新手报到', '第一次来这里？先打个招呼，认识一下大家。', 'fas fa-hand-wave', 'introductions'],
            [102, '综合讨论', '日常聊天、观点交流、轻松讨论都放这里。', 'fas fa-comments', 'general-discussion'],
            [103, '问题求助', '遇到问题就发帖，其他成员可以一起帮忙。', 'fas fa-circle-question', 'help-support'],
        ],
    ],
    [
        'name' => '游戏交流',
        'order' => 2,
        'forums' => [
            [201, '游戏推荐', '聊聊最近值得玩的游戏和新发现。', 'fas fa-gamepad', 'game-recommendations'],
            [202, '版本更新', '记录更新内容、活动信息和体验变化。', 'fas fa-bolt', 'update-notes'],
            [203, '攻略讨论', '分享打法、阵容、思路和通关经验。', 'fas fa-compass', 'guides'],
        ],
    ],
    [
        'name' => '创作分享',
        'order' => 3,
        'forums' => [
            [301, '截图与二创', '晒截图、同人、壁纸、整活内容。', 'fas fa-image', 'fan-creations'],
            [302, '建议反馈', '提建议、提改进意见、聊产品体验。', 'fas fa-lightbulb', 'feedback'],
        ],
    ],
];

$term_map = [];
foreach ($categories as $category) {
    $term_map[$category['name']] = ntf_ensure_term($category['name'], $category['order']);
}

$existing_forums = array_map('intval', $wpdb->get_col("SELECT id FROM {$forums_table}"));
foreach ($categories as $category) {
    $term_id = $term_map[$category['name']];
    foreach ($category['forums'] as $index => $forum) {
        [$id, $name, $description, $icon, $slug] = $forum;
        $sort = $index + 1;
        $payload = [
            'name' => $name,
            'parent_id' => $term_id,
            'parent_forum' => 0,
            'description' => $description,
            'icon' => $icon,
            'sort' => $sort,
            'forum_status' => 'normal',
            'slug' => $slug,
        ];

        if (in_array($id, $existing_forums, true)) {
            $wpdb->update($forums_table, $payload, ['id' => $id]);
        } else {
            $payload['id'] = $id;
            $wpdb->insert($forums_table, $payload);
        }
    }
}

$seed = [
    [101, 3, '大家好，我是新来的，来报个到', 18, ['大家好，我刚注册进来，平时主要想看看论坛里的讨论，也想认识一些有共同兴趣的人。以后请多关照。', '欢迎加入，先随便逛逛，有问题也可以直接发到问题求助版块。']],
    [102, 1, '你希望一个社区论坛最先给你的感觉是什么？', 26, ['如果你第一次进入一个论坛，你最在意的是内容质量、界面好看、回复速度，还是社区氛围？欢迎随便聊聊。', '我最在意氛围，愿意认真回复人的社区会让人更想留下来。']],
    [103, 3, '第一次发帖不知道应该写在哪个版块，怎么办？', 14, ['如果我不太确定自己的问题该发到哪里，应该先发综合讨论，还是直接发问题求助？', '拿不准就先发问题求助也可以，后面管理员可以再帮你整理。']],
    [201, 1, '最近你最想推荐的一款游戏是什么？', 33, ['如果只能推荐一款最近真的玩得很上头的游戏，你会推荐什么？', '我会更看重节奏舒服、能长期玩的那种。']],
    [202, 1, '版本更新之后你最先会关注什么？', 21, ['每次版本更新，你第一眼最在意的是新内容、平衡调整，还是活动奖励？', '我一般先看优化和 bug 修复，这会影响继续玩下去的心情。']],
    [203, 3, '有没有适合新手看的入门攻略整理？', 17, ['刚来的新玩家一般最需要的是哪类攻略？阵容、资源规划还是地图探索？', '如果能有一个置顶的新手导航帖会很方便。']],
    [301, 3, '来晒一下你最近最满意的一张截图', 12, ['你最近有没有什么很喜欢的游戏截图、场景图或者角色图？可以发上来一起看看。', '有时候社区里最先把氛围做起来的，反而是这些轻内容。']],
    [302, 1, '你最希望论坛下一步先优化什么？', 19, ['如果继续做这个社区，你最希望先优化的是排版、功能、通知机制还是内容组织？', '我会优先想办法让新用户进来以后更容易发第一帖。']],
];

foreach ($seed as $idx => $item) {
    [$forum_id, $author_id, $title, $views, $posts] = $item;
    $exists = $wpdb->get_var($wpdb->prepare("SELECT id FROM {$topics_table} WHERE name = %s LIMIT 1", $title));
    if ($exists) {
        continue;
    }

    $wpdb->insert($topics_table, [
        'parent_id' => $forum_id,
        'author_id' => $author_id,
        'views' => $views,
        'name' => $title,
        'sticky' => ($idx === 0 ? 1 : 0),
        'closed' => 0,
        'approved' => 1,
        'slug' => sanitize_title($title),
    ]);

    $topic_id = (int) $wpdb->insert_id;
    foreach ($posts as $pidx => $text) {
        $author = $pidx % 2 === 0 ? $author_id : 1;
        $post_time = date('Y-m-d H:i:s', strtotime(current_time('mysql')) - (($idx * 2 + $pidx + 1) * 3600));
        $wpdb->insert($posts_table, [
            'text' => $text,
            'parent_id' => $topic_id,
            'forum_id' => $forum_id,
            'date' => $post_time,
            'date_edit' => '1000-01-01 00:00:00',
            'author_id' => $author,
            'author_edit' => 0,
            'uploads' => '',
        ]);
    }
}

echo 'categories=' . count(get_terms(['taxonomy' => $taxonomy, 'hide_empty' => false])) . PHP_EOL;
echo 'forums=' . $wpdb->get_var("SELECT COUNT(*) FROM {$forums_table}") . PHP_EOL;
echo 'topics=' . $wpdb->get_var("SELECT COUNT(*) FROM {$topics_table}") . PHP_EOL;
