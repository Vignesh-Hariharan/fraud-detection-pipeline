-- Generate Predictions Using BASELINE Model
-- Run this in your Snowflake worksheet

USE DATABASE FRAUD_DETECTION_DB;
USE SCHEMA MARTS_MARTS;

-- Step 1: Create test dataset (data model hasn't seen during training)
CREATE OR REPLACE TABLE FRAUD_TEST_DATA AS
SELECT 
    transaction_id,
    customer_id,
    transaction_timestamp,
    transaction_amount,
    customer_avg_amount,
    amount_z_score,
    hour_of_day,
    merchant_category,
    is_fraud as actual_fraud
FROM FCT_FRAUD_FEATURES
WHERE transaction_timestamp >= '2020-06-01';

-- Check test data size
SELECT 
    COUNT(*) as test_records,
    SUM(actual_fraud) as actual_frauds,
    ROUND(AVG(actual_fraud::FLOAT) * 100, 3) as fraud_rate_pct
FROM FRAUD_TEST_DATA;

-- Step 2: Generate predictions using BASELINE model
-- Note: Snowflake Cortex uses a specific syntax for predictions
CREATE OR REPLACE TABLE FRAUD_PREDICTIONS AS
SELECT 
    t.*,
    FRAUD_MODEL_BASELINE!PREDICT(
        OBJECT_CONSTRUCT(
            'TRANSACTION_ID', t.transaction_id,
            'TRANSACTION_AMOUNT', t.transaction_amount,
            'CUSTOMER_AVG_AMOUNT', t.customer_avg_amount,
            'AMOUNT_Z_SCORE', t.amount_z_score,
            'HOUR_OF_DAY', t.hour_of_day,
            'MERCHANT_CATEGORY', t.merchant_category
        )
    ) as prediction_result
FROM FRAUD_TEST_DATA t;

-- Step 3: Parse prediction results
-- The prediction returns probabilities for BOTH classes (0 and 1)
-- We want the probability of class 1 (fraud)
CREATE OR REPLACE TABLE FRAUD_PREDICTIONS_PARSED AS
SELECT 
    transaction_id,
    customer_id,
    transaction_timestamp,
    transaction_amount,
    merchant_category,
    actual_fraud,
    prediction_result['class']::INT as predicted_fraud,
    prediction_result['probability']['1']::FLOAT as fraud_probability
FROM FRAUD_PREDICTIONS;

-- Step 4: View sample predictions
SELECT 
    transaction_amount,
    merchant_category,
    actual_fraud,
    predicted_fraud,
    ROUND(fraud_probability * 100, 2) as fraud_prob_pct,
    CASE 
        WHEN actual_fraud = 1 AND predicted_fraud = 1 THEN 'Correct - Caught Fraud'
        WHEN actual_fraud = 0 AND predicted_fraud = 0 THEN 'Correct - Normal'
        WHEN actual_fraud = 1 AND predicted_fraud = 0 THEN 'Missed Fraud'
        WHEN actual_fraud = 0 AND predicted_fraud = 1 THEN 'False Alarm'
    END as result
FROM FRAUD_PREDICTIONS_PARSED
LIMIT 20;

-- Step 5: Get high-risk transactions (for alerts)
CREATE OR REPLACE TABLE HIGH_RISK_TRANSACTIONS AS
SELECT 
    transaction_id,
    customer_id,
    transaction_timestamp,
    transaction_amount,
    merchant_category,
    fraud_probability,
    CASE 
        WHEN fraud_probability >= 0.9 THEN 'CRITICAL'
        WHEN fraud_probability >= 0.7 THEN 'HIGH'
        WHEN fraud_probability >= 0.5 THEN 'MEDIUM'
        ELSE 'LOW'
    END as risk_level
FROM FRAUD_PREDICTIONS_PARSED
WHERE predicted_fraud = 1
ORDER BY fraud_probability DESC;

-- View high-risk summary
SELECT 
    risk_level,
    COUNT(*) as count,
    ROUND(AVG(transaction_amount), 2) as avg_amount,
    ROUND(SUM(transaction_amount), 2) as total_at_risk
FROM HIGH_RISK_TRANSACTIONS
GROUP BY risk_level
ORDER BY risk_level;

