import streamlit as st
import pandas as pd
import duckdb
from groq import Groq
import re
import altair as alt


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="Chat With Your Data",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Chat With Your Data")
st.caption("Ask questions about your CSV or Excel data.")


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

if "sheets" not in st.session_state:
    st.session_state.sheets = {}

if "table_names" not in st.session_state:
    st.session_state.table_names = {}


# =========================================================
# FILE UPLOAD
# =========================================================

uploaded_file = st.file_uploader(
    "Upload CSV or Excel file",
    type=["csv", "xlsx", "xls"]
)


if uploaded_file is None:

    st.info(
        "Upload a CSV or Excel file to get started."
    )

    st.stop()


# =========================================================
# HELPER - SAFE TABLE NAME
# =========================================================

def make_safe_table_name(name, used_names=None):

    if used_names is None:
        used_names = set()

    table_name = re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        str(name)
    ).lower()

    table_name = table_name.strip("_")

    if not table_name:
        table_name = "uploaded_data"

    if table_name[0].isdigit():
        table_name = f"table_{table_name}"

    original_name = table_name
    counter = 2

    while table_name in used_names:

        table_name = (
            f"{original_name}_{counter}"
        )

        counter += 1

    return table_name


# =========================================================
# READ FILE
# =========================================================

if st.session_state.file_name != uploaded_file.name:

    try:

        sheets = {}
        table_names = {}
        used_table_names = set()

        # =================================================
        # CSV
        # =================================================

        if uploaded_file.name.lower().endswith(".csv"):

            df = pd.read_csv(
                uploaded_file
            )

            table_name = make_safe_table_name(
                "uploaded_data",
                used_table_names
            )

            sheets[table_name] = df

            table_names["uploaded_data"] = table_name

            used_table_names.add(
                table_name
            )


        # =================================================
        # EXCEL
        # =================================================

        else:

            excel_file = pd.ExcelFile(
                uploaded_file
            )

            for sheet_name in excel_file.sheet_names:

                sheet_df = pd.read_excel(
                    uploaded_file,
                    sheet_name=sheet_name
                )

                # Skip completely empty sheets
                if sheet_df.empty:
                    continue

                table_name = make_safe_table_name(
                    sheet_name,
                    used_table_names
                )

                sheets[table_name] = sheet_df

                table_names[sheet_name] = table_name

                used_table_names.add(
                    table_name
                )


        if not sheets:

            st.error(
                "The uploaded file does not contain "
                "any usable data."
            )

            st.stop()


        # =================================================
        # SAVE FILE DATA IN SESSION
        # =================================================

        st.session_state.sheets = sheets

        st.session_state.table_names = table_names

        st.session_state.file_name = (
            uploaded_file.name
        )

        # New file = new conversation
        st.session_state.messages = []


    except Exception as e:

        st.error(
            f"Could not read file: {e}"
        )

        st.stop()


# =========================================================
# FILE INFORMATION
# =========================================================

if len(st.session_state.sheets) == 1:

    only_table_name = next(
        iter(st.session_state.sheets)
    )

    only_df = (
        st.session_state.sheets[
            only_table_name
        ]
    )

    st.success(
        f"Loaded: {st.session_state.file_name} "
        f"({len(only_df):,} rows × "
        f"{len(only_df.columns):,} columns)"
    )

else:

    total_rows = sum(
        len(df)
        for df in st.session_state.sheets.values()
    )

    st.success(
        f"Loaded: {st.session_state.file_name} "
        f"({len(st.session_state.sheets)} "
        f"tables/sheets, "
        f"{total_rows:,} total rows)"
    )


# =========================================================
# DATA PREVIEW
# =========================================================

with st.expander(
    "📄 Preview uploaded data"
):

    for table_name, df in (
        st.session_state.sheets.items()
    ):

        st.markdown(
            f"### `{table_name}`"
        )

        st.caption(
            f"{len(df):,} rows × "
            f"{len(df.columns):,} columns"
        )

        st.dataframe(
            df.head(20),
            use_container_width=True
        )


# =========================================================
# DUCKDB
# =========================================================

conn = duckdb.connect(
    ":memory:"
)


for table_name, df in (
    st.session_state.sheets.items()
):

    conn.register(
        table_name,
        df
    )


# =========================================================
# DATABASE SCHEMA
# =========================================================

schema_parts = []

for table_name, df in (
    st.session_state.sheets.items()
):

    column_lines = []

    for column in df.columns:

        column_lines.append(
            f"  - {column}: "
            f"{df[column].dtype}"
        )

    columns_text = "\n".join(
        column_lines
    )

    schema_parts.append(
        f"""
TABLE: {table_name}

Columns:
{columns_text}
"""
    )


schema_text = "\n".join(
    schema_parts
)


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
                    "\nASSISTANT SQL:\n"
                    f"{message['sql']}\n"
                )


    system_prompt = f"""
You are an expert data analyst.

You answer questions about uploaded datasets
using DuckDB SQL.

AVAILABLE DATABASE TABLES:

{schema_text}

CONVERSATION HISTORY:

{conversation_text}

CURRENT QUESTION:

{question}

RULES:

1. Generate exactly ONE SQL query.

2. Only generate SELECT or WITH queries.

3. Never modify any dataset.

4. Never use INSERT.

5. Never use UPDATE.

6. Never use DELETE.

7. Never use DROP.

8. Never use ALTER.

9. Never use CREATE.

10. Never use TRUNCATE.

11. Never use MERGE.

12. Never use REPLACE.

13. Never use GRANT.

14. Never use REVOKE.

15. Never use ATTACH.

16. Never use DETACH.

17. Never use COPY.

18. Never use EXPORT.

19. Never use IMPORT.

20. Use only tables and columns that
    exist in the provided schema.

21. You may query one or more tables.

22. Use JOINs when the question requires
    combining multiple tables.

23. Understand follow-up questions using
    conversation history.

24. Resolve words such as:
    "those", "them", "same", "that",
    "previous", "above", etc. using
    conversation history.

25. When comparing text values, prefer
    case-insensitive comparisons using
    LOWER().

    Example:

    LOWER(Category) = LOWER('books')

26. Do not assume the capitalization used
    by the user exactly matches the data.

27. When the user asks for a ranking such as
    "top 5", use ORDER BY and LIMIT.

28. When calculating totals, use appropriate
    aggregation such as SUM().

29. When calculating averages, use AVG().

30. When counting records, use COUNT().

31. When grouping data, use GROUP BY.

32. Do not invent columns.

33. Do not invent tables.

34. Use valid DuckDB SQL.

35. Return ONLY SQL.

36. Do not use markdown code fences.

If the question cannot be answered using
the uploaded data, return:

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

    if sql is None:
        return None

    sql = re.sub(
        r"```sql",
        "",
        sql,
        flags=re.IGNORECASE
    )

    sql = re.sub(
        r"```",
        "",
        sql
    ).strip()


    if sql.upper() == "CANNOT_ANSWER":
        return None


    # =====================================================
    # ONLY ONE SQL STATEMENT
    # =====================================================

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


    # =====================================================
    # ONLY SELECT / WITH
    # =====================================================

    if not re.match(
        r"^(SELECT|WITH)\b",
        sql,
        flags=re.IGNORECASE
    ):

        raise ValueError(
            "Only SELECT or WITH queries "
            "are allowed."
        )


    # =====================================================
    # FORBIDDEN SQL
    # =====================================================

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
        "IMPORT"
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
# FIX SQL
# =========================================================

def fix_sql(
    question,
    bad_sql,
    error_message
):

    prompt = f"""
You are an expert DuckDB SQL debugger.

The user asked:

{question}

The SQL generated was:

{bad_sql}

DuckDB returned this error:

{error_message}

AVAILABLE DATABASE TABLES:

{schema_text}

Fix the SQL query.

RULES:

1. Return exactly ONE SQL query.

2. Only generate SELECT or WITH queries.

3. Never use INSERT.

4. Never use UPDATE.

5. Never use DELETE.

6. Never use DROP.

7. Never use ALTER.

8. Never use CREATE.

9. Never use TRUNCATE.

10. Never use MERGE.

11. Never use REPLACE.

12. Never use GRANT.

13. Never use REVOKE.

14. Never use ATTACH.

15. Never use DETACH.

16. Never use COPY.

17. Never use EXPORT.

18. Never use IMPORT.

19. Use only tables and columns
    that exist in the schema.

20. You may use JOINs when required.

21. Use valid DuckDB SQL.

22. Prefer case-insensitive text
    comparisons using LOWER().

23. Do not invent columns.

24. Do not invent tables.

25. Return ONLY the corrected SQL.

26. Do not use markdown code fences.
"""


    response = client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": prompt
            }
        ],

        temperature=0
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
# GENERATE NATURAL LANGUAGE ANSWER
# =========================================================

def generate_answer(
    question,
    sql,
    result
):

    result_for_llm = (
        result
        .head(100)
        .to_string(index=False)
    )


    prompt = f"""
You are a helpful data analyst.

The user asked:

{question}

The SQL query used was:

{sql}

The query returned:

{result_for_llm}

Answer the user's question using
ONLY the query result.

RULES:

1. Be concise and clear.

2. Mention important numbers.

3. Do not invent information.

4. Do not claim anything that isn't
   supported by the result.

5. If there are multiple rows,
   summarize the important pattern.

6. Do not show SQL.

7. Do not mention internal implementation
   details.

8. Do not say you looked at data that
   isn't present in the result.
"""


    response = client.chat.completions.create(

        model=MODEL,

        messages=[
            {
                "role": "system",
                "content": prompt
            }
        ],

        temperature=0
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
        or "column chart" in q
        or "column graph" in q
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
# DETECT DATE-LIKE COLUMN
# =========================================================

def is_date_like(series):

    if pd.api.types.is_datetime64_any_dtype(
        series
    ):
        return True

    if not (
        pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
    ):
        return False

    if len(series) == 0:
        return False

    sample = (
        series
        .dropna()
        .astype(str)
        .head(50)
    )

    if sample.empty:
        return False

    converted = pd.to_datetime(
        sample,
        errors="coerce"
    )

    success_rate = (
        converted.notna().mean()
    )

    return success_rate >= 0.8


# =========================================================
# CHART TYPE DETECTION
# =========================================================

def detect_chart_type(
    question,
    result
):

    if result.empty:
        return None


    # User explicitly requested a chart
    requested_chart = get_requested_chart(
        question
    )

    if requested_chart:
        return requested_chart


    if len(result.columns) < 2:
        return None


    # Automatic charts work best with
    # exactly two useful columns
    if len(result.columns) != 2:
        return None


    question_lower = question.lower()


    first_column = result.columns[0]
    second_column = result.columns[1]


    first_series = result[
        first_column
    ]

    second_series = result[
        second_column
    ]


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


    # =====================================================
    # DATE/TIME + NUMERIC → LINE
    # =====================================================

    if (
        is_date_like(first_series)
        and second_is_numeric
    ):

        return "line"


    # =====================================================
    # NUMERIC + NUMERIC → SCATTER
    # =====================================================

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
                "compare"
            ]
        ):

            return "scatter"


    # =====================================================
    # CATEGORY + NUMERIC
    # =====================================================

    if (
        not first_is_numeric
        and second_is_numeric
    ):

        # Time/trend questions
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
                "over time",
                "trend",
                "growth"
            ]
        ):

            return "line"


        # Share/distribution
        if any(
            word in question_lower
            for word in [
                "share",
                "percentage",
                "percent",
                "proportion",
                "distribution"
            ]
        ):

            if len(result) <= 8:
                return "pie"


        # Ranking/comparison
        return "bar"


    return None


# =========================================================
# SHOW CHART
# =========================================================

def show_chart(
    question,
    result
):

    chart_type = detect_chart_type(
        question,
        result
    )


    if chart_type is None:
        return


    if result.empty:
        return


    if len(result.columns) < 2:
        return


    if len(result) > 30:
        st.info(
            "The result contains too many "
            "categories for a readable chart."
        )
        return


    x_column = result.columns[0]
    y_column = result.columns[1]


    chart_data = result[
        [x_column, y_column]
    ].copy()


    # =====================================================
    # PIE
    # =====================================================

    if chart_type == "pie":

        chart = (
            alt.Chart(chart_data)
            .mark_arc()
            .encode(

                theta=alt.Theta(
                    field=y_column,
                    type="quantitative"
                ),

                color=alt.Color(
                    field=x_column,
                    type="nominal",
                    title=x_column
                ),

                tooltip=[
                    x_column,
                    y_column
                ]
            )
            .properties(
                height=450,
                title="Share of Total"
            )
        )


        st.altair_chart(
            chart,
            use_container_width=True
        )


    # =====================================================
    # DONUT
    # =====================================================

    elif chart_type == "donut":

        chart = (
            alt.Chart(chart_data)
            .mark_arc(
                innerRadius=80
            )
            .encode(

                theta=alt.Theta(
                    field=y_column,
                    type="quantitative"
                ),

                color=alt.Color(
                    field=x_column,
                    type="nominal",
                    title=x_column
                ),

                tooltip=[
                    x_column,
                    y_column
                ]
            )
            .properties(
                height=450,
                title="Share of Total"
            )
        )


        st.altair_chart(
            chart,
            use_container_width=True
        )


    # =====================================================
    # BAR
    # =====================================================

    elif chart_type == "bar":

        chart = (
            alt.Chart(chart_data)
            .mark_bar()
            .encode(

                x=alt.X(
                    f"{x_column}:N",
                    sort="-y",
                    title=x_column
                ),

                y=alt.Y(
                    f"{y_column}:Q",
                    title=y_column
                ),

                tooltip=[
                    x_column,
                    y_column
                ]
            )
            .properties(
                height=450
            )
        )


        st.altair_chart(
            chart,
            use_container_width=True
        )


    # =====================================================
    # LINE
    # =====================================================

    elif chart_type == "line":

        line_data = chart_data.copy()


        # Convert date-like first column
        # to actual datetime for Altair
        if not pd.api.types.is_datetime64_any_dtype(
            line_data[x_column]
        ):

            converted_dates = pd.to_datetime(
                line_data[x_column],
                errors="coerce"
            )

            if converted_dates.notna().all():

                line_data[x_column] = (
                    converted_dates
                )


        chart = (
            alt.Chart(line_data)
            .mark_line(
                point=True
            )
            .encode(

                x=alt.X(
                    f"{x_column}:T",
                    title=x_column
                ),

                y=alt.Y(
                    f"{y_column}:Q",
                    title=y_column
                ),

                tooltip=[
                    x_column,
                    y_column
                ]
            )
            .properties(
                height=450
            )
        )


        st.altair_chart(
            chart,
            use_container_width=True
        )


    # =====================================================
    # AREA
    # =====================================================

    elif chart_type == "area":

        area_data = chart_data.copy()


        if not pd.api.types.is_datetime64_any_dtype(
            area_data[x_column]
        ):

            converted_dates = pd.to_datetime(
                area_data[x_column],
                errors="coerce"
            )

            if converted_dates.notna().all():

                area_data[x_column] = (
                    converted_dates
                )


        chart = (
            alt.Chart(area_data)
            .mark_area(
                line=True
            )
            .encode(

                x=alt.X(
                    f"{x_column}:T",
                    title=x_column
                ),

                y=alt.Y(
                    f"{y_column}:Q",
                    title=y_column
                ),

                tooltip=[
                    x_column,
                    y_column
                ]
            )
            .properties(
                height=450
            )
        )


        st.altair_chart(
            chart,
            use_container_width=True
        )


    # =====================================================
    # SCATTER
    # =====================================================

    elif chart_type == "scatter":

        chart = (
            alt.Chart(chart_data)
            .mark_circle(
                size=100
            )
            .encode(

                x=alt.X(
                    f"{x_column}:Q",
                    title=x_column
                ),

                y=alt.Y(
                    f"{y_column}:Q",
                    title=y_column
                ),

                tooltip=[
                    x_column,
                    y_column
                ]
            )
            .properties(
                height=450
            )
        )


        st.altair_chart(
            chart,
            use_container_width=True
        )


# =========================================================
# DISPLAY CHAT HISTORY
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        # =================================================
        # USER
        # =================================================

        if message["role"] == "user":

            st.write(
                message["content"]
            )


        # =================================================
        # ASSISTANT
        # =================================================

        elif message["role"] == "assistant":

            # ---------------------------------------------
            # Natural-language answer
            # ---------------------------------------------

            if "answer" in message:

                st.write(
                    message["answer"]
                )


            # ---------------------------------------------
            # SQL
            # ---------------------------------------------

            if "sql" in message:

                with st.expander(
                    "🔍 View generated SQL"
                ):

                    st.code(
                        message["sql"],
                        language="sql"
                    )


            # ---------------------------------------------
            # Data
            # ---------------------------------------------

            if "data" in message:

                st.dataframe(
                    message["data"],
                    use_container_width=True
                )


            # ---------------------------------------------
            # Chart
            # ---------------------------------------------

            if (
                "question" in message
                and "data" in message
            ):

                show_chart(
                    message["question"],
                    message["data"]
                )


            # ---------------------------------------------
            # Error
            # ---------------------------------------------

            if "error" in message:

                st.error(
                    message["error"]
                )


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

    # =====================================================
    # USER MESSAGE
    # =====================================================

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )


    with st.chat_message("user"):

        st.write(question)


    # =====================================================
    # ASSISTANT
    # =====================================================

    with st.chat_message("assistant"):

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


            # =============================================
            # CANNOT ANSWER
            # =============================================

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
                        "question": question
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

                    result = conn.execute(
                        sql
                    ).df()


            except Exception as first_error:

                # =========================================
                # FIRST SQL FAILED
                # =========================================

                with st.spinner(
                    "Fixing the query..."
                ):

                    corrected_sql = fix_sql(
                        question,
                        sql,
                        str(first_error)
                    )


                if corrected_sql is None:

                    raise RuntimeError(
                        "The generated query "
                        "could not be corrected."
                    )


                # =========================================
                # SECOND ATTEMPT
                # =========================================

                try:

                    with st.spinner(
                        "Running corrected query..."
                    ):

                        result = conn.execute(
                            corrected_sql
                        ).df()


                    sql = corrected_sql


                except Exception as second_error:

                    raise RuntimeError(
                        "I couldn't run the generated "
                        "query after one automatic "
                        "correction attempt.\n\n"
                        f"Database error: "
                        f"{second_error}"
                    )


            # =============================================
            # GENERATE ANSWER
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
                        result
                    )


            # =============================================
            # DISPLAY ANSWER
            # =============================================

            st.write(
                answer
            )


            # =============================================
            # DISPLAY SQL
            # =============================================

            with st.expander(
                "🔍 View generated SQL"
            ):

                st.code(
                    sql,
                    language="sql"
                )


            # =============================================
            # DISPLAY RESULT
            # =============================================

            st.dataframe(
                result,
                use_container_width=True
            )


            # =============================================
            # DISPLAY CHART
            # =============================================

            show_chart(
                question,
                result
            )


            # =============================================
            # SAVE ASSISTANT MESSAGE
            # =============================================

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "answer": answer,
                    "sql": sql,
                    "data": result,
                    "question": question
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
                    "question": question
                }
            )
