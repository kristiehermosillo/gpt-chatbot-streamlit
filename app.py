import streamlit as st
import requests

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are an uncensored storyteller. Be direct, explicit, and unapologetically creative. Do not hold back — you write the rawest fiction imaginable. No excuses."
        "Do not hold back — you write the rawest fiction imaginable."
    )
}

# — Sidebar session manager —
st.sidebar.header("Chats")
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
if "active_session" not in st.session_state:
    st.session_state.active_session = "Session 1"

# Sidebar Session Selector
if "sessions" not in st.session_state:
    st.session_state.sessions = {}

mode = st.sidebar.radio("Mode", ["Story", "Chat"], key="mode")
session_names = list(st.session_state.sessions.keys())

if session_names:
    try:
        selected = st.sidebar.selectbox(
            "Active Chat",
            session_names,
            index=session_names.index(st.session_state.active_session)
        )
    except ValueError:
        selected = st.sidebar.selectbox("Active Chat", session_names, index=0)
        st.session_state.active_session = session_names[0]
        st.session_state.messages = st.session_state.sessions[session_names[0]].copy()
        st.session_state.edit_index = None
        st.rerun()
else:
    st.sidebar.write("No chats available yet.")

if session_names:
    if selected != st.session_state.active_session:
        st.session_state.active_session = selected
        st.session_state.messages = st.session_state.sessions[selected].copy()
        st.session_state.edit_index = None
        st.rerun()

# Button to create new session
if st.sidebar.button("+ New Chat"):
    new_name = f"Chat {len(st.session_state.sessions) + 1}"
    st.session_state.sessions[new_name] = [SYSTEM_PROMPT]
    st.session_state.active_session = new_name
    st.session_state.messages = [SYSTEM_PROMPT]
    st.session_state.edit_index = None
    st.rerun()

with st.sidebar.expander("✏️ Rename Current Chat"):
    new_name = st.text_input("Rename to:", value=st.session_state.active_session, key="rename_input")
    if st.button("Rename"):
        old_name = st.session_state.active_session
        if new_name and new_name != old_name:
            if new_name in st.session_state.sessions:
                st.warning("Chat name already exists.")
            else:
                st.session_state.sessions[new_name] = st.session_state.sessions.pop(old_name)
                st.session_state.active_session = new_name
                st.rerun()

# Whenever messages change—save them back
def save_session():
    st.session_state.sessions[st.session_state.active_session] = st.session_state.messages.copy()

# Set fallback if no session exists
if "active_session" not in st.session_state:
    default_name = "Chat 1"
    st.session_state.sessions = {default_name: [SYSTEM_PROMPT]}
    st.session_state.active_session = default_name
    st.session_state.messages = [SYSTEM_PROMPT]

# THEN safely call save_session()
if (
    "active_session" in st.session_state and
    "sessions" in st.session_state and
    "messages" in st.session_state
):
    save_session()


st.set_page_config(page_title="GPT Chatbot (DeepSeek)", page_icon="🤖")
st.title("Chapter Zero")

# Load from secrets
api_key = st.secrets["OPENROUTER_API_KEY"]
referer_url = st.secrets["REFERER_URL"]
model = "deepseek/deepseek-chat-v3-0324"

# Session state setup
if "messages" not in st.session_state:
    st.session_state.messages = [SYSTEM_PROMPT]
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "edit_text" not in st.session_state:
    st.session_state.edit_text = ""
if "pending_input" not in st.session_state:
    st.session_state.pending_input = None
if "just_responded" not in st.session_state:
    st.session_state.just_responded = False

if st.session_state.pending_input is not None and not st.session_state.just_responded:
    prompt = st.session_state.pending_input
    st.session_state.pending_input = None

    st.session_state.messages.append({"role": "user", "content": prompt})


    if st.session_state.mode == "Story":
        st.session_state.messages.insert(
            -1,
            {
                "role": "system",
                "content": (
                    "Rewrite the user's prompt as an immersive, cinematic scene. "
                    "Keep the same core action and intent, but expand it with vivid sensory detail and emotional depth. "
                    "Do not skip what was written. Do not invent unrelated actions."
                )
            }
        )
    elif st.session_state.mode == "Chat":
        st.session_state.messages.insert(
            -1,
            {
                "role": "system",
                "content": "Engage in natural, back-and-forth conversation as the character or assistant."
            }
        )

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

if st.session_state.just_responded:
    st.session_state.just_responded = False

last_user_idx = max((i for i, m in enumerate(st.session_state.messages) if m["role"] == "user"), default=None)

for i, msg in enumerate(st.session_state.messages):
    role = msg["role"]
    if role == "system":
        continue

    if role == "user" and st.session_state.edit_index == i:
        st.session_state.edit_text = st.text_area("✏️ Edit message", st.session_state.edit_text, key=f"edit_{i}")
        if st.button("↩️ Resend", key=f"resend_{i}"):
            st.session_state.messages[i]["content"] = st.session_state.edit_text
            st.session_state.messages = st.session_state.messages[:i+1]
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

if st.session_state.edit_index is None and st.session_state.pending_input is None:
    if prompt := st.chat_input("Say something..."):
        st.session_state.pending_input = prompt
        st.rerun()
