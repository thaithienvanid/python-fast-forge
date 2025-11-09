-- Create "users" table
CREATE TABLE "users" (
  "email" character varying(255) NOT NULL,
  "username" character varying(100) NOT NULL,
  "full_name" character varying(255) NULL,
  "is_active" boolean NOT NULL,
  "tenant_id" uuid NULL,
  "id" uuid NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  "deleted_at" timestamptz NULL,
  PRIMARY KEY ("id")
);
-- Create index "ix_users_active_only" to table: "users"
CREATE INDEX "ix_users_active_only" ON "users" ("id") WHERE (deleted_at IS NULL);
-- Create index "ix_users_active_status" to table: "users"
CREATE INDEX "ix_users_active_status" ON "users" ("is_active", "deleted_at") WHERE (deleted_at IS NULL);
-- Create index "ix_users_deleted_at" to table: "users"
CREATE INDEX "ix_users_deleted_at" ON "users" ("deleted_at");
-- Create index "ix_users_deleted_records" to table: "users"
CREATE INDEX "ix_users_deleted_records" ON "users" ("deleted_at") WHERE (deleted_at IS NOT NULL);
-- Create index "ix_users_email" to table: "users"
CREATE UNIQUE INDEX "ix_users_email" ON "users" ("email");
-- Create index "ix_users_tenant_active" to table: "users"
CREATE INDEX "ix_users_tenant_active" ON "users" ("tenant_id", "deleted_at") WHERE (deleted_at IS NULL);
-- Create index "ix_users_tenant_id" to table: "users"
CREATE INDEX "ix_users_tenant_id" ON "users" ("tenant_id");
-- Create index "ix_users_username" to table: "users"
CREATE UNIQUE INDEX "ix_users_username" ON "users" ("username");
-- Set comment to column: "email" on table: "users"
COMMENT ON COLUMN "users"."email" IS 'User email address (normalized to lowercase for consistency)';
-- Set comment to column: "username" on table: "users"
COMMENT ON COLUMN "users"."username" IS 'Unique username identifier';
-- Set comment to column: "full_name" on table: "users"
COMMENT ON COLUMN "users"."full_name" IS 'User''s full display name (optional)';
-- Set comment to column: "is_active" on table: "users"
COMMENT ON COLUMN "users"."is_active" IS 'Account activation status (False for suspended accounts)';
-- Set comment to column: "tenant_id" on table: "users"
COMMENT ON COLUMN "users"."tenant_id" IS 'Tenant identifier for multi-tenancy data isolation';
-- Set comment to column: "id" on table: "users"
COMMENT ON COLUMN "users"."id" IS 'Primary key using UUIDv7 for time-ordered identifiers';
-- Set comment to column: "created_at" on table: "users"
COMMENT ON COLUMN "users"."created_at" IS 'Timestamp of entity creation';
-- Set comment to column: "updated_at" on table: "users"
COMMENT ON COLUMN "users"."updated_at" IS 'Timestamp of last modification';
-- Set comment to column: "deleted_at" on table: "users"
COMMENT ON COLUMN "users"."deleted_at" IS 'Soft delete timestamp (NULL if active, set when deleted). Uses partial indexing for performance.';
