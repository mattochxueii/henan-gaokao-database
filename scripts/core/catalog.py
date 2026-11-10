"""Subject-aware, versioned views over the legacy archive and science additions."""

from contextlib import closing
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory

from analysis_db import fingerprint
from gaokao import dumps, read_json, read_lines, require
from local_archive import public_edition, read_bundle
from subjects import SCIENCES, SUBJECTS

DATA = Path("national/multisubject")
LOCAL = Path(".local-data/subject-imports")
HASH = re.compile(r"[0-9a-f]{64}\Z")


def catalog(root):
    doc = read_json(root / DATA / "catalog.json")
    require(doc["version"] == 1, "学科目录版本不符")
    return doc


def use(root, subject, region, year):
    items = [x for x in catalog(root)["exam_uses"] if
             (x["subject"], x["region"], x["year"]) == (subject, region, year)]
    if subject == "math" and not items:
        # Math keeps its existing provincial usages, tracks and series IDs.
        folder = root / "national/catalog/paper-regions.jsonl"
        if folder.is_file():
            items = [x for x in read_lines(folder) if
                     (x["subject"], x["region_id"], x["year"]) == ("math", region, year)
                     and x["usage_status"] != "candidate_requires_independent_source"]
        else:
            for p in read_lines(root / "national/source-catalog.jsonl"):
                if p["subject"] == "math" and p["year"] == year:
                    items.extend({**p, **u} for u in p["regions"]
                                 if u["region_id"] == region and
                                 u["usage_status"] != "candidate_requires_independent_source")
    require(items, "未登记该年度、地区和科目的用卷证据")
    return items


def import_science(root, bundle):
    """Admit locally owned copies with exact source, province and version bindings."""
    manifest, tables, rows = read_bundle(bundle, check_files=True)
    require(manifest["distribution"] == "local-only" and
            manifest["version_scheme"] == "normalized-question", "真题导入须为绑定题面版本的本地资料包")
    sources = {s["id"]: s for s in tables["sources"]}
    papers = {p["id"]: p for p in tables["papers"]}
    uses = tables["paper-regions"]
    require(papers and all(p["subject"] in SCIENCES for p in papers.values()), "本入口仅接收三门理科")
    for p in papers.values():
        matches = [m for m in uses if m["paper_id"] == p["id"]]
        require(len(matches)==1, "每份省级选择性考试卷须绑定一个有证据的地区")
        m = matches[0]
        require(m.get("subject") == p["subject"] and m.get("year") == p["year"] and
                m.get("region_id") == p.get("region_id") and
                m.get("exam_system_id") == p.get("exam_system_id") == "new-3+1+2",
                "试卷与学科、年份或制度映射冲突")
        match = next((e for e in use(root, p["subject"], m["region_id"], p["year"])
                      if e.get("paper_id")==p["id"] and e["series_id"]==p["series_id"]
                      and e["status"]=="historical_selective"), None)
        require(match and m.get("evidence"), "地区、年份与省级卷型不能从考试制度推断")
    for q in rows:
        source = sources[q["source_locator"]["source_id"]]
        require(source.get("rights") == "local_copy_authorized" and source.get("rights_basis"),
                "需记录该原文副本的合法取得与本地处理依据")
        require(type(q.get("content_complete")) is bool and q["content_complete"],
                "完整题面包缺少完整性证明")
        require(q["answer"] is not None and q["answer"] != "" and q["answer"] != {},
                "缺少已绑定的答案")
    dst = root / LOCAL / manifest["dataset_id"]
    require(not dst.exists(), "资料包 ID 已存在")
    conflicts = {(r["paper_id"],r["number"]) for r in all_science_rows(root) if r["record_type"]=="full_text"}
    require(not conflicts.intersection((r["paper_id"],r["number"]) for r in rows), "同卷题号已有本地原文")
    require(not any(Path(f["path"]).suffix.lower() in (".key",".env",".enc",".part")
                    for f in manifest["files"]), "资料包含敏感文件")
    dst.parent.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix=".intake-",dir=dst.parent) as folder:
        staging = Path(folder)/"data"
        shutil.copytree(bundle,staging)
        read_bundle(staging,check_files=True)
        staging.rename(dst)
    return {"installed":len(rows),"quarantined":sum(r.get("review_status")=="quarantined" for r in rows)}


def all_science_rows(root):
    path = root / DATA / "research-samples.json"
    rows = list(read_json(path)) if path.is_file() and not public_edition(root) else []
    for p in sorted((root / LOCAL).glob("*")):
        if not p.is_dir() or p.name.startswith("."):
            continue
        _, tables, questions = read_bundle(p)
        regions = {m["paper_id"]:m["region_id"] for m in tables["paper-regions"]}
        sources = {s["id"]:s for s in tables["sources"]}
        for q in questions:
            source = sources[q["source_locator"]["source_id"]]
            rows.append({
                **q, "region":regions[q["paper_id"]], "source_url":source.get("url"),
                "rights":source["rights"], "record_type":"full_text",
                "answer_version_sha256":q["version_sha256"],
                "review_status":"quarantined" if q.get("review_status")=="quarantined" else "local_unreviewed",
            })
    for row in rows:
        require(row["subject"] in SCIENCES and HASH.fullmatch(row["version_sha256"]), "题面版本或学科无效")
        if row.get("answer") is not None:
            require(row["answer_version_sha256"] == row["version_sha256"], "答案与题目版本不符")
    return rows


def query(root, subject, *, year=None, region=None, topic=None, limit=10, verified_only=False):
    require(subject in SUBJECTS and type(limit) is int and limit>0, "学科或数量无效")
    if subject == "math":
        from subjects.math import research
        return research(root, year=year, region=region, topic=topic, limit=limit, verified_only=verified_only)
    result = []
    for q in all_science_rows(root):
        if q["subject"] != subject or (year is not None and q["year"] != year) or (region and q["region"] != region):
            continue
        if q.get("review_status") == "quarantined" or verified_only and q.get("review_status") not in (
            "source_and_solution_reviewed", "independently_solved_summary",
        ):
            continue
        if topic and topic not in str(q.get("topic")):
            continue
        result.append(q)
    unique = {}
    for q in sorted(result, key=lambda q:q["record_type"]!="full_text"):
        unique.setdefault((q["year"],q["paper_id"],q["number"]),q)
    return [unique[k] for k in sorted(unique)][:limit]


def rebuild(root, output):
    """Materialize a disposable relational index without mutating the source archive."""
    from national_db import available as math_available, rows as math_archive
    require(not output.exists(), "索引路径已存在")
    output.parent.mkdir(parents=True,exist_ok=True)
    science = all_science_rows(root)
    from math_calibration import grade
    math_ready = math_available(root)
    math = [x for x in math_archive(root) if x["subject"]=="math"] if math_ready else []
    source_data = catalog(root)
    schema = """
CREATE TABLE subject(id TEXT PRIMARY KEY,label TEXT NOT NULL);
CREATE TABLE entity(kind TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id));
CREATE TABLE exam_use(subject TEXT REFERENCES subject(id), year INTEGER, region TEXT,
    series_id TEXT, paper_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(subject,year,region,paper_id));
CREATE TABLE question(id TEXT, master_id TEXT, paper_id TEXT, subject TEXT REFERENCES subject(id),
    year INTEGER, number INTEGER, version TEXT NOT NULL, state TEXT, payload TEXT NOT NULL, PRIMARY KEY(id,version));
CREATE TABLE answer(question_id TEXT, version TEXT, payload TEXT NOT NULL, PRIMARY KEY(question_id,version),
    FOREIGN KEY(question_id,version) REFERENCES question(id,version));
CREATE INDEX question_subject_year ON question(subject,year,paper_id,number);
"""
    entities = source_data["entities"]
    for folder in sorted((root / "experiments/phase13").glob("*")):
        candidate = folder / "candidates.json"
        receipt = folder / "publication.json"
        if not (candidate.is_file() and receipt.is_file()):
            continue
        doc, release = read_json(candidate), read_json(receipt)
        subject = doc["subject"]
        entities["GeneratedPaper"].append({"id":"phase13:"+subject,"subject":subject,**release})
        for q in doc["questions"]:
            entities["GeneratedQuestion"].append({
                "id":q["id"], "subject":subject, "version":fingerprint(q),
                "generated_paper_id":"phase13:"+subject, "topic":q["topic"],
            })
    math_targets = root/"forecast/targets.json"
    if math_targets.is_file():
        entities["ForecastTarget"].extend({**x,"subject":"math"} for x in read_json(math_targets)["targets"])
    for snapshot in sorted((root/"forecast/frozen").glob("*.json")):
        doc = read_json(snapshot)
        if "payload" in doc and fingerprint(doc["payload"])==doc.get("payload_sha256"):
            entities["Forecast"].append({"id":snapshot.stem,"subject":"math","payload":doc["payload"],
                                         "version":doc["payload_sha256"]})
    with closing(sqlite3.connect(output)) as db, db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(schema)
        db.executemany("INSERT INTO subject VALUES (?,?)", SUBJECTS.items())
        for kind, records in source_data["entities"].items():
            db.executemany("INSERT INTO entity VALUES (?,?,?)", [(kind, x["id"], dumps(x)) for x in records])
        for m in source_data["exam_uses"]:
            db.execute("INSERT INTO exam_use VALUES (?,?,?,?,?,?)",
                       (m["subject"],m["year"],m["region"],m["series_id"],m["paper_id"],dumps(m)))
        for name, kind in (("series","ExamSeries"),("regions","Region"),("systems","ExamSystem"),("curricula","Curriculum")):
            for row in read_lines(root/"national/catalog"/(name+".jsonl")):
                db.execute("INSERT OR IGNORE INTO entity VALUES (?,?,?)",(kind,row["id"],dumps(row)))
        math_series = {}
        math_papers = root/"national/catalog/papers.jsonl"
        for path in ([math_papers, root/"national/catalog/legacy-papers.jsonl"] if math_papers.is_file()
                     else [root/"national/source-catalog.jsonl"]):
            for row in read_lines(path):
                db.execute("INSERT OR IGNORE INTO entity VALUES (?,?,?)",("Paper",row["id"],dumps(row)))
                math_series[row["id"]] = row["series_id"]
                if path.name=="source-catalog.jsonl" and row["subject"]=="math":
                    for usage in row["regions"]:
                        db.execute("INSERT OR IGNORE INTO exam_use VALUES (?,?,?,?,?,?)",
                                   ("math",row["year"],usage["region_id"],row["series_id"],row["id"],dumps(usage)))
        paper_regions = root/"national/catalog/paper-regions.jsonl"
        if paper_regions.is_file():
            for row in read_lines(paper_regions):
                if row["subject"]=="math":
                    db.execute("INSERT OR IGNORE INTO exam_use VALUES (?,?,?,?,?,?)",
                               ("math",row["year"],row["region_id"],math_series.get(row["paper_id"]),row["paper_id"],dumps(row)))
        for q in [*math,*science]:
            identity = q.get("occurrence_id",q["id"])
            version = q["version_sha256"]
            status = grade(q) if q["subject"]=="math" else q["review_status"]
            db.execute("INSERT INTO question VALUES (?,?,?,?,?,?,?,?,?)",
                       (identity,q.get("question_id",q["id"]),q["paper_id"],q["subject"],q["year"],q["number"],
                        version,status,dumps({k:v for k,v in q.items() if k!="answer"})))
            if q.get("answer") is not None:
                db.execute("INSERT INTO answer VALUES (?,?,?)",(identity,version,dumps(q["answer"])))
            for key,kind in (("national_analysis","Analysis"),("calibration","Verification"),("verification","Verification")):
                if q.get(key):
                    db.execute("INSERT OR REPLACE INTO entity VALUES (?,?,?)",
                               (kind,identity,dumps({"subject":q["subject"],"version":version,"record":q[key]})))
        report = {"subjects":len(SUBJECTS),"math":len(math),"science":len(science),
                  "math_archive_available":math_ready,
                  "math_version_binding":fingerprint(sorted((q["occurrence_id"],q["version_sha256"]) for q in math))
                                         if math_ready else None,
                  "foreign_keys_valid":not list(db.execute("PRAGMA foreign_key_check"))}
        require(report["foreign_keys_valid"], "关系索引校验失败")
    return report
