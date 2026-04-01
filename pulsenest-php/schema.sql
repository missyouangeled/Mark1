CREATE TABLE IF NOT EXISTS pulsenest_users (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(24) NOT NULL,
  nickname VARCHAR(60) NOT NULL,
  email VARCHAR(190) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  avatar_path VARCHAR(255) DEFAULT NULL,
  bio VARCHAR(280) DEFAULT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_pulsenest_users_username (username),
  UNIQUE KEY uniq_pulsenest_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS forum_categories (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(80) NOT NULL,
  slug VARCHAR(80) NOT NULL,
  description VARCHAR(255) DEFAULT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_forum_categories_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS forum_boards (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  category_id INT UNSIGNED NOT NULL,
  name VARCHAR(80) NOT NULL,
  slug VARCHAR(80) NOT NULL,
  description VARCHAR(255) DEFAULT NULL,
  accent_color VARCHAR(20) DEFAULT NULL,
  sort_order INT NOT NULL DEFAULT 0,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_forum_boards_slug (slug),
  KEY idx_forum_boards_category_id (category_id),
  CONSTRAINT fk_forum_boards_category FOREIGN KEY (category_id) REFERENCES forum_categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS posts (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT UNSIGNED NOT NULL,
  board_id INT UNSIGNED DEFAULT NULL,
  title VARCHAR(120) NOT NULL,
  content TEXT NOT NULL,
  image_path VARCHAR(255) DEFAULT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_posts_user_id (user_id),
  KEY idx_posts_board_id (board_id),
  CONSTRAINT fk_posts_user FOREIGN KEY (user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE,
  CONSTRAINT fk_posts_board FOREIGN KEY (board_id) REFERENCES forum_boards(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS comments (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  post_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  parent_id INT UNSIGNED DEFAULT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_comments_post_id (post_id),
  KEY idx_comments_user_id (user_id),
  KEY idx_comments_parent_id (parent_id),
  CONSTRAINT fk_comments_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
  CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE,
  CONSTRAINT fk_comments_parent FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS post_likes (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  post_id INT UNSIGNED NOT NULL,
  user_id INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_post_likes_post_user (post_id, user_id),
  KEY idx_post_likes_user_id (user_id),
  CONSTRAINT fk_post_likes_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
  CONSTRAINT fk_post_likes_user FOREIGN KEY (user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS notifications (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  recipient_user_id INT UNSIGNED NOT NULL,
  actor_user_id INT UNSIGNED NOT NULL,
  post_id INT UNSIGNED NOT NULL,
  comment_id INT UNSIGNED DEFAULT NULL,
  type VARCHAR(40) NOT NULL,
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_notifications_recipient_read (recipient_user_id, is_read),
  KEY idx_notifications_post_id (post_id),
  KEY idx_notifications_comment_id (comment_id),
  CONSTRAINT fk_notifications_recipient FOREIGN KEY (recipient_user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE,
  CONSTRAINT fk_notifications_actor FOREIGN KEY (actor_user_id) REFERENCES pulsenest_users(id) ON DELETE CASCADE,
  CONSTRAINT fk_notifications_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
  CONSTRAINT fk_notifications_comment FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS password_resets (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  email VARCHAR(190) NOT NULL,
  token_hash CHAR(64) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at DATETIME DEFAULT NULL,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uniq_password_resets_token_hash (token_hash),
  KEY idx_password_resets_email (email),
  KEY idx_password_resets_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO forum_categories (name, slug, description, sort_order)
VALUES
  ('星港大厅', 'starport', '社区总览、每日热聊和新人最容易进入的公共区。', 10),
  ('深空回路', 'deep-space', '更偏内容深聊、攻略拆解、世界观和评测。', 20)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  description = VALUES(description),
  sort_order = VALUES(sort_order);

INSERT INTO forum_boards (category_id, name, slug, description, accent_color, sort_order)
SELECT c.id, board_name, board_slug, board_description, accent_color, sort_order
FROM (
  SELECT 'starport' AS category_slug, '综合讨论' AS board_name, 'general' AS board_slug, '随时抛观点、晒近况、接住当天热帖。' AS board_description, '#23d3a2' AS accent_color, 10 AS sort_order
  UNION ALL
  SELECT 'starport', '新手报到', 'introductions', '第一次来 PulseNest，就从这里露个面。', '#77e7ff', 20
  UNION ALL
  SELECT 'deep-space', '攻略 / 评测', 'guides-reviews', '打法、体验、长文评测都丢来这里。', '#b06df0', 10
  UNION ALL
  SELECT 'deep-space', '截图 / 作品', 'screenshots-creations', '发图、晒搭配、丢创作，视觉内容集中展示。', '#ff8bc2', 20
) AS seeds
INNER JOIN forum_categories c ON c.slug = seeds.category_slug
ON DUPLICATE KEY UPDATE
  category_id = VALUES(category_id),
  name = VALUES(name),
  description = VALUES(description),
  accent_color = VALUES(accent_color),
  sort_order = VALUES(sort_order);
