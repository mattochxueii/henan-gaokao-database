"""Recompute delivery evidence without copying private source text into reports."""

import bootstrap
from collections import Counter
from analysis_db import research, fingerprint
from gaokao import ROOT, read_json, read_lines, require, digest
from storage import atomic_json
from mathgen.novelty import cohort_report, paper_difference
from mathgen.review import audit_item
from mathgen.quality import assert_fresh


def main():
    folder = ROOT / "experiments/phase3/deliveries"
    runs = {
        name: read_json(folder / name / "run.json")
        for name in (
            "sequence10",
            "derivative10",
            "mixed50",
            "fullA",
            "fullB",
            "acceptance5",
        )
    }
    pool = [q for run in runs.values() for q in run["questions"]]
    analyses = list(read_lines(ROOT / "analysis/questions.jsonl"))
    for run in runs.values():
        for q, v in zip(run["questions"], run["verifications"]):
            assert_fresh(q, v)
            require(
                v["passed"] and v["independent_ai_review"] == "已完成独立AI推理审查",
                "交付题未通过",
            )
    difference = paper_difference(runs["fullA"], runs["fullB"])
    require(difference["passed"], "两卷结构变化不足")
    atomic_json(ROOT / "reports/paper-difference.json", difference)
    originality = [cohort_report(q, pool, analyses) for q in pool]
    atomic_json(ROOT / "reports/phase3-originality.json", originality)
    for name, run in runs.items():
        ids = {q["id"] for q in run["questions"]}
        atomic_json(
            folder / name / "originality-report.json",
            [r for r in originality if r["question_id"] in ids],
        )
        atomic_json(
            folder / name / "question-quality.json",
            [
                {
                    "id": q["id"],
                    "mode": "ai",
                    "candidate_sha256": q["generation"]["raw_candidate_sha256"],
                    "question_sha256": fingerprint(q),
                    "module": q["module"],
                    "knowledge": q["design"]["knowledge_combination"],
                    "purpose": q["design"]["structure"],
                    "reasoning": q["design"]["reasoning_path"],
                    "designed_difficulty": q["difficulty"],
                    "difficulty_basis": q["difficulty_basis"],
                    "program_verification": v["status"],
                    "independent_ai_review": v["independent_ai_review"],
                    "formal_proof": False,
                    "teacher_review": "尚需人工核验",
                }
                for q, v in zip(run["questions"], run["verifications"])
            ],
        )
    evidence = {}
    for topic in ("数列", "导数"):
        rows = research(ROOT, topic=topic)
        evidence[topic] = [
            {
                "id": r["id"],
                "candidate_sha256": fingerprint(r["candidate"]),
                "source_pages": r["candidate"].get("source_pages"),
                "knowledge": r["analysis"]["knowledge"],
                "key_idea": r["analysis"]["key_idea"],
                "condition_design": r["analysis"]["context_and_condition_design"],
                "official_body_confirmed": False,
            }
            for r in rows
        ]
    atomic_json(
        ROOT / "reports/phase3-research-evidence.json",
        {
            "actual_private_candidates_read": True,
            "topics": evidence,
            "scope": "真实读取当前私有候选与38条分析；这里只保存分析摘要及哈希，避免再分发完整题面",
        },
    )
    templates = {}
    for name in ("sequence", "derivative", "mixed", "full"):
        record = read_json(ROOT / "experiments" / name / "run.json")
        templates[name] = {
            "mode": record["generation_mode"],
            "questions": len(record["questions"]),
            "all_item_audits_pass": all(
                audit_item(q)["passed"] for q in record["questions"]
            ),
        }
    report = {
        "dynamic_questions": len(pool),
        "ai_provider": "host_ai",
        "api_calls": 0,
        "template_calls_in_ai": 0,
        "model_version": "not_exposed_by_host",
        "experiments": {
            name: {
                "questions": len(r["questions"]),
                "points": r["structure"]["points"],
                "status": r["overall_status"],
                "sha256": digest(folder / name / "run.json"),
            }
            for name, r in runs.items()
        },
        "template_rechecks": templates,
        "full_paper_difference": {
            k: v for k, v in difference.items() if k != "slot_comparisons"
        },
        "choice_key_counts": {
            name: dict(
                Counter(
                    v["option_key"]
                    for q, v in zip(r["questions"], r["verifications"])
                    if q["kind"] == "single_choice"
                )
            )
            for name, r in runs.items()
        },
        "limitations": [
            "仅为研究审阅版，整卷偏基础至中档，压轴强度和分值待教师审核",
            "难度及时间未实测",
            "独立AI审题不是人类盲审或形式化证明",
            "不支持任意自然语言证明",
            "API仅模拟传输测试，未付费实调",
        ],
    }
    atomic_json(ROOT / "reports/phase3-summary.json", report)
    print(
        "dynamic questions:",
        len(pool),
        "distinct paper modules:",
        difference["module_position_changes"],
        "structure overlap:",
        difference["structure_set_overlap"],
    )


if __name__ == "__main__":
    main()
