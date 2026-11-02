-- ============================================================
-- 11_visitor_segmentation.sql
-- Behavioral Visitor Segmentation and Buyer RFM
-- Schema: growth_user @ XEPDB1
-- ============================================================

SET DEFINE OFF;
SET PAGESIZE 100 LINESIZE 160;
SET TIMING ON;
SET FEEDBACK ON;

-- 1. Behavioral Visitor Segmentation (All 1.4M Visitors)
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
ORDER BY MIN(total_txns) DESC, MIN(total_carts) DESC, MIN(total_views) DESC;

-- 2. Buyer RFM Segmentation (11,719 Purchasing Visitors)
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
        NTILE(3) OVER (ORDER BY recency_days ASC) AS r_score,
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
ORDER BY total_orders DESC;
