-- ============================================================
-- 10_cohort_retention.sql
-- Weekly Cohort Activity & Purchase Retention Matrices
-- Schema: growth_user @ XEPDB1
-- ============================================================

SET DEFINE OFF;
SET PAGESIZE 100 LINESIZE 160;
SET TIMING ON;
SET FEEDBACK ON;

-- 1. Weekly Visitor Activity Retention
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
    va.cohort_week,
    cs.cohort_size,
    va.week_number,
    COUNT(DISTINCT va.visitorid) AS active_visitors,
    ROUND(COUNT(DISTINCT va.visitorid) * 100.0 / cs.cohort_size, 2) AS retention_rate_pct
FROM visitor_activity va
JOIN cohort_sizes cs ON va.cohort_week = cs.cohort_week
GROUP BY va.cohort_week, cs.cohort_size, va.week_number
ORDER BY va.cohort_week, va.week_number;

-- 2. Buyer Repeat Purchase Retention (By First Purchase Week)
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
    bst.first_purchase_week,
    cb.buyer_cohort_size,
    bst.week_number,
    COUNT(DISTINCT bst.visitorid) AS purchasing_visitors,
    ROUND(COUNT(DISTINCT bst.visitorid) * 100.0 / cb.buyer_cohort_size, 2) AS buyer_retention_pct
FROM buyer_subsequent_txns bst
JOIN cohort_buyers cb ON bst.first_purchase_week = cb.buyer_cohort_week
GROUP BY bst.first_purchase_week, cb.buyer_cohort_size, bst.week_number
ORDER BY bst.first_purchase_week, bst.week_number;
