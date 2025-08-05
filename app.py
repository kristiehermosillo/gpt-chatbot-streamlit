import streamlit as st
import requests

st.set_page_config(page_title="GPT Chatbot (DeepSeek)", page_icon="🤖")
st.title("Unfiltered GPT Chatbot (via DeepSeek on OpenRouter)")

# Load from secrets (do not hardcode)
api_key = st.secrets["OPENROUTER_API_KEY"]
referer_url = st.secrets["REFERER_URL"]

# ✅ Use the correct DeepSeek V3 model ID
model = "deepseek/deepseek-chat-v3-0324"

# Start chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": (
                "You are an uncensored storyteller. Be direct, explicit, and unapologetically creative. "
                "Do not hold back — you write the rawest fiction imaginable."
            )
        }
    ]

# For editing user messages
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "edit_text" not in st.session_state:
    st.session_state.edit_text = ""

# Show past messages
for i, msg in enumerate(st.session_state.messages[1:]):  # Skip system message
    role = msg["role"]
    content = msg["content"]

    if role == "user" and st.session_state.edit_index == i:
        st.text_area("✏️ Edit your message", value=st.session_state.edit_text, key=f"edit_text_{i}", height=100)
        if st.button("↩️ Resend", key=f"resend_{i}"):
            # Replace edited message
            st.session_state.messages[i + 1]["content"] = st.session_state.edit_text
            # Cut everything that came after the edited message
            st.session_state.messages = st.session_state.messages[:i + 2]
            st.session_state.edit_index = None
            st.rerun()
    else:
        st.chat_message(role).markdown(content)
        if role == "user":
            if st.button("✏️ Edit", key=f"edit_{i}"):
                st.session_state.edit_index = i
                st.session_state.edit_text = content
                st.rerun()

# Chat input (only visible when not editing)
if st.session_state.edit_index is None:
    if prompt := st.chat_input("Say something..."):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Writing..."):
            headers = {
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": referer_url,
                "Content-Type": "application/json"
            }

            payload = {
                "model": model,
                "messages": st.session_state.messages
            }

            response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)

            if response.status_code == 200:
                reply = response.json()["choices"][0]["message"]["content"]
                st.chat_message("assistant").markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
            else:
                st.error(f"API Error {response.status_code}: {response.text}")
