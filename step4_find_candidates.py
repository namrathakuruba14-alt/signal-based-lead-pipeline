"""
STEP 4 (part 1) - FIND CANDIDATE SIGNAL LINES
=============================================
What it does:
    Makes one pass over every saved page. It pulls out each line that
    mentions a big retailer or contains a signal phrase (both lists are
    in settings.yaml). These are "candidate lines".

Why:
    Most of a website says nothing about retailers, exports or new
    products. Pulling out the candidate lines first means the reader
    (Claude in-session now, the API later) judges a few hundred relevant
    lines instead of re-reading every page.

    The script only FINDS candidates. It does not decide anything.
    The reader decides, following prompts/step4_signal_instructions.md.

Known limit:
    A signal worded without any of the listed names or phrases is
    missed. Add phrases to settings.yaml to widen the net.

Nothing here visits a website. It only reads files saved in Step 3b.

How to run it:
    python step4_find_candidates.py
"""

import csv
import re
from pathlib import Path

import yaml

BATCH_SIZE = 20
MAX_LINES_PER_SIGNAL = 6    # per company, so one long page cannot flood the batch
MAX_LINE_LENGTH = 400       # long lines are cut around the matching words
CONTEXT_LENGTH = 120        # how much of the line before/after to show


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_pattern(words, is_name):
    """
    One search pattern that finds any of the words.
    - Retailer NAMES must match exactly, capitals included ("Target" the
      shop, not "target" the verb or "Targeted").
    - PHRASES match any capitals and may continue with more letters, so
      "export" also finds "exports", "exporting" and "exporter".
    """
    joined = "|".join(re.escape(w) for w in words)
    if is_name:
        return re.compile(rf"(?<![A-Za-z0-9])(?:{joined})(?![A-Za-z0-9])")
    return re.compile(rf"(?<![A-Za-z0-9])(?:{joined})", re.I)


def cut_around(line, match):
    """Shorten a very long line, keeping the part around the match."""
    if len(line) <= MAX_LINE_LENGTH:
        return line
    start = max(0, match.start() - MAX_LINE_LENGTH // 2)
    return line[start:start + MAX_LINE_LENGTH]


def main():
    settings = load_settings()
    search = settings["signal_search"]
    folder = Path(settings["output"]["data_folder"])
    out_folder = folder / "step4_candidates"
    out_folder.mkdir(exist_ok=True)

    # What to look for, per signal.
    searches = {
        "big_retailer": [make_pattern(search["big_retailers"], True),
                         make_pattern(search["retailer_phrases"], False)],
        "export": [make_pattern(search["export_phrases"], False)],
        "new_product": [make_pattern(search["new_product_phrases"], False)],
    }

    with open(folder / "step3b_pages_index.csv", encoding="utf-8-sig") as f:
        index = [row for row in csv.DictReader(f) if row["status"] == "saved"]

    # Group saved pages by website, keeping the original order.
    sites = {}
    for row in index:
        sites.setdefault(row["website"], {"name": row["company_name"], "pages": []})
        sites[row["website"]]["pages"].append((row["page_kind"], row["saved_file"]))

    packets = []
    total_candidates = 0
    for website, site in sites.items():
        parts = [f"########## COMPANY: {site['name']}", f"WEBSITE: {website}"]
        for signal, patterns in searches.items():
            found = []
            seen = set()
            for kind, saved_file in site["pages"]:
                lines = Path(saved_file).read_text(encoding="utf-8").split("\n")[2:]
                for number, line in enumerate(lines):
                    match = next((m for p in patterns if (m := p.search(line))), None)
                    if not match or line in seen or len(line.split()) < 4:
                        continue  # skip repeats and bare menu items
                    seen.add(line)
                    before = lines[number - 1][-CONTEXT_LENGTH:] if number > 0 else ""
                    after = lines[number + 1][:CONTEXT_LENGTH] if number + 1 < len(lines) else ""
                    found.append(
                        f"  [{kind} page]\n"
                        f"    (line before) {before}\n"
                        f"    >>> {cut_around(line, match)}\n"
                        f"    (line after)  {after}"
                    )
            total_candidates += len(found[:MAX_LINES_PER_SIGNAL])
            parts.append(f"\n--- {signal}: {len(found)} candidate line(s)"
                         + (f", first {MAX_LINES_PER_SIGNAL} shown" if len(found) > MAX_LINES_PER_SIGNAL else ""))
            parts.extend(found[:MAX_LINES_PER_SIGNAL])
        packets.append("\n".join(parts))

    batch_count = 0
    for start in range(0, len(packets), BATCH_SIZE):
        batch_count += 1
        text = "\n\n\n".join(packets[start:start + BATCH_SIZE])
        path = out_folder / f"batch_{batch_count:02d}.txt"
        path.write_text(text, encoding="utf-8")
        print(f"  {path.name}: {len(packets[start:start + BATCH_SIZE])} companies, {len(text):,} characters")

    print(f"\n{total_candidates} candidate lines for {len(packets)} companies, saved in {out_folder}")


if __name__ == "__main__":
    main()
