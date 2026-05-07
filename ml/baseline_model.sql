-- Baseline Model: Start Simple
-- Using only the most basic features to establish baseline performance

USE DATABASE FRAUD_DETECTION_DB;
USE SCHEMA MARTS_MARTS;

-- Create baseline feature set (minimal features)
CREATE OR REPLACE TABLE FRAUD_TRAINING_BASELINE AS
SELECT 
    transaction_id,
    transaction_amount,
    customer_avg_amount,
    amount_z_score,
    hour_of_day,
    merchant_category,
    is_fraud
FROM MARTS_MARTS.FCT_FRAUD_FEATURES
WHERE TRANSACTION_TIMESTAMP < '2020-10-01'
  AND IS_FRAUD IS NOT NULL;

-- Check what we're working with
SELECT 
    COUNT(*) as total_records,
    SUM(is_fraud) as fraud_count,
    ROUND(AVG(is_fraud::FLOAT) * 100, 3) as fraud_rate_pct,
    MIN(transaction_timestamp) as earliest_date,
    MAX(transaction_timestamp) as latest_date
FROM MARTS_MARTS.FCT_FRAUD_FEATURES
WHERE TRANSACTION_TIMESTAMP < '2020-10-01';

-- Train baseline model
CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION FRAUD_MODEL_BASELINE(
    INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'MARTS_MARTS.FRAUD_TRAINING_BASELINE'),
    TARGET_COLNAME => 'IS_FRAUD',
    CONFIG_OBJECT => {'evaluate': TRUE}
);

-- Get baseline metrics
CALL FRAUD_MODEL_BASELINE!SHOW_EVALUATION_METRICS();

