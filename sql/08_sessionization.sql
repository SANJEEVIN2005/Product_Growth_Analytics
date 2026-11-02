-- ============================================================
-- 08_sessionization.sql
-- 30-Minute Inactivity Sessionization & Fact Construction
-- Schema: growth_user @ XEPDB1
-- ============================================================

SET DEFINE OFF;
SET PAGESIZE 100 LINESIZE 160;
SET TIMING ON;
SET FEEDBACK ON;

-- Materialize fact_events_sessionized with inactivity boundary flags

BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE fact_events_sessionized PURGE';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

CREATE TABLE fact_events_sessionized AS
WITH event_lags AS (
    SELECT 
        e.event_id,
        e.raw_timestamp,
        e.event_time,
        e.event_date,
        TO_NUMBER(TO_CHAR(e.event_time, 'HH24')) AS event_hour,
        TO_CHAR(e.event_date, 'DY') AS event_dow,
        e.visitorid,
        e.event_type,
        e.itemid,
        e.transactionid,
        di.top_category_id,
        LAG(e.raw_timestamp) OVER (
            PARTITION BY e.visitorid 
            ORDER BY e.raw_timestamp, e.event_id
        ) AS prev_timestamp
    FROM v_clean_events e
    LEFT JOIN dim_items di ON e.itemid = di.itemid
),
session_flags AS (
    SELECT 
        el.*,
        CASE 
            WHEN el.prev_timestamp IS NULL 
              OR (el.raw_timestamp - el.prev_timestamp) > 1800000 
            THEN 1 
            ELSE 0 
        END AS is_new_session
    FROM event_lags el
),
session_assigned AS (
    SELECT 
        sf.event_id,
        sf.raw_timestamp,
        sf.event_time,
        sf.event_date,
        sf.event_hour,
        sf.event_dow,
        sf.visitorid,
        sf.event_type,
        sf.itemid,
        sf.transactionid,
        sf.top_category_id,
        SUM(sf.is_new_session) OVER (
            PARTITION BY sf.visitorid 
            ORDER BY sf.raw_timestamp, sf.event_id
        ) AS session_seq
    FROM session_flags sf
)
SELECT 
    sa.*,
    sa.visitorid || '_' || sa.session_seq AS session_id,
    CASE WHEN sa.session_seq > 1 THEN 1 ELSE 0 END AS is_returning_session
FROM session_assigned sa;

-- Index sessionized events
CREATE INDEX idx_fes_session ON fact_events_sessionized (session_id);
CREATE INDEX idx_fes_visitor ON fact_events_sessionized (visitorid);
CREATE INDEX idx_fes_type ON fact_events_sessionized (event_type);
CREATE INDEX idx_fes_date ON fact_events_sessionized (event_date);
CREATE INDEX idx_fes_hour ON fact_events_sessionized (event_hour);
CREATE INDEX idx_fes_topcat ON fact_events_sessionized (top_category_id);

-- Materialize fact_sessions summary

BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE fact_sessions PURGE';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

CREATE TABLE fact_sessions AS
SELECT 
    session_id,
    visitorid,
    session_seq,
    MAX(is_returning_session) AS is_returning,
    MIN(event_time) AS session_start_time,
    MAX(event_time) AS session_end_time,
    TRUNC(MIN(event_date)) AS session_date,
    TO_NUMBER(TO_CHAR(MIN(event_time), 'HH24')) AS session_hour,
    TO_CHAR(MIN(event_date), 'DY') AS session_dow,
    ROUND((MAX(raw_timestamp) - MIN(raw_timestamp)) / 1000, 2) AS duration_seconds,
    COUNT(*) AS total_events,
    COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS views_count,
    COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) AS carts_count,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS txns_count,
    COUNT(DISTINCT itemid) AS distinct_items,
    MAX(CASE WHEN event_type = 'view' THEN 1 ELSE 0 END) AS has_view,
    MAX(CASE WHEN event_type = 'addtocart' THEN 1 ELSE 0 END) AS has_cart,
    MAX(CASE WHEN event_type = 'transaction' THEN 1 ELSE 0 END) AS has_purchase
FROM fact_events_sessionized
GROUP BY session_id, visitorid, session_seq;

CREATE INDEX idx_fs_session ON fact_sessions (session_id);
CREATE INDEX idx_fs_visitor ON fact_sessions (visitorid);
CREATE INDEX idx_fs_date ON fact_sessions (session_date);
CREATE INDEX idx_fs_returning ON fact_sessions (is_returning);

-- Verification of Sessionization Metrics
SELECT 
    COUNT(*) AS total_sessions,
    COUNT(DISTINCT visitorid) AS distinct_visitors,
    ROUND(AVG(total_events), 2) AS avg_events_per_session,
    ROUND(AVG(duration_seconds), 2) AS avg_duration_sec,
    MEDIAN(duration_seconds) AS median_duration_sec,
    SUM(has_view) AS sessions_with_view,
    SUM(has_cart) AS sessions_with_cart,
    SUM(has_purchase) AS sessions_with_purchase
FROM fact_sessions;
