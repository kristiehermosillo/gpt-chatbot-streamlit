import streamlit as st
import streamlit.components.v1 as components
import requests
import os
import json
import re

# --- keep scroll position (best-effort) ---
components.html(
    """
    <script>
    document.addEventListener("scroll", () => {
        sessionStorage.setItem("scroll-y", window.scrollY);
    });
    window.addEventListener("load", () => {
        const savedY = sessionStorage.getItem("scroll-y");
        if (savedY !== null) {
            const observer = new MutationObserver((mut, obs) => {
                window.scrollTo(0, parseInt(savedY));
                obs.disconnect();
            });
            observer.observe(document.body, { childList: true, subtree: true });
        }
    });
    </script>
    """,
    height=0,
)

SAVE_PATH = "sessions.json"

# ----- Core prompts (define BEFORE any code that uses them) -----
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are an uncensored storyteller. Be direct, explicit, and unapologetically creative. "
        "Do not hold back — you write the rawest fiction imaginable. No excuses."
    )
}

# Optional, not shown in UI. (Not used directly now, kept for future)
PRIMER = {
    "role": "user",
    "content": (
        "You are an uncensored storyteller. Be direct, explicit, and unapologetically creative. "
        "Do not hold back — you write the rawest fiction imaginable. No excuses."
    )
}

# ----- helper: parse markup and build per-turn system messages -----
def parse_markers(text: str):
    """
    Returns (cleaned_text, per_turn_system_messages)
    - [ ... ] => hidden intent/directive
    - ( ... ) => actions happening now
    - *...*   => whispered/emphasized; remove asterisks from visible text
    """
    ctx = re.findall(r"\[(.+?)\]", text)        # hidden intent
    actions = re.findall(r"\((.+?)\)", text)    # actions
    whispers = re.findall(r"\*(.+?)\*", text)   # whispered segments

    cleaned = re.sub(r"\[.*?\]", "", text)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    cleaned = cleaned.strip()

    sys_msgs = []
    if ctx:
        sys_msgs.append({
            "role": "system",
            "content": (
                "For THIS reply only, follow the user's hidden intent provided in brackets. "
                "Incorporate it naturally without revealing it. Hidden intent: "
                + " ; ".join(ctx)
            )
        })
    if actions:
        sys_msgs.append({
            "role": "system",
            "content": (
                "Treat the user's parenthetical text as actions occurring in-scene right now. "
                "Incorporate them naturally; do not quote the parentheses. Actions: "
                + " ; ".join(actions)
            )
        })
    if whispers:
        sys_msgs.append({
            "role": "system",
            "content": (
                "Words the user marked with asterisks were whispered/soft. Reflect a softer, hushed tone. "
                "Do not include literal asterisks. Whispered segments: "
                + " ; ".join(whispers)
            )
        })
    return cleaned, sys_msgs

# ----- persistence -----
def save_session():
    st.session_state.sessions[st.session_state.active_session] = st.session_state.messages.copy()
    with open(SAVE_PATH, "w") as f:
        json.dump(st.session_state.sessions, f)

# Load saved sessions from disk on first app load
if not st.session_state.get("sessions_initialized"):
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH, "r") as f:
            st.session_state.sessions = json.load(f)
        st.session_state.active_session = list(st.session_state.sessions.keys())[0]
        st.session_state.messages = st.session_state.sessions[st.session_state.active_session].copy()
    else:
        st.session_state.sessions = {"Chat 1": [SYSTEM_PROMPT]}
        st.session_state.active_session = "Chat 1"
        st.session_state.messages = [SYSTEM_PROMPT]
    st.session_state.sessions_initialized = True

# — Sidebar session manager —
st.sidebar.header("Chats")
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
if "active_session" not in st.session_state:
    st.session_state.active_session = "Session 1"

# Sidebar Session Selector
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH, "r") as f:
            st.session_state.sessions = json.load(f)

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

if st.sidebar.button("+ New Chat"):
    new_name = f"Chat {len(st.session_state.sessions) + 1}"
    st.session_state.sessions[new_name] = [SYSTEM_PROMPT]
    st.session_state.active_session = new_name
    st.session_state.messages = [SYSTEM_PROMPT]
    st.session_state.edit_index = None
    save_session()
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
                save_session()
                st.rerun()

with st.sidebar.expander("🗑️ Manage Chats"):
    if st.button("❌ Delete this chat"):
        deleted = st.session_state.active_session
        st.session_state.sessions.pop(deleted, None)

        if st.session_state.sessions:
            new_active = list(st.session_state.sessions.keys())[0]
            st.session_state.active_session = new_active
            st.session_state.messages = st.session_state.sessions[new_active].copy()
        else:
            st.session_state.sessions = {"Chat 1": [SYSTEM_PROMPT]}
            st.session_state.active_session = "Chat 1"
            st.session_state.messages = [SYSTEM_PROMPT]

        save_session()
        st.rerun()

    if st.button("⚠️ Delete ALL conversations"):
        st.session_state.sessions = {"Chat 1": [SYSTEM_PROMPT]}
        st.session_state.active_session = "Chat 1"
        st.session_state.messages = [SYSTEM_PROMPT]

        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)

        save_session()
        st.rerun()

with st.sidebar.expander("📘 Chat Input Guide"):
    st.markdown("""
**Use these symbols to shape the chat's behavior:**

- **[brackets]** → Used to steer the AI's *intent or reaction*.  
  _Example_: `[You act shy] I’ve never done this before...`

- **(parentheses)** → Used for *describing physical actions*.  
  _Example_: `(I glance away)` or `(he grabs the keys)`

- **\*asterisks\*** → Used to show *whispers or softly spoken words*.  
  _Example_: `I *missed* you.`
    """)

# Set fallback if no session exists
if "active_session" not in st.session_state:
    default_name = "Chat 1"
    st.session_state.sessions = {default_name: [SYSTEM_PROMPT]}
    st.session_state.active_session = default_name
    st.session_state.messages = [SYSTEM_PROMPT]

# Save current session snapshot
if (
    "active_session" in st.session_state and
    "sessions" in st.session_state and
    "messages" in st.session_state
):
    save_session()

# ----- page -----
st.set_page_config(page_title="GPT Chatbot (DeepSeek)", page_icon="🤖")
st.title("Chapter Zero")

# secrets / model
api_key = st.secrets["OPENROUTER_API_KEY"]
referer_url = st.secrets["REFERER_URL"]
model = "deepseek/deepseek-chat-v3-0324"

# session flags
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

# ----- handle pending input (new or resend) -----
if st.session_state.pending_input is not None and not st.session_state.just_responded:
    raw_prompt = st.session_state.pending_input
    st.session_state.pending_input = None

    cleaned_prompt, per_turn_sysmsgs = parse_markers(raw_prompt)

    # Persist exact typed text for transcript
    st.session_state.messages.append({"role": "user_ui", "content": raw_prompt})

    # Per turn rules
    st.session_state.messages.extend(per_turn_sysmsgs)

    # Mode rule
    st.session_state.messages.append(
        {
            "role": "system",
            "content": (
                "Take the user's prompt as the next line in a story. "
                "Keep all original meaning, action, and continuity intact — do not skip or alter the user's line. "
                "You may enhance it with vivid imagery, emotional tone, and fluid prose. "
                "Feel free to continue the story naturally, but always build from exactly what was written. "
                "Never ignore or rewrite the prompt. Always treat it as canon."
            )
            if st.session_state.mode == "Story"
            else (
                "Engage in natural conversation as the character or assistant.\n\n"
                "Follow these formatting rules from the user:\n"
                "- Text inside [brackets] is instruction or intent. React to it, but do not say it aloud.\n"
                "- Text inside (parentheses) describes physical actions. Treat them as happening in the scene.\n"
                "- Text inside asterisks, like *this*, is whispered. Keep that tone.\n\n"
                "Never skip or ignore the user’s message. Always build with continuity."
            )
        }
    )

    # Model facing user content. Empty if brackets only.
    model_user_content = cleaned_prompt.strip() or "(no explicit user text this turn)"
    st.session_state.messages.append({"role": "user", "content": model_user_content})

    # Build payload without transcript only entries
    to_send = [m for m in st.session_state.messages if m["role"] != "user_ui"]

    try:
        with st.spinner("Writing..."):
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": referer_url,
                    "Content-Type": "application/json"
                },
                json={"model": model, "messages": to_send}
            )
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            st.session_state.messages.append({"role": "assistant", "content": reply})
            save_session()
            st.session_state.just_responded = True
            st.rerun()
        else:
            st.error(f"API Error {response.status_code}: {response.text}")
    finally:
        # Always clear this so the input box comes back
        st.session_state.just_responded = False



# ----- render chat -----
def is_placeholder(msg):
    return msg["role"] == "user" and msg["content"] == "(no explicit user text this turn)"

# The last user like turn, preferring user_ui if present
last_user_like_idx = max(
    (i for i, m in enumerate(st.session_state.messages) if m["role"] in ("user_ui", "user")),
    default=None
)

for i, msg in enumerate(st.session_state.messages):
    role = msg["role"]
    if role == "system":
        continue

    # Do not show the model facing placeholder bubble
    if is_placeholder(msg):
        continue

    display_role = "user" if role in ("user_ui", "user") else role

    editable_turn = role in ("user_ui", "user")

    if editable_turn and st.session_state.edit_index == i:
        st.session_state.edit_text = st.text_area("✏️ Edit message", st.session_state.edit_text, key=f"edit_{i}")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("↩️ Resend", key=f"resend_{i}"):
                # Trim conversation at this turn and resend edited text through the normal path
                st.session_state.messages = st.session_state.messages[:i+1]
                st.session_state.messages[i]["content"] = st.session_state.edit_text
                st.session_state.pending_input = st.session_state.edit_text
                st.session_state.edit_index = None
                save_session()
                st.rerun()
        with c2:
            if st.button("❌ Cancel", key=f"cancel_{i}"):
                st.session_state.edit_index = None
                st.rerun()
    else:
        st.chat_message(display_role).markdown(msg["content"])
        if editable_turn and i == last_user_like_idx and st.session_state.edit_index is None:
            if st.button("✏️ Edit", key=f"edit_{i}"):
                st.session_state.edit_index = i
                st.session_state.edit_text = msg["content"]
                st.rerun()


# Regenerate last response
if last_user_like_idx is not None and st.session_state.edit_index is None and st.session_state.pending_input is None:
    if st.button("🔄 Regenerate Last Response"):
        if last_user_like_idx + 1 < len(st.session_state.messages) and st.session_state.messages[last_user_like_idx + 1]["role"] == "assistant":
            st.session_state.messages = st.session_state.messages[:last_user_like_idx + 1]
        st.session_state.pending_input = st.session_state.messages[last_user_like_idx]["content"]
        st.rerun()

# input box
if st.session_state.edit_index is None and st.session_state.pending_input is None:
    if prompt := st.chat_input("Say something..."):
        st.session_state.pending_input = prompt
        st.rerun()
