"""Materialize the reviewed math view to the unified plaintext store, to the tracked private research corpus."""
import argparse
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

import bootstrap
from analysis_db import fingerprint
from core.paper_intake import PUBLIC, archive_questions, documents
from gaokao import ROOT, digest, read_json, relative_path, require
from national_db import catalog, private_folder, rows
from national_quality import practice_reviewed
from storage import atomic_json, reference_directory


def copy_crop(folder, asset, out, tmp, rendered):
    from PIL import Image

    if "image" in asset:
        source = relative_path(folder, asset["image"])
        if not source.is_file():
            return
        box = asset["box"]
    else:
        source = relative_path(folder, asset["path"])
        if not source.is_file() or not shutil.which("pdftoppm"):
            return
        require(digest(source) == asset["sha256"], "PDF 题图来源变化")
        key = (source, asset["page"])
        if key not in rendered:
            prefix = tmp / f"page-{len(rendered)}"
            p = str(asset["page"])
            subprocess.run(["pdftoppm", "-f", p, "-l", p, "-r", "144", "-singlefile",
                            "-png", str(source), str(prefix)], check=True, capture_output=True)
            rendered[key] = prefix.with_suffix(".png")
        source = rendered[key]
        with Image.open(source) as page:
            x, y = page.width / asset["page_size"][0], page.height / asset["page_size"][1]
        box = [round(v * (x if i % 2 == 0 else y)) for i,v in enumerate(asset["box"])]
    with Image.open(source) as page:
        require(0 <= box[0] < box[2] <= page.width and 0 <= box[1] < box[3] <= page.height, "题图裁切范围无效")
        crop = tmp / "crop.png"
        page.crop(tuple(box)).save(crop, optimize=True)
    sha = digest(crop)
    path = "assets/" + sha + ".png"
    destination = out / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copyfile(crop,destination)
    asset.update(plaintext_path=path, plaintext_sha256=sha)


def migrate(root):
    with TemporaryDirectory() as temp:
        return migrate_with_crops(root, Path(temp))


def migrate_with_crops(root, temp):
    groups = defaultdict(list)
    existing = {d["id"]: d for p, d in documents(root, "math") if p.is_relative_to(root / PUBLIC)}
    archive = rows(root, prefer_plaintext=False)
    regions = defaultdict(list)
    for relation in catalog(root, "paper-regions"):
        if relation["usage_status"] != "candidate_requires_independent_source":
            regions[relation["paper_id"]].append(relation["region_id"])
    from math_calibration import grade
    out = root / PUBLIC / "math"
    rendered = {}
    review_path = out / "assets/practice-reviews.json"
    practice = read_json(review_path) if review_path.is_file() else {}
    applied = set()
    for row in archive:
        row = {**row, "asset_refs":deepcopy(row.get("asset_refs", []))}
        folder = reference_directory(root) if row["legacy"] else private_folder(root)
        for asset in row.get("asset_refs", []):
            if asset.get("kind") == "pdf_region" or "image" in asset:
                copy_crop(folder, asset, out, temp, rendered)
                continue
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
        if review := practice.get(row["occurrence_id"]):
            row["practice_review"] = review
            evidence = relative_path(out, review["image"])
            require(practice_reviewed(row) and evidence.is_file() and digest(evidence) == review["image_sha256"],
                    "练习级复核版本或补充图件不匹配")
            row["usable_for_practice"] = True
            applied.add(row["occurrence_id"])
        groups[row["paper_id"]].append(row)
    require(applied == set(practice), "存在无法绑定的练习级复核")
    for key, questions in groups.items():
        questions.sort(key=lambda q: q["number"])
        q=questions[0]
        doc={"id":key,"subject":"math","year":q["year"],"title":q.get("paper_title",key),
             "regions":sorted(set(regions[key])),"series_id":q["series_id"],"exam_kind":"official_exam",
             "question_count":len(questions),"source": {"title":"原有项目双源档案",
                       "url":"https://github.com/DxAThing/Gaokao-Math-Problems-Compilation" if not q["legacy"] else
                       q["source_locator"]["source_url"],"rights_basis":"仅用于个人学习与教研归档"},
             "distribution":"private-research","compatibility":"national-math-v1","questions":questions,"content_sha256":fingerprint(questions)}
        if key in existing:
            require(fingerprint(archive_questions(existing[key]["questions"])) == fingerprint(archive_questions(questions)),
                    "既有明文快照不同，须保留旧版本："+key)
            if existing[key]["content_sha256"] == doc["content_sha256"]:
                continue
            require(all(not prev.get("plaintext_path") or cur.get("plaintext_path") == prev["plaintext_path"]
                        for old,new in zip(existing[key]["questions"],questions,strict=True)
                        for prev,cur in zip(old["asset_refs"],new["asset_refs"],strict=True)),
                    "原题图衍生件路径变化："+key)
        atomic_json(out/(key+".json"),doc)
    return {"papers":len(groups),"questions":len(archive),
            "usable":sum(q["usable_for_practice"] for rows in groups.values() for q in rows),
            "conflicts":sum(not q["usable_for_practice"] for rows in groups.values() for q in rows),
            "rights":"private-research"}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    print(migrate(parser.parse_args().root))
