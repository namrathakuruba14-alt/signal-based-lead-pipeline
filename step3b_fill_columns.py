"""
STEP 3b (part 3) - CHECK QUOTES AND FILL COLUMNS
================================================
What it does:
    1. QUOTE CHECK. Takes the reader's answers (data/step3b_answers/)
       and checks every quote against the saved page text. If a quote is
       not there WORD FOR WORD, the answer is deleted and the failure is
       logged. This is what stops invented or misquoted facts, whoever
       (or whatever) did the reading.
    2. KEYWORD MATCH. Looks for the food safety terms listed in
       settings.yaml on each company's saved pages and records each one
       with the line it appeared in. Plain matching, no judgement.
    3. Writes one row per company to data/step3b_enriched.csv.

Nothing here visits a website. It only reads files saved earlier.

How to run it:
    python step3b_fill_columns.py
"""

import csv
import json
import re
from pathlib import Path

import yaml

# The only answers allowed in the "who makes it" column.
WHO_MAKES_IT = {"manufactures itself", "co-packed", "distributor", "retailer"}
SIZE_CLUES = {"employees", "facility size", "plant count", "years"}


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def squash(text):
    """Turn every run of spaces/line breaks into one space.
    This is the ONLY tidying allowed before comparing a quote to a page."""
    return " ".join(text.split())


def find_quote(quote, pages):
    """Is this quote on one of the company's saved pages, word for word?
    Returns the kind of page it was found on (e.g. "about"), or None."""
    quote = squash(quote)
    if len(quote) < 8:  # too short to prove anything
        return None
    for kind, text in pages.items():
        if quote in text:
            return kind
    return None


def find_terms(terms, pages):
    """Find each food safety term on the saved pages.
    Returns a list of (term, the line it appeared in, page kind)."""
    found = []
    for term in terms:
        # Terms written in capitals (SQF, GMP) must match in capitals, so
        # "gmp" inside another word or a web address is not counted.
        flags = 0 if term.isupper() else re.I
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", flags)
        for kind, lines in pages.items():
            line = next((l for l in lines if pattern.search(l)), None)
            if line:
                found.append((term, line[:300], kind))
                break  # one piece of evidence per term is enough
    return found


def main():
    settings = load_settings()
    missing = settings["missing_value_text"]
    folder = Path(settings["output"]["data_folder"])

    # --- Load the saved pages for every company ---
    with open(folder / "step3b_pages_index.csv", encoding="utf-8-sig") as f:
        index = list(csv.DictReader(f))
    page_lines = {}     # website -> {page kind: list of lines}   (for keyword match)
    page_squashed = {}  # website -> {page kind: text on one line} (for quote check)
    external_careers = {}
    for row in index:
        site = row["website"]
        page_lines.setdefault(site, {})
        page_squashed.setdefault(site, {})
        if row["status"] == "saved":
            text = Path(row["saved_file"]).read_text(encoding="utf-8")
            body = text.split("\n", 2)[2] if text.startswith("SOURCE:") else text
            page_lines[site][row["page_kind"]] = body.split("\n")
            page_squashed[site][row["page_kind"]] = squash(body)
        elif row["page_kind"] == "careers" and "another site" in row["status"]:
            external_careers[site] = row["url"]

    # --- Load the reader's answers (every batch file that exists) ---
    answers = {}
    for path in sorted((folder / "step3b_answers").glob("batch_*.json")):
        for answer in json.loads(path.read_text(encoding="utf-8")):
            answers[answer["website"]] = answer

    # --- Check quotes and build one row per company ---
    with open(folder / "step3a_websites.csv", encoding="utf-8-sig") as f:
        companies = [c for c in csv.DictReader(f) if c["website"] != missing]

    check_log = []  # every quote, and whether it passed

    def checked(site, field, answer, quote):
        """Keep an answer only if its quote is really on the page."""
        where = find_quote(quote, page_squashed.get(site, {})) if answer and quote else None
        if answer or quote:
            check_log.append({
                "website": site, "field": field, "answer": answer, "quote": quote,
                "result": f"found on {where} page" if where else "NOT FOUND - answer deleted",
            })
        return (answer, squash(quote), where) if where else ("", "", "")

    rows = []
    for company in companies:
        site = company["website"]
        answer = answers.get(site, {})
        row = dict(company)
        row["pages_saved"] = ", ".join(page_lines.get(site, {})) or "none"
        row["read_by"] = "Claude (in session)" if answer else "not read yet"

        # What they make
        a = answer.get("what_they_make", {})
        row["what_they_make"], row["what_they_make_evidence"], _ = checked(
            site, "what_they_make", a.get("answer", ""), a.get("quote", ""))

        # Who makes it (only the allowed answers are accepted)
        a = answer.get("who_makes_it", {})
        value = a.get("answer", "") if a.get("answer", "") in WHO_MAKES_IT else ""
        row["who_makes_it"], row["who_makes_it_evidence"], _ = checked(
            site, "who_makes_it", value, a.get("quote", ""))

        # Size clues: keep each clue whose quote passes. Never estimated.
        clues, clue_quotes = [], []
        for clue in answer.get("size_clues", []):
            if clue.get("clue") not in SIZE_CLUES:
                continue
            value, quote, _ = checked(site, f"size: {clue['clue']}", clue.get("value", ""), clue.get("quote", ""))
            if value:
                clues.append(f"{clue['clue']}: {value}")
                clue_quotes.append(quote)
        row["size_clues"] = "; ".join(clues) or "unknown"
        row["size_clues_evidence"] = " | ".join(clue_quotes)

        # Open QA / food safety jobs
        jobs, job_quotes = [], []
        for job in answer.get("open_qa_jobs", []):
            title, quote, _ = checked(site, "open_qa_job", job.get("title", ""), job.get("quote", ""))
            if title:
                jobs.append(title)
                job_quotes.append(quote)
        row["open_qa_jobs"] = "; ".join(jobs)
        row["open_qa_jobs_evidence"] = " | ".join(job_quotes)
        row["careers_link_elsewhere"] = external_careers.get(site, "")

        # Food safety terms: plain keyword match, done by code
        terms = find_terms(settings["food_safety_terms"], page_lines.get(site, {}))
        row["food_safety_terms"] = "; ".join(term for term, _, _ in terms)
        row["food_safety_terms_evidence"] = " | ".join(f"{term}: {line}" for term, line, _ in terms)

        rows.append(row)

    # --- Save ---
    path = folder / "step3b_enriched.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    log_path = folder / "step3b_quote_check.csv"
    with open(log_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["website", "field", "answer", "quote", "result"])
        writer.writeheader()
        writer.writerows(check_log)

    failed = sum(1 for c in check_log if c["result"].startswith("NOT FOUND"))
    print(f"Step 3b: {len(rows)} companies, {len(answers)} read so far.")
    print(f"Quote check: {len(check_log)} quotes checked, {failed} not found and deleted.")
    print(f"Saved to {path}  (quote check log: {log_path})")


if __name__ == "__main__":
    main()
