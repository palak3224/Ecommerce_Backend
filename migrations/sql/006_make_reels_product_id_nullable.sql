-- Migration: Support external reels (product_id nullable + external columns)
-- Run this if Alembic migration 006_reels_aoin_external has not been applied.
-- Fixes: IntegrityError 1048 - Column 'product_id' cannot be null.
--
-- Important: Run against the SAME database as your app's DATABASE_URI.
-- If you still get the error after migrating, confirm with:
--   SHOW CREATE TABLE reels;   -- product_id should allow NULL
--
-- If you get "Duplicate column" or "Duplicate key" errors, those parts are already
-- applied. Steps 1a–1c (drop FK, modify column, re-add FK) must all run.

-- 1a. Drop foreign key on product_id (MySQL often won't allow MODIFY otherwise)
ALTER TABLE reels DROP FOREIGN KEY fk_reels_product;

-- 1b. Make product_id nullable (required for external reels)
ALTER TABLE reels MODIFY COLUMN product_id INT NULL;

-- 1c. Re-add foreign key (NULL product_id = external reel; non-NULL = AOIN product)
ALTER TABLE reels ADD CONSTRAINT fk_reels_product FOREIGN KEY (product_id) REFERENCES products(product_id);

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

-- Verify: run this and confirm product_id shows YES in the Null column:
-- SHOW CREATE TABLE reels;
-- Or: SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reels' AND COLUMN_NAME = 'product_id';
