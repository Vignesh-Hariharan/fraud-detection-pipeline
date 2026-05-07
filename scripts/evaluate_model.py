"""
Evaluate trained model and log metrics.

Usage:
    python scripts/evaluate_model.py --config config/snowflake_config.yml
"""

import argparse
import sys
from datetime import datetime
from typing import Dict, Any

import yaml

from scripts.utils.logger import get_logger
from scripts.utils.snowflake_utils import get_connection, execute_query

logger = get_logger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def get_confusion_matrix(conn) -> Dict[str, int]:
    query = """
    SELECT
        SUM(CASE WHEN ACTUAL_FRAUD = 1 AND PREDICTED_FRAUD = 1 THEN 1 ELSE 0 END) as tp,
        SUM(CASE WHEN ACTUAL_FRAUD = 0 AND PREDICTED_FRAUD = 1 THEN 1 ELSE 0 END) as fp,
        SUM(CASE WHEN ACTUAL_FRAUD = 1 AND PREDICTED_FRAUD = 0 THEN 1 ELSE 0 END) as fn,
        SUM(CASE WHEN ACTUAL_FRAUD = 0 AND PREDICTED_FRAUD = 0 THEN 1 ELSE 0 END) as tn
    FROM MARTS.FCT_FRAUD_PREDICTIONS
    """
    
    result = execute_query(conn, query, fetch=True)
    tp, fp, fn, tn = result[0]
    
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn}


def calculate_metrics(confusion_matrix: Dict[str, int]) -> Dict[str, float]:
    tp = confusion_matrix['tp']
    fp = confusion_matrix['fp']
    fn = confusion_matrix['fn']
    tn = confusion_matrix['tn']
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
    
    return {
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1_score': round(f1, 4),
        'accuracy': round(accuracy, 4),
        'specificity': round(specificity, 4)
    }


def get_training_data_stats(conn) -> Dict[str, Any]:
    query = """
    SELECT
        COUNT(*) as total_records,
        SUM(is_fraud) as fraud_count,
        AVG(is_fraud::FLOAT) as fraud_rate
    FROM MARTS.FRAUD_TRAINING_DATA
    """
    
    result = execute_query(conn, query, fetch=True)
    total, fraud_count, fraud_rate = result[0]
    
    return {
        'total_records': total,
        'fraud_count': fraud_count,
        'fraud_rate': round(fraud_rate, 6)
    }


def log_to_registry(conn, metrics: Dict[str, float], training_stats: Dict[str, Any]) -> None:
    # Log metrics to registry
    query = """
    INSERT INTO MARTS.MODEL_REGISTRY (
        model_name,
        model_version,
        training_date,
        training_data_size,
        fraud_rate,
        precision_score,
        recall_score,
        f1_score,
        threshold_used,
        notes
    ) VALUES (
        'FRAUD_MODEL',
        %s,
        CURRENT_TIMESTAMP(),
        %s,
        %s,
        %s,
        %s,
        %s,
        0.5,
        'Snowflake Cortex ML with balanced class handling'
    )
    """
    
    version = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    execute_query(conn, query, params=(
        version,
        training_stats['total_records'],
        training_stats['fraud_rate'],
        metrics['precision'],
        metrics['recall'],
        metrics['f1_score']
    ))
    
    logger.info(f"Logged metrics to registry with version: {version}")


def print_evaluation_report(
    confusion_matrix: Dict[str, int],
    metrics: Dict[str, float],
    training_stats: Dict[str, Any]
) -> None:
    """Print formatted evaluation report."""
    print("\n" + "="*70)
    print("MODEL EVALUATION REPORT")
    print("="*70)
    
    print("\nTraining Data Statistics:")
    print(f"  Total Records: {training_stats['total_records']:,}")
    print(f"  Fraud Count: {training_stats['fraud_count']:,}")
    print(f"  Fraud Rate: {training_stats['fraud_rate']*100:.3f}%")
    
    print("\nConfusion Matrix:")
    print(f"  True Positives:  {confusion_matrix['tp']:,}")
    print(f"  False Positives: {confusion_matrix['fp']:,}")
    print(f"  False Negatives: {confusion_matrix['fn']:,}")
    print(f"  True Negatives:  {confusion_matrix['tn']:,}")
    
    print("\nPerformance Metrics:")
    print(f"  Precision:   {metrics['precision']:.4f} ({metrics['precision']*100:.2f}%)")
    print(f"  Recall:      {metrics['recall']:.4f} ({metrics['recall']*100:.2f}%)")
    print(f"  F1 Score:    {metrics['f1_score']:.4f}")
    print(f"  Accuracy:    {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.2f}%)")
    print(f"  Specificity: {metrics['specificity']:.4f} ({metrics['specificity']*100:.2f}%)")
    
    print("\nInterpretation:")
    if metrics['precision'] > 0.8:
        print("  High precision - low false positive rate")
    elif metrics['precision'] > 0.5:
        print("  Moderate precision - some false positives")
    else:
        print("  Low precision - many false positives")
    
    if metrics['recall'] > 0.8:
        print("  High recall - catching most fraud")
    elif metrics['recall'] > 0.5:
        print("  Moderate recall - missing some fraud")
    else:
        print("  Low recall - missing significant fraud")
    
    print("\n" + "="*70 + "\n")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Evaluate fraud detection model performance'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/snowflake_config.yml',
        help='Path to Snowflake configuration file'
    )
    parser.add_argument(
        '--skip-registry',
        action='store_true',
        help='Skip logging to model registry'
    )
    
    args = parser.parse_args()
    
    try:
        logger.info("Starting model evaluation...")
        
        config = load_config(args.config)
        conn = get_connection(config)
        
        training_stats = get_training_data_stats(conn)
        logger.info(f"Training data: {training_stats['total_records']:,} records")
        
        confusion_matrix = get_confusion_matrix(conn)
        logger.info("Calculated confusion matrix")
        
        metrics = calculate_metrics(confusion_matrix)
        logger.info("Calculated performance metrics")
        
        if not args.skip_registry:
            log_to_registry(conn, metrics, training_stats)
        
        print_evaluation_report(confusion_matrix, metrics, training_stats)
        
        conn.close()
        
        logger.info("Evaluation completed successfully")
    
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

