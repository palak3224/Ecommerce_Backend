-- Migration: Support external reels (product_id nullable + external columns)
-- Run this if Alembic migration 006_reels_aoin_external has not been applied.
-- Fixes: IntegrityError 1048 - Column 'product_id' cannot be null.
--
-- If you get "Duplicate column" or "Duplicate key" errors, those parts are already
-- applied; at minimum run step 1 (ALTER product_id) to fix the external-reel insert.

-- 1. Make product_id nullable (required for external reels)
ALTER TABLE reels MODIFY COLUMN product_id INT NULL;

-- 2. Add external reel columns (skip if you get "Duplicate column" errors)
ALTER TABLE reels ADD COLUMN product_url VARCHAR(2048) NULL;
ALTER TABLE reels ADD COLUMN product_name VARCHAR(500) NULL;
ALTER TABLE reels ADD COLUMN category_id INT NULL;
ALTER TABLE reels ADD COLUMN category_name VARCHAR(255) NULL;
ALTER TABLE reels ADD COLUMN platform VARCHAR(50) NULL;

-- 3. Add foreign key for category_id (skip if fk_reels_category_id already exists)
ALTER TABLE reels ADD CONSTRAINT fk_reels_category_id FOREIGN KEY (category_id) REFERENCES categories(category_id);

-- 4. Index for platform (skip if idx_reels_platform already exists)
CREATE INDEX idx_reels_platform ON reels(platform);

-- 5. Backfill existing reels as AOIN (set platform and product_url)
-- Replace 'https://aoinstore.com' with your PRODUCT_PAGE_BASE_URL or FRONTEND_URL if needed.
UPDATE reels
SET platform = 'aoin', product_url = CONCAT('https://aoinstore.com', '/product/', product_id)
WHERE product_id IS NOT NULL;
