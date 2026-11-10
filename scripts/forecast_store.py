"""Local SQLite materialisation and immutable file snapshots for forecast studies."""

from datetime import date
from contextlib import closing
import sqlite3
from analysis_db import fingerprint
from gaokao import digest, dumps, read_json, read_lines, require

SCHEMA = """
CREATE TABLE evidence(id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL,
                      available_on TEXT, payload TEXT NOT NULL);
CREATE TABLE curriculum_topic(id TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE curriculum_weight(evidence_id TEXT NOT NULL REFERENCES evidence(id),
                               topic TEXT NOT NULL REFERENCES curriculum_topic(id),
                               stage TEXT NOT NULL, hours INTEGER NOT NULL CHECK(hours>0),
                               PRIMARY KEY(evidence_id,topic,stage));
CREATE VIEW policy_document AS SELECT * FROM evidence WHERE kind='PolicyDocument';
CREATE VIEW assessment_requirement AS SELECT * FROM evidence WHERE kind='AssessmentRequirement';
CREATE VIEW official_review AS SELECT * FROM evidence WHERE kind='OfficialReview';
CREATE VIEW teaching_trend AS SELECT * FROM evidence WHERE kind='TeachingTrend';
CREATE TABLE forecast_target(id TEXT PRIMARY KEY, layer TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE exam_feature(occurrence_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL, version_sha256 TEXT NOT NULL,
                          available_on TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE feature_observation(paper_id TEXT NOT NULL, target_id TEXT NOT NULL REFERENCES forecast_target(id),
                                 available_on TEXT NOT NULL, vintage TEXT NOT NULL, value INTEGER,
                                 evidence_id TEXT REFERENCES evidence(id),
                                 PRIMARY KEY(paper_id,target_id,vintage));
CREATE TABLE forecast(snapshot_sha256 TEXT PRIMARY KEY, target_year INTEGER NOT NULL,
                      as_of TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE backtest(run_sha256 TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE INDEX feature_by_paper ON exam_feature(paper_id);
CREATE INDEX observation_as_of ON feature_observation(available_on,target_id);
"""


def inputs(root):
    folder = root / "forecast"
    spec = read_json(folder / "targets.json")
    evidence = list(read_lines(folder / "evidence.jsonl"))
    required = {"CurriculumWeight", "CurriculumTopic", "OfficialReview", "AssessmentRequirement",
                "PolicyDocument", "TeachingTrend"}
    ids = [e["id"] for e in evidence]
    require(len(ids) == len(set(ids)), "证据编号重复")
    for e in evidence:
        require(e["type"] in required and e["subject"] == "math"
                and e["url"].startswith("https://") and e["facts"] and e["usage"], "证据缺少来源与范围")
        available = e["available_on"]
        if available:
            date.fromisoformat(available)
        if e["published_on"]:
            require(available and date.fromisoformat(e["published_on"]) <= date.fromisoformat(available),
                    "证据可用时间早于发布")
    entries = list(read_lines(folder / "contemporaneous.jsonl"))
    return spec, evidence, entries


def paper_catalog(root):
    from national_db import catalog

    result = list(catalog(root, "papers"))
    for p in catalog(root, "legacy-papers"):
        if p.get("series_id"):
            meta = read_json(root / p["legacy_path"])
            result.append({**p, "max_score": meta["max_points"]})
    return result


def model_files(root):
    return {name: digest(root / "scripts" / name)
            for name in ("forecast_model.py", "forecast_features.py", "forecast_store.py", "forecast_research.py")}


def envelope(payload):
    return {"payload": payload, "payload_sha256": fingerprint(payload)}


def frozen(path):
    obj = read_json(path)
    require(obj["payload_sha256"] == fingerprint(obj["payload"]), "冻结预测完整性校验失败")
    return obj


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), "已存在的研究版本不可覆盖，请使用新版本")
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(dumps(value) + "\n")


def materialize(path, spec, evidence, features, dated, archive, prediction=None, backtest=None):
    require(not path.exists(), "SQLite 为可重建研究快照，请使用新路径")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb"):
        pass
    try:
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA foreign_keys = ON")
            db.executescript(SCHEMA)
            db.executemany("INSERT INTO evidence VALUES(?,?,?,?,?)", [
                (e["id"],e["type"],e["subject"],e["available_on"],dumps(e)) for e in evidence
            ])
            topic = {**spec["topics"],"modeling":"建模与探究活动","flex":"机动"}
            db.executemany("INSERT INTO curriculum_topic VALUES(?,?)", topic.items())
            db.executemany("INSERT INTO curriculum_weight VALUES(?,?,?,?)", [
                (e["id"],k,stage,value)
                for e in evidence for stage, values in e["variables"].get("hours", {}).items()
                for k,value in values.items()
            ])
            db.executemany("INSERT INTO forecast_target VALUES(?,?,?)", [
                (r["id"],r["layer"],dumps(r)) for r in spec["targets"]
            ])
            db.executemany("INSERT INTO exam_feature VALUES(?,?,?,?,?)", [
                (r["occurrence_id"],r["paper_id"],r["version_sha256"],r["available_on"],dumps(r))
                for r in features
            ])
            for vintage, dataset in (("contemporaneous", dated), ("version_bound_2026", archive)):
                db.executemany("INSERT INTO feature_observation VALUES(?,?,?,?,?,?)", [
                    (r["paper_id"],k,r["available_on"],vintage,v,next(iter(r.get("evidence", [])),None))
                    for r in dataset for k,v in r["events"].items()
                ])
            if prediction:
                payload = prediction["payload"]
                db.execute("INSERT INTO forecast VALUES(?,?,?,?)", (
                    prediction["payload_sha256"],payload["target_year"],payload["as_of"],dumps(prediction)
                ))
            if backtest:
                db.execute("INSERT INTO backtest VALUES(?,?)",(fingerprint(backtest),dumps(backtest)))
            tables = ["evidence","curriculum_topic","curriculum_weight","forecast_target","exam_feature",
                      "feature_observation","forecast","backtest"]
            require(db.execute("PRAGMA integrity_check").fetchone()[0]=="ok", "研究数据库完整性异常")
            return {name: db.execute("SELECT COUNT(*) FROM " + name).fetchone()[0] for name in tables}
    except Exception:
        path.unlink(missing_ok=True)
        raise
