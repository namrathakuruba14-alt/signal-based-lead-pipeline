# Step 3b reading instructions

These are the instructions given to the reader. In this run the reader is
Claude working in a Claude Code session. Later the same instructions can be
sent to the Claude API by a script, with no other change to the pipeline.

## Your job

You are given the saved text of a few pages from one company's website
(home, about, products, careers). Fill in the fields below **using only that
text**.

## Rules

1. **Every answer needs a quote.** The quote must be copied **word for word**
   from the page text: same words, same order, same spelling and punctuation.
   Do not fix typos, join separate lines, or shorten with "...".
   A script checks every quote against the saved page. If the quote is not
   found exactly, the answer is deleted.
2. **If the page does not state it, leave it blank.** Do not guess, infer
   from the company name, or use anything you know from elsewhere.
3. **Never estimate size.** Only record a size clue if the page states a
   number or fact. No "probably small" or "looks like a large company".
4. Keep each quote short: one sentence or one line is enough.
5. Ignore recall notices when deciding what the company makes or who makes
   it, unless nothing else on the site says it.

## Fields

### what_they_make
- `answer`: a few plain words saying what products the company makes or
  sells (for example "fresh pasta and sauces").
- `quote`: the line that says so.

### who_makes_it
Does the company make the food itself?
- `answer`: exactly one of
  - `manufactures itself` - the page says they make, produce, bake, roast,
    process or pack the product in their own facility
  - `co-packed` - the page says another company makes it for them
  - `distributor` - they import, distribute or wholesale products made by others
  - `retailer` - they are a shop, grocery chain, restaurant or cafe
  - blank - the page does not make it clear
- `quote`: the line that shows it.

If a company both makes food and runs shops, choose `manufactures itself`
when the page clearly says they make it.

### size_clues
A list. One entry for each stated fact about size. Leave the list empty if
there are none.
- `clue`: one of `employees`, `facility size`, `plant count`, `years`
  (`years` = founding year or years in business)
- `value`: the stated fact (for example "150 employees", "110,000 square feet",
  "3 plants", "founded 1991")
- `quote`: the line that states it.

### open_qa_jobs
A list. One entry for each **currently advertised** job in quality
assurance, quality control, food safety, HACCP, SQF, sanitation or
regulatory compliance. Leave the list empty if there are none. A general
"we're hiring" message with no such role does not count.
- `title`: the job title as written
- `quote`: the line showing the job.

## Answer format

One JSON object per company:

```json
{
  "website": "example.com",
  "what_they_make": {"answer": "", "quote": ""},
  "who_makes_it": {"answer": "", "quote": ""},
  "size_clues": [{"clue": "", "value": "", "quote": ""}],
  "open_qa_jobs": [{"title": "", "quote": ""}]
}
```

A batch is a JSON list of these objects, saved as
`data/step3b_answers/batch_XX.json`.
