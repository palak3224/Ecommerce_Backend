-- Create reels table
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

