# Verification

All model responses in tests and deliverables are **mocked** (hand-written in `mock/extractions.json`, or scripted inside each test). No live provider call was made; no API key was available.

## Commands

| Purpose | Command |
|---|---|
| All automated tests | `python3 -m unittest discover -s tests -v` |
| Regenerate mocked deliverables | `rm -rf state && python3 -m intake --provider mock accuracy && python3 -m intake --provider mock export && python3 -m intake evidence` |
| Live accuracy check (needs `ANTHROPIC_API_KEY`) | `python3 -m intake accuracy` |

## Test cases and what each compares

Expected values come from `accuracy/expected.json` (typed by hand from the messages and `materials/office-policy.md`), or are stated inline in the test. They are not read back from extraction output.

| Required case | Test (tests/test_intake.py) | Intended comparison |
|---|---|---|
| Complete request | `TestExpectedResults.test_complete_request_goes_to_system_owner` | IT-001 fields equal expected; no issues; owner System Owner, status review, next action review-request |
| All supplied messages route as policy says | `test_every_supplied_message_routes_as_policy_expects` | owner, status, next_action of the 20 records equal the expected route for each |
| Schema and quotes | `test_every_record_conforms_to_schema_and_quotes_are_exact` | each extraction validates against the schema; each quote is a substring of its message |
| Missing dates | `test_missing_dates_stay_null_with_issue`, `test_start_after_end_needs_clarification` | IT-003, IT-010, IT-011 date fields are null with a matching issue; relative dates stay unresolved; IT-014 start after end routes to needs-information |
| Conflicting details | `test_conflicting_details_are_preserved_not_resolved`, `test_identifier_mismatch_keeps_stated_id_and_asks` | IT-004 environment and IT-020 manager null with both alternatives quoted; corrections in IT-008 and IT-015 replace earlier values; IT-016 keeps stated ID IT-061 |
| Embedded instructions | `TestEmbeddedInstructions` (2 tests) | IT-006 stays read/staging, routes to IT Service Desk / review / inspect-message, instruction quoted; routing holds even when the model fails to flag it |
| Provider failure | `TestProviderFailures` (5 tests) | error record (null extraction, retry-extraction, retry command in error); other 19 messages complete; retry count equals `max_attempts`; `retry-after` and doubling backoff honoured; no retry on auth errors; one message raising an unexpected exception does not stop others; unreadable input becomes an error record |
| Unchanged rerun | `TestReuseAndVersions.test_unchanged_rerun_reuses_results` | zero provider calls; hash, attempt and timestamp unchanged; 20 current records; one history entry each |
| Changed source content | `test_changed_source_creates_new_result_and_keeps_old` | new hash and new value current; history holds both hashes in order; one current record |
| Paraphrase | `test_paraphrase_on_fresh_wording` | IT-021 fields and route equal expected (mock response; see limits) |
| Refusal | `TestResponseHandling.test_refusal` | stop_reason refusal gives error record |
| Interrupted response | `test_interrupted_response` | stop_reason max_tokens gives error record with null extraction |
| Malformed output | `test_malformed_variants` | nine variants (no tool call, extra property, bad enum, missing key, bad date format, impossible date, invented quote, non-object input, unexpected stop) each rejected as malformed |
| Failed retry after prior success | `test_failed_retry_after_prior_success_keeps_old_result_labelled`, `test_failure_after_source_change_points_at_older_source` | latest record is error with null extraction; `previous_valid` holds the earlier extraction labelled with its attempt, hash and same-source flag; history has both attempts; a later successful retry restores a current valid record |

## Operational checks

| Situation | Test | Intended comparison |
|---|---|---|
| Model setting change | `test_model_setting_change_refreshes_with_new_model_call` | one new call; history shows both models |
| Policy version change | `test_policy_version_change_reroutes_without_model_call` | zero calls; new attempt with new policy version; old attempt keeps the old one |
| Failed record retried | `test_error_record_is_retried_on_plain_rerun` | plain `process` replaces the error with a valid record, reason `retry` |
| Resume after interruption | `test_resume_processes_only_unfinished` | after a partial run, the next run makes calls only for the 17 unfinished messages |
| Inspect while pending | `test_queue_shows_completed_work_while_others_pending` | queue text and `queue.json` list completed entries and the 18 pending ones |
| Slow message | `test_slow_message_does_not_block_others` | with one message blocked, the other five complete; status shows the blocked one `in-progress` |
| Two operators | `test_two_operators_do_not_duplicate_work_on_one_document`, `test_concurrent_operators_leave_one_current_record_and_one_history_entry` | a held message is skipped; two concurrent runs over 10 messages make exactly 10 calls in total and leave one history entry each |
| Queue and records agree | `test_queue_and_extractions_agree_on_source_version` | same document ids and hashes in `queue.json` and `extractions.jsonl` |
| Failure visible in queue | `test_failed_records_appear_in_queue_with_retry_command` | error entry carries the retry command |
| Credential redaction | `test_log_is_credential_redacted`, `test_evidence_file_has_no_credential`, `test_http_errors_are_classified` | key string absent from log, stored error text, evidence file and raised errors |
| Anthropic request path | `TestAnthropicProviderRequest` | URL, headers, key taken from `ANTHROPIC_API_KEY`, forced tool call, timeout; HTTP 429/529/503/401/400, timeout and network errors classified; missing key reported by name (all against a fake opener, no network) |
| Routing rules | `TestPolicyUnits` | each policy rule and rule precedence, with unit inputs |
| Scale | `test_scale_two_thousand_messages` | 2,000 messages, instant fake provider, 8 workers, all processed and routed |

## Observed results

Observed on 2026-10-26, Python 3.14.8, macOS, mock/scripted providers only:

- `python3 -m unittest discover -s tests -v`: **47 tests, OK** (about 4 seconds, of which about 2 seconds is the 2,000-message test).
- Repairs made during development, found by these tests: an error message from a provider containing the key was being stored unredacted on the record (the log was already redacted); fixed by redacting before storing. One test assertion that searched the whole record for the word "approved" matched the mock's own issue text and was replaced by an assertion on status.
- Mocked accuracy run (`deliverables/accuracy.md`): 230 of 231 scored fields exact, 1 factual error (IT-007 kind, planted in the mock), 21 of 21 routes as expected. This measures the pipeline and comparison procedure, not model quality.
- Live provider path without a key: `python3 -m intake process --only IT-001` produced an error record `provider no_credentials: environment variable ANTHROPIC_API_KEY is not set. Retry: python3 -m intake process --only IT-001.json` and exit code 1 (this state was deleted afterwards).
- After `process` on the mock state a second `process` reported all 20 messages `unchanged`.

## Limits of this verification

- No live model call was made. Real response behaviour (quote fidelity, refusals, relative-date handling, whether the model flags conflicts and overrides in `issues`) is untested. The mock responses were written by the same author as the expected values and the policy code, so agreement between them is not independent evidence about a model.
- The paraphrase check uses a mock response, so it does not test fresh-wording robustness; it tests that the pipeline and expected values agree. A live run of `python3 -m intake accuracy` is the real test.
- Concurrency tests use threads in one process (and a second `Store` object on the same folder); `flock` between separate operating-system processes and across machines was not exercised. Locking on network file systems is not supported.
- Scale was tested for bookkeeping only (no network latency, no rate limiting). Behaviour under a real shared rate limit is unmeasured; the retry and backoff logic is tested with scripted errors.
- Kill-during-write recovery relies on atomic file replacement and OS-released locks; no test kills a process mid-run.
- Conflict detection depends on the model's `conflict:` issue prefix; only instruction override, identifier mismatch, missing facts and date order are checked deterministically.
- Expected values cover 20 supplied messages and one paraphrase; other message shapes (non-English, over 200 words, several requests in one message) are not covered.
