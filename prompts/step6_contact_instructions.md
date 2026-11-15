# Step 6 contact instructions

These are the instructions given to the reader. In this run the reader is
Claude working in a Claude Code session. Later the same instructions can be
sent to the Claude API by a script, with no other change to the pipeline.

## Your job

For each company you are given "candidate lines": lines from its saved
website pages that contain a job-title word (quality, operations, owner,
founder and so on), each shown with the line before and after it.

List the named people whose title puts them in one of these three kinds,
most wanted first:

1. **QA / food safety** - quality, food safety, QA, QC, compliance, regulatory
2. **operations** - operations, COO, plant manager, production manager, general manager
3. **owner / founder** - owner, founder, co-founder, president, CEO

## Rules

1. **Never guess a name or a role.** Only record a person if the page gives
   both their name and their title.
2. **Every contact needs a quote** copied word for word from the page, and
   the quote must contain **both the name and the title**. If the name and
   title are on neighbouring lines, copy both lines with a single space
   between them. A script checks the quote against the saved page and
   checks that the name and title are inside it. If any check fails, the
   contact is deleted and the company shows "not found".
3. **Use the title exactly as written.** Do not upgrade "Cheesemonger" to
   "Quality Manager".
4. **A first name alone is acceptable only if that is all the page gives.**
   Record exactly what is written.
5. Customer testimonials, authors of blog posts, and people at other
   companies are not contacts.
6. If nobody qualifies, leave the list empty. "Not found" is a correct answer.

## Answer format

One JSON object per company:

```json
{
  "website": "example.com",
  "contacts": [
    {"kind": "owner / founder", "name": "", "title": "", "quote": ""}
  ]
}
```

Saved as `data/step6_answers/batch_01.json`.

## Privacy

Real names are personal data. They stay in the `data/` folder, which is
never uploaded. The copy that goes to GitHub has every name replaced with
"[name redacted]".
