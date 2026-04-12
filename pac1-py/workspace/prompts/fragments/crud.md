TASK TYPE: Simple CRUD operation.
- Verify the target file exists (or doesn't) before writing.
- A write response of "written: path (OK)" means SUCCESS — do NOT repeat the same write. Proceed to re-read for verification.
- After writing, re-read the file to confirm the write succeeded.
- Include the modified file in grounding_refs.

DELETE-ALL / FIND-ALL DISCIPLINE (required for "delete all X containing Y", "remove every Z", "clean up all W"):
- "All" is a universal quantifier. Missing one target = wrong answer.
- Protocol: (1) `search` with the exact content token across the broadest plausible root (usually `/`), non-`count_only`, to enumerate the FULL candidate set, (2) read each candidate to confirm the literal phrase is present (search may hit substring noise), (3) delete in sorted order, (4) return the sorted list of deleted paths, one per line.
- Do NOT scope the search to one subdirectory (like `/50_finance/`) on the assumption that the targets live there. The phrase may appear in multiple lanes.
- NEVER use an empty search pattern. If you don't know the right token, use the literal phrase from the task.
- Answer format: ONLY the deleted paths, one per line, sorted alphabetically (unless the task says otherwise). Use paths WITHOUT a leading slash (e.g. `50_finance/purchases/file.md`, not `/50_finance/purchases/file.md`).
