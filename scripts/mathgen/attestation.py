"""Bind independent AI reviews to immutable candidate versions before exporting a research copy."""

from pathlib import Path
from analysis_db import fingerprint
from gaokao import read_json, require
from storage import atomic_json
from .quality import assert_fresh


def attest(run_path, report_path, blind_path=None, export=True):
    run_path = Path(run_path)
    output = run_path.parent
    record = read_json(run_path)
    report = read_json(report_path)
    require(record.get("generation_mode") == "ai", "仅接受动态AI记录")
    rows = {}
    for row in report.get("questions", []) + report.get("re_reviews", []):
        sha = row.get("candidate_sha256")
        if not sha:
            continue
        old = rows.get(sha, {})
        merged = {**old, **row}
        if row.get("status") != "pass":
            merged["status"] = row.get("status")
        rows[sha] = merged
    blind = read_json(blind_path) if blind_path else None
    blind_rows = (
        {r["candidate_sha256"]: r for r in blind.get("reviews", [])} if blind else {}
    )
    report_sha = fingerprint(report)
    review_records = []
    for q, v in zip(record["questions"], record["verifications"]):
        assert_fresh(q, v)
        require(v["passed"], "程序验证失败，不能接收审题结论")
        sha = q["generation"]["raw_candidate_sha256"]
        row = rows.get(sha)
        require(
            row and row.get("status") == "pass", "独立AI审题缺失或不通过 " + q["id"]
        )
        if blind:
            require(
                blind_rows.get(sha, {}).get("pass") is True, "独立盲审未覆盖当前版本"
            )
        v["independent_ai_review"] = "已完成独立AI推理审查"
        v["ai_review_record"] = {
            "candidate_sha256": sha,
            "review_report_sha256": report_sha,
            "reviewer": row.get("reviewer", report.get("reviewer")),
            "model_version": row.get("model_version", "not_exposed_by_host"),
            "formal_proof": False,
            "human_review": "尚需人工核验",
        }
        solution = row.get("independent_solution") or row.get(
            "mathematical_review", {}
        ).get("independent_solution", "")
        if blind:
            solution = "；".join(blind_rows[sha]["independent_solution"])
        if q["kind"] in ("constructed_response", "fill_in") and solution:
            # Choice review text may name original letters; never copy them after layout shuffling.
            marker = "独立AI高中解法复核："
            v["steps"] = [
                step for step in v["steps"] if not step.startswith(marker)
            ] + [marker + solution]
        v["remaining_uncertainty"] = (
            "程序验证与独立AI推理审查均已完成；不是形式化证明。尚需教师审核和考生实测。"
        )
        review_records.append({"id": q["id"], **v["ai_review_record"], "review": row})
    atomic_json(
        output / "independent-review.json",
        {
            "report_sha256": report_sha,
            "questions": review_records,
            "blind_report_sha256": fingerprint(blind) if blind else None,
        },
    )
    record["overall_status"] = "研究审阅版：程序验证及独立AI审查完成，尚需教师核验"
    record["independent_review_sha256"] = report_sha
    record["structure"]["independent_ai_reviewed"] = len(review_records)
    record["structure"]["human_review"] = "尚需人工核验"
    record["structure"]["formal_proof"] = False
    record["publication_gate"] = {
        "research_copy_allowed": True,
        "high_quality_exam_certified": False,
        "teacher_review_required": True,
    }
    record["stages"] = [
        {
            "stage": "planner",
            "version": "dynamic-planner-v1",
            "input_sha256": record["research_context_sha256"],
            "output_sha256": fingerprint(record["blueprint"]),
            "model": "not_applicable",
            "passed": True,
        },
        {
            "stage": "ai_proposer",
            "version": "ai-protocol-v1",
            "provider": record["provider"],
            "model": record["provenance"].get(
                "model",
                record["provenance"].get("model_version", "not_exposed_by_host"),
            ),
            "input_sha256": record["research_context_sha256"],
            "output_sha256": fingerprint(read_json(output / "raw-ai-proposal.json")),
            "passed": True,
        },
        *[
            {
                "stage": "independent_solver_and_item_audit",
                "version": v["version"],
                "question_id": q["id"],
                "model": "not_applicable",
                "input_sha256": fingerprint(q["problem"]),
                "output_sha256": fingerprint(v["solver_record"]),
                "audit_sha256": fingerprint(v["quality"]),
                "passed": v["passed"],
                "failure_reasons": v["quality"].get("errors", []),
            }
            for q, v in zip(record["questions"], record["verifications"])
        ],
        {
            "stage": "independent_ai_review",
            "version": "version-bound-review-v1",
            "model": "not_exposed_by_host",
            "input_sha256": fingerprint(
                [q["generation"]["raw_candidate_sha256"] for q in record["questions"]]
            ),
            "output_sha256": report_sha,
            "passed": True,
            "formal_proof": False,
        },
        {
            "stage": "whole_paper_audit",
            "version": "paper-audit-v2",
            "model": "not_applicable",
            "input_sha256": fingerprint(record["questions"]),
            "output_sha256": fingerprint(record["structure"]),
            "passed": record["structure"]["passed"],
        },
    ]
    atomic_json(output / "quality-report.json", record["structure"])
    if export:
        from .export import export_run

        presentation = {
            **record,
            "events": [
                {
                    "passed": True,
                    "quality": {
                        "duplicate": {"closest": {"score": "见结构化原创性报告"}}
                    },
                }
                for _ in record["questions"]
            ],
        }
        record["files"] = export_run(presentation, output)
        from gaokao import digest

        record["stages"].append(
            {
                "stage": "typesetting",
                "version": "pdf-layout-v3",
                "model": "not_applicable",
                "input_sha256": fingerprint(record["questions"]),
                "output_files_sha256": {
                    name: digest(output / name)
                    for name in ("paper.pdf", "solutions.pdf")
                },
                "passed": True,
                "visual_review": "须另见逐页PDF检查报告",
            }
        )
    atomic_json(run_path, record)
    return {
        "questions_reviewed": len(review_records),
        "status": record["overall_status"],
        "files": record.get("files", {}),
    }
