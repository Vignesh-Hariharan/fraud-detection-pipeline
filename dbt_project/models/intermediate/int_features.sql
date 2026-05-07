{{ config(materialized='table') }}

WITH base_transactions AS (
    SELECT * FROM {{ ref('stg_transactions') }}
),

customer_aggregates AS (
    SELECT
        customer_id,
        AVG(transaction_amount) AS customer_avg_amount,
        STDDEV(transaction_amount) AS customer_stddev_amount,
        MODE(transaction_city) AS customer_home_city,
        MIN(transaction_timestamp) AS first_transaction_date
    FROM base_transactions
    GROUP BY customer_id
),

merchant_aggregates AS (
    SELECT
        merchant_name,
        AVG(is_fraud::FLOAT) AS merchant_fraud_rate
    FROM base_transactions
    GROUP BY merchant_name
),

transaction_velocity AS (
    SELECT
        transaction_id,
        customer_id,
        transaction_timestamp,
        COUNT(*) OVER (
            PARTITION BY customer_id
            ORDER BY transaction_timestamp
            RANGE BETWEEN INTERVAL '24 HOURS' PRECEDING AND CURRENT ROW
        ) - 1 AS txns_last_24h,
        COUNT(*) OVER (
            PARTITION BY customer_id
            ORDER BY transaction_timestamp
            RANGE BETWEEN INTERVAL '7 DAYS' PRECEDING AND CURRENT ROW
        ) - 1 AS txns_last_7d,
        LAG(transaction_timestamp) OVER (
            PARTITION BY customer_id
            ORDER BY transaction_timestamp
        ) AS previous_transaction_timestamp,
        MAX(transaction_amount) OVER (
            PARTITION BY customer_id
            ORDER BY transaction_timestamp
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ) AS previous_max_amount
    FROM base_transactions
),

enriched_features AS (
    SELECT
        t.transaction_id,
        t.customer_id,
        t.transaction_timestamp,
        t.transaction_amount,
        t.merchant_name,
        t.merchant_category,
        t.transaction_city,
        t.transaction_state,
        t.transaction_lat,
        t.transaction_long,
        t.customer_dob,
        t.is_fraud,
        
        ca.customer_avg_amount,
        ca.customer_stddev_amount,
        ca.customer_home_city,
        ca.first_transaction_date,
        
        ma.merchant_fraud_rate,
        
        v.txns_last_24h,
        v.txns_last_7d,
        v.previous_transaction_timestamp,
        v.previous_max_amount,
        
        CASE
            WHEN ca.customer_stddev_amount = 0 OR ca.customer_stddev_amount IS NULL THEN 0
            ELSE (t.transaction_amount - ca.customer_avg_amount) / ca.customer_stddev_amount
        END AS amount_z_score,
        
        CASE
            WHEN v.previous_transaction_timestamp IS NULL THEN NULL
            ELSE DATEDIFF(MINUTE, v.previous_transaction_timestamp, t.transaction_timestamp)
        END AS minutes_since_last_txn,
        
        HOUR(t.transaction_timestamp) AS hour_of_day,
        
        CASE
            WHEN DAYOFWEEK(t.transaction_timestamp) IN (0, 6) THEN TRUE
            ELSE FALSE
        END AS is_weekend,
        
        DATEDIFF(YEAR, t.customer_dob, t.transaction_timestamp) AS customer_age,
        
        CASE
            WHEN t.transaction_city != ca.customer_home_city THEN TRUE
            ELSE FALSE
        END AS is_different_city,
        
        CASE
            WHEN t.transaction_amount > COALESCE(v.previous_max_amount, 0) THEN TRUE
            ELSE FALSE
        END AS is_new_max_amount,
        
        CASE
            WHEN HOUR(t.transaction_timestamp) BETWEEN 2 AND 5 THEN TRUE
            ELSE FALSE
        END AS is_late_night,
        
        DATEDIFF(DAY, ca.first_transaction_date, t.transaction_timestamp) AS account_age_days
        
    FROM base_transactions t
    LEFT JOIN customer_aggregates ca ON t.customer_id = ca.customer_id
    LEFT JOIN merchant_aggregates ma ON t.merchant_name = ma.merchant_name
    LEFT JOIN transaction_velocity v ON t.transaction_id = v.transaction_id
)

SELECT * FROM enriched_features

