-- 05_clean.sql
-- Turn the raw text into typed, checked rows. Rebuilt in full on every run,
-- so a new month's files change the results with no manual edits.
--
-- Every raw row ends up in exactly one of three places:
--   clean        it passed every rule and is the latest version of that record
--   rejected     it broke a rule; the rejects list says which rule, file and row
--   superseded   a later month's file sent a newer version of the same record
-- Criterion 2 checks that raw = clean + rejected + superseded, so nothing vanishes.
--
-- The pattern is the same for all three tables:
--   1. parsed:  convert text to numbers and dates. TRY_ functions return NULL
--               instead of failing when a value can't be read.
--   2. ruled:   give each row the first rule it breaks, or NULL if none.
--   3. ranked:  among rows that pass, number the versions of each record,
--               newest month first.
--   4. final:   decide clean, duplicate (rejected) or superseded.

USE DATABASE MARLOW;

-- ============================== BIDS ==============================

CREATE OR REPLACE VIEW CLEAN.BIDS_CHECKED AS
WITH parsed AS (
  SELECT
    r.*,
    NULLIF(TRIM(r.bid_id), '') AS bid_key,
    m.job_type,
    -- "£12,500" becomes 12500: strip the pound sign and the comma, then read the number.
    TRY_TO_NUMBER(REPLACE(REPLACE(r.fee_quoted_gbp, '£', ''), ',', ''), 12, 2) AS fee_gbp,
    TRY_TO_NUMBER(r.priced_hours, 10, 2) AS priced_hrs,
    -- UK dates first; a few rows were saved as ISO dates (2025-03-14).
    COALESCE(TRY_TO_DATE(r.submitted_on, 'DD/MM/YYYY'),
             TRY_TO_DATE(r.submitted_on, 'YYYY-MM-DD')) AS submitted_date,
    CASE UPPER(TRIM(r.outcome))
      WHEN 'WON'     THEN 'Won'
      WHEN 'LOST'    THEN 'Lost'
      WHEN 'PENDING' THEN 'Pending'
      ELSE 'No outcome recorded'
    END AS outcome_clean
  FROM RAW.BIDS r
  LEFT JOIN REF.JOB_TYPE_MAP m
    ON m.label_key = UPPER(TRIM(r.job_type_label))
),
ruled AS (
  SELECT
    p.*,
    CASE
      WHEN bid_key IS NULL                                  THEN 'Bid ID missing'
      WHEN NULLIF(TRIM(job_type_label), '') IS NULL         THEN 'Job type missing'
      WHEN job_type IS NULL                                 THEN 'Job type not recognised'
      WHEN fee_gbp IS NULL OR fee_gbp <= 0                  THEN 'Fee missing or not a number'
      WHEN priced_hrs IS NULL OR priced_hrs <= 0            THEN 'Priced hours missing or not a number'
      WHEN submitted_date IS NULL                           THEN 'Submitted date unreadable'
    END AS rule_broken
  FROM parsed p
),
ranked AS (
  SELECT
    u.*,
    -- Rows that broke a rule are numbered separately, so they never push a good row aside.
    ROW_NUMBER() OVER (PARTITION BY bid_key, rule_broken IS NULL
                       ORDER BY load_batch DESC, source_row DESC) AS version_rank,
    MAX(load_batch) OVER (PARTITION BY bid_key, rule_broken IS NULL) AS newest_batch
  FROM ruled u
)
SELECT
  k.*,
  CASE
    WHEN rule_broken IS NOT NULL THEN rule_broken
    WHEN version_rank > 1 AND load_batch = newest_batch THEN 'Duplicate bid in the same file'
  END AS reject_reason,
  (rule_broken IS NULL AND version_rank > 1 AND load_batch < newest_batch) AS is_superseded
FROM ranked k;

CREATE OR REPLACE TABLE CLEAN.BIDS AS
SELECT
  bid_key         AS bid_id,
  client_code,
  job_type,
  submitted_date,
  fee_gbp,
  CASE
    WHEN fee_gbp < 10000 THEN 'Under £10k'
    WHEN fee_gbp < 25000 THEN '£10k to £25k'
    WHEN fee_gbp < 50000 THEN '£25k to £50k'
    ELSE '£50k and over'
  END             AS fee_band,
  CASE
    WHEN fee_gbp < 10000 THEN 1
    WHEN fee_gbp < 25000 THEN 2
    WHEN fee_gbp < 50000 THEN 3
    ELSE 4
  END             AS fee_band_order,
  priced_hrs      AS priced_hours,
  outcome_clean   AS outcome,
  lead_partner,
  load_batch,
  source_file,
  source_row
FROM CLEAN.BIDS_CHECKED
WHERE reject_reason IS NULL AND NOT is_superseded;

-- ============================== JOBS ==============================
-- A job is only kept if its bid made it into CLEAN.BIDS.

CREATE OR REPLACE VIEW CLEAN.JOBS_CHECKED AS
WITH parsed AS (
  SELECT
    r.*,
    NULLIF(TRIM(r.job_id), '') AS job_key,
    b.bid_id AS matched_bid,
    COALESCE(TRY_TO_DATE(r.start_date, 'DD/MM/YYYY'), TRY_TO_DATE(r.start_date, 'YYYY-MM-DD')) AS start_dt,
    COALESCE(TRY_TO_DATE(r.end_date, 'DD/MM/YYYY'),   TRY_TO_DATE(r.end_date, 'YYYY-MM-DD'))   AS end_dt,
    CASE UPPER(TRIM(r.status))
      WHEN 'COMPLETE' THEN 'Complete'
      WHEN 'ACTIVE'   THEN 'Active'
    END AS status_clean
  FROM RAW.JOBS r
  LEFT JOIN CLEAN.BIDS b
    ON b.bid_id = TRIM(r.bid_id)
),
ruled AS (
  SELECT
    p.*,
    CASE
      WHEN job_key IS NULL                                   THEN 'Job ID missing'
      WHEN matched_bid IS NULL                               THEN 'Bid not found or rejected'
      WHEN status_clean IS NULL                              THEN 'Status not recognised'
      WHEN start_dt IS NULL                                  THEN 'Start date unreadable'
      WHEN status_clean = 'Complete' AND end_dt IS NULL      THEN 'Complete job has no end date'
    END AS rule_broken
  FROM parsed p
),
ranked AS (
  SELECT
    u.*,
    ROW_NUMBER() OVER (PARTITION BY job_key, rule_broken IS NULL
                       ORDER BY load_batch DESC, source_row DESC) AS version_rank,
    MAX(load_batch) OVER (PARTITION BY job_key, rule_broken IS NULL) AS newest_batch
  FROM ruled u
)
SELECT
  k.*,
  CASE
    WHEN rule_broken IS NOT NULL THEN rule_broken
    WHEN version_rank > 1 AND load_batch = newest_batch THEN 'Duplicate job in the same file'
  END AS reject_reason,
  (rule_broken IS NULL AND version_rank > 1 AND load_batch < newest_batch) AS is_superseded
FROM ranked k;

CREATE OR REPLACE TABLE CLEAN.JOBS AS
SELECT
  job_key       AS job_id,
  matched_bid   AS bid_id,
  start_dt      AS start_date,
  end_dt        AS end_date,
  status_clean  AS status,
  load_batch,
  source_file,
  source_row
FROM CLEAN.JOBS_CHECKED
WHERE reject_reason IS NULL AND NOT is_superseded;

-- ============================ TIMESHEETS ============================
-- One line per person, per job, per week. A line is only kept if its job
-- made it into CLEAN.JOBS.

CREATE OR REPLACE VIEW CLEAN.TIMESHEETS_CHECKED AS
WITH parsed AS (
  SELECT
    r.*,
    NULLIF(TRIM(r.job_code), '')    AS job_key,
    NULLIF(TRIM(r.employee_id), '') AS employee_key,
    j.job_id AS matched_job,
    TRY_TO_NUMBER(r.hours, 10, 2) AS hrs,
    COALESCE(TRY_TO_DATE(r.week_ending, 'DD/MM/YYYY'), TRY_TO_DATE(r.week_ending, 'YYYY-MM-DD')) AS week_dt
  FROM RAW.TIMESHEETS r
  LEFT JOIN CLEAN.JOBS j
    ON j.job_id = TRIM(r.job_code)
),
ruled AS (
  SELECT
    p.*,
    CASE
      WHEN job_key IS NULL          THEN 'No job code'
      WHEN hrs IS NULL              THEN 'Hours not a number'
      WHEN hrs <= 0                 THEN 'Hours zero or negative'
      WHEN matched_job IS NULL      THEN 'Job not found or rejected'
      WHEN week_dt IS NULL          THEN 'Week ending unreadable'
      WHEN employee_key IS NULL     THEN 'Employee ID missing'
    END AS rule_broken
  FROM parsed p
),
ranked AS (
  SELECT
    u.*,
    ROW_NUMBER() OVER (PARTITION BY week_dt, employee_key, job_key, rule_broken IS NULL
                       ORDER BY load_batch DESC, source_row DESC) AS version_rank,
    MAX(load_batch) OVER (PARTITION BY week_dt, employee_key, job_key, rule_broken IS NULL) AS newest_batch
  FROM ruled u
)
SELECT
  k.*,
  CASE
    WHEN rule_broken IS NOT NULL THEN rule_broken
    WHEN version_rank > 1 AND load_batch = newest_batch THEN 'Duplicate timesheet line'
  END AS reject_reason,
  (rule_broken IS NULL AND version_rank > 1 AND load_batch < newest_batch) AS is_superseded
FROM ranked k;

CREATE OR REPLACE TABLE CLEAN.TIMESHEETS AS
SELECT
  week_dt       AS week_ending,
  employee_key  AS employee_id,
  grade,
  matched_job   AS job_id,
  hrs           AS hours,
  load_batch,
  source_file,
  source_row
FROM CLEAN.TIMESHEETS_CHECKED
WHERE reject_reason IS NULL AND NOT is_superseded;

-- ============================ REJECTS LIST ============================
-- One list for all three files. spreadsheet_row is the row number you would
-- see in Excel, with the header as row 1. Snowflake can count rows from the
-- header or from the first data row depending on settings; the IFF lines it up.

CREATE OR REPLACE TABLE CLEAN.REJECTS AS
WITH all_rejects AS (
  SELECT 'bids' AS source_table, load_batch, source_file, source_row,
         bid_id AS record_id, reject_reason AS reason,
         CASE reject_reason
           WHEN 'Job type not recognised' THEN job_type_label
           WHEN 'Fee missing or not a number' THEN fee_quoted_gbp
           WHEN 'Priced hours missing or not a number' THEN priced_hours
           WHEN 'Submitted date unreadable' THEN submitted_on
         END AS value_found
  FROM CLEAN.BIDS_CHECKED WHERE reject_reason IS NOT NULL
  UNION ALL
  SELECT 'jobs', load_batch, source_file, source_row,
         job_id, reject_reason,
         CASE reject_reason
           WHEN 'Bid not found or rejected' THEN bid_id
           WHEN 'Status not recognised' THEN status
           WHEN 'Start date unreadable' THEN start_date
         END
  FROM CLEAN.JOBS_CHECKED WHERE reject_reason IS NOT NULL
  UNION ALL
  SELECT 'timesheets', load_batch, source_file, source_row,
         job_code, reject_reason,
         CASE reject_reason
           WHEN 'Hours not a number' THEN hours
           WHEN 'Hours zero or negative' THEN hours
           WHEN 'Job not found or rejected' THEN job_code
           WHEN 'Week ending unreadable' THEN week_ending
         END
  FROM CLEAN.TIMESHEETS_CHECKED WHERE reject_reason IS NOT NULL
)
SELECT
  a.*,
  source_row + IFF(MIN(source_row) OVER (PARTITION BY source_file) = 1, 1, 0) AS spreadsheet_row
FROM all_rejects a;

-- ============================ JOB RESULTS ============================
-- One row per completed job: what it was priced at and what it took.
-- overrun_pct = actual / priced - 1, so 0.25 means 25% over the priced hours.

CREATE OR REPLACE TABLE CLEAN.JOB_RESULTS AS
SELECT
  j.job_id,
  j.bid_id,
  b.job_type,
  b.fee_band,
  b.fee_band_order,
  b.fee_gbp,
  b.priced_hours,
  COALESCE(SUM(t.hours), 0)                       AS actual_hours,
  COALESCE(SUM(t.hours), 0) / b.priced_hours - 1  AS overrun_pct
FROM CLEAN.JOBS j
JOIN CLEAN.BIDS b
  ON b.bid_id = j.bid_id
LEFT JOIN CLEAN.TIMESHEETS t
  ON t.job_id = j.job_id
WHERE j.status = 'Complete'
GROUP BY j.job_id, j.bid_id, b.job_type, b.fee_band, b.fee_band_order, b.fee_gbp, b.priced_hours;
