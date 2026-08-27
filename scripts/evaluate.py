from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from app.config import Settings
from app.graph.orchestrator import AfterSalesGraph
from app.infrastructure.repository import InMemorySupportRepository
from app.services.llm import OpenAICompatibleLLM
from app.services.rag import PolicyKnowledgeBase
from app.tools.commerce import CommerceTools


def evaluate(cases_path: Path, output_path: Path) -> dict:
    settings = Settings(llm_enabled=False)
    repository = InMemorySupportRepository()
    graph = AfterSalesGraph(
        CommerceTools(repository),
        PolicyKnowledgeBase(Path("data/policies")),
        InMemorySaver(),
        llm=OpenAICompatibleLLM(settings),
        repository=repository,
    )
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    details = []
    for case in cases:
        result = graph.invoke(
            thread_id=f"eval-{case['id']}",
            user_id=case["user_id"],
            query=case["query"],
        )
        checks = {
            "intent": result["intent"] == case["expected_intent"],
            "status": result["status"] == case["expected_status"],
            "citation": not case.get("requires_citation") or bool(result["evidence"]),
            "error": not case.get("expect_error") or bool(result["error"]),
        }
        details.append(
            {
                "id": case["id"],
                "passed": all(checks.values()),
                "checks": checks,
                "actual_intent": result["intent"],
                "actual_status": result["status"],
            }
        )
    total = len(details)
    passed = sum(item["passed"] for item in details)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "deterministic-offline",
        "total": total,
        "passed": passed,
        "task_success_rate": round(passed / total, 4) if total else 0,
        "intent_accuracy": round(sum(item["checks"]["intent"] for item in details) / total, 4)
        if total
        else 0,
        "details": details,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run after-sales agent regression evaluation")
    parser.add_argument("--cases", type=Path, default=Path("data/eval_cases.json"))
    parser.add_argument("--output", type=Path, default=Path("data/evaluation/latest.json"))
    args = parser.parse_args()
    report = evaluate(args.cases, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
