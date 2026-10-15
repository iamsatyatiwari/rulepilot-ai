"""Run the golden set against live Gemini and report which expected outcomes hold.

Usage: python scripts/golden_eval.py [--repeat N] [--case CASE_ID ...] [--save DIR]

Each case runs a fresh investigation with only the baseline as the reference
rule (no approved rules, no review history), then checks it with
``app.golden.check_report``. Held-out metric values are printed for context but
are never pass/fail criteria. Use it after changing the prompt, the model, or a
dataset (skills.md skill 7). Exits 1 if any run fails.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.orchestrator import run_investigation  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.data import DEFAULT_SPLIT_SEED  # noqa: E402
from app.golden import GOLDEN_CASES, check_report  # noqa: E402
from app.intel.advisories import load_curated_advisories  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeat", type=int, default=1, help="runs per case (1-5)")
    parser.add_argument("--case", action="append", help="limit to these case ids")
    parser.add_argument("--save", type=Path, help="directory to write each report JSON")
    args = parser.parse_args()
    if not 1 <= args.repeat <= 5:
        parser.error("--repeat must be between 1 and 5")

    settings = get_settings()
    if not settings.gemini_configured:
        print("Gemini is not configured (set GOOGLE_API_KEY in backend/.env).")
        return 2
    cases = [case for case in GOLDEN_CASES if not args.case or case.case_id in args.case]
    if not cases:
        parser.error("no matching cases")
    advisories = load_curated_advisories()
    if args.save:
        args.save.mkdir(parents=True, exist_ok=True)

    passed = total = 0
    for case in cases:
        for attempt in range(1, args.repeat + 1):
            report = await run_investigation(
                advisories[case.advisory_id], case.dataset_id, DEFAULT_SPLIT_SEED, settings
            )
            failures = check_report(case, report)
            total += 1
            passed += not failures
            context = ""
            if report.holdout_delta is not None:
                context = f" (held-out recall {report.holdout_delta.recall_change:+.1%}, context only)"
            print(f"{'PASS' if not failures else 'FAIL'} {case.case_id} #{attempt}: {report.status}"
                  f" · model {report.model_run.model}{context}")
            for failure in failures:
                print(f"     - {failure}")
            for error in report.model_run.errors:
                print(f"     ! model error: {error[:160]}")
            if args.save:
                path = args.save / f"{case.case_id}-{attempt}.json"
                path.write_text(json.dumps(report.model_dump(mode="json"), indent=2))
    print(f"\n{passed}/{total} golden runs passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
