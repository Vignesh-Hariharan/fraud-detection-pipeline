import os
from typing import Any, Dict, List, Optional, Tuple
import snowflake.connector
from snowflake.connector import SnowflakeConnection
from snowflake.connector.cursor import SnowflakeCursor
from scripts.utils.logger import get_logger

logger = get_logger(__name__)


def get_connection(config: Dict[str, Any]) -> SnowflakeConnection:
    # Create Snowflake connection from config or env vars
    snowflake_config = config.get('snowflake', {})
    
    account = snowflake_config.get('account') or os.getenv('SNOWFLAKE_ACCOUNT')
    user = snowflake_config.get('user') or os.getenv('SNOWFLAKE_USER')
    password = snowflake_config.get('password') or os.getenv('SNOWFLAKE_PASSWORD')
    warehouse = snowflake_config.get('warehouse') or os.getenv('SNOWFLAKE_WAREHOUSE')
    database = snowflake_config.get('database') or os.getenv('SNOWFLAKE_DATABASE')
    schema = snowflake_config.get('schema') or os.getenv('SNOWFLAKE_SCHEMA')
    role = snowflake_config.get('role') or os.getenv('SNOWFLAKE_ROLE', 'ACCOUNTADMIN')
    
    if not all([account, user, password]):
        raise ValueError(
            "Missing Snowflake credentials. Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD"
        )
    
    logger.info(f"Connecting to Snowflake account: {account}")
    
    try:
        conn = snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role
        )
        logger.info("Successfully connected to Snowflake")
        return conn
    
    except snowflake.connector.Error as e:
        logger.error(f"Failed to connect to Snowflake: {e}")
        raise


def execute_query(
    conn: SnowflakeConnection,
    query: str,
    params: Optional[Tuple] = None,
    fetch: bool = False
) -> Optional[List[Tuple]]:
    cursor = None
    try:
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            results = cursor.fetchall()
            logger.info(f"Query returned {len(results)} rows")
            return results
        else:
            logger.info(f"Query executed successfully, {cursor.rowcount} rows affected")
            return None
    
    except snowflake.connector.Error as e:
        logger.error(f"Query execution failed: {e}")
        logger.error(f"Query: {query[:200]}...")
        raise
    
    finally:
        if cursor:
            cursor.close()


def execute_file(conn: SnowflakeConnection, sql_file_path: str) -> None:
    logger.info(f"Executing SQL file: {sql_file_path}")
    
    with open(sql_file_path, 'r') as f:
        sql_content = f.read()
    
    statements = [s.strip() for s in sql_content.split(';') if s.strip()]
    
    for i, statement in enumerate(statements, 1):
        logger.info(f"Executing statement {i}/{len(statements)}")
        execute_query(conn, statement)
    
    logger.info(f"Successfully executed all statements from {sql_file_path}")

