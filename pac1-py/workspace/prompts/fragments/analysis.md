TASK TYPE: Analysis operation.
- Read all relevant sources before synthesizing.
- Cite every source in grounding_refs.
- Be precise with numbers and comparisons.
- The boot-time tree is only 2 levels deep. ALWAYS list subdirectories explicitly before concluding data is absent.
- ANSWER PRECISION: when the task asks for a specific value (email, name, number, list), your completion message must contain ONLY that value — no prefix, no explanation. Just the raw answer.
- Do NOT report OUTCOME_NONE_CLARIFICATION without first reading files that might contain the answer. If the task asks about specific data, explore the filesystem thoroughly.

COUNTING — two different shapes, pick the right one:

SHAPE A: In-file occurrence counting (count how many times pattern X appears in file Y). Use `search(pattern="<token>", root="<file>", count_only=True)`. `pattern` is a CONTENT regex, NOT a filename. Do NOT pass `"README.MD"` or `"*.md"` as pattern — that searches for the literal string inside file bodies.

SHAPE B: Directory-enumeration counting (count entities in directory X where field Y matches Z). Example: "How many PLANNED projects involve NORA?" requires:
1. `list /40_projects/` to see ALL project directories (the full universe).
2. For each candidate, `read README.md` and check frontmatter `status:` field AND body references to the target entity.
3. Accumulate the matching count manually.
4. Answer must be an INTEGER only — no "projects", no "N projects", no "**N**", no bullet. Just the number.
Do NOT use `count_only=True` for Shape B — it doesn't filter by frontmatter fields.

NUMERIC ANSWER FORMAT (when task says "Answer with a number only" / "Just the number" / "return only the number"):
- Completion message body MUST contain exactly one token: the digit sequence. No word "projects", no "The answer is", no bullets, no markdown bold. Just `3` or `520` or `42`.

NUMERIC AND MONETARY DISCIPLINE — when the task asks for an amount, total, subtotal, balance, spend, revenue, or any computed number:
- Before stating a computed result, cite the source file AND the row or field containing each input value. If you summed across multiple rows, cite all of them in grounding_refs.
- READ ALL RELEVANT ROWS FIRST. Do not estimate from a partial read. If there are 8 invoices matching the vendor+date filter, you must read all 8 before summing.
- If a required input value is NOT present after thorough search, return OUTCOME_NONE_CLARIFICATION naming the missing item. Do NOT invent or approximate.
- Transcribe currencies and amounts exactly — no rounding unless the task asks to round, no unit conversion unless asked.
- For "how much did X pay/charge/spend" questions: (1) `list /50_finance/invoices/` or `/purchases/`, (2) filter by vendor (must be inside file content, not filename slug), (3) read all matches, (4) sum `total_eur` or `amount` fields, (5) cite every row.
- For multilingual monetary questions ("wie viel", "多少钱", "cuánto"), treat them identically — the filesystem is language-agnostic.
