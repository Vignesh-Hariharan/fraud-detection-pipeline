# Data Dictionary

## Dataset Source

**Kaggle: Credit Card Transactions Fraud Detection Dataset**

- **URL**: https://www.kaggle.com/datasets/kartik2112/fraud-detection
- **License**: CC0: Public Domain
- **Size**: ~1.3M transactions
- **Fraud Rate**: ~0.17% (highly imbalanced)
- **Time Period**: January 2019 - December 2020

This is a simulated dataset created for fraud detection research and education. It is NOT real bank transaction data.

## Schema

### fraudTrain.csv

| Column | Type | Description |
|--------|------|-------------|
| `trans_num` | String | Unique transaction identifier (UUID format) |
| `trans_date_trans_time` | Timestamp | Transaction date and time |
| `cc_num` | Integer | Credit card number (customer identifier) |
| `merchant` | String | Merchant name |
| `category` | String | Transaction category (e.g., grocery_pos, gas_transport) |
| `amt` | Float | Transaction amount in USD |
| `first` | String | Cardholder first name |
| `last` | String | Cardholder last name |
| `gender` | String | Cardholder gender (M/F) |
| `street` | String | Cardholder street address |
| `city` | String | Cardholder city |
| `state` | String | Cardholder state (2-letter code) |
| `zip` | Integer | Cardholder ZIP code |
| `lat` | Float | Transaction latitude |
| `long` | Float | Transaction longitude |
| `city_pop` | Integer | Population of transaction city |
| `job` | String | Cardholder job title |
| `dob` | Date | Cardholder date of birth |
| `trans_num` | String | Transaction number |
| `unix_time` | Integer | Unix timestamp of transaction |
| `merch_lat` | Float | Merchant latitude |
| `merch_long` | Float | Merchant longitude |
| `is_fraud` | Integer | Fraud label (0 = legitimate, 1 = fraud) |

## Key Characteristics

- **Temporal ordering**: Transactions are ordered chronologically
- **Customer cardinality**: ~1,000 unique customers
- **Merchant cardinality**: ~690 unique merchants
- **Category cardinality**: 14 transaction categories
- **Geographic spread**: Covers all 50 US states

## Usage Notes

1. This dataset is provided for educational and portfolio demonstration purposes
2. The fraud patterns in this dataset are simulated and may not reflect real-world fraud exactly
3. For production fraud detection, you would need to work with actual transaction data from your institution
4. The dataset creators have explicitly balanced realism with privacy considerations

