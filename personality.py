"""User-directed personality preferences for AARON-1. No pretrained models or APIs.

Stores explicit style preferences and user-corrected example replies in the
same local SQLite DB as the existing individual, without replacing its memory.
"""
import difflib
import re
from individual import connect

DEFAULTS = {
    "energy": "2",
    "slang": "2",
    "humor": "1",
    "favorite_phrases": "bro, gang, lowk",
}


def normalized(text):
    return re.sub(r"[^\w\s]", "", text.casefold()).strip()


def initialize(cx):
    cx.execute(
        "CREATE TABLE IF NOT EXISTS personality_settings "
        "(setting TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    cx.execute(
        "CREATE TABLE IF NOT EXISTS reply_examples "
        "(prompt TEXT PRIMARY KEY, response TEXT NOT NULL)"
    )


def get_profile():
    with connect() as cx:
        initialize(cx)
        saved = dict(cx.execute("SELECT setting, value FROM personality_settings"))
    return {**DEFAULTS, **saved}


def save_profile(energy, slang, humor, favorite_phrases):
    entries = {
        "energy": str(max(0, min(3, int(energy)))),
        "slang": str(max(0, min(3, int(slang)))),
        "humor": str(max(0, min(3, int(humor)))),
        "favorite_phrases": favorite_phrases.strip()[:120],
    }
    with connect() as cx:
        initialize(cx)
        cx.executemany(
            "INSERT OR REPLACE INTO personality_settings(setting, value) VALUES (?,?)",
            list(entries.items()),
        )
        cx.commit()


def teach_reply(prompt, response):
    prompt, response = normalized(prompt), response.strip()
    if not prompt or not response:
        return False
    with connect() as cx:
        initialize(cx)
        cx.execute(
            "INSERT OR REPLACE INTO reply_examples(prompt,response) VALUES (?,?)",
            (prompt[:300], response[:1000]),
        )
        cx.commit()
    return True


def learned_examples():
    with connect() as cx:
        initialize(cx)
        return cx.execute(
            "SELECT prompt,response FROM reply_examples ORDER BY prompt"
        ).fetchall()


def forget_example(prompt):
    with connect() as cx:
        initialize(cx)
        cx.execute("DELETE FROM reply_examples WHERE prompt=?", (normalized(prompt),))
        cx.commit()


def learned_response(message):
    key = normalized(message)[:300]
    if not key:
        return None
    rows = learned_examples()
    for prompt, response in rows:
        if prompt == key:
            return response
    # Restrict fuzzy generalization to close, substantial shared input.
    # We do NOT pretend a single example teaches unrestricted English.
    if len(key) >= 12:
        candidates = [
            (difflib.SequenceMatcher(None, key, prompt).ratio(), response)
            for prompt, response in rows
            if len(prompt) >= 12 and abs(len(prompt)-len(key)) <= max(5, len(key)//5)
        ]
        if candidates:
            match, response = max(candidates, key=lambda item: item[0])
            if match >= 0.94:
                return response
    return None


def phrase(profile):
    """Short user-authorized catchphrase, used only occasionally."""
    if int(profile["slang"]) < 2:
        return ""
    choices = [p.strip() for p in profile["favorite_phrases"].split(",") if p.strip()]
    return choices[0][:24] if choices else ""


def voice(kind, *, attribute="", value="", original=""):
    """Bounded style variation on known dialogue intents, not language generation."""
    p = get_profile()
    energy = int(p["energy"])
    slang = int(p["slang"])
    humor = int(p["humor"])
    word = phrase(p)
    opener = (word.capitalize() + ", ") if word else ""
    if kind == "greeting":
        if energy == 0:
            return "hey. what's up?"
        if slang == 0:
            return "Hey! What's on your mind?" if energy > 1 else "Hey there."
        return ("YOOO 😭 what's good? Tell me something." if energy == 3 else
                "yo, what's good? 🤖")
    if kind == "identity":
        return ("I'm AARON-1. I'm picking up your style from what you teach me, "
                "but I'm still a separate AI.")
    if kind == "help":
        return ("You can tell me 'my favorite food is ramen', ask 'what is my favorite food', "
                "or correct how I reply in the Personality section.")
    if kind == "saved":
        lead = (opener + "bet") if slang >= 2 else "Got it"
        return f"{lead}, I'll remember your {attribute} is {value}." + (" 😎" if humor >= 3 else "")
    if kind == "recall":
        return f"{opener if slang >= 2 else ''}your {attribute} is {value}."
    if kind == "missing":
        return f"I don't know your {attribute} yet. Tell me!"
    if kind == "word":
        return f"Got it — '{attribute}' means '{value}' to you."
    if kind == "recognized":
        return f"I recognize '{attribute}' as '{value}'. What should I do with that?"
    if kind == "unknown":
        if slang >= 2:
            return "nah i don't get that one yet 😭 show me how you'd respond in Personality."
        return "I don't understand that one yet. You can teach me a better reply in Personality."
    return original
