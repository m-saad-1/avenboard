-- Additive Avenboard schema. Original starter tables are never dropped.

CREATE TABLE IF NOT EXISTS "ab_users" (
  "id" TEXT PRIMARY KEY,
  "subject" TEXT NOT NULL,
  "pool" TEXT NOT NULL,
  "email" TEXT NOT NULL,
  "name" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_workspaces" (
  "id" TEXT PRIMARY KEY,
  "name" TEXT NOT NULL,
  "owner_id" TEXT NOT NULL,
  "timezone" TEXT NOT NULL,
  "version" BIGINT NOT NULL,
  "next_card" BIGINT NOT NULL,
  "is_demo" BOOLEAN NOT NULL,
  "created_at" TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_memberships" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "user_id" TEXT NOT NULL,
  "role" TEXT NOT NULL,
  "status" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_invitations" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "email" TEXT NOT NULL,
  "role" TEXT NOT NULL,
  "token_hash" TEXT NOT NULL,
  "status" TEXT NOT NULL,
  "applicant_id" TEXT,
  "expires_at" TIMESTAMP NOT NULL,
  "created_at" TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_boards" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "description" TEXT NOT NULL,
  "visibility" TEXT NOT NULL,
  "color" TEXT NOT NULL,
  "version" BIGINT NOT NULL,
  "archived" BOOLEAN NOT NULL,
  "deleted" BOOLEAN NOT NULL,
  "created_at" TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_board_members" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "user_id" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_lists" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "category" TEXT NOT NULL,
  "alias" TEXT NOT NULL,
  "position" BIGINT NOT NULL,
  "version" BIGINT NOT NULL,
  "archived" BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_cards" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "list_id" TEXT NOT NULL,
  "number" BIGINT NOT NULL,
  "title" TEXT NOT NULL,
  "description" TEXT NOT NULL,
  "assignee_id" TEXT,
  "due_date" DATE,
  "position" BIGINT NOT NULL,
  "version" BIGINT NOT NULL,
  "content_version" BIGINT NOT NULL,
  "created_by" TEXT NOT NULL,
  "created_at" TIMESTAMP NOT NULL,
  "updated_at" TIMESTAMP NOT NULL,
  "archived" BOOLEAN NOT NULL,
  "deleted" BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_labels" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "color" TEXT NOT NULL,
  "description" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_card_labels" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "card_id" TEXT NOT NULL,
  "label_id" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_checklist_items" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "card_id" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "completed" BOOLEAN NOT NULL,
  "position" BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_dependencies" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "card_id" TEXT NOT NULL,
  "prerequisite_id" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_activity" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT,
  "card_id" TEXT,
  "actor_id" TEXT NOT NULL,
  "actor_name" TEXT NOT NULL,
  "action" TEXT NOT NULL,
  "before_json" TEXT NOT NULL,
  "after_json" TEXT NOT NULL,
  "created_at" TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_preferences" (
  "id" TEXT PRIMARY KEY,
  "user_id" TEXT NOT NULL,
  "theme" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_favorites" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "user_id" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_receipts" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT,
  "actor_id" TEXT NOT NULL,
  "fingerprint" TEXT NOT NULL,
  "result_json" TEXT NOT NULL,
  "created_at" TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_embedding_jobs" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "card_id" TEXT NOT NULL,
  "content_version" BIGINT NOT NULL,
  "status" TEXT NOT NULL,
  "lease_until" TIMESTAMP,
  "attempts" BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ab_embeddings" (
  "id" TEXT PRIMARY KEY,
  "workspace_id" TEXT NOT NULL,
  "board_id" TEXT NOT NULL,
  "card_id" TEXT NOT NULL,
  "content_version" BIGINT NOT NULL,
  "model" TEXT NOT NULL,
  "dimensions" BIGINT NOT NULL,
  "embedding" VECTOR(512)
);

CREATE TABLE IF NOT EXISTS "ab_schema_versions" (
  "id" TEXT PRIMARY KEY,
  "applied_at" TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS "ab_card_number" ON "ab_cards" ("workspace_id", "number");

CREATE INDEX IF NOT EXISTS "ab_memberships_user_id" ON "ab_memberships" ("user_id");

CREATE INDEX IF NOT EXISTS "ab_boards_workspace_id" ON "ab_boards" ("workspace_id");

CREATE INDEX IF NOT EXISTS "ab_cards_board_id" ON "ab_cards" ("board_id");

CREATE INDEX IF NOT EXISTS "ab_lists_board_id" ON "ab_lists" ("board_id");

CREATE INDEX IF NOT EXISTS "ab_activity_workspace_id" ON "ab_activity" ("workspace_id");

CREATE INDEX IF NOT EXISTS "ab_embedding_jobs_status" ON "ab_embedding_jobs" ("status");
