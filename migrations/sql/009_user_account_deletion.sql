-- Migration 009: users account deletion grace + soft close timestamps
-- Prefer init_db.run_migration_009_user_account_deletion() for idempotent applies.

ALTER TABLE users
  ADD COLUMN account_deletion_requested_at DATETIME NULL,
  ADD COLUMN account_deletion_effective_at DATETIME NULL,
  ADD COLUMN account_deleted_at DATETIME NULL;

CREATE INDEX idx_users_deletion_effective
  ON users (account_deletion_effective_at, account_deleted_at);

