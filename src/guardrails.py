"""
Module: guardrails.py
Description: Production security guardrails for Natural Language to SQL generation.
Enforces:
  1. Read-Only (SELECT / WITH only, strictly no DDL/DML)
  2. Table Allowlist (Only approved analytical tables and views)
  3. Row Limit Enforcement (Auto-caps results to prevent memory exhaustion)
  4. Single-Statement Enforcement (Blocks query chaining and SQL injection)
"""

import re
from typing import Tuple, List, Set

# Approved Tables and Views in Oracle GROWTH_USER Schema
TABLE_ALLOWLIST: Set[str] = {
    "V_CLEAN_EVENTS",
    "FACT_EVENTS_SESSIONIZED",
    "FACT_SESSIONS",
    "DIM_CATEGORIES",
    "DIM_ITEMS",
    "V_PBI_WEEKLY_NORTH_STAR",
    "V_PBI_FUNNEL_STAGES",
    "V_PBI_FUNNEL_VISITOR_TYPE",
    "V_PBI_FUNNEL_BY_CATEGORY",
    "V_PBI_FUNNEL_BY_HOUR",
    "V_PBI_VISITOR_SEGMENTS",
    "V_PBI_BUYER_RFM",
    "DUAL"
}

# Forbidden SQL Keywords (DDL, DML, Administration, Transaction Control)
FORBIDDEN_KEYWORDS: List[str] = [
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bDELETE\b",
    r"\bDROP\b",
    r"\bALTER\b",
    r"\bTRUNCATE\b",
    r"\bCREATE\b",
    r"\bRENAME\b",
    r"\bMERGE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bCALL\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bLOCK\b",
    r"\bCOMMIT\b",
    r"\bROLLBACK\b",
    r"\bSAVEPOINT\b",
    r"\bALTER\s+SYSTEM\b",
    r"\bALTER\s+SESSION\b",
    r"\bDBMS_\w+\b"
]

DEFAULT_ROW_LIMIT = 100

def sanitize_query(raw_query: str) -> str:
    """Removes markdown formatting, comments, and trailing semicolons."""
    # Strip markdown code blocks
    cleaned = re.sub(r'```(?:sql)?', '', raw_query, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    # Strip single-line comments
    lines = [re.sub(r'--.*$', '', line) for line in cleaned.splitlines()]
    cleaned = "\n".join(lines).strip()

    # Strip multi-line comments
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL).strip()

    # Strip trailing semicolon
    cleaned = cleaned.rstrip(';').strip()
    return cleaned

def extract_tables(query: str) -> Set[str]:
    """Extracts table names following FROM and JOIN clauses."""
    # Regex to find table names after FROM or JOIN
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)?)'
    matches = re.findall(pattern, query, flags=re.IGNORECASE)
    tables = set()
    for match in matches:
        # Strip schema prefix if present (e.g. GROWTH_USER.FACT_SESSIONS -> FACT_SESSIONS)
        t_name = match.split('.')[-1].upper()
        tables.add(t_name)
    return tables

def validate_and_secure_query(raw_query: str) -> Tuple[bool, str, str]:
    """
    Validates a SQL query against security guardrails.
    Returns:
        (is_valid: bool, sanitized_or_capped_sql: str, error_message: str)
    """
    query = sanitize_query(raw_query)

    if not query:
        return False, "", "Empty query provided."

    # 1. Single Statement Enforcement
    # Disallow semicolons inside query to prevent query chaining
    if ';' in query:
        return False, "", "Security Violation: Multiple statement chaining (semicolon) is prohibited."

    # 2. SELECT-Only Enforcement (Must start with SELECT or WITH)
    first_word = query.split()[0].upper()
    if first_word not in ("SELECT", "WITH"):
        return False, "", f"Security Violation: Query must start with SELECT or WITH. Received: {first_word}"

    # 3. Forbidden Keyword Scan
    for pattern in FORBIDDEN_KEYWORDS:
        if re.search(pattern, query, flags=re.IGNORECASE):
            matched_kw = re.search(pattern, query, flags=re.IGNORECASE).group(0)
            return False, "", f"Security Violation: Prohibited DDL/DML keyword detected: '{matched_kw}'"

    # 4. Table Allowlist Check
    tables_found = extract_tables(query)
    unauthorized_tables = tables_found - TABLE_ALLOWLIST
    if unauthorized_tables:
        return False, "", f"Security Violation: Access denied to unapproved table(s): {', '.join(unauthorized_tables)}"

    # 5. Row Limit Enforcement
    has_fetch_first = bool(re.search(r'\bFETCH\s+FIRST\s+\d+\s+ROWS\s+ONLY\b', query, flags=re.IGNORECASE))
    has_rownum = bool(re.search(r'\bROWNUM\b', query, flags=re.IGNORECASE))

    final_query = query
    if not has_fetch_first and not has_rownum:
        final_query = f"{query}\nFETCH FIRST {DEFAULT_ROW_LIMIT} ROWS ONLY"

    return True, final_query, ""
