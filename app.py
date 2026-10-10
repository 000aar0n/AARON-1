"""AARON-1 — one assistant, one dashboard.

No LLM, agent network, mock multi-agent population, or access without permission.
"""
from __future__ import annotations

import calendar
import html
from datetime import timedelta
from collections import defaultdict
from datetime import date

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
from ui_theme import install_theme, header, page_heading, metric

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



def render_calendar():
    """Interactive monthly view with a focused day panel and real task actions."""
    today = date.today()
    if "calendar_month" not in st.session_state:
        st.session_state["calendar_month"] = today.replace(day=1).isoformat()
    if "calendar_selected" not in st.session_state:
        st.session_state["calendar_selected"] = today.isoformat()

    month = date.fromisoformat(st.session_state["calendar_month"])
    selected = date.fromisoformat(st.session_state["calendar_selected"])
    if (selected.year, selected.month) != (month.year, month.month):
        selected = month
        st.session_state["calendar_selected"] = selected.isoformat()

    page_heading(
        "Plan your week",
        "Your calendar",
        "A clear view of what's due, what's finished, and what needs your attention.",
    )

    month_tasks = tasks_due_in_month(month.year, month.month)
    by_day = defaultdict(list)
    for task in month_tasks:
        by_day[task["due"]].append(task)
    remaining = [task for task in month_tasks if not task["completed"]]
    today_count = len([task for task in remaining if task["due"] == today.isoformat()])
    completed_count = len(month_tasks) - len(remaining)

    a, b, c = st.columns(3, gap="medium")
    with a:
        metric("Assignments due", len(remaining), "In " + month.strftime("%B"))
    with b:
        metric("Due today", today_count, today.strftime("%a, %b %d"))
    with c:
        metric("Finished", completed_count, "Completed this month")

    grid_column, detail_column = st.columns([7.3, 3.7], gap="large")
    with grid_column:
        nav_prev, nav_title, nav_today, nav_next = st.columns(
            [0.8, 4.6, 1.25, 0.8], gap="small", vertical_alignment="center"
        )
        with nav_prev:
            if st.button("‹", key="cal_prev", help="Previous month",
                         use_container_width=True):
                target = change_month(month, -1)
                st.session_state["calendar_month"] = target.isoformat()
                st.session_state["calendar_selected"] = target.isoformat()
                st.rerun()
        with nav_title:
            st.markdown(
                '<div class="cal-month">' +
                html.escape(month.strftime("%B %Y")) + "</div>",
                unsafe_allow_html=True,
            )
        with nav_today:
            if st.button("Today", key="cal_today", use_container_width=True):
                st.session_state["calendar_month"] = today.replace(day=1).isoformat()
                st.session_state["calendar_selected"] = today.isoformat()
                st.rerun()
        with nav_next:
            if st.button("›", key="cal_next", help="Next month",
                         use_container_width=True):
                target = change_month(month, 1)
                st.session_state["calendar_month"] = target.isoformat()
                st.session_state["calendar_selected"] = target.isoformat()
                st.rerun()

        weekdays = st.columns(7, gap="small")
        for column, name in zip(weekdays, ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")):
            with column:
                st.markdown('<div class="cal-weekday">' + name + "</div>",
                            unsafe_allow_html=True)

        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(
            month.year, month.month
        ):
            columns = st.columns(7, gap="small")
            for column, day in zip(columns, week):
                with column:
                    style = ("outside" if day.month != month.month else
                             "selected" if day == selected else
                             "today" if day == today else "normal")
                    with st.container(
                        border=False, height=124,
                        key=f"cal-cell-{style}-{day.isoformat()}",
                    ):
                        if day.month != month.month:
                            st.markdown(
                                f'<div class="cal-outside-date">{day.day}</div>',
                                unsafe_allow_html=True,
                            )
                            continue

                        day_items = by_day.get(day.isoformat(), [])
                        unfinished = [item for item in day_items if not item["completed"]]
                        if st.button(
                            str(day.day), key=f"cal_day_{day.isoformat()}",
                            use_container_width=False,
                            help=(f"Select {day.strftime('%B %d')}: "
                                  f"{len(unfinished)} remaining"),
                        ):
                            st.session_state["calendar_selected"] = day.isoformat()
                            st.rerun()
                        if day == today:
                            st.markdown(
                                '<span class="cal-today-flag">TODAY</span>',
                                unsafe_allow_html=True,
                            )
                        if unfinished:
                            chips = []
                            for item in unfinished[:2]:
                                subject_class = (
                                    " school" if item.get("source") in ("blackbaud", "calendar")
                                    else ""
                                )
                                chips.append(
                                    '<div class="cal-event' + subject_class + '" title="' +
                                    html.escape(item["title"], quote=True) + '">' +
                                    html.escape(item["title"]) + "</div>"
                                )
                            if len(unfinished) > 2:
                                chips.append(
                                    '<div class="cal-more">+' +
                                    str(len(unfinished) - 2) + " more</div>"
                                )
                            chips.append(
                                '<div class="cal-count">' +
                                str(len(unfinished)) + ' due</div>'
                            )
                            st.markdown(
                                '<div class="cal-events">' + "".join(chips) + "</div>",
                                unsafe_allow_html=True,
                            )
                        elif day_items:
                            st.markdown('<div class="cal-finished">✓ All done</div>',
                                        unsafe_allow_html=True)
                        else:
                            st.markdown('<div class="cal-quiet">—</div>',
                                        unsafe_allow_html=True)

        st.markdown(
            '<div class="muted-line" style="margin-top:12px">'
            '<span style="color:#a79cff">●</span> Personal tasks &nbsp;&nbsp;'
            '<span style="color:#76d6c1">●</span> Imported assignments'
            '</div>', unsafe_allow_html=True,
        )

    with detail_column:
        with st.container(border=True, key="calendar-day-detail"):
            st.markdown('<div class="eyebrow">SELECTED DAY</div>',
                        unsafe_allow_html=True)
            st.markdown(
                '<div class="cal-detail-title">' +
                html.escape(selected.strftime("%A, %B ")) + str(selected.day) +
                '</div><div class="cal-detail-sub">' +
                str(selected.year) + " · " +
                str(len([t for t in by_day.get(selected.isoformat(), [])
                         if not t["completed"]])) +
                ' open assignment(s)</div>',
                unsafe_allow_html=True,
            )
            day_tasks = by_day.get(selected.isoformat(), [])
            pending = [task for task in day_tasks if not task["completed"]]
            completed = [task for task in day_tasks if task["completed"]]

            if not pending:
                st.markdown(
                    '<div class="cal-no-tasks">All clear for this day. '
                    'Enjoy the breathing room or add something below.</div>',
                    unsafe_allow_html=True,
                )

            for item in pending:
                with st.container(border=True, key=f"cal-task-{item['id']}"):
                    st.markdown(
                        '<div class="cal-task-title">' +
                        html.escape(item["title"]) + "</div>",
                        unsafe_allow_html=True,
                    )
                    source = ("School import" if item.get("source") in ("blackbaud", "calendar")
                              else "Gmail" if item.get("source") == "email"
                              else "Personal task")
                    st.markdown(
                        '<div class="cal-task-meta">' +
                        html.escape(source) + "</div>",
                        unsafe_allow_html=True,
                    )
                    done_col, important_col = st.columns(2, gap="small")
                    if done_col.button(
                        "✓ Done", key=f"cal_done_{item['id']}",
                        use_container_width=True,
                    ):
                        update_task(item["id"], completed=True)
                        st.rerun()
                    if important_col.button(
                        "↑ Important", key=f"cal_priority_{item['id']}",
                        use_container_width=True,
                    ):
                        learn_priority(item["id"], True)
                        st.rerun()

            if completed:
                with st.expander(f"Completed ({len(completed)})"):
                    for item in completed:
                        name_col, reopen_col = st.columns([4, 1.6])
                        name_col.caption(item["title"])
                        if reopen_col.button(
                            "Reopen", key=f"cal_reopen_{item['id']}",
                        ):
                            update_task(item["id"], completed=False)
                            st.rerun()

            st.divider()
            st.markdown("**Add an assignment**")
            with st.form("calendar_new_task", clear_on_submit=True):
                title = st.text_input(
                    "Task name", placeholder="e.g. Finish chemistry problems",
                    label_visibility="collapsed",
                )
                if st.form_submit_button(
                    "+ Add to " + selected.strftime("%b ") + str(selected.day),
                    type="primary", use_container_width=True,
                ):
                    try:
                        add_task(title, due=selected.isoformat())
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        no_date = tasks_without_due_date()
        if no_date:
            with st.expander(f"Unscheduled tasks ({len(no_date)})"):
                st.caption("Choose a date on the calendar, then schedule the task.")
                for item in no_date:
                    title_col, schedule_col = st.columns([3.2, 1.1])
                    title_col.caption(item["title"])
                    if schedule_col.button(
                        "Set date", key=f"cal_schedule_{item['id']}",
                        use_container_width=True,
                    ):
                        set_task_due_date(item["id"], selected.isoformat())
                        st.rerun()


def render_connections():
    st.subheader("Connect your accounts")
    st.caption("Nothing is connected until you authorize it. "
               "No password sharing, no sending mail, no deleting mail.")

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
    from assistant_core import migrate_legacy_facts
    migrate_legacy_facts()
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

    chat_tab, calendar_tab, task_tab, connection_tab = st.tabs(
        ["💬 Chat", "📅 Calendar", "✅ Tasks", "🔗 Connect"]
    )
    with chat_tab:
        render_chat()
    with calendar_tab:
        render_calendar()
    with task_tab:
        render_tasks()
    with connection_tab:
        render_connections()

    _, n = load_weights()
    st.caption(f"🧠 AARON-1 has learned from {n} priority decisions. "
               "Your files and saved memories stay on this Mac.")


if __name__ == "__main__":
    main()
