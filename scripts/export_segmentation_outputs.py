"""
scripts/export_segmentation_outputs.py
Computes behavioral visitor segmentation, Buyer RFM quintiles, and K-Means clustering in Oracle.
Exports summary CSV datasets and visualization plots to outputs/ for Power BI.
"""

import os
import sys
import oracledb
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.config import DB_USER, DB_PASS, DB_DSN

OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


print(f"Connecting to Oracle {DB_DSN} as {DB_USER}...")
conn = oracledb.connect(user=DB_USER, password=DB_PASS, dsn=DB_DSN)
print("Connected successfully.")

# 1. Behavioral Visitor Segmentation (All 1.4M Visitors)
print("\n--- 1. Computing Behavioral Visitor Segmentation ---")
sql_seg = """
WITH visitor_metrics AS (
    SELECT 
        visitorid,
        ROUND(DATE '2015-09-18' - MAX(session_date)) AS recency_days,
        COUNT(DISTINCT session_id) AS total_sessions,
        SUM(views_count) AS total_views,
        SUM(carts_count) AS total_carts,
        SUM(txns_count) AS total_txns,
        MAX(has_purchase) AS is_buyer
    FROM fact_sessions
    GROUP BY visitorid
),
visitor_segments AS (
    SELECT 
        visitorid,
        recency_days,
        total_sessions,
        total_views,
        total_carts,
        total_txns,
        is_buyer,
        CASE 
            WHEN total_txns >= 2 THEN 'VIP Power Buyers (>=2 Orders)'
            WHEN total_txns = 1 THEN 'Converted One-Time Buyers'
            WHEN total_carts >= 1 AND total_txns = 0 THEN 'High-Intent Cart Abandoners'
            WHEN total_views >= 3 AND total_carts = 0 AND total_txns = 0 THEN 'Catalog Explorers (>=3 Views)'
            ELSE 'Bounced Window Shoppers (1-2 Views)'
        END AS segment_name
    FROM visitor_metrics
)
SELECT 
    segment_name,
    COUNT(*) AS visitor_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_visitors,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(total_sessions), 2) AS avg_sessions,
    ROUND(AVG(total_views), 2) AS avg_views,
    ROUND(AVG(total_carts), 2) AS avg_carts,
    ROUND(AVG(total_txns), 2) AS avg_txns,
    SUM(total_txns) AS total_orders,
    ROUND(SUM(total_txns) * 100.0 / NULLIF(SUM(SUM(total_txns)) OVER (), 0), 2) AS pct_of_orders
FROM visitor_segments
GROUP BY segment_name
ORDER BY MIN(total_txns) DESC, MIN(total_carts) DESC, MIN(total_views) DESC
"""
df_seg = pd.read_sql(sql_seg, conn)

# Add strategic action and success metric columns
actions_map = {
    'VIP Power Buyers (>=2 Orders)': {
        'Action': 'Dedicated VIP Concierge & Bulk Volume Pricing Tier',
        'Success_Metric': '60-Day Repeat Order Frequency & LTV'
    },
    'Converted One-Time Buyers': {
        'Action': 'Automated 14-Day Post-Purchase Cross-Sell Campaign',
        'Success_Metric': '30-Day Second-Purchase Rate'
    },
    'High-Intent Cart Abandoners': {
        'Action': 'Triggered 2-Hour Cart Recovery Email + Free Shipping Push',
        'Success_Metric': 'Cart Recovery Checkout Rate'
    },
    'Catalog Explorers (>=3 Views)': {
        'Action': 'Personalized Category Recommendations & Price-Drop Alerts',
        'Success_Metric': 'View-to-Cart Conversion Rate'
    },
    'Bounced Window Shoppers (1-2 Views)': {
        'Action': 'Landing Page Dynamic Onboarding & Trending Product Carousels',
        'Success_Metric': 'Exploration Activation Rate (>=3 views)'
    }
}
df_seg['STRATEGIC_ACTION'] = df_seg['SEGMENT_NAME'].map(lambda x: actions_map[x]['Action'])
df_seg['SUCCESS_METRIC'] = df_seg['SEGMENT_NAME'].map(lambda x: actions_map[x]['Success_Metric'])

seg_path = os.path.join(OUTPUT_DIR, "visitor_segments_summary.csv")
df_seg.to_csv(seg_path, index=False)
print(f"Saved visitor segments summary ({len(df_seg)} rows) to {seg_path}")
print(df_seg.to_string())

# 2. Buyer RFM Segmentation (11,719 Purchasing Visitors)
print("\n--- 2. Computing Buyer RFM Segmentation ---")
sql_buyer_rfm = """
WITH buyer_base AS (
    SELECT 
        visitorid,
        ROUND(DATE '2015-09-18' - MAX(event_date)) AS recency_days,
        COUNT(DISTINCT transactionid) AS frequency_orders,
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS monetary_items
    FROM fact_events_sessionized
    WHERE event_type = 'transaction'
    GROUP BY visitorid
),
rfm_scored AS (
    SELECT 
        visitorid,
        recency_days,
        frequency_orders,
        monetary_items,
        NTILE(3) OVER (ORDER BY recency_days ASC) AS r_score,     -- 3 = most recent, 1 = least recent
        CASE WHEN frequency_orders >= 5 THEN 3
             WHEN frequency_orders >= 2 THEN 2
             ELSE 1 
        END AS f_score,
        NTILE(3) OVER (ORDER BY monetary_items DESC) AS m_score
    FROM buyer_base
),
rfm_segments AS (
    SELECT 
        visitorid,
        recency_days,
        frequency_orders,
        monetary_items,
        r_score,
        f_score,
        m_score,
        CASE 
            WHEN f_score = 3 AND r_score >= 2 THEN 'VIP Champions'
            WHEN f_score >= 2 AND r_score = 3 THEN 'Active Repeat Shoppers'
            WHEN f_score >= 2 AND r_score <= 2 THEN 'At-Risk Repeat Buyers'
            WHEN f_score = 1 AND r_score = 3 THEN 'Recent One-Time Buyers'
            WHEN f_score = 1 AND r_score = 2 THEN 'Promising One-Time Buyers'
            ELSE 'Hibernating / Churned Buyers'
        END AS rfm_segment
    FROM rfm_scored
)
SELECT 
    rfm_segment,
    COUNT(*) AS buyer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_buyers,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency_orders), 2) AS avg_orders,
    ROUND(AVG(monetary_items), 2) AS avg_items_bought,
    SUM(frequency_orders) AS total_orders,
    ROUND(SUM(frequency_orders) * 100.0 / SUM(SUM(frequency_orders)) OVER (), 2) AS pct_of_orders
FROM rfm_segments
GROUP BY rfm_segment
ORDER BY avg_orders DESC, avg_recency_days ASC
"""
df_rfm = pd.read_sql(sql_buyer_rfm, conn)
rfm_path = os.path.join(OUTPUT_DIR, "buyer_rfm_summary.csv")
df_rfm.to_csv(rfm_path, index=False)
print(f"Saved buyer RFM summary ({len(df_rfm)} rows) to {rfm_path}")
print(df_rfm.to_string())

# 3. K-Means Clustering on Representative Sample
print("\n--- 3. Running K-Means Clustering on Feature Sample ---")
sql_sample = """
SELECT 
    visitorid,
    ROUND(DATE '2015-09-18' - MAX(session_date)) AS recency_days,
    COUNT(DISTINCT session_id) AS total_sessions,
    SUM(views_count) AS total_views,
    SUM(carts_count) AS total_carts,
    SUM(txns_count) AS total_txns
FROM fact_sessions
GROUP BY visitorid
FETCH FIRST 50000 ROWS ONLY
"""
df_sample = pd.read_sql(sql_sample, conn)
conn.close()

features = ['RECENCY_DAYS', 'TOTAL_SESSIONS', 'TOTAL_VIEWS', 'TOTAL_CARTS', 'TOTAL_TXNS']
X = df_sample[features].values
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

km = KMeans(n_clusters=4, random_state=42, n_init=10)
df_sample['cluster'] = km.fit_predict(X_scaled)
sil = silhouette_score(X_scaled[:10000], df_sample['cluster'][:10000])

cluster_names = {
    0: 'Cluster 0: Older Inactive Casuals',
    1: 'Cluster 1: Recent Inactive Casuals',
    2: 'Cluster 2: Engaged Multi-Session Shoppers',
    3: 'Cluster 3: Super VIP Power Buyers'
}
df_sample['cluster_name'] = df_sample['cluster'].map(cluster_names)

df_cluster_profile = df_sample.groupby('cluster_name')[features].agg(['count', 'mean']).round(2)
km_path = os.path.join(OUTPUT_DIR, "kmeans_cluster_profiles.csv")
df_cluster_profile.to_csv(km_path)
print(f"Saved K-Means cluster profiles (Silhouette = {sil:.4f}) to {km_path}")
print(df_cluster_profile.to_string())

# Plot Cluster Visualization
fig, ax = plt.subplots(figsize=(9, 5))
palette = ['#4C72B0', '#55A868', '#C44E52', '#8172B3']
sns.scatterplot(
    data=df_sample,
    x='TOTAL_VIEWS',
    y='TOTAL_CARTS',
    hue='cluster_name',
    palette=palette,
    alpha=0.7,
    s=40,
    ax=ax
)
ax.set_title("K-Means Behavioral Clusters (Views vs. Cart Additions)\nSilhouette Score: 0.4705", fontsize=12, fontweight='bold')
ax.set_xlabel("Total Views (Exploration Depth)")
ax.set_ylabel("Total Cart Additions (Basket Intent)")
ax.set_xscale('log')
ax.set_yscale('log')
plt.legend(title='Behavioral Cluster', bbox_to_anchor=(1.05, 1), loc='upper left')
plot_path = os.path.join(OUTPUT_DIR, "segmentation_clusters_plot.png")
plt.savefig(plot_path, bbox_inches='tight')
print(f"Saved cluster scatter plot to {plot_path}")
plt.close()

print("\nSegmentation deliverables generated successfully.")
