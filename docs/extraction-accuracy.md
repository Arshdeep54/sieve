# Extraction accuracy

Workflow A reads lender pages with an LLM. The SQL filter in workflow B trusts those numbers, so one bad field silently includes or excludes thousands of users. I checked every eligibility field by hand against the live lender pages, then measured how each error changed matches for the 10k users in `data/users.csv`.

## Method

- **Ground truth:** each lender's eligibility page, read by hand on 2026-10-15.
- **Scope:** the six products that carry eligibility criteria. Each one has seven fields: min/max age, min income, min credit score, employment types, max amount and rate. The table below gives the criteria per product family and leaves out rates.
- **Impact:** the SQL hard filter run twice over the same users, once with the extracted values and once with the corrected values.
- **Not checked:** the twelve BankBazaar rows. They should only list rates, which feed the emails; see below for when they did not.

## Ground truth

| Product | Age | Min income | Credit score | Employment | Max amount |
|---|---|---|---|---|---|
| HDFC | 21–60 | ₹25k | 720 | salaried | ₹40L |
| ICICI salaried | 18–58 | ₹30k | 700 ("preferred") | salaried | ₹50L |
| ICICI self-employed | 23–65 | n/a | n/a | self-employed (no split by type) | ₹50L |
| Kotak | 21–60 | ₹30k general; ₹25k salary-account holders; ₹20k Kotak staff | 750 (the FAQ also says 685) | salaried | ₹1 crore |
| Bajaj Finserv | 21–80 | not stated | 650 | salaried or self-employed | ₹55L |

## Results

The first extraction got **39 of 42** fields right. All three errors were in a field the SQL filter uses:

| # | Error | Cause | Users affected |
|---|---|---|---|
| 1 | Kotak min income ₹20k | The model took the threshold for Kotak's own employees | 106 wrongly matched, all rated "likely" by the LLM judge |
| 2 | ICICI self-employed = `business` only | "Self-employed" was read as one segment | 2,237 self-employed professionals wrongly excluded |
| 3 | Bajaj self-employed = `self_employed` only | Same as #2 | 3,240 business owners wrongly excluded |

Error #1 shows why this audit matters: the LLM judge cannot catch a bad hard filter. It only sees pairs that already passed SQL, and the numbers looked plausible.

## Fixes

**Prompt rules were not enough.** I first added both rules to the extraction prompt:
- Use the general-public threshold.
- Read a plain "self-employed" as both segments.

On the next crawl the model fixed ICICI, but it split Kotak into three products (general, salary-account holders, employees) and still returned Bajaj as `self_employed` only. Rewording the prompt made the output change, not converge. Re-extracting also introduced a new error: a generic "750+ is a good score" line on the BankBazaar rate page was copied onto all 12 lenders it lists, which made those rows matchable.

**The rules now live in code**, in the validation step after the LLM:

| Rule | Why |
|---|---|
| Drop products named for the lender's employees, staff, existing customers or account holders | They are not open to the uploaded users |
| If no product on a page separates `self_employed` from `business`, a self-employed product gets both | Lenders that do split them (separate professional and business products) keep the split |
| A page that lists several lenders supplies rates, amounts and fees only; eligibility fields are cleared | An aggregator's eligibility text is generic, and each lender's own page is the source of truth |

A version tag for the prompt and the validation code is part of each page's fingerprint. Changing either and bumping the tag re-extracts every page once instead of keeping stale products. Products that drop out of a successful crawl are retired. `backend/tests/test_crawler_validation.py` runs the shipped validation code on the exact outputs that failed.

## After the fix

All 42 fields match the lender pages, and the 12 rate-only rows carry no eligibility criteria. Impact on which of the same 10k users pass the SQL hard filter:

| Lender | Change |
|---|---|
| ICICI | +2,237 self-employed professionals now pass |
| Bajaj Finserv | +3,240 business owners now pass |
| Kotak | −106 users with income ₹20k–30k no longer pass (the income fix) |
| Kotak | −1,355 users with credit score 685–749 no longer pass (see the 750 vs 685 limitation below) |

Users who pass for at least one lender went from 8,832 to all 10,000. User–lender pairs rose from 15,441 to 19,457.

## Known limitations

- **"Preferred" scores are treated as minimums.** ICICI's "700+ preferred" becomes a hard cutoff. Some users below it could still be approved.
- **Max age is checked at application.** Bajaj and ICICI give the age limit at the end of the loan tenure. The user's tenure is unknown, so the filter is over-inclusive near the limit.
- **Conflicting numbers on one page.** Kotak's eligibility section says 750 and its FAQ says 685. The first extraction took 685 and every later one took 750, the stricter value. This moves 1,355 users, so it is noted rather than counted as an error.
- **No ground truth over time.** This audit is a snapshot. A page redesign can break extraction silently, so the audit should be repeated whenever a source's fingerprint changes.
