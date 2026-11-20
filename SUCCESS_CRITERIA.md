# Success criteria: Marlow Advisory proof of concept

Written before the build. Version 2, 20 Nov 2026.

## The buyer and the problem

The buyer is the operations director of Marlow Advisory, a 40-person consulting firm. Marlow is fictional and so is all of its data.

The firm prices fixed-fee work from memory and old spreadsheets. Bids, the job register and timesheets sit in three separate files, so nobody can say which kinds of job run over the hours they were priced at, or whether the firm wins some work only because it prices it too low.

## The questions, in order of value to the buyer

1. **Which job types overrun their priced hours?** This is where margin goes, and the director can reprice those job types straight away.
2. **For a new bid, what did similar past jobs actually take?** The director would use this every week. "Similar" means same job type and fee band, falling back to the whole job type when there are fewer than 5 past jobs.
3. **Which job types do we win because we underprice them?** This puts win rate next to overrun. A job type that wins more often than the firm average and also overruns by 10% or more is likely winning on price. Win rate by job type and fee band is kept as a supporting table.

## Pass or fail

| # | Criterion | How it is tested | Result |
|---|---|---|---|
| 1 | One command loads a month's three files, and the row counts in Snowflake match the files | `run.py load` compares rows per file | |
| 2 | Fee and hour totals in Snowflake equal the totals in the files, and every row is accounted for as clean, rejected or superseded | `run.py` compares totals, then checks raw = clean + rejected + superseded | |
| 3 | Each question is answered by a saved view the director can query | Views `Q1`, `Q2`, `Q3`, `Q3B` return rows | |
| 4 | Rows that break a rule (missing job type, negative hours, unknown job code, duplicates and the rest) land in a rejects list with the file, the spreadsheet row and the reason. None vanish | Blank job types and negative hours in the files are counted and matched against the rejects list | |
| 5 | Next month's files load with the same command and the answers update with no manual edits. Loading the same month twice changes nothing | Load October, then load September again | |
| 6 | The director's role reads the answers and a data quality summary, and is refused the raw and clean tables, including individual timesheet lines | `run.py` switches to the director role and tries both | |
| 7 | Runs on the smallest warehouse (X-Small, suspends after 60 seconds idle), and the credits used are read from Snowflake's own metering and reported | `SHOW WAREHOUSES`, then `run.py usage` | |
| 8 | Every answer matches an independent recalculation done outside Snowflake from the same files | `check/independent_check.py` recomputes with pandas and `run.py` compares | |

## Assumptions to confirm with the buyer

- Overrun is judged on completed jobs only.
- A job type "overruns" when its median job is 10% or more over its priced hours.
- Win rate counts Won and Lost bids only. Pending bids and bids with no outcome recorded are left out.
- When the same bid or job appears in two monthly files, the later file wins.
- Negative timesheet hours are treated as errors and rejected. If they are really corrections, the rule changes to net them off. This is the first question for discovery.
- "Workshop facilitation" appears in the bid register but is not one of the agreed job types, so those bids are rejected until the buyer says where they belong.

## Out of scope

AI features, dashboards and live connections to other systems.

## One rule outside the sheet

Every query has to be explainable line by line before the recording.
