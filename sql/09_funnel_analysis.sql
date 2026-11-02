-- ============================================================
-- 09_funnel_analysis.sql
-- Full-Funnel Analysis (Overall, New vs Returning, Category, Hour)
-- Schema: growth_user @ XEPDB1
-- ============================================================

SET DEFINE OFF;
SET PAGESIZE 100 LINESIZE 160;
SET TIMING ON;
SET FEEDBACK ON;

-- 1. Overall Visitor-Level & Session-Level Funnels

-- Visitor Level Funnel
SELECT 
    'Visitor Level' AS funnel_level,
    COUNT(*) AS top_stage_users,
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
);

-- Session Level Funnel
SELECT 
    'Session Level' AS funnel_level,
    COUNT(*) AS total_sessions,
    SUM(has_view) AS view_sessions,
    SUM(has_cart) AS cart_sessions,
    SUM(has_purchase) AS purchase_sessions,
    ROUND(SUM(has_cart) * 100.0 / NULLIF(SUM(has_view), 0), 2) AS view_to_cart_pct,
    ROUND((1 - SUM(has_cart) / NULLIF(SUM(has_view), 0)) * 100.0, 2) AS view_to_cart_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_cart), 0), 2) AS cart_to_purchase_pct,
    ROUND((1 - SUM(has_purchase) / NULLIF(SUM(has_cart), 0)) * 100.0, 2) AS cart_to_purchase_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_view), 0), 3) AS overall_session_cvr_pct
FROM fact_sessions;

-- 2. Funnel Segmentation: New vs Returning Sessions
SELECT 
    CASE WHEN is_returning = 0 THEN 'New Visitor Session (Seq 1)' 
         ELSE 'Returning Visitor Session (Seq 2+)' 
    END AS session_type,
    COUNT(*) AS total_sessions,
    SUM(has_view) AS view_sessions,
    SUM(has_cart) AS cart_sessions,
    SUM(has_purchase) AS purchase_sessions,
    ROUND(SUM(has_cart) * 100.0 / NULLIF(SUM(has_view), 0), 2) AS view_to_cart_cvr_pct,
    ROUND((1 - SUM(has_cart) / NULLIF(SUM(has_view), 0)) * 100.0, 2) AS view_to_cart_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_cart), 0), 2) AS cart_to_purchase_cvr_pct,
    ROUND((1 - SUM(has_purchase) / NULLIF(SUM(has_cart), 0)) * 100.0, 2) AS cart_to_purchase_dropoff_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_view), 0), 3) AS overall_cvr_pct
FROM fact_sessions
GROUP BY is_returning
ORDER BY is_returning;

-- 3. Funnel Segmentation: Top-Level Product Categories
SELECT 
    NVL(TO_CHAR(top_category_id), 'Unclassified/Other') AS top_category,
    COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS views,
    COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) AS carts,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS purchases,
    COUNT(DISTINCT visitorid) AS active_visitors,
    COUNT(DISTINCT CASE WHEN event_type = 'transaction' THEN visitorid END) AS purchasing_visitors,
    ROUND(
        COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 
        2
    ) AS view_to_cart_pct,
    ROUND(
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END), 0), 
        2
    ) AS cart_to_purchase_pct,
    ROUND(
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 
        3
    ) AS view_to_purchase_pct
FROM fact_events_sessionized
GROUP BY top_category_id
ORDER BY views DESC;

-- 4. Funnel Segmentation: Hour of Day (0-23 UTC)
SELECT 
    event_hour,
    COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS views,
    COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) AS carts,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS purchases,
    ROUND(
        COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 
        2
    ) AS view_to_cart_pct,
    ROUND(
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END), 0), 
        2
    ) AS cart_to_purchase_pct,
    ROUND(
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(CASE WHEN event_type = 'view' THEN 1 END), 0), 
        3
    ) AS view_to_purchase_pct
FROM fact_events_sessionized
GROUP BY event_hour
ORDER BY event_hour;
