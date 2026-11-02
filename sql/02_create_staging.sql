-- ============================================================
-- 02_create_staging.sql
-- Run as growth_user in XEPDB1
-- Connect string: sqlplus growth_user/<password>@localhost:1521/XEPDB1
-- ============================================================

-- Drop staging tables if they exist
BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE stg_category_tree PURGE';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE stg_events PURGE';
EXCEPTION WHEN OTHERS THEN NULL;
END;
/

-- Staging table for category tree hierarchy
CREATE TABLE stg_category_tree (
    categoryid    NUMBER(10),
    parentid      NUMBER(10)
);

-- Staging table for raw event stream
CREATE TABLE stg_events (
    timestamp      NUMBER(18),
    visitorid      NUMBER(10),
    event          VARCHAR2(20),
    itemid         NUMBER(10),
    transactionid  NUMBER(10)
);

COMMENT ON TABLE stg_category_tree IS 'Staging raw table for category_tree.csv';
COMMENT ON TABLE stg_events IS 'Staging raw table for events.csv';
