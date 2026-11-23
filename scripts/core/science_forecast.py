"""Comparable province/series baselines, with descriptive small-sample trends."""

from collections import defaultdict
from datetime import date
from statistics import mean

from analysis_db import fingerprint
from core.catalog import HASH, use
from forecast_model import loss
from forecast_store import envelope
from gaokao import require
from subjects import SCIENCES

VERSION = "province-science-frequency-v2"
LEGACY_VERSION = "province-science-frequency-v1"
MIN_YEARS = 5


def evidence_rows(root, subject, region, series, document):
    require(subject in SCIENCES, "数学须使用既有冻结与回测入口")
    require((document["subject"],document["region"],document["series_id"]) == (subject,region,series),
            "预测证据的学科、地区或卷系不一致")
    targets = document["targets"]
    require(len(targets)==len(set(targets)) and all(t.startswith(subject+":") for t in targets),
            "预测目标须属于当前学科")
    indexed = {}
    for row in document["observations"]:
        year = row["year"]
        available = date.fromisoformat(row["available_on"])
        require(available.year >= year and row.get("review_state")=="independently_coded"
                and HASH.fullmatch(row["version_sha256"]) and row["source_url"].startswith("https://"),
                "观察须有时间证据、版本及独立标注")
        allowed = use(root,subject,region,year)
        require(any(x["status"]=="historical_selective" and x["paper_id"]==row["paper_id"]
                    and x["series_id"]==series for x in allowed), "观察并非本省该年同卷系")
        require(year not in indexed, "同一考试年份不能重复入样")
        require(set(row["values"])<=set(targets) and
                all(v is None or type(v) is int and v in (0,1) for v in row["values"].values()),
                "观察目标不符或取值无效")
        indexed[year] = {**row,"available":available}
    return targets,indexed


def estimate(targets, indexed, year, cutoff):
    results = []
    for target in targets:
        trend = [{"year":y,"value":r["values"][target]} for y,r in sorted(indexed.items())
                 if y<year and r["available"]<=cutoff and r["values"].get(target) is not None]
        values = [row["value"] for row in trend]
        supported = len(values)>=MIN_YEARS and len(set(values))==2
        small_sample = 0 < len(values) < MIN_YEARS
        status = ("exploratory_frequency" if supported else "small_sample_trend" if small_sample else
                  "descriptive_constant" if values else "abstained")
        results.append({"target":target,"p":(sum(values)+1)/(len(values)+2) if supported else None,
                        "n_years":len(values),"positive":sum(values),"observed_rate":mean(values) if values else None,
                        "observations":trend,"status":status,
                        "note":"小样本趋势参考，仅描述已知卷面，不用于概率计分" if small_sample else None})
    return results


def forecast(root, subject, region, year, cutoff, document=None):
    require(subject in SCIENCES, "数学预测沿用原入口")
    cutoff = date.fromisoformat(cutoff)
    require(cutoff.year<year, "预测证据截止日须早于目标考试年度")
    mapping = use(root,subject,region,year)
    require(len(mapping)==1 and mapping[0]["status"] in ("historical_selective","system_announced"),
            "预测需同地区同制度选择性考试")
    series = mapping[0]["series_id"]
    default = root / "national" / "multisubject" / f"{subject}-observations.json"
    if document is None and default.is_file():
        from gaokao import read_json

        stored = read_json(default)
        if (stored["subject"], stored["region"], stored["series_id"]) == (subject, region, series):
            document = stored
    document = document or {"subject":subject,"region":region,"series_id":series,"targets":[],"observations":[]}
    targets, indexed = evidence_rows(root,subject,region,series,document)
    probabilities = estimate(targets,indexed,year,cutoff)
    folds = []
    for y,row in sorted(indexed.items()):
        if y>=year or row["available"]>cutoff:
            continue
        p = estimate(targets,indexed,y,date(y-1,12,31))
        scores = [{"target":x["target"],"y":row["values"][x["target"]],"p":x["p"],
                   **loss(x["p"],row["values"][x["target"]])}
                  for x in p if x["p"] is not None and row["values"].get(x["target"]) is not None]
        folds.append({"year":y,"scores":scores})
    values = [s for f in folds for s in f["scores"]]
    return envelope({
        "model":VERSION,"subject":subject,"region":region,"year":year,"series_id":series,
        "as_of":cutoff.isoformat(),"historical_evidence_sha256":fingerprint(document),
        "eligible_years":sorted(y for y,r in indexed.items() if y<year and r["available"]<=cutoff),
        "status":("exploratory_only" if any(x["p"] is not None for x in probabilities) else
                  "small_sample_trend" if any(x["status"]=="small_sample_trend" for x in probabilities) else
                  "descriptive_constant" if any(x["observations"] for x in probabilities) else
                  "abstained_insufficient_evidence"),
        "minimum_independent_years":MIN_YEARS,"predictions":probabilities,"backtest":folds,
        "scored_cases":len(values),"brier":mean(x["brier"] for x in values) if values else None,
    })


def score(snapshot, outcome):
    payload = snapshot["payload"]
    require(snapshot["payload_sha256"]==fingerprint(payload) and payload["model"] in (VERSION, LEGACY_VERSION),
            "快照或模型版本不匹配")
    require(all(payload[k]==outcome[k] for k in ("subject","region","year","series_id")),
            "实测结果不能跨学科、地区或卷系")
    require(outcome.get("review_state")=="independently_coded" and
            HASH.fullmatch(outcome["version_sha256"]) and outcome["source_url"].startswith("https://"),
            "实测须有独立标注、来源及版本")
    released = date.fromisoformat(outcome["available_on"])
    require(released.year==payload["year"] and released<=date.today() and released>date.fromisoformat(payload["as_of"]),
            "实测须在目标考试后可用")
    scores = []
    for row in payload["predictions"]:
        value = outcome["values"].get(row["target"])
        if value is not None:
            require(type(value) is int and value in (0,1), "结果须为二值")
        if value is not None and row["p"] is not None:
            scores.append({"target":row["target"],"p":row["p"],"y":value,**loss(row["p"],value)})
    return {"snapshot_sha256":snapshot["payload_sha256"],"scores":scores,"n":len(scores)}
