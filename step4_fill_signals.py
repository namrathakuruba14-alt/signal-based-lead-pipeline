"""
STEP 4 (part 2) - CHECK QUOTES AND GRADE SIGNALS
================================================
What it does:
    1. Takes the reader's answers (data/step4_answers/).
    2. QUOTE CHECK: every quote must be on the company's saved pages word
       for word. If not, the signal is deleted.
    3. STRENGTH, decided by this script and not by the reader:
         strong = dated within the last 12 months, and the text showing
                  that date was also found on the page
         weak   = a real signal with no date (or an older date)
         blank  = not mentioned
    4. Adds the signal columns to the Step 3b file and saves
       data/step4_signals.csv.

Nothing here visits a website. It only reads files saved earlier.

How to run it:
    python step4_fill_signals.py
"""

import csv
import json
from datetime import date, timedelta
from pathlib import Path

import yaml

# Reuse the exact same quote check as Step 3b.
from step3b_fill_columns import find_quote, squash

SIGNALS = ["big_retailer", "export", "new_product"]


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    settings = load_settings()
    folder = Path(settings["output"]["data_folder"])
    window = settings["signal_search"]["strong_if_dated_within_days"]
    oldest_strong_date = date.today() - timedelta(days=window)

    # --- Load the saved pages (for the quote check) ---
    pages = {}  # website -> {page kind: text on one line}
    with open(folder / "step3b_pages_index.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["status"] == "saved":
                text = Path(row["saved_file"]).read_text(encoding="utf-8")
                body = text.split("\n", 2)[2]
                pages.setdefault(row["website"], {})[row["page_kind"]] = squash(body)

    # --- Load the reader's answers ---
    answers = {}
    for path in sorted((folder / "step4_answers").glob("batch_*.json")):
        for answer in json.loads(path.read_text(encoding="utf-8")):
            answers[answer["website"]] = answer

    with open(folder / "step3b_enriched.csv", encoding="utf-8-sig") as f:
        companies = list(csv.DictReader(f))

    check_log = []
    for company in companies:
        site = company["website"]
        answer = answers.get(site, {})
        site_pages = pages.get(site, {})

        for signal in SIGNALS:
            a = answer.get(signal, {})
            found, quote = a.get("found", ""), a.get("quote", "")
            signal_date, date_quote = a.get("signal_date", ""), a.get("date_quote", "")
            value = evidence = strength = dated = ""

            if found and quote:
                where = find_quote(quote, site_pages)
                check_log.append({"website": site, "signal": signal, "found": found, "quote": quote,
                                  "result": f"found on {where} page" if where else "NOT FOUND - signal deleted"})
                if where:
                    value, evidence, strength = found, squash(quote), "weak"

                    # A date only counts if (a) it reads as a real date,
                    # (b) the text showing it is on the page, and
                    # (c) that text contains the same year.
                    if signal_date and date_quote:
                        date_ok = bool(find_quote(date_quote, site_pages)) and signal_date[:4] in date_quote
                        try:
                            parsed = date.fromisoformat(signal_date)
                        except ValueError:
                            date_ok = False
                        check_log.append({"website": site, "signal": signal + " (date)", "found": signal_date,
                                          "quote": date_quote,
                                          "result": "date accepted" if date_ok else "DATE NOT PROVEN - treated as undated"})
                        if date_ok:
                            dated = signal_date
                            if oldest_strong_date <= parsed <= date.today():
                                strength = "strong"

            company[f"signal_{signal}"] = value
            company[f"signal_{signal}_strength"] = strength
            company[f"signal_{signal}_date"] = dated
            company[f"signal_{signal}_evidence"] = evidence

    # --- Save ---
    path = folder / "step4_signals.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(companies[0].keys()))
        writer.writeheader()
        writer.writerows(companies)

    log_path = folder / "step4_quote_check.csv"
    with open(log_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["website", "signal", "found", "quote", "result"])
        writer.writeheader()
        writer.writerows(check_log)

    failed = sum(1 for c in check_log if c["result"].startswith(("NOT", "DATE NOT")))
    print(f"Step 4: {len(answers)} companies answered. {len(check_log)} checks, {failed} failed.")
    for signal in SIGNALS:
        strong = sum(1 for c in companies if c[f"signal_{signal}_strength"] == "strong")
        weak = sum(1 for c in companies if c[f"signal_{signal}_strength"] == "weak")
        print(f"  {signal}: {strong} strong, {weak} weak")
    print(f"Saved to {path}  (check log: {log_path})")


if __name__ == "__main__":
    main()
