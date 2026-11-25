"""Portable, versioned JSONL bundles for the public edition and user-supplied data."""

import json
import math
import os
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from analysis_db import fingerprint
from gaokao import digest, read_json, read_lines, relative_path, require
from national_schema import validate_paper
from storage import atomic_json, inventory


TABLES = ("papers", "paper-regions", "sources", "questions", "occurrences", "answers")
CONTENT = ("stem", "options", "formulas", "parts", "asset_refs")
DATASET_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,79}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def public_edition(root):
    config = root / "data/database.json"
    return config.is_file() and read_json(config).get("edition") == "public"


def locations(root):
    yield root / "sample-data"
    local = root / ".local-data/bundles"
    if local.is_dir():
        yield from sorted(
            p for p in local.iterdir() if p.is_dir() and not p.name.startswith(".")
        )


def _unique(records, label):
    result = {}
    for row in records:
        identifier = row["id"]
        require(isinstance(identifier, str) and identifier.strip(), f"{label} 缺少 ID")
        require(identifier not in result, f"{label} ID 重复：{identifier}")
        result[identifier] = row
    return result


def _manifest(folder):
    require(folder.is_dir() and not folder.is_symlink(), "数据包目录无效")
    require(not (folder / "manifest.json").is_symlink(), "数据包清单不能是链接")
    manifest = read_json(folder / "manifest.json")
    require(manifest.get("schema_version") == 1, "数据包版本不支持")
    require(DATASET_ID.fullmatch(manifest["dataset_id"]), "数据包 ID 无效")
    require(
        manifest["distribution"] in ("public-original", "local-only"), "数据包用途无效"
    )
    require(
        manifest["version_scheme"] in ("normalized-question", "historical-source"),
        "题面版本规则无效",
    )
    require(
        manifest["distribution"] == "local-only"
        or manifest["version_scheme"] == "normalized-question",
        "原创样题须绑定题面内容",
    )
    return manifest


def read_bundle(folder, check_files=False):
    """Check core table checksums on every load. Validate attachments on import/audit."""
    manifest = _manifest(folder)
    expected = _unique(
        (dict(item, id=item["path"]) for item in manifest["files"]), "文件清单"
    )
    for name in TABLES:
        filename = name + ".jsonl"
        path = relative_path(folder, filename)
        item = expected.get(filename, {})
        require(
            path.is_file()
            and not path.is_symlink()
            and digest(path) == item.get("sha256"),
            "数据表缺失或校验失败：" + filename,
        )
    if check_files:
        for path in folder.rglob("*"):
            require(
                not path.is_symlink()
                and path.resolve().is_relative_to(folder.resolve()),
                "数据包包含链接或越界路径",
            )
        actual = [item for item in inventory(folder) if item["path"] != "manifest.json"]
        require(
            actual == sorted(manifest["files"], key=lambda item: item["path"]),
            "数据包文件清单或校验值不匹配",
        )
    tables = {name: list(read_lines(folder / (name + ".jsonl"))) for name in TABLES}
    papers = _unique(tables["papers"], "试卷")
    questions = _unique(tables["questions"], "主记录")
    occurrences = _unique(tables["occurrences"], "题目实例")
    answers = _unique(tables["answers"], "答案")
    sources = _unique(tables["sources"], "来源")
    for paper in papers.values():
        validate_paper(paper)
        require(paper.get("reported_name"), "缺少卷名")
    for question in questions.values():
        require(
            isinstance(question["stem"], str) and question["stem"].strip(), "缺少题面"
        )
        require(isinstance(question["options"], dict), "选项须为对象")
        require(
            all(isinstance(x, str) and x.strip() for x in question["options"].values()),
            "选项内容无效",
        )
        require(
            isinstance(question["formulas"], list)
            and all(isinstance(x, str) and x.strip() for x in question["formulas"]),
            "公式字段无效",
        )
        require(isinstance(question["parts"], list), "子问字段无效")
        require(isinstance(question["asset_refs"], list), "图像字段无效")
        for asset in question["asset_refs"]:
            path = asset.get("path")
            require(path and path in expected, "缺少图像或附件：" + str(path))
            relative_path(folder, path)
            require(asset.get("sha256") == expected[path]["sha256"], "图像版本不匹配")
    seen = set()
    counts = Counter()
    used_questions = set()
    used_answers = set()
    rows = []
    for occurrence in occurrences.values():
        paper_id = occurrence["paper_id"]
        number = occurrence["number"]
        require(type(number) is int and number > 0, "题号须为正整数")
        require((paper_id, number) not in seen, "同卷题号重复")
        seen.add((paper_id, number))
        paper = papers[paper_id]
        question = questions[occurrence["question_id"]]
        points = occurrence["points"]
        require(
            type(points) in (int, float) and math.isfinite(points) and points > 0,
            "分值无效",
        )
        require(occurrence.get("kind"), "缺少题型")
        if occurrence["kind"] in ("single_choice", "multiple_choice"):
            require(len(question["options"]) >= 2, "选择题缺少选项")
        require(DIGEST.fullmatch(occurrence["version_sha256"]), "题面版本校验值无效")
        if manifest["version_scheme"] == "normalized-question":
            require(
                occurrence["version_sha256"] == fingerprint(question),
                "题面版本与内容不符",
            )
        answer = answers[occurrence["answer_id"]]
        require(
            answer["occurrence_id"] == occurrence["id"]
            and answer["version_sha256"] == occurrence["version_sha256"],
            "答案与题目版本不一致",
        )
        require(
            isinstance(occurrence.get("source_locator"), dict)
            and occurrence["source_locator"],
            "缺少来源定位",
        )
        source_id = occurrence["source_locator"].get("source_id")
        if manifest["version_scheme"] == "normalized-question":
            require(source_id in sources, "题目来源未登记")
        used_questions.add(question["id"])
        used_answers.add(answer["id"])
        counts[paper_id] += 1
        rows.append(
            {
                **occurrence,
                **question,
                **{k: paper[k] for k in ("year", "subject", "series_id")},
                "question_id": question["id"],
                "track": paper.get("track"),
                "curriculum_id": paper.get("curriculum_id"),
                "occurrence_id": occurrence["id"],
                "dataset_id": manifest["dataset_id"],
                "distribution": manifest["distribution"],
                "record_origin": paper.get("record_origin", "historical_candidate"),
                "paper_title": paper["reported_name"],
                "answer": answer["payload"],
            }
        )
    require(
        used_questions == set(questions) and used_answers == set(answers),
        "有未关联的题面或答案",
    )
    require(
        all(p["question_count"] == counts[p["id"]] for p in papers.values()),
        "实际入库题数与登记不符",
    )
    region_keys = set()
    for relation in tables["paper-regions"]:
        paper = papers[relation["paper_id"]]
        key = (paper["id"], relation["region_id"])
        require(key not in region_keys, "省份关系重复")
        region_keys.add(key)
        require(
            (relation["year"], relation["subject"])
            == (paper["year"], paper["subject"]),
            "省份关系版本不符",
        )
    return manifest, tables, rows


def load(root, check_files=False, extra=None):
    papers, questions, occurrences, sources, regions, rows = {}, {}, set(), {}, [], []
    folders = list(locations(root))
    if extra is not None:
        folders.append(extra)
    dataset_ids = set()
    revisions = []
    for folder in folders:
        manifest, tables, bundle_rows = read_bundle(folder, check_files)
        dataset_id = manifest["dataset_id"]
        require(dataset_id not in dataset_ids, "数据包 ID 重复：" + dataset_id)
        require(
            folder == root / "sample-data" or manifest["distribution"] == "local-only",
            "用户导入资料须标为 local-only",
        )
        dataset_ids.add(dataset_id)
        revisions.append((dataset_id, fingerprint(manifest)))
        for paper in tables["papers"]:
            require(paper["id"] not in papers, "试卷 ID 已存在：" + paper["id"])
            papers[paper["id"]] = paper
        for row in tables["questions"]:
            require(
                row["id"] not in questions or questions[row["id"]] == row,
                "同一主记录 ID 对应不同内容",
            )
            questions[row["id"]] = row
        for row in bundle_rows:
            require(row["occurrence_id"] not in occurrences, "题目实例 ID 重复")
            occurrences.add(row["occurrence_id"])
            rows.append(row)
        for source in tables["sources"]:
            require(
                source["id"] not in sources or sources[source["id"]] == source,
                "同一来源 ID 对应不同记录",
            )
            sources[source["id"]] = source
        regions.extend(tables["paper-regions"])
    return {
        "papers": list(papers.values()),
        "legacy-papers": [],
        "paper-regions": regions,
        "sources": list(sources.values()),
        "rows": rows,
        "dataset_ids": sorted(dataset_ids),
        "revision": fingerprint(sorted(revisions)),
    }


def write_bundle(
    folder, dataset_id, distribution, tables, version_scheme="normalized-question"
):
    """Write standard tables into a staging directory, then seal the file inventory."""
    for name in TABLES:
        with (folder / (name + ".jsonl")).open(
            "w", encoding="utf-8", newline="\n"
        ) as stream:
            for row in tables[name]:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    atomic_json(
        folder / "manifest.json",
        {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "distribution": distribution,
            "version_scheme": version_scheme,
            "files": [
                row for row in inventory(folder) if row["path"] != "manifest.json"
            ],
        },
    )
    read_bundle(folder, check_files=True)


def install(root, source):
    require(public_edition(root), "请在公开候选版工作目录导入本地数据")
    manifest, _, _ = read_bundle(source, check_files=True)
    require(manifest["distribution"] == "local-only", "用户数据导入后仅保存在本地")
    parent = relative_path(root, ".local-data/bundles")
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / manifest["dataset_id"]
    lock = parent / ".import.lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError("已有导入正在进行，或上次导入异常退出") from exc
    try:
        require(not target.exists(), "该版本已安装，请使用新的数据包 ID")
        with tempfile.TemporaryDirectory(prefix=".incoming-", dir=parent) as temp:
            staging = Path(temp) / "bundle"
            shutil.copytree(source, staging, symlinks=True)
            load(root, check_files=True, extra=staging)
            os.rename(staging, target)
    finally:
        lock.rmdir()
    return {
        "dataset_id": manifest["dataset_id"],
        "installed": True,
        "location": str(target),
    }
