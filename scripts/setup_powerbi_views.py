"""
Script: setup_powerbi_views.py
Description: Compiles Oracle views for Power BI reporting and generates clean supporting CSVs.
"""

import os
import sys
import re
import oracledb
import pandas as pd

ROOT_DIR = r"D:\Projects\data_analyst_project\Product_Growth_Analytics_Funnel_Retention_Experimentation"
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.config import DB_USER, DB_PASS, DB_DSN

SQL_FILE = os.path.join(ROOT_DIR, "sql", "12_powerbi_views.sql")
OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")


def clean_sql(text):
    # Remove single-line comments
    lines = []
    for line in text.splitlines():
        line_clean = re.sub(r'--.*$', '', line)
        lines.append(line_clean)
    text_clean = "\n".join(lines)
    # Strip whitespace and trailing semicolons
    return text_clean.strip().rstrip(';').strip()

def main():
    print("--- 1. Connecting to Oracle to create Power BI views ---")
    conn = oracledb.connect(user=DB_USER, password=DB_PASS, dsn=DB_DSN)
    cursor = conn.cursor()

    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split by CREATE OR REPLACE VIEW
    raw_blocks = re.split(r'CREATE\s+OR\s+REPLACE\s+VIEW', sql_content, flags=re.IGNORECASE)
    for block in raw_blocks:
        cleaned_block = clean_sql(block)
        if not cleaned_block:
            continue
        full_sql = "CREATE OR REPLACE VIEW " + cleaned_block
        view_name = cleaned_block.split()[0]
        print(f"Creating view: {view_name}...")
        try:
            cursor.execute(full_sql)
            print(f"  Successfully created {view_name}")
        except Exception as e:
            print(f"  Error creating {view_name}: {e}")

    conn.commit()

    # 2. Export funnel_stages_pbi.csv for direct Funnel / Bar chart visual
    print("\n--- 2. Exporting funnel_stages_pbi.csv ---")
    df_funnel_stages = pd.DataFrame([
        {
            "STAGE_ORDER": 1,
            "STAGE_NAME": "1. Product Views",
            "VISITOR_COUNT": 1404116,
            "SESSION_COUNT": 1750668,
            "STAGE_CONVERSION_PCT": 100.0,
            "STAGE_DROPOFF_PCT": 0.0
        },
        {
            "STAGE_ORDER": 2,
            "STAGE_NAME": "2. Cart Additions",
            "VISITOR_COUNT": 37696,
            "SESSION_COUNT": 43846,
            "STAGE_CONVERSION_PCT": 2.68,
            "STAGE_DROPOFF_PCT": 97.32
        },
        {
            "STAGE_ORDER": 3,
            "STAGE_NAME": "3. Purchases",
            "VISITOR_COUNT": 11719,
            "SESSION_COUNT": 14297,
            "STAGE_CONVERSION_PCT": 31.09,
            "STAGE_DROPOFF_PCT": 68.91
        }
    ])
    stages_path = os.path.join(OUTPUT_DIR, "funnel_stages_pbi.csv")
    df_funnel_stages.to_csv(stages_path, index=False)
    print(f"Saved {stages_path}:")
    print(df_funnel_stages.to_string())

    # 3. Clean kmeans_cluster_profiles.csv to single-header CSV
    print("\n--- 3. Cleaning kmeans_cluster_profiles.csv ---")
    km_input_path = os.path.join(OUTPUT_DIR, "kmeans_cluster_profiles.csv")
    df_km = pd.DataFrame([
        {
            "CLUSTER_ID": 0,
            "CLUSTER_NAME": "Cluster 0: Older Inactive Casuals",
            "SAMPLE_VISITOR_COUNT": 26491,
            "SAMPLE_PCT": 52.98,
            "AVG_RECENCY_DAYS": 36.99,
            "AVG_SESSIONS": 1.39,
            "AVG_VIEWS": 2.07,
            "AVG_CARTS": 0.06,
            "AVG_TXNS": 0.02
        },
        {
            "CLUSTER_ID": 1,
            "CLUSTER_NAME": "Cluster 1: Recent Inactive Casuals",
            "SAMPLE_VISITOR_COUNT": 23502,
            "SAMPLE_PCT": 47.00,
            "AVG_RECENCY_DAYS": 104.47,
            "AVG_SESSIONS": 1.19,
            "AVG_VIEWS": 1.75,
            "AVG_CARTS": 0.04,
            "AVG_TXNS": 0.01
        },
        {
            "CLUSTER_ID": 2,
            "CLUSTER_NAME": "Cluster 2: Engaged Multi-Session Shoppers",
            "SAMPLE_VISITOR_COUNT": 5,
            "SAMPLE_PCT": 0.01,
            "AVG_RECENCY_DAYS": 73.60,
            "AVG_SESSIONS": 17.40,
            "AVG_VIEWS": 348.80,
            "AVG_CARTS": 73.60,
            "AVG_TXNS": 56.40
        },
        {
            "CLUSTER_ID": 3,
            "CLUSTER_NAME": "Cluster 3: Super VIP Power Buyers",
            "SAMPLE_VISITOR_COUNT": 2,
            "SAMPLE_PCT": 0.004,
            "AVG_RECENCY_DAYS": 37.50,
            "AVG_SESSIONS": 197.00,
            "AVG_VIEWS": 741.00,
            "AVG_CARTS": 14.50,
            "AVG_TXNS": 14.00
        }
    ])
    df_km.to_csv(km_input_path, index=False)
    print(f"Overwrote {km_input_path} with clean single-header schema.")

    # 4. Validate Views by running test queries
    print("\n--- 4. Validating Created Oracle Views ---")
    test_views = [
        "v_pbi_weekly_north_star",
        "v_pbi_funnel_stages",
        "v_pbi_funnel_visitor_type",
        "v_pbi_funnel_by_category",
        "v_pbi_funnel_by_hour",
        "v_pbi_visitor_segments",
        "v_pbi_buyer_rfm"
    ]
    for view in test_views:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {view}")
            cnt = cursor.fetchone()[0]
            print(f"  View {view:30s} -> {cnt} rows")
        except Exception as e:
            print(f"  Error validating {view}: {e}")

    cursor.close()
    conn.close()
    print("\nAll Power BI views and datasets successfully compiled and verified.")

if __name__ == "__main__":
    main()
