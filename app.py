import streamlit as st
import pandas as pd
import duckdb
from groq import Groq
import re


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="Chat With Your Data",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Chat With Your Data")


# =========================================================
# GROQ
# =========================================================

client = Groq(
    api_key=st.secrets["GROQ_API_KEY"]
)

MODEL = "openai/gpt-oss-20b"


# =========================================================
# SESSION STATE
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "file_name" not in st.session_state:
    st.session_state.file_name = None

if "df" not in st.session_state:
    st.session_state.df = None


# =========================================================
# FILE UPLOAD
# =========================================================

uploaded_file = st.file_uploader(
    "Upload CSV or Excel file",
    type=["csv", "xlsx", "xls"]
)


if uploaded_file is None:

    st.info("Upload a CSV or Excel file to get started.")

    st.stop()


# =========================================================
# READ NEW FILE
# =========================================================

if st.session_state.file_name != uploaded_file.name:

    try:

        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)

        else:
            df = pd.read_excel(uploaded_file)

        st.session_state.df = df
        st.session_state.file_name = uploaded_file.name

        # New file = new conversation
        st.session_state.messages = []

    except Exception as e:

        st.error(f"Could not read file: {e}")

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

with st.expander("📄 Preview uploaded data"):

    st.dataframe(
        df.head(100),
        use_container_width=True
    )


# =========================================================
# DUCKDB
# =========================================================

conn = duckdb.connect(":memory:")

conn.register(
    "uploaded_data",
    df
)


# =========================================================
# SCHEMA
# =========================================================

schema_text = "\n".join(
    f"- {column}: {df[column].dtype}"
    for column in df.columns
)


# =========================================================
# GENERATE SQL
# =========================================================

def generate_sql(question):

    # ---------------------------------------------
    # Build conversation context
    # ---------------------------------------------

    conversation_text = ""

    for message in st.session_state.messages:

        if message["role"] == "user":

            conversation_text += (
                f"\nUSER:\n{message['content']}\n"
            )

        elif message["role"] == "assistant":

            if "sql" in message:

                conversation_text += (
                    f"\nASSISTANT SQL:\n"
                    f"{message['sql']}\n"
                )


    # ---------------------------------------------
    # System prompt
    # ---------------------------------------------

    system_prompt = f"""
You are an expert data analyst.

You answer questions about a dataset using DuckDB SQL.

TABLE:

uploaded_data

SCHEMA:

{schema_text}

CONVERSATION HISTORY:

{conversation_text}

CURRENT USER QUESTION:

{question}

IMPORTANT RULES:

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
16. Understand follow-up questions using the conversation history.
17. If the user says things like "those", "them", "same",
    "only India", etc., resolve the meaning using the
    previous conversation.
18. Return ONLY SQL.
19. Do not use markdown code fences.

If the question cannot be answered from the dataset,
return exactly:

CANNOT_ANSWER
"""

    # ---------------------------------------------
    # Ask Groq
    # ---------------------------------------------

    response = client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": question
            }
        ],

        temperature=0
    )

    return response.choices[0].message.content.strip()


# =========================================================
# VALIDATE SQL
# =========================================================

def validate_sql(sql):

    sql = re.sub(
        r"```sql",
        "",
        sql,
        flags=re.IGNORECASE
    )

    sql = sql.replace("```", "").strip()

    if sql == "CANNOT_ANSWER":
        return None

    if not re.match(
        r"^(SELECT|WITH)\b",
        sql,
        flags=re.IGNORECASE
    ):
        raise ValueError(
            "Only SELECT queries are allowed."
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
        "REPLACE"
    ]

    for word in forbidden_words:

        if re.search(
            rf"\b{word}\b",
            sql,
            flags=re.IGNORECASE
        ):
            raise ValueError(
                f"Unsafe SQL detected: {word}"
            )

    return sql


# =========================================================
# DISPLAY PREVIOUS CONVERSATION
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        if message["role"] == "user":

            st.write(message["content"])

        elif message["role"] == "assistant":

            if "sql" in message:

                st.write("**Generated SQL**")

                st.code(
                    message["sql"],
                    language="sql"
                )

            if "data" in message:

                st.write("**Result**")

                st.dataframe(
                    message["data"],
                    use_container_width=True
                )

            if "error" in message:

                st.error(message["error"])


# =========================================================
# CHAT INPUT
# =========================================================

question = st.chat_input(
    "Ask a question about your data..."
)


# =========================================================
# PROCESS QUESTION
# =========================================================

if question:

    # ---------------------------------------------
    # Save user message
    # ---------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    with st.chat_message("user"):

        st.write(question)


    # ---------------------------------------------
    # Assistant
    # ---------------------------------------------

    with st.chat_message("assistant"):

        try:

            with st.spinner("Generating SQL..."):

                raw_sql = generate_sql(question)

                sql = validate_sql(raw_sql)


            if sql is None:

                answer = (
                    "I can't answer that using "
                    "the uploaded dataset."
                )

                st.warning(answer)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "error": answer
                    }
                )

                st.stop()


            # -----------------------------------------
            # Execute SQL
            # -----------------------------------------

            with st.spinner("Running query..."):

                result = conn.execute(sql).df()


            # -----------------------------------------
            # Display SQL
            # -----------------------------------------

            st.write("### Generated SQL")

            st.code(
                sql,
                language="sql"
            )


            # -----------------------------------------
            # Display result
            # -----------------------------------------

            st.write("### Result")

            if result.empty:

                st.info(
                    "The query ran successfully, "
                    "but returned no rows."
                )

            else:

                st.dataframe(
                    result,
                    use_container_width=True
                )


            # -----------------------------------------
            # Save assistant message
            # -----------------------------------------

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "sql": sql,
                    "data": result
                }
            )


        except Exception as e:

            st.error(
                f"Something went wrong: {e}"
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "error": str(e)
                }
            )
