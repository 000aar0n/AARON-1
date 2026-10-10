"""AARON-1's Winter Arc 2026 workout calendar, based on the workout tracker.

October 8 to December 30 inclusive. Four all-day training reminders a week:
Monday/Thursday push and core; Tuesday/Friday pull and legs. Once seeded,
deleting an individual workout is respected on subsequent app reruns.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from assistant_core import connect
from planner import ensure_schema

START = date(2026, 10, 8)
END = date(2026, 12, 30)
MIGRATION = "winter_arc_2026_workout_reminders_v1"
PUSH = "Push + Core"
PULL = "Pull + Legs"

WORKOUTS = {
    PUSH: (
        "5-minute warm-up; rest 60–90 seconds between sets.\n"
        "Push-ups — 3 × 10–18\n"
        "Pike push-ups — 2 × 5–10\n"
        "5-lb lateral raises — 3 × 12–20\n"
        "Close-grip push-ups — 2 × 6–12\n"
        "5-lb dumbbell triceps kickbacks — 2 × 15–20\n"
        "Reverse crunches — 2 × 10–15\n"
        "Side planks — 2 × 20–30 sec per side\n"
        "Log your sets in your Winter Arc tracker. Rest if sore; "
        "no band triceps extensions."
    ),
    PULL: (
        "5-minute warm-up; rest 60–90 seconds between sets.\n"
        "Band bent-over rows — 3 × 10–15\n"
        "Band + dumbbell curls — 3 × 10–15\n"
        "Band reverse flyes — 2 × 12–20\n"
        "Split squats — 3 × 10–15 per leg\n"
        "Single-leg glute bridges — 2 × 12 per leg\n"
        "Standing calf raises — 2 × 15–25\n"
        "Dead bugs — 2 × 8–12 per side\n"
        "Log your sets in your Winter Arc tracker. Rest if sore."
    ),
}


def workout_for_day(day):
    if not START <= day <= END:
        return None
    if day.weekday() in (0, 3):
        return PUSH
    if day.weekday() in (1, 4):
        return PULL
    return None


def upcoming_workout(today=None):
    now = today or date.today()
    for delta in range(0, 7):
        day = now + timedelta(days=delta)
        session = workout_for_day(day)
        if session:
            return day, session
    return None


def seed_winter_arc():
    """Add 48 local all-day workouts one time, with stable IDs per date.

    Called at startup only because the user explicitly requested integration.
    A migration sentinel avoids recreating sessions the user later deletes.
    """
    ensure_schema()
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute(
            "SELECT 1 FROM migrations WHERE name=?", (MIGRATION,)
        ).fetchone():
            db.commit()
            return 0
        created = 0
        day = START
        while day <= END:
            session = workout_for_day(day)
            if session:
                external = "winter_arc_2026:" + day.isoformat()
                if not db.execute(
                    "SELECT 1 FROM tasks WHERE source='winter_arc' AND external_id=?",
                    (external,),
                ).fetchone():
                    db.execute(
                        """INSERT INTO tasks
                        (id,title,due,notes,source,external_id,created_at,
                         item_type,priority_level,duration_min,estimated_min)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (str(uuid.uuid4()), "🏋️ Winter Arc · " + session,
                         day.isoformat(), WORKOUTS[session],
                         "winter_arc", external,
                         datetime.now(timezone.utc).isoformat(),
                         "event", 2, 60, 30),
                    )
                    created += 1
            day += timedelta(days=1)
        db.execute(
            "INSERT INTO migrations(name) VALUES (?)", (MIGRATION,)
        )
        db.commit()
    return created
