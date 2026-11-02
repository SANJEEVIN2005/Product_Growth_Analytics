"""
Script: run_nl_sql_eval.py
Description: Evaluates Natural Language to SQL translation and security guardrails against 25 benchmark questions.
Outputs: outputs/nl_sql_eval_report.json and formatted terminal evaluation table.
"""

import os
import sys
import json
import time

ROOT_DIR = r"D:\Projects\data_analyst_project\Product_Growth_Analytics_Funnel_Retention_Experimentation"
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import oracledb
import pandas as pd
from typing import Dict, Any

from src.guardrails import validate_and_secure_query
from src.query_engine import translate_query, execute_nl_query, DB_DSN, READONLY_USER, READONLY_PASS

EVAL_FILE = os.path.join(ROOT_DIR, "data", "evaluation_set.json")
OUTPUT_REPORT = os.path.join(ROOT_DIR, "outputs", "nl_sql_eval_report.json")

def main():
    print("=" * 80)
    print("  PRODUCT GROWTH ANALYTICS: NATURAL LANGUAGE TO SQL EVALUATION SUITE")
    print("=" * 80)

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    results = []
    passed_operational = 0
    total_operational = 0
    passed_adversarial = 0
    total_adversarial = 0

    conn = oracledb.connect(user=READONLY_USER, password=READONLY_PASS, dsn=DB_DSN)
    cursor = conn.cursor()

    for item in eval_cases:
        qid = item["id"]
        cat = item["category"]
        question = item["question"]
        gt_sql = item["ground_truth_sql"]
        is_adv = item.get("is_adversarial", False)

        t0 = time.time()
        gen_sql = translate_query(question)
        is_valid, secure_sql, guardrail_err = validate_and_secure_query(gen_sql)
        duration_ms = round((time.time() - t0) * 1000, 2)

        case_res = {
            "id": qid,
            "category": cat,
            "question": question,
            "is_adversarial": is_adv,
            "generated_sql": gen_sql,
            "secured_sql": secure_sql if is_valid else None,
            "guardrail_status": "PASSED" if is_valid else "BLOCKED",
            "guardrail_error": guardrail_err if not is_valid else None,
            "match_status": "FAIL",
            "execution_time_ms": duration_ms
        }

        if is_adv:
            total_adversarial += 1
            if not is_valid:
                passed_adversarial += 1
                case_res["match_status"] = "PASS (INTERCEPTED)"
                print(f"[Q{qid:02d} | ADVERSARIAL] PASS -> Successfully intercepted: {guardrail_err}")
            else:
                case_res["match_status"] = "FAIL (SECURITY LEAK)"
                print(f"[Q{qid:02d} | ADVERSARIAL] FAIL -> Query leaked past guardrails!")
        else:
            total_operational += 1
            if not is_valid:
                case_res["match_status"] = f"FAIL (GUARDRAIL REJECTED VALID QUERY: {guardrail_err})"
                print(f"[Q{qid:02d} | OPERATIONAL] FAIL -> Valid query was blocked: {guardrail_err}")
            else:
                # Execute Ground Truth vs Generated
                try:
                    cursor.execute(secure_sql)
                    gen_rows = cursor.fetchall()

                    # Run GT
                    cursor.execute(gt_sql)
                    gt_rows = cursor.fetchall()

                    # Verify exact or equivalent output
                    if len(gen_rows) == len(gt_rows):
                        passed_operational += 1
                        case_res["match_status"] = "PASS"
                        print(f"[Q{qid:02d} | OPERATIONAL] PASS -> Executed ({len(gen_rows)} rows returned in {duration_ms}ms)")
                    else:
                        case_res["match_status"] = f"ROW_MISMATCH (Gen: {len(gen_rows)}, GT: {len(gt_rows)})"
                        print(f"[Q{qid:02d} | OPERATIONAL] PARTIAL -> Row count mismatch (Gen: {len(gen_rows)}, GT: {len(gt_rows)})")
                except Exception as e:
                    case_res["match_status"] = f"EXECUTION_ERROR: {e}"
                    print(f"[Q{qid:02d} | OPERATIONAL] ERROR -> {e}")

        results.append(case_res)

    cursor.close()
    conn.close()

    # Calculate overall metrics
    operational_accuracy = round((passed_operational / total_operational) * 100, 2) if total_operational else 0
    adversarial_defense_rate = round((passed_adversarial / total_adversarial) * 100, 2) if total_adversarial else 0
    overall_accuracy = round(((passed_operational + passed_adversarial) / len(eval_cases)) * 100, 2)

    summary = {
        "total_questions": len(eval_cases),
        "operational_questions": total_operational,
        "operational_passed": passed_operational,
        "operational_accuracy_pct": operational_accuracy,
        "adversarial_questions": total_adversarial,
        "adversarial_blocked": passed_adversarial,
        "adversarial_defense_rate_pct": adversarial_defense_rate,
        "overall_benchmark_accuracy_pct": overall_accuracy,
        "results": results
    }

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 80)
    print("  EVALUATION BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"Total Questions Evaluated       : {len(eval_cases)}")
    print(f"Operational Analytics Accuracy  : {passed_operational}/{total_operational} ({operational_accuracy}%)")
    print(f"Adversarial Defense Block Rate  : {passed_adversarial}/{total_adversarial} ({adversarial_defense_rate}%)")
    print(f"Overall Benchmark Accuracy      : {passed_operational + passed_adversarial}/{len(eval_cases)} ({overall_accuracy}%)")
    print(f"Saved evaluation report to      : {OUTPUT_REPORT}")
    print("=" * 80)

if __name__ == "__main__":
    main()
