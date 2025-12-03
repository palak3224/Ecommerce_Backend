-- ============================================================================
-- Reels System - Complete Migration (Consolidated)
-- ============================================================================
-- This file contains ALL migrations for the Reels module including:
-- - Reels table
-- - User-reel interactions (likes, views, shares)
-- - Merchant follow system
-- - Category preferences for recommendations
-- - All performance indexes
-- - Full-text search index
--
-- Run this file to set up the complete reels system:
-- mysql -u root -p ecommerce_db < migrations/sql/001_create_reels_system_complete.sql
-- ============================================================================

-- ============================================================================
-- PART 1: CREATE ALL TABLES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Create reels table
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `reels` (
    `reel_id` INT NOT NULL AUTO_INCREMENT,
    `merchant_id` INT NOT NULL,
    `product_id` INT NOT NULL,
    
    -- Video storage
    `video_url` VARCHAR(512) NOT NULL,
    `video_public_id` VARCHAR(255) NULL,
    `thumbnail_url` VARCHAR(512) NULL,
    `thumbnail_public_id` VARCHAR(255) NULL,
    
    -- Metadata
    `description` TEXT NOT NULL,
    `duration_seconds` INT NULL,
    `file_size_bytes` BIGINT NULL,
    `video_format` VARCHAR(10) NULL,
    `resolution` VARCHAR(20) NULL,
    
    -- Stats
    `views_count` INT NOT NULL DEFAULT 0,
    `likes_count` INT NOT NULL DEFAULT 0,
    `shares_count` INT NOT NULL DEFAULT 0,
    
    -- Status
    `is_active` BOOLEAN NOT NULL DEFAULT 1,
    `approval_status` VARCHAR(20) NOT NULL DEFAULT 'approved',
    `approved_at` DATETIME NULL,
    `approved_by` INT NULL,
    `rejection_reason` VARCHAR(255) NULL,
    
    -- Timestamps
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted_at` DATETIME NULL,
    
    PRIMARY KEY (`reel_id`),
    INDEX `idx_reels_merchant_id` (`merchant_id`),
    INDEX `idx_reels_product_id` (`product_id`),
    INDEX `idx_reels_is_active` (`is_active`),
    INDEX `idx_reels_approval_status` (`approval_status`),
    INDEX `idx_reels_created_at` (`created_at`),
    INDEX `idx_reels_deleted_at` (`deleted_at`),
    
    CONSTRAINT `fk_reels_merchant` FOREIGN KEY (`merchant_id`) REFERENCES `merchant_profiles` (`id`),
    CONSTRAINT `fk_reels_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`),
    CONSTRAINT `fk_reels_approved_by` FOREIGN KEY (`approved_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2. Create user_reel_likes table
-- Purpose: Track which users like which reels for recommendation algorithms
-- ----------------------------------------------------------------------------
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

-- ----------------------------------------------------------------------------
-- 3. Create user_reel_views table
-- Purpose: Track which users viewed which reels for recommendation system
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_reel_views` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `reel_id` INT NOT NULL,
    `viewed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `view_duration` INT NULL COMMENT 'Duration in seconds (optional)',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (`id`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_reel_id` (`reel_id`),
    INDEX `idx_viewed_at` (`viewed_at`),
    
    CONSTRAINT `fk_user_reel_views_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_user_reel_views_reel` FOREIGN KEY (`reel_id`) REFERENCES `reels` (`reel_id`) ON DELETE CASCADE,
    CONSTRAINT `uq_user_reel_view` UNIQUE (`user_id`, `reel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 4. Create user_reel_shares table
-- Purpose: Track which users share which reels for analytics
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_reel_shares` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `reel_id` INT NOT NULL,
    `shared_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (`id`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_reel_id` (`reel_id`),
    INDEX `idx_shared_at` (`shared_at` DESC),
    
    CONSTRAINT `fk_user_reel_shares_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_user_reel_shares_reel` FOREIGN KEY (`reel_id`) REFERENCES `reels` (`reel_id`) ON DELETE CASCADE,
    CONSTRAINT `uq_user_reel_share` UNIQUE (`user_id`, `reel_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 5. Create user_merchant_follows table
-- Purpose: Track which merchants users follow for personalized feed
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_merchant_follows` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `merchant_id` INT NOT NULL,
    `followed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (`id`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_merchant_id` (`merchant_id`),
    INDEX `idx_followed_at` (`followed_at`),
    
    CONSTRAINT `fk_user_merchant_follows_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_user_merchant_follows_merchant` FOREIGN KEY (`merchant_id`) REFERENCES `merchant_profiles` (`id`) ON DELETE CASCADE,
    CONSTRAINT `uq_user_merchant_follow` UNIQUE (`user_id`, `merchant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 6. Create user_category_preferences table
-- Purpose: Store calculated category preferences for faster recommendation queries
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `user_category_preferences` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `category_id` INT NOT NULL,
    `preference_score` DECIMAL(5,4) NOT NULL DEFAULT 0.0000 COMMENT 'Score 0.0000 to 1.0000',
    `interaction_count` INT NOT NULL DEFAULT 0 COMMENT 'Total interactions in this category',
    `last_interaction_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    PRIMARY KEY (`id`),
    INDEX `idx_user_id` (`user_id`),
    INDEX `idx_category_id` (`category_id`),
    INDEX `idx_preference_score` (`preference_score` DESC),
    INDEX `idx_last_interaction` (`last_interaction_at` DESC),
    
    CONSTRAINT `fk_user_category_preferences_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_user_category_preferences_category` FOREIGN KEY (`category_id`) REFERENCES `categories` (`category_id`) ON DELETE CASCADE,
    CONSTRAINT `uq_user_category_pref` UNIQUE (`user_id`, `category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- PART 2: ADD PERFORMANCE INDEXES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 7. Composite index for trending queries
-- Purpose: Optimize queries for trending algorithm
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS `idx_reels_trending` 
ON `reels`(`created_at` DESC, `views_count` DESC, `likes_count` DESC, `shares_count` DESC);

-- ----------------------------------------------------------------------------
-- 8. Index for merchant-specific queries
-- Purpose: Optimize queries for merchant-specific reel feeds
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS `idx_reels_merchant_created` 
ON `reels`(`merchant_id`, `created_at` DESC);

-- ----------------------------------------------------------------------------
-- 9. Composite index for visibility queries
-- Purpose: Optimize queries that filter reels by product status
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS `idx_reels_product_visibility` 
ON `reels`(`product_id`, `deleted_at`, `is_active`);

-- ----------------------------------------------------------------------------
-- 10. Composite index for merchant feeds
-- Purpose: Optimize queries for merchant-specific reel feeds with filters
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS `idx_reels_merchant_feed` 
ON `reels`(`merchant_id`, `created_at` DESC, `is_active`, `deleted_at`);

-- ----------------------------------------------------------------------------
-- 11. Composite index for user_reel_views queries
-- Purpose: Optimize queries that check if user has viewed a reel
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS `idx_user_reel_views_user_reel` 
ON `user_reel_views`(`user_id`, `reel_id`, `viewed_at` DESC);

-- ----------------------------------------------------------------------------
-- 12. Composite index for user_reel_likes queries
-- Purpose: Optimize queries that check if user has liked a reel
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS `idx_user_reel_likes_user_reel` 
ON `user_reel_likes`(`user_id`, `reel_id`, `created_at` DESC);

-- ============================================================================
-- PART 3: ADD FULL-TEXT SEARCH INDEX
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 13. Add FULLTEXT index on reels.description
-- Purpose: Enable fast full-text search on reel descriptions
-- Note: FULLTEXT indexes require MyISAM or InnoDB with innodb_ft_min_token_size
-- If using InnoDB, ensure innodb_ft_min_token_size is set appropriately (default: 3)
-- ----------------------------------------------------------------------------
CREATE FULLTEXT INDEX IF NOT EXISTS `idx_reels_description_fulltext` 
ON `reels`(`description`);

-- ============================================================================
-- Migration Complete
-- ============================================================================
-- All reels system tables, indexes, and full-text search have been created successfully.
-- This includes:
-- - 6 tables: reels, user_reel_likes, user_reel_views, user_reel_shares, 
--   user_merchant_follows, user_category_preferences
-- - 12+ performance indexes for optimized queries
-- - 1 full-text search index for description search
-- ============================================================================

