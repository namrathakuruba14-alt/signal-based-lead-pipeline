"""
STEP 3b (part 2) - PREPARE READING BATCHES
==========================================
What it does:
    Bundles the saved page text into "reading packets": one text file
    per batch of about 20 companies. A reader then goes through each
    packet and fills in the facts, following the instructions in
    prompts/step3b_read_instructions.md.

Who is the reader?
    In this run: Claude, working in a Claude Code session.
    Later: a script can send the same packet and the same instructions
    to the Claude API. Nothing else in the pipeline changes.

Why tidy the text first:
    Websites repeat their menu and footer on every page. This script
    removes lines already seen on an earlier page of the same site, so
    the reader is not given the same menu five times.

Nothing here visits a website. It only reads files saved earlier.

How to run it:
    python step3b_prepare_reading.py
"""

import csv
from pathlib import Path

import yaml

BATCH_SIZE = 20

# Pages given to the reader for this step, and how much of each (in
# characters, after repeated lines are removed). News is left out here;
# Step 4 reads it when looking for signals.
PAGES_TO_READ = {"home": 5000, "about": 6000, "products": 3000, "careers": 6000}


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def company_packet(company_name, website, pages):
    """Build the text one company's pages contribute to a packet."""
    parts = [f"########## COMPANY: {company_name}", f"WEBSITE: {website}"]
    seen_lines = set()

    for kind, limit in PAGES_TO_READ.items():
        if kind not in pages:
            continue
        text = Path(pages[kind]).read_text(encoding="utf-8")
        lines = text.split("\n")[2:]  # skip the "SOURCE:" line and the blank after it

        # Keep only lines not already shown from an earlier page of this site.
        fresh = []
        for line in lines:
            if line not in seen_lines and len(line) > 2:
                fresh.append(line)
                seen_lines.add(line)
        body = "\n".join(fresh)

        note = ""
        if len(body) > limit:
            body = body[:limit]
            note = f"  (first {limit} characters only)"
        parts.append(f"\n----- PAGE: {kind}{note}\n{body}")

    return "\n".join(parts)


def main():
    settings = load_settings()
    folder = Path(settings["output"]["data_folder"])
    out_folder = folder / "step3b_reading"
    out_folder.mkdir(exist_ok=True)

    # The index lists every page saved in part 1.
    with open(folder / "step3b_pages_index.csv", encoding="utf-8-sig") as f:
        index = list(csv.DictReader(f))

    # Group saved pages by website, keeping the original order.
    sites = {}
    for row in index:
        site = sites.setdefault(row["website"], {"name": row["company_name"], "pages": {}})
        if row["status"] == "saved":
            site["pages"][row["page_kind"]] = row["saved_file"]

    # Only companies with at least one saved page can be read.
    readable = [(w, s) for w, s in sites.items() if s["pages"]]

    batch_count = 0
    for start in range(0, len(readable), BATCH_SIZE):
        batch = readable[start:start + BATCH_SIZE]
        batch_count += 1
        text = "\n\n\n".join(company_packet(s["name"], w, s["pages"]) for w, s in batch)
        path = out_folder / f"batch_{batch_count:02d}.txt"
        path.write_text(text, encoding="utf-8")
        print(f"  {path.name}: {len(batch)} companies, {len(text):,} characters")

    print(f"\n{len(readable)} companies in {batch_count} batches, saved in {out_folder}")
    print(f"{len(sites) - len(readable)} companies had no saved pages and cannot be read.")


if __name__ == "__main__":
    main()
