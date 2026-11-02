@echo off
REM ============================================================
REM scripts/load_staging.bat
REM Loads category_tree.csv and events.csv into Oracle 21c XE
REM using SQL*Loader direct path / high-throughput parameters.
REM ============================================================

set ORACLE_HOME=D:\Downloads\Oracle21c\dbhomeXE
set PATH=%ORACLE_HOME%\bin;%PATH%

if "%DB_USER%"=="" set DB_USER=growth_user
if "%DB_CONNECT%"=="" set DB_CONNECT=localhost:1521/XEPDB1
if "%DB_PASS%"=="" (
  set /p DB_PASS="Enter database password for %DB_USER%: "
)


echo.
echo ============================================================
echo [1/2] Loading category_tree.csv (Expected: 1,669 rows)
echo ============================================================
sqlldr userid=%DB_USER%/%DB_PASS%@%DB_CONNECT% ^
  control=ctl\category_tree.ctl ^
  log=logs\category_tree.log ^
  bad=logs\category_tree.bad ^
  discard=logs\category_tree.dsc

echo.
echo ============================================================
echo [2/2] Loading events.csv (Expected: 2,756,101 rows)
echo ============================================================
sqlldr userid=%DB_USER%/%DB_PASS%@%DB_CONNECT% ^
  control=ctl\events.ctl ^
  log=logs\events.log ^
  bad=logs\events.bad ^
  discard=logs\events.dsc ^
  direct=true

echo.
echo SQL*Loader batch completed. Check logs\category_tree.log and logs\events.log.
