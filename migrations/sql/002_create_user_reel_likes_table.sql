-- Create user_reel_likes table to track which users like which reels
-- This table is used for recommendation algorithms
CREATE TABLE IF NOT EXISTS `user_reel_likes` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `reel_id` INT NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (`id`),
    INDEX `idx_user_reel_likes_user_id` (`user_id`),
    INDEX `idx_user_reel_likes_reel_id` (`reel_id`),
    
    CONSTRAINT `fk_user_reel_likes_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_user_reel_likes_reel` FOREIGN KEY (`reel_id`) REFERENCES `reels` (`reel_id`) ON DELETE CASCADE,
    CONSTRAINT `uq_user_reel_like` UNIQUE (`user_id`, `reel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

