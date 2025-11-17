-- Migration: Make user_id nullable in phone_verifications table for phone sign-up flow
-- Date: 2025-11-17

-- Make user_id nullable
ALTER TABLE phone_verifications 
MODIFY COLUMN user_id INT NULL;

-- Add created_at column if it doesn't exist
ALTER TABLE phone_verifications 
ADD COLUMN IF NOT EXISTS created_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- Add index on phone for faster lookups
ALTER TABLE phone_verifications 
ADD INDEX IF NOT EXISTS idx_phone (phone);

