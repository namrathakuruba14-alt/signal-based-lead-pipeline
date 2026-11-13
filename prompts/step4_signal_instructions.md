# Step 4 signal instructions

These are the instructions given to the reader. In this run the reader is
Claude working in a Claude Code session. Later the same instructions can be
sent to the Claude API by a script, with no other change to the pipeline.

## Your job

For each company you are given "candidate lines": lines from its saved
website pages that mention a big retailer or contain a signal phrase. Each
candidate is shown with the line before and after it, because a date is
often on a neighbouring line.

Decide whether the company shows each of three signals. Most candidate
lines are NOT signals. The word "international" in a slogan is not proof
of exporting. Be strict.

## Rules

1. **Every signal needs a quote** copied word for word from the candidate
   text. A script checks it against the saved page and deletes the signal
   if the quote is not found exactly.
2. **If the pages do not show the signal, leave it blank.** Do not use
   anything you know about the company from elsewhere.
3. **Dates.** If the signal is dated, give the date as YYYY-MM-DD in
   `signal_date` and copy the text that shows the date into `date_quote`
   (for example "September 14, 2026"). If only a month and year are given,
   use the first day of the month. If there is no date, leave both blank.
   A copyright year in a footer is not a date for a signal.
4. Where you can, pick a quote that does not contain a person's name.

## The three signals

### big_retailer
The page says the company's own products are sold in, or made for, a named
big US retailer (the list is in settings.yaml), or says in general terms
that its products are sold through major retailers or grocery chains.
- `found`: the retailer names, or "major retailers (not named)".
- Does NOT count: the company is itself the retailer; a retailer is
  mentioned for another reason (a recall notice saying where a product was
  sold does count, a job advert mentioning "Target audience" does not).

### export
The page says the company sells, ships or distributes its products
**outside the United States**.
- `found`: where to, in a few words (for example "more than 60 countries").
- Does NOT count: importing goods INTO the US; sourcing ingredients from
  abroad; being owned by a foreign parent; vague words like "world-class".

### new_product
The page announces a specific new product, flavour or product line.
- `found`: what was launched, in a few words.
- Does NOT count: a generic "new arrivals" menu item; seasonal items that
  return every year unless described as new; a sale or discount.

## Answer format

One JSON object per company. Leave a signal's fields empty if not found.

```json
{
  "website": "example.com",
  "big_retailer": {"found": "", "quote": "", "signal_date": "", "date_quote": ""},
  "export": {"found": "", "quote": "", "signal_date": "", "date_quote": ""},
  "new_product": {"found": "", "quote": "", "signal_date": "", "date_quote": ""}
}
```

A batch is a JSON list of these objects, saved as
`data/step4_answers/batch_XX.json`.

## How strength is decided (by the script, not by you)

- **strong**: the quote passed, a date was given, the date text was found on
  the page, and the date is within the last 12 months.
- **weak**: the quote passed but there is no date, or the date is older.
- **blank**: no signal, or the quote failed the check.
