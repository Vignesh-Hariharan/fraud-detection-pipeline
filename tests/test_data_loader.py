import pytest
import pandas as pd
from scripts.load_data import validate_schema, REQUIRED_COLUMNS


def test_validate_schema_success():
    """Test that validate_schema passes with all required columns."""
    df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    
    try:
        validate_schema(df)
    except ValueError:
        pytest.fail("validate_schema raised ValueError unexpectedly")


def test_validate_schema_missing_columns():
    """Test that validate_schema fails when required columns are missing."""
    df = pd.DataFrame(columns=['trans_num', 'amt', 'merchant'])
    
    with pytest.raises(ValueError) as exc_info:
        validate_schema(df)
    
    assert "Missing required columns" in str(exc_info.value)


def test_validate_schema_extra_columns():
    """Test that validate_schema passes with extra columns."""
    columns = REQUIRED_COLUMNS + ['extra_column_1', 'extra_column_2']
    df = pd.DataFrame(columns=columns)
    
    try:
        validate_schema(df)
    except ValueError:
        pytest.fail("validate_schema raised ValueError unexpectedly")


def test_validate_schema_empty_dataframe():
    """Test that validate_schema works with empty but correctly structured DataFrame."""
    df = pd.DataFrame(columns=REQUIRED_COLUMNS)
    
    try:
        validate_schema(df)
    except ValueError:
        pytest.fail("validate_schema raised ValueError unexpectedly")

