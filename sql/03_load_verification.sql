-- ============================================================
-- 03_load_verification.sql
-- Run as growth_user in XEPDB1 to verify staging table loads
-- ============================================================

SET PAGESIZE 50 LINESIZE 120;

-- 1. Checking Category Tree Row Count (Expected: 1,669)
SELECT COUNT(*) AS total_categories,
       COUNT(parentid) AS with_parent,
       COUNT(*) - COUNT(parentid) AS root_categories
FROM stg_category_tree;

-- 2. Checking Staging Events Total Count (Expected: 2,756,101)
SELECT COUNT(*) AS total_stg_events FROM stg_events;

-- 3. Checking Events Breakdown by Event Type
-- Expected: view = 2,664,312 | addtocart = 69,332 | transaction = 22,457
SELECT event, 
       COUNT(*) AS event_count,
       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
FROM stg_events
GROUP BY event
ORDER BY event_count DESC;

-- 4. Checking Transaction ID Integrity
-- Expected: Exactly 22,457 non-null transaction IDs, 0 on views/carts
SELECT event,
       COUNT(transactionid) AS non_null_txns,
       COUNT(*) - COUNT(transactionid) AS null_txns,
       COUNT(DISTINCT transactionid) AS distinct_txns
FROM stg_events
GROUP BY event
ORDER BY non_null_txns DESC;
