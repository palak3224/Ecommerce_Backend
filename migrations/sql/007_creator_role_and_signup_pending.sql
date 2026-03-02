-- Migration 007: Add CREATOR role and creator signup pending table
-- Run after init_db create_all() so creator_signup_pending is created by SQLAlchemy.
-- This file only alters users.role enum for MySQL to accept 'creator'.

-- 1. Add 'creator' to users.role enum (MySQL)
-- Adjust if your column is different (e.g. VARCHAR). Check with: SHOW COLUMNS FROM users WHERE Field = 'role';
ALTER TABLE users MODIFY COLUMN role ENUM('user', 'merchant', 'admin', 'super_admin', 'creator') NOT NULL DEFAULT 'user';

-- Success message
SELECT 'Migration 007 completed: users.role accepts creator.' AS message;
