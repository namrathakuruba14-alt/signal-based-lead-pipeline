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
| 3 | Enrich | 3a: find and verify each company's website. 3b: read the website: what they make, whether they make it themselves, size clues, food safety terms, QA jobs | To judge fit we need to know what the company actually does | Done |
| 4 | Signal | Look for big-retailer, export and new-product signals on the saved pages, each graded strong or weak | Signals tell us who needs help now | Done |
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

**Being polite:** the script identifies itself honestly, obeys each site's robots.txt (the site's rules for programs), waits 5 seconds between visits to the same site, reads at most 5 pages per site, and never re-visits a company it has already checked.

**Why not a search engine?** Scraping Google breaks its rules, and the search services built for programs now need a paid plan or a card on file. This method is free and needs no account. The cost is that it misses companies whose web address doesn't match their name.

**Result on the newest 100 companies: 20 verified websites (20%).** I read all 20 by hand and each one is the right company. The other 80 are "not found", for these reasons:

| Reason | Companies |
|--------|-----------|
| None of the guessed addresses exist (the web address doesn't match the legal name) | 39 |
| The address exists but the page could not be read (often sites that turn away automated visitors) | 18 |
| Probably the right site, but no address shown on the pages checked | 16 |
| The address belongs to a different company | 7 |

**What this shows:** the verification works (no wrong websites got through), but guessing alone finds too few. The biggest gap is legal names that differ from the brand's web address, which only a search can solve.

**Two free improvements made after that first run:**

- It now also checks privacy and terms pages, which often carry the legal address.
- When a page can't be read it records the exact reason (for example "site refused automated visitors"). Blocks are recorded and respected, never worked around.

The rule stayed strict: **no location on the page means "not found"**, even when the site is probably right.

**Final result across all 449 companies: 95 verified websites (21%).** Ten of the later finds came from a privacy or terms page. I read the evidence for all 95 and found no wrong match.

Why the rest of the later 349 were "not found" (a company can have more than one reason, so these overlap slightly):

| Reason | Companies |
|--------|-----------|
| None of the guessed addresses exist | 104 |
| Company name on the site, but no matching location shown | 65 |
| The address belongs to a different company | 41 |
| No working website at the address | 22 |
| Security certificate problem | 20 |
| Site refused automated visitors (respected, not worked around) | 15 |
| Site asked programs not to visit (robots.txt) | 2 |
| Other errors | 12 |

## Known limitation and next improvement

**Limitation:** guessing only works when a company's web address looks like its legal name. It can't find "G L Mezzetta Inc" at mezzetta.com, or a company that trades under a brand name. This was the largest group of misses (143 of the 449 companies). The pipeline therefore continues with the 95 companies that have a verified website, which is fewer than needed to be sure of 50 fits.

**Next improvement:** add a search service as a second way to find candidate addresses, feeding into the *same* verification. The verification wouldn't change, so accuracy would stay the same while coverage goes up. It isn't built because the search services designed for programs currently need a paid plan or a card on file, and this project is free-only for now.

## Step 3b in detail: reading the websites

**Goal:** for each company with a verified website, record what it makes, whether it makes the food itself, any stated size facts, food safety terms and certifications, and open QA or food safety jobs. Every fact comes with the exact sentence it is based on.

**It runs in three parts:**

1. **Collect** (`step3b_collect_pages.py`). Saves the text of the Home, About, Products, Careers and News pages (those that exist) into `data/pages/`. Later steps read these saved copies, so each website is visited once. Result: 302 pages from 89 of the 95 websites. Six sites could not be reached and are marked "not read".
2. **Read** (`step3b_prepare_reading.py` + `prompts/step3b_read_instructions.md`). The saved text is bundled into batches of 20 companies. A reader follows the instruction file and writes one answer per company, each with a quote.
3. **Check and fill** (`step3b_fill_columns.py`). A script checks every quote against the saved page. **If the quote is not there word for word, the answer is deleted.** It also does the food safety keyword match (plain matching from the list in the settings file) and writes `data/step3b_enriched.csv`.

**Who did the reading in this run: Claude, in a Claude Code session.** This was a deliberate choice: no extra cost and no new account. The trade-off is that this one part cannot be re-run by code alone. The quote check is what keeps it honest: it is done by a script, and it would catch an invented or misquoted fact whoever did the reading.

**Result of the quote check: 261 quotes checked, 0 failed.**

| What was found (95 companies) | Companies |
|-------------------------------|-----------|
| Manufactures itself | 53 |
| Distributor | 18 |
| Retailer | 2 |
| Not stated clearly on the pages, left blank | 16 |
| Website could not be read | 6 |
| States an employee count | 7 |
| No size fact of any kind ("unknown") | 36 |
| Lists an open QA or food safety job | 4 |
| Mentions at least one food safety term | 42 |

**Rules the reader follows:** use only the page text; leave blank if not stated; never estimate size; label "manufactures itself" only when the page says so. Several companies that probably do manufacture are blank for this reason, and the Judge step treats blank as "not proven", not as "no".

**Next step, Option A: let a script do the reading through the Claude API.** The same instruction file and the same batches are sent to the API, and the answers are saved in the same format. Nothing else changes, including the quote check. Estimated cost for this run's roughly 500,000 characters of page text: **under $0.10 with the smallest model (Haiku 5.5), or under $1 with the mid model (Sonnet 5.5)**, using list prices dated 3 November 2026. It needs an Anthropic API account with a card on file, and the key would go in `.env`. Not built yet, by choice.

## Step 4 in detail: looking for signals

The recall signal came with the source list, and QA job openings were captured in Step 3b. Step 4 looks for the other three on the pages already saved (no website is visited again):

1. **Big US retailers.** The company's products are sold in, or made for, a big retailer. Big retailers usually require suppliers to hold a food safety certification.
2. **Exporting.** The company sells outside the United States. (Importing into the US does not count.)
3. **New product launches.**

**Same design as Step 3b, with one extra part at the front:**

1. **Find candidates** (`step4_find_candidates.py`). A script pulls out every line that names a retailer from the list in the settings file, or contains a signal phrase such as "available at", "export" or "launch". This cut the reading from about 500,000 characters to about 95,000: 246 candidate lines for 89 companies.
2. **Read** (`prompts/step4_signal_instructions.md`). The reader decides which candidates are real signals. Most are not: "international" in a slogan is not exporting, and "Sprouts" is usually a vegetable, not the grocery chain.
3. **Check and grade** (`step4_fill_signals.py`). Every quote is checked word for word against the saved page, exactly as in Step 3b. The script, not the reader, then sets the strength:
   - **strong**: dated within the last 12 months, and the text showing that date was also found on the page
   - **weak**: a real signal with no date, or an older date
   - **blank**: not mentioned

**Read in-session by Claude**, in 5 batches, same as Step 3b. The API option described above applies here too, and would cost even less because the candidate text is small.

**Result: 49 checks, 0 failed. 35 of 89 companies show at least one signal.**

| Signal | Strong | Weak |
|--------|--------|------|
| Big retailer | 0 | 11 |
| Export | 0 | 16 |
| New product | 2 | 14 |

**What this shows, honestly:** websites rarely date these statements. "We sell to Whole Foods" sits on an About page with no date, so it can only be weak. Only press-release style news items produce strong signals. The recall, which has an exact date from the FDA, remains the one reliably dated signal in this pipeline.

**Known limits:**

- A signal worded without any listed retailer name or phrase is missed. The lists are in the settings file and can be widened.
- A retailer shown only as a logo image cannot be read as text.
- "Sells to retailers" in general terms was not counted unless the page said major or large retailers, club stores or mass merchandisers.

## Named scoring rule: "top priority"

**The rule:** a company is top priority when it has **a recall**, AND **sells to a big retailer or exports**, AND **no food safety certification was found** on its website.

**The reasoning:**

- A **recall** is proof of a real food safety problem, with a date.
- **Big retailers and export markets** are the customers who demand audited certification. A company selling to them is under pressure to have one, and has the most to lose if it can't show one.
- **No certification found** means the gap is still open. A company that already displays SQF or BRC has probably solved this.

Together these describe a company with a proven problem, demanding customers and no visible answer, which is exactly who the client's food safety partners can help.

**Two cautions built into how it is used:**

- "No certification found" means not found on the pages we saved. A company may hold one and not mention it. So the rule ranks a company for attention; it does not state a fact about them.
- Only audited schemes count as a certification here (SQF, BRC/BRCGS, FSSC 22000, ISO 22000, GFSI). Kosher, Organic, HACCP and GMP do not, because they are diet labels or internal programmes rather than what retailers ask for. The list is in the settings file.

In this test market every company has a recall, because the list came from the FDA. So here the rule comes down to "retailer or export, and no certification found". A first count gives 21 companies, 12 of which say they manufacture themselves. The final list is produced in the scoring step, after the Judge step.

## Rules already decided for Step 5 (Judge) and Step 6 (Score)

These live in the settings file, so they can be changed per market.

- **Must manufacture.** The FDA list is "companies that had a recall", not "manufacturers". It includes grocery chains, restaurants and distributors. A "fit" requires that **the company manufactures or processes food itself**, backed by a sentence from its website.
- **Unknown size does not rule a company out.** Only a *stated* size outside 11–200 employees does. Most small companies don't publish a headcount, so "unknown" is normal. Example: size unknown + manufactures itself + has a recall = "maybe".
- **QA job openings get a low score weight** (1 point, against 3 for a recall). See the limitation below.
- **"Likely too big" flag.** Some companies never state a headcount but give other clues: two or more plants, or one facility of 100,000 square feet or more. These are flagged for a person to review. **The flag never excludes a company**, because a plant count is a clue, not a headcount. The thresholds are in the settings file.
- **"Top priority" rule.** Explained in the section above.

## Known limitation: job openings are mostly invisible

Most company careers pages don't list jobs. They link to an outside job board (Indeed, ADP, a recruiting platform). This pipeline stays on the company's own website, so it writes down that link but does not visit it, and it never touches LinkedIn.

The effect: "no QA job found" usually means "we couldn't see the job list", not "they aren't hiring". A signal that can rarely be seen shouldn't decide the ranking, so it carries little weight in the score.

**Next improvement:** read public job boards that allow it (many publish a job feed meant for programs), feeding into the same quote check.

## How to run it

```
pip install -r requirements.txt
python step1_source.py
python step2_clean.py
python step3a_find_websites.py
python step3b_collect_pages.py
python step3b_prepare_reading.py
# (the reader fills data/step3b_answers/ following prompts/step3b_read_instructions.md)
python step3b_fill_columns.py
python step4_find_candidates.py
# (the reader fills data/step4_answers/ following prompts/step4_signal_instructions.md)
python step4_fill_signals.py
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
| `step3b_collect_pages.py` | Step 3b part 1: saves page text from each verified website |
| `step3b_prepare_reading.py` | Step 3b part 2: bundles saved pages into reading batches |
| `step3b_fill_columns.py` | Step 3b part 3: quote check, keyword match, final columns |
| `step4_find_candidates.py` | Step 4 part 1: pulls out lines that might be a signal |
| `step4_fill_signals.py` | Step 4 part 2: quote check and strong/weak grading |
| `prompts/` | The instructions the reader (Claude in-session now, the API later) follows |
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
- **Step 3a, full run:** Added privacy/terms pages and exact failure reasons, then ran all 449 companies: 95 verified websites (21%).
- **Step 3b:** Saved 302 pages from 89 websites, read them in 5 batches in-session, and quote-checked every answer: 261 quotes, 0 failed. 53 companies say they manufacture themselves.
- **Step 4:** Searched the saved pages for retailer, export and new-product signals. 35 of 89 companies show at least one; 49 checks, 0 failed. Added the "top priority" rule and the "likely too big" flag to the settings file.
- **Swappable source:** Moved the FDA code into a plug-in so a new market can use a different source by changing one line in the settings file.
