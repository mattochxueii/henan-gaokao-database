"""Build answer-free, version-bound labels and preserve blind disagreements."""

from collections import Counter, defaultdict
from pathlib import Path
import re
from analysis_db import fingerprint
from forecast_features import CORE, group_ids
from forecast_store import paper_catalog, write_new
from gaokao import ROOT, digest, read_json, require

SOURCE_REVIEWED = "source_and_solution_reviewed"
FUNCTION = r"函数|数列|前.{0,14}项和|通项"
SOLID = r"棱锥|棱柱|正方体|空间|二面角|底面"
CONIC = r"圆锥曲线|双曲线|抛物线|椭圆"
PROOF = r"证明|求证|证(?=\s*[：:\\])"
DEPENDENCE = r"(?:利用|根据|由|依据|结合|说明).{0,20}(?:前(?:一|二)?问|上一问|[（(]\s*(?:[123一二三]|i{1,3}|[ⅰⅱⅲ])\s*[）)](?:的|问|中)?\s*(?:结论|结果|条件)|上述(?:结论|结果))"
SCOPES = ("single_choice", "multiple_choice", "fill_in", "constructed_response")
TARGETED = {
    (2022,"I"): (4,20), (2022,"II"): (3,19),
    (2023,"I"): (17,20,22), (2023,"II"): (15,19,22),
    (2024,"I"): (8,17,18,19), (2024,"II"): (6,15,18,19),
    (2025,"I"): (6,16,17,18), (2025,"II"): (16,18,19),
    (2026,"I"): (7,16,17,19), (2026,"II"): (14,15,17,19),
}


def in_scope(target, kind):
    return (target["scope"] == "all" or
            target["scope"] == "constructed" and kind == "constructed_response" or
            target["scope"] == "objective" and kind in SCOPES[:3])


def cue(pattern, text):
    return bool(re.search(pattern, text, re.I))


def proxy(row, targets):
    """Literal cues, with conservatively scoped trial proxies. No answer or existing labels."""
    stem = row["stem"]
    parts = " ".join(p["text"] if isinstance(p, dict) else p for p in row["parts"])
    premise = stem.split("（子项）", 1)[0]
    text = stem + " " + parts
    recurrence = re.findall(r"([a-z])_\{?n[+-]\d+\}?", premise)
    function_task = cue(FUNCTION, premise) and not cue(SOLID + "|" + CONIC, premise)
    recurs = cue(r"求.{0,12}递推(?:式|关系)|递推公式", text) or (
        cue(r"数列", premise) and any(re.search(rf"{s}_(?:\{{n\}}|n(?![A-Za-z0-9]))", premise) for s in recurrence)
        and cue(r"=|等于", premise)
    )
    calls = {
        "module.functions_anchor": function_task,
        "structure.sequence_recurrence": recurs,
        "method.explicit_proof": cue(PROOF, text),
        "method.explicit_dependence": cue(DEPENDENCE, text),
        "structure.derivative_parameter": cue(r"函数", premise) and cue(r"单调|恒成立|不等式|零点", text)
            and cue(r"(?:[amk]\s*的取值范围|参数|讨论.{0,45}单调)", text),
        "structure.conic_dynamic": cue(CONIC, premise) and cue(r"轨迹|定值|定点|恒|存在", text)
            and cue(r"动点|任意|斜率|相交|交于|弦|切于|相切", text),
        "structure.conditional_decision": cue(r"条件概率|\\mid|患病率|漏诊率|误诊率", text)
            and cue(r"概率|估计|风险", text),
        "structure.solid_existence": cue(SOLID, premise) and cue(r"是否存在|证明.{0,15}存在", text),
        "method.necessity_sufficiency": cue(r"(?:证明|求证).{0,100}(?:充要条件|当且仅当)", text),
        "method.choice_cases": cue(r"分类|分情况|分段|奇数.{0,60}偶数", text),
        "method.real_model": cue(r"工程|建筑|竞赛|患病|比赛|工厂|公司|温度|生产|测量|监测|试验|飞船|风速|购票|调查|收获|育苗|种植|古塔|青铜峡|航行|传感器", text),
        "method.transfer_prompt": cue(r"称.{0,80}为|定义.{0,80}为|记.{0,80}为.{0,20}序列", premise),
    }
    return {t["id"]: int(calls[t["id"]]) if in_scope(t, row["kind"]) else None for t in targets}


def question_rows(root, protocol):
    from math_calibration import grade
    from national_db import rows

    papers = {p["id"]: p for p in paper_catalog(root)
              if p["series_id"] in CORE and p["year"] in protocol["archive_years"]}
    groups = defaultdict(list)
    for q in rows(root):
        if q["paper_id"] in papers:
            groups[q["paper_id"]].append(q)
    records = []
    for pid, paper in sorted(papers.items()):
        year, series = paper["year"], CORE[paper["series_id"]]
        yy = year - min(protocol["archive_years"])
        ss = protocol["series"].index(series)
        paper_rows = sorted(groups[pid], key=lambda q: q["number"])
        numbers = [q["number"] for q in paper_rows]
        require(numbers == list(range(1, paper["question_count"] + 1)), "历史题号或全卷覆盖异常")
        selected = set()
        for kind in SCOPES:
            positions = [q["number"] for q in paper_rows if q["kind"] == kind]
            if positions:
                selected.add(positions[((2 if kind == "constructed_response" else 1)*yy + ss) % len(positions)])
        for q in paper_rows:
            item = {k: q.get(k) for k in (
                "occurrence_id","paper_id","version_sha256","kind","stem","parts","options",
                "content_sha256","question_id","asset_refs","number",
            )}
            item.update(year=year, series=series, grade=grade(q),
                        equivalence_id=(q.get("calibration") or {}).get("equivalence_id"),
                        strata=[s for s, ids in (
                            ("systematic", selected), ("targeted", TARGETED.get((year, series), ()))
                        ) if q["number"] in ids])
            records.append(item)
    return records


def compare_pairs(pairs):
    usable = [(a,b) for a,b in pairs if a is not None and b is not None]
    n = len(usable)
    matrix = Counter(f"{a}{b}" for a,b in usable)
    a_positive = sum(a for a,_ in usable)
    b_positive = sum(b for _,b in usable)
    observed = sum(a == b for a,b in usable) / n if n else None
    expected = ((a_positive*b_positive+(n-a_positive)*(n-b_positive))/n**2) if n else None
    kappa = (observed-expected)/(1-expected) if expected is not None and expected < 1 else None
    return {
        "comparable": n, "excluded_null": len(pairs)-n,
        "review_positive": b_positive, "review_negative": n-b_positive,
        "proxy_positive": a_positive, "proxy_negative": n-a_positive,
        "agreement": observed, "cohen_kappa": kappa,
        "matrix": {k: matrix[k] for k in ("00","01","10","11")},
        "repeatable_for_exploration": 0 < b_positive < n and kappa is not None and kappa >= 0.6,
    }


def archive_and_audit(root, review, decisions):
    base = root / "forecast/validation"
    protocol = read_json(base / "protocol.json")
    sources = read_json(base / "paper-dates.json")
    targets = protocol["targets"][1:]
    records = question_rows(root, protocol)
    by_id = {r["occurrence_id"]: r for r in records}
    known_targets = {t["id"] for t in targets}
    codes = {qid: proxy(r, targets) for qid,r in by_id.items()}
    expected = {qid for qid,r in by_id.items() if r["strata"] and r["stem"]}
    reviewers = review["records"]
    seen = {r["occurrence_id"] for r in reviewers}
    require(seen == expected and len(seen) == len(reviewers), "独立复标缺题、重复或抽样范围错误")
    require(review["labels_produced_on"] >= protocol["locked_on"], "独立复标日期早于锁定协议")
    judgements = {}
    stats = defaultdict(lambda: defaultdict(list))
    disagreements = []
    for item in reviewers:
        qid = item["occurrence_id"]
        r = by_id[qid]
        require(item["version_sha256"] == r["version_sha256"] and set(item["labels"]) == known_targets,
                "独立复标版本或目标不一致")
        for key, b in item["labels"].items():
            require(b is None or type(b) is int and b in (0,1), "复标值必须为0、1或未知")
            if b == 1:
                require(item["evidence"].get(key), "正例复标缺少题面依据")
            a = codes[qid][key]
            if r["grade"] == SOURCE_REVIEWED:
                for stratum in r["strata"]:
                    stats[stratum][key].append((a,b))
            if a != b:
                disagreements.append({
                    "occurrence_id": qid, "version_sha256": r["version_sha256"], "target": key,
                    "proxy": a, "blind_review": b, "review_reason": item["evidence"].get(key),
                    "grade": r["grade"], "strata": r["strata"],
                })
            judgements[qid,key] = b

    # Only explicitly adjudicated findings change baseline codes. Unresolved
    # mismatches for primary replay labels remain unknown, even if the proxy was binary.
    overrides = {}
    for d in decisions["records"]:
        qid, key = d["occurrence_id"], d["target"]
        require((qid,key) not in overrides and d["version_sha256"] == by_id[qid]["version_sha256"]
                and key in known_targets and d["reason"]
                and (d["value"] is None or type(d["value"]) is int and d["value"] in (0,1)),
                "裁决缺少唯一题面版本、依据或合法标签")
        overrides[qid,key] = d
    for diff in disagreements:
        pair = diff["occurrence_id"], diff["target"]
        diff["resolution"] = overrides.get(pair, {}).get("value")
        diff["resolution_reason"] = overrides.get(pair, {}).get(
            "reason", "仍有分歧，回放适用项保留未知；试验标签不进入回放。")
    groups = group_ids(records)
    by_paper = defaultdict(list)
    for r in records:
        by_paper[r["paper_id"]].append(r)
    source_by = {(x["year"],x["series"]):x for x in sources["records"]}
    require(len(source_by)==len(sources["records"]), "同卷日期证据重复")
    observations = []
    for pid, rr in by_paper.items():
        year, series = rr[0]["year"], rr[0]["series"]
        source = source_by.get((year,series), {})
        events, anchors, coverage = {}, {}, {}
        for target in targets:
            key = target["id"]
            if target["disposition"] != "replay":
                continue
            votes = {}
            for r in rr:
                if not in_scope(target, r["kind"]):
                    continue
                qid = r["occurrence_id"]
                pair = qid, key
                code = codes[qid][key]
                votes[qid] = None if r["grade"] != SOURCE_REVIEWED else (
                    overrides[pair]["value"] if pair in overrides else
                    None if pair in judgements and judgements[pair] != code else code
                )
            anchors[key] = [{"occurrence_id": qid, "version_sha256": by_id[qid]["version_sha256"]}
                            for qid, value in votes.items() if value == 1]
            coverage[key] = {"scoped": len(votes), "unknown": sum(v is None for v in votes.values())}
            events[key] = (1 if 1 in votes.values() else 0 if votes and None not in votes.values() else None)
            if not source.get("raw_available_on"):
                events[key] = None
        observations.append({
            "paper_id": pid, "year": year, "series": series, "raw_available_on": source.get("raw_available_on"),
            "dated_source": source.get("url"), "label_protocol": protocol["version"],
            "labels_produced_on": review["labels_produced_on"],
            "paper_version_sha256": fingerprint([(r["occurrence_id"],r["version_sha256"]) for r in rr]),
            "question_groups": sorted({groups[r["occurrence_id"]] for r in rr}),
            "events": events, "anchors": anchors, "coverage": coverage,
        })
    archive = {
        "protocol_sha256": digest(base/"protocol.json"), "dates_sha256": digest(base/"paper-dates.json"),
        "blind_review_sha256": fingerprint(review), "adjudications_sha256": fingerprint(decisions),
        "observations": sorted(observations,key=lambda r:(r["year"],r["series"])),
    }
    return archive, {
        "blind_count": len(reviewers),
        "strict_blind_count": sum(by_id[q]["grade"] == SOURCE_REVIEWED for q in seen),
        "previously_reviewed_same_version_overlap": review.get("prior_overlap"),
        "counts_by_stratum": dict(Counter(s for q in seen for s in by_id[q]["strata"])),
        "agreement": {stratum: {k: compare_pairs(v) for k,v in fields.items()} for stratum, fields in stats.items()},
        "disagreements": disagreements,
        "adjudications": decisions,
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--review",type=Path,required=True)
    parser.add_argument("--decisions",type=Path,required=True)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--audit",type=Path,required=True)
    args = parser.parse_args(argv)
    archive, audit = archive_and_audit(args.root,read_json(args.review),read_json(args.decisions))
    write_new(args.archive,archive)
    write_new(args.audit,audit)


if __name__ == "__main__":
    main()
