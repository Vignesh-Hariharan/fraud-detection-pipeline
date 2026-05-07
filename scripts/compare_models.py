"""
Compare different model experiments.

Usage:
    python scripts/compare_models.py --config config/snowflake_config.yml
"""

import argparse
import sys
from typing import Dict, List, Tuple
import yaml
from scripts.utils.logger import get_logger
from scripts.utils.snowflake_utils import get_connection, execute_query

logger = get_logger(__name__)


def load_config(config_path: str) -> Dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_test_data_query() -> str:
    return """
    SELECT *
    FROM MARTS.FCT_FRAUD_FEATURES
    WHERE TRANSACTION_TIMESTAMP >= '2020-10-01'
    """


def score_model(conn, model_name: str, feature_columns: List[str]) -> str:
    # Score model on test data and create predictions table
    logger.info(f"Scoring model: {model_name}")
    
    # Create feature selection
    feature_select = ", ".join(feature_columns)
    
    # Create predictions table
    predictions_table = f"MARTS.PREDICTIONS_{model_name}"
    
    query = f"""
    CREATE OR REPLACE TABLE {predictions_table} AS
    WITH test_data AS (
        SELECT 
            transaction_id,
            {feature_select},
            is_fraud as actual_fraud
        FROM MARTS.FCT_FRAUD_FEATURES
        WHERE TRANSACTION_TIMESTAMP >= '2020-10-01'
    )
    SELECT
        transaction_id,
        actual_fraud,
        {model_name}!PREDICT(OBJECT_CONSTRUCT(*))['prediction']::INTEGER AS predicted_fraud,
        {model_name}!PREDICT(OBJECT_CONSTRUCT(*))['probability'][1]::FLOAT AS fraud_probability
    FROM test_data
    """
    
    execute_query(conn, query)
    logger.info(f"Created predictions table: {predictions_table}")
    
    return predictions_table


def calculate_metrics(conn, predictions_table: str) -> Dict:
    query = f"""
    WITH metrics AS (
        SELECT
            SUM(CASE WHEN actual_fraud = 1 AND predicted_fraud = 1 THEN 1 ELSE 0 END)::FLOAT as tp,
            SUM(CASE WHEN actual_fraud = 0 AND predicted_fraud = 1 THEN 1 ELSE 0 END)::FLOAT as fp,
            SUM(CASE WHEN actual_fraud = 1 AND predicted_fraud = 0 THEN 1 ELSE 0 END)::FLOAT as fn,
            SUM(CASE WHEN actual_fraud = 0 AND predicted_fraud = 0 THEN 1 ELSE 0 END)::FLOAT as tn
        FROM {predictions_table}
    )
    SELECT
        tp, fp, fn, tn,
        tp / NULLIF(tp + fp, 0) as precision,
        tp / NULLIF(tp + fn, 0) as recall,
        (tp + tn) / NULLIF(tp + fp + fn + tn, 0) as accuracy
    FROM metrics
    """
    
    result = execute_query(conn, query, fetch=True)
    tp, fp, fn, tn, precision, recall, accuracy = result[0]
    
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        'tp': int(tp) if tp else 0,
        'fp': int(fp) if fp else 0,
        'fn': int(fn) if fn else 0,
        'tn': int(tn) if tn else 0,
        'precision': round(precision, 4) if precision else 0,
        'recall': round(recall, 4) if recall else 0,
        'f1_score': round(f1, 4),
        'accuracy': round(accuracy, 4) if accuracy else 0
    }


def test_thresholds(conn, predictions_table: str, thresholds: List[float]) -> List[Dict]:
    # Test different probability thresholds
    logger.info(f"Testing {len(thresholds)} different thresholds...")
    
    results = []
    
    for threshold in thresholds:
        query = f"""
        WITH metrics AS (
            SELECT
                SUM(CASE WHEN actual_fraud = 1 AND fraud_probability >= {threshold} THEN 1 ELSE 0 END)::FLOAT as tp,
                SUM(CASE WHEN actual_fraud = 0 AND fraud_probability >= {threshold} THEN 1 ELSE 0 END)::FLOAT as fp,
                SUM(CASE WHEN actual_fraud = 1 AND fraud_probability < {threshold} THEN 1 ELSE 0 END)::FLOAT as fn
            FROM {predictions_table}
        )
        SELECT
            tp,
            fp,
            fn,
            tp / NULLIF(tp + fp, 0) as precision,
            tp / NULLIF(tp + fn, 0) as recall
        FROM metrics
        """
        
        result = execute_query(conn, query, fetch=True)
        tp, fp, fn, precision, recall = result[0]
        
        f1 = 2 * precision * recall / (precision + recall) if (precision and recall) else 0
        
        results.append({
            'threshold': threshold,
            'tp': int(tp) if tp else 0,
            'fp': int(fp) if fp else 0,
            'fn': int(fn) if fn else 0,
            'precision': round(precision, 4) if precision else 0,
            'recall': round(recall, 4) if recall else 0,
            'f1_score': round(f1, 4)
        })
    
    return results


def print_comparison(experiments: Dict[str, Dict]) -> None:
    print("\n" + "="*80)
    print("MODEL COMPARISON RESULTS")
    print("="*80)
    
    # Header
    print(f"\n{'Model':<20} {'Features':<10} {'Precision':<12} {'Recall':<12} {'F1':<10}")
    print("-"*80)
    
    # Rows
    for exp_name, data in experiments.items():
        print(f"{exp_name:<20} {data['num_features']:<10} "
              f"{data['metrics']['precision']:<12.4f} "
              f"{data['metrics']['recall']:<12.4f} "
              f"{data['metrics']['f1_score']:<10.4f}")
    
    # Find best model
    best_f1_model = max(experiments.items(), key=lambda x: x[1]['metrics']['f1_score'])
    best_recall_model = max(experiments.items(), key=lambda x: x[1]['metrics']['recall'])
    
    print("\n" + "="*80)
    print(f"Best F1 Score: {best_f1_model[0]} ({best_f1_model[1]['metrics']['f1_score']:.4f})")
    print(f"Best Recall: {best_recall_model[0]} ({best_recall_model[1]['metrics']['recall']:.4f})")
    print("="*80 + "\n")


def print_threshold_analysis(model_name: str, threshold_results: List[Dict]) -> None:
    # Print threshold analysis
    print(f"\nThreshold Analysis for {model_name}:")
    print("-"*70)
    print(f"{'Threshold':<12} {'Precision':<12} {'Recall':<12} {'F1':<10} {'Flagged':<10}")
    print("-"*70)
    
    for result in threshold_results:
        flagged = result['tp'] + result['fp']
        print(f"{result['threshold']:<12.2f} "
              f"{result['precision']:<12.4f} "
              f"{result['recall']:<12.4f} "
              f"{result['f1_score']:<10.4f} "
              f"{flagged:<10}")
    
    best_f1 = max(threshold_results, key=lambda x: x['f1_score'])
    print(f"\nBest threshold: {best_f1['threshold']} (F1: {best_f1['f1_score']:.4f})")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Compare trained fraud detection models'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/snowflake_config.yml',
        help='Path to Snowflake configuration file'
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("Starting model comparison...")
        
        config = load_config(args.config)
        conn = get_connection(config)
        
        # Define experiments with their feature sets
        experiments = {
            'baseline': {
                'model_name': 'FRAUD_MODEL_BASELINE',
                'features': ['transaction_amount', 'customer_avg_amount', 'amount_z_score', 
                           'hour_of_day', 'merchant_category', 'is_fraud'],
                'num_features': 6
            },
            'with_velocity': {
                'model_name': 'FRAUD_MODEL_EXP2',
                'features': ['transaction_amount', 'customer_avg_amount', 'amount_z_score',
                           'txns_last_24h', 'txns_last_7d', 'minutes_since_last_txn',
                           'hour_of_day', 'merchant_category', 'is_fraud'],
                'num_features': 9
            },
            'with_customer_time': {
                'model_name': 'FRAUD_MODEL_EXP3',
                'features': ['transaction_amount', 'customer_avg_amount', 'amount_z_score',
                           'txns_last_24h', 'txns_last_7d', 'minutes_since_last_txn',
                           'hour_of_day', 'is_weekend', 'is_late_night',
                           'customer_age', 'account_age_days', 'merchant_category', 'is_fraud'],
                'num_features': 13
            },
            'full_features': {
                'model_name': 'FRAUD_MODEL',
                'features': ['transaction_id', 'customer_id', 'transaction_timestamp',
                           'transaction_amount', 'customer_avg_amount', 'amount_z_score',
                           'txns_last_24h', 'txns_last_7d', 'minutes_since_last_txn',
                           'hour_of_day', 'is_weekend', 'customer_age', 'merchant_category',
                           'is_different_city', 'is_new_max_amount', 'merchant_fraud_rate',
                           'is_late_night', 'account_age_days', 'is_fraud'],
                'num_features': 15
            }
        }
        
        # Score each model and calculate metrics
        for exp_name, exp_data in experiments.items():
            logger.info(f"Evaluating {exp_name}...")
            
            predictions_table = score_model(
                conn, 
                exp_data['model_name'],
                exp_data['features']
            )
            
            metrics = calculate_metrics(conn, predictions_table)
            exp_data['metrics'] = metrics
            exp_data['predictions_table'] = predictions_table
        
        # Print comparison
        print_comparison(experiments)
        
        # Threshold analysis for best model
        best_model = max(experiments.items(), key=lambda x: x[1]['metrics']['f1_score'])
        thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        
        threshold_results = test_thresholds(
            conn,
            best_model[1]['predictions_table'],
            thresholds
        )
        
        print_threshold_analysis(best_model[0], threshold_results)
        
        conn.close()
        
        logger.info("Model comparison completed successfully")
        logger.info(f"Use the {best_model[0]} model for final predictions")
        
    except Exception as e:
        logger.error(f"Model comparison failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

