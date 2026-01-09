-- Migration: Make user_id nullable in phone_verifications table for phone sign-up flow
-- Date: 2025-11-17

-- Make user_id nullable (allows NULL for sign-up flow where user doesn't exist yet)
ALTER TABLE phone_verifications 
MODIFY COLUMN user_id INT NULL;

