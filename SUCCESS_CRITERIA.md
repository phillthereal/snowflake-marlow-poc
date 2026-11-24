# Success criteria: Marlow Advisory proof of concept

Version 1, with seven criteria, was written on 19 Nov 2026 before any code. Version 2, on 20 Nov 2026, was finalised alongside the build. It put the questions in order of value to the buyer, merged win rate with overrun into question 3, tightened criteria 2, 4 and 5, and added criterion 8 (the independent recalculation).

## The buyer and the problem

The buyer is the operations director of Marlow Advisory, a 40-person consulting firm. Marlow is fictional and so is all of its data.

The firm prices fixed-fee work from memory and old spreadsheets. Bids, the job register and timesheets sit in three separate files, so nobody can say which kinds of job run over the hours they were priced at, or whether the firm wins some work only because it prices it too low.

## The questions, in order of value to the buyer

1. **Which job types overrun their priced hours?** This is where margin goes, and the director can reprice those job types straight away.
2. **For a new bid, what did similar past jobs actually take?** The director would use this every week. "Similar" means same job type and fee band, falling back to the whole job type when there are fewer than 5 past jobs.
3. **Which job types do we win because we underprice them?** This puts win rate next to overrun. A job type that wins more often than the firm average and also overruns by 10% or more is likely winning on price. Win rate by job type and fee band is kept as a supporting table.

## Pass or fail

The Result column was filled in after the run on a Snowflake trial account on 24 Nov 2026, copied from the final load. The full record is in [docs/run-2026-11-24.md](docs/run-2026-11-24.md). The earlier run is in [docs/run-2026-11-20.md](docs/run-2026-11-20.md).

| # | Criterion | How it is tested | Result |
|---|---|---|---|
| 1 | One command loads a month's three files, and the row counts in Snowflake match the files | `run.py load` compares rows per file | PASS: batch_2026_09/bids: file 326, Snowflake 326; batch_2026_09/jobs: file 149, Snowflake 149; batch_2026_09/timesheets: file 1755, Snowflake 1755; batch_2026_10/bids: file 16, Snowflake 16; batch_2026_10/jobs: file 7, Snowflake 7; batch_2026_10/timesheets: file 31, Snowflake 31 |
| 2 | Fee and hour totals in Snowflake equal the totals in the files, and every row is accounted for as clean, rejected or superseded | `run.py` compares totals, then checks raw = clean + rejected + superseded | 2a PASS: batch_2026_09 fees £: file 7,127,300.00, Snowflake 7,127,300.00; batch_2026_09 priced hours: file 61,497.00, Snowflake 61,497.00; batch_2026_09 timesheet hours: file 31,640.50, Snowflake 31,640.50; batch_2026_10 fees £: file 302,950.00, Snowflake 302,950.00; batch_2026_10 priced hours: file 2,586.00, Snowflake 2,586.00; batch_2026_10 timesheet hours: file 584.00, Snowflake 584.00. 2b PASS: bids: raw 342 = clean 329 + rejected 6 + superseded 7; jobs: raw 156 = clean 150 + rejected 2 + superseded 4; timesheets: raw 1786 = clean 1741 + rejected 45 + superseded 0 |
| 3 | Each question is answered by a saved view the director can query | Views `Q1`, `Q2`, `Q3`, `Q3B` return rows | PASS: Q1 6 rows, Q2 21 rows, Q3 6 rows, Q3b 16 rows |
| 4 | Rows that break a rule (missing job type, negative hours, unknown job code, duplicates and the rest) land in a rejects list with the file, the spreadsheet row and the reason. None vanish | Blank job types and negative hours in the files are counted and matched against the rejects list | PASS: blank job type: 3 in files, 3 rejected; negative hours: 4 in files, 4 rejected; rejects without file, row or reason: 0 |
| 5 | Next month's files load with the same command and the answers update with no manual edits. Loading the same month twice changes nothing | Load October, then load September again | PASS: batch_2026_09 (repeat load, nothing added): rows added {'BIDS': 0, 'JOBS': 0, 'TIMESHEETS': 0}; completed jobs 148 before, 148 after |
| 6 | The director's role reads the answers and a data quality summary, and is refused the raw and clean tables, including individual timesheet lines | `run.py` switches to the director role and tries both | PASS: answers readable (6 rows); MARLOW.CLEAN.TIMESHEETS refused; MARLOW.RAW.TIMESHEETS refused; MARLOW.CLEAN.REJECTS refused |
| 7 | Runs on the smallest warehouse (X-Small, suspends after 60 seconds idle), and the credits used are read from Snowflake's own metering and reported | `SHOW WAREHOUSES`, then `run.py usage` | PASS: size X-Small, auto-suspend 60s; credits: run `python run.py usage` (metering can lag up to 3 hours, cloud services up to 6). **Credits: to be read with `python run.py usage` at least 6 hours after the run, because Snowflake's metering lags.** |
| 8 | Every answer matches an independent recalculation done outside Snowflake from the same files | `check/independent_check.py` recomputes with pandas and `run.py` compares | PASS: Q1, Q2 (21 rows), Q3, Q3b and the rejects summary all match the pandas recalculation from the CSV files |

## Assumptions to confirm with the buyer

- Overrun is judged on completed jobs only.
- A job type "overruns" when its median job is 10% or more over its priced hours.
- Win rate counts Won and Lost bids only. Pending bids and bids with no outcome recorded are left out.
- A job type with no decided bids, or with no completed jobs, is reported as exactly that. It gets no verdict in question 3 until there is something to judge.
- When the same bid or job appears in two monthly files, the later file wins.
- Negative timesheet hours are treated as errors and rejected. If they are really corrections, the rule changes to net them off. This is the first question for discovery.
- "Workshop facilitation" appears in the bid register but is not one of the agreed job types, so those bids are rejected until the buyer says where they belong.

## Out of scope

AI features, dashboards and live connections to other systems.
