"""Independent check (criterion 8).

Recomputes every answer straight from the CSV files with pandas, without
Snowflake. run.py compares these numbers with what the Snowflake views return.
The rules are written out again here on purpose, from the success criteria,
not copied from the SQL, so a mistake in one shows up as a mismatch.

Usage on its own: python check/independent_check.py data/batch_2026_09 [data/batch_2026_10]
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

JOB_TYPE_MAP = {
    "MARKET ASSESSMENT": "Market assessment",
    "COMMERCIAL DUE DILIGENCE": "Commercial due diligence",
    "COMMERCIAL DD": "Commercial due diligence",
    "CDD": "Commercial due diligence",
    "OPERATING MODEL REVIEW": "Operating model review",
    "OP MODEL REVIEW": "Operating model review",
    "COST REDUCTION REVIEW": "Cost reduction review",
    "COST REDUCTION": "Cost reduction review",
    "PROCUREMENT SUPPORT": "Procurement support",
    "PROCUREMENT": "Procurement support",
    "DATA AND REPORTING AUDIT": "Data and reporting audit",
    "DATA & REPORTING AUDIT": "Data and reporting audit",
    "REPORTING AUDIT": "Data and reporting audit",
}
FEE_BANDS = [(10_000, "Under £10k", 1), (25_000, "£10k to £25k", 2),
             (50_000, "£25k to £50k", 3), (float("inf"), "£50k and over", 4)]


def blank(v):
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def num(v):
    if blank(v):
        return None
    try:
        return float(str(v).replace("£", "").replace(",", ""))
    except ValueError:
        return None


def plain_num(v):
    if blank(v):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def day(v):
    if blank(v):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v), fmt).date()
        except ValueError:
            pass
    return None


def read_batches(batch_dirs):
    """Read every batch's three files, tagging rows with batch and row number."""
    out = {}
    for name in ("bids", "jobs", "timesheets"):
        frames = []
        for d in batch_dirs:
            d = Path(d)
            df = pd.read_csv(d / f"{name}.csv", dtype=str, keep_default_na=False)
            df["load_batch"] = d.name
            df["source_row"] = range(1, len(df) + 1)
            frames.append(df)
        out[name] = pd.concat(frames, ignore_index=True)
    return out


def keep_latest(df, key_cols):
    """Among rows with no rule broken: newest batch wins; repeats in the same
    batch are duplicates; versions from older batches are superseded."""
    ok = df[df["reason"].isna()].copy()
    ok = ok.sort_values(["load_batch", "source_row"], ascending=False)
    ok["rank"] = ok.groupby(key_cols, dropna=False).cumcount() + 1
    newest = ok.groupby(key_cols, dropna=False)["load_batch"].transform("max")
    dup = (ok["rank"] > 1) & (ok["load_batch"] == newest)
    sup = (ok["rank"] > 1) & (ok["load_batch"] < newest)
    df.loc[ok.index[dup], "reason"] = "DUP"
    df["superseded"] = False
    df.loc[ok.index[sup], "superseded"] = True
    return df


def compute(batch_dirs):
    raw = read_batches(batch_dirs)

    # ---- bids
    b = raw["bids"].copy()
    b["job_type_c"] = b["job_type"].map(lambda v: JOB_TYPE_MAP.get(str(v).strip().upper()))
    b["fee"] = b["fee_quoted_gbp"].map(num)
    b["priced"] = b["priced_hours"].map(plain_num)
    b["submitted"] = b["submitted_on"].map(day)
    b["outcome_c"] = b["outcome"].map(lambda v: {"WON": "Won", "LOST": "Lost", "PENDING": "Pending"}
                                      .get(str(v).strip().upper(), "No outcome recorded"))

    def bid_rule(r):
        if blank(r.bid_id):
            return "Bid ID missing"
        if blank(r.job_type):
            return "Job type missing"
        if pd.isna(r.job_type_c):
            return "Job type not recognised"
        if pd.isna(r.fee) or r.fee <= 0:
            return "Fee missing or not a number"
        if pd.isna(r.priced) or r.priced <= 0:
            return "Priced hours missing or not a number"
        if pd.isna(r.submitted):
            return "Submitted date unreadable"
        return None

    b["key"] = b["bid_id"].str.strip()
    b["reason"] = [bid_rule(r) for r in b.itertuples()]
    b = keep_latest(b, ["key"])
    b["reason"] = b["reason"].replace("DUP", "Duplicate bid in the same file")
    clean_b = b[b["reason"].isna() & ~b["superseded"]].copy()

    def band(fee):
        for limit, label, order in FEE_BANDS:
            if fee < limit:
                return label, order

    clean_b["fee_band"] = clean_b["fee"].map(lambda f: band(f)[0])
    clean_b["fee_band_order"] = clean_b["fee"].map(lambda f: band(f)[1])
    bid_ids = set(clean_b["key"])

    # ---- jobs
    j = raw["jobs"].copy()
    j["key"] = j["job_id"].str.strip()
    j["start"] = j["start_date"].map(day)
    j["end"] = j["end_date"].map(day)
    j["status_c"] = j["status"].map(lambda v: {"COMPLETE": "Complete", "ACTIVE": "Active"}
                                    .get(str(v).strip().upper()))

    def job_rule(r):
        if blank(r.job_id):
            return "Job ID missing"
        if str(r.bid_id).strip() not in bid_ids:
            return "Bid not found or rejected"
        if pd.isna(r.status_c):
            return "Status not recognised"
        if pd.isna(r.start):
            return "Start date unreadable"
        if r.status_c == "Complete" and pd.isna(r.end):
            return "Complete job has no end date"
        return None

    j["reason"] = [job_rule(r) for r in j.itertuples()]
    j = keep_latest(j, ["key"])
    j["reason"] = j["reason"].replace("DUP", "Duplicate job in the same file")
    clean_j = j[j["reason"].isna() & ~j["superseded"]].copy()
    job_ids = set(clean_j["key"])

    # ---- timesheets
    t = raw["timesheets"].copy()
    t["hrs"] = t["hours"].map(plain_num)
    t["week"] = t["week_ending"].map(day)
    t["job_key"] = t["job_code"].str.strip()
    t["emp"] = t["employee_id"].str.strip()

    def line_rule(r):
        if blank(r.job_code):
            return "No job code"
        if pd.isna(r.hrs):
            return "Hours not a number"
        if r.hrs <= 0:
            return "Hours zero or negative"
        if r.job_key not in job_ids:
            return "Job not found or rejected"
        if pd.isna(r.week):
            return "Week ending unreadable"
        if blank(r.employee_id):
            return "Employee ID missing"
        return None

    t["reason"] = [line_rule(r) for r in t.itertuples()]
    t = keep_latest(t, ["week", "emp", "job_key"])
    t["reason"] = t["reason"].replace("DUP", "Duplicate timesheet line")
    clean_t = t[t["reason"].isna() & ~t["superseded"]].copy()

    # ---- job results (completed jobs)
    hours = clean_t.groupby("job_key")["hrs"].sum()
    done = clean_j[clean_j["status_c"] == "Complete"].copy()
    done["bid_key"] = done["bid_id"].str.strip()
    done = done.merge(clean_b, left_on="bid_key", right_on="key", suffixes=("", "_bid"))
    done["actual"] = done["key"].map(hours).fillna(0.0)
    done["overrun"] = done["actual"] / done["priced"] - 1
    jr = done[["key", "job_type_c", "fee_band", "fee_band_order", "priced", "actual", "overrun"]]

    # ---- Q1
    q1 = jr.groupby("job_type_c").agg(
        completed_jobs=("key", "count"),
        priced_hours=("priced", "sum"),
        actual_hours=("actual", "sum"),
        median_overrun_pct=("overrun", lambda s: s.median() * 100),
        jobs_10pct_or_more_over=("overrun", lambda s: int((s >= 0.10).sum())),
    )
    q1["hours_over_price"] = q1["actual_hours"] - q1["priced_hours"]
    q1["share_10pct_or_more_over"] = q1["jobs_10pct_or_more_over"] / q1["completed_jobs"] * 100

    # ---- Q2
    def bench(g):
        return pd.Series({
            "similar_jobs": len(g),
            "median_priced_hours": g["priced"].median(),
            "median_actual_hours": g["actual"].median(),
            "p80_actual_hours": g["actual"].quantile(0.8),
            "median_overrun_pct": g["overrun"].median() * 100,
        })

    q2a = jr.groupby(["job_type_c", "fee_band"]).apply(bench, include_groups=False)
    q2b = jr.groupby("job_type_c").apply(bench, include_groups=False)
    q2b["fee_band"] = "All fee bands"
    q2b = q2b.set_index("fee_band", append=True)
    q2 = pd.concat([q2a, q2b])

    # ---- Q3
    decided = clean_b[clean_b["outcome_c"].isin(["Won", "Lost"])]
    # Every job type with a clean bid gets a row, even if none are decided yet.
    wins = clean_b.groupby("job_type_c").agg(
        decided_bids=("outcome_c", lambda s: int(s.isin(["Won", "Lost"]).sum())),
        won_bids=("outcome_c", lambda s: int((s == "Won").sum())))
    firm = wins["won_bids"].sum() / wins["decided_bids"].sum()
    # No decided bids means no win rate (blank), not a division by zero.
    wins["win_rate_pct"] = wins["won_bids"] / wins["decided_bids"].where(wins["decided_bids"] > 0) * 100
    wins["firm_win_rate_pct"] = firm * 100
    med = jr.groupby("job_type_c")["overrun"].median()
    wins["median_overrun_pct"] = med * 100

    def verdict(r):
        if r.decided_bids == 0:
            return "No decided bids yet"
        if pd.isna(r.median_overrun_pct):
            return "No completed jobs yet"
        over = r.median_overrun_pct >= 10
        wins_often = r.win_rate_pct > r.firm_win_rate_pct
        if wins_often and over:
            return "Winning on price: wins often and overruns"
        if over:
            return "Overruns and wins less often"
        if wins_often:
            return "Wins often and delivers within price"
        return "Wins less often, delivers within price"

    wins["verdict"] = [verdict(r) for r in wins.itertuples()]

    # ---- Q3b
    q3b = decided.groupby(["job_type_c", "fee_band"]).agg(
        decided_bids=("key", "count"),
        won_bids=("outcome_c", lambda s: int((s == "Won").sum())))
    q3b["win_rate_pct"] = q3b["won_bids"] / q3b["decided_bids"] * 100

    # ---- rejects summary and file totals
    rejects = pd.concat([
        b.loc[b["reason"].notna(), ["reason"]].assign(source_table="bids"),
        j.loc[j["reason"].notna(), ["reason"]].assign(source_table="jobs"),
        t.loc[t["reason"].notna(), ["reason"]].assign(source_table="timesheets"),
    ]).groupby(["source_table", "reason"]).size()

    return {
        "q1": q1, "q2": q2, "q3": wins, "q3b": q3b, "rejects": rejects,
        "clean_counts": {"bids": len(clean_b), "jobs": len(clean_j), "timesheets": len(clean_t)},
        "superseded": {"bids": int(b["superseded"].sum()), "jobs": int(j["superseded"].sum()),
                       "timesheets": int(t["superseded"].sum())},
    }


def file_totals(batch_dir):
    """Row counts and parseable totals straight from one batch's files (criteria 1 and 2)."""
    raw = read_batches([batch_dir])
    fees = [v for v in raw["bids"]["fee_quoted_gbp"].map(num) if pd.notna(v)]
    priced = [v for v in raw["bids"]["priced_hours"].map(plain_num) if pd.notna(v)]
    hrs = [v for v in raw["timesheets"]["hours"].map(plain_num) if pd.notna(v)]
    return {
        "rows": {k: len(v) for k, v in raw.items()},
        "fee_total": round(sum(fees), 2),
        "priced_hours_total": round(sum(priced), 2),
        "timesheet_hours_total": round(sum(hrs), 2),
    }


if __name__ == "__main__":
    res = compute(sys.argv[1:])
    pd.set_option("display.width", 160)
    for k in ("q1", "q3"):
        print(f"\n{k.upper()}\n", res[k].round(1))
    print("\nREJECTS\n", res["rejects"])
