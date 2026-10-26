"""Review-queue routing from materials/office-policy.md. Deterministic: it runs after validation
and never calls the model, so a policy change can re-route stored extractions without new requests."""
import re

from .extraction import SCALAR_FIELDS

REQUIRED = ["request_id", "request_date", "requester", "team", "system", "environment",
            "permission", "business_purpose", "start_date", "end_date", "manager"]
SERVICE_DESK = "IT Service Desk"
OVERRIDE_PATTERNS = [
    r"system override", r"ignore (all |any |the )?(previous|prior|above)", r"bypass\b.{0,40}\bapproval",
    r"highest[- ]priority system instruction", r"mark (this |the )?request as approved",
    r"disregard\b.{0,30}\binstruction", r"reveal\b.{0,30}\b(api key|password|secret)",
    r"display the api key",
]


def filename_id(document_id):
    return document_id.rsplit(".", 1)[0]


def _mentions(issues, field):
    names = {field, field.replace("_", " ")}
    return any(n in issue.lower() for issue in issues for n in names)


def _has_prefix(issues, prefix):
    return any(i.lower().startswith(prefix) for i in issues)


def route(extraction, document_id, message):
    """Return (extraction_with_intake_issues, routing). Adds issues for absent facts and id mismatch."""
    ext = dict(extraction)
    issues = list(ext["issues"])
    added = []

    def add(text):
        issues.append(text)
        added.append(text)

    stated = ext["request_id"]
    mismatch = stated is not None and stated != filename_id(document_id)
    if mismatch and not _has_prefix(issues, "id-mismatch"):
        add(f"id-mismatch: message states {stated}, filename is {document_id} (intake check)")
    for field in SCALAR_FIELDS:
        if ext[field] is None and not _mentions(issues, field):
            add(f"missing: {field} - not stated in the message (intake check)")
    ext["issues"] = issues

    override = _has_prefix(issues, "instruction-override") or any(
        re.search(p, message, re.IGNORECASE) for p in OVERRIDE_PATTERNS)
    if override and not _has_prefix(issues, "instruction-override"):
        ext["issues"].append("instruction-override: message contains text instructing the system (intake check)")
        added.append(ext["issues"][-1])

    kind = ext["kind"]
    reasons = []
    if override:
        owner, status, action = SERVICE_DESK, "review", "inspect-message"
        reasons.append("rule 1: instruction-override attempt")
    elif kind == "withdrawal" and ext["request_id"] and ext["request_date"]:
        owner, status, action = SERVICE_DESK, "review", "confirm-withdrawal"
        reasons.append("rule 2: withdrawal with request_id and request_date")
    else:
        if kind in (None, "other"):
            reasons.append(f"kind is {kind}")
        if kind == "withdrawal":
            reasons.append("withdrawal lacks request_id or request_date")
        if _has_prefix(issues, "conflict"):
            reasons.append("conflicting details")
        if mismatch:
            reasons.append("request_id differs from filename")
        missing = [f for f in REQUIRED if ext[f] is None]
        if kind in ("new", "change") and missing:
            reasons.append("missing required: " + ", ".join(missing))
        if ext["start_date"] and ext["end_date"] and ext["start_date"] > ext["end_date"]:
            reasons.append("start_date is after end_date")
            if not _has_prefix(issues, "date-order"):
                add("date-order: start_date is after end_date (intake check)")
        if reasons:
            owner, status, action = SERVICE_DESK, "needs-information", "clarify"
            reasons.insert(0, "rule 3")
        elif ext["environment"] == "production" or ext["permission"] in ("write", "admin"):
            owner, status, action = "Security Review", "review", "review-risk-then-owner"
            reasons.append("rule 4: complete request with production, write or admin")
        else:
            owner, status, action = "System Owner", "review", "review-request"
            reasons.append("rule 5: complete staging/read request")
    ext["issues"] = issues
    return ext, {"owner": owner, "status": status, "next_action": action,
                 "reasons": reasons, "added_issues": added}
