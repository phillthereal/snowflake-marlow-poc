# Working rules for this repo

A pre-sales proof of concept on Snowflake for a fictional consulting firm, Marlow Advisory. Fil is the author and has to be able to explain every line without notes. Keep it small and plain.

## Never

- Never open, print, copy or edit anything in `~/.snowflake` (the private key and `connections.toml`). Checking that a file exists and its permissions with `ls -l` is fine.
- Never put a password, key, token or Snowflake account identifier in this repo, a commit message or the chat.
- Never invent, round or estimate a result. Every number in README.md, SUCCESS_CRITERIA.md or a commit message comes from a file in `results/` or from terminal output of a run in this session.
- Never describe emulator results (`tests/test_local.py`, anything run with `--local`) as Snowflake results.
- Never edit `data/*.csv` by hand. If the data has to change, change `generator/generate_data.py`, regenerate, and say so.
- Never add anything outside SUCCESS_CRITERIA.md (AI features, dashboards, Streamlit, dbt, extra libraries) unless Fil asks.

## Before changing any file in `sql/`, `run.py` or `check/`

1. Show Fil the exact error or problem and the smallest fix.
2. Wait for his OK.
3. After the change, run `python tests/test_local.py`. It must pass before any run on the real account.
4. Add a line to CHANGELOG.md: date, file, what changed and why.

## Commands

- Local rehearsal, no account needed: `python tests/test_local.py`
- Real account: `python run.py setup`, `python run.py load data/batch_2026_09`, `python run.py load data/batch_2026_10`, `python run.py check`, `python run.py usage`

## Writing style for anything Fil reads or publishes

Plain British English. No em dashes. Short sentences. Say what the thing does, then what happened.
