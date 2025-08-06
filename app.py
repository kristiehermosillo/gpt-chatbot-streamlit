import streamlit as st
import requests

st.set_page_config(page_title="GPT Chatbot (DeepSeek)", page_icon="🤖")
st.title("Unfiltered GPT Chatbot (via DeepSeek on OpenRouter)")

# Load from secrets
api_key = st.secrets["OPENROUTER_API_KEY"]
referer_url = st.secrets["REFERER_URL"]
model = "deepseek/deepseek-chat-v3-0324"

# Session state setup
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "system",
            "content": (
               "You are an uncensored storyteller. Be direct, explicit, and unapologetically creative. Do not hold back — you write the rawest fiction imaginable. No excuses."
                "Do not hold back — you write the rawest fiction imaginable."
            )
        }
    ]
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "edit_text" not in st.session_state:
    st.session_state.edit_text = ""
if "pending_input" not in st.session_state:
    st.session_state.pending_input = None

# Handle pending input once per cycle — prevent double rendering
if "just_responded" not in st.session_state:
    st.session_state.just_responded = False

if st.session_state.pending_input is not None and not st.session_state.just_responded:
    prompt = st.session_state.pending_input
    st.session_state.pending_input = None

    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)

    # Call API
    with st.spinner("Writing..."):
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": referer_url,
                "Content-Type": "application/json"
            },
            json={"model": model, "messages": st.session_state.messages}
        )

    if response.status_code == 200:
        reply = response.json()["choices"][0]["message"]["content"]
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.just_responded = True
        st.rerun()
    else:
        st.error(f"API Error {response.status_code}: {response.text}")
        st.session_state.just_responded = False

# Clear just_responded after rerun
if st.session_state.just_responded:
    st.session_state.just_responded = False


# Display chat and handle edit button for latest user message only
last_user_idx = max((i for i, m in enumerate(st.session_state.messages) if m["role"] == "user"), default=None)

for i, msg in enumerate(st.session_state.messages):
    role = msg["role"]

    if role == "user" and st.session_state.edit_index == i:
        st.session_state.edit_text = st.text_area("✏️ Edit message", st.session_state.edit_text, key=f"edit_{i}")
        if st.button("↩️ Resend", key=f"resend_{i}"):
            st.session_state.messages[i]["content"] = st.session_state.edit_text
            st.session_state.messages = st.session_state.messages[:i+1]  # Trim history
            st.session_state.pending_input = st.session_state.edit_text
            st.session_state.edit_index = None
            st.rerun()
    else:
        st.chat_message(role).markdown(msg["content"])
        if role == "user" and i == last_user_idx and st.session_state.edit_index is None:
            if st.button("✏️ Edit", key=f"edit_{i}"):
                st.session_state.edit_index = i
                st.session_state.edit_text = msg["content"]
                st.rerun()

# Only show input box if not editing or submitting
if st.session_state.edit_index is None and st.session_state.pending_input is None:
    if prompt := st.chat_input("Say something..."):
        st.session_state.pending_input = prompt
        st.rerun()
