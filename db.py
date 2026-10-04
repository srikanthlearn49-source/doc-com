import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row


# =========================================================
# DATABASE URL
# =========================================================

def get_database_url():
    """
    Get PostgreSQL connection string from Streamlit Secrets
    or environment variables.
    """

    try:

        import streamlit as st

        database_url = st.secrets.get(
            "DATABASE_URL",
            None,
        )

        if database_url:
            return database_url

    except Exception:
        pass

    return os.getenv(
        "DATABASE_URL"
    )


# =========================================================
# DATABASE CONNECTION
# =========================================================

@contextmanager
def get_connection():

    database_url = get_database_url()

    if not database_url:

        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    connection = None

    try:

        connection = psycopg.connect(
            database_url,
            row_factory=dict_row,
            connect_timeout=10,
        )

        yield connection

    finally:

        if connection:

            connection.close()


# =========================================================
# DATABASE STATUS
# =========================================================

def get_database_status():

    database_url = get_database_url()

    if not database_url:

        return {
            "connected": False,
            "message": "DATABASE_URL is not configured.",
        }

    try:

        with get_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    "SELECT 1;"
                )

                cursor.fetchone()

        return {
            "connected": True,
            "message": "PostgreSQL connected.",
        }

    except Exception as e:

        return {
            "connected": False,
            "message": str(e),
        }


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def initialize_database():

    database_url = get_database_url()

    if not database_url:

        return False

    try:

        with get_connection() as connection:

            with connection.cursor() as cursor:

                # =================================================
                # USERS
                # =================================================

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGSERIAL PRIMARY KEY,

                        email TEXT NOT NULL UNIQUE,

                        password_hash TEXT NOT NULL,

                        display_name TEXT,

                        is_active BOOLEAN NOT NULL DEFAULT TRUE,

                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )


                # =================================================
                # DATASETS
                # =================================================

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS datasets (
                        id BIGSERIAL PRIMARY KEY,

                        user_id BIGINT NOT NULL
                            REFERENCES users(id)
                            ON DELETE CASCADE,

                        file_name TEXT NOT NULL,

                        file_hash TEXT,

                        row_count BIGINT,

                        column_count INTEGER,

                        schema_json JSONB,

                        storage_path TEXT,

                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )


                # =================================================
                # CONVERSATIONS
                # =================================================

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id BIGSERIAL PRIMARY KEY,

                        user_id BIGINT NOT NULL
                            REFERENCES users(id)
                            ON DELETE CASCADE,

                        dataset_id BIGINT
                            REFERENCES datasets(id)
                            ON DELETE SET NULL,

                        title TEXT,

                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )


                # =================================================
                # MESSAGES
                # =================================================

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id BIGSERIAL PRIMARY KEY,

                        conversation_id BIGINT NOT NULL
                            REFERENCES conversations(id)
                            ON DELETE CASCADE,

                        role TEXT NOT NULL,

                        content TEXT,

                        sql_query TEXT,

                        result_json JSONB,

                        chart_type TEXT,

                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )


                # =================================================
                # INDEXES
                # =================================================

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_datasets_user_id
                    ON datasets(user_id);
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_conversations_user_id
                    ON conversations(user_id);
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_conversations_dataset_id
                    ON conversations(dataset_id);
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
                    ON messages(conversation_id);
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_users_email
                    ON users(email);
                    """
                )


            connection.commit()

        return True

    except Exception as e:

        print(
            f"Database initialization error: {e}"
        )

        return False


# =========================================================
# USER FUNCTIONS
# =========================================================

def create_user(
    email,
    password_hash,
    display_name=None,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO users (
                    email,
                    password_hash,
                    display_name
                )

                VALUES (
                    %s,
                    %s,
                    %s
                )

                RETURNING
                    id,
                    email,
                    password_hash,
                    display_name,
                    is_active,
                    created_at,
                    updated_at;
                """,
                (
                    email,
                    password_hash,
                    display_name,
                ),
            )

            user = cursor.fetchone()

        connection.commit()

    return user


def get_user_by_email(
    email,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash,
                    display_name,
                    is_active,
                    created_at,
                    updated_at

                FROM users

                WHERE LOWER(email) = LOWER(%s)

                LIMIT 1;
                """,
                (
                    email,
                ),
            )

            return cursor.fetchone()


def get_user_by_id(
    user_id,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    id,
                    email,
                    password_hash,
                    display_name,
                    is_active,
                    created_at,
                    updated_at

                FROM users

                WHERE id = %s

                LIMIT 1;
                """,
                (
                    user_id,
                ),
            )

            return cursor.fetchone()


# =========================================================
# DATASET FUNCTIONS
# =========================================================

def create_dataset(
    user_id,
    file_name,
    file_hash=None,
    row_count=None,
    column_count=None,
    schema_json=None,
    storage_path=None,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO datasets (
                    user_id,
                    file_name,
                    file_hash,
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
                    %s
                )

                RETURNING *;
                """,
                (
                    user_id,
                    file_name,
                    file_hash,
                    row_count,
                    column_count,
                    schema_json,
                    storage_path,
                ),
            )

            dataset = cursor.fetchone()

        connection.commit()

    return dataset


def get_datasets_for_user(
    user_id,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT *

                FROM datasets

                WHERE user_id = %s

                ORDER BY created_at DESC;
                """,
                (
                    user_id,
                ),
            )

            return cursor.fetchall()


# =========================================================
# CONVERSATION FUNCTIONS
# =========================================================

def create_conversation(
    user_id,
    dataset_id=None,
    title=None,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO conversations (
                    user_id,
                    dataset_id,
                    title
                )

                VALUES (
                    %s,
                    %s,
                    %s
                )

                RETURNING *;
                """,
                (
                    user_id,
                    dataset_id,
                    title,
                ),
            )

            conversation = cursor.fetchone()

        connection.commit()

    return conversation


def get_conversations_for_user(
    user_id,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    c.*,
                    d.file_name

                FROM conversations c

                LEFT JOIN datasets d
                    ON d.id = c.dataset_id

                WHERE c.user_id = %s

                ORDER BY c.updated_at DESC;
                """,
                (
                    user_id,
                ),
            )

            return cursor.fetchall()


def get_conversation(
    conversation_id,
    user_id,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT *

                FROM conversations

                WHERE id = %s

                AND user_id = %s

                LIMIT 1;
                """,
                (
                    conversation_id,
                    user_id,
                ),
            )

            return cursor.fetchone()


# =========================================================
# MESSAGE FUNCTIONS
# =========================================================

def create_message(
    conversation_id,
    role,
    content=None,
    sql_query=None,
    result_json=None,
    chart_type=None,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO messages (
                    conversation_id,
                    role,
                    content,
                    sql_query,
                    result_json,
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

                RETURNING *;
                """,
                (
                    conversation_id,
                    role,
                    content,
                    sql_query,
                    result_json,
                    chart_type,
                ),
            )

            message = cursor.fetchone()


            # Update conversation timestamp

            cursor.execute(
                """
                UPDATE conversations

                SET updated_at = NOW()

                WHERE id = %s;
                """,
                (
                    conversation_id,
                ),
            )

        connection.commit()

    return message


def get_messages_for_conversation(
    conversation_id,
    user_id,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    m.*

                FROM messages m

                INNER JOIN conversations c
                    ON c.id = m.conversation_id

                WHERE m.conversation_id = %s

                AND c.user_id = %s

                ORDER BY m.created_at ASC,
                         m.id ASC;
                """,
                (
                    conversation_id,
                    user_id,
                ),
            )

            return cursor.fetchall()


# =========================================================
# UPDATE CONVERSATION TITLE
# =========================================================

def update_conversation_title(
    conversation_id,
    user_id,
    title,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE conversations

                SET
                    title = %s,
                    updated_at = NOW()

                WHERE id = %s

                AND user_id = %s;
                """,
                (
                    title,
                    conversation_id,
                    user_id,
                ),
            )

        connection.commit()


# =========================================================
# DELETE CONVERSATION
# =========================================================

def delete_conversation(
    conversation_id,
    user_id,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM conversations

                WHERE id = %s

                AND user_id = %s;
                """,
                (
                    conversation_id,
                    user_id,
                ),
            )

        connection.commit()
