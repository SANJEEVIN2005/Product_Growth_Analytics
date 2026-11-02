# Business Questions & Analytical Objectives

## Project: Product Growth Analytics: Funnel, Retention and Experimentation

### Context
Product growth teams rely on behavioral telemetry, funnel diagnostics, retention tracking, and rigorous experimentation to drive sustainable user and revenue growth. This project analyzes real-world e-commerce user behavior (Retailrocket events dataset) and mobile game experimentation data (Cookie Cats A/B test) across the user lifecycle.

---

### Core Business Questions

#### 1. Full-Funnel Conversion & Friction Points
- **Question:** What is the micro-conversion rate across key user milestones (`View` $\rightarrow$ `Add to Cart` $\rightarrow$ `Transaction`), and where is the steepest drop-off occurring?
- **Dimensions:** How does conversion differ between **first-time visitors** vs. **returning visitors**, across **product categories**, and by **hour of day / day of week**?
- **Decision Impact:** Identifies whether product discovery, basket intent, or checkout friction is the primary bottleneck for revenue growth.

#### 2. Cohort Retention & Habit Formation
- **Question:** How well does the platform retain visitor engagement and purchase activity over time when tracking weekly acquisition cohorts?
- **Dimensions:** What is the 1-week, 2-week, and multi-week activity retention vs. repeat purchase retention?
- **Decision Impact:** Quantifies baseline churn and customer lifetime dynamics; determines whether marketing acquisition translates into organic re-engagement or single-session attrition.

#### 3. Traffic Integrity & Bot Identification
- **Question:** How much of the platform's observed activity is driven by automated scrapers/bots versus genuine prospective buyers?
- **Dimensions:** Event velocity, total events per visitor, view-to-transaction anomalies, and timestamp clustering.
- **Decision Impact:** Prevents product teams from optimizing for phantom bot sessions, distorts baseline conversion metrics, and ensures business decisions rely on genuine human demand.

#### 4. Behavioral Segmentation & Intent Profiling
- **Question:** Since e-commerce conversion rates are typically low (<2-3%), how can visitors be grouped by intent and exploration depth (sessions, view intensity, distinct items viewed, cart adds)?
- **Dimensions:** Recency, frequency of visits, product breadth, and basket velocity.
- **Decision Impact:** Unlocks personalized growth levers: identifies "High-Intent Lurkers" ripe for targeted retargeting or checkout nudges, and separates window shoppers from committed buyers.

#### 5. Controlled Experimentation & Feature Impact (A/B Test)
- **Question:** Does changing the progression gate from Level 30 to Level 40 in Cookie Cats improve player engagement (game rounds) and retention (Day 1 and Day 7 retention)?
- **Dimensions:** Control (Gate 30) vs. Treatment (Gate 40), Sample Ratio Mismatch (SRM), statistical power, two-proportion z-tests, bootstrap confidence intervals, and multiple testing guardrails.
- **Decision Impact:** Delivers a clear, statistically sound Ship / No-Ship product decision backed by hypothesis validation and risk assessment.
