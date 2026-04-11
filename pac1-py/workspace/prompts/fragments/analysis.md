TASK TYPE: Analysis operation.
- Read all relevant sources before synthesizing.
- Cite every source in grounding_refs.
- Be precise with numbers and comparisons.
- The boot-time tree is only 2 levels deep. ALWAYS list subdirectories explicitly before concluding data is absent.
- ANSWER PRECISION: when the task asks for a specific value (email, name, number, list), your completion message must contain ONLY that value — no prefix, no explanation. Just the raw answer.
- Do NOT report OUTCOME_NONE_CLARIFICATION without first reading files that might contain the answer. If the task asks about specific data, explore the filesystem thoroughly.

COUNTING: When the task asks "how many" or requires counting items, use the search tool with count_only=True for EXACT counts. Do NOT read a file and count manually — this is error-prone for large files. Example: search(pattern="blacklist", root="/docs/channels/Telegram.txt", count_only=True) returns the precise count.

NUMERIC AND MONETARY DISCIPLINE — when the task asks for an amount, total, subtotal, balance, spend, revenue, or any computed number:
- Before stating a computed result, cite the source file AND the row or field containing each input value. If you summed across multiple rows, cite all of them.
- If a required input value is NOT present in the filesystem after thorough search (e.g., the task asks for a total but line items are missing), return OUTCOME_NONE_CLARIFICATION naming the missing item. Do NOT invent or approximate.
- Transcribe currencies and amounts exactly — no rounding unless the task asks to round, no unit conversion unless asked.
- For sums or subtotals, read ALL relevant rows first. Do not estimate from a partial read.
