"""Report review coverage and duplicate relationships without exporting historical text."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from gaokao import ROOT, dumps, read_json, require
from math_calibration import grade, load
from national_db import catalog, rows
from national_duplicates import compare
from national_quality import research_eligible
from storage import atomic_json


def report(root):
    raw = rows(root, calibrated=False)
    data = rows(root)
    ledger = load(root)
    active = {r["occurrence_id"]: r for r in data}
    require(
        all(
            key in active and active[key].get("calibration") == review
            for key, review in ledger.items()
        ),
        "复核台账含缺失或过期的题面版本",
    )
    by_series, by_year = defaultdict(Counter), defaultdict(Counter)
    for r in data:
        status = grade(r)
        by_series[r["series_id"]][status] += 1
        by_year[f"{r['series_id']}:{r['year']}"][status] += 1
    alignment = read_json(root / "reports/phase5-auto-alignment.json")["records"]
    anomalies = [
        row["occurrence_id"]
        for row in alignment
        if "native_pdf_text_alignment_needs_review" in row["issues"]
        and "quarantined_source_content_conflict"
        not in active[row["occurrence_id"]]["issues"]
    ]
    matches = defaultdict(list)
    for r in raw:
        matches[r["id"]].append(r["occurrence_id"])
    multi_region = Counter(x["paper_id"] for x in catalog(root, "paper-regions"))
    dupes = compare(raw)
    equivalent = defaultdict(list)
    for key, row in ledger.items():
        if alias := row.get("equivalence_id"):
            equivalent[alias].append(key)
    return {
        "total_occurrences": len(data),
        "unique_masters": len(matches),
        "ledger_rows": len(ledger),
        "by_confidence": dict(Counter(map(grade, data))),
        "by_series": dict(by_series),
        "by_series_and_year": dict(by_year),
        "deep_analyses": sum("deep_analysis" in r for r in data),
        "body_repaired": [
            r["occurrence_id"] for r in data if r.get("base_version_sha256")
        ],
        "answer_replaced_without_body_change": [
            key
            for key, row in ledger.items()
            if row.get("answer_disposition") == "replace"
        ],
        "quarantined_count": sum(not research_eligible(r) for r in data),
        "source_conflicts_excluded_from_references": sum(
            grade(r) == "source_conflict" for r in data
        ),
        "pdf_alignment_anomaly_count": len(anomalies),
        "pdf_alignment_anomaly_reviewed": [key for key in anomalies if key in ledger],
        "pdf_alignment_anomaly_pending": [
            key for key in anomalies if key not in ledger
        ],
        "shared_masters": [group for group in matches.values() if len(group) > 1],
        "reviewed_equivalent_groups": dict(equivalent),
        "multi_region_paper_count": sum(n > 1 for n in multi_region.values()),
        "duplicates_screen": dupes,
        "human_reviewed": False,
        "official_original_confirmed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = report(args.root)
    if args.output:
        atomic_json(args.output, result)
    print(dumps(result))
