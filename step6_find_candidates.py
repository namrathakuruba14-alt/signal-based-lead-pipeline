"""
STEP 6 (part 2) - FIND LINES THAT MIGHT NAME A DECISION MAKER
=============================================================
What it does:
    Goes through the saved pages of each Step 6 company (About and Team
    first, then Home and Careers) and pulls out every line containing a
    job-title word from settings.yaml, with the line before and after it.
    A name is usually on the same line as the title or right next to it.

    It only FINDS candidates. The reader decides, following
    prompts/step6_contact_instructions.md.

Nothing here visits a website.

How to run it:
    python step6_find_candidates.py
"""

import csv
import re
from pathlib import Path

from step6_collect_team import load_settings, select_companies

PAGE_ORDER = ["about", "team", "home", "careers"]
MAX_LINES = 25          # per company
MAX_LINE_LENGTH = 500


def title_pattern(settings):
    """One search pattern for all job-title words. Short all-capital words
    (QA, COO, CEO) must match in capitals so "coo" in "cooking" is ignored."""
    parts = []
    for role in settings["decision_maker"]["role_order"]:
        for word in role["title_words"]:
            if word.isupper():
                parts.append(re.escape(word))
            else:
                parts.append("(?i:" + re.escape(word) + ")")
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(parts) + r")(?![A-Za-z0-9])")


def main():
    settings = load_settings()
    folder = Path(settings["output"]["data_folder"])
    out_folder = folder / "step6_candidates"
    out_folder.mkdir(exist_ok=True)
    pattern = title_pattern(settings)

    with open(folder / "step3b_pages_index.csv", encoding="utf-8-sig") as f:
        index = [row for row in csv.DictReader(f) if row["status"] == "saved"]

    packets = []
    for company in select_companies(settings):
        site = company["website"]
        parts = [f"########## COMPANY: {company['company_name']}", f"WEBSITE: {site}"]
        found, seen = 0, set()
        for kind in PAGE_ORDER:
            row = next((r for r in index if r["website"] == site and r["page_kind"] == kind), None)
            if row is None:
                continue
            lines = Path(row["saved_file"]).read_text(encoding="utf-8").split("\n")[2:]
            for number, line in enumerate(lines):
                if not pattern.search(line) or line in seen or found >= MAX_LINES:
                    continue
                seen.add(line)
                found += 1
                before = lines[number - 1][-200:] if number > 0 else ""
                after = lines[number + 1][:200] if number + 1 < len(lines) else ""
                parts.append(f"  [{kind} page]\n    (line before) {before}\n"
                             f"    >>> {line[:MAX_LINE_LENGTH]}\n    (line after)  {after}")
        parts.insert(2, f"--- {found} candidate line(s)")
        packets.append("\n".join(parts))

    path = out_folder / "batch_01.txt"
    path.write_text("\n\n\n".join(packets), encoding="utf-8")
    print(f"{len(packets)} companies, saved in {path}")


if __name__ == "__main__":
    main()
