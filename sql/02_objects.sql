-- 02_objects.sql
-- Database, schemas, raw tables and the job type map. Safe to run again.
-- Four schemas, one job each:
--   RAW      the files exactly as received, every column as text
--   REF      reference data the buyer signs off (the job type map)
--   CLEAN    rows that pass every rule, the rejects list, and per-job results
--   ANSWERS  the views the director queries

CREATE DATABASE IF NOT EXISTS MARLOW;
USE DATABASE MARLOW;

CREATE SCHEMA IF NOT EXISTS RAW;
CREATE SCHEMA IF NOT EXISTS REF;
CREATE SCHEMA IF NOT EXISTS CLEAN;
CREATE SCHEMA IF NOT EXISTS ANSWERS;

-- Raw tables hold every value as text, so a badly typed cell never stops a load.
-- Bad values are caught later, by named rules, and sent to the rejects list.
-- The last four columns record where each row came from.

CREATE TABLE IF NOT EXISTS RAW.BIDS (
  bid_id          VARCHAR,
  client_code     VARCHAR,
  job_type_label  VARCHAR,
  submitted_on    VARCHAR,
  fee_quoted_gbp  VARCHAR,
  priced_hours    VARCHAR,
  outcome         VARCHAR,
  lead_partner    VARCHAR,
  load_batch      VARCHAR,
  source_file     VARCHAR,
  source_row      NUMBER,
  loaded_at       TIMESTAMP_LTZ
);

CREATE TABLE IF NOT EXISTS RAW.JOBS (
  job_id       VARCHAR,
  bid_id       VARCHAR,
  start_date   VARCHAR,
  end_date     VARCHAR,
  status       VARCHAR,
  load_batch   VARCHAR,
  source_file  VARCHAR,
  source_row   NUMBER,
  loaded_at    TIMESTAMP_LTZ
);

CREATE TABLE IF NOT EXISTS RAW.TIMESHEETS (
  week_ending  VARCHAR,
  employee_id  VARCHAR,
  grade        VARCHAR,
  job_code     VARCHAR,
  hours        VARCHAR,
  load_batch   VARCHAR,
  source_file  VARCHAR,
  source_row   NUMBER,
  loaded_at    TIMESTAMP_LTZ
);

-- The job type map: every spelling found in the bid register, matched in
-- upper case with spaces trimmed, pointing at one agreed job type.
-- A spelling missing from this list is rejected, not guessed.
-- "Workshop facilitation" is left out on purpose: it is a question for the buyer.
CREATE OR REPLACE TABLE REF.JOB_TYPE_MAP (
  label_key  VARCHAR,
  job_type   VARCHAR
);

INSERT INTO REF.JOB_TYPE_MAP (label_key, job_type) VALUES
  ('MARKET ASSESSMENT',        'Market assessment'),
  ('COMMERCIAL DUE DILIGENCE', 'Commercial due diligence'),
  ('COMMERCIAL DD',            'Commercial due diligence'),
  ('CDD',                      'Commercial due diligence'),
  ('OPERATING MODEL REVIEW',   'Operating model review'),
  ('OP MODEL REVIEW',          'Operating model review'),
  ('COST REDUCTION REVIEW',    'Cost reduction review'),
  ('COST REDUCTION',           'Cost reduction review'),
  ('PROCUREMENT SUPPORT',      'Procurement support'),
  ('PROCUREMENT',              'Procurement support'),
  ('DATA AND REPORTING AUDIT', 'Data and reporting audit'),
  ('DATA & REPORTING AUDIT',   'Data and reporting audit'),
  ('REPORTING AUDIT',          'Data and reporting audit');
