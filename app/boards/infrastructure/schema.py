"""Explicit DataK3 tables. Names are an internal allowlist, never client-controlled."""

TABLES = {
    "users": {
        "id": "TEXT PRIMARY KEY",
        "subject": "TEXT NOT NULL",
        "pool": "TEXT NOT NULL",
        "email": "TEXT NOT NULL",
        "name": "TEXT NOT NULL",
    },
    "workspaces": {
        "id": "TEXT PRIMARY KEY",
        "name": "TEXT NOT NULL",
        "owner_id": "TEXT NOT NULL",
        "timezone": "TEXT NOT NULL",
        "version": "BIGINT NOT NULL",
        "next_card": "BIGINT NOT NULL",
        "is_demo": "BOOLEAN NOT NULL",
        "created_at": "TIMESTAMP NOT NULL",
    },
    "memberships": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "user_id": "TEXT NOT NULL",
        "role": "TEXT NOT NULL",
        "status": "TEXT NOT NULL",
    },
    "invitations": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "email": "TEXT NOT NULL",
        "role": "TEXT NOT NULL",
        "token_hash": "TEXT NOT NULL",
        "status": "TEXT NOT NULL",
        "applicant_id": "TEXT",
        "expires_at": "TIMESTAMP NOT NULL",
        "created_at": "TIMESTAMP NOT NULL",
    },
    "boards": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "title": "TEXT NOT NULL",
        "description": "TEXT NOT NULL",
        "visibility": "TEXT NOT NULL",
        "color": "TEXT NOT NULL",
        "version": "BIGINT NOT NULL",
        "archived": "BOOLEAN NOT NULL",
        "deleted": "BOOLEAN NOT NULL",
        "created_at": "TIMESTAMP NOT NULL",
    },
    "board_members": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "user_id": "TEXT NOT NULL",
    },
    "lists": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "title": "TEXT NOT NULL",
        "category": "TEXT NOT NULL",
        "alias": "TEXT NOT NULL",
        "position": "BIGINT NOT NULL",
        "version": "BIGINT NOT NULL",
        "archived": "BOOLEAN NOT NULL",
    },
    "cards": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "list_id": "TEXT NOT NULL",
        "number": "BIGINT NOT NULL",
        "title": "TEXT NOT NULL",
        "description": "TEXT NOT NULL",
        "assignee_id": "TEXT",
        "due_date": "DATE",
        "position": "BIGINT NOT NULL",
        "version": "BIGINT NOT NULL",
        "content_version": "BIGINT NOT NULL",
        "created_by": "TEXT NOT NULL",
        "created_at": "TIMESTAMP NOT NULL",
        "updated_at": "TIMESTAMP NOT NULL",
        "archived": "BOOLEAN NOT NULL",
        "deleted": "BOOLEAN NOT NULL",
    },
    "labels": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "name": "TEXT NOT NULL",
        "color": "TEXT NOT NULL",
        "description": "TEXT NOT NULL",
    },
    "card_labels": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "card_id": "TEXT NOT NULL",
        "label_id": "TEXT NOT NULL",
    },
    "checklist_items": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "card_id": "TEXT NOT NULL",
        "title": "TEXT NOT NULL",
        "completed": "BOOLEAN NOT NULL",
        "position": "BIGINT NOT NULL",
    },
    "dependencies": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "card_id": "TEXT NOT NULL",
        "prerequisite_id": "TEXT NOT NULL",
    },
    "activity": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT",
        "card_id": "TEXT",
        "actor_id": "TEXT NOT NULL",
        "actor_name": "TEXT NOT NULL",
        "action": "TEXT NOT NULL",
        "before_json": "TEXT NOT NULL",
        "after_json": "TEXT NOT NULL",
        "created_at": "TIMESTAMP NOT NULL",
    },
    "preferences": {
        "id": "TEXT PRIMARY KEY",
        "user_id": "TEXT NOT NULL",
        "theme": "TEXT NOT NULL",
    },
    "favorites": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "user_id": "TEXT NOT NULL",
    },
    "receipts": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT",
        "actor_id": "TEXT NOT NULL",
        "fingerprint": "TEXT NOT NULL",
        "result_json": "TEXT NOT NULL",
        "created_at": "TIMESTAMP NOT NULL",
    },
    "embedding_jobs": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "card_id": "TEXT NOT NULL",
        "content_version": "BIGINT NOT NULL",
        "status": "TEXT NOT NULL",
        "lease_until": "TIMESTAMP",
        "attempts": "BIGINT NOT NULL",
    },
    "embeddings": {
        "id": "TEXT PRIMARY KEY",
        "workspace_id": "TEXT NOT NULL",
        "board_id": "TEXT NOT NULL",
        "card_id": "TEXT NOT NULL",
        "content_version": "BIGINT NOT NULL",
        "model": "TEXT NOT NULL",
        "dimensions": "BIGINT NOT NULL",
        "embedding": "VECTOR(512)",
    },
    "schema_versions": {"id": "TEXT PRIMARY KEY", "applied_at": "TIMESTAMP NOT NULL"},
}


def schema_sql():
    statements = [
        "-- Additive Avenboard schema. Original starter tables are never dropped."
    ]
    for name, columns in TABLES.items():
        fields = ",\n  ".join(f'"{key}" {kind}' for key, kind in columns.items())
        statements.append(f'CREATE TABLE IF NOT EXISTS "ab_{name}" (\n  {fields}\n);')
    statements.append(
        'CREATE UNIQUE INDEX IF NOT EXISTS "ab_card_number" ON "ab_cards" ("workspace_id", "number");'
    )
    for table, column in (
        ("memberships", "user_id"),
        ("boards", "workspace_id"),
        ("cards", "board_id"),
        ("lists", "board_id"),
        ("activity", "workspace_id"),
        ("embedding_jobs", "status"),
    ):
        statements.append(
            f'CREATE INDEX IF NOT EXISTS "ab_{table}_{column}" ON "ab_{table}" ("{column}");'
        )
    return "\n\n".join(statements) + "\n"
