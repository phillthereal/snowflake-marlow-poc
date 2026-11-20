"""Generate the fictional data for Marlow Advisory.

Marlow Advisory is a made-up 40-person consulting firm. Every row this script
writes is synthetic. Some patterns are planted on purpose (see PLANTED below)
so the proof of concept can be tested against an answer we already know.
Nothing here describes a real firm, client or person.

The script is seeded, so running it again writes exactly the same files.

Output:
  data/batch_2026_09/  bids.csv, jobs.csv, timesheets.csv
      Everything the firm's spreadsheets held on 30 Sep 2026.
  data/batch_2026_10/  bids.csv, jobs.csv, timesheets.csv
      What changed in October: new bids, bids decided in October,
      new jobs, jobs completed in October, October timesheets.
  data/planted.json    The planted patterns and the deliberate mess,
                       used by the local tests.

Usage: python generator/generate_data.py
"""

import csv
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20261120
FIRST_DAY = date(2024, 1, 1)
CUTOFF_SEP = date(2026, 9, 30)
CUTOFF_OCT = date(2026, 10, 31)
OUT = Path(__file__).resolve().parent.parent / "data"

# Planted patterns. win = base chance of winning a bid of this type.
# overrun = typical actual hours / priced hours for this type.
# Two types are planted as "won because underpriced": a high win rate
# combined with a large overrun (Commercial due diligence, Data and reporting audit).
PLANTED = {
    "Market assessment":        {"win": 0.42, "overrun": 0.96, "hours": (40, 160)},
    "Commercial due diligence": {"win": 0.66, "overrun": 1.34, "hours": (120, 400)},
    "Operating model review":   {"win": 0.36, "overrun": 1.04, "hours": (150, 500)},
    "Cost reduction review":    {"win": 0.32, "overrun": 1.12, "hours": (100, 350)},
    "Procurement support":      {"win": 0.56, "overrun": 0.92, "hours": (60, 250)},
    "Data and reporting audit": {"win": 0.62, "overrun": 1.29, "hours": (50, 200)},
}

# How each job type is spelled in the firm's bid register. The first label
# is the most common. The rest are real-world inconsistency.
LABELS = {
    "Market assessment": ["Market assessment", "Market Assessment", "market assessment "],
    "Commercial due diligence": ["Commercial due diligence", "Commercial DD", "CDD"],
    "Operating model review": ["Operating model review", "Op model review", "Operating Model Review"],
    "Cost reduction review": ["Cost reduction review", "Cost reduction", "Cost Reduction Review"],
    "Procurement support": ["Procurement support", "Procurement Support", "procurement"],
    "Data and reporting audit": ["Data and reporting audit", "Data & reporting audit", "Reporting audit"],
}

# 40 staff: 4 partners, 8 managers, 14 consultants, 14 analysts.
STAFF = (
    [(f"E{i:02d}", "Partner") for i in range(1, 5)]
    + [(f"E{i:02d}", "Manager") for i in range(5, 13)]
    + [(f"E{i:02d}", "Consultant") for i in range(13, 27)]
    + [(f"E{i:02d}", "Analyst") for i in range(27, 41)]
)
SENIOR = [s for s in STAFF if s[1] in ("Partner", "Manager")]
JUNIOR = [s for s in STAFF if s[1] in ("Consultant", "Analyst")]
PARTNERS = ["P1", "P2", "P3", "P4"]


def uk(d):
    return d.strftime("%d/%m/%Y")


def iso(d):
    return d.isoformat()


def friday_on_or_after(d):
    return d + timedelta(days=(4 - d.weekday()) % 7)


def fee_band_shift(fee):
    if fee < 10_000:
        return 0.05
    if fee < 25_000:
        return 0.0
    if fee < 50_000:
        return -0.05
    return -0.10


def halves(x):
    """Round to the nearest half hour."""
    return round(x * 2) / 2


def simulate(rng):
    """Simulate every bid, job and timesheet line from Jan 2024 to Oct 2026."""
    bids, jobs, lines = [], [], []
    types = list(PLANTED)
    d = FIRST_DAY
    bid_no = job_no = 0
    while d <= CUTOFF_OCT:
        for _ in range(rng.randint(7, 12)):  # bids submitted this month
            bid_no += 1
            jt = rng.choice(types)
            p = PLANTED[jt]
            submitted = d + timedelta(days=rng.randint(0, 27))
            if submitted > CUTOFF_OCT:
                continue
            priced = rng.randint(*p["hours"])
            rate = rng.uniform(95, 135)
            fee = round(priced * rate / 50) * 50
            decided = submitted + timedelta(days=rng.randint(14, 45))
            won = rng.random() < p["win"] + fee_band_shift(fee)
            labels = LABELS[jt]
            label = labels[0] if rng.random() < 0.7 else rng.choice(labels[1:])
            bid = {
                "bid_id": f"B-{bid_no:04d}",
                "client_code": f"C-{rng.randint(1, 140):03d}",
                "job_type": jt,
                "label": label,
                "submitted": submitted,
                "decided": decided,
                "fee": fee,
                "priced": priced,
                "won": won,
                "partner": rng.choice(PARTNERS),
            }
            bids.append(bid)
            if not won:
                continue
            job_no += 1
            start = decided + timedelta(days=rng.randint(7, 21))
            actual = halves(priced * p["overrun"] * math.exp(rng.gauss(0, 0.12)))
            weekly = rng.uniform(35, 80)
            weeks = max(1, round(actual / weekly))
            first_friday = friday_on_or_after(start)
            last_friday = first_friday + timedelta(weeks=weeks - 1)
            end = last_friday
            job = {
                "job_id": f"J-{job_no:04d}",
                "bid_id": bid["bid_id"],
                "start": start,
                "end": end,
                "actual": actual,
            }
            jobs.append(job)
            # Spread the actual hours over the weeks and over a small team.
            team = [rng.choice(SENIOR)] + rng.sample(JUNIOR, rng.randint(1, 3))
            per_week = [halves(actual / weeks)] * weeks
            per_week[-1] = halves(actual - sum(per_week[:-1]))
            for w, week_total in enumerate(per_week):
                friday = first_friday + timedelta(weeks=w)
                senior_share = halves(week_total * 0.12)
                rest = week_total - senior_share
                juniors = team[1:]
                split = [halves(rest / len(juniors))] * len(juniors)
                split[-1] = halves(rest - sum(split[:-1]))
                for (emp, grade), hrs in zip(team, [senior_share] + split):
                    if hrs <= 0:
                        continue
                    lines.append({
                        "week_ending": friday,
                        "employee_id": emp,
                        "grade": grade,
                        "job_id": job["job_id"],
                        "hours": hrs,
                    })
        # next month
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return bids, jobs, lines


def bid_row(b, cutoff, rng, fmt_iso=False):
    outcome = ""
    if b["decided"] <= cutoff:
        outcome = "Won" if b["won"] else "Lost"
    else:
        outcome = "Pending"
    fee = str(b["fee"])
    return {
        "bid_id": b["bid_id"],
        "client_code": b["client_code"],
        "job_type": b["label"],
        "submitted_on": iso(b["submitted"]) if fmt_iso else uk(b["submitted"]),
        "fee_quoted_gbp": fee,
        "priced_hours": str(b["priced"]),
        "outcome": outcome,
        "lead_partner": b["partner"],
    }


def job_row(j, cutoff):
    complete = j["end"] <= cutoff
    return {
        "job_id": j["job_id"],
        "bid_id": j["bid_id"],
        "start_date": uk(j["start"]),
        "end_date": uk(j["end"]) if complete else "",
        "status": "Complete" if complete else "Active",
    }


def line_row(t):
    return {
        "week_ending": uk(t["week_ending"]),
        "employee_id": t["employee_id"],
        "grade": t["grade"],
        "job_code": t["job_id"],
        "hours": f"{t['hours']:g}",
    }


def write(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


BID_FIELDS = ["bid_id", "client_code", "job_type", "submitted_on", "fee_quoted_gbp",
              "priced_hours", "outcome", "lead_partner"]
JOB_FIELDS = ["job_id", "bid_id", "start_date", "end_date", "status"]
LINE_FIELDS = ["week_ending", "employee_id", "grade", "job_code", "hours"]


def main():
    rng = random.Random(SEED)
    bids, jobs, lines = simulate(rng)
    mess = {"batch_2026_09": {}, "batch_2026_10": {}}

    # ---------------- Batch 1: everything known on 30 Sep 2026 ----------------
    b1 = [b for b in bids if b["submitted"] <= CUTOFF_SEP]
    bid_rows = []
    for b in b1:
        bid_rows.append(bid_row(b, CUTOFF_SEP, rng, fmt_iso=rng.random() < 0.05))
    by_id = {r["bid_id"]: r for r in bid_rows}

    # Mess: fees typed with a pound sign and comma.
    pound = rng.sample(bid_rows, 15)
    for r in pound:
        r["fee_quoted_gbp"] = f"£{int(r['fee_quoted_gbp']):,}"
    # Mess: outcomes typed inconsistently.
    for r in rng.sample([r for r in bid_rows if r["outcome"] in ("Won", "Lost")], 12):
        r["outcome"] = rng.choice([r["outcome"].lower(), r["outcome"] + " ", r["outcome"].upper()])
    # Mess: lost bids with no job type, and lost bids with a label nobody mapped.
    lost = [r for r in bid_rows if r["outcome"].strip().lower() == "lost"
            and r not in pound]
    picks = rng.sample(lost, 8)
    for r in picks[:3]:
        r["job_type"] = ""
    for r in picks[3:5]:
        r["job_type"] = "Workshop facilitation"
    # Mess: decided lost bids with no outcome recorded.
    for r in picks[5:8]:
        r["outcome"] = ""
    mess["batch_2026_09"]["bids_job_type_missing"] = [r["bid_id"] for r in picks[:3]]
    mess["batch_2026_09"]["bids_job_type_unrecognised"] = [r["bid_id"] for r in picks[3:5]]
    mess["batch_2026_09"]["bids_no_outcome"] = [r["bid_id"] for r in picks[5:8]]
    mess["batch_2026_09"]["bids_pound_formatted"] = len(pound)
    # Mess: one bid pasted twice.
    dup_bid = dict(rng.choice([r for r in bid_rows if r["outcome"] == "Won"]))
    bid_rows.insert(bid_rows.index(by_id[dup_bid["bid_id"]]) + 1, dup_bid)
    mess["batch_2026_09"]["bids_duplicated"] = [dup_bid["bid_id"]]

    j1 = [j for j in jobs if j["start"] <= CUTOFF_SEP]
    job_rows = [job_row(j, CUTOFF_SEP) for j in j1]
    # Mess: one job pasted twice.
    dup_job = dict(rng.choice([r for r in job_rows if r["status"] == "Complete"]))
    job_rows.insert([r["job_id"] for r in job_rows].index(dup_job["job_id"]) + 1, dup_job)
    # Mess: a job whose bid number does not exist.
    orphan = {"job_id": "J-0999", "bid_id": "B-9999", "start_date": "12/05/2025",
              "end_date": "27/06/2025", "status": "Complete"}
    job_rows.append(orphan)
    mess["batch_2026_09"]["jobs_duplicated"] = [dup_job["job_id"]]
    mess["batch_2026_09"]["jobs_bid_not_found"] = ["J-0999"]

    l1 = [t for t in lines if t["week_ending"] <= CUTOFF_SEP]
    line_rows = [line_row(t) for t in l1]
    extra = []
    # Mess: admin time logged with no job code.
    for _ in range(24):
        emp, grade = rng.choice(STAFF)
        wk = friday_on_or_after(FIRST_DAY + timedelta(days=rng.randint(0, 990)))
        extra.append({"week_ending": uk(wk), "employee_id": emp, "grade": grade,
                      "job_code": "", "hours": f"{rng.choice([2, 3.5, 4, 6, 7.5]):g}"})
    # Mess: job codes mistyped (letter O for zero).
    for _ in range(3):
        t = rng.choice(line_rows)
        extra.append({**t, "job_code": t["job_code"].replace("0", "O", 1)})
    # Mess: correction lines with negative hours.
    for _ in range(4):
        t = rng.choice(line_rows)
        extra.append({**t, "hours": f"-{rng.choice([2, 4, 7.5]):g}"})
    # Mess: hours typed with a unit.
    for _ in range(2):
        t = rng.choice(line_rows)
        extra.append({**t, "hours": t["hours"] + "h"})
    # Mess: lines exported twice.
    dups = [dict(t) for t in rng.sample(line_rows, 6)]
    # Lines for the orphan job (rejected with it).
    for wk in ("16/05/2025", "23/05/2025", "30/05/2025"):
        extra.append({"week_ending": wk, "employee_id": "E15", "grade": "Consultant",
                      "job_code": "J-0999", "hours": "20"})
    all_lines = line_rows + extra + dups
    rng.shuffle(all_lines)
    all_lines.sort(key=lambda r: (r["week_ending"][6:], r["week_ending"][3:5], r["week_ending"][:2]))
    mess["batch_2026_09"]["timesheets"] = {
        "no_job_code": 24, "job_code_mistyped": 3, "negative_hours": 4,
        "hours_not_a_number": 2, "duplicated_lines": 6, "orphan_job_lines": 3,
    }

    write(OUT / "batch_2026_09" / "bids.csv", bid_rows, BID_FIELDS)
    write(OUT / "batch_2026_09" / "jobs.csv", job_rows, JOB_FIELDS)
    write(OUT / "batch_2026_09" / "timesheets.csv", all_lines, LINE_FIELDS)

    # ---------------- Batch 2: what changed in October 2026 ----------------
    new_bids = [b for b in bids if CUTOFF_SEP < b["submitted"] <= CUTOFF_OCT]
    decided_in_oct = [b for b in bids if b["submitted"] <= CUTOFF_SEP
                      and CUTOFF_SEP < b["decided"] <= CUTOFF_OCT]
    bid_rows2 = [bid_row(b, CUTOFF_OCT, rng) for b in decided_in_oct + new_bids]
    new_jobs = [j for j in jobs if CUTOFF_SEP < j["start"] <= CUTOFF_OCT]
    done_in_oct = [j for j in jobs if j["start"] <= CUTOFF_SEP
                   and CUTOFF_SEP < j["end"] <= CUTOFF_OCT]
    job_rows2 = [job_row(j, CUTOFF_OCT) for j in done_in_oct + new_jobs]
    l2 = [line_row(t) for t in lines if CUTOFF_SEP < t["week_ending"] <= CUTOFF_OCT]
    for _ in range(2):
        emp, grade = rng.choice(STAFF)
        l2.append({"week_ending": "16/10/2026", "employee_id": emp, "grade": grade,
                   "job_code": "", "hours": "3"})
    l2.append(dict(rng.choice(l2[:-2])))  # one line exported twice
    mess["batch_2026_10"] = {
        "bids_new": len(new_bids), "bids_decided_in_october": len(decided_in_oct),
        "jobs_new": len(new_jobs), "jobs_completed_in_october": len(done_in_oct),
        "timesheets": {"no_job_code": 2, "duplicated_lines": 1},
    }
    write(OUT / "batch_2026_10" / "bids.csv", bid_rows2, BID_FIELDS)
    write(OUT / "batch_2026_10" / "jobs.csv", job_rows2, JOB_FIELDS)
    write(OUT / "batch_2026_10" / "timesheets.csv", l2, LINE_FIELDS)

    planted = {
        "note": "Synthetic data. Patterns planted on purpose so the build can be tested.",
        "job_types": {k: {"win_rate": v["win"], "overrun_factor": v["overrun"]}
                      for k, v in PLANTED.items()},
        "expected_winning_on_price": ["Commercial due diligence", "Data and reporting audit"],
        "mess": mess,
    }
    (OUT / "planted.json").write_text(json.dumps(planted, indent=2))
    print(f"bids {len(bid_rows)}+{len(bid_rows2)}, jobs {len(job_rows)}+{len(job_rows2)}, "
          f"timesheet lines {len(all_lines)}+{len(l2)}")


if __name__ == "__main__":
    main()
