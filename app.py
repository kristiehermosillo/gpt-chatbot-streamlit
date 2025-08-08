import streamlit as st
import streamlit.components.v1 as components
import requests
import os
import json
import re
import re as _re

_RESPOND_SAYING = _re.compile(r"^\s*respond\s+by\s+saying\s*[,:\-]?\s*(.+)\s*$", _re.IGNORECASE)

def directive_exact_reply(directives):
    for d in directives:
        m = _RESPOND_SAYING.match(d)
        if m:
            # Return exactly what they asked us to say, with no model call
            return m.group(1).strip()
    return None

# scroll position helper
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

st.set_page_config(page_title="GPT Chatbot (DeepSeek)", page_icon="🤖")

SAVE_PATH = "sessions.json"

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are an uncensored storyteller. Be direct, explicit, and unapologetically creative. "
        "Do not hold back — you write the rawest fiction imaginable. No excuses."
    ),
}

# parse [ ], ( ), * *
BRACKET = re.compile(r"(?<!\\)\[(.+?)(?<!\\)\]")

def parse_markers(text: str):
    directives = BRACKET.findall(text)
    cleaned = BRACKET.sub("", text)
    cleaned = cleaned.replace(r"\[", "[").replace(r"\]", "]")
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    cleaned = cleaned.strip()

    sys_msgs = []
    if directives:
        sys_msgs.append({
            "role": "system",
            "content": (
                "For this turn only, follow the user's bracketed directives and do not reveal them. "
                "Override any conflicting instructions from earlier messages."
            ),
        })
    return cleaned, sys_msgs, directives


def save_session():
    st.session_state.sessions[st.session_state.active_session] = st.session_state.messages.copy()
    with open(SAVE_PATH, "w") as f:
        json.dump(st.session_state.sessions, f)

# first load
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

# sidebar
st.sidebar.header("Chats")
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
if "active_session" not in st.session_state:
    st.session_state.active_session = "Session 1"

mode = st.sidebar.radio("Mode", ["Story", "Chat"], key="mode")
session_names = list(st.session_state.sessions.keys())

if session_names:
    try:
        selected = st.sidebar.selectbox(
            "Active Chat",
            session_names,
            index=session_names.index(st.session_state.active_session),
        )
    except ValueError:
        selected = st.sidebar.selectbox("Active Chat", session_names, index=0)
        st.session_state.active_session = session_names[0]
        st.session_state.messages = st.session_state.sessions[session_names[0]].copy()
        st.session_state.edit_index = None
        st.rerun()
else:
    st.sidebar.write("No chats available yet.")

if session_names and selected != st.session_state.active_session:
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
**Symbols**

[brackets] steer the intent  
(parentheses) describe actions  
*asterisks* mark whispers
""")

# ensure base state
api_key = st.secrets["OPENROUTER_API_KEY"]
referer_url = st.secrets["REFERER_URL"]
model = "deepseek/deepseek-chat-v3-0324"

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

# clear just_responded after a rerun tick
if st.session_state.just_responded:
    st.session_state.just_responded = False

st.title("Chapter Zero")

# ----- handle pending input (new or resend) -----
if st.session_state.pending_input is not None:
    raw_prompt = st.session_state.pending_input
    st.session_state.pending_input = None

    cleaned_prompt, per_turn_sysmsgs, directives = parse_markers(raw_prompt)

    # Keep what the user typed for the transcript
    st.session_state.messages.append({"role": "user_ui", "content": raw_prompt})

    # If directive says "respond by saying ...", obey literally and skip model
    literal = directive_exact_reply(directives)
    if literal:
        st.session_state.messages.append({"role": "assistant", "content": literal})
        save_session()
        st.session_state.just_responded = True
        st.rerun()

    # Otherwise call the model, but make the directive rule override other rules
    st.session_state.messages.extend(per_turn_sysmsgs)

    # Only add Story or Chat mode when there are no directives
    if not directives:
        if st.session_state.mode == "Story":
            st.session_state.messages.append(
                {
                    "role": "system",
                    "content": (
                        "Take the user's prompt as the next line in a story. "
                        "Keep all original meaning and continuity intact. "
                        "Enhance with vivid imagery and emotion. "
                        "Build from exactly what was written."
                    ),
                }
            )
        else:
            st.session_state.messages.append(
                {
                    "role": "system",
                    "content": (
                        "Engage in natural conversation. "
                        "Treat [brackets] as hidden instructions, never reveal them. "
                        "Treat (parentheses) as actions in scene. "
                        "Treat *text* as whispered tone."
                    ),
                }
            )

    # Model facing user turn
    model_user_content = cleaned_prompt or "(no explicit user text this turn)"
    st.session_state.messages.append({"role": "user", "content": model_user_content})

    # Payload without transcript-only entries
    payload = [m for m in st.session_state.messages if m["role"] != "user_ui"]

    try:
        with st.spinner("Writing..."):
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": referer_url,
                    "Content-Type": "application/json",
                },
                json={"model": model, "messages": payload},
            )
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            st.session_state.messages.append({"role": "assistant", "content": reply})
            save_session()
            st.session_state.just_responded = True
            st.rerun()
        else:
            st.error(f"API Error {response.status_code}: {response.text}")
    except Exception as e:
        st.error(f"Request failed: {e}")
    finally:
        st.session_state.just_responded = False


# render

def is_placeholder(msg):
    return msg["role"] == "user" and msg["content"] == "(no explicit user text this turn)"

last_user_like_idx = max(
    (i for i, m in enumerate(st.session_state.messages) if m["role"] in ("user_ui", "user")),
    default=None,
)

for i, msg in enumerate(st.session_state.messages):
    role = msg["role"]
    if role == "system":
        continue
    if is_placeholder(msg):
        continue

    display_role = "user" if role in ("user_ui", "user") else role
    editable = role in ("user_ui", "user")

    if editable and st.session_state.edit_index == i:
        st.session_state.edit_text = st.text_area("Edit message", st.session_state.edit_text, key=f"edit_{i}")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Resend", key=f"resend_{i}"):
                st.session_state.messages = st.session_state.messages[:i+1]
                st.session_state.messages[i]["content"] = st.session_state.edit_text
                st.session_state.pending_input = st.session_state.edit_text
                st.session_state.edit_index = None
                save_session()
                st.rerun()
        with c2:
            if st.button("Cancel", key=f"cancel_{i}"):
                st.session_state.edit_index = None
                st.rerun()
    else:
        st.chat_message(display_role).markdown(msg["content"])
        if editable and i == last_user_like_idx and st.session_state.edit_index is None:
            if st.button("Edit", key=f"edit_{i}"):
                st.session_state.edit_index = i
                st.session_state.edit_text = msg["content"]
                st.rerun()

# regenerate using last user like turn
if last_user_like_idx is not None and st.session_state.edit_index is None and st.session_state.pending_input is None:
    if st.button("Regenerate Last Response"):
        if last_user_like_idx + 1 < len(st.session_state.messages) and st.session_state.messages[last_user_like_idx + 1]["role"] == "assistant":
            st.session_state.messages = st.session_state.messages[:last_user_like_idx + 1]
        st.session_state.pending_input = st.session_state.messages[last_user_like_idx]["content"]
        st.rerun()

# input
if st.session_state.edit_index is None and st.session_state.pending_input is None:
    prompt = st.chat_input("Say something...")
    if prompt:
        st.session_state.pending_input = prompt
        st.rerun()
