"""Evidence-based module planning, without a list of question families."""

from collections import Counter
import random
from analysis_db import fingerprint
from gaokao import read_json, read_lines, require


def context(root, include_local=True, evaluation_split=None, strict=False, topics=None):
    from local_archive import public_edition, read_bundle

    public = public_edition(root)
    records = (
        list(read_lines(root / "analysis/questions.jsonl"))
        if include_local and evaluation_split is None and not strict
        else []
    )
    applied = []
    override_path = root / "analysis/review-overrides.json"
    if override_path.is_file():
        for change in read_json(override_path).get("overrides", []):
            for r in records:
                if (
                    r["question_id"] == change["question_id"]
                    and r["candidate_sha256"] == change["candidate_sha256"]
                    and fingerprint(r) == change["analysis_sha256"]
                    and change["field"] == "knowledge.module"
                    and r["knowledge"]["module"] == change["original_value"]
                ):
                    r["knowledge"] = {
                        **r["knowledge"],
                        "module": change["reviewed_value"],
                    }
                    applied.append(change)
    national_summary = {}
    if (root / "national/config.json").is_file():
        from national_db import catalog, target, available, planning_references

        papers = (
            read_bundle(root / "sample-data")[1]["papers"]
            if public and not include_local
            else catalog(root, "papers")
        )
        national_summary = {
            "target": target(root),
            "papers": [
                {
                    k: p[k]
                    for k in ("id", "year", "series_id", "track", "question_count")
                }
                for p in papers
            ],
            "full_history_available": available(root) and not public,
            "question_registry_is_not_full_text": True,
            "retrieval_entry": "national_cli.py research --target-region 河南 --target-year 2027",
        }
    if include_local and (public or national_summary.get("full_history_available")):
        national_summary["bounded_reference_packs"] = planning_references(
            root,
            **({"topics": topics} if topics else {}),
            verified_only=(strict and not public) or evaluation_split is not None,
            allowed_ids=evaluation_split["reference"] if evaluation_split else None,
        )
        if evaluation_split:
            national_summary["evaluation_split_sha256"] = evaluation_split["sha256"]
        if public:
            national_summary["dataset_scope"] = "原创样本与用户本地导入资料"
    elif not include_local:
        national_summary["dataset_scope"] = "外部模型不接收本地历史题面或逐题分析"
    return {
        "rules": read_json(root / "analysis/rules.json"),
        "analyses": [
            {
                "question_id": r["question_id"],
                "candidate_sha256": r["candidate_sha256"],
                "knowledge": r["knowledge"],
                "key_idea": r["key_idea"],
                "condition_design": r["context_and_condition_design"],
                "review_status": r["review_status"],
                "official_body_confirmed": False,
            }
            for r in records
        ],
        "sample_papers": 0 if public else 2,
        "applied_review_overrides": applied,
        "scope": "公开原创样本与本地导入"
        if public
        else "候选版本绑定的AI分析，尚无命题机构逐题认证",
        "national_archive": national_summary,
    }


def plan(root, mode, profile="balanced", seed=0, proposed=None):
    evidence = context(root)
    rules = evidence["rules"]
    rng = random.Random(seed)
    weights = Counter(r["knowledge"]["module"] for r in evidence["analyses"])
    if evidence.get("national_archive"):
        weights = Counter(
            evidence["national_archive"]["target"]["module_coverage_weights"]
        )
    kinds = []
    if mode == "full":
        for section in rules["blueprint"]["sections"]:
            values = section.get(
                "points", [section.get("points_each")] * section["count"]
            )
            kinds.extend((section["kind"], p) for p in values)
    elif mode == "mixed":
        kinds = [("single_choice", 5)] * 4 + [("constructed_response", 10)] * 3
    elif mode in ("sequence", "derivative"):
        kinds = [("constructed_response", 10)] * 10
    else:
        kinds = [("constructed_response", 10)] * 5
    labels = list(weights)
    if mode == "sequence":
        labels = ["数列"]
    if mode == "derivative":
        labels = ["函数与导数"]
    slots = []
    counts = Counter()
    for i, (kind, points) in enumerate(kinds):
        ranked = sorted(
            labels,
            key=lambda m: (
                (
                    weights[m]
                    + (
                        4
                        if (profile == "geometry" and m in ("解析几何", "立体几何"))
                        else 0
                    )
                )
                / (1 + counts[m]),
                rng.random(),
            ),
            reverse=True,
        )
        module = ranked[0]
        if proposed:
            require(i < len(proposed), "AI蓝图缺槽位")
            module = proposed[i]["module"]
            require(module in weights or module == "排列组合", "AI蓝图知识模块未获准")
        counts[module] += 1
        ids = [
            r["question_id"]
            for r in evidence["analyses"]
            if r["knowledge"]["module"] == module
        ]
        slots.append(
            {
                "order": i + 1,
                "kind": kind,
                "points": points,
                "module": module,
                "research_ids": ids,
                "national_reference_ids": [
                    r["occurrence_id"]
                    for pack in evidence.get("national_archive", {})
                    .get("bounded_reference_packs", {})
                    .values()
                    for r in pack["references"]
                    if module in str(r.get("topic_flags", []))
                    or module
                    in str(r.get("national_analysis", {}).get("knowledge", []))
                ],
                "reasoning_target": "基本转化"
                if i < 5
                else "条件关联"
                if i < 14
                else "分层综合与论证",
            }
        )
    if proposed:
        require(len(proposed) == len(slots), "AI蓝图题数与规则不符")
    return {
        "version": "dynamic-planner-v1",
        "mode": mode,
        "profile": profile,
        "seed": seed,
        "title": {
            "full": "河南2027高考风格数学研究模拟卷",
            "mixed": "50分数学综合检测",
            "sequence": "AI动态数列专项",
            "derivative": "AI动态导数专项",
        }.get(mode, "AI动态命题验收卷"),
        "slots": slots,
        "total_points": sum(p for _, p in kinds),
        "research_context_sha256": fingerprint(evidence),
        "rules_sha256": fingerprint(rules),
        "sample_size": evidence["sample_papers"],
        "official_2027_structure_verified": False,
        "reference_policy": evidence.get("national_archive", {}).get("target"),
        "planning_basis": "读取逐题知识与条件设计分析，结合AI本轮提出的模块搭配；计分结构由历史候选规则约束",
        "simulation_settings": [
            "2027详细结构尚为模拟设定",
            "难度和用时为设计估计，需教师与考生验证",
        ],
    }
