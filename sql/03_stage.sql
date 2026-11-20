-- 03_stage.sql
-- The file format and the internal stage the monthly files are uploaded to.
-- Snowflake only (the local emulator loads files a different way).

USE DATABASE MARLOW;

-- How to read the spreadsheet exports: comma separated, one header row,
-- quotes around values that contain commas (like "£12,500"),
-- and an empty cell becomes NULL. Spaces are kept, so "Won " arrives as typed.
CREATE FILE FORMAT IF NOT EXISTS RAW.CSV_FORMAT
  TYPE = CSV
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  EMPTY_FIELD_AS_NULL = TRUE
  NULL_IF = ('')
  ENCODING = 'UTF8';

-- Monthly exports are uploaded here, one folder per month.
CREATE STAGE IF NOT EXISTS RAW.LANDING
  FILE_FORMAT = RAW.CSV_FORMAT
  COMMENT = 'Monthly spreadsheet exports, one folder per batch';
