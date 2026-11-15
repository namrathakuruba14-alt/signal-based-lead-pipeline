"""
STEP 7 - SCORE AND FINAL CSV
============================
What it does:
    Gives each remaining company a score using fixed rules, ranks them,
    and writes the final list. No AI reading: it only adds up facts that
    earlier steps already tied to a quote.

How the score is built (all points are in settings.yaml):
    + points for each signal the company shows:
        recall, big retailer, export, new product, open QA job
      A weak signal counts in full. Signal strength is not used, because
      almost no signal on a website carries a date.
    + points if no audited food safety certification was found on the
      pages checked (which does not mean the company is uncertified)
    + points if the verdict is "fit" (so fit ranks above maybe)
    + points if a named contact was found

    The reasons are written next to the score, so nobody has to trust
    the number on its own.

Ranking: highest score first. Ties: top-priority companies first, then
fits, then alphabetical.

Output:
    data/step7_final_leads.csv            real names, never uploaded
    sample_output/final_leads_sample.csv  same rows, names redacted

How to run it:
    python step7_score.py
"""

import csv
from pathlib import Path

from step6_collect_team import load_settings
from step6_fill_contacts import REDACTED, redact

# Careful wording. We only looked at a few saved pages of each website,
# so "not found" is a statement about our search, not about the company.
NOT_FOUND_WORDING = "no certification found on the pages checked"
NOT_FOUND_NOTE = ("This does not mean the company is uncertified. "
                  "It may hold a certification that these pages do not mention.")

# Which column shows each signal. The left side is the signal's id in
# the "signals" list in settings.yaml.
SIGNAL_COLUMNS = {
    "recall": "signal_evidence",          # the FDA recall reason, from Step 1
    "retail_expansion": "signal_big_retailer",
    "export": "signal_export",
    "new_product": "signal_new_product",
    "hiring_qa": "open_qa_jobs",
}


def certifications_found(company, settings):
    """Which audited certifications are mentioned, and the lines showing them."""
    wanted = settings["scoring_rules"]["top_priority"]["certification_terms"]
    found = [t for t in company["food_safety_terms"].split("; ") if t in wanted]
    # Step 3b stored evidence as "term: line | term: line".
    lines = [piece for piece in company["food_safety_terms_evidence"].split(" | ")
             if piece.split(": ")[0] in wanted]
    return found, lines


def score(company, settings):
    """Add up the points for one company. Returns (score, list of reasons)."""
    missing = settings["missing_value_text"]
    signal_points = {signal["id"]: (signal["points"], signal["label"]) for signal in settings["signals"]}
    extra = settings["scoring"]["points"]
    total, reasons = 0, []

    for signal_id, column in SIGNAL_COLUMNS.items():
        points, label = signal_points[signal_id]
        if company[column] and company[column] != missing:
            total += points
            reasons.append(f"{label} +{points}")

    certifications, _ = certifications_found(company, settings)
    if not certifications:
        total += extra["no_audited_certification_found"]
        reasons.append("no certification found on the pages checked "
                       f"+{extra['no_audited_certification_found']}")

    if company["verdict"] == "fit":
        total += extra["verdict_is_fit"]
        reasons.append(f"verdict is fit +{extra['verdict_is_fit']}")

    if company["contact_name"] != missing:
        total += extra["contact_found"]
        reasons.append(f"named contact found +{extra['contact_found']}")

    return total, reasons


def main():
    settings = load_settings()
    missing = settings["missing_value_text"]
    folder = Path(settings["output"]["data_folder"])
    label_for_maybe = settings["offer"]["size_unknown_label"]

    # The companies that came out of Step 6, with their contacts.
    with open(folder / "step6_contacts.csv", encoding="utf-8-sig") as f:
        companies = list(csv.DictReader(f))

    rows = []
    for company in companies:
        total, reasons = score(company, settings)
        certifications, certification_lines = certifications_found(company, settings)
        rows.append({
            "rank": 0,
            "company_name": company["company_name"],
            "website": company["website"],
            "city": company["city"],
            "state": company["state"],
            "verdict": company["verdict"],
            "label": "fit" if company["verdict"] == "fit" else label_for_maybe,
            "top_priority": company["top_priority"],
            "score": total,
            "score_reasons": "; ".join(reasons),
            "verdict_rule": company["verdict_rule"],
            "what_they_make": company["what_they_make"],
            "evidence_makes_it_itself": company["who_makes_it_evidence"],
            "recall_date": company["signal_date"],
            "recall_count": company["signal_count"],
            "evidence_recall": company["signal_evidence"],
            "big_retailer": company["signal_big_retailer"],
            "evidence_big_retailer": company["signal_big_retailer_evidence"],
            "export": company["signal_export"],
            "evidence_export": company["signal_export_evidence"],
            "new_product": company["signal_new_product"],
            "evidence_new_product": company["signal_new_product_evidence"],
            "open_qa_jobs": company["open_qa_jobs"],
            "audited_certifications_found": "; ".join(certifications) or NOT_FOUND_WORDING,
            "evidence_certification": " | ".join(certification_lines),
            "certification_note": "" if certifications else NOT_FOUND_NOTE,
            "size_clues": company["size_clues"],
            "contact_kind": company["contact_kind"],
            "contact_name": company["contact_name"],
            "contact_title": company["contact_title"],
            "evidence_contact": company["contact_quote"],
            "contact_page": company["contact_page"],
            "other_contacts": company["other_contacts"],
        })

    # Highest score first. Ties: top priority, then fit, then name.
    rows.sort(key=lambda r: (-r["score"], r["top_priority"] != "yes",
                             r["verdict"] != "fit", r["company_name"].lower()))
    for position, row in enumerate(rows, start=1):
        row["rank"] = position

    def save(path, data):
        path.parent.mkdir(exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            writer.writeheader()
            writer.writerows(data)

    save(folder / "step7_final_leads.csv", rows)

    # The shareable copy: identical, but every person's name is removed.
    sample = []
    for row in rows:
        safe = dict(row)
        if row["contact_name"] != missing:
            others = [item.split(" (")[0] for item in row["other_contacts"].split("; ") if item]
            names = [row["contact_name"]] + others
            safe["contact_name"] = REDACTED
            safe["evidence_contact"] = redact(row["evidence_contact"], names)
            safe["other_contacts"] = "; ".join(
                REDACTED + " (" + item.split(" (", 1)[1] for item in row["other_contacts"].split("; ") if item)
        sample.append(safe)
    sample_path = Path(settings["output"]["sample_folder"]) / "final_leads_sample.csv"
    save(sample_path, sample)

    print(f"Step 7: scored and ranked {len(rows)} companies")
    for row in rows:
        print(f"  {row['rank']:>2}. {row['score']:>2} pts | {row['company_name']} | {row['label']}"
              f" | top priority: {row['top_priority']}")
    print(f"Real names: {folder / 'step7_final_leads.csv'} (not uploaded)")
    print(f"Redacted sample: {sample_path}")


if __name__ == "__main__":
    main()
