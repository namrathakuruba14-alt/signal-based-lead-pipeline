# Signal-Based Lead Pipeline

A small, reusable tool that builds a list of companies worth contacting **right now** — not just companies that match a profile, but companies showing a recent, public sign ("signal") that they need what you sell.

It works for any market. Everything about the target market lives in one settings file, so pointing it at a new market means editing that file, not the code.

## The idea in one paragraph

Most lead lists answer "who *could* buy?" This pipeline also answers "who has a reason to buy *now*?" It finds companies, reads their websites, looks for signals such as hiring or recalls, and then judges each company as **fit / maybe / no**. Every judgement comes with the exact sentence it was based on, so a human can check it.

## The steps

| # | Step | What it does | Why | Status |
|---|------|--------------|-----|--------|
| 0 | Setup | Version history (git), settings file, safety rules | So work is saved, reusable and safe to publish | Done |
| 1 | Source | Pull recent food recalls from the FDA's free public database | We need a starting list, and a recall is itself a signal | Done |
| 2 | Clean | Merge repeated rows into one row per company. Pass 1 by name (done), pass 2 by website domain (after Step 3) | The same company appears many times, sometimes under slightly different names | Pass 1 done |
| 3 | Enrich | Visit each website: what they do, who they sell to, size if available | To judge fit we need to know what the company actually does | Not started |
| 4 | Signal | Look for the signals listed in the settings file | Signals tell us who needs help now | Not started |
| 5 | Judge | Fit / maybe / no, with the exact sentence behind it | So every decision can be checked by a person | Not started |
| 6 | Score & output | Score each company and save to a CSV (later a Google Sheet) | So the best leads are at the top | Not started |
| 7 | Opener (stretch) | Write a first line for each "fit" company based on its signal | Makes outreach specific instead of generic | Not started |

## Step 1 in detail: where the list comes from

**Source:** the FDA's public recall database (openFDA). It is free, official, and needs no password or key.

**Why this source:** no free source gives company name, website and employee count together (that is what paid databases sell). So I picked the free source where every company arrives with a signal already attached. A recall is the strongest reason a food company would need testing or an audit.

**What happens when it runs:**

1. `step1_source.py` reads the settings file to see which source to use.
2. It runs that source's plug-in. For this market that is `sources/openfda_recalls.py`, which asks the FDA for 12 months of US food recalls, one page at a time, pausing between pages.
3. It saves the result to `data/step1_companies_raw.csv`.
4. It writes "not found" for anything the source left blank (for example, the FDA does not publish websites).

**The source is swappable.** Different markets need different starting lists: recalls for food manufacturers, a job board for startups. So each source is a separate plug-in file in the `sources/` folder, and the settings file names which one to use (`source` → `type`).

Every plug-in hands back rows with the same seven standard columns, so the later steps never need to know where the list came from:

| Column | Meaning |
|--------|---------|
| `company_name` | The company |
| `website` | Its website, if the source has it |
| `city`, `state` | Location |
| `signal_id` | Which signal from the settings file this row shows (here: `recall`) |
| `signal_date` | When it happened |
| `signal_evidence` | The exact text the signal is based on |

A plug-in can add extra columns of its own (the FDA one adds product, severity and so on).

**To add a new source:** create one file in `sources/` with a `fetch` function, add one line to `sources/__init__.py`, and put its name in the settings file. Nothing else changes.

**Known limits, handled in later steps:**

- One company can appear many times (one row per recalled product). Step 2 fixes this.
- Not every company is a manufacturer. Grocery chains, distributors and supplement sellers are on the list too. Step 5 filters them.
- There is no website or company size yet. Step 3 looks for those.
- The list leans towards companies that had a recall. The other signals are added as extra evidence in Step 4.

## Step 2 in detail: one row per company

**The problem:** Step 1 gives one row per signal. A company with 20 recalled products appears 20 times.

**Why two passes:** the plan was to remove duplicates by website domain, but the source has no websites. Finding a website is the slow part, so it makes no sense to do it 1,276 times for about 450 companies. So:

- **Pass 1 (done): merge by company name.** Two rows are the same company when their names match after ignoring capitals, punctuation and endings like "Inc" or "LLC", *and* they are in the same state.
- **Pass 2 (after Step 3): merge by website domain.** This catches what names can't, such as one company filing under two legal names or from plants in two states.

**What each company keeps:** the date and exact evidence text of its most recent signal, a count of all its signals, and every spelling that was merged (so each merge can be checked by eye).

**What it deliberately does not do:**

- **No guessing.** It never decides that two similar-looking names are "probably" the same. A wrong merge hides a real lead and is hard to notice.
- **No filtering.** Grocery chains and other non-manufacturers stay in. Removing them is a judgement, and judgements belong in Step 5 where the reason is written down.

**Works for any market:** it only uses the standard columns, and the list of name endings to ignore lives in the settings file (add "Ltd" or "GmbH" for another country).

**Result:** 1,276 rows in, 449 companies out. Saved to `data/step2_companies_clean.csv`.

## Step 3a in detail: finding websites without a paid tool

**The problem:** the list has names and locations but no websites, and Step 3 needs a website to read.

**The method: guess, then verify.**

1. **Guess** likely addresses from the name: "Honeyville, Inc" → `honeyville.com`. It also tries the name without a generic last word ("Palmetto Gourmet Foods" → `palmettogourmet.com`) and both halves of a "doing business as" name.
2. **Check the address exists** using the internet's address book. This doesn't visit the site, so wrong guesses bother nobody.
3. **Verify** by reading the site. The guess is accepted only if the site shows the company's **name** and its **location** (city and state written together, or the zip code). It looks at the home page first and opens up to two Contact/About pages only if needed.
4. **Save the evidence:** the exact text that matched and the page it was on.

If nothing passes, the website is "not found", with a note saying why (no such address, name not on the site, location not on the site). **A missing website is better than a wrong one.**

**Being polite:** the script identifies itself honestly, obeys each site's robots.txt (the site's rules for programs), waits 5 seconds between visits to the same site, and reads at most 3 pages per site.

**Why not a search engine?** Scraping Google breaks its rules, and the search services built for programs now need a paid plan or a card on file. This method is free and needs no account. The cost is that it misses companies whose web address doesn't match their name.

**Result on the newest 100 companies: 20 verified websites (20%).** I read all 20 by hand and each one is the right company. The other 80 are "not found", for these reasons:

| Reason | Companies |
|--------|-----------|
| None of the guessed addresses exist (the web address doesn't match the legal name) | 39 |
| The address exists but the page could not be read (often sites that turn away automated visitors) | 18 |
| Probably the right site, but no address shown on the pages checked | 16 |
| The address belongs to a different company | 7 |

**What this shows:** the verification works (no wrong websites got through), but guessing alone finds too few. The biggest gap is legal names that differ from the brand's web address, which only a search can solve.

## A note for Step 5 (Judge)

The FDA list is "companies that had a recall", not "manufacturers". It includes grocery chains, restaurants and distributors. So the settings file has a required check for a "fit": **the company manufactures or processes food itself**, backed by a sentence from its website.

## How to run it

```
pip install -r requirements.txt
python step1_source.py
python step2_clean.py
python step3a_find_websites.py
```

## First test market

The settings file is currently set up for this test:

- **Target:** US food manufacturers with 11–200 employees
- **What they need:** food testing, audits or certifications
- **Signals:** hiring QA / food safety roles, recalls, getting into big retailers, starting to export, new product launches
- **Who to contact:** QA or food safety manager, head of operations, or owner
- **Goal:** 50 companies

## What's in this folder

| File | What it is |
|------|------------|
| `settings.yaml` | The target market: who to look for, which signals, which roles. **The only file you edit to change markets.** |
| `step1_source.py` | Step 1: runs whichever source the settings file names and saves the list |
| `step2_clean.py` | Step 2: merges repeated rows into one row per company |
| `step3a_find_websites.py` | Step 3a: guesses each company's website and verifies it |
| `sources/` | One plug-in file per source. `openfda_recalls.py` is the FDA one. `__init__.py` is the list of available sources. |
| `requirements.txt` | The two free Python helpers the project needs |
| `README.md` | This explanation |
| `.gitignore` | The list of files that must never be uploaded (secrets and real data) |
| `.env.example` | A blank template showing where secret keys would go, if any are ever needed |
| `data/` | Real results. Created when the pipeline runs. Never uploaded. |
| `sample_output/` | An example of the output using made-up names. Safe to share. (Coming later.) |

## Rules this project follows

1. **Never invent facts.** If something can't be found, the output says "not found".
2. **Show the evidence.** Every judgement includes the exact sentence it was based on.
3. **No secrets in code.** Keys go in a `.env` file that is never uploaded.
4. **Protect personal data.** Real names and emails stay off GitHub. The repo only has a sample with fake names.
5. **Be polite to websites.** Slow, spaced-out visits. No LinkedIn scraping.
6. **Keep costs low.** Free sources first.

## Build log

- **Setup:** Created the project, version history, settings file and safety rules.
- **Step 1:** Pulled 12 months of US food recalls from the FDA: 1,276 recall records from about 450 company names.
- **Step 2 (pass 1):** Merged repeated rows by company name: 1,276 rows became 449 companies.
- **Step 3a:** Guess-and-verify website finder. First run on the newest 100 companies: 20 verified, 0 wrong.
- **Swappable source:** Moved the FDA code into a plug-in so a new market can use a different source by changing one line in the settings file.
