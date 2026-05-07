{{ config(materialized='view') }}

SELECT
    trans_num AS transaction_id,
    trans_date_trans_time::TIMESTAMP AS transaction_timestamp,
    cc_num AS customer_id,
    merchant AS merchant_name,
    category AS merchant_category,
    amt AS transaction_amount,
    city AS transaction_city,
    state AS transaction_state,
    lat AS transaction_lat,
    long AS transaction_long,
    dob::DATE AS customer_dob,
    gender AS customer_gender,
    job AS customer_job,
    city_pop AS city_population,
    is_fraud::INTEGER AS is_fraud
FROM {{ source('raw', 'transactions') }}
WHERE trans_num IS NOT NULL

