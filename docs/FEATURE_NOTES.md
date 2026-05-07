# Feature Engineering Process

This document explains the features engineered for the fraud detection model, based on research into common fraud detection patterns.

## Approach

Features were built in two phases, testing model performance after each phase to validate effectiveness.

## Phase 1: Initial Features (10)

Ten basic features were selected based on common fraud detection patterns.

### Amount Features

**1. transaction_amount**
- Just the raw dollar amount
- Keeping it simple as a baseline

**2. customer_avg_amount**
- Average of what this customer typically spends
- Calculated from their transaction history

**3. amount_z_score**
- How far this transaction is from the customer's normal spending
- Formula: `(current amount - average) / standard deviation`
- If stddev is 0, set to 0 to avoid division errors

### Activity Count Features

**4. txns_last_24h**
- How many transactions in the last 24 hours
- Used Snowflake window functions with RANGE

**5. txns_last_7d**
- How many transactions in the last 7 days
- Wider time window to see overall activity

**6. minutes_since_last_txn**
- Time since their previous transaction
- Used LAG window function
- NULL for first transaction

### Time-Based Features

**7. hour_of_day**
- Simple extraction: 0-23
- Figured transactions at 3 AM might be different than 3 PM

**8. is_weekend**
- Boolean for Saturday/Sunday
- Used DAYOFWEEK function

### Customer Info

**9. customer_age**
- Calculated from date of birth
- Used DATEDIFF in years

**10. merchant_category**
- Category field from the dataset (grocery, gas, etc.)
- Let the model figure out if certain categories are riskier

## Phase 2: Additional Features (5)

After initial model training, 5 additional features were added based on performance analysis.

### Location Check

**11. is_different_city**
- Boolean: is the transaction in a different city than usual?
- Found the customer's "home city" using MODE function
- Simple comparison, no fancy distance calculations

### Spending Behavior

**12. is_new_max_amount**
- Boolean: is this the highest amount they've ever spent?
- Used MAX window function looking backwards

### Merchant History

**13. merchant_fraud_rate**
- What percentage of transactions at this merchant were fraud?
- Simple: `AVG(is_fraud) GROUP BY merchant`
- Some merchants might be targeted more

### Time Pattern

**14. is_late_night**
- Boolean: is it between 2 AM and 5 AM?
- Based on reading that late-night transactions can be risky

### Account History

**15. account_age_days**
- How many days since the customer's first transaction
- Used MIN to find first transaction date, then DATEDIFF

## Implementation Details

All features are implemented in a single dbt model (`int_features.sql`) using SQL. Structure:
- CTEs for customer aggregates
- CTEs for merchant aggregates
- CTE for window function calculations
- Final SELECT joining everything together

This approach kept it simple and readable.

## What I Didn't Build

Features researched but not included:

**Geographic distance calculations**
- Would need Haversine formula for lat/long
- Seemed complex for a first version
- Already have city comparison which is simpler

**Transaction sequences**
- Looking at patterns like "gas then grocery then online"
- Would need more complex SQL or Python
- Maybe for v2

**Device or IP information**
- Not in the Kaggle dataset
- Would need external data sources

**Complex time windows**
- Like "acceleration" of transaction frequency
- Too complicated for initial version

**Feature crosses**
- Multiplication of features (e.g., amount * is_weekend)
- Decided to let the model learn interactions

## How I Validated Features

1. Ran dbt tests to check data quality
2. Looked at feature distributions for fraud vs non-fraud
3. Trained the model and checked if it worked
4. Added Phase 2 features and compared performance

No fancy feature selection algorithms. Just built features that made sense, tested, and iterated.

## Notes for Future Improvement

- Test removing features to see if simpler models perform better
- Add feature importance analysis to identify most impactful features
- Try normalizing features for better model performance
- Experiment with different time windows (12h, 3d, etc.)

These features provide a solid baseline for fraud detection with room for further optimization.
