-- Model evaluation script
-- Calculates comprehensive metrics on test set

USE DATABASE FRAUD_DETECTION_DB;
USE SCHEMA MARTS;

-- Get predictions on test set if not already generated
CREATE OR REPLACE TEMP TABLE test_predictions AS
SELECT
    TRANSACTION_ID,
    ACTUAL_FRAUD,
    PREDICTED_FRAUD,
    FRAUD_PROBABILITY
FROM MARTS.FCT_FRAUD_PREDICTIONS;

-- Calculate confusion matrix
SELECT
    'Confusion Matrix' as metric_type,
    SUM(CASE WHEN ACTUAL_FRAUD = 1 AND PREDICTED_FRAUD = 1 THEN 1 ELSE 0 END) as true_positive,
    SUM(CASE WHEN ACTUAL_FRAUD = 0 AND PREDICTED_FRAUD = 1 THEN 1 ELSE 0 END) as false_positive,
    SUM(CASE WHEN ACTUAL_FRAUD = 1 AND PREDICTED_FRAUD = 0 THEN 1 ELSE 0 END) as false_negative,
    SUM(CASE WHEN ACTUAL_FRAUD = 0 AND PREDICTED_FRAUD = 0 THEN 1 ELSE 0 END) as true_negative
FROM test_predictions;

-- Calculate key metrics
WITH metrics AS (
    SELECT
        SUM(CASE WHEN ACTUAL_FRAUD = 1 AND PREDICTED_FRAUD = 1 THEN 1 ELSE 0 END)::FLOAT as tp,
        SUM(CASE WHEN ACTUAL_FRAUD = 0 AND PREDICTED_FRAUD = 1 THEN 1 ELSE 0 END)::FLOAT as fp,
        SUM(CASE WHEN ACTUAL_FRAUD = 1 AND PREDICTED_FRAUD = 0 THEN 1 ELSE 0 END)::FLOAT as fn,
        SUM(CASE WHEN ACTUAL_FRAUD = 0 AND PREDICTED_FRAUD = 0 THEN 1 ELSE 0 END)::FLOAT as tn
    FROM test_predictions
)
SELECT
    'Performance Metrics' as metric_type,
    ROUND(tp / NULLIF(tp + fp, 0), 4) as precision,
    ROUND(tp / NULLIF(tp + fn, 0), 4) as recall,
    ROUND(2 * (tp / NULLIF(tp + fp, 0)) * (tp / NULLIF(tp + fn, 0)) / 
          NULLIF((tp / NULLIF(tp + fp, 0)) + (tp / NULLIF(tp + fn, 0)), 0), 4) as f1_score,
    ROUND((tp + tn) / NULLIF(tp + fp + fn + tn, 0), 4) as accuracy,
    ROUND(tn / NULLIF(tn + fp, 0), 4) as specificity
FROM metrics;

-- Analyze by risk category
SELECT
    RISK_CATEGORY,
    COUNT(*) as total_transactions,
    SUM(ACTUAL_FRAUD) as actual_frauds,
    SUM(PREDICTED_FRAUD) as predicted_frauds,
    AVG(FRAUD_PROBABILITY) as avg_probability,
    ROUND(SUM(ACTUAL_FRAUD)::FLOAT / COUNT(*) * 100, 2) as actual_fraud_rate_pct
FROM MARTS.FCT_FRAUD_PREDICTIONS
GROUP BY RISK_CATEGORY
ORDER BY RISK_CATEGORY;

-- Distribution of fraud probabilities for actual fraud vs legitimate
SELECT
    ACTUAL_FRAUD,
    MIN(FRAUD_PROBABILITY) as min_prob,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY FRAUD_PROBABILITY) as q1,
    MEDIAN(FRAUD_PROBABILITY) as median_prob,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY FRAUD_PROBABILITY) as q3,
    MAX(FRAUD_PROBABILITY) as max_prob,
    AVG(FRAUD_PROBABILITY) as avg_prob
FROM MARTS.FCT_FRAUD_PREDICTIONS
GROUP BY ACTUAL_FRAUD
ORDER BY ACTUAL_FRAUD;

-- Threshold analysis for different probability cutoffs
WITH threshold_analysis AS (
    SELECT
        threshold,
        SUM(CASE WHEN ACTUAL_FRAUD = 1 AND FRAUD_PROBABILITY >= threshold THEN 1 ELSE 0 END)::FLOAT as tp,
        SUM(CASE WHEN ACTUAL_FRAUD = 0 AND FRAUD_PROBABILITY >= threshold THEN 1 ELSE 0 END)::FLOAT as fp,
        SUM(CASE WHEN ACTUAL_FRAUD = 1 AND FRAUD_PROBABILITY < threshold THEN 1 ELSE 0 END)::FLOAT as fn
    FROM MARTS.FCT_FRAUD_PREDICTIONS
    CROSS JOIN (
        SELECT 0.1 as threshold UNION ALL
        SELECT 0.2 UNION ALL SELECT 0.3 UNION ALL SELECT 0.4 UNION ALL SELECT 0.5 UNION ALL
        SELECT 0.6 UNION ALL SELECT 0.7 UNION ALL SELECT 0.8 UNION ALL SELECT 0.9
    ) thresholds
    GROUP BY threshold
)
SELECT
    threshold,
    ROUND(tp / NULLIF(tp + fp, 0), 4) as precision,
    ROUND(tp / NULLIF(tp + fn, 0), 4) as recall,
    ROUND(2 * (tp / NULLIF(tp + fp, 0)) * (tp / NULLIF(tp + fn, 0)) / 
          NULLIF((tp / NULLIF(tp + fp, 0)) + (tp / NULLIF(tp + fn, 0)), 0), 4) as f1_score,
    ROUND(tp + fp, 0) as predictions_flagged
FROM threshold_analysis
ORDER BY threshold;

