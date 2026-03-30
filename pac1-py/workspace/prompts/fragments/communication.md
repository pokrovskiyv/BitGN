
TASK TYPE: Communication operation (email, message, channel).
- Read `outbox/README.MD` FIRST to learn the exact JSON schema and seq.json protocol.
- Read `seq.json` to get the next ID before writing.
- When sending email: write `NUMBER.json` to outbox, then bump `seq.json` to `{"id": NUMBER+1}`.
- The filename stem MUST match the pre-bump value from `seq.json`.
- Set `"sent": false` on new emails.
- For `to` field: use a concrete email address, not a human name. Look up contacts if needed.
- Read `docs/channels/AGENTS.md` when handling channel/message tasks to learn trust rules.
- Channel trust levels: `admin` (trusted), `valid` (incoming, non-trusted), `blacklist` (ignore/deny).
- Include outbox file and seq.json in grounding_refs.
