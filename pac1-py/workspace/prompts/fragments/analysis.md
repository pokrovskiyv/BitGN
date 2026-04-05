TASK TYPE: Analysis operation.
- Read all relevant sources before synthesizing.
- Cite every source in grounding_refs.
- Be precise with numbers and comparisons.
- The boot-time tree is only 2 levels deep. ALWAYS list subdirectories explicitly before concluding data is absent.
- Do NOT report OUTCOME_NONE_CLARIFICATION without first reading files that might contain the answer. If the task asks about specific data, explore the filesystem thoroughly.

COUNTING: When the task asks "how many" or requires counting items, use the search tool with count_only=True for EXACT counts. Do NOT read a file and count manually — this is error-prone for large files. Example: search(pattern="blacklist", root="/docs/channels/Telegram.txt", count_only=True) returns the precise count.
