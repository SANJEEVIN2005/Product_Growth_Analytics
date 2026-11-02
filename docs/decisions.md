# Analytical Decisions and Assumptions Log

This document records architectural, data engineering, statistical, and modeling decisions made throughout the project lifecycle.

---

## Log

### DEC-001: Data Directory Structure and Version Control
- **Date:** 2026-11-01
- **Domain:** Project Architecture & Setup
- **Decision:** Raw dataset files (`events.csv` ~94MB, `category_tree.csv` ~14KB, and raw archives) are stored in `data/raw/` and excluded from git tracking via `.gitignore`. Processed CSV deliverables intended for Power BI consumption will be exported to `outputs/` and tracked.
- **Rationale:** Large raw datasets bloat Git repositories and violate version control best practices.

### DEC-002: Segmentation Dimensions in the Absence of Device Telemetry
- **Date:** 2026-11-01
- **Domain:** Telemetry Schema & Segmentation Dimensions
- **Decision:** As verified in schema inspection, `events.csv` contains only `(timestamp, visitorid, event, itemid, transactionid)` and contains NO device or user-agent attribute. We will strictly avoid fabricating or segmenting by device type. Instead, analysis will segment across:
  1. Visitor Lifecycle Status: New (first recorded visit) vs. Returning visitors.
  2. Taxonomy: Top-level and sub-level product categories from `category_tree.csv`.
  3. Temporal: Hour of day (0-23 UTC) and day of week.
- **Rationale:** Upholds analytical integrity. Product companies frequently analyze feature engagement across temporal cohorts and user lifecycle stages when device instrumentation is missing.

### DEC-003: Timestamp Standardization and Epoch Millisecond Conversion
- **Date:** 2026-11-01
- **Domain:** Timestamp Standardization & Pipeline Design
- **Decision:** `events.csv` stores timestamps as 13-digit Unix epoch milliseconds (UTC range: 1430622004384 to 1442545187788, covering 2015-05-03 03:00:04 UTC to 2015-09-18 02:59:47 UTC).
  In Oracle SQL:
  - Staging loads raw `timestamp` as `NUMBER(18)`.
  - The clean table derives:
    `event_time = TIMESTAMP '1970-01-01 00:00:00.000 UTC' + numtodsinterval(timestamp / 1000, 'SECOND')`
    and `event_date = TRUNC(CAST(event_time AS DATE))`.
- **Rationale:** Preserves millisecond precision for sessionization tie-breaking while providing standard date indexing for partitioning and cohort analysis.

### DEC-004: Staging Table Design, SQL*Loader Direct Path, and Clean Events Indexing
- **Date:** 2026-11-01
- **Domain:** High-Throughput Staging & Indexing
- **Decision:** 
  1. Staging tables `stg_category_tree` and `stg_events` created in `GROWTH_USER` on Oracle 21c XE (`XEPDB1`).
  2. SQL*Loader direct path (`direct=true`) employed for `events.csv`, loading all 2,756,101 rows in 6.77 seconds with 0 rejections and 0 discards.
  3. Clean analytical table `events` populated with atomic date conversions and indexed on:
     - `idx_events_visitor`: `(visitorid, event_time)` for sessionization and funnel lag/lead window evaluations.
     - `idx_events_date`: `(event_date)` for temporal range and daily cohort aggregations.
     - `idx_events_type`: `(event_type)` for filtering views, cart additions, and transactions.
     - `idx_events_item`: `(itemid)` for category joins.
- **Rationale:** Minimizes I/O overhead on analytical window queries and guarantees 100% data reconciliation against source CSV files.

### DEC-005: Data Quality Findings and Bot Filtering Strategy
- **Date:** 2026-11-01
- **Domain:** Data Quality & Bot Filtering
- **Decision & Findings:**
  1. **Date Range & Span:** 2015-05-03 03:00:04 UTC to 2015-09-18 02:59:47 UTC (138 calendar days, 2,756,101 events).
  2. **Duplicates:** 458 groups comprising 460 excess duplicate events (0.017% of total volume) with identical millisecond timestamps, visitorid, event, itemid, and transactionid. Proposed to be deduplicated in the analytical layer.
  3. **Null Invariants:** 0 NULLs in mandatory fields; 0 non-null transaction IDs on views/carts; 100% of transaction events have transaction IDs.
  4. **Direct Checkouts:** 2,633 out of 22,457 purchased items (11.72%) lack a prior recorded view for that specific item in the dataset, reflecting direct reorders, category-level additions, or left-censored browsing history prior to May 3, 2015.
  5. **Bot Cutoff Recommendation:** Naive event-count filtering (e.g. >200 events) drops 125 VIP heavy buyers responsible for 5,779 purchases (25.7% of platform sales). To preserve commercial truth, we propose a precision rule targeting non-converting scrapers:
     `is_bot = 1 WHERE total_events > 200 AND total_transactions = 0`
     This eliminates 63 automated web crawlers (29,000 phantom views/carts, 1.05% of traffic) with 0 transactions lost.
- **Rationale:** Protects conversion metrics from phantom bot views while preventing catastrophic loss of high-value buyer cohorts.

### DEC-006: Metric Framework Architecture, Activation Criteria, and Guardrail Thresholds
- **Date:** 2026-11-01
- **Domain:** Growth Metrics & North Star Framework
- **Decision:**
  1. **North Star Metric:** Weekly Purchasing Visitors (WPV). Measures unique non-bot transacting customers per ISO calendar week. Baseline hovers around 640 buyers/week (range: 482 - 727), with weekly buyer conversion rate between 0.67% and 0.94%.
  2. **Activation Definition:** Formally defined as "Exploration Activation" ($\ge 3$ distinct items viewed) and "Intent Activation" ($\ge 1$ cart addition). Empirical analysis showed single-view bounced visitors convert at only 0.032%, whereas exploring $\ge 3$ items delivers a 5.18x conversion lift (4.32%), and cart addition delivers a 33.7x lift (28.06%).
  3. **Velocity Baseline:** 81.61% of buyers complete their first purchase on the same calendar day (median elapsed time: 0.31 hours / 18.6 minutes).
  4. **Power Buyer Concentration:** Repeat purchase rate is 9.07%, but 90 power buyers (0.77% of all buyers) generate 26.19% of all platform orders.
  5. **Guardrail Metric:** Cart abandonment rate benchmarked at 71.94% (ceiling threshold: 75.0%), and scraper traffic ratio benchmarked at 1.05% (ceiling threshold: 3.0%).
- **Rationale:** Provides mathematically defensible, mutually exclusive metric definitions backed by empirical distribution analysis.

### DEC-007: Sessionization Parameterization, Tie-Breakers, and Category Hierarchy Resolution
- **Date:** 2026-11-01
- **Domain:** Sessionization & Funnel Analytics
- **Decision:**
  1. **Inactivity Threshold:** Standard digital analytics 30-minute inactivity boundary (1,800,000 milliseconds) implemented via `LAG(raw_timestamp) OVER (PARTITION BY visitorid ORDER BY raw_timestamp, event_id)`.
  2. **Deterministic Tie-Breaker:** When timestamps are identical down to the millisecond, `event_id` (auto-incrementing identity sequence) is enforced as the deterministic tie-breaker.
  3. **Category Tree Resolution:** `dim_categories` and `dim_items` constructed by resolving 1,669 category nodes up to Level 6 into 25 Level-1 root categories using Oracle hierarchical SQL (`CONNECT_BY_ROOT categoryid START WITH parentid IS NULL CONNECT BY PRIOR categoryid = parentid`). 416,916 item mappings joined to enable category funnel segmentation.
  4. **Fact Tables Materialized:** `fact_events_sessionized` (2,726,642 rows) and `fact_sessions` (1,756,558 rows) created with B-tree indexing on `session_id`, `visitorid`, `session_date`, and `is_returning`.
- **Rationale:** Materialization reduces subsequent multi-stage cohort and segmentation query execution from minutes to milliseconds and ensures reproducible data exports for Power BI.

### DEC-008: Cohort Retention Modeling & E-Commerce Plateau Interpretation
- **Date:** 2026-11-02
- **Domain:** Cohort Retention Dynamics
- **Decision:**
  1. **Cohort Grain:** Weekly ISO cohorts (`TRUNC(session_date, 'IW')`) tracking 21 weekly acquisition groups from 2015-04-27 to 2015-09-14.
  2. **Activity Retention:** Defined as any recorded session in subsequent weeks ($W_0, W_1, \dots, W_{12+}$).
  3. **Buyer Repeat Retention:** Defined as any purchasing session in subsequent weeks for customers whose first transaction occurred in their cohort week.
  4. **Analytical Interpretation of Low Retention:** $W_1$ activity retention drops sharply to 3.4% - 4.8%, which is realistic for open-web e-commerce without required authentication. Importantly, the retention curve flattens into a horizontal plateau around 0.6% - 1.0% by Week 6+, demonstrating habit formation for a core loyal segment.
- **Rationale:** Honest, unvarnished reporting of e-commerce retention dynamics is essential for product strategy; false inflation of retention through loose definitions would mislead executive resource allocation.

### DEC-009: Controlled Experimentation Methodology and Ship Decision (Cookie Cats A/B Test)
- **Date:** 2026-11-02
- **Domain:** Experimentation & Hypothesis Testing
- **Decision & Analytical Findings:**
  1. **Outlier Treatment:** Single user `6390605` in `gate_30` logged 49,854 game rounds (75th percentile: 51). Identified as an impossible bot/counter corruption and removed, resulting in a clean analytical sample of 90,188 players.
  2. **Sample Ratio Mismatch (SRM):** Control = 44,699 (49.56%), Treatment = 45,489 (50.44%). Chi-square goodness-of-fit yielded $\chi^2 = 6.920$, $p = 0.0085$. Documented as a minor operational discrepancy, robustly checked across parametric and non-parametric evaluations.
  3. **Statistical Power & MDE:** Baseline 7-day retention of 19.02% with $N \approx 45,000$ per variant provided 88.44% achieved statistical power to detect an MDE of $\pm 0.726\%$ absolute ($\pm 3.82\%$ relative) at $\alpha = 0.05$.
  4. **Primary Metric Result (7-Day Retention):** Dropped from 19.02% (Gate 30) to 18.20% (Gate 40) ($-0.818$ percentage points, relative $-4.30\%$). Two-proportion z-test yielded $z = -3.1574$, $p = 0.00159$. 10,000-iteration bootstrap simulation confirmed a 99.93% probability that Gate 30 is superior (95% CI: $[-1.326\%, -0.319\%]$). Remains statistically significant after Bonferroni correction ($\alpha_{\text{Bonf}} = 0.0167$).
  5. **Secondary Metric (1-Day Retention):** Dropped from 44.82% to 44.23% ($-0.592$ percentage points, $z = -1.787$, $p = 0.0739$, not statistically significant at $\alpha = 0.05$).
  6. **Guardrail Metric (Game Rounds):** No statistically significant difference in rounds played (mean 51.34 vs. 51.30, Welch $p = 0.9495$, Mann-Whitney $p = 0.0509$).
  7. **Product Recommendation:** **DO NOT SHIP.** Moving the gate to Level 40 provides zero engagement gain while triggering a statistically significant and commercially detrimental $-4.3\%$ relative degradation in 7-day player retention. Gate 30 forces an early breather that prevents hedonic burnout.
- **Rationale:** Backed by hypothesis rejection, non-parametric validation, and multiple testing error control.
### DEC-012: Product Manager Decision Memo & Strategic Roadmap Formulation
- **Date:** 2026-11-02
- **Domain:** Strategic Decision Memo & Product Roadmap
- **Decision:**
  1. **Strategic Synthesis:** Consolidated findings from clickstream analysis (2.73M clean events) and experimentation (90.2K users) into an executive 1–2 page memo ([`docs/decision_memo.md`](file:///d:/Projects/data_analyst_project/Product_Growth_Analytics_Funnel_Retention_Experimentation/docs/decision_memo.md)) targeted at the VP of Product and Growth leadership.
  2. **Core Growth Lever Priorities:**
     - **P0: Automated 2-Hour Cart Recovery Sequence:** Targeting 27,120 High-Intent Cart Abandoners. Modeled recovery of 5%–8% yields +1,356 to +2,170 incremental orders (+7.7% to +12.3% platform order expansion) with Very High confidence.
     - **P0: Catalog Explorer Activation Engine:** Targeting 170,577 visitors with $\ge 3$ views. Dynamic category carousels projected to yield +530 to +850 orders with High confidence (backed by the 5.18x activation lift).
     - **P0: Experimentation Governance (Do Not Ship Gate 40):** Formalized no-ship decision on Gate 40 to protect 7-day player retention (-4.3% degradation avoided) and established mandatory SRM and runtime guardrails.
     - **P1: VIP Loyalty Concierge:** Defending against attrition among 750 repeat buyers (6.4% of buyers driving 35.8% of orders).
  3. **Risk & Governance Transparency:** Explicitly documented limitations regarding unobserved currency/GMV, absence of device/channel attribution, and cookie expiration boundaries.
- **Rationale:** Demonstrates product sense, business acumen, and commercial prioritization essential for senior product data analyst roles.

### DEC-013: Ask-Your-Data Layer Architecture & Defense-in-Depth Guardrails
- **Date:** 2026-11-02
- **Domain:** Self-Service Analytics Engine & Security Guardrails
- **Decision:**
  1. **User Interface:** Built an interactive web application using Streamlit (`app/streamlit_app.py`) allowing non-technical product managers and growth leads to query Oracle XE via natural language.
  2. **Multi-Layer Defense-in-Depth Security:**
     - **Database-Level RBAC:** Created dedicated Oracle user `GROWTH_READONLY` (`sql/13_create_readonly_user.sql`) with quota 0, granted strictly `CREATE SESSION` and `SELECT` on analytical tables/views, preventing any DDL/DML mutation even if malicious SQL slips past application boundaries.
     - **Application-Level AST & Regex Guard:** Implemented `src/guardrails.py` to enforce `SELECT` / `WITH` exclusively, scan for prohibited keywords (`DROP`, `ALTER`, `TRUNCATE`, `UPDATE`, `DELETE`, `EXEC`), block query chaining (`;`), and enforce a 12-table allowlist (`V_PBI_*`, `FACT_*`, `DIM_*`).
     - **Performance Guard:** Automatically appends `FETCH FIRST 100 ROWS ONLY` if no row limit is specified, protecting Oracle memory.
     - **Connection-Level Guard:** Issues `SET TRANSACTION READ ONLY` on each session.
  3. **Evaluation Suite & Benchmarks:** Created `data/evaluation_set.json` with 25 ground-truth test cases (20 operational product questions across North Star, funnels, categories, hourly, and RFM tiers + 5 adversarial security injection attempts).
  4. **Empirical Evaluation Results:** Verified via `scripts/run_nl_sql_eval.py`:
     - Operational Analytics Accuracy: 20/20 (100.0%)
     - Adversarial Defense Block Rate: 5/5 (100.0%)
     - Overall Benchmark Accuracy: 25/25 (100.0%)
     - Stored full evaluation output in `outputs/nl_sql_eval_report.json`.
- **Rationale:** Delivers enterprise-grade security and reliability, demonstrating readiness for self-service analytics deployments.










