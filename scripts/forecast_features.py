"""Project verified question versions into a dated, uncertainty-aware label ledger."""

from collections import Counter, defaultdict
import re
from analysis_db import fingerprint
from gaokao import require

VERSION = "math-features-v1"
CORE = {"cn-new-gaokao-1": "I", "cn-new-gaokao-2": "II"}
MODULES = {
    "foundations": r"集合|交集|并集|补集|子集|量词|充分条件|必要条件|命题|一元二次不等式|基本不等式|\\cap|\\cup",
    "functions": r"函数|导数|数列|通项|前.{0,12}项和|单调|周期|极值|正弦|余弦|\\(?:sin|cos|tan|ln|log)\b|递推",
    "geometry": r"复数|虚部|虚数|共轭|实部|向量|椭圆|双曲线|抛物线|曲线|焦点|斜率|棱锥|棱柱|二面角|球面|正方体|圆锥|直线与圆|垂直|平行|离心率|\\overrightarrow",
    "probability": r"概率|随机|抽样|分布|数据|统计|回归|中位数|众数|方差|频率|频数|期望|计数|排列|组合|二项式|列联表|频率直方图",
}
METHODS = {
    "classification": r"分类|分情况|分段|讨论",
    "substitution": r"换元|代换|引入辅助",
    "symmetry": r"对称|奇偶性|反射",
    "deduction": r"反证|推理|充要|必要性|充分性",
    "algebra_geometry": r"数形结合|坐标化|几何化|几何意义",
    "recursion": r"递推|递归|归纳",
    "optimization": r"最值|极值|上界|下界|不等式",
}
CONTEXT = r"企业|工厂|车间|患者|疾病|比赛|运动员|生产|产品|调查|学校|学生|交通|铁路|疫情|工程|建筑|帆船|农田|种植|养殖|保险|天气|气象|水位|温度|检测|空气|节能|人口|桥梁|青铜峡|培训|活动|实验|农场|造林|救援|购票|火车|风速|传感器|电子元件|发射|工程师"
ABSTRACT = r"纯数学|纯代数|纯几何|抽象数学|无现实|非实际|数学内部"
LINK = r"(?:由|利用|根据|结合|依据|沿用|在|应用)\s*(?:上述|前一问|第?\s*[（(]\s*[1一]\s*[）)]|前问)|上一问的(?:条件|结论|结果)"
CONDITIONAL = r"条件概率|已知[^。；]{0,40}(?:发生|命中|阳性|合格|不合格|击中|抽到|选中)[^。；]{0,48}(?:概率)|在[^。；]{0,36}(?:发生|命中|阳性|合格|击中|抽到)[^。；]{0,48}(?:条件|情况下|的概率)"
CONICS = r"椭圆|双曲线|抛物线|圆锥曲线"
MIDPOINT = r"弦.{0,18}中点|中点.{0,18}弦|线段.{0,18}中点"


def text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(text(item) for item in value)
    return ""


def evidence_scope(row):
    parts = [p["text"] if isinstance(p, dict) else p for p in row.get("parts", [])]
    return " ".join([row["stem"], text(parts)])


def scan(value, patterns):
    return {key: len(re.findall(regex, value, re.I)) for key, regex in patterns.items()}


def best(scores):
    maximum = max(scores.values(), default=0)
    choices = [k for k, value in scores.items() if maximum and value == maximum]
    return choices[0] if len(choices) == 1 else None


def match(regex, value):
    return bool(re.search(regex, value, re.I))


def project_question(row, available_on):
    review = row["calibration"]
    deep = row.get("deep_analysis") or review.get("deep_analysis") or {}
    prompt = evidence_scope(row)
    analysis_topic = " ".join([text(review.get("topic")), text(deep.get("knowledge"))])
    independent_solution = text(review.get("solution"))
    archival = scan(analysis_topic, MODULES)
    if not best(archival):
        archival = scan(independent_solution, MODULES)
    stem = scan(prompt, MODULES)
    a, b = best(stem), best(archival)
    primary = a if a and a == b else None
    # Single view is useful for adjudication, and remains unknown for primary points.
    context_a = match(CONTEXT, prompt)
    context_b = match(CONTEXT, text(deep.get("context")) + " " + text(deep.get("condition_design")))
    abstract_b = match(ABSTRACT, text(deep.get("context")))
    condition_a = match(CONDITIONAL, prompt) or match(r"P\s*\([^)]{1,60}\\mid[^)]{1,60}\)", prompt)
    condition_b = match(r"条件概率|贝叶斯|全概率", independent_solution + " " + text(deep.get("methods")))
    chord_a = match(CONICS, prompt) and match(MIDPOINT, prompt)
    chord_b = match(r"中点|点差法", independent_solution + " " + text(deep.get("knowledge")))
    binary = {
        "method.proof": row["kind"] == "constructed_response" and match(r"证明|求证|证[：:]", prompt),
        "method.linked": match(LINK, prompt),
        "method.context": True if context_a and context_b else (
            False if not context_a and not context_b and abstract_b else None
        ),
        "structure.conditional": (
            True if condition_a and condition_b else False if not condition_a and not condition_b
            and not match(MODULES["probability"], prompt) else None
        ),
        "structure.midpoint": (
            True if chord_a and chord_b else False if not match(CONICS, prompt)
            or not match(r"中点|平分|垂直平分", prompt) else None
        ),
    }
    available = sorted({k for k in MODULES if stem[k] and archival[k]})
    condition = {
        "has_real_parameter_cue": match(r"实数\s*\\?\(?[a-z]|参数|取值范围", prompt),
        "explicit_if": match(r"若|如果|在.{0,20}条件下", prompt),
        "figure_in_catalog": bool(row.get("asset_refs")),
    }
    computation = text(deep.get("computation"))
    load = ("high" if match(r"较大|中高|较高|高|繁", computation) else
            "medium" if match(r"中等|中|适中", computation) else
            "low" if match(r"低|少|小|一次", computation) else None)
    mechanics = sorted(k for k, count in scan(text(deep.get("methods")), METHODS).items() if count)
    reasoning_cues = scan(text(deep.get("breakthrough")) + " " + text(deep.get("progression")), METHODS)
    depth_label = text(deep.get("difficulty"))
    depth = (
        "basic" if re.match(r"基础|容易", depth_label) else
        "intermediate" if re.match(r"中档|中等", depth_label) else
        "advanced" if re.match(r"较难|高难|压轴|难题", depth_label) else None
    )
    return {
        "occurrence_id": row["occurrence_id"], "paper_id": row["paper_id"], "year": row["year"],
        "series": CORE.get(row["series_id"]), "version_sha256": row["version_sha256"],
        "question_id": row["question_id"],
        "equivalence_id": review.get("equivalence_id"), "content_sha256": row.get("content_sha256"),
        "kind": row["kind"], "points": row["points"], "available_on": available_on,
        "extractor_version": VERSION, "primary_topic": primary,
        "secondary_topic_cues": [k for k in available if k != primary],
        "source_views": {"prompt_primary": a, "archived_analysis_primary": b},
        "features": binary, "method_cues": mechanics,
        "reasoning_cues": sorted(k for k, count in reasoning_cues.items() if count),
        "reasoning_depth_editorial": depth,
        "modeling_cue": match(r"建模|数学模型|抽象成", text(deep.get("methods")) + " " + text(deep.get("context"))),
        "conditions": condition, "computational_load_editorial": load,
        "analysis_fields_present": sorted(k for k, v in deep.items() if k not in {"evidence", "solution_path"} and v),
        "novelty_cues": {
            "new_definition_explicit": match(r"定义.{0,25}(?:称为|记为)|称.{0,25}为|新定义", prompt),
            "open_condition_choice": match(r"任选|选取.{0,20}条件|补充.{0,15}条件", prompt),
        },
        "analysis_evidence_sha256": fingerprint(deep) if deep else None,
    }


def agreement(predicted, independent):
    pairs = [(a, b) for a, b in zip(predicted, independent, strict=True) if a is not None and b is not None]
    if not pairs:
        return {"comparable": 0, "matches": 0, "agreement": None, "kappa": None}
    n = len(pairs)
    first, second = map(Counter, zip(*pairs))
    expected = sum(first[k] * second[k] for k in first) / n**2
    matches = sum(a == b for a, b in pairs)
    return {
        "comparable": n, "matches": matches, "agreement": matches / n,
        "kappa": ((matches / n - expected) / (1 - expected)) if expected < 1 else None,
        "reviewer_positives": sum(b is True for _, b in pairs),
    }


def feature_ledger(root, independent, available_on):
    from math_calibration import grade
    from national_db import rows

    source = rows(root)
    result = {
        row["occurrence_id"]: project_question(row, available_on)
        for row in source if grade(row) == "source_and_solution_reviewed"
    }
    review_map = {"proof": "method.proof", "applied_context": "method.context",
                  "conditional_probability": "structure.conditional", "conic_midpoint": "structure.midpoint"}
    scored = defaultdict(lambda: defaultdict(lambda: ([], [])))
    observed = set()
    by_group = set()
    first_view = {}
    sample = [(r, "systematic_endpoints") for r in independent["records"]]
    sample.extend((r, "purposive_structural") for r in independent.get("targeted_records", []))
    for reviewer, group in sample:
        oid = reviewer["occurrence_id"]
        require((group,oid) not in by_group, "同一抽样组独立核对重复题目")
        by_group.add((group,oid))
        observed.add(oid)
        record = result[oid]
        unreviewed = first_view.setdefault(oid,(record["primary_topic"],dict(record["features"])))
        require(record["version_sha256"] == reviewer["version_sha256"], "独立标签对应其他题面版本")
        before = unreviewed[0]
        after = reviewer["primary"]
        require(after is None or after in MODULES, "未识别的独立知识模块")
        scored[group]["primary_topic"][0].append(before)
        scored[group]["primary_topic"][1].append(after)
        record["primary_topic"] = after
        record["independent_review"] = True
        for public_key, key in review_map.items():
            after = reviewer[public_key]
            require(type(after) is bool, "独立二分类标签须为真/假")
            scored[group][key][0].append(unreviewed[1][key])
            scored[group][key][1].append(after)
            record["features"][key] = after
    return list(result.values()), {
        "strict_question_records": len(result), "independently_audited": len(observed),
        "review_records_by_sample": dict(Counter(group for group,_ in by_group)),
        "pre_adjudication": {g: {k: agreement(*v) for k,v in fields.items()}
                             for g,fields in scored.items()},
        "scope": independent["review_scope"], "labels_available_on": available_on,
        "targeted_scope": independent.get("targeted_scope"),
        "human_verified": False,
    }


def group_ids(records):
    """Transitive union of known master, identical-content and adjudicated-equivalence links."""
    parents = {}
    def find(k):
        parents.setdefault(k, k)
        while parents[k] != k:
            parents[k] = parents[parents[k]]
            k = parents[k]
        return k
    for row in records:
        oid = row["occurrence_id"]
        for field in ("question_id", "equivalence_id", "content_sha256"):
            if value := row.get(field):
                parents[find(f"{field}:{value}")] = find(oid)
    return {r["occurrence_id"]: find(r["occurrence_id"]) for r in records}


def aggregate(records, papers):
    grouped = group_ids(records)
    per_paper = defaultdict(list)
    for row in records:
        if row["series"] in CORE.values():
            per_paper[row["paper_id"]].append(row)
    result = []
    for p in papers:
        if p["series_id"] not in CORE:
            continue
        rows = per_paper[p["id"]]
        # Preserve the real paper denominator even when version conflict leaves holes.
        full_count, total = p["question_count"], p["max_score"]
        require(len(rows) <= full_count and total > 0, "试卷覆盖或总分异常")
        unique = {}
        for row in rows:
            unique.setdefault(grouped[row["occurrence_id"]], row)
        unique_rows = list(unique.values())
        known = sum(r["points"] for r in unique_rows if r["primary_topic"])
        require(0 <= known <= total, "主类得分合计越界")
        full = len(unique_rows) == full_count
        row = {"paper_id": p["id"], "year": p["year"], "series": CORE[p["series_id"]],
               "observed_questions": len(rows), "unique_question_groups": len(unique),
               "full_questions": full_count, "unallocated_points": total - known,
               "available_on": max((r["available_on"] for r in rows), default=None),
               "question_groups": sorted(unique),
               "events": {}, "shares": {}}
        for topic in MODULES:
            points = sum(r["points"] for r in unique_rows if r["primary_topic"] == topic)
            event_id = "module." + topic
            row["events"][event_id] = 1 if points else 0 if full and known == total else None
            row["shares"][event_id] = [points / total, (points + total - known) / total]
        for key in ("method.proof", "method.linked", "method.context", "structure.conditional", "structure.midpoint"):
            vals = [r["features"][key] for r in unique_rows]
            row["events"][key] = 1 if True in vals else 0 if full and None not in vals else None
        row["events"]["paper.compact"] = int(full_count < 22)
        result.append(row)
    return sorted(result, key=lambda row: (row["year"], row["series"]))
