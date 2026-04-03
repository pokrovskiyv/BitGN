"""Gate-enrichment helpers: contextual hints injected into write gate messages."""

import os
from collections import Counter


def folder_format_hint(client, domain, write_path: str, tracker) -> str:
    """Hints about folder format and inbox-stem preservation for write gate messages."""
    from domain_fs import Req_List

    folder = os.path.dirname(write_path) or "/"
    hints = []
    try:
        result = domain.dispatch(client, Req_List(tool="list", path=folder))
        names = [e.name for e in result.entries if not e.is_dir]
        if any(n.upper() == "README.MD" for n in names):
            hints.append(
                f"Hint: '{folder}/README.MD' exists — read it for the required file format."
            )
        exts = [
            os.path.splitext(n)[1].lower() for n in names if n.upper() != "README.MD" and "." in n
        ]
        if exts:
            dominant = Counter(exts).most_common(1)[0][0]
            hints.append(f"Hint: existing files in '{folder}/' use '{dominant}' format.")
    except Exception:
        pass
    # Inbox stem preservation when writing to cards/
    if "cards" in write_path.lower():
        inbox_reads = [p for p in tracker._reads if "inbox" in p.lower()]
        if inbox_reads:
            stem = os.path.splitext(os.path.basename(inbox_reads[-1]))[0]
            if os.path.basename(write_path) != f"{stem}.md":
                hints.append(f"Hint: inbox stem is '{stem}' — card filename MUST be '{stem}.md'.")
    return "\n".join(hints)
