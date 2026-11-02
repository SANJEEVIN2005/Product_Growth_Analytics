-- ============================================================
-- Script: 13_create_readonly_user.sql
-- Description: Creates read-only database user for Ask-Your-Data layer
-- Run as: sqlplus / as sysdba
-- ============================================================

ALTER SESSION SET CONTAINER = XEPDB1;

-- Drop user if already exists
BEGIN
   EXECUTE IMMEDIATE 'DROP USER growth_readonly CASCADE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -01918 THEN
         RAISE;
      END IF;
END;
/

-- Create dedicated read-only database user (pass password as parameter &1)
CREATE USER growth_readonly IDENTIFIED BY "&1"
  DEFAULT TABLESPACE USERS
  TEMPORARY TABLESPACE TEMP
  QUOTA 0 ON USERS;


GRANT CREATE SESSION TO growth_readonly;

-- Grant SELECT ONLY privileges on all clean analytics tables and views
GRANT SELECT ON growth_user.v_clean_events TO growth_readonly;
GRANT SELECT ON growth_user.fact_events_sessionized TO growth_readonly;
GRANT SELECT ON growth_user.fact_sessions TO growth_readonly;
GRANT SELECT ON growth_user.dim_categories TO growth_readonly;
GRANT SELECT ON growth_user.dim_items TO growth_readonly;
GRANT SELECT ON growth_user.v_pbi_weekly_north_star TO growth_readonly;
GRANT SELECT ON growth_user.v_pbi_funnel_stages TO growth_readonly;
GRANT SELECT ON growth_user.v_pbi_funnel_visitor_type TO growth_readonly;
GRANT SELECT ON growth_user.v_pbi_funnel_by_category TO growth_readonly;
GRANT SELECT ON growth_user.v_pbi_funnel_by_hour TO growth_readonly;
GRANT SELECT ON growth_user.v_pbi_visitor_segments TO growth_readonly;
GRANT SELECT ON growth_user.v_pbi_buyer_rfm TO growth_readonly;

-- Create public synonyms for analytical tables and views so queries don't need 'growth_user.' prefix
CREATE OR REPLACE PUBLIC SYNONYM v_clean_events FOR growth_user.v_clean_events;
CREATE OR REPLACE PUBLIC SYNONYM fact_events_sessionized FOR growth_user.fact_events_sessionized;
CREATE OR REPLACE PUBLIC SYNONYM fact_sessions FOR growth_user.fact_sessions;
CREATE OR REPLACE PUBLIC SYNONYM dim_categories FOR growth_user.dim_categories;
CREATE OR REPLACE PUBLIC SYNONYM dim_items FOR growth_user.dim_items;
CREATE OR REPLACE PUBLIC SYNONYM v_pbi_weekly_north_star FOR growth_user.v_pbi_weekly_north_star;
CREATE OR REPLACE PUBLIC SYNONYM v_pbi_funnel_stages FOR growth_user.v_pbi_funnel_stages;
CREATE OR REPLACE PUBLIC SYNONYM v_pbi_funnel_visitor_type FOR growth_user.v_pbi_funnel_visitor_type;
CREATE OR REPLACE PUBLIC SYNONYM v_pbi_funnel_by_category FOR growth_user.v_pbi_funnel_by_category;
CREATE OR REPLACE PUBLIC SYNONYM v_pbi_funnel_by_hour FOR growth_user.v_pbi_funnel_by_hour;
CREATE OR REPLACE PUBLIC SYNONYM v_pbi_visitor_segments FOR growth_user.v_pbi_visitor_segments;
CREATE OR REPLACE PUBLIC SYNONYM v_pbi_buyer_rfm FOR growth_user.v_pbi_buyer_rfm;
