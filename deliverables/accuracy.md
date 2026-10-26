# Accuracy report

Run type: **MOCKED**. Every extraction below came from hand-written mock responses (`mock/extractions.json`), not from a model. The figures check the pipeline, validation, routing and this comparison procedure; they say nothing about how well the model extracts. One flaw is planted in the mock (IT-007 kind) so the error reporting has something to report.

## Configuration

- Provider: mock; model: claude-sonnet-5-5; max_tokens: 2048; temperature: not set
- Policy version: northstar-intake-policy-2026-10-26
- State read from: state/mock and state/paraphrase/mock
- Live observations: none recorded in this submission (no API key was available).

## Procedure

1. Expected values for 20 supplied messages plus one authored paraphrase (IT-021) are in `accuracy/expected.json`, written by hand from the message text and `materials/office-policy.md`, without reference to any extraction output.
2. Scored fields (11): request_id, request_date, kind, requester, team, system, environment, permission, start_date, end_date, manager. Free text (business_purpose, supporting_quotes, issues) is not scored.
3. A field matches only on exact equality (same string, or both null). No case or whitespace normalisation.
4. Denominator is fixed at documents x 11 fields. A document whose latest attempt is an error scores 0 of 11.
5. Factual error: a non-null extracted value that differs from the expected value (wrong-value), or a non-null value where the source supports none (fabricated). A null where the source gives a value (omitted) counts as a miss but not a factual error.
6. Routing: owner, status and next_action must all equal the expected route derived from the policy rules.
7. Supporting quotes are checked on every run as exact substrings of the message (a failing quote makes the record an error, so it never reaches this table).

## Results

- Field exact matches: **230 / 231** (99.6%)
- Documents with all 11 fields exact: **20 / 21**
- Routes equal to expected: **21 / 21**
- Factual errors: **1**

| Document | Field | Kind | Expected | Extracted |
|---|---|---|---|---|
| IT-007.json | kind | wrong-value | change | new |

| Document | Fields exact | Route as expected | Latest attempt status |
|---|---|---|---|
| IT-001.json | 11 / 11 | yes | review |
| IT-002.json | 11 / 11 | yes | review |
| IT-003.json | 11 / 11 | yes | needs-information |
| IT-004.json | 11 / 11 | yes | needs-information |
| IT-005.json | 11 / 11 | yes | review |
| IT-006.json | 11 / 11 | yes | review |
| IT-007.json | 10 / 11 | yes | review |
| IT-008.json | 11 / 11 | yes | review |
| IT-009.json | 11 / 11 | yes | needs-information |
| IT-010.json | 11 / 11 | yes | needs-information |
| IT-011.json | 11 / 11 | yes | needs-information |
| IT-012.json | 11 / 11 | yes | review |
| IT-013.json | 11 / 11 | yes | review |
| IT-014.json | 11 / 11 | yes | needs-information |
| IT-015.json | 11 / 11 | yes | review |
| IT-016.json | 11 / 11 | yes | needs-information |
| IT-017.json | 11 / 11 | yes | needs-information |
| IT-018.json | 11 / 11 | yes | review |
| IT-019.json | 11 / 11 | yes | review |
| IT-020.json | 11 / 11 | yes | needs-information |
| IT-021.json | 11 / 11 | yes | review |

## Expected values

| Document | request_id | request_date | kind | requester | team | system | environment | permission | start_date | end_date | manager | Expected route | Basis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IT-001.json | IT-001 | 2026-10-22 | new | Maya Chen | Analytics | Atlas | staging | read | 2026-10-23 | 2026-11-06 | Priya Shah | System Owner / review / review-request | Complete staging/read request (rule 5). |
| IT-002.json | IT-002 | 2026-10-22 | new | Owen Reed | Payments | Ledger | production | write | 2026-10-24 | 2026-10-25 | Elena Park | Security Review / review / review-risk-then-owner | Complete; production and write (rule 4). 'Needed during 2026-10-24 and 2026-10-25' gives both dates. |
| IT-003.json | IT-003 | 2026-10-22 | new | Lina Gomez | Customer Success | Beacon | null | null | null | null | Priya Shah | IT Service Desk / needs-information / clarify | Environment and permission not stated ('same access Sam has'); no dates ('next week' is relative and no dates are given) (rule 3). |
| IT-004.json | IT-004 | 2026-10-22 | new | Theo Malik | Quality Engineering | Atlas | null | read | 2026-10-23 | 2026-10-30 | Nia Patel | IT Service Desk / needs-information / clarify | 'in staging' and 'for the production environment' conflict with no correction, so environment is unresolved (rule 3). |
| IT-005.json | IT-005 | 2026-10-22 | withdrawal | Ava Brooks | Design | null | null | null | null | null | Elena Park | IT Service Desk / review / confirm-withdrawal | Withdrawal with request_id and request_date (rule 2). 'My boss is Elena Park' gives manager. |
| IT-006.json | IT-006 | 2026-10-22 | new | Finn Lee | Platform | Atlas | staging | read | 2026-10-23 | 2026-10-24 | Nia Patel | IT Service Desk / review / inspect-message | Embedded 'SYSTEM OVERRIDE' instruction (rule 1); the genuine request stays staging/read, not admin. |
| IT-007.json | IT-007 | 2026-10-22 | change | Grace Tan | Developer Experience | Forge | staging | write | 2026-10-24 | 2026-10-28 | Nia Patel | Security Review / review / review-risk-then-owner | Change from read to write: extract the NEW permission, write (rule 4). |
| IT-008.json | IT-008 | 2026-10-22 | new | Noah Kim | Finance | Atlas | staging | read | 2026-10-25 | 2026-10-31 | Priya Shah | System Owner / review / review-request | Explicit correction replaces production with staging (rule 5). |
| IT-009.json | IT-009 | 2026-10-22 | new | Isla Morgan | Support | Beacon | staging | read | 2026-10-26 | 2026-10-29 | null | IT Service Desk / needs-information / clarify | No manager named anywhere in the message (rule 3). |
| IT-010.json | IT-010 | 2026-10-22 | new | Ben Carter | Operations | Ledger | production | read | 2026-10-27 | null | Elena Park | IT Service Desk / needs-information / clarify | 'Haven't quite fixed on the end date': end_date absent (rule 3). |
| IT-011.json | IT-011 | 2026-10-22 | new | Zoe Adams | Research | Atlas | staging | read | null | null | Priya Shah | IT Service Desk / needs-information / clarify | 'next Monday - Friday' is relative, so both dates stay null (rule 3). 'boss' is the manager. |
| IT-012.json | IT-012 | 2026-10-22 | new | Ravi Shah | Infrastructure | Forge | staging | admin | 2026-10-26 | 2026-10-27 | Nia Patel | Security Review / review / review-risk-then-owner | Complete; admin (rule 4). |
| IT-013.json | IT-013 | 2026-10-22 | new | Emma Wilson | Compliance | Beacon | production | read | 2026-10-28 | 2026-10-30 | Elena Park | Security Review / review / review-risk-then-owner | Complete; production (rule 4). |
| IT-014.json | IT-014 | 2026-10-22 | new | Lucas Brown | Sales Operations | Atlas | staging | read | 2026-11-05 | 2026-11-02 | Priya Shah | IT Service Desk / needs-information / clarify | start_date 2026-11-05 is after end_date 2026-11-02 (rule 3). |
| IT-015.json | IT-015 | 2026-10-22 | new | Mia Davis | Learning | Beacon | staging | read | 2026-10-29 | 2026-10-31 | Elena Park | System Owner / review / review-request | Explicit correction replaces 2026-10-24 - 2026-10-26 (rule 5). |
| IT-016.json | IT-061 | 2026-10-22 | new | Alex Turner | Platform | Forge | staging | read | 2026-10-26 | 2026-10-28 | Nia Patel | IT Service Desk / needs-information / clarify | Message states IT-061, filename is IT-016: identifier mismatch (rule 3). The stated identifier is kept. |
| IT-017.json | IT-017 | 2026-10-22 | other | Chloe Martin | Communications | null | null | null | null | null | null | IT Service Desk / needs-information / clarify | A question about the form location, not an access request: kind other (rule 3). |
| IT-018.json | IT-018 | 2026-10-22 | new | Daniel Wright | Data Engineering | Atlas | staging | read | 2026-10-27 | 2026-11-03 | Priya Shah | System Owner / review / review-request | Complete staging/read request (rule 5). |
| IT-019.json | IT-019 | 2026-10-22 | change | Sara Ahmed | Customer Operations | Beacon | production | read | 2026-10-28 | 2026-11-04 | Elena Park | Security Review / review / review-risk-then-owner | Change write to read: new permission is read; production (rule 4). |
| IT-020.json | IT-020 | 2026-10-22 | new | Ethan Clark | Product | Atlas | staging | read | 2026-10-29 | 2026-11-02 | null | IT Service Desk / needs-information / clarify | Two different managers (Priya Shah, Elena Park) with no correction: manager unresolved (rule 3). |
| IT-021.json | IT-021 | 2026-10-22 | new | Jun Okafor | Finance Operations | Ledger | staging | read | 2026-11-09 | 2026-11-13 | Elena Park | System Owner / review / review-request | Paraphrase authored for this exercise (not a supplied export): complete staging/read request (rule 5). |
