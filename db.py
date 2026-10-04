import os
import uuid
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
import streamlit as st


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

def get_database_url():
    """
    Get PostgreSQL connection URL.

    Recommended Streamlit secret:

    DATABASE_URL = "postgresql://..."

    Environment variable is also supported.
    """

    try:
        database_url = st.secrets.get(
            "DATABASE_URL",
            None
        )
    except Exception:
        database_url = None

    if not database_url:
        database_url = os.getenv(
            "DATABASE_URL"
        )

    return database_url


# =========================================================
# CONNECTION
# =========================================================

def get_connection():

    database_url = get_database_url()

    if not database_url:

        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Add your PostgreSQL connection string "
            "to Streamlit Secrets."
        )

    return psycopg.connect(
        database_url,
        row_factory=dict_row
    )


# =========================================================
# DATABASE HEALTH CHECK
# =========================================================

def test_database_connection():

    try:

        with get_connection() as conn:

            with conn.cursor() as cursor:

                cursor.execute(
                    "SELECT 1 AS connected"
                )

                result = cursor.fetchone()

        return result["connected"] == 1

    except Exception:

        return False


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def initialize_database():

    schema_sql = """
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

        email TEXT UNIQUE NOT NULL,

        password_hash TEXT,

        display_name TEXT,

        is_active BOOLEAN NOT NULL DEFAULT TRUE,

        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );


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
    """

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                schema_sql
            )

        conn.commit()


# =========================================================
# DATABASE STATUS
# =========================================================

def get_database_status():

    database_url = get_database_url()

    if not database_url:

        return {
            "configured": False,
            "connected": False,
            "message": (
                "DATABASE_URL is not configured."
            )
        }

    try:

        initialize_database()

        return {
            "configured": True,
            "connected": True,
            "message": (
                "PostgreSQL connected successfully."
            )
        }

    except Exception as e:

        return {
            "configured": True,
            "connected": False,
            "message": str(e)
        }


# =========================================================
# USER HELPERS
# =========================================================

def create_user(
    email,
    password_hash=None,
    display_name=None
):

    user_id = str(
        uuid.uuid4()
    )

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO users (
                    id,
                    email,
                    password_hash,
                    display_name
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING *
                """,
                (
                    user_id,
                    email.lower().strip(),
                    password_hash,
                    display_name
                )
            )

            user = cursor.fetchone()

        conn.commit()

    return user


def get_user_by_email(email):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1
                """,
                (
                    email.strip(),
                )
            )

            return cursor.fetchone()


def get_user_by_id(user_id):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (
                    user_id,
                )
            )

            return cursor.fetchone()


# =========================================================
# DATASET HELPERS
# =========================================================

def create_dataset(
    user_id,
    name,
    original_filename,
    file_type=None,
    file_size=None,
    table_name=None,
    row_count=None,
    column_count=None,
    schema_json=None,
    storage_path=None
):

    dataset_id = str(
        uuid.uuid4()
    )

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO datasets (
                    id,
                    user_id,
                    name,
                    original_filename,
                    file_type,
                    file_size,
                    table_name,
                    row_count,
                    column_count,
                    schema_json,
                    storage_path
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING *
                """,
                (
                    dataset_id,
                    user_id,
                    name,
                    original_filename,
                    file_type,
                    file_size,
                    table_name,
                    row_count,
                    column_count,
                    schema_json,
                    storage_path
                )
            )

            dataset = cursor.fetchone()

        conn.commit()

    return dataset


def get_user_datasets(user_id):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM datasets
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (
                    user_id,
                )
            )

            return cursor.fetchall()


def get_dataset(
    dataset_id,
    user_id
):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM datasets
                WHERE id = %s
                AND user_id = %s
                LIMIT 1
                """,
                (
                    dataset_id,
                    user_id
                )
            )

            return cursor.fetchone()


# =========================================================
# CONVERSATION HELPERS
# =========================================================

def create_conversation(
    user_id,
    dataset_id=None,
    title=None
):

    conversation_id = str(
        uuid.uuid4()
    )

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO conversations (
                    id,
                    user_id,
                    dataset_id,
                    title
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING *
                """,
                (
                    conversation_id,
                    user_id,
                    dataset_id,
                    title
                )
            )

            conversation = cursor.fetchone()

        conn.commit()

    return conversation


def get_user_conversations(
    user_id
):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    c.*,
                    d.name AS dataset_name
                FROM conversations c
                LEFT JOIN datasets d
                    ON c.dataset_id = d.id
                WHERE c.user_id = %s
                ORDER BY c.updated_at DESC
                """,
                (
                    user_id,
                )
            )

            return cursor.fetchall()


def get_conversation(
    conversation_id,
    user_id
):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM conversations
                WHERE id = %s
                AND user_id = %s
                LIMIT 1
                """,
                (
                    conversation_id,
                    user_id
                )
            )

            return cursor.fetchone()


def update_conversation_title(
    conversation_id,
    user_id,
    title
):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                UPDATE conversations
                SET
                    title = %s,
                    updated_at = NOW()
                WHERE id = %s
                AND user_id = %s
                """,
                (
                    title,
                    conversation_id,
                    user_id
                )
            )

        conn.commit()


# =========================================================
# MESSAGE HELPERS
# =========================================================

def create_message(
    conversation_id,
    role,
    content=None,
    sql_query=None,
    chart_type=None
):

    message_id = str(
        uuid.uuid4()
    )

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO messages (
                    id,
                    conversation_id,
                    role,
                    content,
                    sql_query,
                    chart_type
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                RETURNING *
                """,
                (
                    message_id,
                    conversation_id,
                    role,
                    content,
                    sql_query,
                    chart_type
                )
            )

            message = cursor.fetchone()

            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = NOW()
                WHERE id = %s
                """,
                (
                    conversation_id,
                )
            )

        conn.commit()

    return message


def get_conversation_messages(
    conversation_id,
    user_id
):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    m.*
                FROM messages m
                INNER JOIN conversations c
                    ON m.conversation_id = c.id
                WHERE m.conversation_id = %s
                AND c.user_id = %s
                ORDER BY m.created_at ASC
                """,
                (
                    conversation_id,
                    user_id
                )
            )

            return cursor.fetchall()


# =========================================================
# DELETE HELPERS
# =========================================================

def delete_conversation(
    conversation_id,
    user_id
):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM conversations
                WHERE id = %s
                AND user_id = %s
                """,
                (
                    conversation_id,
                    user_id
                )
            )

        conn.commit()


def delete_dataset(
    dataset_id,
    user_id
):

    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM datasets
                WHERE id = %s
                AND user_id = %s
                """,
                (
                    dataset_id,
                    user_id
                )
            )

        conn.commit()
