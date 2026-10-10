"""AARON-1 — one local assistant, planner, and optional trainable language model."""
from __future__ import annotations

import html
import hmac
from datetime import date, timedelta

import streamlit as st

from assistant_core import (
    _configuration_value, persistent_database_configured,
    add_task, concise_reply, connect, learn_priority, list_tasks, parse_csv,
    parse_ics, ranked_tasks, score_task, update_task, load_weights,
    change_month, tasks_due_in_month, tasks_without_due_date, set_task_due_date,
)
from gmail_access import (
    check_account, client_ready, connected, disconnect, finish_auth,
    list_messages, make_auth_url, store_client_upload,
)
from ui_theme import install_theme, header, page_heading
from planner_ui import calendar_page, tasks_page
from planner import ensure_schema
from google_calendar_import import import_google_calendar
from winter_arc import seed_winter_arc
from assistant_conversation import respond, local_models
from training_ui import training_page
from training_data import trained_model
from trained_chat import inference_dependencies_ready
from data_backup import export_personal_data, restore_personal_data

APP_BUILD = "2026.10.10-minimal-workspace"

st.set_page_config(page_title="AARON-1", page_icon="📅", layout="wide")


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
            return "Latest Gmail inbox subjects:\n" + "\n".join(
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
        "SETTINGS",
        "Connections",
        "Link Gmail with read-only permission or import your school assignments. "
        "You control what AARON-1 can access.",
    )

    with st.container(border=True):
        st.markdown("### Data protection")
        if persistent_database_configured():
            st.success("Persistent database configured — events and chat are stored remotely.")
        else:
            st.warning(
                "Temporary local storage is in use. Streamlit Community Cloud "
                "can erase locally saved events, tasks and chat on reboot or sleep. "
                "Download a backup before restarting the app."
            )
        st.caption(
            "Private database setup: configure TURSO_DATABASE_URL, "
            "TURSO_AUTH_TOKEN and APP_PASSWORD in Streamlit Cloud Secrets. "
            "Do not paste credentials into GitHub."
        )
        try:
            backup = export_personal_data()
            st.download_button(
                "Download complete personal-data backup",
                data=backup,
                file_name="aaron1-personal-data.json",
                mime="application/json",
                use_container_width=True,
                key="aaron_export_backup",
            )
        except (ValueError, OSError, RuntimeError) as exc:
            st.error("Could not prepare data backup: " + str(exc))
        with st.expander("Restore a saved backup"):
            st.caption(
                "Restores missing entries only. Existing records are not overwritten "
                "or deleted. You can use this after switching to persistent storage."
            )
            restore_file = st.file_uploader(
                "AARON-1 backup JSON", type=["json"], key="aaron_restore_json"
            )
            confirm = st.checkbox(
                "I want to import missing records from this backup",
                key="aaron_restore_confirm",
            )
            if st.button(
                "Restore missing records", key="aaron_restore_button",
                disabled=restore_file is None or not confirm,
                use_container_width=True,
            ):
                try:
                    recovered = restore_personal_data(restore_file.getvalue())
                    st.success(f"Restored {recovered} previously missing records.")
                    st.rerun()
                except (ValueError, RuntimeError, OSError) as exc:
                    st.error("Restore failed: " + str(exc))

    with st.container(border=True):
        st.markdown("### Gmail")
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
        st.markdown("### Calendar import")
        st.caption(
            "Import your Google Calendar export directly, including the ZIP "
            "download. Event times, durations, multi-day entries and recurring "
            "instances are preserved. This makes a local copy only; nothing "
            "is uploaded to GitHub or changed in Google. AARON-1 shows your "
            "imported calendar events as saved, and its assistant answers "
            "schedule questions from actual stored event records, not guesses."
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
        st.markdown("### School assignments")
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
    """Dedicated conversation view; settings never crowd the message stream."""
    page_heading(
        "ASSISTANT", "Chat",
        "Plan your week, ask about your saved calendar, or talk to a local model.",
    )
    local = not bool(__import__("os").environ.get("RENDER"))
    active_adapter = trained_model() if local else None
    ready = inference_dependencies_ready() if local else False
    ollama_options = available_local_models() if local else []
    options = ["Planner (available everywhere)"]
    if ready:
        options.append("AARON-1 base (local)")
    if active_adapter and inference_dependencies_ready(adapter=True):
        options.append("AARON-1 trained (local)")
    options.extend(ollama_options)

    current = st.session_state.get("aaron_selected_chat_model")
    desired = (
        "AARON-1 trained (local)" if current == "__aaron_trained__"
        else "AARON-1 base (local)" if current == "__aaron_base__"
        else current if current in ollama_options
        else options[0]
    )
    if desired not in options:
        desired = options[0]
    if st.session_state.get("aaron_model_picker") not in options:
        st.session_state.pop("aaron_model_picker", None)
    model_col, detail_col = st.columns([2, 3], vertical_alignment="bottom")
    with model_col:
        selected = st.selectbox(
            "Conversation engine", options, index=options.index(desired),
            key="aaron_model_picker",
        )
    with detail_col:
        if selected == options[0]:
            st.caption(
                "Calendar and task commands are live. Open-ended language "
                "model chat requires local inference."
            )
        else:
            st.caption("Model runs on the machine hosting AARON-1.")
    st.session_state["aaron_selected_chat_model"] = (
        "__aaron_trained__" if selected == "AARON-1 trained (local)"
        else "__aaron_base__" if selected == "AARON-1 base (local)"
        else None if selected == options[0] else selected
    )

    previous = messages(limit=80)
    with st.container(height=600, border=True, key="aaron_chat_scroll_window"):
        if not previous:
            st.markdown("**Start a conversation**")
            st.caption(
                "Ask what's on your calendar tomorrow, what needs doing, "
                "or add a task with a due date."
            )
        for item in previous:
            if item["role"] in ("user", "assistant"):
                with st.chat_message(item["role"]):
                    st.markdown(item["message"])
    # IME-safe composer: a normal Enter keypress must never submit a message.
    # Chinese Pinyin/Japanese/Korean keyboards use Enter to confirm a character
    # candidate. Streamlit's chat_input can mistake that Enter for Send.
    # A text_area inside a form only submits when the explicit Send action is
    # chosen (or the user intentionally uses the form-submit shortcut).
    with st.form("aaron_chat_compose_form", clear_on_submit=True):
        prompt = st.text_area(
            "Your message",
            placeholder="Message AARON-1 · 中文输入也可以",
            height=90,
            key="aaron_chat_composer",
            help="Press Enter normally to compose/select Chinese characters. "
                 "Click Send when your message is complete.",
        )
        submitted = st.form_submit_button("Send", type="primary")
    if submitted and prompt.strip():
        history = messages(limit=12)
        write_chat("user", prompt.strip())
        try:
            reply = answer_with_context(prompt.strip(), history)
        except (ValueError, OSError) as exc:
            reply = f"Couldn't process that request ({type(exc).__name__})."
        write_chat("assistant", reply)
        st.rerun()

    with st.expander("Conversation data", expanded=False):
        st.caption(
            "Chat history is stored in the app's SQLite database. "
            "On Render's free, non-persistent instance it can be lost on redeploy. "
            "No conversation is automatically used for model training."
        )
        st.download_button(
            "Export chat history",
            data=__import__("json").dumps(previous, indent=2),
            file_name="aaron1-chat.json",
            mime="application/json",
            disabled=not bool(previous),
        )



def answer_with_context(message, history):
    lower = message.lower()
    if any(phrase in lower for phrase in (
        "check my email", "check my gmail", "show my inbox", "latest emails",
        "new email", "my mail", "read my email",
    )):
        return answer(message)
    model = st.session_state.get("aaron_selected_chat_model")
    return respond(message, previous=history, model=model)[0]


def render_planner_workspace():
    """Calendar and priority tools share one main page."""
    view = st.segmented_control(
        "Planner view", ["Calendar", "Tasks"], default="Calendar",
        key="aaron_planner_view",
    )
    if view == "Tasks":
        render_tasks()
    else:
        render_calendar()


def _require_password_if_configured():
    password = _configuration_value("APP_PASSWORD")
    if persistent_database_configured() and not password:
        st.error(
            "Cloud database is configured but APP_PASSWORD is missing from "
            "Streamlit Secrets. Add APP_PASSWORD to protect your school calendar."
        )
        st.stop()
    if not password or st.session_state.get("aaron_authenticated"):
        return
    st.title("AARON—1")
    st.caption("Private workspace")
    with st.form("aaron_password_gate"):
        entered = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Unlock")
    if submitted:
        if hmac.compare_digest(entered.encode("utf-8"), password.encode("utf-8")):
            st.session_state["aaron_authenticated"] = True
            st.rerun()
        st.error("Incorrect password")
    st.stop()


def main():
    _require_password_if_configured()
    init_chat()
    ensure_schema()
    # Only once per local database, honoring the user's Winter Arc schedule.
    seed_winter_arc()
    from assistant_core import migrate_legacy_facts
    migrate_legacy_facts()

    install_theme()

    # Native multi-page navigation: independent URLs and a single rendered view.
    pages = [
        st.Page(render_planner_workspace, title="Planner",
                url_path="planner", default=True),
        st.Page(render_chat, title="Chat", url_path="chat"),
        st.Page(lambda: training_page(messages(limit=120)),
                title="Model Lab", url_path="model-lab"),
        st.Page(render_connections, title="Settings", url_path="settings"),
    ]
    current_page = st.navigation(pages, position="sidebar")
    with st.sidebar:
        st.divider()
        st.caption("AARON—1")
        st.caption("Storage on this Render service is temporary.")
        st.caption("Back up your calendar before any deployment.")

    header()
    # OAuth callbacks return to the root, independent of the active page.
    if "code" in st.query_params or "error" in st.query_params:
        try:
            finish_auth(st.query_params.to_dict())
            st.query_params.clear()
            st.toast("Gmail connected")
        except Exception as exc:
            st.query_params.clear()
            st.error(f"Gmail connection failed: {exc}")

    if not persistent_database_configured():
        st.warning(
            "This app is using temporary storage. Rebooting or sleeping can erase "
            "events and chat. Open Settings → Data protection to download a backup "
            "and configure a persistent database."
        )
    current_page.run()

    st.markdown(
        '<div class="muted-line" style="margin-top:32px;padding-top:18px;'
        'border-top:1px solid #303439;">'
        'AARON—1 · ' + APP_BUILD + '</div>',
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    main()
