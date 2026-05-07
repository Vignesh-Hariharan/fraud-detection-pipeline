"""
Run the complete fraud detection pipeline.

Usage:
    python scripts/run_pipeline.py --config config/snowflake_config.yml
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from scripts.utils.logger import get_logger
from scripts.utils.snowflake_utils import get_connection, execute_query
import yaml

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def validate_data_quality(config: dict) -> bool:
    logger.info("Running data quality checks...")
    
    conn = get_connection(config)
    
    try:
        query = """
        SELECT
            COUNT(*) as total_rows,
            COUNT(DISTINCT transaction_id) as unique_transactions,
            SUM(CASE WHEN transaction_amount < 0 THEN 1 ELSE 0 END) as negative_amounts,
            SUM(CASE WHEN customer_id IS NULL THEN 1 ELSE 0 END) as null_customers
        FROM MARTS.FCT_FRAUD_FEATURES
        """
        
        result = execute_query(conn, query, fetch=True)
        total, unique, negative, nulls = result[0]
        
        logger.info(f"Data quality results: {total:,} rows, {unique:,} unique transactions")
        
        if negative > 0:
            logger.error(f"Found {negative} transactions with negative amounts")
            return False
        
        if nulls > 0:
            logger.error(f"Found {nulls} transactions with null customer IDs")
            return False
        
        if total != unique:
            logger.warning(f"Duplicate transaction IDs detected: {total - unique} duplicates")
        
        logger.info("Data quality checks passed")
        return True
    
    finally:
        conn.close()


def run_dbt_models() -> bool:
    logger.info("Running dbt models...")
    
    dbt_dir = PROJECT_ROOT / 'dbt_project'
    
    try:
        result = subprocess.run(
            ['dbt', 'run'],
            cwd=dbt_dir,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("dbt models completed successfully")
        logger.info(result.stdout)
        return True
    
    except subprocess.CalledProcessError as e:
        logger.error(f"dbt run failed: {e.stderr}")
        return False


def run_dbt_tests() -> bool:
    logger.info("Running dbt tests...")
    
    dbt_dir = PROJECT_ROOT / 'dbt_project'
    
    try:
        result = subprocess.run(
            ['dbt', 'test'],
            cwd=dbt_dir,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("dbt tests passed")
        return True
    
    except subprocess.CalledProcessError as e:
        logger.warning(f"Some dbt tests failed: {e.stderr}")
        return True


def generate_predictions(config: dict) -> bool:
    logger.info("Generating predictions...")
    
    conn = get_connection(config)
    
    try:
        sql_file = PROJECT_ROOT / 'ml' / 'generate_predictions.sql'
        
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        for statement in statements:
            if statement.startswith('--') or not statement:
                continue
            execute_query(conn, statement)
        
        logger.info("Predictions generated successfully")
        return True
    
    except Exception as e:
        logger.error(f"Prediction generation failed: {e}")
        return False
    
    finally:
        conn.close()


def send_alerts(config_path: str) -> bool:
    # Send alerts for high-risk transactions
    logger.info("Checking for high-risk transactions...")
    
    try:
        result = subprocess.run(
            ['python', 'scripts/slack_alert.py', '--config', config_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info("Alert check completed")
        logger.info(result.stdout)
        return True
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Alert system failed: {e.stderr}")
        return False


def log_pipeline_run(config: dict, success: bool, duration: float) -> None:
    # Log pipeline run to database
    conn = get_connection(config)
    
    try:
        query = """
        CREATE TABLE IF NOT EXISTS MARTS.PIPELINE_RUNS (
            run_id VARCHAR(100),
            run_timestamp TIMESTAMP_NTZ,
            status VARCHAR(20),
            duration_seconds FLOAT,
            notes VARCHAR(500)
        )
        """
        execute_query(conn, query)
        
        run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        status = 'SUCCESS' if success else 'FAILED'
        
        insert_query = """
        INSERT INTO MARTS.PIPELINE_RUNS (run_id, run_timestamp, status, duration_seconds)
        VALUES (%s, CURRENT_TIMESTAMP(), %s, %s)
        """
        
        execute_query(conn, insert_query, params=(run_id, status, duration))
        logger.info(f"Logged pipeline run: {run_id}")
    
    finally:
        conn.close()


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(
        description='Run complete fraud detection pipeline'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/snowflake_config.yml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--skip-dbt',
        action='store_true',
        help='Skip dbt model execution'
    )
    parser.add_argument(
        '--skip-alerts',
        action='store_true',
        help='Skip alert generation'
    )
    
    args = parser.parse_args()
    
    start_time = datetime.now()
    success = False
    
    try:
        logger.info("="*70)
        logger.info("FRAUD DETECTION PIPELINE STARTED")
        logger.info(f"Start time: {start_time}")
        logger.info("="*70)
        
        config = load_config(args.config)
        
        if not args.skip_dbt:
            if not run_dbt_models():
                raise RuntimeError("dbt model execution failed")
            
            run_dbt_tests()
        
        if not validate_data_quality(config):
            raise RuntimeError("Data quality checks failed")
        
        if not generate_predictions(config):
            raise RuntimeError("Prediction generation failed")
        
        if not args.skip_alerts:
            send_alerts(args.config)
        
        success = True
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("="*70)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info("="*70)
        
        log_pipeline_run(config, success, duration)
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        config = load_config(args.config) if args.config else {}
        log_pipeline_run(config, success, duration)
        
        sys.exit(1)


if __name__ == '__main__':
    main()

