-- Merchant account deletion (24h grace, soft close)
-- Prefer init_db.run_migration_008_merchant_account_deletion() for idempotent applies.

ALTER TABLE merchant_profiles
  ADD COLUMN account_deletion_requested_at DATETIME NULL;

ALTER TABLE merchant_profiles
  ADD COLUMN account_deletion_effective_at DATETIME NULL;

ALTER TABLE merchant_profiles
  ADD COLUMN account_deleted_at DATETIME NULL;

CREATE INDEX idx_merchant_profiles_deletion_effective
  ON merchant_profiles (account_deletion_effective_at, account_deleted_at);
