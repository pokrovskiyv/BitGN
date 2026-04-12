TASK TYPE: Search/discovery operation.
- Use `list` or `tree` to orient yourself before broad exploration.
- Use `search` only when you already have a concrete token, phrase, or field name to look for.
- NEVER call `search` with an empty or generic pattern. If you do not yet know the right text, use `list`, `tree`, or `read` first.
- Prefer the smallest plausible root instead of searching the whole workspace.
- Read all relevant files before answering.
- Include every file you consulted in grounding_refs.

LOOKUP DISCIPLINE:
- When the task asks for a single factual value (name, date, email, number), identify the canonical directory first, then read only the candidate files needed for the answer.
- Do not keep searching the whole workspace after you have already found the authoritative folder.
- If AGENTS.MD names an authoritative source, go there directly instead of doing exploratory global search.
- Read the CANONICAL ENTITY FILE first (for person/entity questions: `/10_entities/cast/<person>.md`). The entity file typically names the right channel / thread / project — follow those references rather than guessing.

MULTI-FILTER DISAMBIGUATION (REQUIRED when the task has TWO or more constraints):
- Tasks like "bill from <vendor> issued around <date range>" have TWO independent filters. One filter is usually in the filename (date), the other is usually in the file CONTENT (vendor).
- The filename slug is NOT the vendor. Slugs like `family_map_wall_board`, `house_mesh_esp32_topup`, `repair_ledger_faucet_parts` describe the PRODUCT/PROJECT, not the seller.
- DO NOT answer from a single filename-date hit without opening the file to verify the other filter(s) inside.
- Protocol: (1) list all candidates matching the cheap filter (usually date range), (2) read each candidate's frontmatter, (3) keep only those matching ALL filters, (4) if exactly one remains, answer from it; if zero, return CLARIFICATION naming the missing combination.

SET / MEMBERSHIP LOOKUPS (REQUIRED when the task asks "in which X is Y involved" or "what projects involve Z"):
- This is NOT a single-value lookup. Expected answer is a LIST.
- Protocol: (1) read the person/entity canonical file for back-references, (2) `list`/`tree` the candidate container (e.g., `/40_projects/`) to see the FULL universe, (3) for each candidate, read its README and check the participant field / body for the target entity, (4) return the sorted list of matches from the `name:` field (NOT the directory slug).
- Do NOT stop at the first 2-3 hits. Enumerate the full container.
- Do NOT grep for the filename pattern `README.MD` — use entity-name tokens or leave `pattern` targeted.

DATE / UPCOMING LOOKUPS (MANDATORY first action: `context()`):
- For "next", "upcoming", or any date-comparison lookup, step 1 MUST be `context()` to get the current date. This is not a hint — it is a hard precondition.
- Then list the canonical entity directory and use `search` with a field token like `birthday:`, `date:`, `dob:` BEFORE falling back to per-file reads (a single search across the directory is cheaper than N reads).
- Budget check: if the task requires reading > 20 entity files, recognize you're overspending and think about a directory-level search first.

RETRY BEFORE GIVING UP:
- If your first search returns 0 results, try: partial terms, individual words, broader directory listing, or a different root path.
- Never declare CLARIFICATION after only 1 failed search. Try at least 3 different search strategies before concluding data is absent.
- Project/entity names in the task may not match filesystem slugs exactly. Try each word separately.
- SEMANTIC MATCHING: if the task uses a descriptive phrase (e.g. "house systems layer"), match by `kind:`, `lane:`, `type:`, or `category:` fields in entity/project files — not just by literal name. Read candidate files and check metadata fields.

ENTITY NAME RESOLUTION:
- When returning a person's name, ALWAYS use the FULL NAME from the entity file heading (`# First Last`), never the `alias:` field from frontmatter.
- Example: if `cast/lukas.md` has heading `# Lukas Brenner` and `alias: lukas`, the answer is `Lukas Brenner`.

ANSWER PRECISION:
- When the task asks for a specific value (email, name, number, list), your completion message must contain ONLY that value — no prefix, no explanation, no extra context. Just the raw answer.
- For list answers ("sorted alphabetically", "one per line"), the body must be the raw list with no header, no bullet, no numbering — just the values separated by newlines.
