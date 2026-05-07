-- Train fraud detection classifier using Snowflake Cortex ML
-- Split by time: train on data before Oct 2020

USE DATABASE FRAUD_DETECTION_DB;
USE SCHEMA MARTS_MARTS;

-- Create training dataset with temporal split
CREATE OR REPLACE TABLE FRAUD_TRAINING_DATA AS
SELECT 
    transaction_id,
    customer_id,
    transaction_timestamp,
    transaction_amount,
    customer_avg_amount,
    amount_z_score,
    txns_last_24h,
    txns_last_7d,
    minutes_since_last_txn,
    hour_of_day,
    is_weekend,
    customer_age,
    merchant_category,
    is_different_city,
    is_new_max_amount,
    merchant_fraud_rate,
    is_late_night,
    account_age_days,
    is_fraud
FROM MARTS_MARTS.FCT_FRAUD_FEATURES
WHERE TRANSACTION_TIMESTAMP < '2020-10-01'
  AND IS_FRAUD IS NOT NULL;

-- Check class distribution
SELECT 
    is_fraud,
    COUNT(*) as count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM FRAUD_TRAINING_DATA
GROUP BY is_fraud;

-- Train classification model
-- Cortex handles the imbalanced dataset automatically
CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION FRAUD_MODEL(
    INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'MARTS_MARTS.FRAUD_TRAINING_DATA'),
    TARGET_COLNAME => 'IS_FRAUD',
    CONFIG_OBJECT => {
        'evaluate': TRUE,
        'on_error': 'SKIP_FILE'
    }
);

-- View training information
SELECT SYSTEM$EXPLAIN_ML_FUNCTIONS('FRAUD_MODEL');

-- View evaluation metrics
-- Execute this after training completes:
CALL FRAUD_MODEL!SHOW_EVALUATION_METRICS();

-- View feature importance
CALL FRAUD_MODEL!SHOW_GLOBAL_EVALUATION_METRICS();

-- Create model registry table to track versions and performance
CREATE TABLE IF NOT EXISTS MODEL_REGISTRY (
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    training_date TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    training_data_size INT,
    fraud_rate FLOAT,
    precision_score FLOAT,
    recall_score FLOAT,
    f1_score FLOAT,
    auc_roc FLOAT,
    threshold_used FLOAT,
    notes VARCHAR(500)
);
