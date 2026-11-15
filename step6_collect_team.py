"""
STEP 6 (part 1) - PICK THE COMPANIES, FETCH A TEAM PAGE IF THERE IS ONE
=======================================================================
What it does:
    1. Picks the companies Step 6 runs on (rules in settings.yaml):
         - every "fit"
         - "size unknown" maybes that also match the top-priority rule
         - minus companies a person dropped by hand
    2. For each of them, looks for ONE Team / Leadership page, only if
       the website links to it and it is not saved already. That is at
       most two visits per site: the home page (to read its links) and
       the team page.

Being polite: same rules as before. It obeys robots.txt, waits between
visits, stays on the company's own site and respects blocks.

How to run it:
    python step6_collect_team.py
"""

import csv
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml
from bs4 import BeautifulSoup

from step3a_find_websites import USER_AGENT, get_page, read_robots
from step3b_collect_pages import INDEX_COLUMNS, readable_text


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def select_companies(settings):
    """The companies Step 6 runs on. Used by all three Step 6 scripts."""
    folder = Path(settings["output"]["data_folder"])
    certifications = settings["scoring_rules"]["top_priority"]["certification_terms"]
    dropped = settings["decision_maker"]["dropped_by_hand"]

    with open(folder / "step5_judged.csv", encoding="utf-8-sig") as f:
        companies = list(csv.DictReader(f))

    selected = []
    for company in companies:
        if company["website"] in dropped:
            continue
        has_certification = any(term in company["food_safety_terms"].split("; ")
                                for term in certifications)
        # In this market every company has a recall, so top priority comes
        # down to: sells to a big retailer or exports, and no certification
        # found on the pages checked.
        top_priority = bool(company["signal_big_retailer"] or company["signal_export"]) \
            and not has_certification
        company["top_priority"] = "yes" if top_priority else "no"

        size_unknown_maybe = (company["verdict"] == "maybe"
                              and company["verdict_rule"].startswith("rule 8"))
        if company["verdict"] == "fit" or (size_unknown_maybe and top_priority):
            selected.append(company)
    return selected


def find_team_link(soup, home_url, words):
    """Find a link on the home page that looks like a Team/Leadership page."""
    own_site = urlparse(home_url).netloc.lower().removeprefix("www.")
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(home_url, href).split("#")[0]
        label = (link.get_text(" ") + " " + urlparse(url).path).lower()
        same_site = urlparse(url).netloc.lower().removeprefix("www.") == own_site
        if same_site and any(word in label for word in words):
            return url
    return None


def main():
    settings = load_settings()
    folder = Path(settings["output"]["data_folder"])
    index_path = folder / "step3b_pages_index.csv"
    wait = settings["politeness"]["seconds_between_requests"]
    words = settings["decision_maker"]["team_page_words"]

    companies = select_companies(settings)
    print(f"Step 6 covers {len(companies)} companies")

    with open(index_path, encoding="utf-8-sig") as f:
        index = list(csv.DictReader(f))
    already_checked = {row["website"] for row in index if row["page_kind"] == "team"}

    for company in companies:
        site = company["website"]
        if site in already_checked:
            print(f"  {site}: team page already checked")
            continue

        def record(status, url="", text=None):
            saved_file = ""
            if text is not None:
                saved_file = str(folder / "pages" / site / "team.txt")
                Path(saved_file).write_text(f"SOURCE: {url}\n\n{text}", encoding="utf-8")
            index.append({"company_name": company["company_name"], "state": company["state"],
                          "website": site, "page_kind": "team", "status": status, "url": url,
                          "characters": len(text) if text is not None else 0,
                          "saved_file": saved_file})
            print(f"  {site}: {status}")

        rules = read_robots("https://" + site, settings)
        home_url = "https://" + site + "/"
        if not rules.can_fetch(USER_AGENT, home_url):
            record("not saved: site asks programs not to visit")
            continue
        time.sleep(wait)
        home, reason = get_page(home_url, settings)
        if home is None:
            record(f"not saved: {reason}")
            continue

        soup = BeautifulSoup(home.text[:2_000_000], "html.parser")
        url = find_team_link(soup, home.url, words)
        saved_urls = {row["url"].rstrip("/") for row in index if row["website"] == site}
        if url is None:
            record("no such page found on the site")
        elif url.rstrip("/") in saved_urls:
            record("team link points to a page that is already saved", url)
        elif not rules.can_fetch(USER_AGENT, url):
            record("not saved: site asks programs not to visit this page", url)
        else:
            time.sleep(wait)
            page, reason = get_page(url, settings)
            if page is None:
                record(f"not saved: {reason}", url)
            else:
                record("saved", page.url, readable_text(BeautifulSoup(page.text[:2_000_000], "html.parser")))

        with open(index_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
            writer.writeheader()
            writer.writerows(index)


if __name__ == "__main__":
    main()
