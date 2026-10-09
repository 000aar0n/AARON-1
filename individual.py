"""AARON-1: persistent symbolic conversation learner, no LLM or APIs.

Small teachable vocabulary, explicit facts, and confidence-limited dialogue.
Does not pretend to understand unrestricted English.
"""
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB = Path("data") / "aaron_individual.sqlite3"

def connect():
    DB.parent.mkdir(exist_ok=True)
    cx = sqlite3.connect(DB, timeout=10)
    cx.execute("CREATE TABLE IF NOT EXISTS facts (subject TEXT, attribute TEXT, value TEXT, PRIMARY KEY(subject,attribute))")
    cx.execute("CREATE TABLE IF NOT EXISTS lexicon (phrase TEXT PRIMARY KEY, meaning TEXT NOT NULL)")
    cx.execute("CREATE TABLE IF NOT EXISTS dialogue (id INTEGER PRIMARY KEY, input TEXT, response TEXT, created_at TEXT)")
    cx.commit()
    return cx

def learn_fact(subject, attribute, value):
    with connect() as cx:
        cx.execute("INSERT OR REPLACE INTO facts VALUES (?, ?, ?)", (subject, attribute, value))
        cx.commit()

def recall_fact(subject, attribute):
    with connect() as cx:
        row = cx.execute("SELECT value FROM facts WHERE subject=? AND attribute=?", (subject, attribute)).fetchone()
    return row[0] if row else None

def teach(phrase, meaning):
    phrase, meaning = phrase.strip().lower(), meaning.strip().lower()
    if not phrase or not meaning:
        return False
    with connect() as cx:
        cx.execute("INSERT OR REPLACE INTO lexicon VALUES (?,?)", (phrase, meaning))
        cx.commit()
    return True

def vocabulary():
    with connect() as cx:
        return cx.execute("SELECT phrase, meaning FROM lexicon ORDER BY phrase").fetchall()

def log(message, response):
    with connect() as cx:
        cx.execute("INSERT INTO dialogue (input,response,created_at) VALUES (?,?,?)",
                   (message, response, datetime.now(timezone.utc).isoformat()))
        cx.commit()

def history(limit=30):
    with connect() as cx:
        return cx.execute("SELECT input,response FROM dialogue ORDER BY id DESC LIMIT ?", (limit,)).fetchall()[::-1]

def respond(message):
    raw = message.strip()
    msg = raw.lower().strip(" .!?")
    if not msg:
        return "Say something and I'll try to understand it."
    # Syntax: teach: hello = greeting
    m = re.fullmatch(r"teach:\s*(.+?)\s*=\s*(.+)", msg)
    if m:
        teach(m.group(1), m.group(2))
        reply = f"Learned: '{m.group(1)}' means '{m.group(2)}'."
    elif msg in ("hello", "hi", "hey"):
        reply = "Hello! I'm AARON-1. I can learn simple words and remember facts you teach me."
    elif msg in ("who are you", "what are you"):
        reply = "I'm AARON-1, a persistent experimental agent. My conversation system is symbolic, not an LLM."
    elif msg in ("what do you know", "help"):
        reply = "Try: 'my favorite color is blue', 'what is my favorite color', or 'teach: yo = greeting'."
    else:
        m = re.fullmatch(r"my (.+?) is (.+)", msg)
        q = re.fullmatch(r"what is my (.+)", msg)
        if m:
            attribute, value = m.group(1), m.group(2)
            learn_fact("user", attribute, value)
            reply = f"Okay, I'll remember that your {attribute} is {value}."
        elif q:
            attribute = q.group(1)
            value = recall_fact("user", attribute)
            reply = f"Your {attribute} is {value}." if value else f"I don't know your {attribute} yet. Tell me!"
        else:
            matches = [meaning for phrase, meaning in vocabulary() if phrase == msg]
            if matches:
                reply = f"I recognize '{raw}' as '{matches[0]}'. What should I do with that meaning?"
            else:
                reply = ("I don't understand that yet. You can teach a word with "
                         "'teach: phrase = meaning', or tell me a fact using 'my X is Y'.")
    log(raw, reply)
    return reply

def symbolic_peer(target):
    """Show existing trained sender/receiver channel, separate from English chat."""
    path = Path("data/checkpoint.json")
    if not path.exists():
        return None
    try:
        pair = json.loads(path.read_text())["pair"]
        n = pair["n"]
        if not 0 <= target < n:
            return None
        signal = max(range(n), key=lambda i: pair["sender"][target][i])
        guess = max(range(n), key=lambda i: pair["receiver"][signal][i])
        return {"signal": signal, "decoded": guess, "correct": guess == target}
    except (KeyError, ValueError, TypeError):
        return None
