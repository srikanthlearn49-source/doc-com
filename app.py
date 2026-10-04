import streamlit as st
from groq import Groq

st.set_page_config(
    page_title="Chat With Your Data",
    page_icon="📊"
)

st.title("📊 Chat With Your Data")

# Get Groq API key from Streamlit Secrets
client = Groq(
    api_key=st.secrets["GROQ_API_KEY"]
)

st.success("Groq API key loaded successfully!")

question = st.text_input(
    "Ask Groq something"
)

if question:

    with st.spinner("Asking Groq..."):

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0
        )

        answer = response.choices[0].message.content

    st.write("### Groq's answer")

    st.write(answer)
