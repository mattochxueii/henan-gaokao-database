"""Inspect the tracked plaintext corpus and optionally refresh subject research profiles."""
import argparse
from pathlib import Path

import bootstrap  # noqa: F401
from core.paper_intake import CORE, PUBLIC, dna, documents
from gaokao import ROOT, digest, require
from storage import atomic_json


def answer_present(value):
    if isinstance(value, dict) and "reference_answer" in value:
        return bool(value["reference_answer"])
    return bool(value)


def audit(root, write_profiles=False):
    coverage = {}
    for subject in CORE:
        rows = []
        for path, paper in documents(root, subject):
            if not path.is_relative_to(root / PUBLIC):
                continue
            questions = paper["questions"]
            start = 21 if paper.get("written_only") else 1
            require([q["number"] for q in questions] == list(range(start, start+paper["question_count"])),
                    "明文卷题号不连续："+paper["id"])
            require(all(q["stem"] and q["stem"].strip() for q in questions), "明文卷缺题干："+paper["id"])
            for q in questions:
                for asset in q.get("asset_refs", []):
                    relative = asset.get("plaintext_path") if subject=="math" else asset["path"]
                    if relative:
                        local = path.parent / relative
                        sha = asset.get("plaintext_sha256") or asset.get("sha256")
                        require(local.is_file() and (not sha or digest(local)==sha),
                                "明文题图缺失或哈希错误："+q["id"])
            rows.append({"id":paper["id"],"year":paper["year"],"title":paper["title"],"regions":paper["regions"],
                         "exam_kind":paper["exam_kind"],"written_only":bool(paper.get("written_only")),
                         "path":path.relative_to(root).as_posix(),"content_sha256":paper["content_sha256"],
                         "question_count":len(questions),
                         "standalone_answers":sum(answer_present(q.get("reviewed_answer") or q.get("answer")) for q in questions),
                         "answers":sum(answer_present(q.get("reviewed_answer") or q.get("answer"))
                                       or bool(isinstance(q.get("answer"), dict)
                                               and (q["answer"].get("explanation") or q["answer"].get("raw_solution_latex")))
                                       for q in questions),
                         "usable_for_practice":sum(q.get("usable_for_practice", False) for q in questions),
                         "source_and_solution_reviewed":sum(q.get("source_and_solution_reviewed",False) for q in questions),
                         "blocked_numbers":[q["number"] for q in questions if not q.get("usable_for_practice")],
                         "source_url":paper["source"]["url"]})
        coverage[subject] = rows
        if write_profiles:
            atomic_json(root / "data/dna" / f"{subject}.json", dna(root,subject,tracked_only=True))
    return coverage


if __name__=="__main__":
    import json
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",type=Path,default=ROOT)
    ap.add_argument("--write-profiles",action="store_true")
    ap.add_argument("--coverage",type=Path)
    args=ap.parse_args()
    results=audit(args.root,args.write_profiles)
    if args.coverage:
        atomic_json(args.coverage,results)
    print(json.dumps({s:{"papers":len(rows),"questions":sum(p["question_count"] for p in rows),
                         "answers":sum(p["answers"] for p in rows),
                         "usable":sum(p["usable_for_practice"] for p in rows)}
                      for s,rows in results.items()},ensure_ascii=False,indent=2))
