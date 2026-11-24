# Changelog

| Date | File | Change | Why |
|---|---|---|---|
| 2026-11-20 | all | First version | Tested on the local emulator only at this point (criteria 1 to 5 and 8 pass) |
| 2026-11-20 | README.md, SUCCESS_CRITERIA.md, docs/run-2026-11-20.md | Recorded the first run on a Snowflake trial account | All 8 criteria passed. No code changed between the first version and this run |
| 2026-11-22 | sql/06_answers.sql, check/independent_check.py, run.py | Q3 divides by `NULLIF(decided_bids, 0)`. Two new verdicts: "No decided bids yet" and "No completed jobs yet" | A job type whose bids are all pending would stop the view with "Division by zero" on Snowflake. A type with no completed jobs was labelled "delivers within price" with no evidence |
| 2026-11-22 | sql/05_clean.sql, tests/test_local.py | `spreadsheet_row` is counted from the first row loaded from each file, not from the first rejected row. The local test now checks every rejected bid and job against its line in the CSV | The old line could report a reject one spreadsheet row out. On the local emulator B-0049 showed as row 49, and it sits on row 50 |
| 2026-11-22 | sql/01_setup.sql | Metering access granted through the `SNOWFLAKE.USAGE_VIEWER` database role, not `IMPORTED PRIVILEGES` | The old grant also opened query history, login history and the user list to the pipeline role |
| 2026-11-22 | run.py | `load` refuses a batch folder not named like `batch_2026_09` | The folder name is put into SQL text |
| 2026-11-22 | run.py, tests/test_local.py | Emulator result files have `local` in their names. The usage output says the figure is to date and how far metering can lag | Emulator and Snowflake files were named the same way |
| 2026-11-22 | RUN_GUIDE.md, SUCCESS_CRITERIA.md, README.md, CLAUDE.md | Run guide cut down to the steps needed to run the build, and now switches the connection to `MARLOW_ADMIN` after setup. Criteria sheet states its version history and when results were added | Keep the public docs to what a reader needs, and state history accurately |
| 2026-11-24 | README.md, SUCCESS_CRITERIA.md, docs/run-2026-11-24.md | Recorded the 24 Nov run on a Snowflake trial account, after the database was dropped and rebuilt | All 8 criteria passed on every load. This is the first Snowflake run of the 22 Nov changes. The credit figure is left out until metering catches up |

The 22 Nov changes passed the local emulator test (`python tests/test_local.py`) and then ran on a Snowflake trial account on 24 Nov 2026.
