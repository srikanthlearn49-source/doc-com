import hashlib
import hmac
import re
import secrets
import json

import streamlit as st
import pandas as pd
import duckdb
from groq import Groq
import altair as alt

from db import (
    initialize_database,
    get_database_status,
    create_user,
    get_user_by_email,
)


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="Chat With Your Data",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Chat With Your Data")
st.caption("Ask questions about your CSV or Excel data.")


# =========================================================
# CONFIGURATION
# =========================================================

MODEL = "openai/gpt-oss-20b"


# =========================================================
# SESSION STATE
# =========================================================

DEFAULT_STATE = {
    "messages": [],
    "file_name": None,
    "df": None,
    "question_input": "",
    "suggestions": [],
    "suggestions_file": None,
    "auth_mode": "guest",
    "user": None,
}

for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# GROQ
# =========================================================

try:

    client = Groq(
        api_key=st.secrets["GROQ_API_KEY"]
    )

except Exception as e:

    st.error(
        "Groq API key is not configured correctly."
    )

    st.stop()


# =========================================================
# AUTHENTICATION HELPERS
# =========================================================

def hash_password(password):
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    The salt is stored together with the hash.
    """

    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310000,
    )

    return (
        salt.hex()
        + "$"
        + password_hash.hex()
    )


def verify_password(password, stored_hash):

    try:

        salt_hex, hash_hex = stored_hash.split(
            "$",
            1
        )

        salt = bytes.fromhex(
            salt_hex
        )

        expected_hash = bytes.fromhex(
            hash_hex
        )

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            310000,
        )

        return hmac.compare_digest(
            actual_hash,
            expected_hash,
        )

    except Exception:

        return False


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

database_status = get_database_status()


# =========================================================
# AUTH UI
# =========================================================

def show_authentication():

    st.sidebar.markdown("---")

    st.sidebar.subheader("👤 Account")

    if st.session_state.user:

        user = st.session_state.user

        display_name = (
            user.get("display_name")
            or user.get("email")
            or "User"
        )

        st.sidebar.success(
            f"Logged in as {display_name}"
        )

        if st.sidebar.button(
            "Logout",
            use_container_width=True,
        ):

            st.session_state.user = None
            st.session_state.auth_mode = "guest"
            st.session_state.messages = []
            st.session_state.file_name = None
            st.session_state.df = None
            st.session_state.suggestions = []
            st.session_state.suggestions_file = None

            st.rerun()

        return


    auth_choice = st.sidebar.radio(
        "Mode",
        [
            "Guest Mode",
            "Login",
            "Register",
        ],
        key="auth_mode_selector",
    )


    if auth_choice == "Guest Mode":

        st.session_state.auth_mode = "guest"

        st.sidebar.info(
            "Guest Mode stores your current "
            "working data in the Streamlit session."
        )

        return


    if not database_status["connected"]:

        st.sidebar.error(
            "PostgreSQL is not available. "
            "Configure DATABASE_URL in Streamlit Secrets."
        )

        return


    # =====================================================
    # LOGIN
    # =====================================================

    if auth_choice == "Login":

        st.session_state.auth_mode = "login"

        with st.sidebar.form(
            "login_form"
        ):

            st.subheader("🔐 Login")

            email = st.text_input(
                "Email"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Login",
                use_container_width=True,
            )

            if submitted:

                email = email.strip().lower()

                if not email or not password:

                    st.error(
                        "Enter your email and password."
                    )

                else:

                    try:

                        user = get_user_by_email(
                            email
                        )

                        if (
                            user
                            and user.get("is_active", True)
                            and user.get("password_hash")
                            and verify_password(
                                password,
                                user["password_hash"],
                            )
                        ):

                            st.session_state.user = user
                            st.session_state.auth_mode = "user"

                            st.success(
                                "Login successful."
                            )

                            st.rerun()

                        else:

                            st.error(
                                "Invalid email or password."
                            )

                    except Exception as e:

                        st.error(
                            "Login failed. "
                            "Please try again."
                        )


    # =====================================================
    # REGISTER
    # =====================================================

    elif auth_choice == "Register":

        st.session_state.auth_mode = "register"

        with st.sidebar.form(
            "register_form"
        ):

            st.subheader("📝 Create Account")

            display_name = st.text_input(
                "Name"
            )

            email = st.text_input(
                "Email"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            confirm_password = st.text_input(
                "Confirm password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Create account",
                use_container_width=True,
            )

            if submitted:

                email = email.strip().lower()

                if not email or not password:

                    st.error(
                        "Email and password are required."
                    )

                elif len(password) < 8:

                    st.error(
                        "Password must contain at least "
                        "8 characters."
                    )

                elif password != confirm_password:

                    st.error(
                        "Passwords do not match."
                    )

                else:

                    try:

                        existing_user = get_user_by_email(
                            email
                        )

                        if existing_user:

                            st.error(
                                "An account with this "
                                "email already exists."
                            )

                        else:

                            password_hash = hash_password(
                                password
                            )

                            user = create_user(
                                email=email,
                                password_hash=password_hash,
                                display_name=(
                                    display_name.strip()
                                    or None
                                ),
                            )

                            st.session_state.user = user
                            st.session_state.auth_mode = "user"

                            st.success(
                                "Account created successfully."
                            )

                            st.rerun()

                    except Exception as e:

                        st.error(
                            "Could not create account. "
                            "Please try again."
                        )


# =========================================================
# SHOW AUTHENTICATION
# =========================================================

show_authentication()


# =========================================================
# DATABASE STATUS
# =========================================================

with st.sidebar:

    st.markdown("---")

    if database_status["connected"]:

        st.success(
            "PostgreSQL: Connected"
        )

    else:

        st.warning(
            "PostgreSQL: Not configured"
        )


# =========================================================
# CURRENT USER
# =========================================================

current_user = st.session_state.user


# =========================================================
# FILE UPLOAD
# =========================================================

uploaded_file = st.file_uploader(
    "Upload CSV or Excel file",
    type=[
        "csv",
        "xlsx",
        "xls",
    ],
)


if uploaded_file is None:

    st.info(
        "Upload a CSV or Excel file to get started."
    )

    st.stop()


# =========================================================
# READ FILE
# =========================================================

if (
    st.session_state.file_name
    != uploaded_file.name
):

    try:

        if uploaded_file.name.lower().endswith(
            ".csv"
        ):

            df = pd.read_csv(
                uploaded_file
            )

        else:

            df = pd.read_excel(
                uploaded_file
            )

        st.session_state.df = df

        st.session_state.file_name = (
            uploaded_file.name
        )

        # Reset conversation
        st.session_state.messages = []

        # Reset suggestions
        st.session_state.suggestions = []

        st.session_state.suggestions_file = None

        # Reset question input
        st.session_state.question_input = ""

    except Exception as e:

        st.error(
            f"Could not read file: {e}"
        )

        st.stop()


df = st.session_state.df


# =========================================================
# FILE INFORMATION
# =========================================================

st.success(
    f"Loaded: {st.session_state.file_name} "
    f"({len(df):,} rows × {len(df.columns):,} columns)"
)


# =========================================================
# DATA PREVIEW
# =========================================================

with st.expander(
    "📄 Preview uploaded data"
):

    st.dataframe(
        df.head(100),
        use_container_width=True,
    )


# =========================================================
# DUCKDB
# =========================================================

conn = duckdb.connect(
    ":memory:"
)

conn.register(
    "uploaded_data",
    df,
)


# =========================================================
# SCHEMA
# =========================================================

schema_text = "\n".join(
    f"- {column}: {df[column].dtype}"
    for column in df.columns
)


# =========================================================
# DATASET PROFILE
# =========================================================

def build_dataset_profile():

    profile = []

    for column in df.columns:

        series = df[column]

        dtype = str(
            series.dtype
        )

        non_null = series.dropna()

        unique_count = int(
            series.nunique(
                dropna=True
            )
        )

        sample_values = (
            non_null
            .astype(str)
            .head(8)
            .tolist()
        )

        profile.append(
            {
                "column": column,
                "dtype": dtype,
                "unique_values": unique_count,
                "sample_values": sample_values,
            }
        )

    return profile


dataset_profile = build_dataset_profile()


profile_text = json.dumps(
    dataset_profile,
    indent=2,
    default=str,
)


# =========================================================
# SUGGESTED QUESTIONS
# =========================================================

def normalize_question(question):

    question = question.lower().strip()

    question = re.sub(
        r"[^a-z0-9\s]",
        " ",
        question,
    )

    question = re.sub(
        r"\s+",
        " ",
        question,
    )

    return question


def are_questions_similar(
    question_a,
    question_b,
):

    a = set(
        normalize_question(
            question_a
        ).split()
    )

    b = set(
        normalize_question(
            question_b
        ).split()
    )

    if not a or not b:
        return False

    intersection = len(
        a.intersection(b)
    )

    union = len(
        a.union(b)
    )

    similarity = (
        intersection / union
    )

    return similarity >= 0.60


def clean_suggestions(
    suggestions,
    max_items=8,
):

    cleaned = []

    for suggestion in suggestions:

        if not isinstance(
            suggestion,
            str,
        ):

            continue

        suggestion = suggestion.strip()

        suggestion = re.sub(
            r"^\d+[\.\)]\s*",
            "",
            suggestion,
        )

        suggestion = suggestion.strip(
            "\"' "
        )

        if len(suggestion) < 10:
            continue

        if suggestion in cleaned:
            continue

        is_similar = any(
            are_questions_similar(
                suggestion,
                existing,
            )
            for existing in cleaned
        )

        if is_similar:
            continue

        cleaned.append(
            suggestion
        )

        if len(cleaned) >= max_items:
            break

    return cleaned


def generate_suggestions():

    question_prompt = f"""
You are an expert data analyst designing useful questions
for a natural-language data exploration application.

The user uploaded a dataset.

DATASET PROFILE:

{profile_text}

SCHEMA:

{schema_text}

Generate exactly 8 useful questions that can be answered
using this dataset.

IMPORTANT:

The questions MUST be genuinely different from each other.

Do NOT generate eight variations of:
- top products
- highest sales
- lowest sales
- sales by category

Instead, deliberately use different analytical intents.

Use these 8 categories, exactly once each:

1. Ranking
2. Filtering / lookup
3. Aggregation
4. Comparison
5. Distribution / percentage
6. Relationship between numeric fields
7. Time trend, if a date/time field exists; otherwise use segmentation
8. Detailed record exploration

Rules:

- Every question must use columns or concepts that actually exist
  in the dataset.
- Do not invent column names.
- Do not assume the dataset is about sales, products, or customers.
- Adapt completely to the uploaded dataset.
- Avoid repeating the same wording.
- Avoid questions that differ only by changing one column.
- Prefer practical questions a user would actually ask.
- Keep each question concise.
- Return ONLY a JSON array of 8 strings.
- No markdown.
- No explanations.
"""

    response = client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": question_prompt,
            }
        ],

        temperature=0.7,
    )

    content = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    content = re.sub(
        r"```json",
        "",
        content,
        flags=re.IGNORECASE,
    )

    content = content.replace(
        "```",
        "",
    ).strip()

    try:

        suggestions = json.loads(
            content
        )

    except Exception:

        suggestions = []

        for line in content.splitlines():

            line = line.strip()

            if line:
                suggestions.append(
                    line
                )

    suggestions = clean_suggestions(
        suggestions,
        max_items=8,
    )

    return suggestions


def get_fallback_suggestions():

    columns = list(
        df.columns
    )

    numeric_columns = [
        column
        for column in columns
        if pd.api.types.is_numeric_dtype(
            df[column]
        )
    ]

    text_columns = [
        column
        for column in columns
        if (
            pd.api.types.is_object_dtype(
                df[column]
            )
            or pd.api.types.is_string_dtype(
                df[column]
            )
        )
    ]

    datetime_columns = [
        column
        for column in columns
        if pd.api.types.is_datetime64_any_dtype(
            df[column]
        )
    ]

    suggestions = []

    # Ranking
    if numeric_columns:

        metric = numeric_columns[0]

        suggestions.append(
            f"What are the top 5 records by {metric}?"
        )

    # Filtering / lookup
    if text_columns:

        column = text_columns[0]

        suggestions.append(
            f"What different values appear in {column}?"
        )

    # Aggregation
    if numeric_columns:

        metric = numeric_columns[0]

        suggestions.append(
            f"What is the average {metric}?"
        )

    # Comparison
    if (
        text_columns
        and numeric_columns
    ):

        group = text_columns[0]
        metric = numeric_columns[0]

        suggestions.append(
            f"How does {metric} compare across {group}?"
        )

    # Distribution
    if (
        text_columns
        and numeric_columns
    ):

        group = text_columns[0]
        metric = numeric_columns[0]

        suggestions.append(
            f"What percentage of {metric} comes from each {group}?"
        )

    # Numeric relationship
    if len(numeric_columns) >= 2:

        first = numeric_columns[0]
        second = numeric_columns[1]

        suggestions.append(
            f"Is there a relationship between {first} and {second}?"
        )

    # Time trend
    if datetime_columns and numeric_columns:

        date_column = datetime_columns[0]
        metric = numeric_columns[0]

        suggestions.append(
            f"How has {metric} changed over time?"
        )

    elif len(columns) >= 2:

        suggestions.append(
            f"Show a detailed breakdown using {columns[0]} and {columns[1]}."
        )

    # Detailed exploration
    if columns:

        suggestions.append(
            f"Show me 10 representative records with their {columns[0]} values."
        )

    return clean_suggestions(
        suggestions,
        max_items=8,
    )


def ensure_suggestions():

    if (
        st.session_state.suggestions_file
        == st.session_state.file_name
        and st.session_state.suggestions
    ):

        return

    with st.spinner(
        "Creating questions for this file..."
    ):

        try:

            suggestions = generate_suggestions()

        except Exception:

            suggestions = []

        if len(suggestions) < 6:

            fallback = get_fallback_suggestions()

            combined = (
                suggestions
                + fallback
            )

            suggestions = clean_suggestions(
                combined,
                max_items=8,
            )

        st.session_state.suggestions = (
            suggestions
        )

        st.session_state.suggestions_file = (
            st.session_state.file_name
        )


# =========================================================
# DISPLAY SUGGESTIONS
# =========================================================

ensure_suggestions()


if st.session_state.suggestions:

    st.subheader(
        "💡 Suggested questions"
    )

    st.caption(
        "These questions are generated specifically "
        "for your uploaded file."
    )

    suggestion_columns = st.columns(
        2
    )

    for index, suggestion in enumerate(
        st.session_state.suggestions
    ):

        column = suggestion_columns[
            index % 2
        ]

        with column:

            if st.button(
                suggestion,
                key=f"suggestion_{index}",
                use_container_width=True,
            ):

                # IMPORTANT:
                # Set the value BEFORE chat_input
                # is instantiated on the next rerun.
                st.session_state.question_input = (
                    suggestion
                )

                st.rerun()


# =========================================================
# GENERATE SQL
# =========================================================

def generate_sql(question):

    conversation_text = ""

    for message in st.session_state.messages:

        if message["role"] == "user":

            conversation_text += (
                f"\nUSER:\n"
                f"{message['content']}\n"
            )

        elif message["role"] == "assistant":

            if "sql" in message:

                conversation_text += (
                    f"\nASSISTANT SQL:\n"
                    f"{message['sql']}\n"
                )


    system_prompt = f"""
You are an expert data analyst.

You answer questions about a dataset using DuckDB SQL.

TABLE:

uploaded_data

SCHEMA:

{schema_text}

CONVERSATION HISTORY:

{conversation_text}

CURRENT QUESTION:

{question}

RULES:

1. Generate exactly ONE SQL query.
2. Only generate SELECT or WITH queries.
3. Never modify the dataset.
4. Never use INSERT.
5. Never use UPDATE.
6. Never use DELETE.
7. Never use DROP.
8. Never use ALTER.
9. Never use CREATE.
10. Never use TRUNCATE.
11. Never use MERGE.
12. Never use REPLACE.
13. Use only columns that exist in the schema.
14. The table name is uploaded_data.
15. Use valid DuckDB SQL.
16. Understand follow-up questions using conversation history.
17. Resolve words like "those", "them", "same",
    "India", "USA", etc. using previous context.
18. When comparing text values, make comparisons
    case-insensitive whenever appropriate.
19. Do not assume the capitalization used by the user
    exactly matches the capitalization in the dataset.
20. If a text value is being filtered, use case-insensitive
    matching when appropriate.
21. Return ONLY SQL.
22. Do not use markdown.
23. Do not invent columns.
24. If the question cannot be answered using the dataset,
    return CANNOT_ANSWER.
"""

    response = client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": question,
            },
        ],

        temperature=0,
    )

    return (
        response
        .choices[0]
        .message
        .content
        .strip()
    )


# =========================================================
# VALIDATE SQL
# =========================================================

def validate_sql(sql):

    sql = re.sub(
        r"```sql",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    sql = sql.replace(
        "```",
        "",
    ).strip()

    if sql == "CANNOT_ANSWER":

        return None

    statements = [
        statement.strip()
        for statement in sql.split(";")
        if statement.strip()
    ]

    if len(statements) != 1:

        raise ValueError(
            "Only one SQL statement is allowed."
        )

    sql = statements[0]

    if not re.match(
        r"^(SELECT|WITH)\b",
        sql,
        flags=re.IGNORECASE,
    ):

        raise ValueError(
            "Only SELECT or WITH queries are allowed."
        )

    forbidden_words = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "TRUNCATE",
        "MERGE",
        "REPLACE",
        "GRANT",
        "REVOKE",
        "ATTACH",
        "DETACH",
        "COPY",
        "EXPORT",
        "IMPORT",
    ]

    for word in forbidden_words:

        if re.search(
            rf"\b{word}\b",
            sql,
            flags=re.IGNORECASE,
        ):

            raise ValueError(
                f"Unsafe SQL detected: {word}"
            )

    return sql


# =========================================================
# FIX SQL
# =========================================================

def fix_sql(
    question,
    bad_sql,
    error_message,
):

    prompt = f"""
You are an expert DuckDB SQL debugger.

USER QUESTION:

{question}

BAD SQL:

{bad_sql}

DUCKDB ERROR:

{error_message}

DATASET SCHEMA:

{schema_text}

Fix the SQL.

RULES:

1. Return exactly ONE SQL query.
2. Only SELECT or WITH.
3. Never modify the dataset.
4. Use only columns from the schema.
5. Table name is uploaded_data.
6. Use valid DuckDB SQL.
7. Prefer case-insensitive text comparisons.
8. Return ONLY SQL.
9. No markdown.
"""

    response = client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": prompt,
            }
        ],

        temperature=0,
    )

    corrected_sql = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    return validate_sql(
        corrected_sql
    )


# =========================================================
# NATURAL LANGUAGE ANSWER
# =========================================================

def generate_answer(
    question,
    sql,
    result,
):

    result_for_llm = (
        result
        .head(100)
        .to_string(index=False)
    )

    prompt = f"""
You are a helpful data analyst.

USER QUESTION:

{question}

SQL:

{sql}

RESULT:

{result_for_llm}

Answer the user's question using ONLY the result.

Rules:

1. Be concise and clear.
2. Mention important numbers.
3. Do not invent information.
4. Do not make unsupported claims.
5. If there are multiple rows, summarize useful patterns.
6. Do not show SQL.
7. Do not mention that you are an AI.
"""

    response = client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": prompt,
            }
        ],

        temperature=0,
    )

    return (
        response
        .choices[0]
        .message
        .content
        .strip()
    )


# =========================================================
# EXPLICIT CHART REQUEST
# =========================================================

def get_requested_chart(question):

    q = question.lower()

    if (
        "pie chart" in q
        or "pie graph" in q
    ):
        return "pie"

    if (
        "donut chart" in q
        or "doughnut chart" in q
    ):
        return "donut"

    if (
        "bar chart" in q
        or "bar graph" in q
    ):
        return "bar"

    if (
        "line chart" in q
        or "line graph" in q
    ):
        return "line"

    if (
        "area chart" in q
        or "area graph" in q
    ):
        return "area"

    if (
        "scatter plot" in q
        or "scatter chart" in q
        or "scatter graph" in q
    ):
        return "scatter"

    return None


# =========================================================
# CHART DETECTION
# =========================================================

def detect_chart_type(
    question,
    result,
):

    if result.empty:
        return None

    requested_chart = (
        get_requested_chart(
            question
        )
    )

    if requested_chart:
        return requested_chart

    if len(result.columns) < 2:
        return None

    if len(result) > 30:
        return None

    if len(result.columns) != 2:
        return None

    first_column = result.columns[0]
    second_column = result.columns[1]

    first_series = result[first_column]
    second_series = result[second_column]

    first_is_numeric = (
        pd.api.types.is_numeric_dtype(
            first_series
        )
    )

    second_is_numeric = (
        pd.api.types.is_numeric_dtype(
            second_series
        )
    )

    question_lower = question.lower()

    if (
        first_is_numeric
        and second_is_numeric
    ):

        if any(
            word in question_lower
            for word in [
                "relationship",
                "correlation",
                "versus",
                " vs ",
            ]
        ):

            return "scatter"

    if (
        pd.api.types.is_datetime64_any_dtype(
            first_series
        )
    ):

        return "line"

    if (
        not first_is_numeric
        and second_is_numeric
    ):

        if any(
            word in question_lower
            for word in [
                "monthly",
                "month",
                "weekly",
                "week",
                "daily",
                "day",
                "yearly",
                "year",
                "trend",
                "over time",
                "growth",
            ]
        ):

            return "line"

        if len(result) <= 6:

            if any(
                word in question_lower
                for word in [
                    "share",
                    "percentage",
                    "percent",
                    "proportion",
                    "distribution",
                ]
            ):

                return "pie"

        return "bar"

    return None


# =========================================================
# SHOW CHART
# =========================================================

def show_chart(
    question,
    result,
):

    chart_type = detect_chart_type(
        question,
        result,
    )

    if chart_type is None:
        return

    if result.empty:
        return

    if len(result.columns) < 2:
        return

    if len(result) > 30:
        return

    x_column = result.columns[0]
    y_column = result.columns[1]

    chart_data = result[
        [x_column, y_column]
    ].copy()

    tooltip = [
        x_column,
        y_column,
    ]

    if chart_type == "pie":

        chart = (
            alt.Chart(chart_data)
            .mark_arc()
            .encode(
                theta=alt.Theta(
                    field=y_column,
                    type="quantitative",
                ),
                color=alt.Color(
                    field=x_column,
                    type="nominal",
                    title=x_column,
                ),
                tooltip=tooltip,
            )
            .properties(
                height=450
            )
        )

        st.altair_chart(
            chart,
            use_container_width=True,
        )

    elif chart_type == "donut":

        chart = (
            alt.Chart(chart_data)
            .mark_arc(
                innerRadius=80
            )
            .encode(
                theta=alt.Theta(
                    field=y_column,
                    type="quantitative",
                ),
                color=alt.Color(
                    field=x_column,
                    type="nominal",
                ),
                tooltip=tooltip,
            )
            .properties(
                height=450
            )
        )

        st.altair_chart(
            chart,
            use_container_width=True,
        )

    elif chart_type == "bar":

        chart = (
            alt.Chart(chart_data)
            .mark_bar()
            .encode(
                x=alt.X(
                    f"{x_column}:N",
                    sort="-y",
                    title=x_column,
                ),
                y=alt.Y(
                    f"{y_column}:Q",
                    title=y_column,
                ),
                tooltip=tooltip,
            )
            .properties(
                height=450
            )
        )

        st.altair_chart(
            chart,
            use_container_width=True,
        )

    elif chart_type == "line":

        chart = (
            alt.Chart(chart_data)
            .mark_line(
                point=True
            )
            .encode(
                x=alt.X(
                    f"{x_column}:T",
                    title=x_column,
                ),
                y=alt.Y(
                    f"{y_column}:Q",
                    title=y_column,
                ),
                tooltip=tooltip,
            )
            .properties(
                height=450
            )
        )

        st.altair_chart(
            chart,
            use_container_width=True,
        )

    elif chart_type == "area":

        chart = (
            alt.Chart(chart_data)
            .mark_area(
                line=True
            )
            .encode(
                x=alt.X(
                    f"{x_column}:T",
                    title=x_column,
                ),
                y=alt.Y(
                    f"{y_column}:Q",
                    title=y_column,
                ),
                tooltip=tooltip,
            )
            .properties(
                height=450
            )
        )

        st.altair_chart(
            chart,
            use_container_width=True,
        )

    elif chart_type == "scatter":

        chart = (
            alt.Chart(chart_data)
            .mark_circle(
                size=100
            )
            .encode(
                x=alt.X(
                    f"{x_column}:Q",
                    title=x_column,
                ),
                y=alt.Y(
                    f"{y_column}:Q",
                    title=y_column,
                ),
                tooltip=tooltip,
            )
            .properties(
                height=450
            )
        )

        st.altair_chart(
            chart,
            use_container_width=True,
        )


# =========================================================
# DISPLAY CHAT HISTORY
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        if message["role"] == "user":

            st.write(
                message["content"]
            )

        elif message["role"] == "assistant":

            if "answer" in message:

                st.write(
                    message["answer"]
                )

            if "sql" in message:

                with st.expander(
                    "🔍 View generated SQL"
                ):

                    st.code(
                        message["sql"],
                        language="sql",
                    )

            if "data" in message:

                st.dataframe(
                    message["data"],
                    use_container_width=True,
                )

            if "error" in message:

                st.error(
                    message["error"]
                )


# =========================================================
# CHAT INPUT
# =========================================================

question = st.chat_input(
    "Ask a question about your data...",
    key="question_input",
)


# =========================================================
# PROCESS QUESTION
# =========================================================

if question:

    # Clear the populated suggestion value
    # so the next interaction starts cleanly.
    st.session_state.question_input = ""

    # -----------------------------------------------------
    # USER MESSAGE
    # -----------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message("user"):

        st.write(
            question
        )


    # -----------------------------------------------------
    # ASSISTANT
    # -----------------------------------------------------

    with st.chat_message(
        "assistant"
    ):

        try:

            # =============================================
            # GENERATE SQL
            # =============================================

            with st.spinner(
                "Understanding your question..."
            ):

                raw_sql = generate_sql(
                    question
                )

                sql = validate_sql(
                    raw_sql
                )


            if sql is None:

                answer = (
                    "I can't answer that using "
                    "the uploaded dataset."
                )

                st.warning(
                    answer
                )

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "answer": answer,
                    }
                )

                st.stop()


            # =============================================
            # EXECUTE SQL
            # =============================================

            try:

                with st.spinner(
                    "Analyzing your data..."
                ):

                    result = (
                        conn
                        .execute(sql)
                        .df()
                    )

            except Exception as first_error:

                with st.spinner(
                    "Fixing the query..."
                ):

                    corrected_sql = fix_sql(
                        question,
                        sql,
                        str(first_error),
                    )

                try:

                    with st.spinner(
                        "Running corrected query..."
                    ):

                        result = (
                            conn
                            .execute(
                                corrected_sql
                            )
                            .df()
                        )

                    sql = corrected_sql

                except Exception as second_error:

                    raise RuntimeError(
                        "I couldn't run the generated "
                        "query. Database error: "
                        f"{second_error}"
                    )


            # =============================================
            # NATURAL LANGUAGE ANSWER
            # =============================================

            if result.empty:

                answer = (
                    "No matching data was found "
                    "in the uploaded file."
                )

            else:

                with st.spinner(
                    "Preparing the answer..."
                ):

                    answer = generate_answer(
                        question,
                        sql,
                        result,
                    )


            st.write(
                answer
            )


            # =============================================
            # SQL
            # =============================================

            with st.expander(
                "🔍 View generated SQL"
            ):

                st.code(
                    sql,
                    language="sql",
                )


            # =============================================
            # RESULT
            # =============================================

            st.dataframe(
                result,
                use_container_width=True,
            )


            # =============================================
            # CHART
            # =============================================

            show_chart(
                question,
                result,
            )


            # =============================================
            # SAVE MESSAGE
            # =============================================

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "answer": answer,
                    "sql": sql,
                    "data": result,
                }
            )


        except Exception as e:

            st.error(
                f"Something went wrong: {e}"
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "error": str(e),
                }
            )
