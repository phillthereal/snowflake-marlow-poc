-- 07_access.sql
-- Criterion 6: the director reads the answer views and nothing else.
-- Re-run after every rebuild, because CREATE OR REPLACE VIEW drops old grants.
-- Snowflake only.
--
-- Views run with their owner's rights, so the director can read a view built
-- on CLEAN tables without having any right to the CLEAN tables themselves.

USE DATABASE MARLOW;

GRANT USAGE ON DATABASE MARLOW TO ROLE MARLOW_DIRECTOR;
GRANT USAGE ON SCHEMA MARLOW.ANSWERS TO ROLE MARLOW_DIRECTOR;
GRANT SELECT ON ALL VIEWS IN SCHEMA MARLOW.ANSWERS TO ROLE MARLOW_DIRECTOR;
