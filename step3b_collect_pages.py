"""
STEP 3b (part 1) - COLLECT PAGES
================================
What it does:
    For every company with a verified website, it saves the text of:
        Home, About, Products, Careers/Jobs and News
    (only the ones that exist) into the data/pages/ folder.

Why:
    Every later step (reading what the company does, looking for
    signals, judging fit) works from these saved copies. So each website
    is visited ONCE, and we can re-run later steps as often as we like
    without bothering anyone.

What it does NOT do:
    It does not interpret anything. It only saves text.

Being polite (same rules as Step 3a):
    - obeys robots.txt, waits between visits, respects blocks
    - at most 5 pages per site
    - stays on the company's own site. If the Careers link goes to
      another site (a job board, say), it writes down the link but does
      NOT visit it.
    - sites already collected in an earlier run are skipped

How to run it:
    python step3b_collect_pages.py        (all companies with a website)
    python step3b_collect_pages.py 3      (just the first 3, for testing)
"""

import csv
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml
from bs4 import BeautifulSoup

# Reuse the polite-visiting tools from Step 3a.
from step3a_find_websites import USER_AGENT, get_page, read_robots

# Links to files like these are not web pages, so we skip them.
NOT_PAGES = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".doc", ".docx")

INDEX_COLUMNS = ["company_name", "state", "website", "page_kind", "status", "url", "characters", "saved_file"]


def load_settings():
    """Read settings.yaml and return it as a Python dictionary."""
    with open("settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def readable_text(soup):
    """The page's readable text, one line per block, without code."""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    lines = [" ".join(line.split()) for line in soup.get_text("\n").splitlines()]
    return "\n".join(line for line in lines if line)[:200_000]


def find_page_links(soup, home_url, page_kinds, blocked_sites):
    """
    Look through the home page's links and pick ONE link for each kind
    of page (about, products, careers, news).
    Returns {kind: (url, is it on the company's own site?)}.
    """
    own_site = urlparse(home_url).netloc.lower().removeprefix("www.")
    chosen = {}
    used_urls = {home_url.rstrip("/")}

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(home_url, href).split("#")[0]
        if url.lower().endswith(NOT_PAGES) or url.rstrip("/") in used_urls:
            continue

        link_site = urlparse(url).netloc.lower().removeprefix("www.")
        if any(blocked in link_site for blocked in blocked_sites):
            continue  # never even note down links to blocked sites

        # What the visitor sees ("About Us") plus the address ("/about-us")
        label = (link.get_text(" ") + " " + urlparse(url).path).lower()

        for kind, words in page_kinds.items():
            if kind in chosen or not any(word in label for word in words):
                continue
            on_own_site = link_site == own_site
            # Only Careers links are worth noting when they leave the site.
            if on_own_site or kind == "careers":
                chosen[kind] = (url, on_own_site)
                used_urls.add(url.rstrip("/"))
            break
    return chosen


def collect_site(company, settings, pages_folder):
    """Visit one website and save its pages. Returns rows for the index."""
    wait = settings["politeness"]["seconds_between_requests"]
    website = company["website"]
    site_folder = pages_folder / website
    rows = []

    def record(kind, status, url="", text=None):
        """Add one line to the index, and save the text if we have it."""
        saved_file = ""
        if text is not None:
            site_folder.mkdir(parents=True, exist_ok=True)
            saved_file = str(site_folder / f"{kind}.txt")
            # First line of each saved file says where the text came from.
            Path(saved_file).write_text(f"SOURCE: {url}\n\n{text}", encoding="utf-8")
        rows.append({
            "company_name": company["company_name"], "state": company["state"],
            "website": website, "page_kind": kind, "status": status, "url": url,
            "characters": len(text) if text is not None else 0,
            "saved_file": saved_file,
        })

    # --- Home page ---
    rules = read_robots("https://" + website, settings)
    home_url = "https://" + website + "/"
    if not rules.can_fetch(USER_AGENT, home_url):
        record("home", "not saved: site asks programs not to visit", home_url)
        return rows

    time.sleep(wait)
    home, reason = get_page(home_url, settings)
    if home is None:
        record("home", f"not saved: {reason}", home_url)
        return rows

    soup = BeautifulSoup(home.text[:2_000_000], "html.parser")
    links = find_page_links(
        soup, home.url, settings["collect_pages"]["page_kinds"],
        settings["politeness"]["blocked_sites"],
    )
    record("home", "saved", home.url, readable_text(soup))

    # --- The other pages, one of each kind ---
    for kind in settings["collect_pages"]["page_kinds"]:
        if kind not in links:
            record(kind, "no such page found on the site")
            continue
        url, on_own_site = links[kind]
        if not on_own_site:
            record(kind, "link goes to another site - noted, not visited", url)
            continue
        if not rules.can_fetch(USER_AGENT, url):
            record(kind, "not saved: site asks programs not to visit this page", url)
            continue
        time.sleep(wait)
        page, reason = get_page(url, settings)
        if page is None:
            record(kind, f"not saved: {reason}", url)
            continue
        page_soup = BeautifulSoup(page.text[:2_000_000], "html.parser")
        record(kind, "saved", page.url, readable_text(page_soup))
    return rows


def main():
    settings = load_settings()
    missing = settings["missing_value_text"]
    folder = Path(settings["output"]["data_folder"])
    pages_folder = folder / "pages"
    index_path = folder / "step3b_pages_index.csv"

    # Only companies whose website was verified in Step 3a.
    with open(folder / "step3a_websites.csv", encoding="utf-8-sig") as f:
        companies = [c for c in csv.DictReader(f) if c["website"] != missing]
    if len(sys.argv) > 1:
        companies = companies[: int(sys.argv[1])]

    # Sites collected in an earlier run are kept and skipped.
    index = []
    if index_path.exists():
        with open(index_path, encoding="utf-8-sig") as f:
            index = list(csv.DictReader(f))
    done = {row["website"] for row in index}

    todo = [c for c in companies if c["website"] not in done]
    print(f"Step 3b: {len(companies)} websites, {len(companies) - len(todo)} "
          f"already collected, {len(todo)} to do")

    for number, company in enumerate(todo, start=1):
        try:
            rows = collect_site(company, settings, pages_folder)
        except Exception as error:  # one bad site must not stop the whole run
            rows = [{
                "company_name": company["company_name"], "state": company["state"],
                "website": company["website"], "page_kind": "home",
                "status": f"not saved: error ({error})", "url": "",
                "characters": 0, "saved_file": "",
            }]
        index.extend(rows)
        saved = [r["page_kind"] for r in rows if r["status"] == "saved"]
        print(f"  {number}/{len(todo)} {company['website']}: saved {', '.join(saved) or 'nothing'}",
              flush=True)

        # Save the index after every site, so nothing is lost if interrupted.
        with open(index_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS)
            writer.writeheader()
            writer.writerows(index)

    sites_saved = len({r["website"] for r in index if r["status"] == "saved"})
    pages_saved = sum(1 for r in index if r["status"] == "saved")
    print(f"\nSaved {pages_saved} pages from {sites_saved} websites.")
    print(f"Page text is in {pages_folder}, the list of pages in {index_path}")


if __name__ == "__main__":
    main()
