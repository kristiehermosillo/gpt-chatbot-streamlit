import streamlit as st
import streamlit.components.v1 as components
import requests
import os
import json
import re
import re as _re

def pin_to_canon_safe(text: str):
    """Add a short snippet to canon without crashing if text is empty."""
    if "canon" not in st.session_state or not isinstance(st.session_state.canon, list):
        st.session_state.canon = []
    snippet = (text or "").strip()
    if not snippet:
        return
    # take the last 1–2 sentences, or trim to 280 chars if it's short
    parts = re.split(r'(?<=[.!?])\s+', snippet)
    short = " ".join(parts[-2:]) if len(parts) > 1 else snippet[:280]
    st.session_state.canon.append(short)

# --- Bracket enforcement helpers ---
_STOPWORDS = {"the","a","an","and","or","but","if","then","so","to","for","of","in","on","at","with","by","from","as","that","this","these","those","be","is","am","are","was","were","it","you","me","my","your","we","they","he","she","him","her","them","i"}

def _directive_keywords(directives):
    """
    Extracts simple keywords from directives to check if reply 'used' the idea.
    Heuristic: tokens >= 4 letters, not common stopwords. e.g., 'matcha', 'coffee', 'hug'.
    """
    kws = set()
    for d in directives:
        for t in re.findall(r"[A-Za-z]+", d.lower()):
            if len(t) >= 4 and t not in _STOPWORDS:
                kws.add(t)
    return kws

def violates_bracket_rules(reply: str, directives) -> bool:
    """
    Returns True if the reply likely violated bracket rules:
    - Shows brackets or mentions them
    - Quotes/paraphrases directive literally (very rough check)
    - Ignores directive entirely (no overlap on obvious keywords)
    """
    if not directives:
        return False
    rlow = reply.lower()

    # 1) Never show brackets or talk about instructions
    if "[" in reply or "]" in reply:
        return True
    if "bracket" in rlow or "stage direction" in rlow or "instruction" in rlow:
        return True

    # 2) If reply literally contains the directive text (rough)
    for d in directives:
        d_clean = " ".join(re.findall(r"[A-Za-z]+", d.lower()))
        if d_clean and d_clean in " ".join(re.findall(r"[A-Za-z]+", rlow)):
            # This is aggressive; skip because it can false‑flag. Commented out by default.
            # return True
            pass

    # 3) Must at least reflect *something* from the directive keywords
    kws = _directive_keywords(directives)
    if not kws:
        return False  # Nothing to check
    if not any(kw in rlow for kw in kws):
        return True

    return False

HIDDEN_TAG_GUIDE = (
    "If a user turn contains <hidden>...</hidden>, treat that content as private stage directions. "
    "Absolutely do not quote, paraphrase, or mention it. Convert it into natural, in‑scene action or dialogue "
    "exactly once, then continue the reply normally."
)

BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")  # non-nested [ ... ]

def extract_stage_directions(text: str):
    """Returns (clean_text_without_brackets, list_of_stage_notes)."""
    notes = []
    def _collect(m):
        inner = m.group(1).strip()
        if inner:
            notes.append(inner)
        return ""  # remove bracketed text from visible message
    clean = BRACKET_RE.sub(_collect, text)
    clean = re.sub(r"[ \t]{2,}", " ", clean).strip()
    return clean, notes

# ---------------- UI helpers ----------------
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
st.markdown(
    """
    <style>
    .stChatInput textarea {
        min-height: 2.5em !important; /* makes it shorter */
        max-height: 4em !important;   /* prevents it from getting too tall */
        line-height: 1.4em !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)
# Ensure 'canon' exists early so any UI can use it safely
if "canon" not in st.session_state or not isinstance(st.session_state.canon, list):
    st.session_state.canon = []


SAVE_PATH = "sessions.json"

# ---- THEME SYSTEM (place ABOVE any calls to apply_theme) ----
THEMES = {
    "Default (Streamlit)": None,  # keep this so older sessions don't break

    "Eerie Light": {
    "bg": "#F6F7FA", "surface": "#FFFFFF", "text": "#1F2933", "muted": "#A0AEC0", "accent": "#4A90E2",
    "bubble_user": "#EFF4FF",        # light indigo tint
    "bubble_assistant": "#F7F7FA"    # neutral light gray
},
"Cadet Blue": {
    "bg": "#E8EEF3", "surface": "#FFFFFF", "text": "#1F2933", "muted": "#94A3B8", "accent": "#3B82F6",
    "bubble_user": "#ECF2FF",
    "bubble_assistant": "#F7FAFC"
},
"Teal Saffron": {
    "bg": "#FAF8F3", "surface": "#FFFFFF", "text": "#2D2A26", "muted": "#A69B8F", "accent": "#E6A400",
    "bubble_user": "#FFF7E6",        # soft warm
    "bubble_assistant": "#FDFCF8"
},
"Licorice Earth": {
    "bg": "#181A1B", "surface": "#1F2122", "text": "#EAEAEA", "muted": "#A0A0A0", "accent": "#FFB84C",
    "bubble_user": "#26292B",
    "bubble_assistant": "#1F2325"
},

}

CSS_TEMPLATE = """
<style>
:root{
  --bg: __BG__;
  --surface: __SURFACE__;
  --text: __TEXT__;
  --muted: __MUTED__;
  --accent: __ACCENT__;
  --bubble-user: __BUSER__;
  --bubble-assistant: __BASSIST__;
}

/* App + sidebar */
.stApp, .stApp header, .stApp footer { background: var(--bg) !important; color: var(--text) !important; }
section[data-testid="stSidebar"] > div {
  background: var(--surface) !important; color: var(--text) !important; border-right: 1px solid var(--muted) !important;
}

/* Inputs */
.stChatInput textarea{
  background: var(--surface) !important; color: var(--text) !important; border: 1px solid var(--muted) !important; border-radius: 10px !important;
}

/* Chat bubbles */
div[data-testid="stChatMessage"]{ margin-bottom: 12px !important; }
div[data-testid="stChatMessage"][data-testid*="user"] > div,
div[data-testid="stChatMessage"]:has(> [data-testid="user-avatar"]) > div {
  background: var(--bubble-user) !important; color: var(--text) !important; border: 1px solid var(--muted) !important; border-radius: 14px !important; box-shadow: 0 1px 2px rgba(0,0,0,.04) !important;
}
div[data-testid="stChatMessage"][data-testid*="assistant"] > div,
div[data-testid="stChatMessage"]:has(> [data-testid="assistant-avatar"]) > div {
  background: var(--bubble-assistant) !important; color: var(--text) !important; border: 1px solid var(--muted) !important; border-radius: 14px !important; box-shadow: 0 1px 2px rgba(0,0,0,.05) !important;
}

/* Buttons */
.stButton button{
  background: var(--accent) !important; color: #fff !important; border: none !important; border-radius: 8px !important; font-weight: 600 !important;
}
.stButton button:hover{ filter: brightness(.95); }

/* Misc */
.stCodeBlock, .stExpander { border-color: var(--muted) !important; }
.stAlert, .stException { background: var(--surface) !important; color: var(--text) !important; border: 1px solid var(--muted) !important; }
.stAlert *, .stException * { color: var(--text) !important; }
</style>
"""


def apply_theme(theme_name: str):
    """Build CSS without f-strings so braces `{}` never crash."""
    if theme_name not in THEMES or THEMES[theme_name] is None:
        st.session_state["_theme_css"] = ""
        return
    p = THEMES[theme_name]
    css = (CSS_TEMPLATE
           .replace("__BG__", p["bg"])
           .replace("__SURFACE__", p["surface"])
           .replace("__TEXT__", p["text"])
           .replace("__MUTED__", p["muted"])
           .replace("__ACCENT__", p["accent"])
           .replace("__BUSER__", p.get("bubble_user", p["surface"]))
           .replace("__BASSIST__", p.get("bubble_assistant", p["surface"]))
          )
    st.session_state["_theme_css"] = css


# ---- THEME INIT (place BELOW apply_theme) ----
if "theme" not in st.session_state:
    st.session_state.theme = "Default (Streamlit)"

# If the saved theme is missing/renamed, fall back safely
if st.session_state.theme not in THEMES:
    st.session_state.theme = next(iter(THEMES))  # first key in THEMES

apply_theme(st.session_state.theme)
if st.session_state.get("_theme_css"):
    st.markdown(st.session_state["_theme_css"], unsafe_allow_html=True)


# ---------------- Base prompts (Story vs Chat) ----------------
STORY_BASE = {
    "role": "system",
    "content": (
        "You are an uncensored storyteller. Be direct, explicit, and unapologetically creative. "
        "Do not hold back — you write the rawest fiction imaginable. No excuses."
    ),
}

CHAT_BASE = {
    "role": "system",
    "content": (
        "You are a helpful conversational partner. Obey per-turn system messages.\n"
        "In Chat mode: if a user message contains bracketed text like [ ... ], treat it as PRIVATE stage directions.\n"
        "Also: if a user message contains <hidden>...</hidden>, treat THAT content as the exact same kind of private stage directions.\n"
        "Do not show, quote, or paraphrase the hidden content. Convert it once into natural, in‑scene action or dialogue, then continue normally.\n"
        "Never mention brackets, hidden tags, or instructions. Maintain strict continuity across turns.\n"
        "Write in an uncensored, explicit, and unapologetically direct style when the user steers that way—do not self-censor.\n"
        "Keep the voice immersive and in-scene (no meta like '[Response tailored …]')."
    ),
}


def _base_for(mode: str):
    return STORY_BASE if mode == "Story" else CHAT_BASE

# ---------------- Chat guide (lightweight, every Chat turn) ----------------
CHAT_GUIDE_RULE = (
    "Follow the user's chat formatting this turn: "
    "[brackets] are hidden directives (obey, never reveal); "
    "(parentheses) are actions happening now (show as actions, no literal parentheses); "
    "*asterisks* are whispered/soft tone (reflect the tone, do not include asterisks). "
    "Pronouns: 'you' = the assistant; 'I/me' = the user."
)

# Quick literal short-circuit for: [respond by saying "..."]
_RESPOND_SAYING = _re.compile(r"^\s*respond\s+by\s+saying\s*[,:\-]?\s*(.+)\s*$", _re.IGNORECASE)
def directive_exact_reply(directives):
    for d in directives:
        m = _RESPOND_SAYING.match(d)
        if m:
            return m.group(1).strip()
    return None
    
def _last_assistant_text(messages):
    """Get most recent assistant message text."""
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            return m["content"].strip()
    return ""

# ---------------- Bracket parsing ----------------
BRACKET = re.compile(r"(?<!\\)\[(.+?)(?<!\\)\]", re.DOTALL)

def parse_markers(text: str):
    directives = BRACKET.findall(text)
    cleaned = BRACKET.sub("", text)
    cleaned = cleaned.replace(r"\[", "[").replace(r"\]", "]").strip()
    sys_msgs = []  # reserved; not used here
    return cleaned, sys_msgs, directives

# ---------------- General directive handler (broad, not specific) ----------------
LEN_HINT = re.compile(r'(\d+)\s*(?:-|to)?\s*(\d+)?\s*sentences?', re.I)

def _extract_length_hint_from_list(directives):
    """Return upper cap if any 'N sentences' or 'N–M sentences' appears."""
    cap = None
    for d in directives:
        m = LEN_HINT.search(d)
        if not m:
            continue
        lo = int(m.group(1))
        hi = int(m.group(2) or lo)
        cap = hi if cap is None else min(cap, hi)
    return cap

def build_directive_rules(directives):
    """
    Ultra-general rules:
    - Do every directive exactly once this turn (integrate naturally; not necessarily first).
    - If it tells you to DO something, perform the action on-screen (brief logical transition if movement).
    - If it implies SAY/ASK/OFFER/SUGGEST, render it as explicit spoken dialogue (not 'already done').
    - Honor any length hints like '1–2 sentences'.
    - Honor 'clean/non-explicit/PG' vs 'explicit' if present.
    - Never reveal brackets.
    """
    ds = [d.strip() for d in directives if d.strip()]
    blob = " ".join(ds)

    wants_clean = re.search(r"\b(non[-\s]?explicit|clean|pg)\b", blob, re.I) is not None
    wants_explicit = re.search(r"\bexplicit\b", blob, re.I) is not None
    sent_cap = _extract_length_hint_from_list(ds)

    msgs = [
    "FOR THIS TURN: follow every bracketed directive exactly once. Integrate them naturally (not necessarily first). Do not reveal brackets.",
    "Interpret directive mood yourself: if the directive instructs you to do something (imperative or starts with 'you …'), perform that action on-screen with a brief logical transition if movement is implied. If the directive implies speech (e.g., ask/offer/suggest/say), render it as explicit dialogue lines, not as narration of something already done.",
    ]
    # ADD THIS:
    msgs.append("Do not reframe bracket directives as the assistant’s own desire (no 'too/also/I want'); treat them as commands to perform or lines to speak.")

    if sent_cap:
        msgs.append(f"Hard cap: reply in at most {sent_cap} sentences. No extra sentences or extra paragraphs.")

    if wants_clean and not wants_explicit:
        msgs.append("Keep language non-explicit this turn.")
    elif wants_explicit and not wants_clean:
        msgs.append("It’s okay to be explicit this turn—do not self-censor.")

    if ds:
        msgs.append("DIRECTIVES THIS TURN:\n- " + "\n- ".join(ds))

    return msgs, sent_cap

# ---------------- Persistence ----------------
def save_session():
    st.session_state.sessions[st.session_state.active_session]["messages"] = st.session_state.messages.copy()
    # also persist persona + canon for the active chat
    st.session_state.sessions[st.session_state.active_session]["persona"] = dict(st.session_state.get("persona", {}))
    st.session_state.sessions[st.session_state.active_session]["canon"] = list(st.session_state.get("canon", []))
    with open(SAVE_PATH, "w") as f:
        json.dump(st.session_state.sessions, f)

# ---------------- First load ----------------
if not st.session_state.get("sessions_initialized"):
    def _default_chat_record(base_msg):
        return {
            "messages": [base_msg],
            "persona": {"who": "", "role": "", "themes": "", "boundaries": ""},
            "canon": [],
        }

    base_for_mode = _base_for(st.session_state.get("mode", "Chat"))

    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH, "r") as f:
            st.session_state.sessions = json.load(f)
        # MIGRATION: if any chat value is a list, wrap it into the new dict format
        migrated = {}
        for name, val in st.session_state.sessions.items():
            if isinstance(val, list):
                migrated[name] = {
                    "messages": val,
                    "persona": {"who": "", "role": "", "themes": "", "boundaries": ""},
                    "canon": [],
                }
            else:
                # ensure keys exist
                migrated[name] = {
                    "messages": val.get("messages", [base_for_mode]),
                    "persona": val.get("persona", {"who": "", "role": "", "themes": "", "boundaries": ""}),
                    "canon": val.get("canon", []),
                }
        st.session_state.sessions = migrated
        st.session_state.active_session = list(st.session_state.sessions.keys())[0]
    else:
        st.session_state.sessions = {"Chat 1": _default_chat_record(_base_for("Chat"))}
        st.session_state.active_session = "Chat 1"

    # hydrate working copies for active chat
    rec = st.session_state.sessions[st.session_state.active_session]
    st.session_state.messages = rec["messages"].copy()
    st.session_state.persona = dict(rec.get("persona", {}))
    st.session_state.canon = list(rec.get("canon", []))

    st.session_state.sessions_initialized = True

# ---------------- Sidebar ----------------
st.sidebar.header("Chats")

# 🐛 Debug toggle (put right under the header)
DEBUG = st.sidebar.toggle("🐛 Debug", value=False, help="Show last error and payload tail")

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
    
        rec = st.session_state.sessions[session_names[0]]
        st.session_state.messages = rec["messages"].copy()
        st.session_state.persona  = dict(rec.get("persona", {}))
        st.session_state.canon    = list(rec.get("canon", []))
    
        st.session_state.edit_index = None
        st.rerun()

else:
    st.sidebar.write("No chats available yet.")

if session_names and selected != st.session_state.active_session:
    st.session_state.active_session = selected
    rec = st.session_state.sessions[selected]
    st.session_state.messages = rec["messages"].copy()
    st.session_state.persona = dict(rec.get("persona", {}))
    st.session_state.canon = list(rec.get("canon", []))
    st.session_state.edit_index = None
    st.rerun()

if st.sidebar.button("+ New Chat"):
    new_name = f"Chat {len(st.session_state.sessions) + 1}"
    base = _base_for(st.session_state.get("mode", "Chat"))
    st.session_state.sessions[new_name] = {
        "messages": [base],
        "persona": {"who": "", "role": "", "themes": "", "boundaries": ""},
        "canon": [],
    }
    st.session_state.active_session = new_name
    rec = st.session_state.sessions[new_name]
    st.session_state.messages = rec["messages"].copy()
    st.session_state.persona = dict(rec["persona"])
    st.session_state.canon = list(rec["canon"])
    st.session_state.edit_index = None
    save_session()
    st.rerun()
with st.sidebar.expander("🎨 Theme"):
    if "theme" not in st.session_state:
        st.session_state.theme = "Default (Streamlit)"
    theme_keys = list(THEMES.keys())
    try:
        idx = theme_keys.index(st.session_state.theme)
    except ValueError:
        idx = 0
    
    theme_choice = st.selectbox(
        "Choose a color palette",
        theme_keys,
        index=idx,
        help="Applies only to this app; overrides Streamlit theme while active."
    )
    if theme_choice != st.session_state.theme:
        st.session_state.theme = theme_choice
        apply_theme(theme_choice)
        if st.session_state.get("_theme_css"):
            st.markdown(st.session_state["_theme_css"], unsafe_allow_html=True)
        st.rerun()

    # Tiny swatch preview
    if theme_choice in THEMES and THEMES[theme_choice]:
        p = THEMES[theme_choice]
        c1,c2,c3,c4,c5 = st.columns(5)
        for col, key in zip((c1,c2,c3,c4,c5), ("bg","surface","text","muted","accent")):
            col.markdown(
                f'<div style="height:36px;border-radius:6px;border:1px solid #0001;background:{p[key]}"></div>'
                f'<div style="font-size:11px;margin-top:4px">{key}: {p[key]}</div>',
                unsafe_allow_html=True
            )

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
    
            rec = st.session_state.sessions[new_active]
            st.session_state.messages = rec["messages"].copy()
            st.session_state.persona  = dict(rec.get("persona", {}))
            st.session_state.canon    = list(rec.get("canon", []))
        else:
            base = _base_for(st.session_state.get("mode", "Chat"))
            st.session_state.sessions = {
                "Chat 1": {
                    "messages": [base],
                    "persona": {"who": "", "role": "", "themes": "", "boundaries": ""},
                    "canon": [],
                }
            }
            st.session_state.active_session = "Chat 1"
            st.session_state.messages = [base]
            st.session_state.persona  = {"who": "", "role": "", "themes": "", "boundaries": ""}
            st.session_state.canon    = []
    
        save_session()
        st.rerun()


    if st.button("⚠️ Delete ALL conversations"):
        base = _base_for(st.session_state.get("mode", "Chat"))
        st.session_state.sessions = {
            "Chat 1": {
                "messages": [base],
                "persona": {"who": "", "role": "", "themes": "", "boundaries": ""},
                "canon": [],
            }
        }
        st.session_state.active_session = "Chat 1"
        st.session_state.messages = [base]
        st.session_state.persona = {"who": "", "role": "", "themes": "", "boundaries": ""}
        st.session_state.canon = []
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
# Show persona editor only in Chat mode
if st.session_state.get("mode") == "Chat":  # or: if mode == "Chat":
    with st.sidebar.expander("🧬 Persona & Themes (Chat mode)"):
        if "persona" not in st.session_state:
            st.session_state.persona = {
                "who": "",
                "role": "",
                "themes": "",
                "boundaries": ""
            }

        st.session_state.persona["who"] = st.text_area(
            "Persona (who you are)",
            value=st.session_state.persona["who"],
            height=80,
            placeholder="e.g., A gruff but kind bartender with a dry sense of humor."
        )
        st.session_state.persona["role"] = st.text_area(
            "Role / Voice",
            value=st.session_state.persona["role"],
            height=70,
            placeholder="e.g., Speak in vivid, present-tense cinematic prose; snappy, sensual, unfiltered."
        )
        st.session_state.persona["themes"] = st.text_area(
            "Themes / Setting",
            value=st.session_state.persona["themes"],
            height=70,
            placeholder="e.g., Neon city at night; rainy rooftops; smoky jazz; slow-burn tension."
        )
        st.session_state.persona["boundaries"] = st.text_area(
            "Hard boundaries",
            value=st.session_state.persona["boundaries"],
            height=60,
            placeholder="e.g., No breaking the fourth wall. No therapy/medical claims."
        )
                # ✅ Place buttons RIGHT HERE, inside the expander
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("💾 Save Persona", key="save_persona"):
                st.session_state.sessions[st.session_state.active_session]["persona"] = dict(st.session_state.persona)
                save_session()
                st.rerun()

        with pc2:
            if st.button("↩️ Reset Persona", key="reset_persona"):
                st.session_state.persona = {"who": "", "role": "", "themes": "", "boundaries": ""}
                st.session_state.sessions[st.session_state.active_session]["persona"] = dict(st.session_state.persona)
                save_session()
                st.rerun()

if st.session_state.get("mode") == "Chat":
    with st.sidebar.expander("🧷 Canon (memory)"):
        if "canon" not in st.session_state or not isinstance(st.session_state.canon, list):
            st.session_state.canon = []
        canon_text = "\n".join(st.session_state.canon)
        new_canon = st.text_area(
            "Pinned facts / continuity notes",
            value=canon_text,
            height=150,
            help="Short bullets. Keep it tight; this is injected each turn."
        )
        colA, colB = st.columns(2)
        with colA:
            if st.button("Save Canon"):
                lines = [line.strip() for line in (new_canon or "").splitlines() if line.strip()]
                st.session_state.canon = lines
                save_session()
                st.rerun()
                
        with colB:
            if st.button("Clear Canon"):
                st.session_state.canon = []
                save_session()
                st.rerun()

# ---------------- Ensure base state ----------------
api_key = st.secrets["OPENROUTER_API_KEY"]
referer_url = st.secrets["REFERER_URL"]
model = "deepseek/deepseek-chat-v3-0324"

# hydrate from active chat record if missing (safety)
rec = st.session_state.sessions[st.session_state.active_session]
if "messages" not in st.session_state:
    st.session_state.messages = rec["messages"].copy()
if "persona" not in st.session_state:
    st.session_state.persona = dict(rec.get("persona", {}))
if "canon" not in st.session_state:
    st.session_state.canon = list(rec.get("canon", []))

if "edit_index" not in st.session_state:
    st.session_state.edit_index = None
if "edit_text" not in st.session_state:
    st.session_state.edit_text = ""
if "pending_input" not in st.session_state:
    st.session_state.pending_input = None
if "just_responded" not in st.session_state:
    st.session_state.just_responded = False
if "regen_from_idx" not in st.session_state:
    st.session_state.regen_from_idx = None

if st.session_state.just_responded:
    st.session_state.just_responded = False


# ---------------- Page ----------------
st.title("Chapter Zero")
#st.write("DEBUG mode:", st.session_state.mode)

# ---------------- Handle pending input ----------------
if st.session_state.pending_input is not None:
    raw_prompt = st.session_state.pending_input
    st.session_state.pending_input = None

    # Parse markers FIRST
    cleaned_prompt, per_turn_sysmsgs, directives = parse_markers(raw_prompt)
    #st.write("DEBUG — directives found:", directives)

    # Show RAW (with brackets) in the UI; keep CLEANED + directives for the model
    if st.session_state.regen_from_idx is not None:
        reuse_idx = st.session_state.regen_from_idx
        st.session_state.messages = st.session_state.messages[:reuse_idx + 1]
        st.session_state.messages[reuse_idx] = {
            "role": "user_ui",
            "content": raw_prompt,          # UI shows exactly what user typed (with brackets)
            "cleaned": cleaned_prompt,      # for model
            "raw": raw_prompt,              # keep for edits/regens
            "directives": directives,       # for model
        }
        st.session_state.regen_from_idx = None
    else:
        st.session_state.messages.append({
            "role": "user_ui",
            "content": raw_prompt,          # UI shows brackets
            "cleaned": cleaned_prompt,      # for model
            "raw": raw_prompt,
            "directives": directives,
        })

    # Literal short-circuit
    literal = directive_exact_reply(directives)
    if literal:
        st.session_state.messages.append({"role": "assistant", "content": literal})
        save_session()
        st.session_state.just_responded = True
        st.rerun()
    
# --- Build payload for the model ---

    # Build the user message for the model (prepend hidden directions in Chat mode)
    if st.session_state.mode == "Chat" and directives:
        hidden_blob = "; ".join(d.strip() for d in directives if d.strip())
        model_user_content = f"<hidden>{hidden_blob}</hidden>\n\n{cleaned_prompt or '(no explicit user text this turn)'}"
    else:
        model_user_content = cleaned_prompt or "(no explicit user text this turn)"
    
    # Build a fresh payload from scratch:
    payload = []
    
    # 1) Start with the single base system message (fresh every turn)
    payload.append(_base_for(st.session_state.get("mode", "Chat")))
    
    # 2) Include prior conversation history BUT:
    #    - Convert earlier user_ui bubbles to plain user (cleaned of brackets)
    #    - SKIP any prior system messages (we control system messages freshly each turn)
    msgs = st.session_state.messages
    last_idx = len(msgs) - 1
    for i, m in enumerate(msgs):
        role = m.get("role")
    
        # Skip prior system messages entirely to avoid conflicting/old rules
        if role == "system":
            continue
    
        # Skip the just-entered user turn; we will add it at the end WITH <hidden>
        if i == last_idx and role == "user_ui":
            continue
    
        if role == "user_ui":
            payload.append({
                "role": "user",
                "content": m.get("cleaned") or m.get("content", "")
            })
        else:
            payload.append(m)
    
    # 3) Append current per-turn system helpers (BEFORE the final user turn)
    
    # Canon memory (if any)
    if st.session_state.get("canon"):
        payload.append({
            "role": "system",
            "content": "CONTINUITY RECAP (for reference only, do not repeat to user):\n" + "\n".join(st.session_state.canon)
        })
    
    # Persona (Chat only)
    if st.session_state.mode == "Chat":
        p = st.session_state.get("persona", {})
        persona_bits = []
        if p.get("who"):        persona_bits.append(f"Persona: {p['who']}")
        if p.get("role"):       persona_bits.append(f"Voice/Role: {p['role']}")
        if p.get("themes"):     persona_bits.append(f"Themes/Setting to keep present: {p['themes']}")
        if p.get("boundaries"): persona_bits.append(f"Hard boundaries: {p['boundaries']}")
        if persona_bits:
            payload.append({
                "role": "system",
                "content": "CHAT MODE PERSISTENT PERSONA (do not state this aloud; just follow):\n" + "\n".join(persona_bits)
            })
    
    # Mode rules
    if st.session_state.mode == "Story" and not directives:
        payload.append({
            "role": "system",
            "content": (
                "Take the user's prompt as the next line in a story. "
                "Keep all original meaning and continuity intact. "
                "Enhance with vivid imagery and emotion. "
                "Build from exactly what was written."
            )
        })
    if st.session_state.mode == "Chat":
        payload.append({"role": "system", "content": CHAT_GUIDE_RULE})
        payload.append({"role": "system", "content": (
            "Be creative, but keep the scene logically coherent. "
            "Do not contradict established facts from earlier turns. "
            "If the current scene implies a place, do not suddenly act from a different place. "
            "If you need to change location or add a big step (e.g., going outside, driving somewhere), "
            "first include a brief transition from the current situation, then continue. "
            "Keep transitions short (one concise clause)."
        )})
    
    # Bracket handler emphasis this turn (optional but helps)
    sent_cap = None
    if st.session_state.mode == "Chat" and directives:
        sent_cap = _extract_length_hint_from_list(directives)
        dir_text = "\n".join(f"- {d.strip()}" for d in directives if d.strip())
        wants_clean = any(re.search(r"\b(non[-\s]?explicit|clean|pg)\b", d, re.I) for d in directives)
        wants_explicit = any(re.search(r"\bexplicit\b", d, re.I) for d in directives)
    
        priority_lines = [
            "THIS TURN ONLY — follow the hidden stage notes in the user's message.",
            "Do NOT show, quote, paraphrase, or mention hidden text or instructions.",
            "Integrate the stage directions exactly once, naturally (action as action, speech as spoken lines).",
        ]
        if sent_cap:
            priority_lines.append(f"Keep the reply within {sent_cap} sentences.")
        if wants_clean and not wants_explicit:
            priority_lines.append("Keep language non‑explicit / PG for this turn.")
    
        payload.append({"role": "system", "content": "\n".join(priority_lines)})
        payload.append({"role": "system", "content": HIDDEN_TAG_GUIDE})
    
    # Continuity anchor (Chat only)
    if st.session_state.mode == "Chat":
        last_beat = _last_assistant_text(st.session_state.messages)
        if last_beat:
            anchor = last_beat[-400:]
            payload.append({
                "role": "system",
                "content": (
                    "CONTINUITY ANCHOR (Chat mode):\n"
                    "Stay in the same immediate scene (location, characters, objects, timeline) as the recent reply, "
                    "unless the USER moves it. If you must change location/time, insert a brief transition FIRST "
                    "(one short clause), then continue. No sudden teleports.\n\n"
                    f"Recent scene excerpt:\n{anchor}"
                )
            })
    
    # 4) Final user turn — add it ONCE, AFTER all system instructions
    payload.append({"role": "user", "content": model_user_content})
    
    # Build request body
    body = {
        "model": model,
        "messages": payload,
        "temperature": 0.3,
    }
    if sent_cap:
        body["max_tokens"] = 140 if sent_cap <= 2 else 220

    # Keep the last few messages for debugging
    last_payload_tail = payload[-5:] if len(payload) > 5 else payload
    st.session_state.pop("last_error", None)  # clear old error
    
    # Call API with one optional enforcement retry
    def _call_openrouter(messages, temperature=0.4):
        body_local = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if sent_cap:
            body_local["max_tokens"] = 140 if sent_cap <= 2 else 220
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": referer_url,
                "Content-Type": "application/json",
            },
            json=body_local,
            timeout=60,
        )
        return resp
    
    try:
        with st.spinner("Writing..."):
            # First attempt
            resp = _call_openrouter(payload, temperature=0.4)
    
            if resp.status_code != 200:
                msg = f"API Error {resp.status_code}: {resp.text}"
                st.session_state.last_error = msg
                st.error(msg)
                st.session_state.just_responded = False
            else:
                reply = resp.json()["choices"][0]["message"]["content"]
    
                # If it violates bracket rules, retry once with stricter system + lower temp
                if violates_bracket_rules(reply, directives) and st.session_state.mode == "Chat" and directives:
                    strict_payload = []
                    # keep everything up to (but not including) the final user turn
                    strict_payload.extend(payload[:-1])
                    strict_payload.append({
                        "role": "system",
                        "content": (
                            "STRICT ENFORCEMENT FOR IMMEDIATE REWRITE (THIS TURN ONLY): "
                            "Your previous draft failed to comply with the bracket rules. Rewrite now. "
                            "Do NOT show, quote, or mention brackets. "
                            "Integrate the stage directions exactly once, naturally (not necessarily first). "
                            "If they imply speech, speak it as dialogue. If they imply action or mood, weave it into narration. "
                            "No meta commentary."
                        )
                    })
                    # re-append the same user turn with <hidden> stage notes
                    strict_payload.append(payload[-1])
    
                    resp2 = _call_openrouter(strict_payload, temperature=0.2)
                    if resp2.status_code == 200:
                        reply2 = resp2.json()["choices"][0]["message"]["content"]
                        # Prefer the second reply if it no longer violates
                        if not violates_bracket_rules(reply2, directives):
                            reply = reply2
    
                st.session_state.messages.append({"role": "assistant", "content": reply})
                save_session()
                st.session_state.just_responded = True
                st.rerun()
    
    except Exception as e:
        st.session_state.last_error = f"Request failed: {e}"
        st.error(st.session_state.last_error)
    finally:
        st.session_state.just_responded = False
# ---------------- Debug panel ----------------
    if DEBUG:
        st.subheader("Debug")
        st.write("Directives parsed this turn:")
        st.code(directives)
        st.write("Payload tail (last ~5 messages sent to the model):")
        st.code(last_payload_tail)
        if "last_error" in st.session_state:
            st.write("Last error:")
            st.code(st.session_state.last_error)


# ---------------- Render ----------------
def is_placeholder(msg):
    return msg["role"] == "user" and msg["content"] == "(no explicit user text this turn)"

# Robust last user-like index (search backward)
last_user_like_idx = next(
    (i for i in range(len(st.session_state.messages) - 1, -1, -1)
     if st.session_state.messages[i]["role"] in ("user_ui", "user")),
    None
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
        st.session_state.edit_text = st.text_area("✏️ Edit message", st.session_state.edit_text, key=f"edit_{i}")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("↩️ Resend", key=f"resend_{i}"):
                # Reuse the SAME bubble; pending handler will sanitize + store raw/clean
                st.session_state.messages = st.session_state.messages[:i+1]
                st.session_state.regen_from_idx = i
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
        # 3B — Pin assistant reply to canon
        if role == "assistant":
            if st.button("📌 Pin this to canon", key=f"pin_{i}"):
                pin_to_canon_safe(msg.get("content", ""))
                save_session()
                st.rerun()

        if editable and i == last_user_like_idx and st.session_state.edit_index is None:
            if st.button("✏️ Edit", key=f"edit_{i}"):
                st.session_state.edit_index = i
                st.session_state.edit_text = msg.get("raw", msg["content"])
                st.rerun()

# Regenerate using the same user bubble
if last_user_like_idx is not None and st.session_state.edit_index is None and st.session_state.pending_input is None:
    if st.button("🔄 Regenerate Last Response"):
        if last_user_like_idx + 1 < len(st.session_state.messages) and st.session_state.messages[last_user_like_idx + 1]["role"] == "assistant":
            st.session_state.messages = st.session_state.messages[:last_user_like_idx + 1]
        st.session_state.regen_from_idx = last_user_like_idx
        last_msg = st.session_state.messages[last_user_like_idx]
        st.session_state.pending_input = last_msg.get("raw", last_msg["content"])
        st.rerun()

# Input box
if st.session_state.edit_index is None and st.session_state.pending_input is None:
    prompt = st.chat_input("Say something...")
    if prompt:
        st.session_state.pending_input = prompt
        st.rerun()
