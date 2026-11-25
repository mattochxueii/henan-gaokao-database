"""Version-bound research interface. Original candidate records stay immutable."""

import hashlib
import json

from gaokao import load, load_solutions, read_lines, read_json, require
from reference import reference_rows
from storage import reference_directory


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def research(root, topic=None, year=None, kind=None):
    sources, papers, _, entries = load(root)
    folder = reference_directory(root)
    if folder is not None:
        references = reference_rows(folder, sources, papers, entries, check_hash=True)
    else:
        from national_db import plain_math

        references = {row["id"]:row["candidate"] for row in plain_math(root) if row["legacy"]}
    solutions = load_solutions(root, entries, sources)
    analyses = {
        row["question_id"]: row for row in read_lines(root / "data/analysis/questions.jsonl")
    }
    curation = {
        row["question_id"]: row for row in read_lines(root / "data/analysis/curation.jsonl")
    }
    result = []
    for row in entries:
        key = row["id"]
        if key not in analyses:
            continue
        analysis = analyses[key]
        if year is not None and papers[row["paper_id"]]["year"] != year:
            continue
        if kind and row["kind"] != kind:
            continue
        if topic and topic not in json.dumps(analysis["knowledge"], ensure_ascii=False):
            continue
        ref = references[key]
        require(
            analysis["candidate_sha256"] == fingerprint(ref),
            f"题面发生变化，请重新分析 {key}",
        )
        result.append(
            {
                "id": key,
                "year": papers[row["paper_id"]]["year"],
                "kind": row["kind"],
                "points": row["points"],
                "candidate": ref,
                "analysis": analysis,
                "curation": curation[key],
                "original_independent_solution": solutions[key],
            }
        )
    return result


def rules(root):
    value = read_json(root / "data/analysis/rules.json")
    require(value["schema_version"] == 1, "命题规则版本不支持")
    return value
