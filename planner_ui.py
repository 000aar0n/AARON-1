"""FullCalendar + explainable task tracker for the AARON-1 Streamlit app."""
from __future__ import annotations

import html
import sqlite3
from datetime import date, datetime, time, timedelta

import streamlit as st
from streamlit_calendar import calendar

from assistant_core import learn_priority
from winter_arc import upcoming_workout
from planner import (
    EVENT_COLORS, PRIORITY_NAMES, all_tasks, calendar_events,
    clear_manually_added_tasks, create_item, daily_items, delete_item,
    effective_color_name, get_item, items_for_calendar, linkable_events,
    manually_added_task_count, next_actions, open_tasks, related_assignments,
    toggle_complete, update_item, set_priority,
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
.fc .fc-daygrid-event {border-radius:6px;padding:5px 7px;min-height:29px;
 border-left-width:4px!important;overflow:visible!important;white-space:normal!important}
.fc .fc-event-title,.fc .fc-list-event-title {
 font-size:12px!important;line-height:1.35!important;font-weight:760!important;
 white-space:normal!important;overflow-wrap:anywhere!important;
 word-break:normal!important;letter-spacing:.01em}
.fc .fc-event-main,.fc .fc-event-main-frame {overflow:visible!important;
 white-space:normal!important}
.fc .fc-event-time {font-size:11px!important;font-weight:800!important;
 white-space:nowrap!important;margin-right:4px}
.fc .fc-timegrid-event {min-height:24px!important;border-left-width:4px!important;
 padding:3px 5px!important}
.fc .fc-timegrid-event .fc-event-title {
 white-space:normal!important;overflow-wrap:anywhere!important}
.fc .fc-daygrid-dot-event {padding:4px!important}
.fc .fc-list-event td {padding:10px 12px!important}
.fc .fc-list-event-title a {font-weight:760!important;white-space:normal!important}
.fc .fc-daygrid-more-link {font-size:12px!important;font-weight:750!important}
.fc .fc-daygrid-event .fc-event-main {white-space:normal!important}
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
/* The calendar now owns the FULL page width, with no editor sidebar. */
.fc .fc-daygrid-day-frame{min-height:125px}
.fc .fc-daygrid-event-harness{margin:2px 2px 3px}
.fc .fc-daygrid-event,.fc .fc-timegrid-event,.fc .fc-list-event{
  cursor:pointer}
.fc .fc-event-title,.fc .fc-list-event-title{
  font-size:13px!important;font-weight:780!important;
  line-height:1.45!important;overflow-wrap:break-word!important}
.fc .fc-daygrid-event .fc-event-title{display:block!important;
  white-space:normal!important;text-overflow:clip!important}
.fc .fc-timegrid-event .fc-event-main{padding:2px 4px!important}
.fc .fc-timegrid-event .fc-event-title{max-height:none!important}
.fc .fc-daygrid-more-link{font-size:13px!important;
  padding:4px!important;color:#d8d2ff!important}
/* Click feedback for mouse, keyboard and persisted selection. */
.fc .fc-event:hover{outline:2px solid #b9b4ff!important;
  outline-offset:1px!important;filter:brightness(1.14)!important;
  box-shadow:0 3px 14px #12122290!important;z-index:9!important}
.fc .fc-event:focus,.fc .fc-event:focus-visible{
  outline:3px solid #f9efb3!important;outline-offset:1px!important;
  box-shadow:0 0 0 4px #7566de5c!important;z-index:10!important}
.fc .fc-event.aaron-event-selected{
  outline:3px solid #f9edac!important;outline-offset:1px!important;
  box-shadow:0 0 0 5px #7870d46e,0 5px 22px #06080caa!important;
  filter:brightness(1.2)!important;z-index:11!important}
.fc .fc-col-header-cell-cushion{font-size:12px!important}
.fc .fc-timegrid-axis,.fc .fc-timegrid-slot-label{min-width:58px}
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
    # Occurrences are virtual: clicking one edits its parent weekly series.
    raw = str(item_id or "")
    parent, separator, occurrence = raw.partition("::")
    st.session_state["planner_editor_id"] = parent
    st.session_state["planner_selected_occurrence"] = (
        occurrence if separator else None
    )
    st.session_state["planner_editor_nonce"] = (
        st.session_state.get("planner_editor_nonce", 0) + 1
    )


def _new_item(day=None, at_time=None, kind="task", linked_event_id=None):
    st.session_state["planner_editor_id"] = None
    st.session_state["planner_selected_occurrence"] = None
    st.session_state["planner_new_parent"] = linked_event_id
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


def _render_editor(*, scope):
    """One editor; each Streamlit tab has unique widget keys, shared task state."""
    if scope not in ("calendar", "priorities"):
        raise ValueError("Invalid editor scope")
    existing = get_item(st.session_state.get("planner_editor_id")) if (
        st.session_state.get("planner_editor_id")) else None
    nonce = st.session_state.get("planner_editor_nonce", 0)
    prefix = f"{scope}_planner_{nonce}"
    name = "Edit entry" if existing else "Create an entry"
    st.markdown("#### " + name)
    if scope == "calendar" and existing:
        st.markdown("### " + html.escape(existing["title"]))
        st.caption(
            ("📅 Event · " if (existing.get("item_type") or "task") == "event"
             else "✅ Assignment · ") + _format_deadline(existing)
        )
    if existing and existing.get("repeat_weekly"):
        st.info("↻ This is a weekly series. Changes here update every occurrence "
                "in the series, not just the date you clicked.")

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
    weekly = False
    if category == "Event":
        weekly = st.checkbox(
            "↻ Repeat every week", value=bool(existing.get("repeat_weekly"))
            if existing and kind_default == "event" else False,
            key=f"{prefix}_weekly",
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
        colors = list(EVENT_COLORS)
        previous_color = existing.get("color_name") or "Auto" if existing else "Auto"
        color_name = st.selectbox(
            "🎨 Calendar color", colors,
            index=colors.index(previous_color) if previous_color in colors else 0,
            key=f"{prefix}_color",
            help="Automatic colors use the source (Google, Winter Arc) or task priority.",
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
        repeat_until = None
        if category == "Event":
            if weekly:
                repeat_until = st.date_input(
                    "Repeat weekly until (inclusive)",
                    value=_safe_day(existing["repeat_until"]) if (
                        existing and existing.get("repeat_until")
                    ) else initial_date + timedelta(weeks=12),
                    key=f"{prefix}_weekly_until",
                )
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
            linked_event_id = None
        else:
            options = linkable_events()
            by_id = {event["id"]: event for event in options}
            event_ids = [None] + list(by_id)
            selected_parent = (
                existing.get("linked_event_id") if existing
                else st.session_state.get("planner_new_parent")
            )
            linked_event_id = st.selectbox(
                "📎 Attach assignment to an event (optional)",
                event_ids,
                index=event_ids.index(selected_parent)
                if selected_parent in event_ids else 0,
                format_func=lambda key: (
                    "Not attached" if key is None else (
                        by_id[key]["title"] + " · " + (by_id[key].get("due") or "")
                        + (" · weekly" if by_id[key].get("repeat_weekly") else "")
                    )
                ),
                key=f"{prefix}_linked_event",
                help="Link a homework assignment to a class or weekly event. "
                     "The assignment keeps its own due date and priority.",
            )
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
            key=f"{prefix}_save",
        )
    if submitted:
        details = dict(
            title=title, description=description,
            due=selected_date.isoformat(),
            due_time=None if all_day else selected_time.strftime("%H:%M"),
            item_type="event" if category == "Event" else "task",
            priority=priority, duration_min=duration, estimated_min=estimate,
            color_name=color_name, repeat_weekly=weekly,
            repeat_until=repeat_until, linked_event_id=linked_event_id,
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
            if scope == "calendar":
                _dismiss_calendar_popup()
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    if existing:
        if (existing.get("item_type") or "task") == "task" and existing.get("linked_event_id"):
            parent = get_item(existing["linked_event_id"])
            if parent:
                st.caption("📎 Attached to: " + parent["title"])
        if (existing.get("item_type") or "task") == "event":
            related = related_assignments(existing["id"])
            st.markdown("##### 📎 Assignments linked to this event")
            if not related:
                st.caption("No assignments attached yet.")
            for linked_task in related:
                one, two = st.columns([3, 1])
                one.caption(
                    ("✓ " if linked_task.get("completed") else "") +
                    linked_task["title"] + " · " + _format_deadline(linked_task)
                )
                if two.button(
                    "Edit", key=f"{prefix}_linked_edit_{linked_task['id']}"
                ):
                    _choose_item(linked_task["id"])
                    st.rerun()
            if st.button(
                "+ Add assignment to this event",
                key=f"{prefix}_create_attached",
                use_container_width=True,
            ):
                _new_item(kind="task", linked_event_id=existing["id"])
                st.rerun()
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
            if scope == "calendar":
                _dismiss_calendar_popup()
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
                if scope == "calendar":
                    _dismiss_calendar_popup()
                st.toast("Entry deleted")
                st.rerun()


def _action_list(limit=5, *, scope):
    """Show a duplicated recommendation list with unique keys per tab."""
    if scope not in ("calendar", "priorities"):
        raise ValueError("Invalid recommendation scope")
    actions = next_actions(limit=limit)
    if not actions:
        st.success("You're clear! No outstanding tasks.")
        return
    for rank, task in enumerate(actions, 1):
        with st.container(border=True, key=f"{scope}_recommended_{task['id']}"):
            head, grade = st.columns([5, 1])
            head.markdown("**" + html.escape(task["title"]) + "**")
            grade.caption(f"#{rank}")
            st.caption(f"{_format_deadline(task)} · {PRIORITY_NAMES[int(task.get('priority_level') or 2)]}")
            st.caption("Why: " + task["why"])
            if task.get("notes"):
                st.caption("Notes: " + str(task["notes"])[:200])
            c1, c2, c3 = st.columns([1, 1.4, 1], gap="small")
            if c1.button("✓ Done", key=f"{scope}_rec_done_{task['id']}",
                         use_container_width=True):
                toggle_complete(task["id"], True)
                st.rerun()
            if c2.button("↑ Important", key=f"{scope}_rec_raise_{task['id']}",
                         use_container_width=True):
                set_priority(task["id"], min(4, int(task.get("priority_level") or 2) + 1))
                st.rerun()
            if c3.button("Edit", key=f"{scope}_rec_edit_{task['id']}",
                         use_container_width=True):
                _choose_item(task["id"])
                if scope == "calendar":
                    st.session_state["planner_popup_open"] = True
                st.rerun()


def _dismiss_calendar_popup():
    """Called when the modal is dismissed, saved, or explicitly closed."""
    st.session_state["planner_popup_open"] = False
    # Keep selected event highlighted after the dialog closes so it's obvious
    # which calendar item was just inspected/edited.


def _open_calendar_popup(*, item_id=None, day=None, at_time=None, kind="task"):
    """Set the selected record; only the calendar tab shows a modal."""
    if item_id is not None:
        st.session_state["planner_highlight_id"] = str(item_id)
        _choose_item(item_id)
    else:
        st.session_state.pop("planner_highlight_id", None)
        _new_item(day=day, at_time=at_time, kind=kind)
    st.session_state["planner_popup_open"] = True


@st.dialog("Calendar details", width="large", on_dismiss=_dismiss_calendar_popup)
def _calendar_editor_dialog():
    """Create/edit in a roomy modal so events retain the full page width."""
    _render_editor(scope="calendar")
    if st.button("Cancel / Close", key="calendar_dialog_cancel", use_container_width=True):
        _dismiss_calendar_popup()
        st.rerun()


def calendar_page():
    from ui_theme import page_heading, metric
    page_heading(
        "Time & priorities", "Your planner",
        "Your classes, assignments and workouts — full-size. Click anything to "
        "open a popup; the calendar stays wide.",
    )
    today = date.today()
    upcoming = upcoming_workout(today)
    if upcoming:
        workout_day, kind = upcoming
        if workout_day == today:
            st.info(
                f"🏋️ **Winter Arc reminder · Today: {kind}** "
                "— Click today's event to view your workout and reps."
            )
        else:
            st.caption(
                f"🏋️ Next Winter Arc session: {workout_day.strftime('%a, %b %d')} "
                f"· {kind}. The plan ends December 30, 2026."
            )

    # These are CLASSES imported from Google, not a generic "Google" category.
    # The legend describes the meaning the user gave the colors.
    keys = [
        ("Classes", "Blue"), ("Winter Arc", "Green"), ("Other events", "Teal"),
        ("Homework", "Purple"), ("High priority", "Orange"),
        ("Urgent", "Red"),
    ]
    legend = "".join(
        '<span style="display:inline-flex;align-items:center;gap:6px;'
        'padding:5px 9px;margin:0 6px 6px 0;border:1px solid #344052;'
        'border-radius:8px;font-size:12px;color:#e2e8f5">'
        '<i style="display:inline-block;width:10px;height:10px;'
        'border-radius:3px;background:' + EVENT_COLORS[color] + '"></i>'
        + label + '</span>'
        for label, color in keys
    )
    st.markdown(legend, unsafe_allow_html=True)

    new_task, new_event, hint = st.columns([1.1, 1.1, 4], gap="small")
    if new_task.button(
        "+ New task", use_container_width=True, type="primary",
        key="planner_new_task",
    ):
        _open_calendar_popup(kind="task")
    if new_event.button(
        "+ New event", use_container_width=True, key="planner_new_event"
    ):
        _open_calendar_popup(kind="event")
    hint.caption(
        "Click a class to see its FULL title and attached assignments, "
        "or click/drag an empty slot to create something."
    )

    # Full-width calendar. Weekly occurrences are expanded only for the
    # supported nearby range; the single canonical event remains editable.
    range_start = today - timedelta(days=365)
    range_end = today + timedelta(days=730)
    all_events = calendar_events(
        items_for_calendar(start=range_start, end=range_end),
        start=range_start, end=range_end,
    )
    selected_event_id = st.session_state.get("planner_highlight_id")
    if selected_event_id:
        for calendar_event in all_events:
            if calendar_event["id"] == selected_event_id:
                calendar_event["classNames"] = ["aaron-event-selected"]
    options = {
        "initialView": "timeGridWeek",
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
        },
        "views": {
            "dayGridMonth": {
                "dayMaxEventRows": 5,
                "fixedWeekCount": False,
            },
            "timeGridWeek": {
                "slotMinTime": "06:00:00",
                "slotMaxTime": "23:00:00",
            },
        },
        "firstDay": 1,
        "height": 980,
        "expandRows": True,
        "nowIndicator": True,
        "editable": False,
        "selectable": True,
        "selectMirror": True,
        "navLinks": True,
        "slotEventOverlap": False,
        "eventMinHeight": 34,
        "eventShortHeight": 42,
        "eventTimeFormat": {
            "hour": "numeric", "minute": "2-digit", "meridiem": "short"
        },
        "slotMinTime": "06:00:00",
        "slotMaxTime": "23:00:00",
        "slotDuration": "00:30:00",
        "scrollTime": "08:00:00",
        "allDaySlot": True,
        "dayMaxEvents": 5,
        "moreLinkClick": "popover",
        "eventDisplay": "block",
        "buttonText": {
            "today": "Today", "month": "Month", "week": "Week",
            "day": "Day", "list": "Agenda"
        },
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
            parent_id = item_id.split("::", 1)[0]
            signature = ("eventClick", item_id)
            if parent_id and get_item(parent_id):
                if st.session_state.get("planner_last_click") != signature:
                    st.session_state["planner_last_click"] = signature
                    _open_calendar_popup(item_id=item_id)
                    st.rerun()  # Rerender to show the selected event outline.
        elif callback in ("dateClick", "select"):
            details = result.get(callback) or {}
            raw = details.get("date") or details.get("start")
            if raw:
                signature = (callback, str(raw))
                if st.session_state.get("planner_last_click") != signature:
                    st.session_state["planner_last_click"] = signature
                    clock = (
                        None if details.get("allDay", True)
                        else _safe_clock(str(raw)[11:16])
                    )
                    _open_calendar_popup(
                        day=_safe_day(raw), at_time=clock, kind="event",
                    )
        else:
            # Allows clicking the same event again after another interaction.
            st.session_state.pop("planner_last_click", None)

    st.caption(
        "Bigger calendar · click an event to read/edit in a popup · click or "
        "drag an empty time slot to add one · use Month, Week, Day, or Agenda. "
        "Long titles also appear in full when opened."
    )

    # Keep the planner itself uncluttered; supporting panels sit BELOW it.
    with st.expander("🎯 Your next moves", expanded=False):
        actions = next_actions(10)
        all_open = open_tasks()
        today_items = daily_items(today)
        a, b, c = st.columns(3)
        with a:
            metric("Open tasks", len(all_open), "Across your schedule")
        with b:
            metric("On today's calendar", len(today_items), "Events and deadlines")
        with c:
            metric(
                "Next move", "Ready" if actions else "All clear",
                actions[0]["title"][:55] if actions else "No tasks waiting",
            )
        _action_list(limit=4, scope="calendar")

    with st.expander("📅 What's on the selected day?", expanded=False):
        selected = st.session_state.get("planner_new_date", today)
        if not isinstance(selected, date):
            selected = _safe_day(selected)
        st.write(f"**{selected.strftime('%A, %b %d')}**")
        on_day = daily_items(selected)
        if not on_day:
            st.caption("Nothing scheduled here yet.")
        for item in on_day:
            label = _format_deadline(item) + " · " + item["title"]
            if st.button(label, key=f"day_entry_{item['id']}"):
                _open_calendar_popup(item_id=item["id"])

    # Streamlit renders a single modal on this page at a time, not a
    # permanently visible editor that squeezes the calendar columns.
    if st.session_state.get("planner_popup_open"):
        _calendar_editor_dialog()


def _task_delete_controls():
    """List-only delete flow with explicit per-task confirmation."""
    item_id = st.session_state.get("planner_pending_delete_id")
    if not item_id:
        return
    item = get_item(item_id)
    if not item or (item.get("item_type") or "task") != "task":
        st.session_state.pop("planner_pending_delete_id", None)
        return
    st.warning("Delete task **" + html.escape(item["title"]) + "**? "
               "This deletes the local task, not its school/email source.")
    confirm, cancel = st.columns(2)
    if confirm.button(
        "Yes, delete task", key="priorities_confirm_single_delete",
        type="primary", use_container_width=True,
    ):
        delete_item(item_id)
        st.session_state.pop("planner_pending_delete_id", None)
        if st.session_state.get("planner_editor_id") == item_id:
            _new_item(kind="task")
        st.toast("Task deleted")
        st.rerun()
    if cancel.button(
        "Cancel", key="priorities_cancel_single_delete",
        use_container_width=True,
    ):
        st.session_state.pop("planner_pending_delete_id", None)
        st.rerun()


def _clear_manual_tasks_panel():
    """A deliberate bulk action; imported tasks and calendar events survive."""
    count = manually_added_task_count()
    with st.expander("🗑 Clear all tasks I added", expanded=False):
        st.markdown(f"**{count} manually added task(s)** (including completed tasks)")
        st.caption(
            "This removes ONLY tasks created manually in AARON-1, including "
            "tasks added through chat. It does NOT delete imported school "
            "assignments, email-derived tasks, calendar events, memories, "
            "training examples, or chat history. A backup is saved locally first."
        )
        if count == 0:
            st.info("There are no manually added tasks to clear.")
            return
        # A fresh checkbox is required after each successful clear. Reusing
        # the same Streamlit key would leave a future deletion pre-approved.
        nonce = st.session_state.get("priorities_bulk_confirmation_nonce", 0)
        confirmed = st.checkbox(
            f"Yes, remove all {count} manually added tasks",
            key=f"priorities_confirm_bulk_delete_{nonce}",
        )
        if st.button(
            f"Delete my {count} tasks",
            key="priorities_bulk_delete",
            type="primary", use_container_width=True,
            disabled=not confirmed,
        ):
            try:
                deleted, backup = clear_manually_added_tasks(
                    expected_count=count
                )
                st.session_state["planner_editor_id"] = None
                st.session_state["planner_editor_nonce"] = (
                    st.session_state.get("planner_editor_nonce", 0) + 1
                )
                st.session_state.pop("planner_pending_delete_id", None)
                st.session_state["planner_clear_feedback"] = (
                    f"Deleted {deleted} manually added tasks. "
                    f"Backup saved at: {backup}"
                )
                st.session_state["priorities_bulk_confirmation_nonce"] = nonce + 1
                st.rerun()
            except (ValueError, OSError, sqlite3.Error) as exc:
                st.error(f"Could not clear the tasks: {exc}")


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
        _action_list(limit=12, scope="priorities")
        st.divider()
        with st.expander("All tasks · including completed"):
            tasks = all_tasks()
            if not tasks:
                st.caption("No tasks saved. Add one from Planner or Chat.")
            for task in tasks:
                a, b, c, d = st.columns([4, 1.4, 1, 1.2])
                title = ("✓ " if task.get("completed") else "") + task["title"]
                a.write(title)
                b.caption(_format_deadline(task))
                if c.button("Edit", key=f"priorities_all_edit_{task['id']}"):
                    _choose_item(task["id"])
                    st.rerun()
                if d.button(
                    "Delete", key=f"priorities_all_delete_{task['id']}",
                    use_container_width=True,
                ):
                    st.session_state["planner_pending_delete_id"] = task["id"]
                    st.rerun()
        # Keep confirmation visible even if Streamlit closes the list expander.
        _task_delete_controls()
        if st.session_state.get("planner_clear_feedback"):
            st.success(st.session_state.pop("planner_clear_feedback"))
        _clear_manual_tasks_panel()
        st.caption("Marking a task important also trains AARON-1's local "
                   "personal ranking model.")
    with edit_col:
        if st.button("+ Create task", key="priority_add_new", type="primary",
                     use_container_width=True):
            _new_item(kind="task")
            st.rerun()
        with st.container(border=True):
            _render_editor(scope="priorities")
