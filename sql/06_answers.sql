-- 06_answers.sql
-- The views the operations director queries. One per question, plus a
-- data quality summary. All of them read from CLEAN, never from RAW.
--
-- Agreed assumptions (to confirm with the buyer):
--   * "Overrun" is judged on completed jobs only.
--   * A job type "overruns" when its typical (median) job is 10% or more over.
--   * Win rate counts decided bids only: Won and Lost. Pending and
--     "No outcome recorded" are left out.
--   * "Similar past jobs" means same job type and same fee band. When fewer
--     than 5 such jobs exist, use the row for the whole job type.

USE DATABASE MARLOW;

-- Q1. Which job types overrun their priced hours?
CREATE OR REPLACE VIEW ANSWERS.Q1_OVERRUN_BY_JOB_TYPE AS
SELECT
  job_type,
  COUNT(*)                                              AS completed_jobs,
  SUM(priced_hours)                                     AS priced_hours,
  SUM(actual_hours)                                     AS actual_hours,
  SUM(actual_hours) - SUM(priced_hours)                 AS hours_over_price,
  ROUND(MEDIAN(overrun_pct) * 100, 1)                   AS median_overrun_pct,
  COUNT_IF(overrun_pct >= 0.10)                         AS jobs_10pct_or_more_over,
  ROUND(COUNT_IF(overrun_pct >= 0.10) / COUNT(*) * 100, 1) AS share_10pct_or_more_over
FROM CLEAN.JOB_RESULTS
GROUP BY job_type;

-- Q2. For a new bid, what did similar past jobs actually take?
-- One row per job type and fee band, plus one row per job type across all bands.
-- p80_actual_hours: 8 in 10 similar past jobs finished within this many hours.
CREATE OR REPLACE VIEW ANSWERS.Q2_BID_BENCHMARKS AS
WITH by_band AS (
  SELECT
    job_type,
    fee_band,
    fee_band_order,
    COUNT(*)                                                       AS similar_jobs,
    MEDIAN(priced_hours)                                           AS median_priced_hours,
    MEDIAN(actual_hours)                                           AS median_actual_hours,
    PERCENTILE_CONT(0.8) WITHIN GROUP (ORDER BY actual_hours)      AS p80_actual_hours,
    MEDIAN(overrun_pct)                                            AS median_overrun
  FROM CLEAN.JOB_RESULTS
  GROUP BY job_type, fee_band, fee_band_order
),
all_bands AS (
  SELECT
    job_type,
    'All fee bands'                                                AS fee_band,
    9                                                              AS fee_band_order,
    COUNT(*)                                                       AS similar_jobs,
    MEDIAN(priced_hours)                                           AS median_priced_hours,
    MEDIAN(actual_hours)                                           AS median_actual_hours,
    PERCENTILE_CONT(0.8) WITHIN GROUP (ORDER BY actual_hours)      AS p80_actual_hours,
    MEDIAN(overrun_pct)                                            AS median_overrun
  FROM CLEAN.JOB_RESULTS
  GROUP BY job_type
),
combined AS (
  SELECT * FROM by_band
  UNION ALL
  SELECT * FROM all_bands
)
SELECT
  job_type,
  fee_band,
  fee_band_order,
  similar_jobs,
  ROUND(median_priced_hours, 1)   AS median_priced_hours,
  ROUND(median_actual_hours, 1)   AS median_actual_hours,
  ROUND(p80_actual_hours, 1)      AS p80_actual_hours,
  ROUND(median_overrun * 100, 1)  AS median_overrun_pct,
  IFF(similar_jobs >= 5, 'Enough past jobs', 'Fewer than 5 past jobs: use the All fee bands row') AS sample_note
FROM combined;

-- Q3. Which job types do we win because we underprice them?
-- Puts win rate (from bids) next to overrun (from completed jobs).
-- A type that wins more often than the firm average AND overruns by 10% or
-- more is likely winning on price.
CREATE OR REPLACE VIEW ANSWERS.Q3_WIN_RATE_VS_OVERRUN AS
WITH wins AS (
  SELECT
    job_type,
    COUNT_IF(outcome IN ('Won', 'Lost'))  AS decided_bids,
    COUNT_IF(outcome = 'Won')             AS won_bids
  FROM CLEAN.BIDS
  GROUP BY job_type
),
firm AS (
  SELECT SUM(won_bids) / SUM(decided_bids) AS firm_win_rate FROM wins
),
overrun AS (
  SELECT job_type, MEDIAN(overrun_pct) AS median_overrun, COUNT(*) AS completed_jobs
  FROM CLEAN.JOB_RESULTS
  GROUP BY job_type
)
SELECT
  w.job_type,
  w.decided_bids,
  w.won_bids,
  ROUND(w.won_bids / w.decided_bids * 100, 1)  AS win_rate_pct,
  ROUND(f.firm_win_rate * 100, 1)              AS firm_win_rate_pct,
  o.completed_jobs,
  ROUND(o.median_overrun * 100, 1)             AS median_overrun_pct,
  CASE
    WHEN w.won_bids / w.decided_bids > f.firm_win_rate AND o.median_overrun >= 0.10
      THEN 'Winning on price: wins often and overruns'
    WHEN o.median_overrun >= 0.10
      THEN 'Overruns and wins less often'
    WHEN w.won_bids / w.decided_bids > f.firm_win_rate
      THEN 'Wins often and delivers within price'
    ELSE 'Wins less often, delivers within price'
  END                                          AS verdict
FROM wins w
CROSS JOIN firm f
LEFT JOIN overrun o
  ON o.job_type = w.job_type;

-- Q3b. The original win-rate question: by job type and fee band.
CREATE OR REPLACE VIEW ANSWERS.Q3B_WIN_RATE_BY_FEE_BAND AS
SELECT
  job_type,
  fee_band,
  fee_band_order,
  COUNT_IF(outcome IN ('Won', 'Lost'))  AS decided_bids,
  COUNT_IF(outcome = 'Won')             AS won_bids,
  ROUND(COUNT_IF(outcome = 'Won') / NULLIF(COUNT_IF(outcome IN ('Won', 'Lost')), 0) * 100, 1) AS win_rate_pct
FROM CLEAN.BIDS
GROUP BY job_type, fee_band, fee_band_order;

-- Data quality summary for the director: counts only. The row-level rejects
-- list stays with the admin, because timesheet rejects show individual people.
CREATE OR REPLACE VIEW ANSWERS.DATA_QUALITY AS
SELECT
  source_table,
  load_batch,
  reason,
  COUNT(*) AS rows_rejected
FROM CLEAN.REJECTS
GROUP BY source_table, load_batch, reason;
