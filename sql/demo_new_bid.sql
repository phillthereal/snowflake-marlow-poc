-- demo_new_bid.sql
-- For the recording: the director is pricing a new bid.
-- Change the two values below, then run the whole file in a Snowsight worksheet.

USE ROLE MARLOW_DIRECTOR;
USE SECONDARY ROLES NONE;
USE WAREHOUSE MARLOW_WH;

SET new_job_type = 'Commercial due diligence';
SET new_fee_band = '£25k to £50k';

-- What similar past jobs took. If the first row says "Fewer than 5 past jobs",
-- read the "All fee bands" row instead.
SELECT
  fee_band,
  similar_jobs,
  median_priced_hours,
  median_actual_hours,
  p80_actual_hours,
  median_overrun_pct,
  sample_note
FROM MARLOW.ANSWERS.Q2_BID_BENCHMARKS
WHERE job_type = $new_job_type
  AND fee_band IN ($new_fee_band, 'All fee bands')
ORDER BY fee_band_order;

-- Is this a job type the firm wins because it underprices?
SELECT job_type, win_rate_pct, firm_win_rate_pct, median_overrun_pct, verdict
FROM MARLOW.ANSWERS.Q3_WIN_RATE_VS_OVERRUN
WHERE job_type = $new_job_type;
