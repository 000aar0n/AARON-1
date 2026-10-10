"""Conversational front door for AARON-1: safe task commands + optional local chat.

The planner and memories belong to AARON-1. The pretrained Qwen model runs
directly via PyTorch/Transformers; Ollama is entirely optional.
Without inference dependencies, rule-based tasks and commands still work.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from assistant_core import remember, recall, connect
from planner import create_item, daily_items, next_actions, open_tasks, PRIORITY_NAMES

OLLAMA_BASE = "http://127.0.0.1:11434"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday")


def local_models(timeout=2):
    """Only communicate with the local loopback Ollama installation."""
    try:
        with urlopen(OLLAMA_BASE + "/api/tags", timeout=timeout) as response:
            payload = json.load(response)
        return [item["name"] for item in payload.get("models", [])
                if isinstance(item, dict) and isinstance(item.get("name"), str)]
    except (OSError, ValueError, TypeError, KeyError):
        return []


def _date_expression(raw, today):
    raw = raw.strip().lower().replace(",", "")
    if raw in ("today", "tonight"):
        return today
    if raw == "tomorrow":
        return today + timedelta(days=1)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return date.fromisoformat(raw)
    for weekday, name in enumerate(WEEKDAYS):
        if raw in (name, "next " + name, "this " + name):
            delta = (weekday - today.weekday()) % 7
            if raw.startswith("next "):
                delta = delta if delta > 0 else 7
            return today + timedelta(days=delta)
    return None


def _clock_expression(raw):
    if not raw:
        return None
    s = str(raw).strip().lower().replace(" ", "")
    am_pm = re.fullmatch(r"(1[0-2]|[1-9])(?::([0-5]\d))?(am|pm)", s)
    if am_pm:
        hour = int(am_pm.group(1)) % 12 + (12 if am_pm.group(3) == "pm" else 0)
        minute = int(am_pm.group(2) or 0)
        return f"{hour:02d}:{minute:02d}"
    twenty_four = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", s)
    if twenty_four:
        return f"{int(twenty_four.group(1)):02d}:{twenty_four.group(2)}"
    return None


def _task_summary(entries, label, max_items=8):
    if not entries:
        return f"No tasks or events listed for {label}."
    lines = [f"Here is your schedule for {label}:"]
    for entry in entries[:max_items]:
        when = entry.get("due_time") or "all day"
        typ = entry.get("item_type") or "task"
        state = " ✓ done" if entry.get("completed") else ""
        lines.append(f"• {when} — {entry['title']} ({typ}){state}")
    if len(entries) > max_items:
        lines.append(f"…and {len(entries) - max_items} more. Check Calendar.")
    return "\n".join(lines)


def _priority_reply():
    actions = next_actions(limit=4)
    if not actions:
        return "You're all caught up, gang. Nothing outstanding in your task list."
    lines = ["Here's what I'd tackle next, based on your deadlines and priorities:"]
    for i, task in enumerate(actions, 1):
        due = task.get("due") or "no due date"
        if task.get("due_time"):
            due += " at " + task["due_time"]
        lines.append(f"{i}. **{task['title']}** — {due}. {task['why']}.")
    lines.append("Want to plan a realistic study block for the top one?")
    return "\n".join(lines)


def _local_model_reply(message, previous, model):
    """No external network calls; use only a loopback model explicitly enabled."""
    actions = next_actions(limit=8)
    tasks = [
        f"{t['title']} | due {t.get('due') or 'unscheduled'} "
        f"{t.get('due_time') or ''} | priority {PRIORITY_NAMES[int(t.get('priority_level') or 2)]} "
        f"| {t['why']} "
        f"| note: {str(t.get('notes') or '')[:180]}"
        for t in actions
    ]
    with connect() as db:
        known_facts = [
            f"{row['name']}: {row['value']}"
            for row in db.execute(
                "SELECT name,value FROM memories ORDER BY name LIMIT 35"
            ).fetchall()
        ]
    memory_context = "\n".join(known_facts)[:3000]
    system = (
        "You are the conversational voice for AARON-1, a user's locally running "
        "planner and assistant. Speak like an easygoing, curious friend, concise "
        "and warm, without too much forced slang. You CAN discuss the task context "
        "below, but you CANNOT directly manipulate tasks by making claims in your "
        "reply. Actual actions must go through the planner controls or supported "
        "verified chat commands. Never invent assignments, emails, due dates, "
        "connections, or tool results. Be transparent that you are a local model "
        "running locally in AARON-1, based on an existing language model. "
        "Respect boundaries and privacy. Current local datetime: "
        f"{datetime.now().isoformat(timespec='minutes')}. "
        "User-taught memories:\n" + (memory_context or "None") + "\n" +
        "Known outstanding priorities:\n" + "\n".join(tasks or ["None"])
    )
    context = [{"role": "system", "content": system}]
    for item in previous[-10:]:
        if item.get("role") in ("user", "assistant"):
            context.append({"role": item["role"], "content": str(item.get("message", ""))[:2200]})
    context.append({"role": "user", "content": message})
    if model in ("__aaron_base__", "__aaron_trained__"):
        try:
            from trained_chat import generate, generate_base
            return (generate(context) if model == "__aaron_trained__"
                    else generate_base(context))
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            return ("I couldn't load my local conversational model. "
                    "Your tasks and memories are safe. Check the Python "
                    "training dependencies. The first use also downloads "
                    f"Qwen weights (detail: {type(exc).__name__}: {exc}).")
    payload = json.dumps({
        "model": model, "messages": context,
        "stream": False, "options": {"temperature": .55, "num_predict": 420},
    }).encode("utf-8")
    request = Request(OLLAMA_BASE + "/api/chat", data=payload,
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=75) as response:
            value = json.load(response)
        output = value.get("message", {}).get("content")
        if not isinstance(output, str) or not output.strip():
            raise RuntimeError("The local model returned no text.")
        return output.strip()
    except (OSError, RuntimeError, TypeError, KeyError, ValueError) as exc:
        return ("The local chat model didn't respond. Your saved tasks are safe. "
                f"Check that Ollama is running with model '{model}'. "
                f"Technical detail: {type(exc).__name__}.")


def respond(message, previous=(), model=None, now=None):
    """Plan actions, support conversation, and stay honest when no LLM is running.

    Returns (text, action_taken). Gmail read-only handling remains in app.py.
    """
    now = now or datetime.now()
    lower = (message or "").strip().lower().rstrip("!?. ")
    if not lower:
        return ("Say something and I'll help.", False)

    # Explicit commands are handled deterministically: no tool access for a
    # generative model and no automatic destructive actions.
    m = re.fullmatch(r"(?:remember(?: that)? )?my ([a-z\w ]{2,75}) is (.{1,220})", lower)
    if m:
        remember(m.group(1).strip(), m.group(2).strip())
        return (f"Got it — I'll remember your {m.group(1).strip()} is {m.group(2).strip()}.", True)
    m = re.fullmatch(r"(?:what is|what's) my ([a-z\w ]{2,75})", lower)
    if m:
        thing = m.group(1).strip()
        fact = recall(thing)
        return ((f"Your {thing} is {fact}." if fact else
                 f"I haven't learned your {thing} yet. Tell me 'my {thing} is ...'."), False)

    # Supports 'add task essay due tomorrow at 5pm' as well as ISO dates.
    m = re.fullmatch(
        r"(?:add|create|schedule) (?:(task|event) )?(.+?) "
        r"(?:due |on |for )(today|tomorrow|(?:next |this )?"
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"|\d{4}-\d{2}-\d{2})"
        r"(?: at (\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2}))?",
        lower,
    )
    if m:
        kind = m.group(1) or "task"
        title = m.group(2).strip()
        try:
            day = _date_expression(m.group(3), now.date())
            at = _clock_expression(m.group(4))
            if not day or (m.group(4) and not at):
                return ("I couldn't read that date or time. Try 'add task study "
                        "due tomorrow at 5pm'.", False)
            create_item(title=title, due=day, due_time=at, item_type=kind)
            readable = day.strftime("%a %b %d") + (f" at {at}" if at else "")
            return (f"Added **{title}** to your calendar for {readable}.", True)
        except ValueError as exc:
            return (str(exc), False)

    if any(term in lower for term in (
        "what should i do", "what do i do", "whats next", "what's next",
        "what's my priority", "what are my priorities", "prioritize my",
        "what should i work on", "help me lock in", "what to do first",
        "what should i start", "i need to lock in",
    )):
        return (_priority_reply(), False)

    agenda = re.search(
        r"\b(today|tomorrow|(?:next |this )?"
        r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
        lower,
    )
    if agenda and any(word in lower for word in (
        "due", "schedule", "calendar", "homework", "assignment",
        "events", "plans", "have", "doing", "on my plate",
    )):
        day = _date_expression(agenda.group(1), now.date())
        if day:
            return (_task_summary(daily_items(day), day.strftime("%A, %b %d")), False)

    if any(phrase in lower for phrase in ("this week", "next seven days", "coming week")):
        if any(word in lower for word in ("due", "schedule", "homework", "tasks", "plans")):
            future = now.date() + timedelta(days=7)
            entries = [t for t in open_tasks()
                       if t.get("due") and now.date().isoformat() <= t["due"] <= future.isoformat()]
            entries.sort(key=lambda t: (t["due"], t.get("due_time") or ""))
            return (_task_summary(entries, "the next seven days"), False)

    if any(phrase in lower for phrase in (
        "what homework is due", "what's due", "what is due",
        "show my assignments", "show my homework", "upcoming deadlines",
        "what assignments do i have", "show my tasks",
    )):
        return (_priority_reply(), False)

    if any(phrase in lower for phrase in (
        "my schedule", "my calendar", "my day", "today's plan",
    )) and not agenda:
        return (_task_summary(daily_items(now.date()), "today"), False)

    if any(phrase in lower for phrase in ("all my tasks", "list my tasks",
                                         "my assignments", "unfinished tasks")):
        return (_priority_reply(), False)

    if lower in ("hello", "hey", "hi", "yo", "sup", "wassup"):
        return ("Yooo, what's good? 🤖 We can talk, figure out what you're "
                "working on, or organize your schedule.", False)

    if model:
        return (_local_model_reply(message, list(previous), model), False)

    # Symbolic fallback uses recent conversation context, but is not falsely
    # presented as open-ended generative intelligence.
    if any(word in lower for word in ("stressed", "overwhelmed", "anxious", "panicking")):
        actions = next_actions(limit=1)
        if actions:
            return (f"That's a lot to juggle. Let's make it smaller: start with "
                    f"**{actions[0]['title']}** for just 15 minutes. "
                    "Want help breaking it down?", False)
        return ("Sounds stressful. Want to tell me what's going on? "
                "We can work through one thing at a time.", False)
    if any(x in lower for x in ("thank you", "thanks", "thx")):
        return ("Of course 🤝 What's next?", False)
    if "how are you" in lower:
        return ("Doing good — ready to help. How's your day going?", False)
    if any(x in lower for x in ("help", "plan my day", "study plan")):
        return (_priority_reply(), False)
    return (
        "I'm listening! I can discuss your schedule and remember what you tell me. "
        "For open-ended back-and-forth conversations, enable a **local chat model** "
        "in the Chat settings — otherwise I'm still a small rule-based AI.",
        False,
    )
