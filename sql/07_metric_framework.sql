-- ============================================================
-- 07_metric_framework.sql
-- Growth Metric Framework & Baseline Computation
-- Schema: growth_user @ XEPDB1
-- ============================================================

SET DEFINE OFF;
SET PAGESIZE 100 LINESIZE 160;
SET TIMING ON;
SET FEEDBACK ON;

-- 1. North Star Metric: Weekly Purchasing Visitors (WPV)
SELECT 
    TRUNC(event_date, 'IW') AS week_start,
    COUNT(DISTINCT visitorid) AS weekly_active_visitors,
    COUNT(DISTINCT CASE WHEN event_type = 'transaction' THEN visitorid END) AS weekly_purchasing_visitors,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS weekly_transaction_events,
    COUNT(DISTINCT transactionid) AS weekly_unique_orders,
    ROUND(
        COUNT(DISTINCT CASE WHEN event_type = 'transaction' THEN visitorid END) * 100.0 / 
        NULLIF(COUNT(DISTINCT visitorid), 0), 
        3
    ) AS weekly_buyer_conversion_rate
FROM v_clean_events
GROUP BY TRUNC(event_date, 'IW')
ORDER BY week_start;

-- 2. Supporting Metric: Overall Conversion Rates
WITH visitor_milestones AS (
    SELECT 
        visitorid,
        MAX(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS has_view,
        MAX(CASE WHEN event_type = 'addtocart' THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN event_type = 'transaction' THEN 1 ELSE 0 END) AS has_purchase
    FROM v_clean_events
    GROUP BY visitorid
)
SELECT 
    COUNT(*) AS total_visitors,
    SUM(has_view) AS viewing_visitors,
    SUM(has_cart) AS carting_visitors,
    SUM(has_purchase) AS purchasing_visitors,
    ROUND(SUM(has_cart) * 100.0 / NULLIF(SUM(has_view), 0), 2) AS view_to_cart_cvr_pct,
    ROUND(SUM(has_purchase) * 100.0 / NULLIF(SUM(has_cart), 0), 2) AS cart_to_purchase_cvr_pct,
    ROUND(SUM(has_purchase) * 100.0 / COUNT(*), 3) AS visitor_to_purchase_cvr_pct
FROM visitor_milestones;

-- 3. Supporting Metric: Repeat Purchase Rate
WITH buyer_orders AS (
    SELECT 
        visitorid,
        COUNT(DISTINCT transactionid) AS order_count
    FROM v_clean_events
    WHERE event_type = 'transaction'
    GROUP BY visitorid
)
SELECT 
    COUNT(*) AS total_buyers,
    SUM(CASE WHEN order_count = 1 THEN 1 ELSE 0 END) AS single_order_buyers,
    SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_buyers,
    ROUND(SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS repeat_purchase_rate_pct,
    ROUND(AVG(order_count), 2) AS avg_orders_per_buyer,
    MAX(order_count) AS max_orders_by_single_buyer
FROM buyer_orders;

-- 4. Buyer Order Frequency Distribution
WITH buyer_orders AS (
    SELECT 
        visitorid,
        COUNT(DISTINCT transactionid) AS order_count
    FROM v_clean_events
    WHERE event_type = 'transaction'
    GROUP BY visitorid
)
SELECT 
    CASE 
        WHEN order_count = 1 THEN '1 Order (One-Time)'
        WHEN order_count = 2 THEN '2 Orders'
        WHEN order_count = 3 THEN '3 Orders'
        WHEN order_count = 4 THEN '4 Orders'
        WHEN order_count BETWEEN 5 AND 9 THEN '5-9 Orders'
        ELSE '10+ Orders (Power Buyers)'
    END AS order_bucket,
    COUNT(*) AS buyer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_buyers,
    SUM(order_count) AS total_orders,
    ROUND(SUM(order_count) * 100.0 / SUM(SUM(order_count)) OVER (), 2) AS pct_of_orders
FROM buyer_orders
GROUP BY 
    CASE 
        WHEN order_count = 1 THEN '1 Order (One-Time)'
        WHEN order_count = 2 THEN '2 Orders'
        WHEN order_count = 3 THEN '3 Orders'
        WHEN order_count = 4 THEN '4 Orders'
        WHEN order_count BETWEEN 5 AND 9 THEN '5-9 Orders'
        ELSE '10+ Orders (Power Buyers)'
    END
ORDER BY MIN(order_count);

-- 5. Time to First Purchase (Hours from First Event to First Txn)
WITH visitor_journey AS (
    SELECT 
        visitorid,
        MIN(event_time) AS first_event_time,
        MIN(CASE WHEN event_type = 'transaction' THEN event_time END) AS first_txn_time
    FROM v_clean_events
    GROUP BY visitorid
    HAVING COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) > 0
),
journey_diffs AS (
    SELECT 
        visitorid,
        ROUND((CAST(first_txn_time AS DATE) - CAST(first_event_time AS DATE)) * 24, 2) AS hours_to_first_txn,
        ROUND(CAST(first_txn_time AS DATE) - CAST(first_event_time AS DATE), 2) AS days_to_first_txn
    FROM visitor_journey
)
SELECT 
    COUNT(*) AS total_buyers,
    ROUND(AVG(hours_to_first_txn), 2) AS mean_hours_to_txn,
    MEDIAN(hours_to_first_txn) AS median_hours_to_txn,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY hours_to_first_txn) AS p25_hours,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY hours_to_first_txn) AS p75_hours,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY hours_to_first_txn) AS p90_hours,
    ROUND(SUM(CASE WHEN hours_to_first_txn < 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_purchased_within_1_hour,
    ROUND(SUM(CASE WHEN days_to_first_txn < 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_purchased_same_day
FROM journey_diffs;

-- 6. Activation Definition Validation
WITH visitor_behavior AS (
    SELECT 
        visitorid,
        COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS view_count,
        COUNT(DISTINCT itemid) AS distinct_items_viewed,
        MAX(CASE WHEN event_type = 'addtocart' THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN event_type = 'transaction' THEN 1 ELSE 0 END) AS has_purchased
    FROM v_clean_events
    GROUP BY visitorid
)
SELECT 
    'All Visitors' AS cohort,
    COUNT(*) AS total_visitors,
    SUM(has_purchased) AS buyers,
    ROUND(SUM(has_purchased) * 100.0 / COUNT(*), 3) AS cvr_pct
FROM visitor_behavior
UNION ALL
SELECT 
    'Bounced (1 view only)' AS cohort,
    COUNT(*) AS total_visitors,
    SUM(has_purchased) AS buyers,
    ROUND(SUM(has_purchased) * 100.0 / COUNT(*), 3) AS cvr_pct
FROM visitor_behavior
WHERE view_count = 1 AND has_cart = 0
UNION ALL
SELECT 
    'Activated: Explored >= 3 Distinct Items' AS cohort,
    COUNT(*) AS total_visitors,
    SUM(has_purchased) AS buyers,
    ROUND(SUM(has_purchased) * 100.0 / COUNT(*), 3) AS cvr_pct
FROM visitor_behavior
WHERE distinct_items_viewed >= 3
UNION ALL
SELECT 
    'Activated: Added Item to Cart (>= 1 Cart)' AS cohort,
    COUNT(*) AS total_visitors,
    SUM(has_purchased) AS buyers,
    ROUND(SUM(has_purchased) * 100.0 / COUNT(*), 3) AS cvr_pct
FROM visitor_behavior
WHERE has_cart = 1;

-- 7. Guardrail Metric: Cart Abandonment Rate
WITH cart_users AS (
    SELECT 
        visitorid,
        MAX(CASE WHEN event_type = 'addtocart' THEN 1 ELSE 0 END) AS added_to_cart,
        MAX(CASE WHEN event_type = 'transaction' THEN 1 ELSE 0 END) AS purchased
    FROM v_clean_events
    GROUP BY visitorid
    HAVING MAX(CASE WHEN event_type = 'addtocart' THEN 1 ELSE 0 END) = 1
)
SELECT 
    COUNT(*) AS total_cart_visitors,
    SUM(purchased) AS purchasing_cart_visitors,
    COUNT(*) - SUM(purchased) AS abandoned_cart_visitors,
    ROUND((COUNT(*) - SUM(purchased)) * 100.0 / COUNT(*), 2) AS visitor_cart_abandonment_rate_pct
FROM cart_users;
