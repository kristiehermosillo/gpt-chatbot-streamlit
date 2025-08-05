import streamlit as st
import requests

st.set_page_config(page_title="GPT Chatbot (OpenRouter)", page_icon="🤖")

st.title("GPT Chatbot (via OpenRouter)")

# Load keys from secrets
api_key = st.secrets["OPENROUTER_API_KEY"]
referer_url = st.secrets["REFERER_URL"]

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

# Show messages
for msg in st.session_state.messages[1:]:
    st.chat_message(msg["role"]).markdown(msg["content"])

# Input
if prompt := st.chat_input("Say something..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Thinking..."):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": referer_url,
            "Content-Type": "application/json"
        }

        payload = {
            "model": "mistralai/mistral-7b-instruct",  # or any model you want
            "messages": st.session_state.messages
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            st.chat_message("assistant").markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        else:
            st.error(f"API Error: {response.status_code}")
