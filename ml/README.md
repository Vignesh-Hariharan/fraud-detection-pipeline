# ML Training Workflow

This directory contains all ML training and evaluation scripts.

## Training Approach

We use an iterative approach to understand which features actually help:

```
Baseline (6 features)
    ↓ add velocity
Experiment 2 (9 features)
    ↓ add customer/time
Experiment 3 (13 features)
    ↓ add geography/merchant
Full Model (15 features)
    ↓
Compare & Select Best
```

## Execution Order

### 1. Train Baseline Model

```sql
-- In Snowflake, execute:
-- ml/baseline_model.sql
```

Creates: `FRAUD_MODEL_BASELINE` with 6 basic features

Check results:
```sql
CALL FRAUD_MODEL_BASELINE!SHOW_EVALUATION_METRICS();
```

### 2. Run Experiments

```sql
-- In Snowflake, execute:
-- ml/experiments.sql
```

Creates:
- `FRAUD_MODEL_EXP2` (9 features with velocity)
- `FRAUD_MODEL_EXP3` (13 features with customer/time)

Check results:
```sql
CALL FRAUD_MODEL_EXP2!SHOW_EVALUATION_METRICS();
CALL FRAUD_MODEL_EXP3!SHOW_EVALUATION_METRICS();
```

### 3. Train Full Model

```sql
-- In Snowflake, execute:
-- ml/train_model.sql
```

Creates: `FRAUD_MODEL` with all 15 features

Check results:
```sql
CALL FRAUD_MODEL!SHOW_EVALUATION_METRICS();
```

### 4. Compare All Models

```bash
python scripts/compare_models.py
```

This script:
- Scores all 4 models on the same test set
- Calculates precision, recall, F1 for each
- Tests 9 different probability thresholds
- Recommends best model and threshold

Output shows:
- Side-by-side comparison table
- Best performing model
- Optimal threshold for your use case

### 5. Evaluate Selected Model

```bash
python scripts/evaluate_model.py
```

Detailed metrics for the final model including:
- Confusion matrix
- Performance by risk category
- Probability distributions
- Business impact metrics

### 6. Generate Predictions

```sql
-- In Snowflake, execute:
-- ml/generate_predictions.sql
```

Uses the best model (FRAUD_MODEL by default) to score all test transactions.

Creates: `MARTS.FCT_FRAUD_PREDICTIONS` with risk scores

## Files

### Training Scripts (SQL)

- **baseline_model.sql**: Train minimal feature model (starting point)
- **experiments.sql**: Train incremental feature experiments
- **train_model.sql**: Train full feature model + create model registry
- **generate_predictions.sql**: Score test set with selected model
- **evaluate_model.sql**: SQL queries for detailed analysis

### Analysis Scripts (Python)

- **../scripts/compare_models.py**: Compare all experiments systematically
- **../scripts/evaluate_model.py**: Deep dive on final model performance

## Feature Sets

### Baseline (6 features)
```
transaction_amount
customer_avg_amount
amount_z_score
hour_of_day
merchant_category
is_fraud
```

### + Velocity (9 features)
```
+ txns_last_24h
+ txns_last_7d
+ minutes_since_last_txn
```

### + Customer/Time (13 features)
```
+ is_weekend
+ is_late_night
+ customer_age
+ account_age_days
```

### Full (15 features)
```
+ is_different_city
+ is_new_max_amount
+ merchant_fraud_rate
```

## Model Registry

Training scripts create `MARTS.MODEL_REGISTRY` table tracking:
- Model name and version
- Training date and data size
- Fraud rate in training data
- Performance metrics (precision, recall, F1)
- Threshold used
- Notes

Query it:
```sql
SELECT * FROM MARTS.MODEL_REGISTRY ORDER BY training_date DESC;
```

## Experiments Tracking

Training scripts also create `MARTS.ML_EXPERIMENTS` table tracking:
- Experiment ID
- Model name
- Feature set description
- Number of features
- Training data stats
- Notes

Query it:
```sql
SELECT * FROM MARTS.ML_EXPERIMENTS ORDER BY experiment_date DESC;
```

## Tips for Good Results

1. **Run in order**: Baseline → Experiments → Full → Compare
2. **Document metrics**: Record actual numbers for future reference
3. **Test thresholds**: Don't just use 0.5, find what works for your goals
4. **Consider business context**: High recall (catch fraud) vs high precision (avoid false alarms)
5. **Check feature importance**: Snowflake Cortex provides this via `SHOW_GLOBAL_EVALUATION_METRICS()`

## Troubleshooting

**Snowflake Cortex not available?**
- Requires Enterprise Edition or higher
- Only available in specific cloud regions
- If not available, consider exporting data and using sklearn/xgboost

**Training takes too long?**
- Check warehouse size (XSMALL might be too small)
- Consider sampling data for experiments, full data for final model
- Cortex ML can take 5-15 minutes depending on data size

**Poor performance?**
- Check class imbalance (should be ~0.17% fraud)
- Verify temporal split is correct (train before, test after cutoff)
- Look at probability distributions - are they separating fraud from legit?
- Try different thresholds - default 0.5 might not be optimal

**Models not comparable?**
- Ensure using same test set for all models
- Use the compare_models.py script for consistency
- Check that experiments are logged to tracking tables

## Next Steps After Training

1. Select best model and threshold based on comparison results
2. Generate predictions with `generate_predictions.sql`
3. Run evaluation script
4. Deploy to production pipeline via `scripts/run_pipeline.py`

