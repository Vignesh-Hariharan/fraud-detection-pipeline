-- Model Experiments
-- Try different feature combinations and document results

USE DATABASE FRAUD_DETECTION_DB;
USE SCHEMA MARTS_MARTS;

-- Create experiments tracking table
CREATE TABLE IF NOT EXISTS ML_EXPERIMENTS (
    experiment_id VARCHAR(100),
    experiment_date TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    model_name VARCHAR(100),
    feature_set VARCHAR(500),
    num_features INT,
    training_rows INT,
    fraud_rate FLOAT,
    notes VARCHAR(1000)
);

-- Experiment 1: Baseline (already done in baseline_model.sql)
-- Features: amount, customer_avg, z_score, hour, category (6 features)

-- Experiment 2: Add velocity features
CREATE OR REPLACE TABLE FRAUD_TRAINING_EXP2 AS
SELECT 
    transaction_id,
    transaction_amount,
    customer_avg_amount,
    amount_z_score,
    txns_last_24h,
    txns_last_7d,
    minutes_since_last_txn,
    hour_of_day,
    merchant_category,
    is_fraud
FROM MARTS_MARTS.FCT_FRAUD_FEATURES
WHERE TRANSACTION_TIMESTAMP < '2020-10-01'
  AND IS_FRAUD IS NOT NULL;

CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION FRAUD_MODEL_EXP2(
    INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'MARTS_MARTS.FRAUD_TRAINING_EXP2'),
    TARGET_COLNAME => 'IS_FRAUD',
    CONFIG_OBJECT => {'evaluate': TRUE}
);

-- Experiment 3: Add customer and time features
CREATE OR REPLACE TABLE FRAUD_TRAINING_EXP3 AS
SELECT 
    transaction_id,
    transaction_amount,
    customer_avg_amount,
    amount_z_score,
    txns_last_24h,
    txns_last_7d,
    minutes_since_last_txn,
    hour_of_day,
    is_weekend,
    is_late_night,
    customer_age,
    account_age_days,
    merchant_category,
    is_fraud
FROM MARTS_MARTS.FCT_FRAUD_FEATURES
WHERE TRANSACTION_TIMESTAMP < '2020-10-01'
  AND IS_FRAUD IS NOT NULL;

CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION FRAUD_MODEL_EXP3(
    INPUT_DATA => SYSTEM$REFERENCE('TABLE', 'MARTS_MARTS.FRAUD_TRAINING_EXP3'),
    TARGET_COLNAME => 'IS_FRAUD',
    CONFIG_OBJECT => {'evaluate': TRUE}
);

-- Experiment 4: Full feature set (all 15 features)
-- This is already in train_model.sql as FRAUD_MODEL

-- Compare all experiments
-- Run these after all models are trained:

-- Get metrics for each
CALL FRAUD_MODEL_BASELINE!SHOW_EVALUATION_METRICS();
CALL FRAUD_MODEL_EXP2!SHOW_EVALUATION_METRICS();
CALL FRAUD_MODEL_EXP3!SHOW_EVALUATION_METRICS();
CALL FRAUD_MODEL!SHOW_EVALUATION_METRICS();

-- Log experiments
INSERT INTO ML_EXPERIMENTS (experiment_id, model_name, feature_set, num_features, notes)
VALUES 
('baseline', 'FRAUD_MODEL_BASELINE', 'amount_features + basic_time', 6, 'Baseline with minimal features'),
('exp2', 'FRAUD_MODEL_EXP2', 'baseline + velocity', 9, 'Added transaction velocity features'),
('exp3', 'FRAUD_MODEL_EXP3', 'exp2 + customer_time', 13, 'Added customer and time patterns'),
('full', 'FRAUD_MODEL', 'all_features', 15, 'Full feature set including geography and merchant risk');

