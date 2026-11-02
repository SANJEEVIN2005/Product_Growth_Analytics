"""
scripts/export_cohort_outputs.py
Computes weekly cohort activity retention and repeat purchase retention in Oracle,
and exports both unpivoted and pivoted matrix CSV datasets to outputs/ for Power BI.
"""

import os
import sys
import oracledb
import pandas as pd

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.config import DB_USER, DB_PASS, DB_DSN

OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


print(f"Connecting to Oracle {DB_DSN} as {DB_USER}...")
conn = oracledb.connect(user=DB_USER, password=DB_PASS, dsn=DB_DSN)
print("Connected successfully.")

# 1. Weekly Visitor Activity Retention
print("\n--- 1. Computing Weekly Visitor Activity Retention ---")
sql_activity = """
WITH visitor_cohort AS (
    SELECT 
        visitorid,
        TRUNC(MIN(session_date), 'IW') AS cohort_week
    FROM fact_sessions
    GROUP BY visitorid
),
cohort_sizes AS (
    SELECT 
        cohort_week,
        COUNT(*) AS cohort_size
    FROM visitor_cohort
    GROUP BY cohort_week
),
visitor_activity AS (
    SELECT DISTINCT
        s.visitorid,
        vc.cohort_week,
        TRUNC(s.session_date, 'IW') AS activity_week,
        ROUND((TRUNC(s.session_date, 'IW') - vc.cohort_week) / 7) AS week_number
    FROM fact_sessions s
    JOIN visitor_cohort vc ON s.visitorid = vc.visitorid
)
SELECT 
    TO_CHAR(va.cohort_week, 'YYYY-MM-DD') AS cohort_week,
    cs.cohort_size,
    va.week_number,
    COUNT(DISTINCT va.visitorid) AS active_visitors,
    ROUND(COUNT(DISTINCT va.visitorid) * 100.0 / cs.cohort_size, 2) AS retention_rate_pct
FROM visitor_activity va
JOIN cohort_sizes cs ON va.cohort_week = cs.cohort_week
GROUP BY va.cohort_week, cs.cohort_size, va.week_number
ORDER BY va.cohort_week, va.week_number
"""
df_act = pd.read_sql(sql_activity, conn)
act_unpivot_path = os.path.join(OUTPUT_DIR, "cohort_retention_activity.csv")
df_act.to_csv(act_unpivot_path, index=False)
print(f"Saved unpivoted activity retention ({len(df_act)} rows) to {act_unpivot_path}")

# Pivot Activity Retention Matrix
df_act_pivot = df_act.pivot(index='COHORT_WEEK', columns='WEEK_NUMBER', values='RETENTION_RATE_PCT')
df_act_pivot.columns = [f"W{int(c)}" for c in df_act_pivot.columns]
act_matrix_path = os.path.join(OUTPUT_DIR, "cohort_retention_activity_matrix.csv")
df_act_pivot.to_csv(act_matrix_path)
print(f"Saved pivoted activity retention matrix ({len(df_act_pivot)} cohorts) to {act_matrix_path}")
print(df_act_pivot.iloc[:8, :10].to_string())

# 2. Buyer Repeat Purchase Retention
print("\n--- 2. Computing Buyer Repeat Purchase Retention ---")
sql_buyer_repeat = """
WITH buyer_first_txn AS (
    SELECT 
        visitorid,
        TRUNC(MIN(CASE WHEN has_purchase = 1 THEN session_date END), 'IW') AS first_purchase_week
    FROM fact_sessions
    GROUP BY visitorid
    HAVING MAX(has_purchase) = 1
),
cohort_buyers AS (
    SELECT 
        first_purchase_week AS buyer_cohort_week,
        COUNT(DISTINCT visitorid) AS buyer_cohort_size
    FROM buyer_first_txn
    GROUP BY first_purchase_week
),
buyer_subsequent_txns AS (
    SELECT DISTINCT
        s.visitorid,
        bft.first_purchase_week,
        TRUNC(s.session_date, 'IW') AS purchase_week,
        ROUND((TRUNC(s.session_date, 'IW') - bft.first_purchase_week) / 7) AS week_number
    FROM fact_sessions s
    JOIN buyer_first_txn bft ON s.visitorid = bft.visitorid
    WHERE s.has_purchase = 1
)
SELECT 
    TO_CHAR(bst.first_purchase_week, 'YYYY-MM-DD') AS first_purchase_week,
    cb.buyer_cohort_size,
    bst.week_number,
    COUNT(DISTINCT bst.visitorid) AS purchasing_visitors,
    ROUND(COUNT(DISTINCT bst.visitorid) * 100.0 / cb.buyer_cohort_size, 2) AS buyer_retention_pct
FROM buyer_subsequent_txns bst
JOIN cohort_buyers cb ON bst.first_purchase_week = cb.buyer_cohort_week
GROUP BY bst.first_purchase_week, cb.buyer_cohort_size, bst.week_number
ORDER BY bst.first_purchase_week, bst.week_number
"""
df_buy = pd.read_sql(sql_buyer_repeat, conn)
buy_unpivot_path = os.path.join(OUTPUT_DIR, "cohort_retention_purchase.csv")
df_buy.to_csv(buy_unpivot_path, index=False)
print(f"Saved unpivoted buyer purchase retention ({len(df_buy)} rows) to {buy_unpivot_path}")

# Pivot Buyer Purchase Retention Matrix
df_buy_pivot = df_buy.pivot(index='FIRST_PURCHASE_WEEK', columns='WEEK_NUMBER', values='BUYER_RETENTION_PCT')
df_buy_pivot.columns = [f"W{int(c)}" for c in df_buy_pivot.columns]
buy_matrix_path = os.path.join(OUTPUT_DIR, "cohort_retention_purchase_matrix.csv")
df_buy_pivot.to_csv(buy_matrix_path)
print(f"Saved pivoted buyer purchase retention matrix ({len(df_buy_pivot)} cohorts) to {buy_matrix_path}")
print(df_buy_pivot.iloc[:8, :10].to_string())

conn.close()
print("\nCohort retention exports successfully generated in outputs/.")
