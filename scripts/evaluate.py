"""Execute the actual unittest suite and preserve its result."""

import bootstrap
import io
import json
from pathlib import Path
import time
from datetime import datetime, timezone, timedelta
import unittest
from gaokao import ROOT
from storage import atomic_json


def main():
    start = time.monotonic()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {
        "tests_run": result.testsRun,
        "successful": result.wasSuccessful(),
        "failures": [
            {"test": str(test), "traceback": trace} for test, trace in result.failures
        ],
        "errors": [
            {"test": str(test), "traceback": trace} for test, trace in result.errors
        ],
        "skipped": [
            {"test": str(test), "reason": reason} for test, reason in result.skipped
        ],
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "date": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        "command": "python scripts/evaluate.py",
        "scope": "38 legacy tests plus Phase3 public defect, AI transport, mathematics, privacy and PDF regressions",
    }
    atomic_json(ROOT / "reports/test-results.json", report)
    (ROOT / "reports/test-results.txt").write_text(stream.getvalue(), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
