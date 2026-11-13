"""
STEP 2 - CLEAN (pass 1: by company name)
========================================
What it does:
    Step 1 gives one row per signal (e.g. one row per recalled product),
    so the same company can appear many times. This step merges those
    rows into ONE row per company.

How it decides two rows are the same company:
    The names match after ignoring capitals, punctuation and endings
    like "Inc" or "LLC" (the list is in settings.yaml), AND they are in
    the same state. It never guesses that two similar-looking names are
    the same - a wrong merge would hide a real lead.

What each company keeps:
    - the details of its MOST RECENT signal (date + exact evidence text)
    - how many signals it had in total
    - every spelling of its name that was merged, so merges can be checked

What it does NOT do:
    It does not remove duplicates by website yet, because we have no
    websites. That is pass 2, after the Enrich step finds them.

Works with any source: it only uses the standard columns from Step 1.

How to run it:
    python step2_clean.py
"""

import csv
import re
from pathlib import Path

import yaml  # helper for reading the settings file


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def matching_name(name, endings_to_ignore):
    """
    Make a simplified version of a company name, used ONLY for matching.
    "Honeyville, Inc." -> "honeyville"
    The original name is never changed in the output.
    """
    text = name.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]", "", text)  # drop punctuation
    words = text.split()

    # Remove endings like "inc" or "llc" from the END of the name only.
    # (Always keep at least one word, so a name can't become empty.)
    while len(words) > 1 and words[-1] in endings_to_ignore:
        words.pop()

    return " ".join(words)


def main():
    settings = load_settings()
    missing = settings["missing_value_text"]
    endings = set(settings["clean"]["name_endings_to_ignore"])
    also_match = settings["clean"]["must_also_match"]  # e.g. "state"
    folder = Path(settings["output"]["data_folder"])

    # --- Read the raw list from Step 1 ---
    with open(folder / "step1_companies_raw.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    columns = list(rows[0].keys())

    # --- Put rows that belong to the same company into the same group ---
    groups = {}  # key = (simplified name, state) -> list of that company's rows
    for row in rows:
        key = (matching_name(row["company_name"], endings), row.get(also_match, ""))
        groups.setdefault(key, []).append(row)

    # --- Turn each group into one row ---
    companies = []
    for group in groups.values():
        # Sort newest first. A missing date counts as oldest.
        group.sort(
            key=lambda r: "" if r["signal_date"] == missing else r["signal_date"],
            reverse=True,
        )
        company = dict(group[0])  # start from the most recent row

        # How many signals this company had in total
        company["signal_count"] = len(group)

        # Which kinds of signal (a source could report more than one kind)
        kinds = sorted({r["signal_id"] for r in group})
        company["signal_id"] = "; ".join(kinds)

        # Every spelling that was merged into this row, so we can check it
        spellings = sorted({r["company_name"] for r in group})
        company["names_merged"] = " | ".join(spellings)

        companies.append(company)

    # Newest signals at the top
    companies.sort(
        key=lambda c: "" if c["signal_date"] == missing else c["signal_date"],
        reverse=True,
    )

    # --- Save ---
    path = folder / "step2_companies_clean.csv"
    out_columns = columns + ["signal_count", "names_merged"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=out_columns)
        writer.writeheader()
        writer.writerows(companies)

    # --- Summary so we can sanity-check ---
    merged_spellings = sum(1 for c in companies if " | " in c["names_merged"])
    print(f"Step 2: {len(rows)} rows in, {len(companies)} companies out.")
    print(f"{merged_spellings} companies had more than one spelling merged.")
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
