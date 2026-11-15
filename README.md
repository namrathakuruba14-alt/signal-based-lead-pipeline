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
| 5 | Judge | Fit / maybe / no by fixed rules in code, with the rule and the exact sentence behind each verdict | So every decision can be checked by a person, and re-run by anyone | Done |
| 6 | Decision maker finder | Find a named QA, operations or owner contact on the company's own website, with the quote that proves it | A lead is only useful with someone to contact | Done |
| 7 | Score + CSV | Score each company by fixed rules and save a ranked CSV with reasons and evidence | So the best leads are at the top, and each score can be explained | Done |

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

In this test market every company has a recall, because the list came from the FDA. So here the rule comes down to "retailer or export, and no certification found". A first count gives 21 companies, 12 of which say they manufacture themselves. The final list is produced in Step 7 (Score + CSV).

## Step 5 in detail: the verdict

**No AI reading in this step.** Step 5 is fixed rules in code (`step5_judge.py`). It only looks at columns filled in by earlier steps, so anyone who runs it gets the same answer. The judgement that needed reading was done in Steps 3b and 4, where every fact was tied to a quote. Step 5 just applies the rules to those facts.

**The rules, in order. The first one that applies decides.**

| Verdict | Rule |
|---------|------|
| **No** | 1. It is a distributor |
| **No** | 2. It is a retailer |
| **No** | 3. It is not a food maker (packaging, supplements, seeds; keyword list in the settings file) |
| **No** | 4. Its product has been discontinued |
| **No** | 5. It states an employee count outside 11–200 |
| **Maybe** | 6. The website does not say who makes the product |
| **Maybe** | 7. The "likely too big" flag is on |
| **Maybe** | 8. Size is unknown |
| **Fit** | 9. Manufactures itself, is a food maker, no stated size outside 11–200, no too-big flag, and at least one signal (the recall counts) |

**Every verdict carries the rule that decided it and the quote behind it.** For a fit, that is the sentence showing it makes the food itself plus the FDA's recall reason.

**Result for the 95 companies with a verified website:**

| Verdict | Companies | Decided by |
|---------|-----------|------------|
| Fit | 4 | rule 9 |
| Maybe | 49 | not stated who makes it: 9; likely too big: 7; size unknown: 33 |
| No | 36 | distributor: 18; retailer: 2; not a food maker: 11; discontinued: 1; employee count out of range: 4 |
| Not read | 6 | website could not be reached |

**What "size unknown" means.** Step 3b collected founding years as size clues, but "since 1947" says nothing about how big a company is today. So a founding year does not count as a size fact: size is known only when the website gives an employee count, a plant count or a facility size. (With founding years counted, 25 companies would be a fit, including some very large ones. This is one switch in the settings file, `founding_year_alone_counts_as_size`, now off.)

**The honest picture:** only 4 companies state enough to be a clean fit. Small manufacturers rarely publish their size, and the usual place to find it is off limits to this pipeline. So the biggest group is "manufactures itself, has a recall, size unknown".

**Who goes forward to Step 6 and the final CSV: 37 companies.**

- The 4 fits.
- The 33 maybes whose only reason is unknown size. In the final CSV they are labelled **"maybe: confirm headcount before outreach"**, so nobody contacts them assuming they are the right size.

The 16 other maybes (likely too big, or the website does not say who makes the product) do not go forward.

## Step 6 in detail: who to contact

**Goal:** for each company going forward, name the person to contact, in this order of preference: QA or food safety manager, then head of operations, then owner or founder. An owner or founder is a valid contact at a small company.

**Which companies:** the 4 fits, plus the "size unknown" maybes that also match the top-priority rule, minus very large companies removed by hand (listed in the settings file). That was 11 companies when Step 6 ran, and **10** after one more large company was removed.

**Where it looks:**

1. The pages already saved in Step 3b, About first.
2. One Team or Leadership page, only if the website links to one and it is not saved already. This meant at most two polite visits per site. Two of the 11 sites had such a page.
3. Nowhere else. No LinkedIn, no people-search sites, no guessing from email formats.

**Same design as Steps 3b and 4:** a script pulls out lines containing a job-title word, the reader (Claude in-session) picks out named people following `prompts/step6_contact_instructions.md`, and a script checks every contact.

**The check is stricter here, because a wrong name is worse than no name.** A contact is kept only if all four hold:

- the quote is on the saved page, word for word
- the person's name is inside the quote
- the person's title is inside the quote
- the title contains a word for the kind of role claimed

Otherwise the company shows "not found". **No name or role is ever guessed.**

**Result: a contact was found for 3 of the 10 companies.** 5 contacts checked, 0 deleted.

| Kind of contact | Companies |
|-----------------|-----------|
| QA / food safety | 0 |
| Operations | 2 |
| Owner / founder | 1 |
| Not found | 7 |

**What this shows, honestly:** small food manufacturers mostly do not name their staff on their websites, and none of these 11 named a QA or food safety person. Two more sites mention a founder by first name or in a story, but never give a title next to the name, so the rules correctly leave them as "not found". For a real campaign the missing contacts would come from a phone call or a paid contact database, which is outside what this free pipeline does.

**Privacy:** real names are personal data. They are saved only in `data/step6_contacts.csv`, which is never uploaded. The repo has `sample_output/step6_contacts_sample.csv`, the same rows with every name replaced by "[name redacted]".

## Step 7 in detail: score and final list

**No AI reading in this step.** `step7_score.py` adds up facts that earlier steps already tied to a quote, and writes the reasons next to the score so nobody has to trust the number on its own.

**How the score is built** (all points are in the settings file):

| Fact | Points |
|------|--------|
| Recall | 3 |
| Sells to a big retailer | 3 |
| Exports | 2 |
| New product launch | 1 |
| Open QA or food safety job | 1 |
| No audited certification found | 2 |
| Verdict is "fit" (so fit ranks above maybe) | 3 |
| A named contact was found | 1 |

A weak signal counts in full. Signal strength is not used, because almost no signal on a website carries a date.

**Ranking:** highest score first. Ties: top-priority companies first, then fits, then alphabetical.

**Which companies:** the 10 that came out of Step 6 (4 fits and 6 "size unknown" maybes that match the top-priority rule, after four very large companies were removed by hand).

**The final file has, for every company:** rank, verdict, label, top-priority flag, score, the reasons for the score, and the evidence quotes for each fact (makes it itself, recall, retailer, export, new product, certification, contact).

- `data/step7_final_leads.csv` has the real contact names and is never uploaded.
- `sample_output/final_leads_sample.csv` is the same list with every name replaced by "[name redacted]".

**Final ranked list:**

| Rank | Company | Score | Label | Top priority | Contact |
|------|---------|-------|-------|--------------|---------|
| 1 | Nats Nuts LLC | 11 | maybe: confirm headcount before outreach | yes | operations |
| 2 | Straus Family Creamery | 9 | maybe: confirm headcount before outreach | yes | not found |
| 3 | Rose and Shore, Inc. | 9 | fit | no | not found |
| 4 | Deano's Pasta | 8 | maybe: confirm headcount before outreach | yes | not found |
| 5 | Pink House Alchemy, LLC | 8 | maybe: confirm headcount before outreach | yes | operations |
| 6 | Stuffed Foods LLC | 8 | maybe: confirm headcount before outreach | yes | not found |
| 7 | Wondermade LLC | 8 | maybe: confirm headcount before outreach | yes | owner / founder |
| 8 | Boichik Bagels, Inc. | 8 | fit | no | not found |
| 9 | Everything Sprouts, LLC | 8 | fit | no | not found |
| 10 | Produce Innovations | 6 | fit | no | not found |

**How this compares with the goal of 50 companies.** The pipeline started with 449 companies and ends with 10. Each step's loss is counted and explained above; the two largest are the free website finder (95 of 449) and the fact that small manufacturers rarely publish their size or staff. Nothing was invented to fill the gap. The fixes are known and named: a search service for websites, a longer recall look-back, and a contact database or a phone call for headcount and names.

## A bug found and fixed: certification names written in full

While reading for Step 6, one company's About page said it had held "British Retail Consortium Global Standard for Food Safety certification since 2010". The keyword list only had the abbreviation "BRC", so the certification was missed, and Rose and Shore was wrongly marked top priority (which requires *no* certification).

**The fix:** the full names were added to the keyword list alongside the abbreviations (British Retail Consortium, Safe Quality Food, Global Food Safety Initiative, Food Safety System Certification), and the certification and top-priority flags were re-run for every company. Rose and Shore is now correctly shown as certified and is no longer top priority. Two other companies gained a second match for a certification they were already credited with.

**What it shows:** a keyword list only finds the spellings someone thought of. The bug was caught because a person-style read happened to pass over the sentence. This is the main weakness of the keyword parts of the pipeline, and the reason every flag keeps its evidence next to it.

## Rules that apply across Steps 5 and 7

These live in the settings file, so they can be changed per market.

- **Must manufacture.** The FDA list is "companies that had a recall", not "manufacturers". It includes grocery chains, restaurants and distributors. A "fit" requires that **the company manufactures or processes food itself**, backed by a sentence from its website.
- **Unknown size does not rule a company out.** Only a *stated* size outside 11–200 employees does. Most small companies don't publish a headcount, so "unknown" is normal. Example: size unknown + manufactures itself + has a recall = "maybe".
- **QA job openings get a low score weight** (1 point, against 3 for a recall). See the limitation below.
- **"Likely too big" flag.** Some companies never state a headcount but give other clues: two or more plants, or one facility of 100,000 square feet or more. These are flagged for a person to review. **The flag never excludes a company**, because a plant count is a clue, not a headcount. The thresholds are in the settings file.
- **"Top priority" rule.** Explained in the section above.
- **Scoring does not depend on strong signals.** Step 4 showed almost no signal can be dated, so a weak signal counts in full.

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
python step5_judge.py
python step6_collect_team.py
python step6_find_candidates.py
# (the reader fills data/step6_answers/ following prompts/step6_contact_instructions.md)
python step6_fill_contacts.py
python step7_score.py
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
| `step5_judge.py` | Step 5: fit / maybe / no by fixed rules, with the rule and quote for each |
| `step6_collect_team.py` | Step 6 part 1: picks the companies and saves a linked Team page if there is one |
| `step6_find_candidates.py` | Step 6 part 2: pulls out lines that might name a decision maker |
| `step6_fill_contacts.py` | Step 6 part 3: checks every contact, picks the best, writes the redacted sample |
| `step7_score.py` | Step 7: scores, ranks and writes the final CSV plus the redacted sample |
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
- **Step 5:** Judged all companies by fixed rules in code: 4 fit, 49 maybe, 36 no, 6 not read (a founding year does not count as a size fact). 37 companies go forward: the 4 fits plus 33 maybes whose only gap is unknown size. Renumbered the plan: 5 Judge, 6 Decision maker finder, 7 Score + CSV.
- **Step 6:** Looked for a named contact at 11 companies using only their own websites. Found one for 3 (2 operations, 1 founder), each with a checked quote. Real names stay in `data/`; the repo has a redacted sample.
- **Certification fix:** Added full certification names to the keyword list after one was missed; re-ran the flags. One company lost its wrong top-priority mark.
- **Step 7:** Scored and ranked the final 10 companies by fixed rules, with reasons and evidence for each. Final list in `data/`, redacted sample in `sample_output/`.
- **Swappable source:** Moved the FDA code into a plug-in so a new market can use a different source by changing one line in the settings file.
