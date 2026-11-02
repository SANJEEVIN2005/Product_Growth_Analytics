-- ====================================================================
-- Script: 12_powerbi_views.sql
-- Description: Curated Database Views for Power BI Reporting
-- Schema: GROWTH_USER
-- Connection: localhost:1521/XEPDB1
-- ====================================================================

-- 1. Page 1: Weekly North Star & Growth Trajectory View
CREATE OR REPLACE VIEW v_pbi_weekly_north_star AS
WITH weekly_metrics AS (
    SELECT 
        TRUNC(event_date, 'IW') AS week_start,
        COUNT(DISTINCT visitorid) AS weekly_active_visitors,
        COUNT(DISTINCT CASE WHEN event_type = 'transaction' THEN visitorid END) AS weekly_purchasing_visitors,
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS weekly_transaction_events,
        COUNT(DISTINCT transactionid) AS weekly_unique_orders
    FROM fact_events_sessionized
    GROUP BY TRUNC(event_date, 'IW')
)
SELECT 
    TO_CHAR(week_start, 'YYYY-MM-DD') AS week_start,
    weekly_active_visitors,
    weekly_purchasing_visitors,
    weekly_transaction_events,
    weekly_unique_orders,
    ROUND((weekly_purchasing_visitors / NULLIF(weekly_active_visitors, 0)) * 100, 3) AS weekly_buyer_conversion_rate
FROM weekly_metrics
ORDER BY week_start;

-- 2. Page 2: Funnel Stages Summary View
CREATE OR REPLACE VIEW v_pbi_funnel_stages AS
SELECT 1 AS stage_order, '1. Product Views' AS stage_name, 1404116 AS visitor_count, 1750668 AS session_count, 100.00 AS visitor_retention_pct, 0.00 AS visitor_dropoff_pct FROM DUAL
UNION ALL
SELECT 2 AS stage_order, '2. Cart Additions' AS stage_name, 37696 AS visitor_count, 43846 AS session_count, 2.68 AS visitor_retention_pct, 97.32 AS visitor_dropoff_pct FROM DUAL
UNION ALL
SELECT 3 AS stage_order, '3. Purchases' AS stage_name, 11719 AS visitor_count, 14297 AS session_count, 0.835 AS visitor_retention_pct, 68.91 AS visitor_dropoff_pct FROM DUAL;

-- 3. Page 2: Funnel by Visitor Session Type (New vs Returning)
CREATE OR REPLACE VIEW v_pbi_funnel_visitor_type AS
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
GROUP BY is_returning;

-- 4. Page 2: Funnel by Product Category (Top 25 Root Categories)
CREATE OR REPLACE VIEW v_pbi_funnel_by_category AS
SELECT 
    NVL(TO_CHAR(top_category_id), 'Unclassified') AS top_category_id,
    COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS views,
    COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) AS carts,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS purchases,
    COUNT(DISTINCT visitorid) AS distinct_visitors,
    COUNT(DISTINCT CASE WHEN event_type = 'transaction' THEN visitorid END) AS purchasing_visitors,
    ROUND(COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 2) AS view_to_cart_cvr_pct,
    ROUND(COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END), 0), 2) AS cart_to_purchase_cvr_pct,
    ROUND(COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 3) AS overall_view_to_purchase_cvr_pct
FROM fact_events_sessionized
GROUP BY top_category_id;

-- 5. Page 2: Funnel by Hour of Day
CREATE OR REPLACE VIEW v_pbi_funnel_by_hour AS
SELECT 
    EXTRACT(HOUR FROM event_time) AS event_hour,
    COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS views,
    COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) AS carts,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS purchases,
    ROUND(COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 2) AS view_to_cart_cvr_pct,
    ROUND(COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END), 0), 2) AS cart_to_purchase_cvr_pct,
    ROUND(COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 3) AS overall_cvr_pct
FROM fact_events_sessionized
GROUP BY EXTRACT(HOUR FROM event_time);

-- 6. Page 4: Visitor Behavioral Segments View
CREATE OR REPLACE VIEW v_pbi_visitor_segments AS
WITH visitor_agg AS (
    SELECT 
        visitorid,
        ROUND(DATE '2015-09-18' - MAX(session_date)) AS recency_days,
        COUNT(DISTINCT session_id) AS total_sessions,
        SUM(views_count) AS total_views,
        SUM(carts_count) AS total_carts,
        SUM(txns_count) AS total_txns
    FROM fact_sessions
    GROUP BY visitorid
),
segmented AS (
    SELECT 
        visitorid,
        recency_days,
        total_sessions,
        total_views,
        total_carts,
        total_txns,
        CASE 
            WHEN total_txns >= 2 THEN 'VIP Power Buyers (>=2 Orders)'
            WHEN total_txns = 1 THEN 'Converted One-Time Buyers'
            WHEN total_txns = 0 AND total_carts >= 1 THEN 'High-Intent Cart Abandoners'
            WHEN total_txns = 0 AND total_carts = 0 AND total_views >= 3 THEN 'Catalog Explorers (>=3 Views)'
            ELSE 'Bounced Window Shoppers (1-2 Views)'
        END AS segment_name
    FROM visitor_agg
)
SELECT 
    segment_name,
    COUNT(*) AS visitor_count,
    ROUND(COUNT(*) * 100.0 / 1407517, 2) AS pct_of_visitors,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(total_sessions), 2) AS avg_sessions,
    ROUND(AVG(total_views), 2) AS avg_views,
    ROUND(AVG(total_carts), 2) AS avg_carts,
    ROUND(AVG(total_txns), 2) AS avg_txns,
    SUM(total_txns) AS total_orders,
    ROUND(SUM(total_txns) * 100.0 / 22457, 2) AS pct_of_orders
FROM segmented
GROUP BY segment_name;

-- 7. Page 4: Buyer RFM Tiers View
CREATE OR REPLACE VIEW v_pbi_buyer_rfm AS
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
        CASE 
            WHEN f_score = 3 THEN 'VIP Champions'
            WHEN f_score = 2 AND r_score <= 2 THEN 'At-Risk Repeat Buyers'
            WHEN f_score = 2 AND r_score = 3 THEN 'Active Repeat Shoppers'
            WHEN f_score = 1 AND r_score = 1 THEN 'Hibernating / Churned Buyers'
            WHEN f_score = 1 AND r_score = 2 THEN 'Promising One-Time Buyers'
            ELSE 'Recent One-Time Buyers'
        END AS rfm_segment
    FROM rfm_scored
)
SELECT 
    rfm_segment,
    COUNT(*) AS buyer_count,
    ROUND(COUNT(*) * 100.0 / 11719, 2) AS pct_of_buyers,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency_orders), 2) AS avg_orders,
    ROUND(AVG(monetary_items), 2) AS avg_items_bought,
    SUM(frequency_orders) AS total_orders,
    ROUND(SUM(frequency_orders) * 100.0 / 17672, 2) AS pct_of_orders
FROM rfm_segments
GROUP BY rfm_segment;
