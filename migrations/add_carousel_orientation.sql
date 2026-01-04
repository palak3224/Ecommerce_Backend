-- Migration: Add orientation column to carousels table
-- Run this script if you have an existing database with carousels table

-- Add orientation column with default value 'horizontal'
ALTER TABLE carousels 
ADD COLUMN orientation VARCHAR(20) NOT NULL DEFAULT 'horizontal' 
AFTER type;

-- Update existing records to have 'horizontal' orientation (if any exist)
UPDATE carousels 
SET orientation = 'horizontal' 
WHERE orientation IS NULL OR orientation = '';

-- Add comment to column
ALTER TABLE carousels 
MODIFY COLUMN orientation VARCHAR(20) NOT NULL DEFAULT 'horizontal' 
COMMENT 'Banner orientation: horizontal (1920x450px) or vertical (368x564px)';

