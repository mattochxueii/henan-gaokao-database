"""National read model, legacy adapters, explicit relevance tiers and rebuildable SQLite."""

import json, sqlite3, os
import tempfile
from collections import Counter
from contextlib import closing
from pathlib import Path
from gaokao import read_json, read_lines, require, digest
from analysis_db import fingerprint
from national_quality import research_eligible
import local_archive
import math_calibration

ALIASES = {
    "新高考Ⅰ卷": "cn-new-gaokao-1",
    "新课标Ⅰ卷": "cn-new-gaokao-1",
    "新高考I卷": "cn-new-gaokao-1",
    "新高考Ⅱ卷": "cn-new-gaokao-2",
    "新课标Ⅱ卷": "cn-new-gaokao-2",
    "新高考II卷": "cn-new-gaokao-2",
    "全国乙卷": "cn-national-b",
    "旧全国Ⅰ卷": "cn-national-1-legacy",
    "浙江卷": "cn-zhejiang",
}


def settings(root):
    return read_json(root / "national/config.json")


def private_folder(root):
    path = (root / settings(root)["reference_dir"]).resolve()
    require(path.is_relative_to(root.resolve()), "资料目录越界")
    return path


def available(root):
    if local_archive.public_edition(root):
        return (root / "sample-data/manifest.json").is_file()
    return (root / "national/config.json").exists() and (
        private_folder(root) / "manifest.json"
    ).is_file()


def catalog(root, name):
    if local_archive.public_edition(root) and name in (
        "papers",
        "legacy-papers",
        "paper-regions",
        "sources",
    ):
        return local_archive.load(root)[name]
    return list(read_lines(root / settings(root)["catalog_dir"] / (name + ".jsonl")))


def legacy_rows(root):
    from analysis_db import research as legacy_research

    try:
        rows = legacy_research(root)
    except ValueError as e:
        if "尚未恢复" in str(e):
            return []
        raise
    result = []
    for r in rows:
        candidate = r["candidate"]
        result.append(
            {
                "id": r["id"],
                "question_id": r["id"],
                "occurrence_id": r["id"],
                "paper_id": r["id"].split(":")[0],
                "year": r["year"],
                "subject": "math",
                "series_id": "cn-new-gaokao-1",
                "track": "unified",
                "number": int(r["id"].split("q")[-1]),
                "kind": r["kind"],
                "points": r["points"],
                "stem": candidate["stem"],
                "options": candidate.get("options") or {},
                "formulas": candidate.get("formulas", []),
                "parts": candidate.get("subquestions", []),
                "asset_refs": candidate.get("assets", []),
                "reference_root": "legacy:database.json/reference_dir",
                "candidate": candidate,
                "analysis": r["analysis"],
                "curation": r["curation"],
                "answer": r["curation"].get("answer_for_current_candidate"),
                "source_locator": {
                    "source_id": candidate["source_id"],
                    "source_url": candidate["source_url"],
                    "page": candidate["page"],
                    "end_page": candidate["end_page"],
                    "source_files": candidate["source_files"],
                },
                "topic_flags": r["analysis"]["knowledge"].get("primary", []),
                "searchable_analysis": r["analysis"]["knowledge"],
                "version_sha256": fingerprint(candidate),
                "data_status": "既有完整候选；旧ID无损适配",
                "difficulty": None,
                "review_status": r["curation"],
                "legacy": True,
            }
        )
    return result


def rows(root, include_legacy=True, calibrated=True):
    if local_archive.public_edition(root):
        return local_archive.load(root)["rows"]
    require(
        available(root),
        "全国题面尚未恢复；运行national_cli.py restore --key <分离密钥>",
    )
    folder = private_folder(root)
    manifest = read_json(folder / "manifest.json")
    expected = {x["path"]: x["sha256"] for x in manifest["files"]}
    for name in ("questions.jsonl", "occurrences.jsonl", "answers.jsonl"):
        require(
            expected.get(name) == digest(folder / name),
            "结构化原文已改变，旧答案/分析不可沿用；须重新审核并建立新版本：" + name,
        )
    masters = {q["id"]: q for q in read_lines(folder / "questions.jsonl")}
    answers = {a["id"]: a for a in read_lines(folder / "answers.jsonl")}
    papers = {p["id"]: p for p in catalog(root, "papers")}
    result = []
    for occurrence in read_lines(folder / "occurrences.jsonl"):
        q = masters[occurrence["question_id"]]
        p = papers[occurrence["paper_id"]]
        result.append(
            {
                **q,
                **occurrence,
                "occurrence_id": occurrence["id"],
                "id": q["id"],
                "year": p["year"],
                "subject": p["subject"],
                "series_id": p["series_id"],
                "track": p["track"],
                "curriculum_id": p["curriculum_id"],
                "paper_title": p["reported_name"],
                "answer": answers[occurrence["answer_id"]],
                "legacy": False,
            }
        )
    if include_legacy:
        result += legacy_rows(root)
    annotations_path = root / "national/research/annotations.jsonl"
    annotations = (
        {r["occurrence_id"]: r for r in read_lines(annotations_path)}
        if annotations_path.exists()
        else {}
    )
    for r in result:
        a = annotations.get(r["occurrence_id"])
        if a and a["version_sha256"] == r["version_sha256"]:
            r["national_analysis"] = a
    return math_calibration.apply(root, result) if calibrated else result


def target(root, region="河南", year=2027, subject="math"):
    matches = [read_json(p) for p in (root / "national/targets").glob("*.json")]
    found = [
        p
        for p in matches
        if (p["region_id"], p["year"], p["subject"]) == (region, year, subject)
    ]
    require(
        len(found) == 1,
        "目标年度制度/详细规则未登记，不能用历史卷型代替；请先建立有来源的target",
    )
    return found[0]


def relevance(row, policy, kind=None, topic=None):
    y = policy["year"]
    same = row["series_id"] == policy["primary_series"]
    if row.get("record_origin") == "original_sample":
        tier = "project_original_example"
    elif same and row["year"] >= y - 2:
        tier = "current_used_series"
    elif same:
        tier = "same_series_history"
    elif row["series_id"] in ("cn-new-gaokao-1", "cn-new-gaokao-2"):
        tier = "comparable_new_series"
    else:
        tier = "legacy_or_specialty"
    score = policy["reference_tiers"].get(tier, 0) + max(0, 10 - abs(y - row["year"]))
    reasons = [tier, "年份接近度"]
    if row.get("curriculum_id") and row["curriculum_id"] != policy["curriculum_id"]:
        score -= 8
        reasons.append("课标不同或待核，降权")
    if kind:
        score += 5 if row["kind"] == kind else -5
        reasons.append("题型匹配")
    if topic:
        score += 5
        reasons.append("内容/已标注知识筛选")
    return {
        "tier": tier,
        "score": score,
        "reasons": reasons,
        "formula": "明确层级+年份+课程/题型；不使用同卷题数或网站数量",
    }


def query(
    root,
    year=None,
    year_from=None,
    year_to=None,
    region=None,
    subject="math",
    series=None,
    topic=None,
    kind=None,
    number=None,
    difficulty=None,
    method=None,
    capability=None,
    target_region=None,
    target_year=2027,
    limit=None,
    include_candidate_usage=False,
    include_quarantined=False,
    verified_only=False,
):
    require(limit is None or limit > 0, "limit须为正整数")
    require(
        year_from is None or year_to is None or year_from <= year_to, "年份范围倒置"
    )
    series = ALIASES.get(series, series)
    uses = catalog(root, "paper-regions")
    region_papers = {
        r["paper_id"]
        for r in uses
        if r["region_id"] == region
        and (
            include_candidate_usage
            or r["usage_status"] != "candidate_requires_independent_source"
        )
    }
    policy = (
        target(root, target_region, target_year, subject) if target_region else None
    )
    found = []
    for r in rows(root):
        grade = math_calibration.grade(r)
        if verified_only and grade != "source_and_solution_reviewed":
            continue
        if not include_quarantined and not research_eligible(r):
            continue
        if subject and r["subject"] != subject:
            continue
        if year is not None and r["year"] != year:
            continue
        if year_from is not None and r["year"] < year_from:
            continue
        if year_to is not None and r["year"] > year_to:
            continue
        if region and r["paper_id"] not in region_papers:
            continue
        if series and r["series_id"] != series:
            continue
        if kind and r["kind"] != kind:
            continue
        if number is not None and r["number"] != number:
            continue
        analysis = r.get("national_analysis", {})
        feature_flags = r.get("topic_flags", [])
        if topic == "导数":
            # The broad historical feature bucket includes elementary functions too.
            # It is not evidence that an unanalysed question tests differentiation.
            feature_flags = [v for v in feature_flags if v != "函数与导数"]
        if topic and topic not in json.dumps(
            [
                r["stem"],
                feature_flags,
                r.get("searchable_analysis"),
                analysis.get("knowledge"),
                r.get("deep_analysis", {}).get("knowledge"),
                r.get("calibration", {}).get("topic"),
            ],
            ensure_ascii=False,
        ):
            continue
        if (
            difficulty is not None
            and analysis.get("difficulty", {}).get("level") != difficulty
        ):
            continue
        deep = r.get("deep_analysis", {})
        if method and method not in json.dumps(
            [analysis.get("methods"), deep.get("methods")], ensure_ascii=False
        ):
            continue
        if capability and capability not in json.dumps(
            [analysis.get("competencies"), deep.get("competencies")], ensure_ascii=False
        ):
            continue
        r = {**r, "confidence": grade}
        if policy:
            r = {**r, "reference_relevance": relevance(r, policy, kind, topic)}
        found.append(r)
    if policy:
        found.sort(
            key=lambda r: (
                -{"source_and_solution_reviewed": 2, "source_reviewed": 1}.get(
                    r["confidence"], 0
                ),
                -r["reference_relevance"]["score"],
                -r["year"],
                r["paper_id"],
                r["number"],
            )
        )
    else:
        found.sort(key=lambda r: (r["year"], r["paper_id"], r["number"]))
    return found[:limit] if limit is not None else found


def validate(root):
    if local_archive.public_edition(root):
        data = local_archive.load(root, check_files=True)
        return {
            "valid": True,
            "edition": "public",
            "datasets": data["dataset_ids"],
            "paper_count": len(data["papers"]),
            "question_occurrences": len(data["rows"]),
            "answers_version_bound": True,
        }
    folder = private_folder(root)
    manifest = read_json(folder / "manifest.json")
    errors = []
    for f in manifest["files"]:
        p = (folder / f["path"]).resolve()
        if not p.is_relative_to(folder) or not p.is_file() or digest(p) != f["sha256"]:
            errors.append("文件缺失或变化：" + f["path"])
    occurrences = list(read_lines(folder / "occurrences.jsonl"))
    from national_schema import validate_paper

    for paper in catalog(root, "papers"):
        validate_paper(paper)
        group = [o for o in occurrences if o["paper_id"] == paper["id"]]
        if sorted(o["number"] for o in group) != list(
            range(1, paper["question_count"] + 1)
        ):
            errors.append("题数或题号不完整：" + paper["id"])
        total = sum(o["points"] for o in group)
        if paper.get("optional_policy"):
            total -= 10
        if total != paper["max_score"]:
            errors.append("原卷分值不匹配：" + paper["id"])

    answers = {a["id"]: a for a in read_lines(folder / "answers.jsonl")}
    masters = {q["id"]: q for q in read_lines(folder / "questions.jsonl")}
    for o in occurrences:
        if o["question_id"] not in masters:
            errors.append("悬空主题：" + o["id"])
            continue
        a = answers[o["answer_id"]]
        if a["question_version_sha256"] != o["version_sha256"]:
            errors.append("答案版本错配：" + o["id"])
        for asset in masters[o["question_id"]]["asset_refs"] + a["asset_refs"]:
            if digest(folder / asset["path"]) != asset["sha256"]:
                errors.append("题图变化：" + o["id"])
        if any(
            x in masters[o["question_id"]]["stem"]
            for x in (r"\begin{answer}", r"\begin{solution}", r"\solution{")
        ):
            errors.append("答案泄露：" + o["id"])
    require(len({o["id"] for o in occurrences}) == len(occurrences), "题目实例ID重复")
    uses = catalog(root, "paper-regions")
    require(
        len({(u["paper_id"], u["region_id"], u["year"], u["subject"]) for u in uses})
        == len(uses),
        "用卷关系重复",
    )
    require(not errors, str(errors[:10]))
    return {
        "valid": True,
        "new_papers": len(catalog(root, "papers")),
        "new_occurrences": len(occurrences),
        "new_unique_questions": len(masters),
        "legacy_38_preserved": len(legacy_rows(root)) == 38,
        "verified_file_count": len(manifest["files"]),
        "answers_version_bound": True,
        "human_verified": False,
    }


def statistics(root):
    data = rows(root)
    out = []
    for paper in [*catalog(root, "papers"), *catalog(root, "legacy-papers")]:
        group = [r for r in data if r["paper_id"] == paper["id"]]
        if not group:
            continue
        out.append(
            {
                "year": paper["year"],
                "series_id": paper["series_id"],
                "paper_id": paper["id"],
                "record_origin": paper.get("record_origin", "historical_candidate"),
                "track": paper.get("track"),
                "question_occurrences": len(group),
                "full_candidate_stems": sum(bool(r["stem"]) for r in group),
                "research_eligible_candidates": sum(
                    research_eligible(r) for r in group
                ),
                "quarantined_candidates": sum(not research_eligible(r) for r in group),
                "answers_present": sum(
                    bool(r["answer"])
                    and (
                        r["legacy"]
                        or bool(
                            r["answer"].get("reference_answer")
                            or r["answer"].get("explanation")
                        )
                    )
                    for r in group
                ),
                "scoring_complete": paper.get("scoring_complete", True),
                "official_originals": 0,
                "human_verified": 0,
            }
        )
    return {
        "papers": out,
        "paper_count": len(out),
        "question_occurrences": len(data),
        "unique_questions": len({r["id"] for r in data}),
        "original_sample_occurrences": sum(
            r.get("record_origin") == "original_sample" for r in data
        ),
        "new_data_only": False,
        "links_counted_as_questions": False,
        "all_complete_are_candidates_not_official_originals": not any(
            r.get("record_origin") == "original_sample" for r in data
        ),
    }


def rebuild_index(root, snapshot=None):
    cfg = settings(root)
    if snapshot is None and local_archive.public_edition(root):
        snapshot = local_archive.load(root)
    path = root / cfg["index"]
    path.parent.mkdir(exist_ok=True, parents=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, suffix=".sqlite", delete=False
    ) as file:
        tmp = Path(file.name)
    connection = sqlite3.connect(tmp)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
        CREATE TABLE paper(id TEXT PRIMARY KEY,year INTEGER,subject TEXT,series_id TEXT,track TEXT,payload TEXT);
        CREATE TABLE question(id TEXT PRIMARY KEY,stem TEXT,payload TEXT);
        CREATE TABLE occurrence(id TEXT PRIMARY KEY,question_id TEXT REFERENCES question(id),paper_id TEXT REFERENCES paper(id),number INTEGER,kind TEXT,points REAL,version_sha256 TEXT,answer TEXT,payload TEXT);
        CREATE TABLE paper_region(paper_id TEXT REFERENCES paper(id),region_id TEXT,year INTEGER,status TEXT,PRIMARY KEY(paper_id,region_id));
        CREATE INDEX paper_filter ON paper(year,subject,series_id,track);
        CREATE INDEX occurrence_number ON occurrence(paper_id,number);
        CREATE TABLE index_state(version TEXT);
        """)
        revision = (
            snapshot["revision"]
            if snapshot is not None
            else _calibration_revision(root)
        )
        if revision is not None:
            connection.execute("INSERT INTO index_state VALUES (?)", (revision,))
        papers = (
            snapshot["papers"]
            if snapshot is not None
            else [*catalog(root, "papers"), *catalog(root, "legacy-papers")]
        )
        for p in papers:
            connection.execute(
                "INSERT INTO paper VALUES(?,?,?,?,?,?)",
                (
                    p["id"],
                    p["year"],
                    p["subject"],
                    p["series_id"],
                    p.get("track"),
                    json.dumps(p, ensure_ascii=False),
                ),
            )
        seen = set()
        for r in snapshot["rows"] if snapshot is not None else rows(root):
            if r["id"] not in seen:
                connection.execute(
                    "INSERT INTO question VALUES(?,?,?)",
                    (r["id"], r["stem"], json.dumps(r, ensure_ascii=False)),
                )
                seen.add(r["id"])
            connection.execute(
                "INSERT INTO occurrence VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    r["occurrence_id"],
                    r["id"],
                    r["paper_id"],
                    r["number"],
                    r["kind"],
                    r["points"],
                    r["version_sha256"],
                    json.dumps(r["answer"], ensure_ascii=False),
                    json.dumps(r, ensure_ascii=False),
                ),
            )
        for u in (
            snapshot["paper-regions"]
            if snapshot is not None
            else catalog(root, "paper-regions")
        ):
            connection.execute(
                "INSERT INTO paper_region VALUES(?,?,?,?)",
                (u["paper_id"], u["region_id"], u["year"], u["usage_status"]),
            )
        connection.commit()
    except BaseException:
        connection.close()
        tmp.unlink(missing_ok=True)
        raise
    finally:
        connection.close()
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return {"index": cfg["index"], "rebuildable": True, "questions": len(seen)}


def sqlite_query(root, year, series, number):
    path = root / settings(root)["index"]
    if local_archive.public_edition(root):
        snapshot = local_archive.load(root)
        if not _index_has_revision(path, snapshot["revision"]):
            rebuild_index(root, snapshot)
    elif (revision := _calibration_revision(root)) is not None:
        if not _index_has_revision(path, revision):
            rebuild_index(root)
    require(path.is_file(), "请先build-index")
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        result = db.execute(
            "SELECT p.id paper_id,p.year,o.number,o.question_id,q.stem,o.payload,o.answer FROM paper p JOIN occurrence o ON o.paper_id=p.id JOIN question q ON q.id=o.question_id WHERE p.year=? AND p.series_id=? AND o.number=?",
            (year, ALIASES.get(series, series), number),
        ).fetchall()
        return [
            {
                **json.loads(r["payload"]),
                "paper_id": r["paper_id"],
                "year": r["year"],
                "number": r["number"],
                "question_id": r["question_id"],
                "answer": json.loads(r["answer"]),
            }
            for r in result
        ]


def _calibration_revision(root):
    ledger = root / math_calibration.LEDGER
    if ledger.is_file():
        return fingerprint(
            {
                "calibration": digest(ledger),
                "source": digest(private_folder(root) / "manifest.json"),
            }
        )
    return None


def _index_has_revision(path, revision):
    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(path)) as db:
            return db.execute("SELECT version FROM index_state").fetchone() == (
                revision,
            )
    except sqlite3.DatabaseError:
        return False


def reference_pack(
    root,
    topic=None,
    kind=None,
    target_region="河南",
    target_year=2027,
    limit=12,
    verified_only=False,
    allowed_ids=None,
):
    """Bound actual full-text retrieval by paper, not manifest or popularity."""
    require(limit > 0, "limit须为正整数")
    policy = target(root, target_region, target_year)
    found = query(
        root,
        topic=topic,
        kind=kind,
        target_region=target_region,
        target_year=target_year,
        verified_only=verified_only,
    )
    counts = Counter()
    selected = []
    seen_questions = set()
    for row in found:
        if allowed_ids is not None and row["occurrence_id"] not in allowed_ids:
            continue
        if row.get("curation", {}).get("body_state") == "存在版本冲突":
            continue
        if counts[row["paper_id"]] >= policy["per_paper_reference_cap"]:
            continue
        question_id = row.get("calibration", {}).get("equivalence_id") or row.get(
            "question_id", row["occurrence_id"]
        )
        if question_id in seen_questions:
            continue
        seen_questions.add(question_id)
        counts[row["paper_id"]] += 1
        selected.append(row)
        if len(selected) >= limit:
            break
    return {
        "target": policy,
        "references": selected,
        "read_full_content": True,
        "per_paper_cap": policy["per_paper_reference_cap"],
        "quarantined_excluded": True,
        "known_disputed_versions_excluded": True,
        "verified_only": verified_only,
        "one_reference_per_question_master": True,
        "limits": "第三方候选与AI分析；不等于命题机构认证。课标待核样本降权。",
        "version_sha256": fingerprint(
            [(r["occurrence_id"], r["version_sha256"]) for r in selected]
        ),
    }


def planning_references(
    root, topics=("数列", "导数", "解析几何"), max_chars=12000,
    *, verified_only=False, allowed_ids=None,
):
    """Whole student-facing questions only; do not truncate formulae to fit a prompt."""
    result = {}
    used = 0
    for topic in topics:
        pack = reference_pack(
            root, topic=topic, limit=12, verified_only=verified_only,
            allowed_ids=allowed_ids,
        )
        selected = []
        # Split the budget between topics. The full research CLI remains unrestricted.
        budget = max_chars // len(topics)
        topic_used = 0
        for r in pack["references"]:
            item = {
                k: r[k]
                for k in (
                    "occurrence_id",
                    "question_id",
                    "paper_id",
                    "year",
                    "series_id",
                    "number",
                    "kind",
                    "stem",
                    "options",
                    "parts",
                    "version_sha256",
                )
            }
            item["source_locator"] = r["source_locator"]
            item["reference_relevance"] = r["reference_relevance"]
            item["candidate_not_official"] = True
            item["confidence"] = r["confidence"]
            if r.get("deep_analysis"):
                item["design_evidence"] = {
                    field: r["deep_analysis"][field]
                    for field in (
                        "condition_design",
                        "breakthrough",
                        "progression",
                        "design_value",
                    )
                }
            item["version_notice"] = {
                "body_state": r.get("curation", {}).get(
                    "body_state", r.get("data_status")
                ),
                "answer_status": r.get("curation", {}).get(
                    "answer_status", "第三方答案未独立确认"
                ),
                "issues": r.get("issues", []),
            }
            size = len(json.dumps(item, ensure_ascii=False))
            if size + topic_used > budget:
                continue
            selected.append(item)
            topic_used += size
        used += topic_used
        result[topic] = {
            "references": selected,
            "per_paper_cap": pack["per_paper_cap"],
            "read_full_content": True,
            "answer_text_excluded": True,
            "budget_chars": budget,
            "selection_scope": "完整题面及来源；超过预算的整题跳过，不截断公式",
        }
    return result
