"""
SOURCE PLUG-IN: FDA food recalls (openFDA)
==========================================
Asks the FDA's free public database for recent US food recalls.
No password or key needed.

Like every source plug-in, this file has one job: a function called
fetch(settings) that returns a list of rows. Each row must have the
standard columns listed in step1_source.py. Extra columns are allowed.
"""

import time
from datetime import date, timedelta

import requests  # helper for talking to websites

# The FDA allows at most 1000 records per request, so we ask page by page.
PAGE_SIZE = 1000


def format_date(value):
    """The FDA writes dates as 20260225. Turn that into 2026-02-25."""
    text = str(value or "")
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def download_records(settings):
    """Download recall records from the FDA, one page at a time."""
    source = settings["source"]
    politeness = settings["politeness"]

    # Work out the date range, e.g. the last 365 days.
    end = date.today()
    start = end - timedelta(days=source["lookback_days"])

    # The search, written in the FDA's query language:
    # "reported between these two dates AND the company is in the United States"
    search = (
        f"report_date:[{start:%Y%m%d} TO {end:%Y%m%d}]"
        ' AND country:"United States"'
    )

    records = []
    skip = 0  # how many records we have already collected

    while len(records) < source["max_records"]:
        params = {
            "search": search,
            "sort": "report_date:desc",  # newest first
            "limit": PAGE_SIZE,
            "skip": skip,
        }
        response = requests.get(
            source["url"], params=params, timeout=politeness["timeout_seconds"]
        )

        # The FDA answers "404" when there are no (more) results.
        if response.status_code == 404:
            break
        response.raise_for_status()  # stop with a clear error on anything else

        page = response.json()["results"]
        records.extend(page)
        print(f"  downloaded {len(records)} records so far...")

        # A page that is not full means we have reached the end.
        if len(page) < PAGE_SIZE:
            break

        skip += PAGE_SIZE
        # Be polite: pause before asking for the next page.
        time.sleep(politeness["seconds_between_requests"])

    return records[: source["max_records"]]


def fetch(settings):
    """Return recalls as rows in the pipeline's standard shape."""
    rows = []
    for record in download_records(settings):
        rows.append({
            # --- Standard columns (every source provides these) ---
            "company_name": record.get("recalling_firm"),
            "website": None,  # the FDA does not publish websites
            "city": record.get("city"),
            "state": record.get("state"),
            "signal_id": "recall",  # matches the signal id in settings.yaml
            "signal_date": format_date(record.get("recall_initiation_date")),
            "signal_evidence": record.get("reason_for_recall"),
            # --- Extra columns (specific to this source) ---
            "product": record.get("product_description"),
            "severity_class": record.get("classification"),
            "recall_status": record.get("status"),
            "report_date": format_date(record.get("report_date")),
            "recall_number": record.get("recall_number"),
            "street_address": record.get("address_1"),
            "zip_code": record.get("postal_code"),
        })
    return rows
