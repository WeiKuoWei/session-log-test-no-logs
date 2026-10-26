"""Field-by-field comparison of extracted records against accuracy/expected.json.

Expected values are typed by hand from the source messages and the policy, never from extraction output.
Counting rules (also written into the report):
- Scored fields: the 11 in expected.json (business_purpose, quotes and issues are free text, not scored).
- A field matches only on exact equality (string equality, or both null). No normalisation.
- Denominator is fixed: documents x 11. A document whose attempt failed (extraction null) scores 0 for all 11.
- Factual error = extracted non-null value that differs from the expected one ('wrong-value'), or a non-null
  value where the source supports none ('fabricated'). A null where the source gives a value is 'omitted':
  a miss, not a factual error.
- Routing is compared separately: owner, status and next_action must all equal the policy-derived expected route.
"""
import json
from pathlib import Path


def load_expected(path="accuracy/expected.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def classify(expected, actual):
    if expected == actual:
        return "match"
    if actual is None:
        return "omitted"
    return "fabricated" if expected is None else "wrong-value"


def compare(expected_doc, record, fields):
    ext = record.get("extraction") if record else None
    cells = {f: classify(expected_doc["fields"][f], ext[f] if ext else None) if ext else "no-extraction"
             for f in fields}
    route = expected_doc["route"]
    route_ok = bool(record) and all(record[k] == route[k] for k in ("owner", "status", "next_action"))
    return cells, route_ok


def summarize(expected, records_by_doc):
    fields = expected["scored_fields"]
    rows, errors = [], []
    matched = total = docs_exact = routes_ok = 0
    for doc, exp in expected["documents"].items():
        rec = records_by_doc.get(doc)
        cells, route_ok = compare(exp, rec, fields)
        n = sum(1 for c in cells.values() if c == "match")
        matched += n
        total += len(fields)
        docs_exact += n == len(fields)
        routes_ok += route_ok
        rows.append((doc, n, route_ok, rec))
        for f, c in cells.items():
            if c in ("wrong-value", "fabricated"):
                errors.append((doc, f, c, exp["fields"][f], rec["extraction"][f]))
    return {"rows": rows, "matched": matched, "total": total, "docs": len(expected["documents"]),
            "docs_exact": docs_exact, "routes_ok": routes_ok, "factual_errors": errors, "fields": fields}


def render_report(expected, summary, config, mocked, state_note):
    s, fields = summary, summary["fields"]
    label = "MOCKED" if mocked else "LIVE"
    out = [
        "# Accuracy report", "",
        f"Run type: **{label}**. " + (
            "Every extraction below came from hand-written mock responses (`mock/extractions.json`), not from a "
            "model. The figures check the pipeline, validation, routing and this comparison procedure; they say "
            "nothing about how well the model extracts. One flaw is planted in the mock (IT-007 kind) so the "
            "error reporting has something to report." if mocked else
            "Extractions came from the live provider."), "",
        "## Configuration", "",
        f"- Provider: {config['provider']}; model: {config['model']}; max_tokens: {config['max_tokens']}; "
        f"temperature: {config.get('temperature', 'not set')}",
        f"- Policy version: {config['policy_version']}",
        f"- State read from: {state_note}",
        "- Live observations: none recorded in this submission (no API key was available).", "",
        "## Procedure", "",
        "1. Expected values for 20 supplied messages plus one authored paraphrase (IT-021) are in "
        "`accuracy/expected.json`, written by hand from the message text and `materials/office-policy.md`, "
        "without reference to any extraction output.",
        "2. Scored fields (11): " + ", ".join(fields) + ". Free text (business_purpose, supporting_quotes, "
        "issues) is not scored.",
        "3. A field matches only on exact equality (same string, or both null). No case or whitespace normalisation.",
        "4. Denominator is fixed at documents x 11 fields. A document whose latest attempt is an error scores 0 of 11.",
        "5. Factual error: a non-null extracted value that differs from the expected value (wrong-value), or a "
        "non-null value where the source supports none (fabricated). A null where the source gives a value "
        "(omitted) counts as a miss but not a factual error.",
        "6. Routing: owner, status and next_action must all equal the expected route derived from the policy rules.",
        "7. Supporting quotes are checked on every run as exact substrings of the message (a failing quote makes "
        "the record an error, so it never reaches this table).", "",
        "## Results", "",
        f"- Field exact matches: **{s['matched']} / {s['total']}** ({s['matched'] / s['total']:.1%})",
        f"- Documents with all 11 fields exact: **{s['docs_exact']} / {s['docs']}**",
        f"- Routes equal to expected: **{s['routes_ok']} / {s['docs']}**",
        f"- Factual errors: **{len(s['factual_errors'])}**", "",
    ]
    if s["factual_errors"]:
        out += ["| Document | Field | Kind | Expected | Extracted |", "|---|---|---|---|---|"]
        out += [f"| {d} | {f} | {c} | {e} | {a} |" for d, f, c, e, a in s["factual_errors"]]
        out.append("")
    out += ["| Document | Fields exact | Route as expected | Latest attempt status |", "|---|---|---|---|"]
    out += [f"| {d} | {n} / {len(fields)} | {'yes' if ok else 'NO'} | {rec['status'] if rec else 'not processed'} |"
            for d, n, ok, rec in s["rows"]]
    out += ["", "## Expected values", "",
            "| Document | " + " | ".join(fields) + " | Expected route | Basis |",
            "|---|" + "---|" * (len(fields) + 2)]
    for doc, exp in expected["documents"].items():
        r = exp["route"]
        vals = " | ".join("null" if exp["fields"][f] is None else str(exp["fields"][f]) for f in fields)
        out.append(f"| {doc} | {vals} | {r['owner']} / {r['status']} / {r['next_action']} | {exp['basis']} |")
    return "\n".join(out) + "\n"
