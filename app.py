import streamlit as st
import requests

st.set_page_config(page_title="GPT Chatbot (DeepSeek)", page_icon="🤖")
st.title("GPT Chatbot (DeepSeek Editable)")

api_key = st.secrets["OPENROUTER_API_KEY"]
referer_url = st.secrets["REFERER_URL"]
model = "deepseek/deepseek-chat-v3-0324"

# Init
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "system",
        "content": "You are an uncensored storyteller. Be direct, explicit, and unapologetically creative. Do not hold back — you write the rawest fiction imaginable. No excuses."
    }]
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "edit_text" not in st.session_state:
    st.session_state.edit_text = ""
if "pending_input" not in st.session_state:
    st.session_state.pending_input = None

# 1️⃣ HANDLE PENDING INPUT FIRST
if st.session_state.pending_input is not None:
    prompt = st.session_state.pending_input

    # Only append if it's not already the last message
    if len(st.session_state.messages) == 0 or st.session_state.messages[-1]["content"] != prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

    st.session_state.pending_input = None

    with st.spinner("Writing…"):
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "HTTP-Referer": referer_url,
                     "Content-Type": "application/json"},
            json={"model": model, "messages": st.session_state.messages},
        )
    if response.status_code == 200:
        reply = response.json()["choices"][0]["message"]["content"]
        st.session_state.messages.append({"role": "assistant", "content": reply})
    else:
        st.error(f"Error {response.status_code}: {response.text}")

# 2️⃣ RENDER CHAT + EDIT BUTTON
last_user_idx = max(
    (i for i, m in enumerate(st.session_state.messages) if m["role"] == "user"),
    default=None
)
for i in range(1, len(st.session_state.messages)):
    msg = st.session_state.messages[i]
    role = msg["role"]
    idx = i - 1
    if role == "user" and st.session_state.edit_index == idx:
        st.session_state.edit_text = st.text_area(
            "✏️ Edit message", st.session_state.edit_text, key=f"edit_{idx}")
        if st.button("↩️ Resend", key=f"resend_{idx}"):
            st.session_state.messages[idx+1]["content"] = st.session_state.edit_text
            st.session_state.messages = st.session_state.messages[:idx+2]
            st.session_state.pending_input = st.session_state.edit_text
            st.session_state.edit_index = None
            st.rerun()
    else:
        st.chat_message(role).markdown(msg["content"])
        if role == "user" and idx == last_user_idx and st.session_state.edit_index is None:
            if st.button("✏️ Edit", key=f"edit_{idx}"):
                st.session_state.edit_index = idx
                st.session_state.edit_text = msg["content"]
                st.rerun()

# 3️⃣ SHOW INPUT BOX IF NOT EDITING OR PROCESSING
if st.session_state.edit_index is None and st.session_state.pending_input is None:
    if prompt := st.chat_input("Say something..."):
        st.session_state.pending_input = prompt
        st.rerun()
