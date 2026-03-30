---
description: After each PCDRED eval cycle, verify that all latest reports in docs/ are correctly parsed by the dashboard. Run if the dashboard shows stale data, after adding new markdown reports, or if parsers may have broken due to a format change.
---

# Dashboard Updater

You verify that the PCDRED dashboard is current and functional after a cycle completes.

## Trigger

Run after the Evaluator agent writes a new `docs/eval/run-*.md` report.

## Steps

1. Identify the latest reports:
   ```bash
   ls -t docs/eval/run-*.md | head -1
   ls -t docs/analysis/cycle-*.md | head -1
   ls -t docs/redteam/cycle-*.md | head -1
   ls -t docs/optimization/cycle-*.md | head -1
   ```

2. Verify parsers load without errors:
   ```bash
   cd /Users/vitalypokrovskiy/Projects/BitGN && \
   uv run --project dashboard python -c "
   import sys; sys.path.insert(0, 'dashboard')
   from parsers import load_eval_reports, load_analysis_reports, load_redteam_reports, load_opt_reports
   evals = load_eval_reports()
   print('Eval count:', len(evals))
   print('Latest score:', evals[-1].score_pct if evals else 'NO DATA')
   print('Latest timestamp:', evals[-1].timestamp if evals else 'N/A')
   analyses = load_analysis_reports()
   print('Analysis count:', len(analyses))
   redteams = load_redteam_reports()
   print('RedTeam count:', len(redteams))
   opts = load_opt_reports()
   print('Opt count:', len(opts))
   "
   ```

3. If a parser error occurs:
   - Read the failing report file to find format deviations
   - The most common issue is a changed section header (e.g. `## Observation` renamed)
   - Fix the regex in `dashboard/parsers.py` — the patterns are at the top of each parser function
   - Re-run the verification command to confirm the fix

4. Report result.

## Output

One of:
- `DASHBOARD_OK — N eval reports, latest score X%, all loaders clean`
- `PARSER_FIX_NEEDED — [describe which loader failed and what was fixed]`

## How to run the dashboard

```bash
cd /Users/vitalypokrovskiy/Projects/BitGN/dashboard && make run
```

Opens at http://localhost:8501. Reload the page after a new cycle to see updated data.
