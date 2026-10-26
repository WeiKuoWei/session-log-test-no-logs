"""Per-message processing: decide whether work is needed, call the model, validate, route, persist."""
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import extraction_settings
from .extraction import ExtractionError, build_request, parse_response, prompt_version
from .policy import SERVICE_DESK, route
from .provider import ProviderError, redact
from .store import now

RETRY_COMMAND = "python3 -m intake process --only {doc}"


def fingerprint(config):
    blob = json.dumps({"settings": extraction_settings(config), "prompt": prompt_version()}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def decide(current, sha, config):
    """Why this document needs work, or 'unchanged'. Used by process and status."""
    if current is None:
        return "new"
    if current["source_sha256"] != sha:
        return "source-changed"
    if current["status"] == "error":
        return "retry"
    if current["extraction_fingerprint"] != fingerprint(config):
        return "settings-changed"
    if current["policy_version"] != config["policy_version"]:
        return "policy-changed"
    return "unchanged"


def input_files(input_dir, only=None):
    files = sorted(Path(input_dir).glob("*.json"))
    if only:
        wanted = {o if o.endswith(".json") else o + ".json" for o in only}
        files = [f for f in files if f.name in wanted]
    return files


def read_source(path):
    raw = Path(path).read_bytes()
    return raw, hashlib.sha256(raw).hexdigest()


def extract_message(raw):
    """Decode the export and return its message string. Raises ExtractionError('malformed', ...)."""
    try:
        data = json.loads(raw.decode("utf-8"))
        message = data["message"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as e:
        raise ExtractionError("malformed", f"input export is unreadable or has no message ({type(e).__name__})")
    if not isinstance(message, str) or not message.strip():
        raise ExtractionError("malformed", "input export message is empty or not a string")
    return message


def call_model(config, provider, store, doc, message, sleep):
    payload = build_request(config, doc, message)
    for attempt in range(1, config["max_attempts"] + 1):
        try:
            return provider.send(payload)
        except ProviderError as e:
            if not e.retryable or attempt == config["max_attempts"]:
                raise
            delay = e.retry_after if e.retry_after is not None else config["backoff_seconds"] * 2 ** (attempt - 1)
            store.log("provider-retry", document_id=doc, kind=e.kind, attempt=attempt, delay=delay)
            sleep(delay)


def process_one(config, store, provider, path, sleep=time.sleep):
    path = Path(path)
    doc = path.name
    raw, sha = read_source(path)
    if decide(store.read_current(doc), sha, config) == "unchanged":
        return {"document_id": doc, "action": "unchanged"}
    with store.claim(doc) as held:
        if not held:
            store.log("skipped-claimed", document_id=doc)
            return {"document_id": doc, "action": "claimed-by-another-process"}
        current = store.read_current(doc)
        action = decide(current, sha, config)
        if action == "unchanged":  # another operator finished it between our check and the claim
            return {"document_id": doc, "action": "unchanged"}
        record = {
            "document_id": doc, "source_filename": str(path), "source_sha256": sha,
            "extraction": None, "status": "error", "owner": SERVICE_DESK, "next_action": "retry-extraction",
            "error": None, "processed_at": now(), "reason": action,
            "extraction_fingerprint": fingerprint(config), "prompt_version": prompt_version(),
            "policy_version": config["policy_version"], "settings": extraction_settings(config),
            "provider": config["provider"], "mocked": bool(getattr(provider, "mocked", False)),
        }
        try:
            if action == "policy-changed":
                extraction = current["extraction"]  # model output is unchanged; only routing is recomputed
                record["settings"], record["extraction_fingerprint"] = current["settings"], current["extraction_fingerprint"]
                record["prompt_version"], record["mocked"] = current["prompt_version"], current["mocked"]
                message = None
            else:
                message = extract_message(raw)
                response = call_model(config, provider, store, doc, message, sleep)
                record["model_response"] = {"stop_reason": response.get("stop_reason"), "usage": response.get("usage")}
                extraction = parse_response(response, message)
            extraction, routing = route(extraction, doc, message if message is not None else _message_of(raw))
            record.update(extraction=extraction, status=routing["status"], owner=routing["owner"],
                          next_action=routing["next_action"], routing_reasons=routing["reasons"],
                          intake_added_issues=routing["added_issues"])
        except ExtractionError as e:
            record["error"] = redact(f"{e.kind}: {e}") + f". Retry: {RETRY_COMMAND.format(doc=doc)}"
        except ProviderError as e:
            record["error"] = redact(f"provider {e.kind}: {e}") + f". Retry: {RETRY_COMMAND.format(doc=doc)}"
        except Exception as e:  # one message must never stop the others
            record["error"] = f"unexpected {type(e).__name__}: {redact(e)}. Retry: {RETRY_COMMAND.format(doc=doc)}"
        if record["status"] == "error":
            prev = store.last_valid(doc)
            if prev:
                record["previous_valid"] = {
                    "note": f"result of attempt {prev['attempt']} for source {prev['source_sha256'][:12]}, "
                            "not the latest attempt",
                    "attempt": prev["attempt"], "source_sha256": prev["source_sha256"],
                    "same_source_as_latest_attempt": prev["source_sha256"] == sha,
                    "extraction_fingerprint": prev["extraction_fingerprint"], "policy_version": prev["policy_version"],
                    "extraction": prev["extraction"], "status": prev["status"], "owner": prev["owner"],
                    "next_action": prev["next_action"],
                }
        store.commit(record)
        store.log("processed", document_id=doc, action=action, status=record["status"], error=record["error"])
        return {"document_id": doc, "action": action, "status": record["status"], "error": record["error"]}


def _message_of(raw):
    return json.loads(raw.decode("utf-8"))["message"]


def process_all(config, store, provider, files, sleep=time.sleep, progress=None):
    def work(path):
        try:
            result = process_one(config, store, provider, path, sleep)
        except Exception as e:  # unreadable file etc. outside the per-record handler
            result = {"document_id": Path(path).name, "action": "failed", "status": "error", "error": redact(e)}
            store.log("process-failure", document_id=Path(path).name, error=redact(e))
        if progress:
            progress(result)
        return result

    with ThreadPoolExecutor(max_workers=max(1, config["workers"])) as pool:
        futures = [pool.submit(work, f) for f in files]
        try:
            return [f.result() for f in futures]
        except KeyboardInterrupt:
            for f in futures:
                f.cancel()
            raise
