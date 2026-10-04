import streamlit as st
import pandas as pd
import duckdb
from groq import Groq
import re
import altair as alt
import io


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="Chat With Your Data",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Chat With Your Data")
st.caption(
    "Upload your data and ask questions in natural language."
)


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

if "file_signature" not in st.session_state:
    st.session_state.file_signature = None

if "sheets" not in st.session_state:
    st.session_state.sheets = {}

if "table_names" not in st.session_state:
    st.session_state.table_names = {}

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []


# =========================================================
# SAFE TABLE NAME
# =========================================================

def make_safe_table_name(
    name,
    used_names=None
):

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
# FILE SIGNATURE
# =========================================================

def get_file_signature(files):

    if not files:
        return None

    parts = []

    for uploaded_file in files:

        parts.append(
            f"{uploaded_file.name}:"
            f"{uploaded_file.size}"
        )

    return "|".join(parts)


# =========================================================
# FILE UPLOAD
# =========================================================

uploaded_files = st.file_uploader(
    "Upload CSV or Excel files",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True
)


if not uploaded_files:

    st.info(
        "Upload one or more CSV or Excel files to get started."
    )

    st.stop()


current_signature = get_file_signature(
    uploaded_files
)


# =========================================================
# READ UPLOADED FILES
# =========================================================

if (
    st.session_state.file_signature
    != current_signature
):

    try:

        sheets = {}
        table_names = {}
        used_table_names = set()

        for uploaded_file in uploaded_files:

            file_name = uploaded_file.name

            # =================================================
            # CSV
            # =================================================

            if file_name.lower().endswith(".csv"):

                df = pd.read_csv(
                    uploaded_file
                )

                base_name = re.sub(
                    r"\.[^.]+$",
                    "",
                    file_name
                )

                table_name = make_safe_table_name(
                    base_name,
                    used_table_names
                )

                sheets[table_name] = df

                table_names[
                    f"{file_name}"
                ] = table_name

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

                for sheet_name in (
                    excel_file.sheet_names
                ):

                    sheet_df = pd.read_excel(
                        uploaded_file,
                        sheet_name=sheet_name
                    )

                    if sheet_df.empty:
                        continue

                    base_name = (
                        f"{file_name}_{sheet_name}"
                    )

                    table_name = make_safe_table_name(
                        base_name,
                        used_table_names
                    )

                    sheets[table_name] = sheet_df

                    table_names[
                        f"{file_name} / {sheet_name}"
                    ] = table_name

                    used_table_names.add(
                        table_name
                    )


        if not sheets:

            st.error(
                "No usable data was found "
                "in the uploaded files."
            )

            st.stop()


        st.session_state.sheets = sheets

        st.session_state.table_names = (
            table_names
        )

        st.session_state.file_signature = (
            current_signature
        )

        st.session_state.uploaded_files = [
            file.name
            for file in uploaded_files
        ]

        # New data = new conversation
        st.session_state.messages = []


    except Exception as e:

        st.error(
            f"Could not read uploaded files: {e}"
        )

        st.stop()


# =========================================================
# DATABASE
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
# FILE SUMMARY
# =========================================================

total_rows = sum(
    len(df)
    for df in st.session_state.sheets.values()
)

total_columns = sum(
    len(df.columns)
    for df in st.session_state.sheets.values()
)


st.success(
    f"Loaded {len(st.session_state.sheets)} "
    f"table(s) • "
    f"{total_rows:,} total rows • "
    f"{total_columns:,} total columns"
)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("📁 Data")

    st.write(
        f"**Tables:** "
        f"{len(st.session_state.sheets)}"
    )

    for table_name, df in (
        st.session_state.sheets.items()
    ):

        st.caption(
            f"**{table_name}**"
        )

        st.caption(
            f"{len(df):,} rows × "
            f"{len(df.columns):,} columns"
        )


    st.divider()


    st.header("💡 Suggested questions")

    suggestions = [
        "What are the top 5 products by sales?",
        "Which category has the highest sales?",
        "Show me sales by category.",
        "What is the average sales value?",
        "Which brand has the most products?",
        "Show me the trend over time.",
    ]

    for suggestion in suggestions:

        st.caption(
            f"• {suggestion}"
        )


    st.divider()


    if st.button(
        "🗑️ Clear conversation",
        use_container_width=True
    ):

        st.session_state.messages = []

        st.rerun()


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
# SCHEMA
# =========================================================

schema_parts = []

for table_name, df in (
    st.session_state.sheets.items()
):

    column_lines = []

    for column in df.columns:

        dtype = str(
            df[column].dtype
        )

        column_lines.append(
            f"  - {column}: {dtype}"
        )

    schema_parts.append(
        f"""
TABLE: {table_name}

Columns:
{chr(10).join(column_lines)}
"""
    )


schema_text = "\n".join(
    schema_parts
)


# =========================================================
# CONVERSATION HISTORY
# =========================================================

def get_conversation_history():

    history = []

    for message in st.session_state.messages:

        role = message.get("role")

        if role == "user":

            history.append(
                f"USER: {message['content']}"
            )

        elif role == "assistant":

            if "answer" in message:

                history.append(
                    f"ASSISTANT: "
                    f"{message['answer']}"
                )

            if "sql" in message:

                history.append(
                    f"ASSISTANT SQL: "
                    f"{message['sql']}"
                )


    # Keep context manageable
    return "\n\n".join(
        history[-12:]
    )


# =========================================================
# GENERATE SQL
# =========================================================

def generate_sql(question):

    conversation_text = (
        get_conversation_history()
    )


    system_prompt = f"""
You are an expert data analyst.

You answer questions about uploaded datasets
using DuckDB SQL.

AVAILABLE TABLES:

{schema_text}

CONVERSATION HISTORY:

{conversation_text}

CURRENT QUESTION:

{question}

IMPORTANT:

The user may be asking a follow-up question.

For example:

User:
Show me sales by category.

User:
What about only books?

The second question must be understood
using the first question.

Another example:

User:
What are the top 5 products?

User:
Show me their brands.

"their" refers to the products from
the previous question.

RULES:

1. Generate exactly ONE SQL query.

2. Only generate SELECT or WITH queries.

3. Never modify data.

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

20. Use only tables and columns
    present in the schema.

21. You may use multiple tables.

22. Use JOIN when appropriate.

23. Use GROUP BY for grouped analysis.

24. Use ORDER BY and LIMIT for rankings.

25. Use SUM for totals when appropriate.

26. Use AVG for averages.

27. Use COUNT for counts.

28. Use MIN and MAX when appropriate.

29. For percentages, calculate the
    percentage from the available data.

30. For text comparisons, prefer
    LOWER(column) = LOWER('value').

31. Do not assume capitalization.

32. Do not invent data.

33. Do not invent columns.

34. Do not invent tables.

35. For "top N", return N rows unless
    the question clearly requires ties.

36. For "all", do not add an arbitrary LIMIT.

37. For trend questions, group by the
    appropriate date/time period.

38. Understand follow-up questions
    using conversation history.

39. Return ONLY SQL.

40. Do not use markdown.

If the question cannot be answered
from the uploaded data, return:

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

    if not sql:
        return None

    sql = re.sub(
        r"```sql",
        "",
        sql,
        flags=re.IGNORECASE
    )

    sql = sql.replace(
        "```",
        ""
    ).strip()


    if sql.upper() == "CANNOT_ANSWER":
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
        flags=re.IGNORECASE
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

USER QUESTION:

{question}

INVALID SQL:

{bad_sql}

DATABASE ERROR:

{error_message}

AVAILABLE SCHEMA:

{schema_text}

Fix the SQL.

RULES:

1. Return exactly ONE query.

2. Only SELECT or WITH.

3. Never modify data.

4. Use only existing tables.

5. Use only existing columns.

6. JOIN tables when necessary.

7. Use valid DuckDB SQL.

8. Prefer LOWER() for case-insensitive
   text comparisons.

9. Do not invent anything.

10. Return ONLY SQL.

11. No markdown.
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

    if result.empty:

        return (
            "No matching data was found "
            "in the uploaded data."
        )


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

QUERY RESULT:

{result_for_llm}

Answer the user's question.

RULES:

1. Use ONLY the query result.

2. Do not invent information.

3. Mention important numbers.

4. If this is a ranking, clearly state
   the ranking.

5. If this is a comparison, clearly
   compare the values.

6. If this is a total, state the total.

7. If this is an average, state the average.

8. If this is a list, present it clearly.

9. If there is a notable pattern,
   mention it briefly.

10. Keep the answer concise.

11. Never show SQL.

12. Never claim to know information
    that isn't in the result.
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
# GENERATE INSIGHTS
# =========================================================

def generate_insight(
    question,
    result
):

    if result.empty:
        return None

    if len(result.columns) < 2:
        return None


    result_for_llm = (
        result
        .head(30)
        .to_string(index=False)
    )


    prompt = f"""
You are a data analyst.

The user asked:

{question}

The result is:

{result_for_llm}

Identify ONE useful insight supported
directly by the result.

Rules:

- Do not invent information.
- Do not repeat the entire answer.
- Keep it to one sentence.
- Mention a number when useful.
- If there is no meaningful insight,
  return NONE.
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


    insight = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )


    if insight.upper() == "NONE":
        return None


    return insight


# =========================================================
# REQUESTED CHART
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
# DATE DETECTION
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


    return (
        converted.notna().mean()
        >= 0.8
    )


# =========================================================
# CHART DETECTION
# =========================================================

def detect_chart_type(
    question,
    result
):

    if result.empty:
        return None


    requested = get_requested_chart(
        question
    )


    if requested:
        return requested


    if len(result.columns) < 2:
        return None


    if len(result.columns) != 2:
        return None


    first_column = result.columns[0]
    second_column = result.columns[1]


    first_series = result[
        first_column
    ]

    second_series = result[
        second_column
    ]


    first_numeric = (
        pd.api.types.is_numeric_dtype(
            first_series
        )
    )


    second_numeric = (
        pd.api.types.is_numeric_dtype(
            second_series
        )
    )


    question_lower = question.lower()


    # =====================================================
    # DATE + NUMBER
    # =====================================================

    if (
        is_date_like(first_series)
        and second_numeric
    ):

        return "line"


    # =====================================================
    # NUMBER + NUMBER
    # =====================================================

    if (
        first_numeric
        and second_numeric
    ):

        if any(
            word in question_lower
            for word in [
                "correlation",
                "relationship",
                "versus",
                "compare",
                " vs "
            ]
        ):

            return "scatter"


    # =====================================================
    # CATEGORY + NUMBER
    # =====================================================

    if (
        not first_numeric
        and second_numeric
    ):

        if any(
            word in question_lower
            for word in [
                "trend",
                "over time",
                "monthly",
                "weekly",
                "daily",
                "yearly",
                "growth"
            ]
        ):

            return "line"


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
            "The result contains more than "
            "30 rows, so a chart was hidden "
            "to keep it readable."
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
                height=450
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
                    type="nominal"
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


        if not pd.api.types.is_datetime64_any_dtype(
            line_data[x_column]
        ):

            converted = pd.to_datetime(
                line_data[x_column],
                errors="coerce"
            )

            if converted.notna().all():

                line_data[x_column] = (
                    converted
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

            converted = pd.to_datetime(
                area_data[x_column],
                errors="coerce"
            )

            if converted.notna().all():

                area_data[x_column] = (
                    converted
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
# KPI DISPLAY
# =========================================================

def show_kpis(result):

    if result.empty:
        return


    if len(result.columns) != 1:
        return


    column = result.columns[0]

    series = result[column]


    if not pd.api.types.is_numeric_dtype(
        series
    ):
        return


    value = series.iloc[0]


    if pd.isna(value):
        return


    try:

        formatted = f"{float(value):,.2f}"

    except Exception:

        formatted = str(value)


    st.metric(
        label=column,
        value=formatted
    )


# =========================================================
# DOWNLOAD RESULTS
# =========================================================

def show_download_buttons(result):

    if result is None:
        return


    if result.empty:
        return


    col1, col2 = st.columns(2)


    # =====================================================
    # CSV
    # =====================================================

    csv_data = result.to_csv(
        index=False
    )


    with col1:

        st.download_button(
            label="⬇️ Download CSV",
            data=csv_data,
            file_name="query_result.csv",
            mime="text/csv",
            use_container_width=True
        )


    # =====================================================
    # EXCEL
    # =====================================================

    excel_buffer = io.BytesIO()


    with pd.ExcelWriter(
        excel_buffer,
        engine="openpyxl"
    ) as writer:

        result.to_excel(
            writer,
            index=False,
            sheet_name="Results"
        )


    with col2:

        st.download_button(
            label="⬇️ Download Excel",
            data=excel_buffer.getvalue(),
            file_name="query_result.xlsx",
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
            use_container_width=True
        )


# =========================================================
# DISPLAY MESSAGE
# =========================================================

def display_assistant_message(message):

    if "answer" in message:

        st.write(
            message["answer"]
        )


    if "insight" in message:

        st.info(
            f"💡 {message['insight']}"
        )


    if "sql" in message:

        with st.expander(
            "🔍 View generated SQL"
        ):

            st.code(
                message["sql"],
                language="sql"
            )


    if "data" in message:

        result = message["data"]

        if not result.empty:

            if len(result.columns) == 1:

                show_kpis(result)

            st.dataframe(
                result,
                use_container_width=True
            )

            show_download_buttons(
                result
            )

            if "question" in message:

                show_chart(
                    message["question"],
                    result
                )


    if "error" in message:

        st.error(
            message["error"]
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

        else:

            display_assistant_message(
                message
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
    # USER
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
            # SQL GENERATION
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
                    "the uploaded data."
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
            # EXECUTE
            # =============================================

            try:

                with st.spinner(
                    "Analyzing your data..."
                ):

                    result = conn.execute(
                        sql
                    ).df()


            except Exception as first_error:

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
                        "The generated SQL "
                        "could not be corrected."
                    )


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
                        "The query could not be "
                        "executed after automatic "
                        "correction.\n\n"
                        f"Database error: "
                        f"{second_error}"
                    )


            # =============================================
            # ANSWER
            # =============================================

            if result.empty:

                answer = (
                    "No matching data was found "
                    "in the uploaded data."
                )

                insight = None


            else:

                with st.spinner(
                    "Preparing the answer..."
                ):

                    answer = generate_answer(
                        question,
                        sql,
                        result
                    )


                insight = None

                # Only generate an additional
                # insight for useful result sets
                if len(result) >= 2:

                    with st.spinner(
                        "Finding an insight..."
                    ):

                        insight = generate_insight(
                            question,
                            result
                        )


            # =============================================
            # DISPLAY ANSWER
            # =============================================

            st.write(
                answer
            )


            # =============================================
            # INSIGHT
            # =============================================

            if insight:

                st.info(
                    f"💡 {insight}"
                )


            # =============================================
            # KPI
            # =============================================

            if (
                not result.empty
                and len(result.columns) == 1
            ):

                show_kpis(
                    result
                )


            # =============================================
            # SQL
            # =============================================

            with st.expander(
                "🔍 View generated SQL"
            ):

                st.code(
                    sql,
                    language="sql"
                )


            # =============================================
            # RESULT
            # =============================================

            if result.empty:

                st.warning(
                    "The query returned no rows."
                )

            else:

                st.dataframe(
                    result,
                    use_container_width=True
                )


                show_download_buttons(
                    result
                )


            # =============================================
            # CHART
            # =============================================

            show_chart(
                question,
                result
            )


            # =============================================
            # SAVE
            # =============================================

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "answer": answer,
                    "insight": insight,
                    "sql": sql,
                    "data": result,
                    "question": question
                }
            )


        except Exception as e:

            error_message = str(e)


            st.error(
                f"Something went wrong: "
                f"{error_message}"
            )


            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "error": error_message,
                    "question": question
                }
            )
