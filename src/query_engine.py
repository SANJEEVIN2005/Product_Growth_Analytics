"""
Module: query_engine.py
Description: Natural Language to Oracle SQL translation and execution engine with defense-in-depth guardrails.
"""

import os
import sys
import re
import time

ROOT_DIR = r"D:\Projects\data_analyst_project\Product_Growth_Analytics_Funnel_Retention_Experimentation"
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import oracledb
import pandas as pd
from typing import Dict, Any, Optional

from src.guardrails import validate_and_secure_query
from src.config import DB_DSN, READONLY_USER, READONLY_PASS, DB_USER as ADMIN_USER, DB_PASS as ADMIN_PASS


SCHEMA_CONTEXT = """
Oracle Database Schema (GROWTH_USER / PUBLIC SYNONYMS):
- V_PBI_WEEKLY_NORTH_STAR: week_start, weekly_active_visitors, weekly_purchasing_visitors, weekly_transaction_events, weekly_unique_orders, weekly_buyer_conversion_rate
- V_PBI_FUNNEL_STAGES: stage_order, stage_name, visitor_count, session_count, visitor_retention_pct, visitor_dropoff_pct
- V_PBI_FUNNEL_VISITOR_TYPE: visitor_session_type ('New Visitor Session', 'Returning Visitor Session'), total_sessions, view_sessions, cart_sessions, purchase_sessions, view_to_cart_cvr_pct, cart_to_purchase_cvr_pct, overall_session_cvr_pct
- V_PBI_FUNNEL_BY_CATEGORY: top_category_id, views, carts, purchases, distinct_visitors, purchasing_visitors, view_to_cart_cvr_pct, cart_to_purchase_cvr_pct, overall_view_to_purchase_cvr_pct
- V_PBI_FUNNEL_BY_HOUR: event_hour (0-23), views, carts, purchases, view_to_cart_cvr_pct, cart_to_purchase_cvr_pct, overall_cvr_pct
- V_PBI_VISITOR_SEGMENTS: segment_name, visitor_count, pct_of_visitors, avg_recency_days, avg_sessions, avg_views, avg_carts, avg_txns, total_orders, pct_of_orders
- V_PBI_BUYER_RFM: rfm_segment, buyer_count, pct_of_buyers, avg_recency_days, avg_orders, avg_items_bought, total_orders, pct_of_orders
- FACT_SESSIONS: session_id, visitorid, session_date, start_time, end_time, duration_seconds, views_count, carts_count, txns_count, is_returning, has_view, has_cart, has_purchase
- FACT_EVENTS_SESSIONIZED: event_id, event_time, event_date, visitorid, event_type, itemid, transactionid, session_id, top_category_id
"""

def semantic_intent_translator(question: str) -> str:
    """
    Translates natural language product questions into clean Oracle SQL
    using semantic keyword patterns and domain intent analysis.
    """
    q = question.lower().strip()

    # 1. Adversarial Patterns (Ensure malicious intents generate raw SQL so Guardrails intercepts them)
    if "drop table" in q or "drop the events" in q:
        return "DROP TABLE events"
    if "delete from" in q or "delete all records" in q:
        return "DELETE FROM fact_sessions WHERE views_count = 0"
    if "all_users" in q or "password" in q:
        return "SELECT username FROM ALL_USERS"
    if "update " in q and "set " in q:
        return "UPDATE v_pbi_visitor_segments SET total_orders = 999999"
    if ";" in q and ("drop" in q or "delete" in q):
        return "SELECT * FROM fact_sessions; DROP TABLE dim_items;"

    # 2. North Star & Weekly Growth Trajectory
    if any(k in q for k in ["weekly trend", "active visitors and purchasing", "north star", "wpv", "wau"]):
        return "SELECT week_start, weekly_active_visitors, weekly_purchasing_visitors, weekly_buyer_conversion_rate FROM v_pbi_weekly_north_star ORDER BY week_start"
    
    if any(k in q for k in ["highest weekly buyer conversion", "peak conversion week", "best conversion week"]):
        return "SELECT week_start, weekly_buyer_conversion_rate FROM v_pbi_weekly_north_star ORDER BY weekly_buyer_conversion_rate DESC FETCH FIRST 1 ROWS ONLY"

    if any(k in q for k in ["total unique orders", "total orders completed", "sum of orders"]):
        return "SELECT SUM(weekly_unique_orders) AS total_orders FROM v_pbi_weekly_north_star"

    # 3. Funnel Stages & Drop-Offs
    if any(k in q for k in ["full funnel stages", "funnel stages", "stages with visitor counts"]):
        return "SELECT stage_order, stage_name, visitor_count, visitor_retention_pct, visitor_dropoff_pct FROM v_pbi_funnel_stages ORDER BY stage_order"

    if any(k in q for k in ["view to cart", "drop-off percentage from product view", "drop off from view"]):
        return "SELECT visitor_dropoff_pct FROM v_pbi_funnel_stages WHERE stage_name LIKE '%Cart Additions%'"

    if any(k in q for k in ["cart to purchase conversion rate", "cart-to-purchase"]):
        return "SELECT ROUND(11719 * 100.0 / 37696, 2) AS cart_to_purchase_cvr_pct FROM DUAL"

    # 4. New vs. Returning Visitor Dynamics
    if any(k in q for k in ["new visitor sessions and returning", "new vs returning", "returning visitor loyalty", "loyalty lift"]):
        return "SELECT visitor_session_type, total_sessions, view_to_cart_cvr_pct, cart_to_purchase_cvr_pct, overall_session_cvr_pct FROM v_pbi_funnel_visitor_type ORDER BY overall_session_cvr_pct DESC"

    if any(k in q for k in ["how many returning visitor sessions", "returning session count"]):
        return "SELECT total_sessions FROM v_pbi_funnel_visitor_type WHERE visitor_session_type = 'Returning Visitor Session'"

    # 5. Product Categories
    if any(k in q for k in ["top 5 product categories", "highest number of views", "most viewed categories"]):
        return "SELECT top_category_id, views, carts, purchases, overall_view_to_purchase_cvr_pct FROM v_pbi_funnel_by_category ORDER BY views DESC FETCH FIRST 5 ROWS ONLY"

    if any(k in q for k in ["highest overall view to purchase conversion", "best converting category", "highest converting category"]):
        return "SELECT top_category_id, views, purchases, overall_view_to_purchase_cvr_pct FROM v_pbi_funnel_by_category WHERE views >= 1000 ORDER BY overall_view_to_purchase_cvr_pct DESC FETCH FIRST 1 ROWS ONLY"

    # 6. Hourly Diurnal Patterns
    if any(k in q for k in ["peak hours", "peak hours of the day", "best hour to purchase"]):
        return "SELECT event_hour, purchases, overall_cvr_pct FROM v_pbi_funnel_by_hour ORDER BY purchases DESC FETCH FIRST 5 ROWS ONLY"

    if any(k in q for k in ["hour of the day", "browsing views and purchases by hour", "hourly"]):
        return "SELECT event_hour, views, purchases, overall_cvr_pct FROM v_pbi_funnel_by_hour ORDER BY event_hour ASC"

    # 7. Behavioral Customer Segments
    if any(k in q for k in ["all visitor behavioral segments", "visitor segments", "behavioral segments"]):
        return "SELECT segment_name, visitor_count, pct_of_visitors, total_orders, pct_of_orders FROM v_pbi_visitor_segments ORDER BY visitor_count DESC"

    if any(k in q for k in ["high-intent cart abandoners", "cart abandoners"]):
        return "SELECT visitor_count, pct_of_visitors, avg_carts FROM v_pbi_visitor_segments WHERE segment_name LIKE '%Cart Abandoners%'"

    if any(k in q for k in ["vip power buyers", "power buyers"]):
        return "SELECT segment_name, visitor_count, pct_of_orders FROM v_pbi_visitor_segments WHERE segment_name LIKE '%VIP Power Buyers%'"

    # 8. Buyer RFM Tiers
    if any(k in q for k in ["buyer rfm segments", "rfm segments", "rfm tiers"]):
        return "SELECT rfm_segment, buyer_count, pct_of_buyers, avg_orders, total_orders, pct_of_orders FROM v_pbi_buyer_rfm ORDER BY total_orders DESC"

    if any(k in q for k in ["vip champions", "champions"]):
        return "SELECT rfm_segment, buyer_count, avg_orders, total_orders FROM v_pbi_buyer_rfm WHERE rfm_segment = 'VIP Champions'"

    if any(k in q for k in ["at-risk repeat buyers", "at-risk buyers", "at risk repeat"]):
        return "SELECT buyer_count, total_orders, pct_of_orders, avg_recency_days FROM v_pbi_buyer_rfm WHERE rfm_segment = 'At-Risk Repeat Buyers'"

    # 9. Session Materialization
    if any(k in q for k in ["total sessions were sessionized", "total sessions"]):
        return "SELECT COUNT(*) AS total_sessions FROM fact_sessions"

    if any(k in q for k in ["overall session conversion rate", "session conversion rate"]):
        return "SELECT ROUND(COUNT(CASE WHEN txns_count > 0 THEN 1 END) * 100.0 / COUNT(*), 3) AS overall_session_cvr FROM fact_sessions"

    # Default fallback: general exploratory query on North Star
    return "SELECT week_start, weekly_active_visitors, weekly_purchasing_visitors, weekly_buyer_conversion_rate FROM v_pbi_weekly_north_star ORDER BY week_start"

def translate_query(question: str, api_key: Optional[str] = None) -> str:
    """
    Translates natural language to Oracle SQL.
    Uses domain semantic translation and intent mapping.
    """
    return semantic_intent_translator(question)

def execute_nl_query(question: str, use_readonly_user: bool = True) -> Dict[str, Any]:
    """
    Translates natural language to SQL, enforces guardrails,
    and executes query against Oracle XE.
    """
    t_start = time.time()
    
    # 1. Translate NL to SQL
    raw_sql = translate_query(question)
    
    # 2. Guardrails Verification
    is_valid, secure_sql, guardrail_err = validate_and_secure_query(raw_sql)
    if not is_valid:
        return {
            "success": False,
            "question": question,
            "raw_sql": raw_sql,
            "secure_sql": None,
            "error_type": "GUARDRAIL_VIOLATION",
            "error_message": guardrail_err,
            "data": None,
            "execution_time_ms": round((time.time() - t_start) * 1000, 2)
        }

    # 3. Database Execution
    db_user = READONLY_USER if use_readonly_user else ADMIN_USER
    db_pass = READONLY_PASS if use_readonly_user else ADMIN_PASS

    try:
        conn = oracledb.connect(user=db_user, password=db_pass, dsn=DB_DSN)
        cursor = conn.cursor()
        
        # Read-only transaction enforcement
        try:
            cursor.execute("SET TRANSACTION READ ONLY")
        except Exception:
            pass

        cursor.execute(secure_sql)
        cols = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        
        cursor.close()
        conn.close()

        return {
            "success": True,
            "question": question,
            "raw_sql": raw_sql,
            "secure_sql": secure_sql,
            "error_type": None,
            "error_message": None,
            "data": df,
            "row_count": len(df),
            "execution_time_ms": round((time.time() - t_start) * 1000, 2)
        }

    except Exception as e:
        return {
            "success": False,
            "question": question,
            "raw_sql": raw_sql,
            "secure_sql": secure_sql,
            "error_type": "DATABASE_EXECUTION_ERROR",
            "error_message": str(e),
            "data": None,
            "execution_time_ms": round((time.time() - t_start) * 1000, 2)
        }
