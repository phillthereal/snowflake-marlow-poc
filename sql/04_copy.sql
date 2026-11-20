-- 04_copy.sql
-- Copy one month's uploaded files from the stage into the raw tables.
-- run.py uploads the files first (PUT), then runs this with {{BATCH}} filled in.
--
-- Snowflake remembers which files it has already loaded into each table,
-- so running the same month twice loads nothing the second time (criterion 5).
-- METADATA$FILENAME and METADATA$FILE_ROW_NUMBER record the file and row of
-- every record, which is how the rejects list can point at the exact row.

USE DATABASE MARLOW;

COPY INTO RAW.BIDS (bid_id, client_code, job_type_label, submitted_on, fee_quoted_gbp,
                    priced_hours, outcome, lead_partner,
                    load_batch, source_file, source_row, loaded_at)
FROM (
  SELECT f.$1, f.$2, f.$3, f.$4, f.$5, f.$6, f.$7, f.$8,
         '{{BATCH}}', METADATA$FILENAME, METADATA$FILE_ROW_NUMBER, CURRENT_TIMESTAMP()
  FROM @RAW.LANDING/{{BATCH}}/ f
)
FILES = ('bids.csv.gz')
FILE_FORMAT = (FORMAT_NAME = 'RAW.CSV_FORMAT');

COPY INTO RAW.JOBS (job_id, bid_id, start_date, end_date, status,
                    load_batch, source_file, source_row, loaded_at)
FROM (
  SELECT f.$1, f.$2, f.$3, f.$4, f.$5,
         '{{BATCH}}', METADATA$FILENAME, METADATA$FILE_ROW_NUMBER, CURRENT_TIMESTAMP()
  FROM @RAW.LANDING/{{BATCH}}/ f
)
FILES = ('jobs.csv.gz')
FILE_FORMAT = (FORMAT_NAME = 'RAW.CSV_FORMAT');

COPY INTO RAW.TIMESHEETS (week_ending, employee_id, grade, job_code, hours,
                          load_batch, source_file, source_row, loaded_at)
FROM (
  SELECT f.$1, f.$2, f.$3, f.$4, f.$5,
         '{{BATCH}}', METADATA$FILENAME, METADATA$FILE_ROW_NUMBER, CURRENT_TIMESTAMP()
  FROM @RAW.LANDING/{{BATCH}}/ f
)
FILES = ('timesheets.csv.gz')
FILE_FORMAT = (FORMAT_NAME = 'RAW.CSV_FORMAT');
