"""Marlow Advisory proof of concept: one command per job.

  python run.py setup                     once: roles, warehouse, database, stage
  python run.py load data/batch_2026_09   upload a month's files, rebuild, check, show answers
  python run.py check                     re-run the checks on what is loaded
  python run.py usage                     credits used, from Snowflake's own metering

Add --local to run against a local Snowflake emulator instead of a real
account (needs requirements-local.txt). Useful for testing; criteria 6 and 7
can only be tested on the real account.

Connection: reads the [marlow] entry in ~/.snowflake/connections.toml.
No password or key ever lives in this folder. See RUN_GUIDE.md.
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SQL = ROOT / "sql"
RESULTS = ROOT / "results"
sys.path.insert(0, str(ROOT / "check"))
import independent_check  # noqa: E402

FILES = {"bids": "BIDS", "jobs": "JOBS", "timesheets": "TIMESHEETS"}
RAW_COLUMNS = {
    "BIDS": ["bid_id", "client_code", "job_type_label", "submitted_on", "fee_quoted_gbp",
             "priced_hours", "outcome", "lead_partner"],
    "JOBS": ["job_id", "bid_id", "start_date", "end_date", "status"],
    "TIMESHEETS": ["week_ending", "employee_id", "grade", "job_code", "hours"],
}


# ----------------------------------------------------------------- helpers

def statements(path, **values):
    """Split a .sql file into statements. Comment lines are dropped and
    {{NAME}} placeholders are filled in."""
    text = path.read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    out, current = [], []
    for ln in lines:
        current.append(ln)
        if ln.rstrip().endswith(";"):
            stmt = "\n".join(current).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            current = []
    tail = "\n".join(current).strip()
    if tail:
        out.append(tail)
    return out


def run_file(cur, name, **values):
    for stmt in statements(SQL / name, **values):
        cur.execute(stmt)


def rows(cur, sql):
    cur.execute(sql)
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def scalar(cur, sql):
    cur.execute(sql)
    return cur.fetchone()[0]


def show(title, data, cols=None):
    """Print a small table without extra libraries."""
    print(f"\n{title}")
    if not data:
        print("  (no rows)")
        return
    cols = cols or list(data[0].keys())
    fmt = lambda v: "" if v is None else (f"{float(v):,.1f}" if isinstance(v, float) or
                                          type(v).__name__ == "Decimal" else str(v))
    width = {c: max(len(c), *(len(fmt(r[c])) for r in data)) for c in cols}
    print("  " + "  ".join(c.ljust(width[c]) for c in cols))
    for r in data:
        print("  " + "  ".join(fmt(r[c]).ljust(width[c]) for c in cols))


def save(name, data):
    RESULTS.mkdir(exist_ok=True)
    if not data:
        return
    with (RESULTS / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader()
        w.writerows(data)


# -------------------------------------------------------------- connection

def connect(local):
    import snowflake.connector
    if local:
        return snowflake.connector.connect(database="MARLOW", schema="RAW")
    name = os.environ.get("MARLOW_CONNECTION", "marlow")
    return snowflake.connector.connect(connection_name=name)


def use_pipeline_role(cur, local):
    if not local:
        cur.execute("USE ROLE MARLOW_ADMIN")
        cur.execute("USE SECONDARY ROLES NONE")
        cur.execute("USE WAREHOUSE MARLOW_WH")
    cur.execute("CREATE DATABASE IF NOT EXISTS MARLOW")
    cur.execute("USE DATABASE MARLOW")


# ---------------------------------------------------------------- commands

def cmd_setup(cur, local):
    if not local:
        user = scalar(cur, "SELECT CURRENT_USER()")
        run_file(cur, "01_setup.sql", USER=user)
        print(f"Roles, warehouse and grants created for user {user}.")
    use_pipeline_role(cur, local)
    run_file(cur, "02_objects.sql")
    if not local:
        run_file(cur, "03_stage.sql")
    print("Database MARLOW, schemas, raw tables and job type map are ready.")


def load_local(cur, batch_dir, table, filename):
    """Emulator only: insert the file's rows the way COPY INTO would,
    and skip a file that is already loaded, as Snowflake's load history does."""
    source = f"{batch_dir.name}/{filename}.csv"
    if scalar(cur, f"SELECT COUNT(*) FROM RAW.{table} WHERE source_file = '{source}'"):
        print(f"  {source}: already loaded, skipped")
        return
    cols = RAW_COLUMNS[table]
    with (batch_dir / f"{filename}.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        data = [[v if v != "" else None for v in r] + [batch_dir.name, source, i]
                for i, r in enumerate(reader, start=1)]
    marks = ", ".join(["%s"] * (len(cols) + 3))
    cur.executemany(
        f"INSERT INTO RAW.{table} ({', '.join(cols)}, load_batch, source_file, source_row) "
        f"VALUES ({marks})", data)
    print(f"  {source}: {len(data)} rows loaded")


def rebuild(cur, local):
    run_file(cur, "05_clean.sql")
    run_file(cur, "06_answers.sql")
    if not local:
        run_file(cur, "07_access.sql")


def answers(cur):
    q1 = rows(cur, "SELECT * FROM ANSWERS.Q1_OVERRUN_BY_JOB_TYPE ORDER BY median_overrun_pct DESC")
    q2 = rows(cur, "SELECT * FROM ANSWERS.Q2_BID_BENCHMARKS ORDER BY job_type, fee_band_order")
    q3 = rows(cur, "SELECT * FROM ANSWERS.Q3_WIN_RATE_VS_OVERRUN ORDER BY median_overrun_pct DESC")
    q3b = rows(cur, "SELECT * FROM ANSWERS.Q3B_WIN_RATE_BY_FEE_BAND ORDER BY job_type, fee_band_order")
    dq = rows(cur, "SELECT * FROM ANSWERS.DATA_QUALITY ORDER BY source_table, load_batch, reason")
    return q1, q2, q3, q3b, dq


def cmd_load(cur, local, batch_dir):
    batch_dir = Path(batch_dir).resolve()
    batch = batch_dir.name
    use_pipeline_role(cur, local)
    before = {t: scalar(cur, f"SELECT COUNT(*) FROM RAW.{t}") for t in FILES.values()}
    try:
        jobs_before = scalar(cur, "SELECT SUM(completed_jobs) FROM ANSWERS.Q1_OVERRUN_BY_JOB_TYPE")
    except Exception:
        jobs_before = None

    print(f"Loading {batch}")
    if local:
        for filename, table in FILES.items():
            load_local(cur, batch_dir, table, filename)
    else:
        for filename in FILES:
            path = (batch_dir / f"{filename}.csv").as_posix()
            cur.execute(f"PUT 'file://{path}' @RAW.LANDING/{batch}/ AUTO_COMPRESS=TRUE OVERWRITE=FALSE")
        for stmt in statements(SQL / "04_copy.sql", BATCH=batch):
            cur.execute(stmt)
            for r in cur.fetchall():
                print("  ", " | ".join(str(v) for v in r[:4]))
    after = {t: scalar(cur, f"SELECT COUNT(*) FROM RAW.{t}") for t in FILES.values()}

    rebuild(cur, local)
    jobs_after = scalar(cur, "SELECT SUM(completed_jobs) FROM ANSWERS.Q1_OVERRUN_BY_JOB_TYPE")
    load_note = {
        "batch": batch,
        "raw_rows_added": {t: after[t] - before[t] for t in after},
        "completed_jobs_before": jobs_before,
        "completed_jobs_after": jobs_after,
    }
    return cmd_check(cur, local, load_note)


def cmd_check(cur, local, load_note=None):
    use_pipeline_role(cur, local)
    batches = [r["load_batch"] for r in rows(
        cur, "SELECT DISTINCT load_batch FROM RAW.BIDS ORDER BY load_batch")]
    batch_dirs = [ROOT / "data" / b for b in batches]
    results = []  # (criterion, pass/fail/info, evidence)

    # 1. Row counts match the files.
    ok, ev = True, []
    for b, d in zip(batches, batch_dirs):
        totals = independent_check.file_totals(d)
        for filename, table in FILES.items():
            n = scalar(cur, f"SELECT COUNT(*) FROM RAW.{table} WHERE load_batch = '{b}'")
            ok &= n == totals["rows"][filename]
            ev.append(f"{b}/{filename}: file {totals['rows'][filename]}, Snowflake {n}")
    results.append(("1 Row counts match the files", ok, "; ".join(ev)))

    # 2a. Totals match the files.
    ok, ev = True, []
    for b, d in zip(batches, batch_dirs):
        t = independent_check.file_totals(d)
        fee = scalar(cur, "SELECT SUM(TRY_TO_NUMBER(REPLACE(REPLACE(fee_quoted_gbp, '£', ''), ',', ''), 12, 2)) "
                          f"FROM RAW.BIDS WHERE load_batch = '{b}'")
        ph = scalar(cur, f"SELECT SUM(TRY_TO_NUMBER(priced_hours, 10, 2)) FROM RAW.BIDS WHERE load_batch = '{b}'")
        th = scalar(cur, f"SELECT SUM(TRY_TO_NUMBER(hours, 10, 2)) FROM RAW.TIMESHEETS WHERE load_batch = '{b}'")
        pairs = [("fees £", t["fee_total"], fee), ("priced hours", t["priced_hours_total"], ph),
                 ("timesheet hours", t["timesheet_hours_total"], th)]
        for label, file_v, sf_v in pairs:
            ok &= abs(float(file_v) - float(sf_v or 0)) < 0.005
            ev.append(f"{b} {label}: file {file_v:,.2f}, Snowflake {float(sf_v or 0):,.2f}")
    results.append(("2a Fee and hour totals match the files", ok, "; ".join(ev)))

    # 2b. Every raw row is clean, rejected or superseded.
    ok, ev = True, []
    for name, table in FILES.items():
        raw_n = scalar(cur, f"SELECT COUNT(*) FROM RAW.{table}")
        clean_n = scalar(cur, f"SELECT COUNT(*) FROM CLEAN.{table}")
        rej_n = scalar(cur, f"SELECT COUNT(*) FROM CLEAN.REJECTS WHERE source_table = '{name}'")
        sup_n = scalar(cur, f"SELECT COUNT_IF(is_superseded) FROM CLEAN.{table}_CHECKED")
        ok &= raw_n == clean_n + rej_n + sup_n
        ev.append(f"{name}: raw {raw_n} = clean {clean_n} + rejected {rej_n} + superseded {sup_n}")
    results.append(("2b Nothing vanishes", ok, "; ".join(ev)))

    # 3. Each question answered by a saved view.
    q1, q2, q3, q3b, dq = answers(cur)
    ok = all(len(x) > 0 for x in (q1, q2, q3, q3b))
    results.append(("3 Each question has a saved view with an answer", ok,
                    f"Q1 {len(q1)} rows, Q2 {len(q2)} rows, Q3 {len(q3)} rows, Q3b {len(q3b)} rows"))

    # 4. Rule breakers land in the rejects list with file, row and reason.
    missing_type = scalar(cur, "SELECT COUNT(*) FROM RAW.BIDS WHERE NULLIF(TRIM(job_type_label), '') IS NULL")
    rej_type = scalar(cur, "SELECT COUNT(*) FROM CLEAN.REJECTS WHERE reason = 'Job type missing'")
    neg = scalar(cur, "SELECT COUNT(*) FROM RAW.TIMESHEETS WHERE NULLIF(TRIM(job_code), '') IS NOT NULL "
                      "AND TRY_TO_NUMBER(hours, 10, 2) <= 0")
    rej_neg = scalar(cur, "SELECT COUNT(*) FROM CLEAN.REJECTS WHERE reason = 'Hours zero or negative'")
    unlabelled = scalar(cur, "SELECT COUNT(*) FROM CLEAN.REJECTS WHERE reason IS NULL "
                             "OR source_file IS NULL OR spreadsheet_row IS NULL")
    ok = missing_type == rej_type and neg == rej_neg and unlabelled == 0
    results.append(("4 Rule breakers go to the rejects list", ok,
                    f"blank job type: {missing_type} in files, {rej_type} rejected; "
                    f"negative hours: {neg} in files, {rej_neg} rejected; "
                    f"rejects without file, row or reason: {unlabelled}"))

    # 5. Re-running: a new month adds exactly its rows and updates the answers;
    #    the same month a second time adds nothing.
    if load_note:
        added = load_note["raw_rows_added"]
        expected = independent_check.file_totals(ROOT / "data" / load_note["batch"])["rows"]
        first_time = all(added[FILES[f]] == n for f, n in expected.items())
        repeat = all(v == 0 for v in added.values())
        ok = first_time or repeat
        kind = "repeat load, nothing added" if repeat else "new month, every file row added"
        ev = (f"{load_note['batch']} ({kind if ok else 'unexpected row count'}): rows added {added}; "
              f"completed jobs {load_note['completed_jobs_before']} before, "
              f"{load_note['completed_jobs_after']} after")
        results.append(("5 Re-run: new month updates answers, repeat month adds nothing", ok, ev))

    # 6. Director sees answers only.
    if local:
        results.append(("6 Director reads answers only", "SKIP", "Roles can only be tested on the real account"))
    else:
        ok, ev = True, []
        cur.execute("USE ROLE MARLOW_DIRECTOR")
        cur.execute("USE SECONDARY ROLES NONE")
        try:
            n = scalar(cur, "SELECT COUNT(*) FROM MARLOW.ANSWERS.Q1_OVERRUN_BY_JOB_TYPE")
            ev.append(f"answers readable ({n} rows)")
        except Exception as e:
            ok = False
            ev.append(f"answers NOT readable: {e}")
        for table in ("MARLOW.CLEAN.TIMESHEETS", "MARLOW.RAW.TIMESHEETS", "MARLOW.CLEAN.REJECTS"):
            try:
                scalar(cur, f"SELECT COUNT(*) FROM {table}")
                ok = False
                ev.append(f"{table} WAS readable")
            except Exception:
                ev.append(f"{table} refused")
        use_pipeline_role(cur, local)
        results.append(("6 Director reads answers only", ok, "; ".join(ev)))

    # 7. Smallest warehouse.
    if local:
        results.append(("7 Smallest warehouse, credits reported", "SKIP", "Real account only"))
    else:
        cur.execute("SHOW WAREHOUSES LIKE 'MARLOW_WH'")
        cols = [d[0].lower() for d in cur.description]
        wh = dict(zip(cols, cur.fetchone()))
        ok = str(wh.get("size", "")).upper() in ("X-SMALL", "XSMALL") and int(wh.get("auto_suspend") or 0) <= 60
        results.append(("7 Smallest warehouse, credits reported", ok,
                        f"size {wh.get('size')}, auto-suspend {wh.get('auto_suspend')}s; "
                        "credits: run `python run.py usage` (metering can lag up to 3 hours)"))

    # 8. Every answer matches the independent recalculation.
    ok, ev = compare(independent_check.compute(batch_dirs), q1, q2, q3, q3b, dq)
    results.append(("8 Answers match an independent recalculation", ok, ev))

    # ---------------------------------------------------------- report
    show("Q1  Which job types overrun their priced hours?", q1,
         ["job_type", "completed_jobs", "priced_hours", "actual_hours", "median_overrun_pct",
          "share_10pct_or_more_over"])
    show("Q2  What did similar past jobs take? (All fee bands rows)",
         [r for r in q2 if r["fee_band"] == "All fee bands"],
         ["job_type", "similar_jobs", "median_priced_hours", "median_actual_hours", "p80_actual_hours"])
    show("Q3  Which job types do we win because we underprice them?", q3,
         ["job_type", "win_rate_pct", "firm_win_rate_pct", "median_overrun_pct", "verdict"])
    show("Data quality (counts only)", dq)

    print("\nSUCCESS CRITERIA")
    for name, status, evidence in results:
        label = status if isinstance(status, str) else ("PASS" if status else "FAIL")
        print(f"  [{label}] {name}\n         {evidence}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = (load_note or {}).get("batch", "check")
    for name, data in (("q1", q1), ("q2", q2), ("q3", q3), ("q3b", q3b), ("data_quality", dq)):
        save(f"{stamp}_{tag}_{name}", data)
    save(f"{stamp}_{tag}_rejects", rows(cur, "SELECT source_table, load_batch, source_file, spreadsheet_row, "
                                             "record_id, reason, value_found FROM CLEAN.REJECTS "
                                             "ORDER BY source_table, source_file, spreadsheet_row"))
    with (RESULTS / f"{stamp}_{tag}_criteria.md").open("w", encoding="utf-8") as f:
        f.write(f"# Run {stamp} ({'local emulator' if local else 'Snowflake'}), {tag}\n\n")
        f.write("| Criterion | Result | Evidence |\n|---|---|---|\n")
        for name, status, evidence in results:
            label = status if isinstance(status, str) else ("PASS" if status else "FAIL")
            f.write(f"| {name} | {label} | {evidence} |\n")
    print(f"\nSaved answers, rejects and criteria to results/{stamp}_{tag}_*")
    return results


def compare(exp, q1, q2, q3, q3b, dq):
    """Compare Snowflake's answers with the pandas recalculation.
    Percentages in the views are rounded to 1 decimal, so allow 0.05."""
    problems = []

    def close(a, b, tol):
        return a is not None and b is not None and abs(float(a) - float(b)) <= tol + 1e-9

    def check(where, got, expected, tol=0.0):
        if not close(got, expected, tol):
            problems.append(f"{where}: Snowflake {got}, recalculation {expected}")

    e1 = exp["q1"]
    if len(q1) != len(e1):
        problems.append(f"Q1 rows: Snowflake {len(q1)}, recalculation {len(e1)}")
    for r in q1:
        e = e1.loc[r["job_type"]]
        check(f"Q1 {r['job_type']} jobs", r["completed_jobs"], e["completed_jobs"])
        check(f"Q1 {r['job_type']} actual hours", r["actual_hours"], e["actual_hours"], 0.005)
        check(f"Q1 {r['job_type']} median overrun", r["median_overrun_pct"], e["median_overrun_pct"], 0.05)
        check(f"Q1 {r['job_type']} share over", r["share_10pct_or_more_over"], e["share_10pct_or_more_over"], 0.05)

    e2 = exp["q2"]
    if len(q2) != len(e2):
        problems.append(f"Q2 rows: Snowflake {len(q2)}, recalculation {len(e2)}")
    for r in q2:
        e = e2.loc[(r["job_type"], r["fee_band"])]
        check(f"Q2 {r['job_type']} / {r['fee_band']} n", r["similar_jobs"], e["similar_jobs"])
        for col in ("median_actual_hours", "p80_actual_hours", "median_overrun_pct"):
            check(f"Q2 {r['job_type']} / {r['fee_band']} {col}", r[col], e[col], 0.05)

    e3 = exp["q3"]
    for r in q3:
        e = e3.loc[r["job_type"]]
        check(f"Q3 {r['job_type']} decided", r["decided_bids"], e["decided_bids"])
        check(f"Q3 {r['job_type']} win rate", r["win_rate_pct"], e["win_rate_pct"], 0.05)
        if r["verdict"] != e["verdict"]:
            problems.append(f"Q3 {r['job_type']} verdict: Snowflake '{r['verdict']}', recalculation '{e['verdict']}'")

    e3b = exp["q3b"]
    for r in q3b:
        if r["decided_bids"] == 0:
            continue
        e = e3b.loc[(r["job_type"], r["fee_band"])]
        check(f"Q3b {r['job_type']} / {r['fee_band']} win rate", r["win_rate_pct"], e["win_rate_pct"], 0.05)

    got_rej = {}
    for r in dq:
        got_rej[(r["source_table"], r["reason"])] = got_rej.get((r["source_table"], r["reason"]), 0) + r["rows_rejected"]
    exp_rej = exp["rejects"].to_dict()
    if got_rej != exp_rej:
        problems.append(f"Rejects differ: Snowflake {got_rej}, recalculation {exp_rej}")

    if problems:
        return False, f"{len(problems)} mismatches: " + "; ".join(problems[:5])
    return True, (f"Q1, Q2 ({len(q2)} rows), Q3, Q3b and the rejects summary all match "
                  "the pandas recalculation from the CSV files")


def cmd_usage(cur, local):
    if local:
        print("Credit usage exists on the real account only.")
        return
    use_pipeline_role(cur, local)
    data = rows(cur, """
        SELECT warehouse_name,
               MIN(start_time) AS first_hour,
               MAX(end_time)   AS last_hour,
               SUM(credits_used_compute)        AS compute_credits,
               SUM(credits_used_cloud_services) AS cloud_services_credits,
               SUM(credits_used)                AS total_credits
        FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
        WHERE warehouse_name = 'MARLOW_WH'
        GROUP BY warehouse_name""")
    show("Credits used by MARLOW_WH (Snowflake metering, can lag up to 3 hours)", data)
    save(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_usage", data)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["setup", "load", "check", "usage"])
    p.add_argument("batch", nargs="?", help="folder of one month's files, for load")
    p.add_argument("--local", action="store_true", help="use the local emulator, not Snowflake")
    args = p.parse_args()
    if args.command == "load" and not args.batch:
        p.error("load needs a batch folder, for example data/batch_2026_09")

    if args.local:
        import fakesnow
        db_path = Path(os.environ.get("MARLOW_LOCAL_DB", ROOT / ".local_db"))
        db_path.mkdir(parents=True, exist_ok=True)
        patcher = fakesnow.patch(db_path=str(db_path))
        patcher.__enter__()
    conn = connect(args.local)
    cur = conn.cursor()
    results = None
    try:
        if args.command == "setup":
            cmd_setup(cur, args.local)
        elif args.command == "load":
            results = cmd_load(cur, args.local, args.batch)
        elif args.command == "check":
            results = cmd_check(cur, args.local)
        elif args.command == "usage":
            cmd_usage(cur, args.local)
    finally:
        cur.close()
        conn.close()
    if results and any(status is False for _, status, _ in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
