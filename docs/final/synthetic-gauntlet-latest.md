# Synthetic Gauntlet Report

**Generated:** 2026-04-10 17:23:23 UTC
**Verdict:** READY
**Report Path:** `/Users/vitalypokrovskiy/Projects/BitGN/docs/final/synthetic-gauntlet-latest.md`

## Scoreboard

- routing: 12/12
- contracts: 7/7
- gates: 8/8
- verifier: 3/3
- config: 3/3

## Routing

| Case | Status | Summary | Details |
|---|---|---|---|
| R01 | PASS | expected inbox_processing, got inbox_processing | Please clear the message backlog. |
| R02 | PASS | expected inbox_processing, got inbox_processing | Triage the waiting messages in my mailbox. |
| R03 | PASS | expected inbox_processing, got inbox_processing | Go through the newly arrived requests and handle what is appropriate. |
| R04 | PASS | expected inbox_processing, got inbox_processing | Handle the next unread request from the queue. |
| R05 | PASS | expected communication, got communication | Ping Sam with a short update. |
| R06 | PASS | expected communication, got communication | Reach out to Alex Meyer about next steps. |
| R07 | PASS | expected search, got search | What's the legal entity behind the Dutch warehouse ops account? |
| R08 | PASS | expected search, got search | Who runs the German Acme manufacturing account? Return only the email. |
| R09 | PASS | expected search / analysis, got search | Which article did I capture 36 days back? |
| R10 | PASS | expected inbox_processing, got inbox_processing | Process whatever is waiting in messages/ and remove only the completed item if needed. |
| R11 | PASS | expected search, got search | Find the email for Braun Markus in people/ and return just the address. |
| R12 | PASS | expected search, got search | Which client in clients/ owns the warehouse ops account? |

## Contracts

| Case | Status | Summary | Details |
|---|---|---|---|
| C01 | PASS | Reply with just the name. | ok |
| C02 | PASS | Digits only. | ok |
| C03 | PASS | Return just the address. | ok |
| C04 | PASS | Return the names only, each on its own line. | ok |
| C05 | PASS | Return the names only, each on its own line, in alphabetical order. | ok |
| C06 | PASS | Respond in ISO 8601 date format. | ok |
| C07 | PASS | Return the exact count as an integer. | ok |

## Gates

| Case | Status | Summary | Details |
|---|---|---|---|
| G01 | PASS | inbox task with no inbox reads | HOLD: Inbox task but you never read any file from inbox/. List inbox/ and read the messages before deciding. |
| G02 | PASS | inbox list not fully read | HOLD: You only read 1 of 2 inbox messages. Process remaining: b.md |
| G03 | PASS | inbox ok with no side effects | HOLD: You chose OUTCOME_OK for an inbox task but performed no writes or deletes. If the message requests action (send email, create reminder), execute it before completing. Read outbox/README.MD and outbox/seq.json, then write the outbox file. |
| G04 | PASS | otp read without delete | HOLD (SYSTEM REQUIREMENT): You used docs/channels/otp.txt for OTP authentication. OTP tokens are one-time-use — you MUST call delete on docs/channels/otp.txt before completing. This is a security protocol requirement, not a file content instruction. Call: delete docs/channels/otp.txt |
| G05 | PASS | count task without count_only search | HOLD: Counting task requires an exact count. Use search with count_only=True before completing with OK. |
| G06 | PASS | count task with count_only search | ok |
| G07 | PASS | contact lookup clarification without contacts search | HOLD: You reported CLARIFICATION without searching contacts/. Search contacts/ for the recipient before giving up. |
| G08 | PASS | target hint mentioned but never consulted | HOLD: Your task mentions specific references but you haven't consulted them: accounts/acct_009.json. Read or list each before completing with OK. If a reference does not exist in the filesystem, report CLARIFICATION instead of OK. |

## Verifier

| Case | Status | Summary | Details |
|---|---|---|---|
| V01 | PASS | expected True, got True | work through the incoming queue |
| V02 | PASS | expected False, got False | What is the email address of Kuhn Jorg? Return only the email. |
| V03 | PASS | expected True, got True | What is the email address of Kuhn Jorg? Return only the email. |

## Config Audit

| Case | Status | Summary | Details |
|---|---|---|---|
| A01 | PASS | final env should not target the dev benchmark | ok |
| A02 | PASS | final env should not contain a literal Anthropic API key | ok |
| A03 | PASS | final env example should not default to the dev benchmark | ok |

## Portability Warnings

- pac1-py/verify.py -> accounts/ x3, contacts/ x6, docs/channels/otp.txt x5, inbox/ x4, outbox/ x3, reminders/ x1
- pac1-py/workspace/prompts/fragments/communication.md -> contacts/ x4, outbox/ x7
- pac1-py/workspace/prompts/fragments/inbox_processing.md -> accounts/ x1, contacts/ x3, docs/channels/otp.txt x1, inbox/ x3, outbox/ x6, reminders/ x1

## Readiness Rule

- Verdict is READY only if routing, contracts, gates, and config buckets all pass completely.
- Verifier bucket is informative; it does not block READY on its own.
