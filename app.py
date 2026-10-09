"""AARON-1 — one assistant, one dashboard.

No LLM, agent network, mock multi-agent population, or access without permission.
"""
from __future__ import annotations

import html
from datetime import date

import pandas as pd
import streamlit as st

from assistant_core import (
    add_task, concise_reply, connect, learn_priority, list_tasks, parse_csv,
    parse_ics, ranked_tasks, score_task, update_task, load_weights,
)
from gmail_access import (
    check_account, client_ready, connected, disconnect, finish_auth,
    list_messages, make_auth_url, store_client_upload,
)
from avatar import render_face

st.set_page_config(page_title="AARON-1", page_icon="🤖", layout="centered")


def init_chat():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS chat_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL,
          message TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        db.commit()


def write_chat(role, message):
    with connect() as db:
        db.execute("INSERT INTO chat_history(role, message) VALUES (?,?)",
                   (role, str(message)[:6000]))
        db.commit()


def messages(limit=25):
    with connect() as db:
        return [dict(x) for x in db.execute(
            "SELECT role,message FROM (SELECT id,role,message FROM chat_history "
            "ORDER BY id DESC LIMIT ?) ORDER BY id ASC", (limit,)
        )]


def answer(message):
    lower = message.lower()
    if any(word in lower for word in ("email", "inbox", "gmail", "mail")):
        if not connected():
            return ("Gmail isn't connected yet. Open Connect, authorize your Gmail "
                    "account, then ask me again. I can only read messages.")
        try:
            recent = list_messages(search="in:inbox", max_results=5)
            if not recent:
                return "Your inbox has no messages matching the current search."
            lines = [f"• {item['subject']} — {item['from']}" for item in recent]
            return "Here are the latest inbox subjects:\n" + "\n".join(lines)
        except Exception:
            return ("I couldn't load Gmail. Reconnect in the Connect tab if "
                    "your authorization has expired.")
    return concise_reply(message)


def render_tasks():
    st.subheader("Your assignments & to-dos")
    st.caption("Add assignments manually or import a calendar under Connect. "
               "AARON-1 learns what's important from your feedback.")

    with st.form("new_task", clear_on_submit=True):
        title = st.text_input("What do you need to do?", placeholder="Finish chemistry problems")
        due = st.text_input("Due date (optional)", placeholder="YYYY-MM-DD")
        if st.form_submit_button("Add task", type="primary"):
            try:
                add_task(title, due=due or None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    rows = ranked_tasks()
    if not rows:
        st.info("No open tasks yet. Add one above or import your assignment calendar.")
    for task in rows[:80]:
        with st.container(border=True):
            left, right = st.columns([4, 1])
            with left:
                st.markdown(f"**{task['title']}**")
                detail = []
                if task.get("due"):
                    detail.append("Due " + task["due"])
                if task.get("source") != "manual":
                    detail.append("From " + task["source"].capitalize())
                if detail:
                    st.caption(" · ".join(detail))
            with right:
                st.caption(f"Priority {int(score_task(task)*100)}%")
            c1, c2, c3 = st.columns([1, 1, 1])
            if c1.button("✓ Done", key="done_" + task["id"]):
                update_task(task["id"], completed=True)
                st.rerun()
            if c2.button("↑ Important", key="important_" + task["id"]):
                learn_priority(task["id"], True)
                st.rerun()
            if c3.button("↓ Not urgent", key="not_" + task["id"]):
                learn_priority(task["id"], False)
                st.rerun()
    st.caption("Importance labels train a small scoring model; it won't complete "
               "homework or submit work automatically.")
    with st.expander("Completed tasks"):
        completed = [t for t in list_tasks(include_completed=True) if t["completed"]]
        if not completed:
            st.write("Nothing completed yet.")
        for t in completed:
            c1, c2 = st.columns([4, 1])
            c1.write(t["title"])
            if c2.button("Reopen", key="reopen_" + t["id"]):
                update_task(t["id"], completed=False)
                st.rerun()


def render_connections():
    st.subheader("Connect your accounts")
    st.caption("Nothing is connected until you authorize it. "
               "No password sharing, no sending mail, no deleting mail.")

    with st.container(border=True):
        st.markdown("#### ✉️ Gmail")
        st.caption("Personal Gmail is fine. Read-only access to inbox metadata "
                   "and message snippets, approved by you through Google.")
        if connected():
            try:
                st.success("Connected: " + check_account())
            except Exception:
                st.warning("Gmail authorization is saved but needs refreshing.")
            if st.button("Disconnect Gmail", key="disconnect_gmail"):
                disconnect()
                st.session_state.pop("gmail_view", None)
                st.rerun()
            if st.button("Check latest emails", type="primary", key="check_mail"):
                try:
                    st.session_state["gmail_view"] = list_messages("in:inbox", 15)
                except Exception:
                    st.error("Gmail could not be read. Your token may have expired.")
            if st.button("Find assignment-related emails", key="find_school_mail"):
                try:
                    st.session_state["gmail_view"] = list_messages(
                        "newer_than:90d {assignment homework blackbaud deadline}", 20
                    )
                except Exception:
                    st.error("Could not search Gmail. Check your connection.")
            if "gmail_view" in st.session_state:
                emails = st.session_state["gmail_view"]
                if not emails:
                    st.info("No matching emails.")
                for mail in emails:
                    with st.container(border=True):
                        st.markdown(f"**{mail['subject']}**")
                        st.caption(f"{mail['from']} · {mail['date']}")
                        st.write(mail["snippet"])
                        if st.button("Add subject as task", key="mailtask_" + mail["id"]):
                            _, added = add_task(mail["subject"], source="email",
                                                notes=mail["snippet"],
                                                external_id=mail["id"])
                            st.toast("Added to tasks" if added else "Already added")
        else:
            if "code" in st.query_params or "error" in st.query_params:
                try:
                    finish_auth(st.query_params.to_dict())
                    st.query_params.clear()
                    st.success("Gmail successfully connected!")
                    st.rerun()
                except Exception as exc:
                    st.query_params.clear()
                    st.error(f"Google authorization wasn't completed: {exc}")
            if not client_ready():
                st.info("One-time Google setup: create a Google Cloud OAuth "
                        "**Web application** client for the Gmail API, enable the Gmail API, "
                        "add your Gmail as a test user if required, and register "
                        "http://localhost:8501 as the authorized redirect URI.")
                st.caption("Download its JSON credentials and upload them here. "
                           "They stay only on your Mac in the gitignored data folder.")
                uploaded = st.file_uploader("Upload Google OAuth client JSON",
                                            type=["json"], key="gmail_json")
                if uploaded is not None and st.button("Save Google connection setup"):
                    try:
                        store_client_upload(uploaded.getvalue())
                        st.success("Setup saved. You can now authorize Gmail.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
            else:
                try:
                    url = make_auth_url() if st.button("Start Gmail authorization", type="primary") else None
                    if url:
                        # Same-tab navigation: the OAuth callback returns to this Streamlit app.
                        st.markdown(
                            '<a href="' + html.escape(url, quote=True) +
                            '" target="_self">Continue to Google authorization →</a>',
                            unsafe_allow_html=True,
                        )
                except Exception:
                    st.error("Could not start Google authentication. Check OAuth settings.")

    with st.container(border=True):
        st.markdown("#### 📚 School assignments")
        st.caption("For Blackbaud, export an assignment calendar (ICS) or CSV "
                   "if your school makes one available. This does not sign in to Blackbaud.")
        uploaded = st.file_uploader("Import school assignment file",
                                    type=["ics", "csv"], key="school_file")
        if uploaded is not None and st.button("Import assignments", type="primary"):
            try:
                raw = uploaded.getvalue()
                count = (parse_ics(raw) if uploaded.name.lower().endswith(".ics")
                         else parse_csv(raw))
                st.success(f"Imported {count} new assignments. Duplicates skipped.")
            except Exception as exc:
                st.error(f"Could not import file: {exc}")
        st.caption("Direct Blackbaud account sync is not connected. "
                   "We'll need school-supported authorization before adding it.")

    with st.expander("Privacy & permissions"):
        st.write("Gmail permission requested: gmail.readonly. "
                 "AARON-1 cannot send mail or delete messages. "
                 "The app reads basic headers/snippets only when asked. "
                 "Tokens remain local in data/ and are excluded from GitHub. "
                 "Never upload Google passwords or private keys to the repository.")


def render_chat():
    st.subheader("Ask AARON-1")
    with st.expander("🤖 Show robot", expanded=False):
        history = messages(1)
        last = history[-1]["message"] if history and history[-1]["role"] == "assistant" else "Hi. What can I help with?"
        render_face(last, key="home")
    st.caption("One assistant, not a network. It remembers tasks and learns "
               "your priorities. Natural-language skills are still limited.")
    for item in messages():
        with st.chat_message(item["role"]):
            st.markdown(item["message"])
    prompt = st.chat_input("Ask about homework, email, or add a task...")
    if prompt:
        write_chat("user", prompt)
        reply = answer(prompt)
        write_chat("assistant", reply)
        st.rerun()
    if not messages():
        st.write("Try **what homework is due**, **add task read chapter 3**, "
                 "or **check my email**.")


def main():
    init_chat()
    st.title("🤖 AARON-1")
    st.caption("Your personal learning assistant · Local-first · No LLM")

    # OAuth query params might arrive on any tab: process and clear them globally.
    if "code" in st.query_params or "error" in st.query_params:
        try:
            finish_auth(st.query_params.to_dict())
            st.query_params.clear()
            st.toast("Gmail connected")
        except Exception as exc:
            st.query_params.clear()
            st.error(f"Gmail connection failed: {exc}")

    chat_tab, task_tab, connection_tab = st.tabs(["💬 Chat", "✅ Tasks", "🔗 Connect"])
    with chat_tab:
        render_chat()
    with task_tab:
        render_tasks()
    with connection_tab:
        render_connections()

    _, n = load_weights()
    st.caption(f"🧠 AARON-1 has learned from {n} priority decisions. "
               "Your files and saved memories stay on this Mac.")


if __name__ == "__main__":
    main()
