"""Read-only views over the store: status, queue table, and the exported deliverable files."""
import json
import os
from pathlib import Path

from .pipeline import RETRY_COMMAND, decide, input_files, read_source
from .store import now

STATUS_ORDER = {"review": 0, "needs-information": 1, "error": 2}


def document_states(config, store, input_dir):
    """One dict per input file: state is done | error | stale | in-progress | pending."""
    out = []
    for path in input_files(input_dir):
        _, sha = read_source(path)
        cur = store.read_current(path.name)
        why = decide(cur, sha, config)
        if store.is_claimed(path.name):
            state = "in-progress"
        elif cur is None:
            state = "pending"
        elif cur["status"] == "error":
            state = "error"
        elif why != "unchanged":
            state = "stale"
        else:
            state = "done"
        out.append({"document_id": path.name, "state": state, "why": why, "record": cur})
    return out


def format_status(states):
    counts = {}
    for s in states:
        counts[s["state"]] = counts.get(s["state"], 0) + 1
    lines = ["documents: %d  (%s)" % (len(states), ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))]
    for s in states:
        if s["state"] == "done":
            continue
        extra = {"pending": "not processed yet", "in-progress": "being processed by another process",
                 "stale": f"result is out of date ({s['why']}); old result stays visible until reprocessed",
                 "error": s["record"]["error"] if s["record"] else ""}[s["state"]]
        lines.append(f"  {s['document_id']:<14} {s['state']:<12} {extra}")
    if any(s["state"] in ("pending", "stale", "error") for s in states):
        lines.append("resume / refresh / retry all: python3 -m intake process")
    return "\n".join(lines)


def sorted_records(store):
    return sorted(store.list_current(), key=lambda r: (STATUS_ORDER.get(r["status"], 9), r["owner"], r["document_id"]))


def format_queue(store, states=None):
    rows = sorted_records(store)
    lines = [f"{'document':<14}{'status':<19}{'owner':<17}{'next action':<24}{'request':<9}note"]
    for r in rows:
        ext = r["extraction"] or {}
        note = (r["error"] or "; ".join(ext.get("issues", [])[:1]))[:70]
        lines.append(f"{r['document_id']:<14}{r['status']:<19}{r['owner']:<17}{r['next_action']:<24}"
                     f"{str(ext.get('request_id') or '-'):<9}{note}")
    if states:
        waiting = [s["document_id"] for s in states if s["state"] in ("pending", "in-progress")]
        if waiting:
            lines.append(f"not yet in the queue ({len(waiting)}): " + ", ".join(waiting))
    return "\n".join(lines)


def write_json_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def export(config, store, out_dir, states=None):
    """Write extractions.jsonl and queue.json from ONE snapshot of the current records, so the two
    always agree on document_id and source_sha256."""
    records = sorted_records(store)
    ext_rows, entries = [], []
    for r in records:
        row = {k: r[k] for k in ("document_id", "source_sha256", "extraction", "status", "owner", "next_action", "error")}
        row.update({k: r[k] for k in ("source_filename", "attempt", "processed_at", "extraction_fingerprint",
                                       "prompt_version", "policy_version", "settings", "provider", "mocked")})
        for k in ("previous_valid", "routing_reasons", "intake_added_issues"):
            if k in r:
                row[k] = r[k]
        ext_rows.append(row)
        ext = r["extraction"] or {}
        entry = {"document_id": r["document_id"], "source_sha256": r["source_sha256"], "attempt": r["attempt"],
                 "status": r["status"], "owner": r["owner"], "next_action": r["next_action"],
                 "request_id": ext.get("request_id"), "requester": ext.get("requester"),
                 "issues": ext.get("issues", []), "error": r["error"],
                 "policy_version": r["policy_version"], "mocked": r["mocked"]}
        if r["status"] == "error":
            entry["retry_command"] = RETRY_COMMAND.format(doc=r["document_id"])
            if "previous_valid" in r:
                entry["previous_valid_attempt"] = r["previous_valid"]["attempt"]
        entries.append(entry)
    pending = [{"document_id": s["document_id"], "state": s["state"]} for s in (states or [])
               if s["state"] in ("pending", "in-progress")]
    counts = {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    queue = {"generated_at": now(), "policy_version": config["policy_version"], "provider": config["provider"],
             "model": config["model"], "counts": counts, "entries": entries, "pending": pending}
    out = Path(out_dir)
    write_json_atomic(out / "extractions.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ext_rows))
    write_json_atomic(out / "queue.json", json.dumps(queue, indent=2, ensure_ascii=False) + "\n")
    return len(records)
