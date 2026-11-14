"""
STEP 5 - JUDGE (fit / maybe / no)
=================================
What it does:
    Gives every company a verdict using fixed rules. There is no AI
    reading in this step: it only looks at columns filled in earlier
    steps, so anyone can re-run it and get the same answer.

The rules, checked in this order. The first one that applies decides.

    NO
      1. It is a distributor.
      2. It is a retailer.
      3. It is not a food maker (packaging, supplements, seeds...).
      4. Its product has been discontinued.
      5. It states an employee count outside the range in settings.yaml.

    MAYBE
      6. The website does not say who makes the product.
      7. The "likely too big" flag is on (2+ plants or a very large
         facility). The flag never excludes; it asks for a human look.
      8. Size is unknown. (A setting decides whether a founding year
         on its own counts as knowing the size.)

    FIT
      9. Everything else: manufactures itself, is a food maker, no
         stated size outside the range, no too-big flag, and at least
         one signal (the recall counts).

Every verdict comes with the rule that decided it and the quote behind
it, so a person can check it.

How to run it:
    python step5_judge.py
"""

import csv
import re
from pathlib import Path

import yaml

# Words for small numbers, so "team of fourteen growers" can be read.
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def first_number(text):
    """Find the first number in a piece of text: "over 5,000 people" -> 5000,
    "three production facilities" -> 3. Returns None if there is none."""
    match = re.search(r"\d[\d,]*", text)
    if match:
        return int(match.group().replace(",", ""))
    for word in re.findall(r"[a-z]+", text.lower()):
        if word in NUMBER_WORDS:
            return NUMBER_WORDS[word]
    return None


def size_clues(company):
    """Turn the size columns back into a list of (kind, value, quote).
    Step 3b wrote them as "employees: over 5,000 people; years: began 1945"
    with the quotes in the same order, separated by " | "."""
    if company["size_clues"] in ("", "unknown"):
        return []
    values = company["size_clues"].split("; ")
    quotes = company["size_clues_evidence"].split(" | ")
    clues = []
    for value, quote in zip(values, quotes):
        kind, _, detail = value.partition(": ")
        clues.append((kind, detail, quote))
    return clues


def too_big_check(clues, flag_rules):
    """Is the "likely too big" flag on? Returns (reason, quote) or (None, None)."""
    for kind, detail, quote in clues:
        if kind == "plant count":
            count = first_number(detail)
            # "plants in Texas, Utah and Idaho" names several without a number.
            if count is None and (" and " in detail or "several" in detail):
                count = 2
            if count is not None and count >= flag_rules["plants_at_least"]:
                return f"likely too big: {detail}", quote
        if kind == "facility size":
            # Only square feet can be compared. ("five acres" is ignored.)
            match = re.search(r"(\d[\d,]*)[\s-]*(?:square|sq)", detail)
            if match and int(match.group(1).replace(",", "")) >= flag_rules["facility_sq_ft_at_least"]:
                return f"likely too big: {detail}", quote
    return None, None


def find_keyword(company, keywords):
    """Does what the company makes mention one of the keywords?"""
    text = (company["what_they_make"] + " " + company["what_they_make_evidence"]).lower()
    return next((k for k in keywords if k.lower() in text), None)


def judge(company, settings):
    """Apply the rules to one company. Returns (verdict, rule, quote, too-big reason)."""
    market = settings["market"]
    words = settings["judge"]
    clues = size_clues(company)
    too_big, too_big_quote = too_big_check(clues, settings["offer"]["likely_too_big_flag"])
    made_by = company["who_makes_it"]
    maker_quote = company["who_makes_it_evidence"]
    product_quote = company["what_they_make_evidence"]

    if company["read_by"] == "not read yet":
        return "not read", "website could not be reached, so nothing to judge", "", ""

    # ---------- NO ----------
    if made_by == "distributor":
        return "no", "rule 1: it is a distributor", maker_quote, too_big
    if made_by == "retailer":
        return "no", "rule 2: it is a retailer", maker_quote, too_big

    keyword = find_keyword(company, words["not_food_maker_keywords"])
    if keyword:
        return "no", f'rule 3: not a food maker (keyword "{keyword}")', product_quote, too_big

    keyword = find_keyword(company, words["discontinued_keywords"])
    if keyword:
        return "no", "rule 4: the product has been discontinued", product_quote, too_big

    for kind, detail, quote in clues:
        if kind == "employees":
            count = first_number(detail)
            if count is not None and not market["employees_min"] <= count <= market["employees_max"]:
                return ("no", f"rule 5: stated employee count ({detail}) is outside "
                        f"{market['employees_min']}-{market['employees_max']}", quote, too_big)

    # ---------- MAYBE ----------
    if made_by == "":
        return ("maybe", "rule 6: the website does not say who makes the product",
                product_quote, too_big)
    if too_big:
        return "maybe", f"rule 7: {too_big}, needs a human look", too_big_quote, too_big
    # Size is "unknown" when there is no size fact. Whether a founding
    # year alone counts as a size fact is a setting.
    size_facts = clues
    if not settings["offer"]["founding_year_alone_counts_as_size"]:
        size_facts = [c for c in clues if c[0] != "years"]
    if not size_facts:
        return ("maybe", "rule 8: manufactures itself, but size is unknown",
                maker_quote, too_big)

    # ---------- FIT ----------
    # The recall from the source list is always present and counts as the signal.
    signals = ["recall"] + [name for name in ("big_retailer", "export", "new_product")
                            if company[f"signal_{name}"]]
    if company["open_qa_jobs"]:
        signals.append("hiring_qa")
    rule = ("rule 9: manufactures itself, food maker, no stated size outside the range, "
            "no too-big flag, signals: " + ", ".join(signals))
    quote = f"{maker_quote} | RECALL: {company['signal_evidence']}"
    return "fit", rule, quote, too_big


def main():
    settings = load_settings()
    folder = Path(settings["output"]["data_folder"])

    with open(folder / "step4_signals.csv", encoding="utf-8-sig") as f:
        companies = list(csv.DictReader(f))

    for company in companies:
        verdict, rule, quote, too_big = judge(company, settings)
        company["verdict"] = verdict
        company["verdict_rule"] = rule
        company["verdict_quote"] = quote
        company["likely_too_big"] = "yes" if too_big else "no"

    # Fits first, then maybes, then the rest.
    order = {"fit": 0, "maybe": 1, "no": 2, "not read": 3}
    companies.sort(key=lambda c: order[c["verdict"]])

    path = folder / "step5_judged.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(companies[0].keys()))
        writer.writeheader()
        writer.writerows(companies)

    print(f"Step 5: judged {len(companies)} companies")
    for verdict in order:
        print(f"  {verdict}: {sum(1 for c in companies if c['verdict'] == verdict)}")
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
