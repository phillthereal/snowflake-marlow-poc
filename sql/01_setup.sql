-- 01_setup.sql
-- Run once, by the account administrator. run.py runs it with: python run.py setup
-- Creates two roles, the warehouse, and lets the pipeline role create its database.
-- {{USER}} is replaced by run.py with the name of the user running the script.

USE ROLE ACCOUNTADMIN;

-- The pipeline runs as MARLOW_ADMIN, not as account admin (least privilege).
CREATE ROLE IF NOT EXISTS MARLOW_ADMIN COMMENT = 'Runs the Marlow pipeline and owns its objects';

-- The operations director reads the answers and nothing else.
CREATE ROLE IF NOT EXISTS MARLOW_DIRECTOR COMMENT = 'Operations director: reads the answer views only';

-- Keep the standard role tree tidy: SYSADMIN can manage what MARLOW_ADMIN owns.
GRANT ROLE MARLOW_ADMIN TO ROLE SYSADMIN;

-- In a real rollout MARLOW_DIRECTOR goes to the director's own login.
-- For the proof of concept both roles go to the person running it, so the
-- access test in criterion 6 can switch between them.
GRANT ROLE MARLOW_ADMIN TO USER "{{USER}}";
GRANT ROLE MARLOW_DIRECTOR TO USER "{{USER}}";

-- Criterion 7: the smallest warehouse, suspended whenever it sits idle for 60 seconds.
CREATE WAREHOUSE IF NOT EXISTS MARLOW_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Marlow proof of concept. X-Small, suspends after 60 seconds idle.';

GRANT USAGE, OPERATE ON WAREHOUSE MARLOW_WH TO ROLE MARLOW_ADMIN;
GRANT USAGE ON WAREHOUSE MARLOW_WH TO ROLE MARLOW_DIRECTOR;

-- MARLOW_ADMIN creates and therefore owns the MARLOW database.
GRANT CREATE DATABASE ON ACCOUNT TO ROLE MARLOW_ADMIN;

-- Criterion 7 reads credit usage from Snowflake's own metering views.
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE TO ROLE MARLOW_ADMIN;
