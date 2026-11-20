# Marlow Advisory: pricing proof of concept on Snowflake

A small pre-sales proof of concept. A fictional consulting firm keeps its bids, job register and timesheets in three spreadsheets and can't see which kinds of work run over the hours they were priced at. This build loads the monthly exports into Snowflake, checks every row against named rules, and answers three questions the operations director asked for, scored against [success criteria written before the build](SUCCESS_CRITERIA.md).

**All data is synthetic.** Marlow Advisory does not exist. `generator/generate_data.py` writes the files from a fixed seed, with patterns and errors planted on purpose (listed in `data/planted.json`) so the build can be tested against a known answer. The results show the pipeline works. They say nothing about any real firm.

## The three questions

1. Which job types overrun their priced hours?
2. For a new bid, what did similar past jobs actually take?
3. Which job types do we win because we underprice them?

## How it works

```
monthly CSV exports
      │  PUT + COPY INTO (Snowflake skips files it has already loaded)
      ▼
RAW       every value as text, with file name and row number
      │  named rules: TRY_TO_NUMBER / TRY_TO_DATE, job type map, duplicates
      ▼
CLEAN     rows that pass  ──►  REJECTS (file, spreadsheet row, reason)
      │
      ▼
ANSWERS   Q1, Q2, Q3, Q3B and a data quality summary
          (the director's role can read these views and nothing else)
```

| Folder | What's in it |
|---|---|
| `sql/` | Numbered scripts: setup, objects, stage, copy, cleaning rules, answer views, access. `demo_new_bid.sql` is the worksheet for the demo |
| `data/` | Two monthly batches: everything to 30 Sep 2026, then October's changes |
| `check/` | The independent recalculation in pandas (criterion 8) |
| `tests/` | A full rehearsal against a local Snowflake emulator |
| `run.py` | One command per job: `setup`, `load`, `check`, `usage` |
| `CLAUDE.md`, `CHANGELOG.md` | Rules for AI-assisted changes, and a log of every change after the first version |

## Running it

```
pip install -r requirements.txt
python run.py setup
python run.py load data/batch_2026_09
python run.py load data/batch_2026_10
python run.py usage
```

The connection details come from `~/.snowflake/connections.toml` (key-pair authentication). Nothing secret is stored in this folder. [RUN_GUIDE.md](RUN_GUIDE.md) has the full steps.

To rehearse without a Snowflake account:

```
pip install -r requirements-local.txt
python tests/test_local.py
```

## Results

Filled in after the run on a real Snowflake account. Each run writes its pass or fail table, the answers and the rejects list to `results/`.
