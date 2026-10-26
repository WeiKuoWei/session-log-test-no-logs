# Northstar access-request intake

CLI application that reads exported access-request messages (JSON), asks a language model to turn each into a structured record (`intake/snapshot.schema.json`, a copy of `snapshot.schema.json`), applies the review policy in `materials/office-policy.md`, and keeps a review queue for the IT team.

## Runtime and provider

| Item | Value |
|---|---|
| Python | 3.11 or newer (developed on 3.14.8, macOS; Linux works, Windows does not because of `fcntl`) |
| Dependencies | None beyond the standard library. See `requirements.lock` |
| Provider | Anthropic Messages API (`POST https://api.anthropic.com/v1/messages`) over HTTPS |
| Supported configuration | model `claude-sonnet-5-5`, `max_tokens` 2048, forced tool call `record_extraction`, no temperature set |
| Credential | environment variable `ANTHROPIC_API_KEY` (read by name, never written to disk, logs or records) |
| Mock provider | `--provider mock` returns hand-written responses from `mock/extractions.json`. Everything produced this way is labelled `mocked: true` |

All deliverables in `deliverables/` were produced with the **mock** provider. No API key was available, so the live call path (`intake/provider.py`) is covered by tests against a fake HTTP opener and has not been run against the real service.

## Setup

```
export ANTHROPIC_API_KEY=...        # live runs only
python3 -m intake status            # no install step; run from this folder
```

Settings live in `intake.toml` (model, `max_tokens`, `temperature`, timeout, workers, retry attempts, backoff, input folder, state folder, `policy_version`). Settings are read at run time; there are no per-setting command-line flags.

## Commands

| Task | Command |
|---|---|
| Start or resume intake (new, changed, failed and out-of-date messages) | `python3 -m intake process` |
| Intake from another folder | `python3 -m intake process path/to/exports` |
| See what is done, pending, in progress, stale or failed | `python3 -m intake status` |
| Inspect the queue (safe while another process is running) | `python3 -m intake queue` |
| Every attempt for one message | `python3 -m intake history IT-003` |
| Retry one failed message (the command printed in its error) | `python3 -m intake process --only IT-003.json` |
| Write `deliverables/extractions.jsonl` and `deliverables/queue.json` | `python3 -m intake export` |
| Accuracy check (runs intake for the 20 messages and the paraphrase, then writes `deliverables/accuracy.md`) | `python3 -m intake accuracy` |
| Write `deliverables/request-evidence.json` | `python3 -m intake evidence` |
| Automated tests | `python3 -m unittest discover -s tests -v` |
| Use the mock provider for any command | `python3 -m intake --provider mock <command>` |

Exit codes: 0 success, 1 some messages ended in error, 2 nothing to do or a command failure, 130 interrupted.

Reproduce the submitted deliverables (mock):

```
rm -rf state
python3 -m intake --provider mock accuracy
python3 -m intake --provider mock export
python3 -m intake evidence          # builds the live request; sends nothing, needs no key
```

## Inspecting the queue

`queue` prints one row per message: status, owner, next action, stated request ID and the first issue. Rows are ordered review, needs-information, error. Messages not yet processed or currently being processed are listed on a final line. `deliverables/queue.json` carries the same entries (with `source_sha256` linking each to its record in `extractions.jsonl`), failed entries carry `retry_command`, and unprocessed messages are listed under `pending`.

Statuses and owners follow the policy: `review` and `needs-information` go to IT Service Desk, Security Review or System Owner; `error` goes to IT Service Desk with next action `retry-extraction`. Every successful record awaits human review; the application never approves anything.

## How state is kept

```
state/<provider>/current/<document_id>.json   latest attempt, one per message (what the queue shows)
state/<provider>/history/<document_id>/NNNN.json   every attempt, never overwritten
state/<provider>/locks/<document_id>.lock    flock held while a process works on that message
state/<provider>/log.jsonl                    operational log, credential-redacted
```

`document_id` is the input filename (for example `IT-003.json`). The record holds the SHA-256 of the original file bytes, the input path, the settings fingerprint (provider, model, `max_tokens`, temperature, API version, and a hash of the prompt and tool schema), the policy version, attempt number and, for mocks, `mocked: true`.

Per message, `process` decides what to do:

| Situation | Action |
|---|---|
| No current record | extract (reason `new`) |
| Same bytes, same fingerprint, same policy version | nothing (`unchanged`); one current entry, no history added |
| Different bytes | new record; the earlier record stays in `history` with its own hash (`source-changed`) |
| Model settings or prompt changed | new model call, new attempt (`settings-changed`) |
| `policy_version` in `intake.toml` changed | routing recomputed from the stored extraction, no model call (`policy-changed`) |
| Latest attempt failed | retried on the next `process` (`retry`) |

A failed attempt writes `status: error`, owner IT Service Desk, next action `retry-extraction`, `extraction: null` and an error ending in the retry command. If an earlier attempt succeeded, the record also carries `previous_valid`, labelled with that attempt number, source hash, settings and policy version and whether it is the same source as the failed attempt; it is not presented as current.

## Failure handling

| Event | Behaviour |
|---|---|
| HTTP 429, 500/502/503/504/529, timeout, network error | retried up to `max_attempts` with exponential backoff (honours `retry-after`), then error record |
| HTTP 401/403, other 4xx, missing `ANTHROPIC_API_KEY` | not retried; error record naming the cause |
| `stop_reason` refusal | error `refusal` |
| `max_tokens` or other incomplete stop | error `interrupted` |
| No tool call, schema violation, invalid date, supporting quote not an exact substring of the message, unreadable input file | error `malformed` |
| Any failure in one message | that message only; others continue |
| Ctrl-C or killed process | finished messages are already saved; run `process` again. Locks are released by the operating system when a process dies |

## Operating assumptions and limits

- Sizing assumed: 200 to 400 messages on an ordinary day, about 2,000 on an onboarding morning. `workers` (default 4) bounds concurrent model calls; each call has its own timeout and retries, so one slow message does not hold up the rest. Lower `workers` if the shared rate limit is tight. A 2,000-message run with an instant fake provider took about 2 seconds, so intake time is dominated by model latency. At 4 workers and an assumed 5 seconds per call, 2,000 messages take roughly 40 minutes; this is arithmetic, not a measurement.
- Operators share one `state/` folder on a local disk. Per-message locks use `flock`, which is not reliable on network file systems. Two operators starting together split the work; a message held by another process is skipped and reported, and appears as `in-progress` in `status`. Operators in different offices need a shared machine or a shared volume that supports locking; a networked database or service would be the next step and is not built.
- Mock and live runs keep separate state (`state/mock`, `state/anthropic`).
- Model output is trusted only after validation, but routing facts that need judgement (conflict, instruction override) depend on the model flagging them in `issues`. Instruction override and identifier mismatch are also detected deterministically; conflict detection is model-only.
- The review policy is encoded in `intake/policy.py`. After editing it or the policy document, change `policy_version` in `intake.toml` and run `process`; stored extractions are re-routed without model calls.
- Messages are sent to the model inside `<message>` tags with an instruction to treat them as data. This reduces but does not eliminate prompt-injection risk; the queue never auto-approves, and an override attempt is routed to IT Service Desk for inspection.
- Exports are processed as separate documents; absence from a later batch changes nothing. Withdrawal is read from the message text only.
- Not built: authentication, a web UI, rate-limit coordination across tools sharing the key, state-file encryption, log rotation.

## Layout

```
intake/          application (cli, pipeline, extraction prompt + schema, policy routing, provider, store, views, accuracy, evidence)
intake.toml      configuration
mock/            MOCKED model responses
accuracy/        hand-authored expected values (expected.json) and the paraphrased request
tests/           unittest suite
deliverables/    extractions.jsonl, queue.json, accuracy.md, request-evidence.json, verification.md
```
