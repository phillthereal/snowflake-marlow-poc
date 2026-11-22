"""Full rehearsal against the local Snowflake emulator, in a fresh database.

Runs the same commands as the real account: setup, load September, load
October, load September again. Fails if any testable criterion fails, or if
the build does not find the two job types planted as "winning on price".

Usage: python tests/test_local.py
"""

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args, env):
    out = subprocess.run([sys.executable, str(ROOT / "run.py"), *args, "--local"],
                         cwd=ROOT, env=env, capture_output=True, text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr)
        raise SystemExit(f"run.py {' '.join(args)} crashed")
    return out.stdout


def criteria(stdout):
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip().startswith("[")]
    return {ln.split("] ", 1)[1]: ln[1:ln.index("]")] for ln in lines}


def main():
    env = {**os.environ, "PYTHONWARNINGS": "ignore",
           "MARLOW_LOCAL_DB": tempfile.mkdtemp(prefix="marlow_test_")}
    failures = []
    run("setup", env=env)
    for step, batch in (("September", "data/batch_2026_09"), ("October", "data/batch_2026_10"),
                        ("September again", "data/batch_2026_09")):
        result = criteria(run("load", batch, env=env))
        bad = {k: v for k, v in result.items() if v == "FAIL"}
        print(f"{step}: " + ", ".join(f"{k.split()[0]} {v}" for k, v in result.items()))
        failures += [f"{step}: {k}" for k in bad]

    # The two planted "winning on price" types must be the ones flagged.
    latest_q3 = sorted((ROOT / "results").glob("*_local_*_q3.csv"))[-1]
    with latest_q3.open(encoding="utf-8") as f:
        flagged = sorted(r["job_type"] for r in csv.DictReader(f) if r["verdict"].startswith("Winning on price"))
    planted = sorted(json.loads((ROOT / "data" / "planted.json").read_text())["expected_winning_on_price"])
    print(f"Flagged as winning on price: {flagged} (planted: {planted})")
    if flagged != planted:
        failures.append("Q3 did not find the planted pattern")

    # Every rejected bid and job must point at the spreadsheet row that really
    # holds it: line N of the CSV, counting the header as line 1.
    latest_rejects = sorted((ROOT / "results").glob("*_local_*_rejects.csv"))[-1]
    wrong_rows = 0
    with latest_rejects.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["source_table"] == "timesheets":
                continue  # timesheet lines have no unique ID to look up
            with (ROOT / "data" / r["load_batch"] / f"{r['source_table']}.csv").open(encoding="utf-8", newline="") as src:
                lines = list(csv.reader(src))
            if lines[int(r["spreadsheet_row"]) - 1][0] != r["record_id"]:
                wrong_rows += 1
    print(f"Rejected bids and jobs pointing at the wrong spreadsheet row: {wrong_rows}")
    if wrong_rows:
        failures.append("rejects list points at the wrong spreadsheet row")

    if failures:
        raise SystemExit("FAILED: " + "; ".join(failures))
    print("All testable criteria pass on the emulator. Criteria 6 and 7 need the real account.")


if __name__ == "__main__":
    main()
