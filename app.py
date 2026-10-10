"""AARON-1 — one local assistant, planner, and optional trainable language model."""
from __future__ import annotations

import html
from datetime import date, timedelta

import streamlit as st

from assistant_core import (
    add_task, concise_reply, connect, learn_priority, list_tasks, parse_csv,
    parse_ics, ranked_tasks, score_task, update_task, load_weights,
    change_month, tasks_due_in_month, tasks_without_due_date, set_task_due_date,
)
from gmail_access import (
    check_account, client_ready, connected, disconnect, finish_auth,
    list_messages, make_auth_url, store_client_upload,
)
from avatar import render_face
from ui_theme import install_theme, header, page_heading
from planner_ui import calendar_page, tasks_page
from planner import ensure_schema
from google_calendar_import import import_google_calendar
from winter_arc import seed_winter_arc
from assistant_conversation import respond, local_models
from training_ui import training_page
from training_data import trained_model
from trained_chat import inference_dependencies_ready

APP_BUILD = "2026.10.10-calendar-v5"

st.set_page_config(page_title="AARON-1", page_icon="🤖", layout="wide")


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
    lower = message.lower().strip()
    if any(phrase in lower for phrase in (
        "check my email", "check my gmail", "show my inbox", "latest emails",
        "new email", "my mail", "read my email",
    )):
        if not connected():
            return ("Gmail isn't connected yet. Open Connections and authorize "
                    "read-only Gmail access first.")
        try:
            recent = list_messages(search="in:inbox", max_results=6)
            if not recent:
                return "No inbox messages matched that search."
            return "Latest Gmail inbox subjects:\\n" + "\\n".join(
                f"• {item['subject']} — {item['from']}" for item in recent
            )
        except Exception:
            return "Gmail couldn't be read. Check its authorization under Connections."

    model = st.session_state.get("aaron_selected_chat_model")
    response, _ = respond(message, previous=messages(limit=12), model=model)
    return response


def render_tasks():
    tasks_page()


def render_calendar():
    calendar_page()


def render_connections():
    page_heading(
        "Your integrations",
        "Connections",
        "Link Gmail with read-only permission or import your school assignments. "
        "You control what AARON-1 can access.",
    )

    with st.container(border=True):
        st.markdown("#### ✉️ Gmail")
        st.caption("Personal Gmail is fine. Google grants read-only mail access; "
                   "this app requests only headers and short snippets.")
        if connected():
            st.success("Gmail authorization saved · read-only")
            if st.button("Check connected account", key="check_account"):
                try:
                    st.success("Account: " + check_account())
                except Exception:
                    st.warning("The Gmail connection may need refreshing.")
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
        st.markdown("#### 📅 Google Calendar — private import")
        st.caption(
            "Import your Google Calendar export directly, including the ZIP "
            "download. Event times, durations, multi-day entries and recurring "
            "instances are preserved. This makes a local copy only; nothing "
            "is uploaded to GitHub or changed in Google."
        )
        google_file = st.file_uploader(
            "Google Calendar export (.ics or .zip)",
            type=["ics", "zip"], key="google_calendar_file",
        )
        range_from = st.date_input(
            "Import events beginning", value=date.today() - timedelta(days=30),
            key="google_calendar_from",
            help="The export contains years of history. Usually the last 30 "
                 "days onward is enough; choose an earlier date if needed.",
        )
        range_months = st.selectbox(
            "How far ahead?", [6, 12, 18, 24, 36, 48],
            index=2, format_func=lambda x: f"{x} months",
            key="google_calendar_months",
        )
        if google_file is not None:
            st.caption(
                f"Selected: {google_file.name} "
                f"({google_file.size / 1024 / 1024:.1f} MB compressed)"
            )
        recent_google_import = st.session_state.pop(
            "google_calendar_import_result", None
        )
        if recent_google_import is not None:
            summary = recent_google_import
            st.success(
                f"Imported {summary['added']} new events; refreshed "
                f"{summary['updated']} existing events across "
                f"{summary['calendars']} calendar(s)."
            )
            st.caption(
                "Covered " + summary["range_start"] + " through " +
                summary["range_end"] + ". Reimporting refreshes local copies "
                "without duplicates. This is not live sync."
            )
        if st.button(
            "Import Google Calendar", key="google_calendar_import",
            type="primary", disabled=google_file is None,
        ):
            try:
                with st.spinner("Reading and expanding calendar events locally…"):
                    result = import_google_calendar(
                        google_file.getvalue(), google_file.name,
                        from_date=range_from, months=range_months,
                    )
                st.session_state["google_calendar_import_result"] = result
                # Planner is rendered earlier in this same Streamlit run.
                # Rerun so the newly imported events appear immediately.
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(f"Google Calendar import failed: {exc}")

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
                 "This Google permission technically allows reading message bodies, "
                 "but AARON-1 only requests headers and snippets. "
                 "AARON-1 cannot send or delete messages. "
                 "The app checks Gmail only when you ask. "
                 "Tokens remain local in data/ and are excluded from GitHub. "
                 "Never upload Google passwords or private keys to the repository.")


@st.cache_data(ttl=45, show_spinner=False)
def available_local_models():
    return local_models()


def render_chat():
    page_heading(
        "Talk to AARON-1", "Your personal AI",
        "Ask about your day, make plans, and have real conversations "
        "when you enable a local chat model.",
    )
    with st.expander("🧠 Conversation settings", expanded=False):
        active_adapter = trained_model()
        ready = inference_dependencies_ready()
        ollama_options = available_local_models()
        # Direct Transformers inference needs no Ollama installation.
        options = (
            ["AARON-1 (pretrained · no Ollama)"] if ready else []
        ) + (
            ["AARON-1 (fine-tuned)"] if active_adapter else []
        ) + ["Planner only (rules)"] + ollama_options

        current = st.session_state.get("aaron_selected_chat_model")
        current_label = (
            "AARON-1 (fine-tuned)" if current == "__aaron_trained__"
            else "AARON-1 (pretrained · no Ollama)" if current == "__aaron_base__"
            else current if current in options else None
        )
        if current_label not in options:
            current_label = (
                "AARON-1 (fine-tuned)" if active_adapter and
                inference_dependencies_ready(adapter=True)
                else "AARON-1 (pretrained · no Ollama)" if ready
                else ollama_options[0] if ollama_options
                else "Planner only (rules)"
            )
        if st.session_state.get("aaron_model_picker") not in options:
            st.session_state.pop("aaron_model_picker", None)
        choice = st.selectbox(
            "Conversation engine", options,
            index=options.index(current_label),
            help="The pretrained model runs in Python, without Ollama. "
                 "A trained adapter is optional. Tasks change only through "
                 "verified commands.",
            key="aaron_model_picker",
        )
        st.session_state["aaron_selected_chat_model"] = (
            "__aaron_trained__" if choice == "AARON-1 (fine-tuned)"
            else "__aaron_base__" if choice == "AARON-1 (pretrained · no Ollama)"
            else None if choice == "Planner only (rules)"
            else choice
        )
        if choice == "AARON-1 (pretrained · no Ollama)":
            st.success("No Ollama needed. Qwen2.5 0.5B runs through PyTorch. "
                       "The first message downloads and caches the model.")
        elif choice == "AARON-1 (fine-tuned)":
            st.success("Using your fine-tuned adapter with the pretrained "
                       "Qwen base model. No Ollama needed.")
        elif choice in ollama_options:
            st.success("Using optional local Ollama.")
        else:
            st.info("Rule-based planner chat is active. For natural "
                    "conversations, install the training dependencies below.")
        if not ready:
            st.caption("One-time setup for pretrained chat and fine-tuning:")
            st.code(
                "python3 -m pip install -r requirements-training.txt",
                language="bash",
            )
        st.caption("Conversation runs on your computer, not ChatGPT's servers. "
                   "The model's base weights come from Hugging Face once; "
                   "your tasks and memories remain local.")
        if st.button("Refresh local models", key="refresh_local_models"):
            available_local_models.clear()
            st.rerun()

    previous = messages()
    if not previous:
        st.markdown(
            "Ask me something, for example **what should I do next?**, "
            "**what's due tomorrow?**, or "
            "**add task finish chemistry due tomorrow at 5pm**."
        )
    for item in previous:
        with st.chat_message(item["role"]):
            st.markdown(item["message"])
    prompt = st.chat_input("Talk to AARON-1…")
    if prompt:
        history = messages(limit=12)
        write_chat("user", prompt)
        # Preserve prior context without repeating the latest user message.
        reply = answer_with_context(prompt, history)
        write_chat("assistant", reply)
        st.rerun()

    with st.expander("Meet AARON-1", expanded=False):
        last = (previous[-1]["message"] if previous
                and previous[-1]["role"] == "assistant"
                else "Yo! What are we doing today?")
        render_face(last, key="home")


def answer_with_context(message, history):
    lower = message.lower()
    if any(phrase in lower for phrase in (
        "check my email", "check my gmail", "show my inbox", "latest emails",
        "new email", "my mail", "read my email",
    )):
        return answer(message)
    model = st.session_state.get("aaron_selected_chat_model")
    return respond(message, previous=history, model=model)[0]


def main():
    init_chat()
    ensure_schema()
    # Only once per local database, honoring the user's Winter Arc schedule.
    seed_winter_arc()
    from assistant_core import migrate_legacy_facts
    migrate_legacy_facts()

    install_theme()
    header()
    st.caption("AARON-1 build " + APP_BUILD + " · Color-coded calendar, weekly events, and linked assignments")

    # Google returns to this same local dashboard after the user approves OAuth.
    if "code" in st.query_params or "error" in st.query_params:
        try:
            finish_auth(st.query_params.to_dict())
            st.query_params.clear()
            st.toast("Gmail connected")
        except Exception as exc:
            st.query_params.clear()
            st.error(f"Gmail connection failed: {exc}")

    calendar_tab, task_tab, chat_tab, train_tab, connection_tab = st.tabs(
        ["Planner", "Priorities", "Chat", "Train AARON-1", "Connections"]
    )
    with calendar_tab:
        render_calendar()
    with task_tab:
        render_tasks()
    with chat_tab:
        render_chat()
    with train_tab:
        training_page(messages(limit=120))
    with connection_tab:
        render_connections()

    _, feedback_count = load_weights()
    st.markdown(
        '<div class="muted-line" style="margin-top:32px;padding-top:18px;'
        'border-top:1px solid #2a3242;">'
        f'AARON-1 · {feedback_count} personal priority decisions learned · '
        'Data saved locally</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
