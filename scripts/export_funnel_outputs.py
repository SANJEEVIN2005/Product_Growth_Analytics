"""
scripts/export_funnel_outputs.py
Executes full-funnel queries and exports clean CSV datasets to outputs/ for Power BI.
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

def run_and_export(sql: str, filename: str, label: str) -> pd.DataFrame:
    print(f"\n--- Running: {label} ---")
    df = pd.read_sql(sql, conn)
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path, index=False)
    print(f"Saved {len(df)} rows to {path}")
    print(df.to_string())
    return df

# 1. Overall Funnel (Visitor and Session level)
sql_overall = """
SELECT 
    'Visitor Level' AS funnel_level,
    COUNT(*) AS total_units,
    SUM(has_view) AS view_stage,
    SUM(has_cart) AS cart_stage,
    SUM(has_purchase) AS purchase_stage,
    ROUND(SUM(has_cart) * 100.0 / NULLIF(SUM(has_view), 0), 2) AS view_to_cart_pct,
    ROUND((1 - SUM(has_cart) / NULLIF(SUM(has_view), 0)) * 100.0, 2) AS view_to_cart_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_cart), 0), 2) AS cart_to_purchase_pct,
    ROUND((1 - SUM(has_purchase) / NULLIF(SUM(has_cart), 0)) * 100.0, 2) AS cart_to_purchase_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_view), 0), 3) AS overall_cvr_pct
FROM (
    SELECT 
        visitorid,
        MAX(has_view) AS has_view,
        MAX(has_cart) AS has_cart,
        MAX(has_purchase) AS has_purchase
    FROM fact_sessions
    GROUP BY visitorid
)
UNION ALL
SELECT 
    'Session Level' AS funnel_level,
    COUNT(*) AS total_units,
    SUM(has_view) AS view_stage,
    SUM(has_cart) AS cart_stage,
    SUM(has_purchase) AS purchase_stage,
    ROUND(SUM(has_cart) * 100.0 / NULLIF(SUM(has_view), 0), 2) AS view_to_cart_pct,
    ROUND((1 - SUM(has_cart) / NULLIF(SUM(has_view), 0)) * 100.0, 2) AS view_to_cart_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_cart), 0), 2) AS cart_to_purchase_pct,
    ROUND((1 - SUM(has_purchase) / NULLIF(SUM(has_cart), 0)) * 100.0, 2) AS cart_to_purchase_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_view), 0), 3) AS overall_cvr_pct
FROM fact_sessions
"""
run_and_export(sql_overall, "funnel_overall.csv", "Overall Funnel (Visitor vs Session Level)")

# 2. Funnel by Visitor Type (New vs Returning Session)
sql_vis_type = """
SELECT 
    CASE WHEN is_returning = 0 THEN 'New Visitor Session' 
         ELSE 'Returning Visitor Session' 
    END AS visitor_session_type,
    COUNT(*) AS total_sessions,
    SUM(has_view) AS view_sessions,
    SUM(has_cart) AS cart_sessions,
    SUM(has_purchase) AS purchase_sessions,
    ROUND(SUM(has_cart) * 100.0 / NULLIF(SUM(has_view), 0), 2) AS view_to_cart_cvr_pct,
    ROUND((1 - SUM(has_cart) / NULLIF(SUM(has_view), 0)) * 100.0, 2) AS view_to_cart_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_cart), 0), 2) AS cart_to_purchase_cvr_pct,
    ROUND((1 - SUM(has_purchase) / NULLIF(SUM(has_cart), 0)) * 100.0, 2) AS cart_to_purchase_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_view), 0), 3) AS overall_session_cvr_pct
FROM fact_sessions
GROUP BY is_returning
ORDER BY is_returning
"""
run_and_export(sql_vis_type, "funnel_by_visitor_type.csv", "Funnel by Visitor Session Type (New vs Returning)")

# 3. Funnel by Top Product Category
sql_category = """
SELECT 
    NVL(TO_CHAR(top_category_id), 'Unclassified') AS top_category_id,
    COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS views,
    COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) AS carts,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS purchases,
    COUNT(DISTINCT visitorid) AS distinct_visitors,
    COUNT(DISTINCT CASE WHEN event_type = 'transaction' THEN visitorid END) AS purchasing_visitors,
    ROUND(
        COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 
        2
    ) AS view_to_cart_cvr_pct,
    ROUND(
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END), 0), 
        2
    ) AS cart_to_purchase_cvr_pct,
    ROUND(
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 
        3
    ) AS overall_view_to_purchase_cvr_pct
FROM fact_events_sessionized
GROUP BY top_category_id
ORDER BY views DESC
"""
run_and_export(sql_category, "funnel_by_category.csv", "Funnel by Top-Level Category")

# 4. Funnel by Hour of Day
sql_hour = """
SELECT 
    event_hour,
    COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS views,
    COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) AS carts,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS purchases,
    ROUND(
        COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 
        2
    ) AS view_to_cart_cvr_pct,
    ROUND(
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END), 0), 
        2
    ) AS cart_to_purchase_cvr_pct,
    ROUND(
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 
        3
    ) AS overall_cvr_pct
FROM fact_events_sessionized
GROUP BY event_hour
ORDER BY event_hour
"""
run_and_export(sql_hour, "funnel_by_hour.csv", "Funnel by Hour of Day (0-23 UTC)")

# 5. Sessions Distribution & Metrics Summary
sql_sessions_summary = """
SELECT 
    CASE 
        WHEN duration_seconds = 0 THEN '0s (Single Event)'
        WHEN duration_seconds <= 60 THEN '1-60s'
        WHEN duration_seconds <= 300 THEN '1-5m'
        WHEN duration_seconds <= 900 THEN '5-15m'
        ELSE '15m+'
    END AS duration_tier,
    COUNT(*) AS session_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_sessions,
    SUM(has_cart) AS cart_sessions,
    SUM(has_purchase) AS purchase_sessions,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(COUNT(*), 0), 3) AS session_cvr_pct
FROM fact_sessions
GROUP BY 
    CASE 
        WHEN duration_seconds = 0 THEN '0s (Single Event)'
        WHEN duration_seconds <= 60 THEN '1-60s'
        WHEN duration_seconds <= 300 THEN '1-5m'
        WHEN duration_seconds <= 900 THEN '5-15m'
        ELSE '15m+'
    END
ORDER BY MIN(duration_seconds)
"""
run_and_export(sql_sessions_summary, "sessions_summary.csv", "Session Duration and Conversion Summary")

conn.close()
print("\nFunnel exports successfully generated in outputs/.")
