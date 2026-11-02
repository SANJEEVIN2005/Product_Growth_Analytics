-- ============================================================
-- 05_data_quality_checks.sql
-- Comprehensive Data Quality and Telemetry Audit
-- Schema: growth_user @ XEPDB1
-- ============================================================

SET DEFINE OFF;
SET PAGESIZE 100 LINESIZE 160;
SET TIMING ON;
SET FEEDBACK ON;

-- 1. Date Range and Temporal Integrity
SELECT 
    MIN(event_time) AS min_event_time,
    MAX(event_time) AS max_event_time,
    ROUND(MAX(CAST(event_time AS DATE)) - MIN(CAST(event_time AS DATE)), 2) AS total_span_days,
    COUNT(*) AS total_events,
    COUNT(DISTINCT event_date) AS distinct_active_days
FROM events;

-- 2. Exact Duplicates Check
SELECT 
    COUNT(*) AS duplicate_instances,
    NVL(SUM(cnt - 1), 0) AS excess_duplicate_rows
FROM (
    SELECT raw_timestamp, visitorid, event_type, itemid, transactionid, COUNT(*) AS cnt
    FROM events
    GROUP BY raw_timestamp, visitorid, event_type, itemid, transactionid
    HAVING COUNT(*) > 1
);

-- 3. Null Value Audit Across Columns
SELECT
    COUNT(*) - COUNT(event_id)      AS null_event_id,
    COUNT(*) - COUNT(raw_timestamp) AS null_raw_timestamp,
    COUNT(*) - COUNT(event_time)    AS null_event_time,
    COUNT(*) - COUNT(event_date)    AS null_event_date,
    COUNT(*) - COUNT(visitorid)     AS null_visitorid,
    COUNT(*) - COUNT(event_type)    AS null_event_type,
    COUNT(*) - COUNT(itemid)        AS null_itemid,
    COUNT(CASE WHEN event_type = 'transaction' AND transactionid IS NULL THEN 1 END) AS null_txnid_on_purchase,
    COUNT(CASE WHEN event_type != 'transaction' AND transactionid IS NOT NULL THEN 1 END) AS non_null_txnid_on_non_purchase
FROM events;

-- 4. Transaction Integrity and Basket Size Distribution
SELECT 
    items_in_txn,
    COUNT(*) AS transaction_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_txns
FROM (
    SELECT transactionid, COUNT(*) AS items_in_txn
    FROM events
    WHERE event_type = 'transaction'
    GROUP BY transactionid
)
GROUP BY items_in_txn
ORDER BY items_in_txn;

-- 5. Purchases Without Preceding Views (Direct Checkouts)
WITH item_purchases AS (
    SELECT e.visitorid, e.itemid, e.event_time AS txn_time
    FROM events e
    WHERE e.event_type = 'transaction'
),
prior_views AS (
    SELECT p.visitorid, p.itemid, p.txn_time,
           COUNT(v.event_id) AS view_count_prior
    FROM item_purchases p
    LEFT JOIN events v
      ON p.visitorid = v.visitorid
     AND p.itemid = v.itemid
     AND v.event_type = 'view'
     AND v.event_time <= p.txn_time
    GROUP BY p.visitorid, p.itemid, p.txn_time
)
SELECT 
    COUNT(*) AS total_item_purchases,
    SUM(CASE WHEN view_count_prior > 0 THEN 1 ELSE 0 END) AS with_prior_item_view,
    SUM(CASE WHEN view_count_prior = 0 THEN 1 ELSE 0 END) AS without_prior_item_view,
    ROUND(SUM(CASE WHEN view_count_prior = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS pct_without_prior_view
FROM prior_views;

-- 6. Visitor Activity Distribution and Percentiles
WITH visitor_counts AS (
    SELECT visitorid, COUNT(*) AS total_events
    FROM events
    GROUP BY visitorid
)
SELECT 
    COUNT(*) AS total_visitors,
    ROUND(AVG(total_events), 2) AS mean_events,
    MEDIAN(total_events) AS median_p50,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total_events) AS p75,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY total_events) AS p90,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_events) AS p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY total_events) AS p99,
    PERCENTILE_CONT(0.999) WITHIN GROUP (ORDER BY total_events) AS p99_9,
    MAX(total_events) AS max_events
FROM visitor_counts;

-- 7. Top 20 Extreme Activity Visitors (Bot Profiling)
WITH top_visitors AS (
    SELECT * FROM (
        SELECT visitorid, COUNT(*) AS total_events
        FROM events
        GROUP BY visitorid
        ORDER BY total_events DESC
    )
    WHERE ROWNUM <= 20
)
SELECT 
    e.visitorid,
    COUNT(*) AS total_events,
    COUNT(CASE WHEN e.event_type = 'view' THEN 1 END) AS views,
    COUNT(CASE WHEN e.event_type = 'addtocart' THEN 1 END) AS carts,
    COUNT(CASE WHEN e.event_type = 'transaction' THEN 1 END) AS txns,
    COUNT(DISTINCT e.itemid) AS distinct_items,
    COUNT(DISTINCT e.event_date) AS active_days,
    ROUND((MAX(e.raw_timestamp) - MIN(e.raw_timestamp)) / 1000 / 3600, 1) AS active_hours_span,
    ROUND(COUNT(*) / NULLIF((MAX(e.raw_timestamp) - MIN(e.raw_timestamp)) / 1000 / 60, 0), 2) AS events_per_minute
FROM events e
JOIN top_visitors tv ON e.visitorid = tv.visitorid
GROUP BY e.visitorid
ORDER BY total_events DESC;

-- 8. Bot Cutoff Candidate Thresholds Impact
WITH visitor_summary AS (
    SELECT 
        visitorid,
        COUNT(*) AS total_events,
        COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS txn_count
    FROM events
    GROUP BY visitorid
)
SELECT 
    '> 500 events' AS threshold,
    COUNT(CASE WHEN total_events > 500 THEN 1 END) AS visitors_flagged,
    SUM(CASE WHEN total_events > 500 THEN total_events ELSE 0 END) AS events_flagged,
    ROUND(SUM(CASE WHEN total_events > 500 THEN total_events ELSE 0 END) * 100.0 / 2756101, 3) AS pct_events_flagged,
    SUM(CASE WHEN total_events > 500 THEN txn_count ELSE 0 END) AS transactions_lost
FROM visitor_summary
UNION ALL
SELECT 
    '> 300 events' AS threshold,
    COUNT(CASE WHEN total_events > 300 THEN 1 END) AS visitors_flagged,
    SUM(CASE WHEN total_events > 300 THEN total_events ELSE 0 END) AS events_flagged,
    ROUND(SUM(CASE WHEN total_events > 300 THEN total_events ELSE 0 END) * 100.0 / 2756101, 3) AS pct_events_flagged,
    SUM(CASE WHEN total_events > 300 THEN txn_count ELSE 0 END) AS transactions_lost
FROM visitor_summary
UNION ALL
SELECT 
    '> 200 events' AS threshold,
    COUNT(CASE WHEN total_events > 200 THEN 1 END) AS visitors_flagged,
    SUM(CASE WHEN total_events > 200 THEN total_events ELSE 0 END) AS events_flagged,
    ROUND(SUM(CASE WHEN total_events > 200 THEN total_events ELSE 0 END) * 100.0 / 2756101, 3) AS pct_events_flagged,
    SUM(CASE WHEN total_events > 200 THEN txn_count ELSE 0 END) AS transactions_lost
FROM visitor_summary
UNION ALL
SELECT 
    '> 100 events' AS threshold,
    COUNT(CASE WHEN total_events > 100 THEN 1 END) AS visitors_flagged,
    SUM(CASE WHEN total_events > 100 THEN total_events ELSE 0 END) AS events_flagged,
    ROUND(SUM(CASE WHEN total_events > 100 THEN total_events ELSE 0 END) * 100.0 / 2756101, 3) AS pct_events_flagged,
    SUM(CASE WHEN total_events > 100 THEN txn_count ELSE 0 END) AS transactions_lost
FROM visitor_summary
UNION ALL
SELECT 
    '> 50 events (p99.9)' AS threshold,
    COUNT(CASE WHEN total_events > 50 THEN 1 END) AS visitors_flagged,
    SUM(CASE WHEN total_events > 50 THEN total_events ELSE 0 END) AS events_flagged,
    ROUND(SUM(CASE WHEN total_events > 50 THEN total_events ELSE 0 END) * 100.0 / 2756101, 3) AS pct_events_flagged,
    SUM(CASE WHEN total_events > 50 THEN txn_count ELSE 0 END) AS transactions_lost
FROM visitor_summary;
