# AI Full Stack Challenge — IT Access Requests

## The task
Northstar Labs receives access requests as free-text messages. Build a small runnable application that uses a language model to turn those messages into structured records and a review queue for the IT team. The supplied company, people and requests are fictional.

Read docs/requirements.md for the operating context and required behavior, materials/office-policy.md for review rules, and snapshot.schema.json for the record format. The 20 JSON exports in materials/requests/ are your starting data. Choose an interface suited to the IT team: a CLI, service or web application. Operators should be able to start intake, inspect completed results while other requests are pending, and resume unfinished work through the documented interface.

## What to submit
| Path | Content |
|---|---|
| README.md | Setup, supported runtime/provider, exact intake/test/accuracy-check commands, environment-variable names, and how to inspect the queue |
| Source code and dependency lockfile | Runnable application, extraction prompt, schema and model request configuration |
| deliverables/extractions.jsonl | One current record per message: document_id, source_sha256, extraction (schema-conforming object, or null on error), status, owner, next_action, and error (null on success) |
| deliverables/queue.json | The review queue linked to extraction records by document_id |
| deliverables/accuracy.md | Source-derived expected fields for the 20 supplied messages and one paraphrase you author; the field-comparison procedure, exact-match counting/denominator rules, factual-error reporting and model/configuration; distinguish mocked examples from any optional live observations |
| deliverables/request-evidence.json | Credential-redacted example model request showing the model ID and configuration used, plus the implemented response handling |
| deliverables/verification.md | Verification commands and assertions, their intended comparisons, operating limits, and any observed results or repairs clearly identified as such |
| Coding-session capture | Session record paired with the submitted commit, collected through the facilitator's capture setup |

## Submission
Commit and push the application, outputs and session capture. Submit the repository URL and exact commit through the Classroom assignment. The facilitator supplies the assignment and capture instructions.

Submit the implemented provider integration and source-grounded validation procedure. Use mocked responses for reproducible development examples, and label each recorded observation with its configuration and whether it used a mock or provider response.
