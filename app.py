import streamlit as st
import pandas as pd
import duckdb


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
    f"Loaded: {uploaded_file.name}"
)

col1, col2 = st.columns(2)

with col1:
    st.metric("Rows", f"{len(df):,}")

with col2:
    st.metric("Columns", f"{len(df.columns):,}")


# =========================================================
# PREVIEW
# =========================================================

st.subheader("📄 Data Preview")

st.dataframe(
    df.head(100),
    use_container_width=True
)


# =========================================================
# COLUMN INFORMATION
# =========================================================

st.subheader("📋 Columns")

column_info = pd.DataFrame({
    "Column": df.columns,
    "Data Type": [
        str(df[column].dtype)
        for column in df.columns
    ]
})

st.dataframe(
    column_info,
    use_container_width=True,
    hide_index=True
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
# TEST QUERY
# =========================================================

st.subheader("🧪 DuckDB Test")

try:

    result = conn.execute(
        "SELECT * FROM uploaded_data LIMIT 10"
    ).df()

    st.write("DuckDB successfully queried your uploaded file:")

    st.dataframe(
        result,
        use_container_width=True
    )

except Exception as e:

    st.error(
        f"DuckDB query failed: {e}"
    )
