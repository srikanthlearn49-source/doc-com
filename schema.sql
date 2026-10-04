CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- =========================================================
-- USERS
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    email TEXT UNIQUE NOT NULL,

    password_hash TEXT,

    display_name TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================================================
-- DATASETS
-- =========================================================

CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    name TEXT NOT NULL,

    original_filename TEXT NOT NULL,

    file_type TEXT,

    file_size BIGINT,

    table_name TEXT,

    row_count BIGINT,

    column_count INTEGER,

    schema_json JSONB,

    storage_path TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================================================
-- CONVERSATIONS
-- =========================================================

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL
        REFERENCES users(id)
        ON DELETE CASCADE,

    dataset_id UUID
        REFERENCES datasets(id)
        ON DELETE SET NULL,

    title TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================================================
-- MESSAGES
-- =========================================================

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    conversation_id UUID NOT NULL
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    role TEXT NOT NULL,

    content TEXT,

    sql_query TEXT,

    chart_type TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX IF NOT EXISTS idx_datasets_user_id
ON datasets(user_id);


CREATE INDEX IF NOT EXISTS idx_conversations_user_id
ON conversations(user_id);


CREATE INDEX IF NOT EXISTS idx_conversations_dataset_id
ON conversations(dataset_id);


CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
ON messages(conversation_id);


CREATE INDEX IF NOT EXISTS idx_messages_created_at
ON messages(created_at);
