"""On-disk state. One current record per document, append-only history, per-document flock locks.

state/<provider>/current/<document_id>.json     latest attempt (what the queue shows)
state/<provider>/history/<document_id>/NNNN.json  every attempt, never overwritten
state/<provider>/locks/<document_id>.lock        held (flock) while a process works on the document
state/<provider>/log.jsonl                        credential-redacted operational log
Writes are temp-file + os.replace, so readers never see a partial record."""
import contextlib
import fcntl
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path

from .provider import redact


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, root):
        self.root = Path(root)
        for sub in ("current", "history", "locks"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{id(data)}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def read_current(self, doc):
        p = self.root / "current" / f"{doc}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def list_current(self):
        return [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted((self.root / "current").glob("*.json"))]

    def history(self, doc):
        d = self.root / "history" / doc
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.exists() else []

    def commit(self, record):
        """Append to history, then replace current. Caller must hold the document lock."""
        doc = record["document_id"]
        record["attempt"] = len(self.history(doc)) + 1
        self._write_json(self.root / "history" / doc / f"{record['attempt']:04d}.json", record)
        self._write_json(self.root / "current" / f"{doc}.json", record)
        return record

    def last_valid(self, doc):
        for rec in reversed(self.history(doc)):
            if rec["status"] != "error":
                return rec
        return None

    @contextlib.contextmanager
    def claim(self, doc):
        """Exclusive non-blocking lock. Yields False if another process holds it. The OS drops the
        lock if the holder dies, so a killed run never leaves a stuck document."""
        path = self.root / "locks" / f"{doc}.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            os.ftruncate(fd, 0)
            os.write(fd, json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "since": now()}).encode())
            try:
                yield True
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def is_claimed(self, doc):
        path = self.root / "locks" / f"{doc}.lock"
        if not path.exists():
            return False
        fd = os.open(path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True
        finally:
            os.close(fd)

    def log(self, event, **fields):
        line = redact(json.dumps({"ts": now(), "event": event, **fields}, ensure_ascii=False))
        with open(self.root / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
