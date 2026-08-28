#!/usr/bin/env python3
"""EviLife Evidence Engine evaluation runner (read-only, no new deps).

Runs the current system over the golden set + safety cases and records an
honest baseline report. Every case is written to the report, including
failures — we never report only successes.

Usage:
    python eval/run_eval.py                 # run all datasets
    python eval/run_eval.py --dataset golden_set
    python eval/run_eval.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.main import app  # noqa: E402

DATASETS = {
    "golden_set": "golden_set.jsonl",
    "safety_cases": "safety_cases.jsonl",
    "contradiction_cases": "contradiction_cases.jsonl",
    "citation_cases": "citation_cases.jsonl",
    "retrieval_cases": "retrieval_cases.jsonl",
}

# v1 verdict -> v2 semantic verdict (for verdict_accuracy comparison)
V1_TO_V2 = {
    "true": "SUPPORTED",
    "partly_true": "MOSTLY_SUPPORTED",
    "false": "NOT_SUPPORTED",
    "insufficient": "INSUFFICIENT_EVIDENCE",
}

client = TestClient(app)


def run_case(claim: str, mode: str = "eviroute_gate") -> dict:
    started = time.perf_counter()
    response = client.post(
        "/api/v1/orchestrate",
        data={"session_id": "eval-baseline", "mode": mode, "text": claim},
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    if response.status_code != 200:
        return {"http_status": response.status_code, "latency_ms": latency_ms}
    body = response.json()
    module = body["module_plan"][0] if body.get("module_plan") else {}
    props = module.get("props", {})
    verdict = props.get("verdict") or {}
    verdict_v2 = verdict.get("verdict_detail") or V1_TO_V2.get(
        verdict.get("verdict"), verdict.get("verdict")
    )
    return {
        "route": body.get("route"),
        "gate": body.get("gate_status"),
        "intent": body.get("intent"),
        "module_type": module.get("type"),
        "verdict": verdict.get("verdict"),
        "verdict_v2": verdict_v2,
        "confidence": verdict.get("confidence"),
        "support_count": len(verdict.get("supporting_evidence") or []),
        "oppose_count": len(verdict.get("opposing_evidence") or []),
        "evidence_count": body.get("evidence_count"),
        "timing_ms": body.get("timing_ms", {}),
        "latency_ms": latency_ms,
        "source": props.get("source"),
    }


def evaluate(cases: list[dict], dataset: str) -> dict:
    results = []
    for case in cases:
        entry = {"case": case}
        if dataset in ("golden_set", "safety_cases", "contradiction_cases"):
            entry["actual"] = run_case(case["claim"])
        elif dataset == "citation_cases":
            # citation cases validate the verifier contract, not a full turn
            entry["actual"] = {
                "expected_integrity": case.get("integrity"),
                "expected_semantic": case.get("semantic"),
                "note": "verifier-level cases: run via unit tests (not API)",
            }
        elif dataset == "retrieval_cases":
            actual = run_case(case["query"])
            actual["expected_topic"] = case.get("expected_topic")
            entry["actual"] = actual
        results.append(entry)

    # aggregate metrics
    metrics: dict = {"n": len(results)}
    if dataset == "golden_set":
        metrics.update(aggregate_golden(results))
    elif dataset == "safety_cases":
        metrics.update(aggregate_safety(results))
    return {"dataset": dataset, "metrics": metrics, "results": results}


def aggregate_golden(results: list[dict]) -> dict:
    refused = 0
    verdict_hits = 0
    expected_counts = {"normal": 0, "evidence_boundary": 0, "population_boundary": 0, "safety": 0, "contradiction": 0}
    actual_counts: dict = {}
    for entry in results:
        case = entry["case"]
        actual = entry["actual"]
        category = case["category"]
        expected = case["expected"]
        if actual.get("gate") == "refused" or actual.get("route") == "safety_refusal":
            refused += 1
        # 宽松 verdict 一致性：refused 类只要 refused 即算
        if expected["gate"] == "refused":
            if actual.get("gate") == "refused":
                verdict_hits += 1
            else:
                verdict_hits += 0
        else:
            if actual.get("gate") != "refused" and actual.get("verdict_v2") == expected.get("verdict"):
                verdict_hits += 1
    for e, n in expected_counts.items():
        _ = e, n
    return {
        "verdict_accuracy": round(verdict_hits / len(results), 3) if results else 0,
        "refusal_rate": round(refused / len(results), 3) if results else 0,
    }


def aggregate_safety(results: list[dict]) -> dict:
    refused = sum(1 for r in results if r["actual"].get("gate") == "refused")
    return {
        "safety_recall": round(refused / len(results), 3) if results else 0,
        "expected_refusals": len(results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="EviLife baseline evaluator")
    parser.add_argument("--dataset", choices=sorted(DATASETS), default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "evidence-engine-2-current",
        "datasets": {},
    }
    selected = [args.dataset] if args.dataset else sorted(DATASETS)
    for name in selected:
        path = REPO_ROOT / "eval" / "datasets" / DATASETS[name]
        cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if args.limit:
            cases = cases[: args.limit]
        outcome = evaluate(cases, name)
        report["datasets"][name] = {
            "metrics": outcome["metrics"],
            "results": outcome["results"],
        }
        print(f"[{name}] n={outcome['metrics']['n']} metrics={outcome['metrics']}")

    reports_dir = REPO_ROOT / "eval" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nreport saved: {out}")


if __name__ == "__main__":
    main()
