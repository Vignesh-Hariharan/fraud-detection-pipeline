-- Snowflake Setup Script
-- Creates database, schemas, warehouse, and base tables for fraud detection pipeline

-- Create warehouse
CREATE WAREHOUSE IF NOT EXISTS COMPUTE_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 300
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE;

-- Create database
CREATE DATABASE IF NOT EXISTS FRAUD_DETECTION_DB;

USE DATABASE FRAUD_DETECTION_DB;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS RAW;
CREATE SCHEMA IF NOT EXISTS MARTS;

-- Use RAW schema for base tables
USE SCHEMA RAW;

-- Create transactions table
CREATE TABLE IF NOT EXISTS TRANSACTIONS (
    trans_num VARCHAR(100) PRIMARY KEY,
    trans_date_trans_time TIMESTAMP_NTZ,
    cc_num BIGINT,
    merchant VARCHAR(200),
    category VARCHAR(50),
    amt FLOAT,
    first VARCHAR(50),
    last VARCHAR(50),
    gender VARCHAR(1),
    street VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(2),
    zip INT,
    lat FLOAT,
    long FLOAT,
    city_pop INT,
    job VARCHAR(100),
    dob DATE,
    unix_time BIGINT,
    merch_lat FLOAT,
    merch_long FLOAT,
    is_fraud INT
);

-- Grant basic permissions to public role for initial setup
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE PUBLIC;
GRANT USAGE ON DATABASE FRAUD_DETECTION_DB TO ROLE PUBLIC;
GRANT USAGE ON SCHEMA RAW TO ROLE PUBLIC;
GRANT USAGE ON SCHEMA MARTS TO ROLE PUBLIC;

