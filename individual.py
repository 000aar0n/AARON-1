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
    """Handle conversation using saved examples first, then bounded symbolic rules."""
    # Import inside this function to keep the DB helpers independent of style code.
    from personality import ensure_brainrot_training, ensure_dating_training, learned_response, dating_context_reply, voice

    ensure_brainrot_training()
    ensure_dating_training()

    raw = message.strip()
    msg = raw.lower().strip(" .!?")
    if not msg:
        return "Say something and I'll try to understand it."

    taught = learned_response(raw)
    if taught is not None:
        reply = taught
    else:
        m = re.fullmatch(r"teach:\s*(.+?)\s*=\s*(.+)", msg)
        fact = re.fullmatch(r"my (.+?) is (.+)", msg)
        question = re.fullmatch(r"what is my (.+)", msg)
        if m:
            teach(m.group(1), m.group(2))
            reply = voice("word", attribute=m.group(1), value=m.group(2))
        elif msg in ("hello", "hi", "hey", "yo", "wassup", "sup"):
            reply = voice("greeting")
        elif msg in ("who are you", "what are you"):
            reply = voice("identity")
        elif msg in ("what do you know", "help"):
            reply = voice("help")
        elif fact:
            attribute, value = fact.group(1), fact.group(2)
            learn_fact("user", attribute, value)
            reply = voice("saved", attribute=attribute, value=value)
        elif question:
            attribute = question.group(1)
            value = recall_fact("user", attribute)
            reply = (voice("recall", attribute=attribute, value=value) if value
                     else voice("missing", attribute=attribute))
        else:
            matches = [meaning for phrase, meaning in vocabulary() if phrase == msg]
            if matches:
                reply = voice("recognized", attribute=raw, value=matches[0])
            else:
                reply = dating_context_reply(raw) or voice("unknown")
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
