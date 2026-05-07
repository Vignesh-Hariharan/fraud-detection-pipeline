{{ config(materialized='table') }}

SELECT
    transaction_id,
    customer_id,
    transaction_timestamp,
    transaction_amount,
    is_fraud AS actual_fraud,
    NULL::INTEGER AS predicted_fraud,
    NULL::FLOAT AS fraud_probability,
    NULL::VARCHAR AS risk_category,
    FALSE AS alert_sent
FROM {{ ref('fct_fraud_features') }}
WHERE 1 = 0

