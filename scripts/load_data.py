"""
Load Kaggle fraud dataset into Snowflake.

Usage:
    python scripts/load_data.py --config config/snowflake_config.yml
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import yaml
from dotenv import load_dotenv
from kaggle.api.kaggle_api_extended import KaggleApi

from scripts.utils.logger import get_logger
from scripts.utils.snowflake_utils import get_connection, execute_query

load_dotenv()
logger = get_logger(__name__)

REQUIRED_COLUMNS = [
    'trans_num', 'trans_date_trans_time', 'cc_num', 'merchant', 'category',
    'amt', 'first', 'last', 'gender', 'street', 'city', 'state', 'zip',
    'lat', 'long', 'city_pop', 'job', 'dob', 'unix_time', 'merch_lat',
    'merch_long', 'is_fraud'
]

KAGGLE_DATASET = 'kartik2112/fraud-detection'
KAGGLE_FILE = 'fraudTrain.csv'
DATA_DIR = Path(__file__).parent.parent / 'data'


def download_kaggle_dataset() -> Path:
    logger.info(f"Downloading dataset: {KAGGLE_DATASET}")
    
    try:
        api = KaggleApi()
        api.authenticate()
    except Exception as e:
        raise RuntimeError(
            "Failed to authenticate with Kaggle API. "
            "Make sure you have ~/.kaggle/kaggle.json with your credentials."
        ) from e
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        api.dataset_download_file(
            KAGGLE_DATASET,
            file_name=KAGGLE_FILE,
            path=DATA_DIR
        )
        
        csv_path = DATA_DIR / KAGGLE_FILE
        zip_path = DATA_DIR / f"{KAGGLE_FILE}.zip"
        
        if zip_path.exists():
            import zipfile
            logger.info(f"Extracting {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(DATA_DIR)
            zip_path.unlink()
        
        if not csv_path.exists():
            raise RuntimeError(f"Expected file not found after download: {csv_path}")
        
        logger.info(f"Successfully downloaded dataset to {csv_path}")
        return csv_path
    
    except Exception as e:
        raise RuntimeError(f"Failed to download dataset from Kaggle: {e}") from e


def load_config(config_path: str) -> Dict[str, Any]:
    # Load config from YAML file, fall back to env vars if not found
    if not os.path.exists(config_path):
        logger.info(f"Config file not found: {config_path}, using environment variables from .env")
        return {}
    
    logger.info(f"Loading configuration from {config_path}")
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config or {}


def validate_schema(df: pd.DataFrame) -> None:
    missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)
    
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}. "
            f"Expected columns: {REQUIRED_COLUMNS}"
        )
    
    logger.info(f"Schema validation passed. Found {len(df.columns)} columns, {len(df)} rows")


def load_to_snowflake(df: pd.DataFrame, config: Dict[str, Any]) -> int:
    logger.info("Connecting to Snowflake...")
    conn = get_connection(config)
    
    try:
        snowflake_config = config.get('snowflake', {})
        database = snowflake_config.get('database') or os.getenv('SNOWFLAKE_DATABASE', 'FRAUD_DETECTION_DB')
        schema = snowflake_config.get('schema') or os.getenv('SNOWFLAKE_SCHEMA', 'RAW')
        
        execute_query(conn, f"USE DATABASE {database}")
        execute_query(conn, f"USE SCHEMA {schema}")
        
        logger.info("Truncating existing data in TRANSACTIONS table...")
        execute_query(conn, "TRUNCATE TABLE IF EXISTS TRANSACTIONS")
        
        logger.info(f"Loading {len(df)} rows to Snowflake...")
        
        # Use executemany for reliable batch inserts
        cursor = conn.cursor()
        cursor.execute(f"USE DATABASE {database}")
        cursor.execute(f"USE SCHEMA {schema}")
        
        # Prepare data tuples
        logger.info("Preparing data for insert...")
        df = df.fillna('')  # Replace NaN with empty string
        
        data = [
            (
                str(row['trans_num']),
                str(row['trans_date_trans_time']),
                int(row['cc_num']) if pd.notna(row['cc_num']) else None,
                str(row['merchant']),
                str(row['category']),
                float(row['amt']) if pd.notna(row['amt']) else None,
                str(row['first']),
                str(row['last']),
                str(row['gender']),
                str(row['street']),
                str(row['city']),
                str(row['state']),
                int(row['zip']) if pd.notna(row['zip']) else None,
                float(row['lat']) if pd.notna(row['lat']) else None,
                float(row['long']) if pd.notna(row['long']) else None,
                int(row['city_pop']) if pd.notna(row['city_pop']) else None,
                str(row['job']),
                str(row['dob']),
                int(row['unix_time']) if pd.notna(row['unix_time']) else None,
                float(row['merch_lat']) if pd.notna(row['merch_lat']) else None,
                float(row['merch_long']) if pd.notna(row['merch_long']) else None,
                int(row['is_fraud']) if pd.notna(row['is_fraud']) else None
            )
            for _, row in df.iterrows()
        ]
        
        # Bulk insert in batches
        insert_sql = f"""
            INSERT INTO {database}.{schema}.TRANSACTIONS VALUES 
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        batch_size = 10000
        total_rows = len(data)
        rows_loaded = 0
        
        logger.info(f"Executing batch insert ({batch_size} rows per batch)...")
        
        for i in range(0, total_rows, batch_size):
            batch = data[i:i + batch_size]
            cursor.executemany(insert_sql, batch)
            rows_loaded += len(batch)
            
            if i % (batch_size * 5) == 0:
                pct = (rows_loaded * 100) // total_rows
                logger.info(f"Loaded {rows_loaded:,} / {total_rows:,} rows ({pct}%)")
        
        cursor.close()
        
        logger.info(f"Successfully loaded {rows_loaded:,} rows")
        return rows_loaded
    
    except Exception as e:
        logger.error(f"Failed to load data to Snowflake: {e}")
        raise
    
    finally:
        conn.close()
        logger.info("Snowflake connection closed")


def create_sample(df: pd.DataFrame, sample_size: int = 100) -> None:
    sample_path = DATA_DIR / 'sample_transactions.csv'
    
    sample_df = df.sample(n=min(sample_size, len(df)), random_state=42)
    sample_df.to_csv(sample_path, index=False)
    
    logger.info(f"Created sample file with {len(sample_df)} rows: {sample_path}")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Load fraud detection dataset from Kaggle to Snowflake'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/snowflake_config.yml',
        help='Path to Snowflake configuration file'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip Kaggle download (use existing CSV)'
    )
    
    args = parser.parse_args()
    
    try:
        csv_path = DATA_DIR / KAGGLE_FILE
        
        if not args.skip_download or not csv_path.exists():
            csv_path = download_kaggle_dataset()
        else:
            logger.info(f"Using existing CSV: {csv_path}")
        
        logger.info(f"Reading CSV file: {csv_path}")
        df = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
        
        validate_schema(df)
        
        config = load_config(args.config)
        
        rows_loaded = load_to_snowflake(df, config)
        
        create_sample(df)
        
        logger.info("=" * 60)
        logger.info("DATA LOAD COMPLETED SUCCESSFULLY")
        logger.info(f"Total rows loaded: {rows_loaded:,}")
        logger.info(f"Fraud rate: {df['is_fraud'].mean()*100:.3f}%")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Data load failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

