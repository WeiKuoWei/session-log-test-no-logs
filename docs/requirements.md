# Requirements — IT Access Requests

## Operating context

Northstar Labs is a fictional multinational company with approximately 5,000 employees across offices in Asia, Europe and North America. Its regional IT teams share responsibility for preparing access requests for human review. They receive free-text messages through email, chat and the service portal, then work from JSON exports of those messages.

### Workload and the review day

On an ordinary business day, the company receives around 200–400 request messages. A coordinated onboarding or acquisition can bring roughly 2,000 messages into the morning's intake. The supplied 20 exports are a representative sample of message types; the application will also receive other messages in the same export format.

Reviewers begin work at different local times. They want to start on requests that are ready while the rest of the intake is still being prepared. A slow response for one message should leave the rest of their work available. Model access is shared with other internal tools, and the available request rate and response time can vary.

### Shared operations

Regional operators work against the same intake and review records. Their working hours overlap, and two operators may start processing around the same time. Each expects their work to leave a coherent current queue and a trustworthy record of earlier activity.

The application may be stopped during a deployment or interrupted by a service outage. When an operator returns, they need to distinguish completed work from unfinished work and continue from the recorded state. Reviewers rely on the queue and the supporting extraction records agreeing about the same source version.

### Updates and follow-up

Exports arrive throughout the day. A later export may repeat an unchanged document or replace its contents with a corrected or expanded message. An export batch contains new or updated documents; absence from a later batch does not withdraw an earlier request. Withdrawal is expressed in the message and handled under the office policy.

Operators need the current view to reflect the latest processed source and to retain earlier results for follow-up. If a new processing attempt fails, they need to see that failure and identify any older result as belonging to its earlier attempt and source version.

The team periodically changes model configuration and updates its review policy. When such a change affects how records are produced or routed, operators need to refresh the affected results and understand which settings and policy version produced the records they are using.

### Service interruptions and handover

The model service sometimes responds slowly, limits requests or becomes temporarily unavailable. IT staff need to locate affected messages, understand what remains pending and resume processing without losing completed work. Other messages may contain incomplete or conflicting information that needs clarification from the requester.

The original developer and the next operator may be in different offices. The operator will use the repository's setup instructions, configuration guidance and commands to prepare an intake, inspect the queue and follow up on failures. Explain the operating assumptions and limits of your implementation so that this handover is practical.

## Record and review behavior
- Use a language model to extract the request details into records that conform to snapshot.schema.json.
- Validate response structure and completion status before using extracted data. Preserve exact supporting quotes and represent uncertain fields as null with an explanatory issue.
- Use message content as the source of business facts. Preserve missing values, conflicting alternatives and explicit corrections according to the policy. Keep document identity distinct from the request ID stated in the message.
- Apply the supplied review policy and display each request's status, owner and next action. Approval decisions belong to the named human reviewers.
- Record input filenames and SHA-256 hashes. Reuse results when the source and relevant processing settings are unchanged, refresh affected results when those inputs or settings change, and retain earlier versions. Process each message independently and make failures visible with a reproducible retry command.
- Handle malformed output, provider errors, refusal and interrupted responses explicitly. Keep model/provider settings configurable and document a supported configuration. The facilitator supplies model-provider access through environment variables.

## Verification

Include automated tests covering a complete request, missing dates, conflicting details, embedded instructions, provider failure, an unchanged rerun, and changed source content. Build expected results from the supplied messages and policy. Add a paraphrased synthetic request to exercise extraction on fresh wording. Specify expected facts from the source messages and policy independently of the extraction outputs being measured. Include checks for refusal or interrupted responses and a failed retry after a prior success.


Describe how your implementation supports the operating context above, and include checks for the operational situations your design handles. Record assumptions about workload and shared operation, the expected behavior during interruptions, and the limits of the verification you performed.
