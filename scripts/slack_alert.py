"""
Send Slack alerts for high-risk fraud predictions.

Usage:
    python scripts/slack_alert.py --limit 5
    python scripts/slack_alert.py --limit 5 --dry-run
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent))

import requests
import yaml
from dotenv import load_dotenv

from scripts.utils.logger import get_logger
from scripts.utils.snowflake_utils import get_connection, execute_query

logger = get_logger(__name__)

load_dotenv()


def load_config(config_path: str) -> Dict[str, Any]:
    if not os.path.exists(config_path):
        logger.warning(f"Config file not found: {config_path}, using environment variables")
        return {}
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def get_high_risk_transactions(config: Dict[str, Any], limit: int = 10) -> List[Tuple]:
    logger.info("Querying high-risk transactions...")
    
    conn = get_connection(config)
    
    try:
        query = """
        SELECT
            transaction_id,
            customer_id,
            transaction_timestamp,
            transaction_amount,
            fraud_probability,
            risk_level
        FROM FRAUD_DETECTION_DB.MARTS_MARTS.HIGH_RISK_TRANSACTIONS
        WHERE risk_level = 'CRITICAL'
        ORDER BY fraud_probability DESC
        LIMIT {}
        """.format(limit)
        
        cursor = conn.cursor()
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        
        logger.info(f"Found {len(results)} high-risk transactions")
        return results
    
    finally:
        conn.close()


def build_slack_payload(transactions: List[Tuple]) -> Dict[str, Any]:
    total_count = len(transactions)
    total_amount = sum(t[3] for t in transactions)
    
    message_blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"CRITICAL Fraud Alert: {total_count} transactions detected"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Total Amount at Risk:* ${total_amount:,.2f}\n*Risk Level:* CRITICAL (90%+ confidence)\n*Model:* BASELINE (6 features)"
            }
        },
        {
            "type": "divider"
        }
    ]
    
    sample_size = min(5, total_count)
    
    if sample_size > 0:
        message_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Top {sample_size} Transactions:*"
            }
        })
        
        for idx, txn in enumerate(transactions[:sample_size], 1):
            txn_id, customer_id, timestamp, amount, probability, risk = txn
            
            message_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Transaction #{idx}*"
                }
            })
            
            message_blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Transaction ID:*\n{txn_id}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Amount:*\n${amount:,.2f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Probability:*\n{probability:.2%}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{timestamp}"
                    }
                ]
            })
            
            if idx < sample_size:
                message_blocks.append({
                    "type": "divider"
                })
    
    if total_count > sample_size:
        message_blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_{total_count - sample_size} more high-risk transactions not shown_"
                }
            ]
        })
    
    return {"blocks": message_blocks}


def send_slack_notification(payload: Dict[str, Any]) -> None:
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    
    if not webhook_url:
        raise ValueError("SLACK_WEBHOOK_URL not set in .env file")
    
    logger.info("Sending Slack notification...")
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        response.raise_for_status()
        logger.info("Slack notification sent successfully")
    
    except requests.RequestException as e:
        logger.error(f"Failed to send Slack notification: {e}")
        raise


def mark_as_alerted(transaction_ids: List[str], config: Dict[str, Any]) -> None:
    # Mark transactions as alerted (skipped for demo)
    logger.info(f"Would mark {len(transaction_ids)} transactions as alerted (skipped for demo)")
    return


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Send Slack alerts for high-risk fraud transactions'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/snowflake_config.yml',
        help='Path to Snowflake configuration file'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum number of transactions to alert on'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Query transactions but do not send alerts or update database'
    )
    
    args = parser.parse_args()
    
    try:
        config = load_config(args.config)
        
        transactions = get_high_risk_transactions(config, args.limit)
        
        if not transactions:
            logger.info("No high-risk transactions to alert on")
            return
        
        payload = build_slack_payload(transactions)
        
        if args.dry_run:
            logger.info("Dry run mode - would send the following payload:")
            logger.info(payload)
            return
        
        send_slack_notification(payload)
        
        transaction_ids = [txn[0] for txn in transactions]
        mark_as_alerted(transaction_ids, config)
        
        logger.info("=" * 60)
        logger.info("ALERT PROCESS COMPLETED")
        logger.info(f"Alerted on {len(transactions)} high-risk transactions")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Alert process failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

