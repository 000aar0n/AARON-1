"""Encrypted durable state and atomic, expiring, one-use approvals."""
import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet

LOG = logging.getLogger("jarvis")

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

class Store:
    def __init__(self, directory, key):
        Path(directory).mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        self.path = str(Path(directory) / "jarvis.sqlite3")
        self.cipher = Fernet(key.encode())
        with self.db() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, value BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS actions(
              id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload BLOB NOT NULL,
              digest TEXT NOT NULL, state TEXT NOT NULL,
              created REAL NOT NULL, expires REAL NOT NULL, result BLOB);
            CREATE TABLE IF NOT EXISTS audit(
              seq INTEGER PRIMARY KEY, at REAL NOT NULL, event TEXT NOT NULL,
              action_id TEXT, code TEXT);
            """)
            db.execute("UPDATE actions SET state='uncertain' WHERE state='executing'")
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=20, isolation_level="IMMEDIATE")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()

    def encrypt(self, value):
        return self.cipher.encrypt(canonical(value).encode())

    def decrypt(self, value):
        return json.loads(self.cipher.decrypt(value))

    def audit(self, event, action_id=None, code=None):
        with self.db() as db:
            db.execute("INSERT INTO audit(at,event,action_id,code) VALUES(?,?,?,?)",
                       (time.time(), event, action_id, code))
        LOG.info(canonical(dict(event=event, action_id=action_id, code=code)))

    def get(self, key, default=None):
        with self.db() as db:
            row = db.execute("SELECT value FROM kv WHERE k=?", (key,)).fetchone()
        return self.decrypt(row["value"]) if row else default

    def put(self, key, value):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (key, self.encrypt(value)))

    def take(self, key):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM kv WHERE k=?", (key,)).fetchone()
            db.execute("DELETE FROM kv WHERE k=?", (key,))
        return self.decrypt(row["value"]) if row else None

    def propose(self, kind, payload, ttl=3600):
        now = time.time()
        action_id = uuid.uuid4().hex
        digest = hashlib.sha256(canonical(dict(kind=kind, payload=payload)).encode()).hexdigest()
        with self.db() as db:
            db.execute("INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,NULL)",
                (action_id, kind, self.encrypt(payload), digest, "pending", now, now+ttl))
        self.audit("proposed", action_id)
        return self.action(action_id)

    def action(self, action_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM actions WHERE id=?", (action_id,)).fetchone()
        if row is None:
            raise KeyError(action_id)
        a = dict(row)
        a["payload"] = self.decrypt(a["payload"])
        a["result"] = self.decrypt(a["result"]) if a["result"] else None
        return a

    def actions(self, limit=100):
        with self.db() as db:
            ids = db.execute("SELECT id FROM actions ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [self.action(row["id"]) for row in ids]

    def approve(self, action_id, digest):
        with self.db() as db:
            changed = db.execute(
              "UPDATE actions SET state='approved' WHERE id=? AND digest=? AND state='pending' AND expires>?",
              (action_id, digest, time.time())).rowcount
        if changed != 1:
            raise ValueError("Approval invalid, expired, or already used")
        self.audit("owner_approved", action_id)
        return self.action(action_id)

    def reject(self, action_id):
        with self.db() as db:
            n = db.execute("UPDATE actions SET state='rejected' WHERE id=? AND state IN ('pending','approved')",
                           (action_id,)).rowcount
        if n != 1:
            raise ValueError("Action already executing or complete")
        self.audit("owner_rejected", action_id)

    def claim(self, action_id):
        with self.db() as db:
            changed = db.execute(
              "UPDATE actions SET state='executing' WHERE id=? AND state='approved' AND expires>?",
              (action_id, time.time())).rowcount
        if changed != 1:
            raise ValueError("Action requires fresh approval or has already executed")
        return self.action(action_id)

    def finish(self, action_id, state, result):
        if state not in ("succeeded", "failed", "uncertain"):
            raise ValueError("Invalid terminal state")
        with self.db() as db:
            db.execute("UPDATE actions SET state=?, result=? WHERE id=? AND state='executing'",
                       (state, self.encrypt(result), action_id))
        self.audit(state, action_id)

    def consume_inference(self, model):
        now = time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM kv WHERE k='inference_grant'").fetchone()
            grant = self.decrypt(row["value"]) if row else {}
            if grant.get("expires", 0) <= now or grant.get("remaining", 0) <= 0 or grant.get("model") != model:
                raise PermissionError("A current owner-approved inference allowance is required")
            grant["remaining"] -= 1
            db.execute("UPDATE kv SET value=? WHERE k='inference_grant'", (self.encrypt(grant),))
        return grant

    def acquire_lease(self, name, seconds):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM kv WHERE k=?", ("lease:"+name,)).fetchone()
            until = self.decrypt(row["value"]) if row else 0
            if until > time.time():
                return False
            db.execute("INSERT OR REPLACE INTO kv VALUES(?,?)",
                       ("lease:"+name, self.encrypt(time.time()+seconds)))
        return True
