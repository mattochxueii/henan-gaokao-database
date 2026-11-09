"""Project restored private sources into a portable, local-only data bundle."""

import bootstrap  # noqa: F401
import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import national_db as national
from analysis_db import fingerprint, research
from gaokao import ROOT, digest, load, read_json, relative_path, require
from local_archive import write_bundle
from local_data import split_tables
from storage import atomic_json, inventory, reference_directory


def migrate(root, output):
    checked = national.validate(root)
    require(checked["legacy_38_preserved"], "请先恢复两套历史资料")
    old = reference_directory(root)
    new = national.private_folder(root)
    legacy_analysis = {row["id"]: row for row in research(root)}
    for folder, config_path in (
        (old, "private-data/inventory.json"),
        (new, "national/backup.json"),
    ):
        if (root / config_path).is_file():
            info = read_json(root / config_path)
            expected = info["files"] if isinstance(info, dict) else info
            require(inventory(folder) == expected, "源文件与独立备份库存不一致")
    records = national.rows(root, calibrated=False)
    counts = Counter(row["paper_id"] for row in records)
    papers = []
    for paper in [
        *national.catalog(root, "papers"),
        *national.catalog(root, "legacy-papers"),
    ]:
        if paper["id"] in counts:
            papers.append(
                {
                    **paper,
                    "question_count": counts[paper["id"]],
                    "record_origin": "historical_candidate",
                }
            )
    sources = {row["id"]: row for row in national.catalog(root, "sources")}
    legacy_sources, _, _, _ = load(root)
    sources.update(legacy_sources)
    regions = [
        r for r in national.catalog(root, "paper-regions") if r["paper_id"] in counts
    ]
    require(not output.exists(), "迁移输出已存在")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".migrate-", dir=output.parent) as temp:
        staging = Path(temp) / "bundle"
        staging.mkdir()
        shutil.copytree(old, staging / "evidence/legacy")
        shutil.copytree(new, staging / "evidence/national")
        for row in records:
            evidence = "evidence/legacy" if row["legacy"] else "evidence/national"
            row["source_locator"] = {**row["source_locator"], "evidence_root": evidence}
            if row["legacy"]:
                original = legacy_analysis[row["id"]]
                require(
                    row["version_sha256"]
                    == fingerprint(original["candidate"])
                    == row["analysis"]["candidate_sha256"]
                    == row["curation"]["candidate_sha256"],
                    "历史分析与题面版本不符",
                )
                row["original_independent_solution"] = original[
                    "original_independent_solution"
                ]
                for page in row["candidate"]["page_images"]:
                    require(relative_path(old, page).is_file(), "原始页图缺失")
            else:
                require(
                    row["answer"]["question_version_sha256"] == row["version_sha256"],
                    "历史答案与题面版本不符",
                )
                for asset in row["answer"]["asset_refs"]:
                    require(
                        digest(relative_path(new, asset["path"])) == asset["sha256"],
                        "答案配图校验失败",
                    )
                for locator_type in ("pdf", "tex"):
                    locator = row["source_locator"].get(locator_type)
                    if locator and locator.get("path"):
                        require(
                            digest(relative_path(new, locator["path"]))
                            == locator["sha256"],
                            "原文定位校验失败",
                        )
            mapped = []
            for asset in row["asset_refs"]:
                name = asset.get("path") or asset["image"]
                path = evidence + "/" + name
                mapped.append(
                    {
                        **asset,
                        "path": path,
                        "sha256": digest(relative_path(staging, path)),
                    }
                )
            row["asset_refs"] = mapped
        tables = split_tables(
            papers, list(sources.values()), regions, records, use_existing_versions=True
        )
        write_bundle(
            staging,
            "historical-phase5-v1",
            "local-only",
            tables,
            version_scheme="historical-source",
        )
        staging.rename(output)
    return {
        "paper_count": len(papers),
        "occurrences": len(records),
        "unique_questions": len(tables["questions"]),
        "legacy_records": len(legacy_analysis),
        "answers_bound": len(tables["answers"]),
        "analysis_records": sum(
            "analysis" in row or "national_analysis" in row for row in records
        ),
        "formula_entries": sum(len(row["formulas"]) for row in records),
        "asset_references": sum(len(row["asset_refs"]) for row in records),
        "source_inventories_unchanged": True,
        "distribution": "local-only",
        "manual_reverification": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    result = migrate(args.root.resolve(), args.output.resolve())
    atomic_json(args.report, result)
    print(json.dumps(result, ensure_ascii=False))
