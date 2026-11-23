"""Materialize the reviewed math view to the unified plaintext store, for local use."""
import argparse
from collections import defaultdict
from pathlib import Path
import shutil

import bootstrap
from analysis_db import fingerprint
from core.paper_intake import LOCAL, documents
from gaokao import ROOT, digest, relative_path, require
from national_db import catalog, private_folder, rows
from storage import atomic_json, reference_directory


def migrate(root):
    groups = defaultdict(list)
    existing = dict((d["id"], d) for _, d in documents(root, "math"))
    archive = rows(root, prefer_plaintext=False)
    regions = defaultdict(list)
    for relation in catalog(root, "paper-regions"):
        if relation["usage_status"] != "candidate_requires_independent_source":
            regions[relation["paper_id"]].append(relation["region_id"])
    from math_calibration import grade
    out = root / LOCAL / "math"
    for row in archive:
        row = dict(row)
        folder = reference_directory(root) if row["legacy"] else private_folder(root)
        for asset in row.get("asset_refs", []):
            if "path" not in asset:
                continue
            source = relative_path(folder, asset["path"])
            if not source.is_file() or source.suffix.lower() not in (".png", ".jpeg", ".jpg", ".tex"):
                continue
            sha = digest(source)
            require(not asset.get("sha256") or asset["sha256"] == sha, "题图哈希变化")
            require(source.stat().st_size <= 2_000_000, "超大图件须维持原源定位")
            rel = "assets/" + sha + source.suffix.lower()
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copyfile(source, dst)
            asset["plaintext_path"] = rel
        state = grade(row)
        row.update(assessment_state=state, usable_for_practice=state != "source_conflict",
                   source_and_solution_reviewed=state == "source_and_solution_reviewed")
        if not row["usable_for_practice"] and state == "source_conflict" and not row.get("issues"):
            row["issues"] = ["calibration_source_conflict"]
        groups[row["paper_id"]].append(row)
    for key, questions in groups.items():
        questions.sort(key=lambda q: q["number"])
        q=questions[0]
        doc={"id":key,"subject":"math","year":q["year"],"title":q.get("paper_title",key),
             "regions":sorted(set(regions[key])),"series_id":q["series_id"],"exam_kind":"official_exam",
             "question_count":len(questions),"source": {"title":"原有项目双源档案",
                       "rights_basis":"原样保留受控学习／教研使用；公开再分发逐卷复核"},
             "compatibility":"national-math-v1","questions":questions,"content_sha256":fingerprint(questions)}
        if key in existing:
            require(existing[key] == doc, "既有明文快照不同，须保留旧版本："+key)
        else:
            atomic_json(out/(key+".json"),doc)
    return {"papers":len(groups),"questions":len(archive),
            "usable":sum(q["usable_for_practice"] for rows in groups.values() for q in rows),
            "conflicts":sum(not q["usable_for_practice"] for rows in groups.values() for q in rows),
            "rights":"local-only"}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    print(migrate(parser.parse_args().root))
