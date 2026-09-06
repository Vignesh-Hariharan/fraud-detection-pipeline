"""
Measure the effect of the feature leakage documented in the main README.

The Snowflake pipeline computed two families of features over the full dataset
before any train/test split:

  * customer_avg_amount / amount_z_score  -- a customer's average includes their
    own future transactions (point-in-time leakage);
  * merchant_fraud_rate = AVG(is_fraud)   -- computed per merchant across all
    rows, so the feature encodes the label itself, including the current row's.

This script rebuilds both feature families two ways on 1,048,575 rows from the
HuggingFace fraudTrain.csv (Sparkov is listed as ~1.3M; this is the file V2 ran):
once with the leak (full-dataset aggregates) and once point-in-time (expanding
windows that see only prior transactions). It trains the same model on each with a
time-based split, and reports the difference. Nothing here needs Snowflake.

Run:  python v2/leakage_experiment.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

import duckdb
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "fraudTrain.csv"
DATA_URL = (
    "https://huggingface.co/datasets/dazzle-nu/"
    "CIS435-CreditCardFraudDetection/resolve/main/fraudTrain.csv"
)

SHARED = [
    "amount", "txns_last_24h", "txns_last_7d", "minutes_since_last_txn",
    "hour_of_day", "is_weekend", "is_late_night", "customer_age", "is_new_max_amount",
]
LEAKY = ["cust_avg_full", "cust_std_full", "amount_z_full", "merch_rate_full"]
CORRECT = ["cust_avg_pit", "cust_std_pit", "amount_z_pit", "merch_rate_pit"]


def fetch() -> None:
    if DATA.exists():
        return
    DATA.parent.mkdir(parents=True, exist_ok=True)
    print("downloading fraud dataset (~266MB) ...")
    urllib.request.urlretrieve(DATA_URL, DATA)


def build_features() -> "duckdb.DuckDBPyRelation":
    """Compute both feature sets in one pass with DuckDB window functions."""
    con = duckdb.connect()
    src = f"read_csv('{DATA}', header=true, ignore_errors=true)"
    return con.execute(f"""
        WITH base AS (
            SELECT
                cc_num                         AS customer_id,
                merchant,
                trans_num,
                CAST(amt AS DOUBLE)            AS amount,
                CAST(unix_time AS BIGINT)      AS ut,
                to_timestamp(CAST(unix_time AS BIGINT)) AS ts,
                city,
                TRY_CAST(dob AS DATE)          AS dob_date,
                CAST(is_fraud AS INTEGER)      AS is_fraud
            FROM {src}
            WHERE unix_time IS NOT NULL AND amt IS NOT NULL
        ),
        cust_full AS (
            SELECT customer_id, AVG(amount) avg_a, STDDEV(amount) std_a FROM base GROUP BY customer_id
        ),
        merch_full AS (
            SELECT merchant, AVG(CAST(is_fraud AS DOUBLE)) rate FROM base GROUP BY merchant
        )
        SELECT
            b.is_fraud,
            b.ut,
            b.amount,
            -- shared, point-in-time in both models
            COUNT(*) OVER w24 - 1                                              AS txns_last_24h,
            COUNT(*) OVER w7d - 1                                              AS txns_last_7d,
            (b.ut - LAG(b.ut) OVER wc) / 60.0                                  AS minutes_since_last_txn,
            EXTRACT(hour FROM b.ts)                                            AS hour_of_day,
            CASE WHEN EXTRACT(dow FROM b.ts) IN (0, 6) THEN 1 ELSE 0 END       AS is_weekend,
            CASE WHEN EXTRACT(hour FROM b.ts) BETWEEN 2 AND 5 THEN 1 ELSE 0 END AS is_late_night,
            DATE_DIFF('year', b.dob_date, b.ts)                               AS customer_age,
            CASE WHEN b.amount > COALESCE(MAX(b.amount) OVER wc_prior, 0) THEN 1 ELSE 0 END AS is_new_max_amount,

            -- LEAKY: full-dataset aggregates (what the pipeline did)
            cf.avg_a                                                          AS cust_avg_full,
            cf.std_a                                                          AS cust_std_full,
            (b.amount - cf.avg_a) / NULLIF(cf.std_a, 0)                       AS amount_z_full,
            mf.rate                                                           AS merch_rate_full,

            -- CORRECT: expanding, prior rows only (point-in-time)
            AVG(b.amount) OVER wc_prior                                       AS cust_avg_pit,
            STDDEV(b.amount) OVER wc_prior                                    AS cust_std_pit,
            (b.amount - AVG(b.amount) OVER wc_prior) / NULLIF(STDDEV(b.amount) OVER wc_prior, 0) AS amount_z_pit,
            (SUM(CAST(b.is_fraud AS DOUBLE)) OVER wm_prior)
                / NULLIF(COUNT(*) OVER wm_prior, 0)                           AS merch_rate_pit
        FROM base b
        LEFT JOIN cust_full  cf USING (customer_id)
        LEFT JOIN merch_full mf USING (merchant)
        WINDOW
            wc       AS (PARTITION BY b.customer_id ORDER BY b.ut, b.trans_num),
            wc_prior AS (PARTITION BY b.customer_id ORDER BY b.ut, b.trans_num ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
            wm_prior AS (PARTITION BY b.merchant    ORDER BY b.ut, b.trans_num ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
            w24      AS (PARTITION BY b.customer_id ORDER BY b.ut RANGE BETWEEN 86400 PRECEDING AND CURRENT ROW),
            w7d      AS (PARTITION BY b.customer_id ORDER BY b.ut RANGE BETWEEN 604800 PRECEDING AND CURRENT ROW)
        ORDER BY b.ut, b.trans_num
    """).df()


def evaluate(df, feature_cols: list[str], cutoff: int) -> dict:
    train = df[df["ut"] <= cutoff]
    test = df[df["ut"] > cutoff]
    Xtr, ytr = train[feature_cols].to_numpy(dtype="float64"), train["is_fraud"].to_numpy()
    Xte, yte = test[feature_cols].to_numpy(dtype="float64"), test["is_fraud"].to_numpy()

    # early_stopping off + fixed seed makes the run reproducible.
    model = HistGradientBoostingClassifier(
        max_iter=200, learning_rate=0.1, early_stopping=False, random_state=42
    )
    model.fit(Xtr, ytr)
    scores = model.predict_proba(Xte)[:, 1]

    # Realistic fraud operating point: flag the top 1% highest-risk transactions.
    k = max(1, int(len(scores) * 0.01))
    threshold = np.sort(scores)[-k]
    flagged = scores >= threshold
    tp = int(((flagged == 1) & (yte == 1)).sum())
    precision = tp / max(1, flagged.sum())
    recall = tp / max(1, yte.sum())
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "roc_auc": roc_auc_score(yte, scores),
        "pr_auc": average_precision_score(yte, scores),
        "precision@1%": precision,
        "recall@1%": recall,
        "f1@1%": f1,
    }


def main() -> None:
    fetch()
    print("building features (both leaky and point-in-time) ...")
    df = build_features()
    print(f"  rows: {len(df):,}   fraud rate: {df['is_fraud'].mean() * 100:.3f}%")

    # 80/20 time-based split.
    cutoff = int(df["ut"].quantile(0.80))

    leaky = evaluate(df, SHARED + LEAKY, cutoff)
    correct = evaluate(df, SHARED + CORRECT, cutoff)

    metrics = ["roc_auc", "pr_auc", "precision@1%", "recall@1%", "f1@1%"]
    print("\n  metric            leaky (V1)   corrected (V2)")
    print("  " + "-" * 46)
    lines = ["metric,leaky_v1,corrected_v2"]
    for m in metrics:
        print(f"  {m:<16} {leaky[m]:>10.4f}   {correct[m]:>12.4f}")
        lines.append(f"{m},{leaky[m]:.4f},{correct[m]:.4f}")
    (HERE / "results.csv").write_text("\n".join(lines) + "\n")

    gap = (leaky["pr_auc"] - correct["pr_auc"]) / correct["pr_auc"] * 100
    print(f"\n  PR-AUC is {gap:+.0f}% higher on the leaky features -- optimistic")
    print("  performance that does not survive a point-in-time split.")
    print("  results written to v2/results.csv")


if __name__ == "__main__":
    main()
