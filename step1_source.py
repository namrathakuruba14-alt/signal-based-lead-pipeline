"""
STEP 1 - SOURCE
===============
What it does:
    Reads settings.yaml to see WHICH source to use, runs that source's
    plug-in, and saves the result to a CSV file (a simple spreadsheet).

Why it is built this way:
    The source is swappable. This file knows nothing about the FDA or
    any other source. Each source lives in its own file in the sources/
    folder. All of them hand back rows with the same standard columns,
    so the later steps work the same whichever source was used.

What it does NOT do:
    It does not remove duplicates, find websites or judge fit.
    Those are later steps. This file is the raw, untouched list.

How to run it:
    python step1_source.py
"""

import csv
from pathlib import Path

import yaml  # helper for reading the settings file

from sources import SOURCES  # the list of available source plug-ins

# The columns EVERY source must provide, whatever the market.
# Later steps rely on these names.
STANDARD_COLUMNS = [
    "company_name",     # the company
    "website",          # its website, if the source has it
    "city",
    "state",
    "signal_id",        # which signal from settings.yaml this row shows
    "signal_date",      # when it happened
    "signal_evidence",  # the exact text the signal is based on
]


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def clean_value(value, missing_text):
    """Tidy one value. If it is empty, write "not found" instead of guessing."""
    if value is None:
        return missing_text
    text = " ".join(str(value).split())  # collapse line breaks and extra spaces
    if text == "" or text.upper() == "N/A":
        return missing_text
    return text


def save_csv(rows, settings):
    """Write the rows to data/step1_companies_raw.csv."""
    missing = settings["missing_value_text"]
    folder = Path(settings["output"]["data_folder"])
    folder.mkdir(exist_ok=True)  # create the data folder if it is not there
    path = folder / "step1_companies_raw.csv"

    # Standard columns first, then any extra columns this source added.
    extra_columns = [c for c in rows[0] if c not in STANDARD_COLUMNS]
    columns = STANDARD_COLUMNS + extra_columns + ["source"]

    # "utf-8-sig" makes the file open correctly in Excel.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)  # header row
        for row in rows:
            row["source"] = settings["source"]["type"]  # record where it came from
            writer.writerow([clean_value(row.get(c), missing) for c in columns])
    return path


def main():
    settings = load_settings()
    source_type = settings["source"]["type"]

    # Look up the plug-in named in the settings file.
    if source_type not in SOURCES:
        available = ", ".join(SOURCES)
        raise SystemExit(
            f'settings.yaml asks for source "{source_type}", which does not exist. '
            f"Available sources: {available}"
        )
    fetch = SOURCES[source_type]

    print(f"Step 1: pulling from source \"{source_type}\"")
    rows = fetch(settings)

    if not rows:
        raise SystemExit("The source returned no companies. Nothing was saved.")

    path = save_csv(rows, settings)

    # A quick summary so we can sanity-check the result.
    companies = {str(r.get("company_name") or "").strip().lower() for r in rows}
    print(f"Saved {len(rows)} rows to {path}")
    print(f"These come from about {len(companies)} different company names.")
    print("(One company can have several rows. Step 2 will tidy that up.)")


if __name__ == "__main__":
    main()
