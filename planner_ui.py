"""FullCalendar + explainable task tracker for the AARON-1 Streamlit app."""
from __future__ import annotations

import html
from datetime import date, datetime, time, timedelta

import streamlit as st
from streamlit_calendar import calendar

from assistant_core import learn_priority
from planner import (
    PRIORITY_NAMES, calendar_events, create_item, daily_items, delete_item,
    get_item, items_for_calendar, next_actions, open_tasks, toggle_complete,
    update_item, set_priority,
)

CALENDAR_CSS = """
.fc {--fc-border-color:#2a3142; --fc-page-bg-color:#10151e;
     --fc-neutral-bg-color:#171e2a; --fc-today-bg-color:#7361c11a;
     color:#e5e8f1; font-family:Inter,system-ui,sans-serif}
.fc .fc-toolbar {margin-bottom:20px}
.fc .fc-toolbar-title {font-size:1.35rem;font-weight:740;letter-spacing:-.035em;color:#f5f6ff}
.fc .fc-button-primary {background:#262e40;border-color:#404b63;
  color:#dfe5f5;text-transform:capitalize;font-weight:650;border-radius:9px}
.fc .fc-button-primary:hover,.fc .fc-button-primary:not(:disabled).fc-button-active{
  background:#756bd0;border-color:#8279dc;color:#fff}
.fc .fc-button:focus {box-shadow:0 0 0 2px #a79cff88}
.fc .fc-col-header-cell {background:#171c28;padding:9px 0}
.fc .fc-col-header-cell-cushion {color:#a4adbf;text-transform:uppercase;
 font-size:11px;font-weight:750;letter-spacing:.075em}
.fc .fc-daygrid-day-number {color:#dfe4f5;font-size:13px;padding:9px}
.fc .fc-daygrid-day.fc-day-today {background:#7166bb1a}
.fc .fc-daygrid-event {border-radius:6px;padding:3px 5px;overflow:hidden}
.fc .fc-event-title {font-weight:650}
.fc .fc-timegrid-slot-label-cushion {color:#949fb0;font-size:11px}
.fc .fc-timegrid-now-indicator-line {border-color:#e8a16d;border-width:2px}
.fc .fc-timegrid-now-indicator-arrow {border-color:#e8a16d}
.fc .fc-list-day-cushion {background:#252d3c!important;color:#f4f6fa}
.fc .fc-list-event:hover td {background:#2b3447!important}
.fc .fc-list-event-title a {color:#f2f3f9}
.fc a {text-decoration:none}
.fc .fc-popover {background:#192031;color:#f6f7ff;border-color:#45516a}
.fc .fc-daygrid-more-link {color:#bfbaff;font-size:11px}
.fc .fc-highlight {background:#9386ff33}
.fc .fc-view-harness{border:1px solid #30394c;border-radius:13px;overflow:hidden}
@media(max-width:850px){.fc .fc-toolbar-title{font-size:1.04rem}
 .fc .fc-button{font-size:.75rem;padding:.4em .55em}}
"""


def _safe_day(raw):
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return date.today()


def _safe_clock(raw, fallback="16:00"):
    try:
        if raw:
            return time.fromisoformat(str(raw)[:5])
    except (TypeError, ValueError):
        pass
    return time.fromisoformat(fallback)


def _format_deadline(task):
    if not task.get("due"):
        return "No due date"
    value = date.fromisoformat(task["due"]).strftime("%b %d")
    if task.get("due_time"):
        value += " · " + _safe_clock(task["due_time"]).strftime("%I:%M %p").lstrip("0")
    return value


def _choose_item(item_id):
    st.session_state["planner_editor_id"] = item_id
    st.session_state["planner_editor_nonce"] = (
        st.session_state.get("planner_editor_nonce", 0) + 1
    )


def _new_item(day=None, at_time=None, kind="task"):
    st.session_state["planner_editor_id"] = None
    st.session_state["planner_editor_nonce"] = (
        st.session_state.get("planner_editor_nonce", 0) + 1
    )
    st.session_state["planner_new_date"] = (
        day if isinstance(day, date) else _safe_day(day) if day else date.today()
    )
    st.session_state["planner_new_clock"] = (
        at_time if isinstance(at_time, time) else _safe_clock(at_time)
        if at_time else time(16, 0)
    )
    st.session_state["planner_new_kind"] = kind


def _render_editor():
    """One editor for tasks/events; retained data is the same across pages."""
    existing = get_item(st.session_state.get("planner_editor_id")) if (
        st.session_state.get("planner_editor_id")) else None
    nonce = st.session_state.get("planner_editor_nonce", 0)
    prefix = f"planner_{nonce}"
    name = "Edit entry" if existing else "Create an entry"
    st.markdown("#### " + name)

    kind_default = (existing.get("item_type") or "task") if existing else (
        st.session_state.get("planner_new_kind", "task"))
    initial_date = (_safe_day(existing["due"]) if existing and existing.get("due")
                    else st.session_state.get("planner_new_date", date.today()))
    initial_time = (_safe_clock(existing.get("due_time")) if existing else
                    st.session_state.get("planner_new_clock", time(16, 0)))
    chosen_priority = int(existing.get("priority_level") or 2) if existing else 2

    # Controls which change the form's layout must be outside st.form;
    # otherwise Streamlit won't update duration/estimate fields until saving.
    category = st.segmented_control(
        "Type", ["Task", "Event"],
        default="Event" if kind_default == "event" else "Task",
        key=f"{prefix}_type",
    )
    default_all_day = not bool(existing.get("due_time")) if existing else False
    all_day = st.checkbox(
        "All-day / no exact time", value=default_all_day, key=f"{prefix}_allday"
    )
    with st.form(f"{prefix}_form", clear_on_submit=False):
        title = st.text_input(
            "Title", value=(existing["title"] if existing else ""),
            placeholder="Chemistry lab, soccer practice, finish essay…",
            key=f"{prefix}_title",
        )
        description = st.text_area(
            "Description / notes", value=(existing.get("notes") or "") if existing else "",
            placeholder="Instructions, links, things to remember…", height=95,
            key=f"{prefix}_description",
        )
        date_col, clock_col = st.columns(2)
        with date_col:
            selected_date = st.date_input(
                "Date / due date", value=initial_date, key=f"{prefix}_date"
            )
        with clock_col:
            selected_time = st.time_input(
                "Start / due time", value=initial_time, step=900,
                disabled=all_day, key=f"{prefix}_time"
            )
        if category == "Event":
            duration = st.selectbox(
                "Length", [15, 30, 45, 60, 90, 120, 180, 240, 480],
                index=([15, 30, 45, 60, 90, 120, 180, 240, 480].index(
                    int(existing.get("duration_min") or 60))
                    if existing and int(existing.get("duration_min") or 60)
                    in [15, 30, 45, 60, 90, 120, 180, 240, 480] else 3),
                format_func=lambda n: f"{n // 60} hr {n % 60} min" if n >= 60 else f"{n} min",
                key=f"{prefix}_duration",
                disabled=all_day,
            )
            estimate = 30
            priority = 2
        else:
            priority = st.select_slider(
                "Priority",
                options=[1, 2, 3, 4], value=chosen_priority,
                format_func=lambda p: PRIORITY_NAMES[p],
                key=f"{prefix}_priority",
            )
            estimate_choices = [10, 15, 20, 30, 45, 60, 75, 90, 120, 180, 240]
            previous = int(existing.get("estimated_min") or 30) if existing else 30
            estimate = st.selectbox(
                "How much work?",
                estimate_choices,
                index=(estimate_choices.index(previous) if previous in estimate_choices else 3),
                format_func=lambda n: f"{n} minutes" if n < 60 else f"{n / 60:g} hours",
                key=f"{prefix}_estimate",
            )
            duration = 60

        submitted = st.form_submit_button(
            "Save changes" if existing else "Create",
            type="primary", use_container_width=True,
        )
    if submitted:
        details = dict(
            title=title, description=description,
            due=selected_date.isoformat(),
            due_time=None if all_day else selected_time.strftime("%H:%M"),
            item_type="event" if category == "Event" else "task",
            priority=priority, duration_min=duration, estimated_min=estimate,
        )
        try:
            if existing:
                update_item(existing["id"], **details)
                st.toast("Changes saved locally")
            else:
                new_id = create_item(**details)
                st.session_state["planner_editor_id"] = new_id
                st.toast("Added to your calendar")
            st.session_state["planner_editor_nonce"] = nonce + 1
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    if existing:
        b1, b2 = st.columns(2, gap="small")
        if existing.get("item_type", "task") == "task":
            if b1.button(
                "Reopen" if existing.get("completed") else "✓ Mark done",
                key=f"{prefix}_complete", use_container_width=True,
            ):
                toggle_complete(existing["id"], not bool(existing.get("completed")))
                st.rerun()
        if b2.button("Close editor", key=f"{prefix}_close", use_container_width=True):
            _new_item(day=st.session_state.get("planner_new_date", date.today()))
            st.rerun()
        with st.expander("Delete this entry"):
            st.caption("This permanently deletes the local copy. Imported source "
                       "calendars and school accounts are never changed.")
            confirm = st.checkbox("Yes, delete it", key=f"{prefix}_confirm")
            if st.button(
                "Delete", key=f"{prefix}_delete", disabled=not confirm,
            ):
                delete_item(existing["id"])
                _new_item()
                st.toast("Entry deleted")
                st.rerun()


def _action_list(limit=5):
    actions = next_actions(limit=limit)
    if not actions:
        st.success("You're clear! No outstanding tasks.")
        return
    for rank, task in enumerate(actions, 1):
        with st.container(border=True, key=f"recommended_{task['id']}"):
            head, grade = st.columns([5, 1])
            head.markdown("**" + html.escape(task["title"]) + "**")
            grade.caption(f"#{rank}")
            st.caption(f"{_format_deadline(task)} · {PRIORITY_NAMES[int(task.get('priority_level') or 2)]}")
            st.caption("Why: " + task["why"])
            if task.get("notes"):
                st.caption("Notes: " + str(task["notes"])[:200])
            c1, c2, c3 = st.columns([1, 1.4, 1], gap="small")
            if c1.button("✓ Done", key=f"rec_done_{task['id']}",
                         use_container_width=True):
                toggle_complete(task["id"], True)
                st.rerun()
            if c2.button("↑ Important", key=f"rec_raise_{task['id']}",
                         use_container_width=True):
                set_priority(task["id"], min(4, int(task.get("priority_level") or 2) + 1))
                st.rerun()
            if c3.button("Edit", key=f"rec_edit_{task['id']}",
                         use_container_width=True):
                _choose_item(task["id"])
                st.rerun()


def calendar_page():
    from ui_theme import page_heading, metric
    page_heading(
        "Time & priorities", "Your planner",
        "Timed events, assignment deadlines, and a clear next step — in one place.",
    )
    actions = next_actions(10)
    today = date.today()
    today_items = daily_items(today)
    all_open = open_tasks()
    a, b, c = st.columns(3)
    with a:
        metric("Open tasks", len(all_open), "Across your schedule")
    with b:
        metric("On today's calendar", len(today_items), "Events and deadlines")
    with c:
        metric("Next move", "Ready" if actions else "All clear",
               actions[0]["title"][:32] if actions else "No tasks waiting")

    left, right = st.columns([3.65, 1.35], gap="large")
    with left:
        all_events = calendar_events(items_for_calendar())
        options = {
            "initialView": "timeGridWeek",
            "headerToolbar": {
                "left": "today prev,next", "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
            },
            "views": {
                "dayGridMonth": {"dayMaxEventRows": 3},
                "timeGridWeek": {"slotMinTime": "06:00:00"},
            },
            "firstDay": 1,
            "height": 760,
            "nowIndicator": True,
            "weekNumbers": False,
            "editable": False,
            "selectable": True,
            "selectMirror": True,
            "navLinks": True,
            "eventTimeFormat": {"hour": "numeric", "minute": "2-digit", "meridiem": "short"},
            "slotMinTime": "06:00:00",
            "slotMaxTime": "23:00:00",
            "slotDuration": "00:30:00",
            "scrollTime": "08:00:00",
            "allDaySlot": True,
            "dayMaxEvents": 3,
            "eventDisplay": "block",
            "buttonText": {"today": "Today", "month": "Month",
                           "week": "Week", "day": "Day", "list": "Agenda"},
        }
        result = calendar(
            events=all_events,
            options=options,
            custom_css=CALENDAR_CSS,
            callbacks=["dateClick", "eventClick", "select"],
            key="aaron_planner_calendar_v2",
        )
        if isinstance(result, dict):
            callback = result.get("callback")
            if callback == "eventClick":
                clicked = result.get("eventClick") or {}
                event = clicked.get("event") or {}
                item_id = str(event.get("id") or "")
                if item_id and get_item(item_id):
                    if st.session_state.get("planner_editor_id") != item_id:
                        _choose_item(item_id)
            elif callback in ("dateClick", "select"):
                details = result.get(callback) or {}
                raw = details.get("date") or details.get("start")
                if raw:
                    clicked_day = _safe_day(raw)
                    clock = None if details.get("allDay", True) else _safe_clock(str(raw)[11:16])
                    signature = (callback, str(raw))
                    if st.session_state.get("planner_last_click") != signature:
                        st.session_state["planner_last_click"] = signature
                        _new_item(day=clicked_day, at_time=clock)
        st.caption("Click any date to create something; click an event or task to edit it. "
                   "Use Month / Week / Day / Agenda to switch views. Times are shown "
                   "in your browser's local timezone.")
        st.markdown("#### Your next moves")
        _action_list(limit=4)

    with right:
        st.markdown("#### 🎯 What to do now")
        if actions:
            top = actions[0]
            with st.container(border=True, key="next_task_spotlight"):
                st.markdown("**" + html.escape(top["title"]) + "**")
                st.caption(_format_deadline(top) + " · " + top["why"])
                if top.get("notes"):
                    st.caption("Notes: " + str(top["notes"])[:160])
                done, edit = st.columns(2)
                if done.button("✓ Done", key="spotlight_done",
                               use_container_width=True):
                    toggle_complete(top["id"], True)
                    st.rerun()
                if edit.button("Edit task", key="spotlight_edit",
                               use_container_width=True):
                    _choose_item(top["id"])
                    st.rerun()
        else:
            st.success("Nothing urgent — you're all caught up.")
        top1, top2 = st.columns(2)
        if top1.button("+ New task", use_container_width=True, type="primary",
                       key="planner_new_task"):
            _new_item(kind="task")
            st.rerun()
        if top2.button("+ Event", use_container_width=True, key="planner_new_event"):
            _new_item(kind="event")
            st.rerun()
        with st.container(border=True, key="planner_editor_panel"):
            _render_editor()
        with st.expander("What's on the selected day?"):
            selected = st.session_state.get("planner_new_date", today)
            if not isinstance(selected, date):
                selected = _safe_day(selected)
            st.write(f"**{selected.strftime('%A, %b %d')}**")
            on_day = daily_items(selected)
            if not on_day:
                st.caption("Nothing scheduled here yet.")
            for item in on_day:
                label = _format_deadline(item)
                label += "  ·  " + item["title"]
                if st.button(label, key=f"day_entry_{item['id']}"):
                    _choose_item(item["id"])
                    st.rerun()


def tasks_page():
    from ui_theme import page_heading, metric
    page_heading("Do the right thing next", "Task priorities",
                 "AARON-1 weighs deadlines, your chosen priority, and your feedback.")
    actions = next_actions(limit=60)
    total = len(open_tasks())
    urgent = sum(int(t.get("priority_level") or 2) == 4 for t in open_tasks())
    c1, c2, c3 = st.columns(3)
    with c1:
        metric("Open", total)
    with c2:
        metric("Urgent", urgent)
    with c3:
        metric("Next up", actions[0]["title"][:26] if actions else "All done")

    main_col, edit_col = st.columns([3, 1.6], gap="large")
    with main_col:
        st.markdown("### What should I do next?")
        st.caption("Sorted by real due dates and your priorities. Explanations are "
                   "shown for every recommendation.")
        _action_list(limit=12)
        st.divider()
        with st.expander("All open tasks"):
            for task in open_tasks():
                a, b, c = st.columns([5, 1, 1.3])
                a.write(task["title"])
                b.caption(_format_deadline(task))
                if c.button("Edit", key=f"all_edit_{task['id']}"):
                    _choose_item(task["id"])
                    st.rerun()
        st.caption("Marking a task important also trains AARON-1's local "
                   "personal ranking model.")
    with edit_col:
        if st.button("+ Create task", key="priority_add_new", type="primary",
                     use_container_width=True):
            _new_item(kind="task")
            st.rerun()
        with st.container(border=True):
            _render_editor()
