-- ============================================================
-- 01_create_user.sql
-- Run as SYSDBA or admin in pluggable database XEPDB1
-- Usage: sqlplus sys/<sys_password>@localhost:1521/XEPDB1 as sysdba @sql\01_create_user.sql <growth_user_password>
-- ============================================================

ALTER SESSION SET CONTAINER = XEPDB1;

-- Create analytical schema user
-- Note: Replace &1 or enter password when prompted by SQL*Plus
CREATE USER growth_user IDENTIFIED BY "&1"
  DEFAULT TABLESPACE USERS
  TEMPORARY TABLESPACE TEMP
  QUOTA UNLIMITED ON USERS;


GRANT CONNECT, RESOURCE, CREATE VIEW, CREATE TABLE, CREATE SEQUENCE TO growth_user;

-- Verify creation
SELECT username, account_status, default_tablespace 
FROM dba_users 
WHERE username = 'GROWTH_USER';
