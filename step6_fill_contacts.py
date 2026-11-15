"""
STEP 6 (part 3) - CHECK EVERY CONTACT AND PICK THE BEST ONE
===========================================================
What it does:
    1. Takes the reader's answers (data/step6_answers/).
    2. Checks every contact. A contact is kept only if ALL of these hold:
         - the quote is on the company's saved pages, word for word
         - the person's name is inside the quote
         - the person's title is inside the quote
         - the title contains a word for the kind of role claimed
       Anything else is deleted. No name is ever guessed.
    3. Picks the most wanted kind found: QA / food safety first, then
       operations, then owner / founder. If none, "not found".
    4. Saves the real result to data/step6_contacts.csv (never uploaded)
       and a copy with every name replaced by "[name redacted]" to
       sample_output/step6_contacts_sample.csv (safe for GitHub).

How to run it:
    python step6_fill_contacts.py
"""

import csv
import json
import re
from pathlib import Path

from step3b_fill_columns import squash
from step6_collect_team import load_settings, select_companies

REDACTED = "[name redacted]"

# Columns that go into the shareable sample.
SAMPLE_COLUMNS = [
    "company_name", "website", "state", "verdict", "top_priority", "what_they_make",
    "contact_kind", "contact_name", "contact_title", "contact_quote", "contact_page",
    "other_contacts",
]


def redact(text, names):
    """Replace every part of every name with the redaction marker."""
    for name in names:
        text = text.replace(name, REDACTED)
        for part in name.split():
            if len(part) > 2:
                text = re.sub(rf"\b{re.escape(part)}\b", REDACTED, text)
    # Tidy "[name redacted] [name redacted]" into one marker.
    text = re.sub(rf"(?:{re.escape(REDACTED)}[\s.]*)+", REDACTED + " ", text).strip()
    return text.replace(REDACTED + " ,", REDACTED + ",")


def main():
    settings = load_settings()
    missing = settings["missing_value_text"]
    folder = Path(settings["output"]["data_folder"])
    roles = settings["decision_maker"]["role_order"]
    kinds = [role["kind"] for role in roles]

    # Saved pages, for the quote check (page kind -> (url, text on one line)).
    pages = {}
    with open(folder / "step3b_pages_index.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["status"] == "saved":
                text = Path(row["saved_file"]).read_text(encoding="utf-8")
                pages.setdefault(row["website"], {})[row["page_kind"]] = (row["url"], squash(text.split("\n", 2)[2]))

    answers = {}
    for path in sorted((folder / "step6_answers").glob("batch_*.json")):
        for answer in json.loads(path.read_text(encoding="utf-8")):
            answers[answer["website"]] = answer

    check_log, results, sample = [], [], []
    for company in select_companies(settings):
        site = company["website"]
        kept = []
        for contact in answers.get(site, {}).get("contacts", []):
            name, title = contact.get("name", ""), contact.get("title", "")
            kind, quote = contact.get("kind", ""), squash(contact.get("quote", ""))

            where = next(((page_kind, url) for page_kind, (url, text) in pages.get(site, {}).items()
                          if quote and quote in text), None)
            title_words = next((r["title_words"] for r in roles if r["kind"] == kind), [])
            problems = []
            if not where:
                problems.append("quote not found on the saved pages")
            if not name or name not in quote:
                problems.append("name is not inside the quote")
            if not title or title not in quote:
                problems.append("title is not inside the quote")
            if not any(word.lower() in title.lower() for word in title_words):
                problems.append("title does not match the kind of role claimed")

            check_log.append({"website": site, "kind": kind, "name": name, "title": title, "quote": quote,
                              "result": "kept" if not problems else "DELETED: " + "; ".join(problems)})
            if not problems:
                kept.append({"kind": kind, "name": name, "title": title, "quote": quote,
                             "page": f"{where[0]} page: {where[1]}"})

        # Most wanted kind first.
        kept.sort(key=lambda c: kinds.index(c["kind"]))
        best = kept[0] if kept else None
        company["contact_kind"] = best["kind"] if best else missing
        company["contact_name"] = best["name"] if best else missing
        company["contact_title"] = best["title"] if best else missing
        company["contact_quote"] = best["quote"] if best else missing
        company["contact_page"] = best["page"] if best else missing
        company["other_contacts"] = "; ".join(f"{c['name']} ({c['title']})" for c in kept[1:])
        results.append(company)

        # The shareable copy: same row, every name removed.
        names = [c["name"] for c in kept]
        safe = {column: company[column] for column in SAMPLE_COLUMNS}
        if best:
            safe["contact_name"] = REDACTED
            safe["contact_quote"] = redact(best["quote"], names)
            safe["other_contacts"] = "; ".join(f"{REDACTED} ({c['title']})" for c in kept[1:])
        sample.append(safe)

    def save(path, rows):
        path.parent.mkdir(exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    save(folder / "step6_contacts.csv", results)
    save(folder / "step6_contact_check.csv", check_log)
    sample_path = Path(settings["output"]["sample_folder"]) / "step6_contacts_sample.csv"
    save(sample_path, sample)

    found = sum(1 for c in results if c["contact_name"] != missing)
    deleted = sum(1 for c in check_log if c["result"].startswith("DELETED"))
    print(f"Step 6: {len(results)} companies, contact found for {found}.")
    print(f"Checks: {len(check_log)} contacts checked, {deleted} deleted.")
    for kind in kinds:
        print(f"  {kind}: {sum(1 for c in results if c['contact_kind'] == kind)}")
    print(f"Real names: {folder / 'step6_contacts.csv'} (not uploaded)")
    print(f"Redacted sample: {sample_path}")


if __name__ == "__main__":
    main()
