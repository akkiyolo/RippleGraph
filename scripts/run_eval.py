"""Run the evaluation harness."""

import json
import logging
import sys
from pathlib import Path

from ripplegraph.clients.pg_store import PgStore
from ripplegraph.clients.llm_client import create_llm_client
from ripplegraph.config import get_settings
from ripplegraph.eval.runner import run_evaluation
from ripplegraph.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info("=== RippleGraph Evaluation ===")

    store = PgStore(settings)
    store.initialize()
    llm = create_llm_client(settings)

    eval_path = sys.argv[1] if len(sys.argv) > 1 else "data/demo/eval_queries.json"
    report = run_evaluation(eval_path, store, llm, settings)

    # Print summary
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"Total queries:      {report['total']}")
    print(f"Status accuracy:    {report['status_accuracy']:.0%}")
    print(f"Content accuracy:   {report['content_accuracy']:.0%}")
    print(f"Temporal accuracy:  {report['temporal_accuracy']:.0%}")
    print("-" * 60)

    for r in report["results"]:
        status_icon = "✅" if r["status_match"] and r["content_match"] else "❌"
        print(f"  {status_icon} [{r['id']}] {r['question'][:50]}")
        print(f"     status={r['actual_status']} conf={r['confidence']:.2f} "
              f"temporal={r['actual_temporal']} evidence={r['evidence_count']}")
        if r["actual_answer"]:
            print(f"     answer: {r['actual_answer'][:80]}")
        if not r["status_match"]:
            print(f"     ⚠ expected status={r['expected_status']}")
        if not r["content_match"]:
            print(f"     ⚠ expected contains={r['expected_contains']}")

    # Save results
    results_path = Path("results/eval_results.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
