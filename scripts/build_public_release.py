"""Build a clean, allowlisted public candidate, with no inherited Git history."""

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from gaokao import ROOT, digest, read_json, read_lines, relative_path, require
from local_archive import write_bundle
from local_data import split_tables
from security_scan import scan_blob
from storage import atomic_json

PILOT = "experiments/phase5/pilotC-v3"
BLOCKED = {".git", ".private", "private-data", ".deps", ".local-data", "work"}
BLOCKED_EXT = {".key", ".env", ".enc", ".part", ".log", ".sqlite", ".bundle"}
WINDOWS_PATH = re.compile(rb"(?i)[A-Z]:[\\\/](?:Users|chatgptfile)[\\\/]")


def export_path(name):
    path = PurePosixPath(name)
    require(
        not path.is_absolute()
        and str(path) == name
        and "\\" not in name
        and ":" not in name
        and ".." not in path.parts
        and not BLOCKED.intersection(part.lower() for part in path.parts)
        and path.suffix.lower() not in BLOCKED_EXT,
        "禁止发布路径：" + name,
    )
    return path


def copy_allowlist(root, target):
    used = set()
    for line in (
        (root / "public-release/files.txt").read_text(encoding="utf-8").splitlines()
    ):
        if not line or line.startswith("#"):
            continue
        source, _, destination = line.partition(" -> ")
        destination = destination or source
        export_path(source)
        export_path(destination)
        require(destination not in used, "发布路径重复：" + destination)
        used.add(destination)
        original = relative_path(root, source)
        require(
            original.is_file()
            and not any(
                (root / part).is_symlink()
                for part in (PurePosixPath(source), *PurePosixPath(source).parents)
            ),
            "发布源文件无效：" + source,
        )
        output = target / destination
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, output)


def export_sample(root, target):
    folder = root / PILOT
    proof = read_json(root / "reports/phase5-original-artifact-provenance.json")
    certificate = read_json(folder / "publication.json")
    require(
        certificate["published"] and certificate["question_count"] == 5,
        "原创样卷缺少发布记录",
    )
    require(
        certificate["pdf_sha256"] == digest(folder / "paper.pdf")
        and certificate["solutions_sha256"] == digest(folder / "solutions.pdf"),
        "原创样卷版本已变化，须重新审查",
    )
    author = read_json(folder / "raw-ai-candidate.json")
    visible = read_json(folder / "student-text.json")
    verified = read_json(folder / "math-verification.json")
    from analysis_db import fingerprint

    (provenance,) = [
        row
        for row in proof["generated_documents"]
        if row["folder"].endswith("/pilotC-v3")
    ]
    require(
        provenance["paper_sha256"] == certificate["pdf_sha256"]
        and provenance["answers_sha256"] == certificate["solutions_sha256"]
        and provenance["historical_complete_stem_exact_matches"] == []
        and certificate["candidate_sha256"] == fingerprint(author)
        and certificate["writing_sha256"] == fingerprint(visible),
        "原创性复核或版本记录不匹配",
    )
    paper_id = "example-original-math-pilot-c"
    source_id = "project-original-pilot-c"
    records = []
    for number, (q, wording, check) in enumerate(
        zip(author["questions"], visible["questions"], verified, strict=True), 1
    ):
        require(q["id"] == wording["id"] == check["id"], "样题版本关联错误")
        require(
            q["id"].startswith("orig:ai:phase5:C:") and not wording["figure"],
            "样题未在发布范围",
        )
        require(check["program_checks_passed"], "样题程序校验失败")
        records.append(
            {
                "id": q["id"],
                "paper_id": paper_id,
                "number": number,
                "kind": q["kind"],
                "points": q["points"],
                "stem": wording["stem"],
                "options": wording["options"],
                "parts": wording["parts"],
                "asset_refs": [],
                "formulas": [
                    formula
                    for value in [
                        wording["stem"],
                        *wording["options"].values(),
                        *(part["text"] for part in wording["parts"]),
                    ]
                    for formula in re.findall(r"\\\((.+?)\\\)", value, re.S)
                ],
                "topic_flags": [q["module"]],
                "source_locator": {
                    "source_id": source_id,
                    "path": "examples/pilot/paper.pdf",
                    "number": number,
                },
                "answer": {
                    "explanation": q["solution"],
                    "independent_check": check["tasks"],
                    "answer_key": check.get("answer_key"),
                },
                "review_status": "独立数学与PDF审查通过的项目原创样题",
                "content_complete": True,
            }
        )
    require(len(records) == 5, "样题数量不符")
    require(
        provenance["authored_question_ids"] == [r["id"] for r in records],
        "样题 ID 未纳入来源核查",
    )
    papers = [
        {
            "id": paper_id,
            "year": 2026,
            "subject": "math",
            "series_id": "project-original",
            "track": "unified",
            "question_count": len(records),
            "reported_name": visible["title"],
            "record_origin": "original_sample",
            "official_original": False,
        }
    ]
    sources = [
        {
            "id": source_id,
            "kind": "project_authored",
            "path": "examples/pilot/paper.pdf",
            "sha256": certificate["pdf_sha256"],
        }
    ]
    data = target / "sample-data"
    data.mkdir()
    write_bundle(
        data,
        "project-original-pilot-v1",
        "public-original",
        split_tables(papers, sources, [], records),
    )
    atomic_json(
        target / "examples/pilot/provenance.json",
        {
            "record_origin": "original_sample",
            "historical_exam": False,
            "publication": certificate,
            "question_ids": [r["id"] for r in records],
            "historical_occurrences_compared": proof["historical_occurrences_compared"],
        },
    )


def export_catalog(root, target):
    catalog = root / "national/catalog"
    sources = {r["id"]: r.get("url") for r in read_lines(catalog / "sources.jsonl")}
    from gaokao import source_catalog

    sources.update(
        {key: value.get("url") for key, value in source_catalog(root).items()}
    )
    relations = list(read_lines(catalog / "paper-regions.jsonl"))
    papers = [
        *read_lines(catalog / "papers.jsonl"),
        *read_lines(catalog / "legacy-papers.jsonl"),
    ]
    rows = []
    for paper in papers:
        uses = [r for r in relations if r["paper_id"] == paper["id"]]
        urls = {
            meta["url"]
            for label, meta in paper.get("source_files", {}).items()
            if label in ("pdf", "tex") and meta.get("url")
        }
        urls.update(sources.get(s) for r in uses for s in r["evidence"])
        if paper.get("legacy_path"):
            meta = read_json(root / paper["legacy_path"])
            urls.update(sources.get(s) for s in meta.get("attribution_sources", []))
            for material in meta["materials"].values():
                if isinstance(material, dict):
                    urls.update(sources.get(s) for s in material.get("source_ids", []))
        rows.append(
            {
                **{
                    key: paper[key]
                    for key in (
                        "id",
                        "year",
                        "subject",
                        "reported_name",
                        "series_id",
                        "track",
                        "official_original",
                    )
                },
                "regions": [
                    {k: r[k] for k in ("region_id", "usage_status")} for r in uses
                ],
                "source_urls": sorted(
                    u
                    for u in urls
                    if isinstance(u, str) and u.startswith(("https://", "http://"))
                ),
                "availability": "source_only",
                "bundled_questions": 0,
            }
        )
    with (target / "national/source-catalog.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def export_rules(root, target):
    rules = read_json(root / "analysis/rules.json")
    rules["scope"] = "开放候选版。蓝图只用于模拟；随包数据为项目原创样题。"
    rules["requirements"] = [
        row
        for row in rules["requirements"]
        if row["class"] in ("official_requirement", "simulation_setting")
    ]
    atomic_json(target / "analysis/rules.json", rules)
    editorial = read_json(root / "analysis/language-rules.json")
    atomic_json(
        target / "analysis/language-rules.json",
        {
            "schema_version": editorial["schema_version"],
            "version": editorial["version"],
            "source_scope": "项目中文题面编辑规则，历史语料单独管理",
            "rules": [
                {key: row[key] for key in ("id", "category", "rule", "blocking")}
                for row in editorial["rules"]
            ],
            "rubric_dimensions": editorial["rubric_dimensions"],
            "empirical_calibration": False,
        },
    )


def verify_release(folder):
    manifest = read_json(folder / "release-manifest.json")
    files = {}
    for path in sorted(folder.rglob("*")):
        name = path.relative_to(folder).as_posix()
        if name == "release-manifest.json":
            continue
        export_path(name)
        require(not path.is_symlink(), "发布包包含链接：" + name)
        if path.is_file():
            data = path.read_bytes()
            require(scan_blob(name, data)["passed"], "发布包安全扫描未通过：" + name)
            require(not WINDOWS_PATH.search(data), "发布包含有本机绝对路径：" + name)
            files[name] = digest(path)
    require(files == manifest["sha256"], "发布包文件与清单不一致")
    return manifest


def build(root, output, archive=None):
    require(
        not output.exists() and not output.is_relative_to(root.resolve()),
        "请选择现有仓库以外的新输出目录",
    )
    require(archive is None or not archive.exists(), "发布 ZIP 已存在")
    require(
        archive is None or not archive.is_relative_to(output), "ZIP 必须位于发布目录外"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".public-release-", dir=output.parent
    ) as tmp:
        stage = Path(tmp) / "release"
        stage.mkdir()
        copy_allowlist(root, stage)
        export_sample(root, stage)
        export_catalog(root, stage)
        export_rules(root, stage)
        manifest = {
            "schema_version": 1,
            "historical_full_text_included": False,
            "original_sample_count": 5,
            "sha256": {
                p.relative_to(stage).as_posix(): digest(p)
                for p in sorted(stage.rglob("*"))
                if p.is_file()
            },
        }
        atomic_json(stage / "release-manifest.json", manifest)
        verify_release(stage)
        stage.rename(output)
    if archive is not None:
        archive.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(archive, "x", compression=ZIP_DEFLATED) as bundle:
            for file in sorted(p for p in output.rglob("*") if p.is_file()):
                info = ZipInfo(file.relative_to(output).as_posix())
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, file.read_bytes())
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--zip", type=Path)
    options = parser.parse_args()
    result = build(
        ROOT, options.output.resolve(), options.zip and options.zip.resolve()
    )
    print(
        json.dumps(
            {
                "files": len(result["sha256"]),
                "original_sample_count": result["original_sample_count"],
            }
        )
    )
