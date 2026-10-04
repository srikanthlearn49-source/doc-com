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
# FILE UPLOAD
# =========================================================

uploaded_file = st.file_uploader(
    "Upload a CSV or Excel file",
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is None:

    st.info("Upload a CSV or Excel file to get started.")

    st.stop()


# =========================================================
# READ FILE
# =========================================================

try:

    if uploaded_file.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file)

    else:
        df = pd.read_excel(uploaded_file)

except Exception as e:

    st.error(f"Could not read the file: {e}")

    st.stop()


# =========================================================
# FILE INFORMATION
# =========================================================

st.success(
    f"Loaded: {uploaded_file.name} "
    f"({len(df):,} rows × {len(df.columns):,} columns)"
)


# =========================================================
# PREVIEW
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

    system_prompt = f"""
You are an expert data analyst.

The user has uploaded a dataset.

The DuckDB table name is:

uploaded_data

The dataset has these columns:

{schema_text}

Your task is to convert the user's natural language
question into ONE DuckDB SQL query.

IMPORTANT RULES:

1. Generate ONLY SELECT or WITH queries.
2. Never modify the data.
3. Never use INSERT.
4. Never use UPDATE.
5. Never use DELETE.
6. Never use DROP.
7. Never use ALTER.
8. Never use CREATE.
9. Never use TRUNCATE.
10. Use ONLY columns that exist in the dataset.
11. The table name is uploaded_data.
12. Use valid DuckDB SQL.
13. Return ONLY the SQL query.
14. Do not use markdown code fences.

If the question cannot be answered using the dataset,
return:

CANNOT_ANSWER
"""

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

    sql = response.choices[0].message.content.strip()

    return sql


# =========================================================
# SQL VALIDATION
# =========================================================

def validate_sql(sql):

    # Remove markdown if the model accidentally adds it
    sql = re.sub(
        r"```sql",
        "",
        sql,
        flags=re.IGNORECASE
    )

    sql = sql.replace("```", "").strip()

    if sql == "CANNOT_ANSWER":
        return None

    # Must start with SELECT or WITH
    if not re.match(
        r"^(SELECT|WITH)\b",
        sql,
        re.IGNORECASE
    ):
        raise ValueError(
            "Generated SQL is not a SELECT query."
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
            re.IGNORECASE
        ):

            raise ValueError(
                f"Unsafe SQL detected: {word}"
            )

    return sql


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

    # -----------------------------------------------------
    # Show question
    # -----------------------------------------------------

    with st.chat_message("user"):

        st.write(question)


    # -----------------------------------------------------
    # Generate and execute SQL
    # -----------------------------------------------------

    with st.chat_message("assistant"):

        try:

            with st.spinner("Generating SQL..."):

                raw_sql = generate_sql(question)

                sql = validate_sql(raw_sql)


            if sql is None:

                st.warning(
                    "I can't answer that question "
                    "using the uploaded data."
                )

                st.stop()


            # -------------------------------------------------
            # Execute SQL
            # -------------------------------------------------

            with st.spinner("Running query..."):

                result = conn.execute(sql).df()


            # -------------------------------------------------
            # Show SQL
            # -------------------------------------------------

            st.subheader("Generated SQL")

            st.code(
                sql,
                language="sql"
            )


            # -------------------------------------------------
            # Show result
            # -------------------------------------------------

            st.subheader("Result")

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


        except Exception as e:

            st.error(
                f"Something went wrong: {e}"
            )
