-- ============================================================
-- 06_flag_bots_and_duplicates.sql
-- Flag bots and duplicates on events table
-- Schema: growth_user @ XEPDB1
-- ============================================================

SET DEFINE OFF;
SET TIMING ON;
SET FEEDBACK ON;

-- Add is_bot and is_duplicate columns to events
ALTER TABLE events ADD (
    is_bot       NUMBER(1) DEFAULT 0 NOT NULL,
    is_duplicate NUMBER(1) DEFAULT 0 NOT NULL
);

-- Flag 460 excess duplicate events
MERGE INTO events e
USING (
    SELECT event_id
    FROM (
        SELECT event_id,
               ROW_NUMBER() OVER (
                   PARTITION BY raw_timestamp, visitorid, event_type, itemid, transactionid 
                   ORDER BY event_id
               ) AS rn
        FROM events
    )
    WHERE rn > 1
) dup
ON (e.event_id = dup.event_id)
WHEN MATCHED THEN
  UPDATE SET e.is_duplicate = 1;

COMMIT;

-- Flag 63 pure non-buyer bot/scraper visitors
MERGE INTO events e
USING (
    SELECT visitorid
    FROM events
    WHERE is_duplicate = 0
    GROUP BY visitorid
    HAVING COUNT(*) > 200 
       AND COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) = 0
) bot
ON (e.visitorid = bot.visitorid)
WHEN MATCHED THEN
  UPDATE SET e.is_bot = 1;

COMMIT;

-- Index flags and create v_clean_events view
CREATE INDEX idx_events_flags ON events (is_bot, is_duplicate);

CREATE OR REPLACE VIEW v_clean_events AS
SELECT 
    event_id,
    raw_timestamp,
    event_time,
    event_date,
    visitorid,
    event_type,
    itemid,
    transactionid
FROM events
WHERE is_bot = 0 
  AND is_duplicate = 0;

-- Verification of Curated Clean Dataset
SELECT 
    COUNT(*) AS total_clean_events,
    COUNT(DISTINCT visitorid) AS clean_visitors,
    COUNT(DISTINCT itemid) AS clean_items,
    COUNT(DISTINCT transactionid) AS clean_transactions,
    COUNT(CASE WHEN event_type = 'view' THEN 1 END) AS clean_views,
    COUNT(CASE WHEN event_type = 'addtocart' THEN 1 END) AS clean_carts,
    COUNT(CASE WHEN event_type = 'transaction' THEN 1 END) AS clean_txns
FROM v_clean_events;
