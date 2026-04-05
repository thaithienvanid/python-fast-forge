-- Add Event Sourcing tables for CQRS pattern
-- This migration adds the event store, snapshot tables, and projection checkpoints required for event sourcing

-- Create "event_store" table
CREATE TABLE "event_store" (
  "event_id" uuid NOT NULL,
  "event_type" character varying(255) NOT NULL,
  "event_version" integer NOT NULL DEFAULT 1,
  "aggregate_type" character varying(100) NOT NULL,
  "aggregate_id" uuid NOT NULL,
  "aggregate_version" integer NOT NULL,
  "event_data" jsonb NOT NULL,
  "event_metadata" jsonb DEFAULT '{}',
  "occurred_at" timestamptz NOT NULL,
  "recorded_at" timestamptz NOT NULL,
  PRIMARY KEY ("event_id")
);

-- Create indexes on event_store
CREATE INDEX "ix_event_store_aggregate_id" ON "event_store" ("aggregate_id");
CREATE UNIQUE INDEX "ix_event_store_aggregate_version_unique" ON "event_store" ("aggregate_id", "aggregate_version");
CREATE INDEX "ix_event_store_event_type" ON "event_store" ("event_type");
CREATE INDEX "ix_event_store_occurred_at" ON "event_store" ("occurred_at");
CREATE INDEX "ix_event_store_aggregate" ON "event_store" ("aggregate_type", "aggregate_id");

-- Set comments on event_store columns
COMMENT ON COLUMN "event_store"."event_id" IS 'Unique event identifier (UUIDv7 for time-ordering)';
COMMENT ON COLUMN "event_store"."event_type" IS 'Fully-qualified event type (e.g., ''user.created'')';
COMMENT ON COLUMN "event_store"."event_version" IS 'Event schema version for evolution';
COMMENT ON COLUMN "event_store"."aggregate_type" IS 'Type of aggregate (e.g., ''User'', ''Order'')';
COMMENT ON COLUMN "event_store"."aggregate_id" IS 'Aggregate instance identifier';
COMMENT ON COLUMN "event_store"."aggregate_version" IS 'Aggregate version after this event (for optimistic locking)';
COMMENT ON COLUMN "event_store"."event_data" IS 'Full event payload as JSON';
COMMENT ON COLUMN "event_store"."event_metadata" IS 'Additional metadata (causation_id, correlation_id, user_id, etc.)';
COMMENT ON COLUMN "event_store"."occurred_at" IS 'When the event occurred (business time)';
COMMENT ON COLUMN "event_store"."recorded_at" IS 'When the event was persisted (technical time)';

-- Create "event_store_snapshots" table
CREATE TABLE "event_store_snapshots" (
  "id" uuid NOT NULL,
  "aggregate_type" character varying(100) NOT NULL,
  "aggregate_id" uuid NOT NULL,
  "aggregate_version" integer NOT NULL,
  "snapshot_data" jsonb NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  UNIQUE ("aggregate_id")
);

-- Set comments on event_store_snapshots columns
COMMENT ON COLUMN "event_store_snapshots"."id" IS 'Unique snapshot identifier';
COMMENT ON COLUMN "event_store_snapshots"."aggregate_type" IS 'Type of aggregate (e.g., ''User'', ''Order'')';
COMMENT ON COLUMN "event_store_snapshots"."aggregate_id" IS 'Aggregate instance identifier (one snapshot per aggregate)';
COMMENT ON COLUMN "event_store_snapshots"."aggregate_version" IS 'Aggregate version when snapshot was taken';
COMMENT ON COLUMN "event_store_snapshots"."snapshot_data" IS 'Full aggregate state as JSON';
COMMENT ON COLUMN "event_store_snapshots"."created_at" IS 'When this snapshot was created';

-- Create "projection_checkpoints" table
CREATE TABLE "projection_checkpoints" (
  "projection_name" character varying(100) NOT NULL,
  "last_event_timestamp" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("projection_name")
);

-- Set comments on projection_checkpoints columns
COMMENT ON COLUMN "projection_checkpoints"."projection_name" IS 'Unique projection identifier';
COMMENT ON COLUMN "projection_checkpoints"."last_event_timestamp" IS 'Last processed event timestamp';
COMMENT ON COLUMN "projection_checkpoints"."updated_at" IS 'When checkpoint was last updated';
