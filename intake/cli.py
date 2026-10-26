"""Command line: python3 -m intake <process|status|queue|history|export|accuracy|evidence>"""
import argparse
import json
import sys
from pathlib import Path

from .accuracy import load_expected, render_report, summarize
from .config import load_config, state_dir
from .evidence import build_evidence
from .pipeline import input_files, process_all
from .provider import make_provider, redact
from .store import Store
from .views import document_states, export, format_queue, format_status, write_json_atomic

PARAPHRASE_DIR = "accuracy/paraphrase"


def run_process(config, input_dir, only, out=print):
    store, provider = Store(state_dir(config)), make_provider(config)
    files = input_files(input_dir, only)
    if not files:
        out(f"no input files matched in {input_dir}")
        return 2
    out(f"provider={config['provider']} model={config['model']} workers={config['workers']} files={len(files)}"
        + ("  [MOCKED responses]" if provider.mocked else ""))
    results = process_all(config, store, provider, files,
                          progress=lambda r: out(f"  {r['document_id']:<14} {r['action']:<26} {r.get('status', '')}"))
    failed = [r for r in results if r.get("status") == "error"]
    for r in failed:
        out(f"FAILED {r['document_id']}: {r['error']}")
    out(f"done: {len(results) - len(failed)} ok/unchanged, {len(failed)} failed")
    return 1 if failed else 0


def run_accuracy(config, out=print):
    expected = load_expected()
    run_process(config, config["input_dir"], None, out)
    main_store = Store(state_dir(config))
    para_config = dict(config, state_root=str(Path(config["state_root"]) / "paraphrase"))
    run_process(para_config, PARAPHRASE_DIR, None, out)
    records = {r["document_id"]: r for r in main_store.list_current()}
    records.update({r["document_id"]: r for r in Store(state_dir(para_config)).list_current()})
    mocked = config["provider"] == "mock"
    text = render_report(expected, summarize(expected, records), config, mocked,
                         f"{state_dir(config)} and {state_dir(para_config)}")
    Path("deliverables").mkdir(exist_ok=True)
    write_json_atomic("deliverables/accuracy.md", text)
    out("wrote deliverables/accuracy.md")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m intake", description="Northstar access-request intake")
    ap.add_argument("--provider", choices=["anthropic", "mock"], help="override provider from intake.toml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("process", help="process new, changed, failed and out-of-date messages (resumes automatically)")
    p.add_argument("input_dir", nargs="?", help="folder of exported JSON messages (default: input_dir in intake.toml)")
    p.add_argument("--only", action="append", metavar="DOC", help="process just this document id (repeatable); the retry command")
    sub.add_parser("status", help="what is done, pending, in progress, stale or failed")
    sub.add_parser("queue", help="print the current review queue (safe to run while processing)")
    h = sub.add_parser("history", help="list every attempt for one document")
    h.add_argument("document")
    e = sub.add_parser("export", help="write deliverables/extractions.jsonl and deliverables/queue.json")
    e.add_argument("--out", default="deliverables")
    sub.add_parser("accuracy", help="process the 20 messages and the paraphrase, then write deliverables/accuracy.md")
    sub.add_parser("evidence", help="write deliverables/request-evidence.json")
    args = ap.parse_args(argv)
    config = load_config(provider=args.provider)
    try:
        return dispatch(args, config)
    except KeyboardInterrupt:
        print("\ninterrupted. Finished messages are saved; resume with: python3 -m intake process")
        return 130
    except Exception as e:
        print(f"error: {redact(e)}", file=sys.stderr)
        return 2


def dispatch(args, config):
    store = Store(state_dir(config)) if args.cmd != "evidence" else None
    input_dir = getattr(args, "input_dir", None) or config["input_dir"]
    if args.cmd == "process":
        return run_process(config, input_dir, args.only)
    if args.cmd == "status":
        print(format_status(document_states(config, store, input_dir)))
    elif args.cmd == "queue":
        print(format_queue(store, document_states(config, store, input_dir)))
    elif args.cmd == "history":
        for rec in store.history(args.document if args.document.endswith(".json") else args.document + ".json"):
            print(f"attempt {rec['attempt']}  {rec['processed_at']}  sha {rec['source_sha256'][:12]}  "
                  f"{rec['status']:<17} reason={rec['reason']}  policy={rec['policy_version']}  "
                  f"model={rec['settings']['model']}  mocked={rec['mocked']}" + (f"\n    error: {rec['error']}" if rec["error"] else ""))
    elif args.cmd == "export":
        n = export(config, store, args.out, document_states(config, store, input_dir))
        print(f"wrote {n} records to {args.out}/extractions.jsonl and {args.out}/queue.json")
    elif args.cmd == "accuracy":
        run_accuracy(config)
    elif args.cmd == "evidence":
        write_json_atomic("deliverables/request-evidence.json", json.dumps(build_evidence(config), indent=2) + "\n")
        print("wrote deliverables/request-evidence.json")
    return 0
