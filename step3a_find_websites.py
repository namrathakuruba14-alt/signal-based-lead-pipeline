"""
STEP 3a - FIND WEBSITES (guess, then verify)
============================================
What it does:
    Our list has company names and locations but no websites.
    For each company this step:
      1. GUESSES likely web addresses from the name
         ("Honeyville, Inc" -> honeyville.com)
      2. Checks whether each guessed address exists at all
      3. VERIFIES it: the site must show the company's name AND its
         location (city + state, or zip code)
      4. Saves the exact text that matched, so a person can check it

    If no guess passes the check, the website is "not found".
    A missing website is better than a wrong one.

Being polite:
    - It identifies itself honestly to websites.
    - It obeys each site's robots.txt (the site's rules for programs).
    - It waits between visits to the same site (see settings.yaml).
    - It looks at 5 pages per site at most, and stops as soon as it has proof.
    - If a site refuses automated visitors, it records that and moves on.
      It never tries to get around a block.
    - Companies checked in an earlier run are skipped, not visited again.

How to run it:
    python step3a_find_websites.py        (uses the number in settings.yaml)
    python step3a_find_websites.py 5      (just the first 5, for testing)
"""

import csv
import re
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests                # helper for visiting websites
import yaml                    # helper for reading the settings file
from bs4 import BeautifulSoup  # helper for reading the text of a web page

from step2_clean import matching_name  # reuse the name-simplifying rule

# How this program introduces itself to websites.
USER_AGENT = "lead-pipeline-research/0.1 (small polite research script)"

# State abbreviations and full names, so "WA" also matches "Washington".
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------
# PART 1: GUESS
# ----------------------------------------------------------------------

def guess_names(company_name, settings):
    """
    Turn a company name into a few simplified versions to try.
    "Palmetto Gourmet Foods Inc." -> ["palmetto gourmet foods", "palmetto gourmet"]
    """
    endings = set(settings["clean"]["name_endings_to_ignore"])
    optional = set(settings["find_website"]["optional_last_words"])

    # "Silver Moon LP dba Loard's Ice Cream" is two names: the legal name
    # and the trading name ("dba" = "doing business as"). Try both.
    parts = re.split(r"\s+(?:dba|d/b/a|doing business as)\s+", company_name, flags=re.I)

    names = []
    for part in parts:
        words = matching_name(part, endings).split()
        if words and words[0] == "the":
            words = words[1:]
        names.append(" ".join(words))
        # Also try without a generic last word such as "foods".
        if len(words) > 1 and words[-1] in optional:
            names.append(" ".join(words[:-1]))

    # Remove repeats and anything too short to be a sensible guess.
    unique = []
    for name in names:
        if len(name.replace(" ", "")) >= 4 and name not in unique:
            unique.append(name)
    return unique


def guess_domains(name, settings):
    """ "palmetto gourmet" -> ["palmettogourmet.com", "palmetto-gourmet.com"] """
    words = name.split()
    domains = []
    for ending in settings["find_website"]["domain_endings"]:
        domains.append("".join(words) + ending)
        if len(words) > 1:
            domains.append("-".join(words) + ending)
    return domains


def domain_exists(domain):
    """Ask the internet's address book whether this address exists.
    This does not visit the website, so it bothers nobody."""
    try:
        socket.gethostbyname(domain)
        return True
    except OSError:
        return False


# ----------------------------------------------------------------------
# PART 2: VISIT POLITELY
# ----------------------------------------------------------------------

def get_page(url, settings):
    """
    Download one web page.
    Returns (response, "") if it worked, or (None, the exact reason) if not.
    If a site refuses us, we record that and move on. We never try to
    get around a block.
    """
    timeout = settings["politeness"]["timeout_seconds"]
    try:
        response = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=timeout
        )
    except requests.exceptions.SSLError:
        return None, "security certificate problem"
    except requests.exceptions.Timeout:
        return None, f"too slow, gave up after {timeout} seconds"
    except requests.exceptions.TooManyRedirects:
        return None, "redirects in a loop"
    except requests.exceptions.ConnectionError:
        return None, "connection failed (no working website at this address)"
    except requests.RequestException as error:
        return None, f"request failed ({type(error).__name__})"

    if response.status_code in (401, 403, 429):
        return None, f"site refused automated visitors (code {response.status_code})"
    if response.status_code != 200:
        return None, f"site answered with error code {response.status_code}"
    if "html" not in response.headers.get("Content-Type", ""):
        return None, "address does not return a normal web page"
    return response, ""


def read_robots(site_root, settings):
    """Read the site's robots.txt - its rules for programs like this one."""
    rules = RobotFileParser()
    try:
        response = requests.get(
            site_root + "/robots.txt",
            headers={"User-Agent": USER_AGENT},
            timeout=settings["politeness"]["timeout_seconds"],
        )
        if response.status_code == 200:
            rules.parse(response.text.splitlines())
        else:
            rules.parse([])  # no rules file = no restrictions
    except requests.RequestException:
        rules.parse([])
    return rules


def page_text(response):
    """Get the readable text of a page, without code or menus' styling."""
    soup = BeautifulSoup(response.text[:2_000_000], "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())  # collapse spaces/line breaks
    return soup, text


# Pages that often show a company's address, most useful first.
# Privacy and terms pages usually carry the legal address.
ADDRESS_PAGE_WORDS = ["contact", "location", "about", "privacy", "terms", "legal"]


def address_page_links(soup, page_url, limit):
    """Find links that look like Contact, About, Privacy or Terms pages."""
    site = urlparse(page_url).netloc
    found = {}  # url -> how useful (0 = most useful)
    for link in soup.find_all("a", href=True):
        label = (link.get_text(" ") + " " + link["href"]).lower()
        ranks = [i for i, word in enumerate(ADDRESS_PAGE_WORDS) if word in label]
        if not ranks:
            continue
        url = urljoin(page_url, link["href"]).split("#")[0]
        # Stay on the same website, and don't repeat pages.
        if urlparse(url).netloc == site and url != page_url:
            found[url] = min(ranks[0], found.get(url, 99))

    # Most useful kind first; at most one page of each kind.
    chosen, kinds_used = [], set()
    for url, rank in sorted(found.items(), key=lambda item: item[1]):
        if rank not in kinds_used:
            chosen.append(url)
            kinds_used.add(rank)
    return chosen[:limit]


# ----------------------------------------------------------------------
# PART 3: VERIFY
# ----------------------------------------------------------------------

def snippet(text, start, end, margin=100):
    """Cut out the text around a match, so a person can read the evidence."""
    return "..." + text[max(0, start - margin): end + margin].strip() + "..."


def find_name(text, name):
    """Is the company name on the page? Returns True/False."""
    # Compare simplified versions: lowercase, punctuation turned into spaces.
    simple = re.sub(r"[^a-z0-9]+", " ", text.lower().replace("&", " and "))
    simple = " " + " ".join(simple.split()) + " "
    return f" {name} " in simple or f" {name.replace(' ', '')} " in simple


def find_location(text, company, missing):
    """
    Is the company's location on the page?
    Returns (kind of match, the text around it) or (None, None).
    Checks from strongest evidence to weakest.
    """
    city, state = company["city"], company["state"]
    zip5 = company.get("zip_code", "")[:5]
    state_full = STATE_NAMES.get(state, state)

    # Strongest: "Ogden, UT" or "Ogden, Utah" written together.
    if city != missing and state != missing:
        pattern = (
            rf"\b{re.escape(city)}\b[\s,]+"
            rf"(?:{re.escape(state)}\b|{re.escape(state_full)}\b)"
        )
        match = re.search(pattern, text, flags=re.I)
        if match:
            return "city + state together", snippet(text, match.start(), match.end())

    # Next: the zip code.
    if zip5.isdigit() and len(zip5) == 5:
        match = re.search(rf"\b{zip5}\b", text)
        if match:
            return "zip code", snippet(text, match.start(), match.end())

    return None, None


def check_site(domain, name, company, settings):
    """
    Visit one guessed website and decide whether it is really this company.
    Returns a dictionary with the result and the evidence.
    """
    missing = settings["missing_value_text"]
    wait = settings["politeness"]["seconds_between_requests"]
    result = {"website": missing, "note": ""}

    # Rule 1: obey the site's own rules for programs.
    rules = read_robots("https://" + domain, settings)
    if not rules.can_fetch(USER_AGENT, "https://" + domain + "/"):
        result["note"] = f"{domain}: site asks programs not to visit"
        return result

    time.sleep(wait)
    home, reason = get_page("https://" + domain, settings)
    if home is None:
        result["note"] = f"{domain}: could not be read - {reason}"
        return result

    # The address may redirect somewhere else. Never use a blocked site.
    final_site = urlparse(home.url).netloc.lower().removeprefix("www.")
    if any(b in final_site for b in settings["politeness"]["blocked_sites"]):
        result["note"] = f"{domain}: redirects to a blocked site"
        return result

    soup, text = page_text(home)
    pages = [(home.url, text)]
    name_seen = find_name(text, name)

    # Check the home page first; only open more pages if we need to.
    to_visit = address_page_links(soup, home.url, settings["find_website"]["extra_pages_per_site"])
    while True:
        url, text = pages[-1]
        name_seen = name_seen or find_name(text, name)
        kind, evidence = find_location(text, company, missing)
        if kind and name_seen:
            return {
                "website": final_site,
                "website_match": f"name + {kind}",
                "website_evidence": evidence,
                "website_evidence_page": url,
                "note": "",
            }
        # Not proven yet. Try the next Contact/About page, if allowed.
        next_page = None
        while to_visit and next_page is None:
            candidate = to_visit.pop(0)
            if rules.can_fetch(USER_AGENT, candidate):
                time.sleep(wait)
                next_page, _ = get_page(candidate, settings)
        if next_page is None:
            break
        pages.append((next_page.url, page_text(next_page)[1]))

    what = "name seen, location not" if name_seen else "company name not on the site"
    result["note"] = f"{final_site}: {what}"
    return result


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def find_website(company, settings):
    """Try every guess for one company. Stop at the first that is verified."""
    notes = []
    tried_any = False
    for name in guess_names(company["company_name"], settings):
        for domain in guess_domains(name, settings):
            if not domain_exists(domain):
                continue
            tried_any = True
            result = check_site(domain, name, company, settings)
            if result["website"] != settings["missing_value_text"]:
                return result
            notes.append(result["note"])
    if not tried_any:
        notes.append("none of the guessed addresses exist")
    return {"website": settings["missing_value_text"], "note": "; ".join(notes)}


def main():
    settings = load_settings()
    missing = settings["missing_value_text"]
    folder = Path(settings["output"]["data_folder"])

    # How many companies? A number on the command line overrides settings.
    how_many = settings["find_website"]["companies_per_run"]
    if len(sys.argv) > 1:
        how_many = int(sys.argv[1])

    # Step 2's file is already sorted newest signal first.
    with open(folder / "step2_companies_clean.csv", encoding="utf-8-sig") as f:
        companies = list(csv.DictReader(f))[:how_many]

    # Companies checked in an earlier run are kept as they are and skipped,
    # so we never visit the same websites twice for no reason.
    path = folder / "step3a_websites.csv"
    done = {}
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                done[(row["company_name"], row["state"])] = row

    todo = sum(1 for c in companies if (c["company_name"], c["state"]) not in done)
    print(f"Step 3a: {len(companies)} companies, {len(companies) - todo} "
          f"already checked, {todo} to do")

    results = []
    for number, company in enumerate(companies, start=1):
        key = (company["company_name"], company["state"])
        if key in done:
            results.append(done[key])
            continue

        try:
            result = find_website(company, settings)
        except Exception as error:  # one bad site must not stop the whole run
            result = {"website": missing, "note": f"error: {error}"}

        company["website"] = result["website"]
        company["website_match"] = result.get("website_match", missing)
        company["website_evidence"] = result.get("website_evidence", missing)
        company["website_evidence_page"] = result.get("website_evidence_page", missing)
        company["website_note"] = result["note"] or missing
        results.append(company)

        print(f"  {number}/{len(companies)} {company['company_name']}: "
              f"{company['website']}  {result['note']}", flush=True)

        # Save after every company, so nothing is lost if the run is interrupted.
        # (Companies not reached yet are simply not in the file.)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results + [
                done[k] for k in done
                if k not in {(r["company_name"], r["state"]) for r in results}
            ])

    found = sum(1 for r in results if r["website"] != missing)
    print(f"\nVerified a website for {found} of {len(results)} companies "
          f"({found / len(results):.0%}).")
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
