"""Three-layer exam workflow with an immutable PDF-only student review gate."""

from pathlib import Path
import json, shutil, subprocess
from analysis_db import fingerprint
from gaokao import require, read_json, digest
from storage import atomic_json
from core.editorial_rules import LAYOUT_MODES, REVISION
from .editorial import compile_writing
from .student_pdf import render
from .school_solver import solve_spec
from .paper_quality import placement_report, verify_position_review
from .research_quality import (
    PROTOCOL,
    coverage_report,
    require_specialty_certificates,
    uses_protocol,
    verify_blind_quality,
    verify_design,
)

VERSION = "exam-workflow-v2"


def compile_for_layout(question, layout):
    visible = compile_writing(question)
    if layout == "math_compact":
        visible.update(module=question.get("module"),
                       figure_required=question["writing"].get("figure_required", False))
        if technique := question.get("math_technique"):
            visible["math_technique"] = technique
    return visible


def prepare(root, document, output, pilot_certificate=None, specialty_certificates=(), *,
            skip_pilot=False, layout_mode="practice"):
    output = Path(output)
    require(layout_mode in LAYOUT_MODES, "排版模式须为 practice 或 exam")
    require(not output.exists(), "使用新目录保留旧候选和失败记录")
    require(document.get("schema_version") == 2, "须提供带中文写作层的v2候选")
    require(document.get("research_protocol") in (None, PROTOCOL), "未知的研究命题协议")
    require(
        document["provenance"]["mode"] == "ai"
        and document["provenance"]["template_calls"] == 0,
        "不是AI动态创作候选",
    )
    mode = document["paper"]["mode"]
    trend = document["paper"].get("edition") == "trend_pack"
    has_signals = "trend_snapshot_sha256" in document or any("trend_basis" in q for q in document["questions"])
    require(trend == has_signals and (not trend or mode != "full"), "标准整卷与趋势研判专题须分别制作")
    if trend:
        from math_trends import validate_pack

        validate_pack(root, document)
    verify_design(root, document)
    require(not skip_pilot or (mode == "full" and pilot_certificate is None), "仅可对整卷显式跳过样卷")
    if mode == "full" and uses_protocol(document) and not skip_pilot:
        require_specialty_certificates(specialty_certificates)
        require(pilot_certificate is not None, "整卷须先通过五题题位样卷")
        cert = read_json(pilot_certificate)
        require(
            cert.get("published") and cert.get("kind") == "pilot"
            and cert.get("question_count") == 5 and cert.get("position_review_sha256"),
            "五题题位样卷未完成独立审核",
        )
        verify_certificate(Path(pilot_certificate).parent, cert)
    elif mode == "full" and not skip_pilot:
        require(pilot_certificate is not None, "整卷生成前须通过5题样卷")
        cert = read_json(pilot_certificate)
        require(
            cert.get("published")
            and cert.get("kind") == "pilot"
            and cert.get("question_count") == 5,
            "5题样卷尚未通过",
        )
        # Certificates remain bound to their reviewed PDF and pages, not a bare boolean.
        verify_certificate(Path(pilot_certificate).parent, cert)
    coverage = None
    if mode == "full" or document.get("position_pilot"):
        output.mkdir(parents=True, exist_ok=True)
        atomic_json(output / "raw-ai-candidate.json", document)
        position = placement_report(document, None)
        atomic_json(output / "position-plan.json", position)
        if skip_pilot:
            atomic_json(output / "pilot-waiver.json", {"mode": "full", "scope": "generation_only"})
        require(not position["failures"], "整卷题位计划未通过，详见position-plan.json")
    if mode == "full":
        require(document["paper"].get("require_scoring") is True, "整卷需要逐步评分细则")
        coverage = coverage_report(document)
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "raw-ai-candidate.json", document)
    presentation = {
        "title": document["paper"]["title"],
        "minutes": document["paper"]["minutes"],
        "total_points": document["paper"]["total_points"],
        "layout_mode": layout_mode,
        "questions": [],
    }
    reference = document.get("quality_benchmarks") or {}
    from core.quality_audit import MAIN_VERSION
    if reference.get("protocol") == MAIN_VERSION:
        presentation.update(layout="math_compact", subject="math", standard=mode=="full", edition_rules=REVISION)
        if mode == "full" and reference.get("exam_policy"):
            presentation.update(exam_policy=reference["exam_policy"], qa_protocol=reference["review_board"])
            if reference.get("release_rules"):
                presentation["release_rules"]=reference["release_rules"]
                presentation["ledger_topics"]=document.get("ledger_topics",{})
        if trend:
            presentation["benchmark_slots"] = reference["benchmark_slots"]
    verification = []
    failures = []
    for q in document["questions"]:
        try:
            require("family" not in q, "禁止模板题目族伪装AI")
            student = compile_for_layout(q, presentation.get("layout"))
            result = solve_spec(q["math_spec"])
            require(result["program_checks_passed"], "数学计算失败：" + str(result))
            if q["kind"] == "single_choice" and q["math_spec"].get("assertions"):
                truth = [r.get("result") for r in result["tasks"]]
                require(
                    len(truth) == 4 and all(type(v) is bool for v in truth),
                    "单选真值须可独立求出",
                )
                require(truth.count(True) == 1, "单选正确答案不唯一")
                result["answer_key"] = "ABCD"[truth.index(True)]
            elif q["kind"] == "single_choice":
                values = {
                    k: v["semantic_value"] for k, v in q["math_spec"]["options"].items()
                }
                from .ai_spec import parse
                import sympy as s

                target = parse(str(result["tasks"][0]["result"]))
                keys = [
                    k for k, v in values.items() if s.simplify(parse(v) - target) == 0
                ]
                require(len(keys) == 1, "单选正确答案不唯一")
                require(
                    len({str(s.simplify(parse(v))) for v in values.values()}) == 4,
                    "选项等价",
                )
                for key, option in q["math_spec"]["options"].items():
                    if option.get("error_calculation"):
                        require(
                            s.simplify(
                                parse(option["error_calculation"])
                                - parse(option["semantic_value"])
                            )
                            == 0,
                            "干扰项错因计算不对应实际选项",
                        )
                result["answer_key"] = keys[0]
            elif q["kind"] == "multiple_choice":
                truth = [r.get("result") for r in result["tasks"]]
                if all(type(v) == bool for v in truth):
                    key = "".join(k for k, v in zip("ABCD", truth) if v)
                    require(len(key) in (2, 3), "多选答案集合不规范")
                    result["answer_key"] = key
                else:
                    result["answer_key"] = None
            result["id"] = q["id"]
            result["math_spec_sha256"] = fingerprint(q["math_spec"])
            result["writing_sha256"] = fingerprint(student)
            presentation["questions"].append(student)
            verification.append(result)
        except Exception as e:
            failures.append({"id": q.get("id"), "reason": str(e)})
    atomic_json(output / "rejected.json", failures)
    require(not failures, "候选未通过，详见rejected.json")
    require(
        sum(q["points"] for q in presentation["questions"])
        == presentation["total_points"],
        "分值不符",
    )
    require(
        [q["order"] for q in presentation["questions"]]
        == list(range(1, len(presentation["questions"]) + 1)),
        "题号不连续",
    )
    if mode == "full":
        kinds = [q["kind"] for q in presentation["questions"]]
        if uses_protocol(document):
            from national_db import target

            configuration = read_json(root / target(root)["structure_source"])
            sections = configuration["blueprint"]["sections"]
            expected_kinds = [s["kind"] for s in sections for _ in range(s["count"])]
            expected_points = [
                p
                for s in sections
                for p in (
                    s["points"] if "points" in s else [s["points_each"]] * s["count"]
                )
            ]
        else:
            expected_kinds = (
                ["single_choice"] * 8
                + ["multiple_choice"] * 3
                + ["fill_in"] * 3
                + ["constructed_response"] * 5
            )
            expected_points = [5] * 8 + [6] * 3 + [5] * 3 + [13, 15, 15, 17, 17]
        require(
            kinds == expected_kinds,
            "完整卷型结构不符",
        )
        require(
            [q["points"] for q in presentation["questions"]] == expected_points,
            "完整卷分值结构不符",
        )
    atomic_json(output / "student-text.json", presentation)
    atomic_json(output / "math-verification.json", verification)
    if coverage is not None:
        atomic_json(output / "coverage-review.json", coverage)
    return render_preview(output)


def render_preview(output):
    output = Path(output)
    document = read_json(output / "raw-ai-candidate.json")
    require(
        not (output / "publication.json").exists(), "已发布版本不可重排，请创建修订版本"
    )
    presentation = read_json(output / "student-text.json")
    verification = read_json(output / "math-verification.json")
    require(len(verification) == len(document["questions"]), "数学核查数量不完整")
    for q, visible, check in zip(
        document["questions"], presentation["questions"], verification
    ):
        require(
            check["program_checks_passed"]
            and check["id"] == q["id"]
            and check["math_spec_sha256"] == fingerprint(q["math_spec"]),
            "数学验证已过期",
        )
        compiled = compile_for_layout(q, presentation.get("layout"))
        require(fingerprint(compiled) == fingerprint(visible), "写作文本已变化，必须回到题面核查")
    mode = document["paper"]["mode"]
    preview = output / "review-only"
    preview.mkdir(exist_ok=True)
    render(presentation, preview / "paper.pdf")
    pages = preview / "pages"
    pages.mkdir(exist_ok=True)
    for old in pages.glob("page-*.png"):
        require(old.resolve().parent == pages.resolve(), "渲染图片越界")
        old.unlink()
    subprocess.run(
        [
            "pdftoppm",
            "-r",
            "120",
            "-png",
            str(preview / "paper.pdf"),
            str(pages / "page"),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    images = sorted(pages.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
    manifest = {
        "workflow_version": VERSION,
        "kind": mode,
        "question_count": len(verification),
        "candidate_sha256": fingerprint(document),
        "writing_sha256": fingerprint(presentation),
        "pdf_sha256": digest(preview / "paper.pdf"),
        "pages": [{"number": i + 1, "sha256": digest(p)} for i, p in enumerate(images)],
        "status": "仅供盲审；尚未发布",
        "solutions_available_to_student_reviewer": False,
    }
    atomic_json(output / "review-manifest.json", manifest)
    return manifest


def verify_certificate(folder, cert):
    document = read_json(folder / "raw-ai-candidate.json")
    require(
        fingerprint(document) == cert["candidate_sha256"],
        "已审数学候选被修改",
    )
    require(digest(folder / "paper.pdf") == cert["pdf_sha256"], "已审PDF被修改")
    require(
        fingerprint(read_json(folder / "student-text.json")) == cert["writing_sha256"],
        "已审文本被修改",
    )
    review = read_json(folder / "student-review.json")
    require(fingerprint(review) == cert["review_sha256"], "审题报告被修改")
    require(review["pdf_sha256"] == cert["pdf_sha256"], "PDF与审核内容不一致")
    require(
        cert.get("solutions_sha256")
        and digest(folder / "solutions.pdf") == cert["solutions_sha256"],
        "答案文件缺失或已改变",
    )
    if document.get("quality_benchmarks"):
        from core.quality_audit import publication_quality

        require(publication_quality(folder, review) == cert.get("quality_audit_sha256"), "命题审稿证书失效")
    comparison = read_json(folder / "mathematical-comparison.json")
    require(
        fingerprint(read_json(folder / "math-verification.json"))
        == comparison["math_verification_sha256"],
        "已审数学核查记录被修改",
    )
    require(
        fingerprint(comparison) == cert["mathematical_comparison_sha256"]
        and comparison["all_consistent"],
        "数学对照证书无效",
    )
    if document.get("position_pilot") or cert.get("position_review_sha256") or (
        cert["workflow_version"] == VERSION and cert["kind"] == "full"
    ):
        position = read_json(folder / "position-review.json")
        rechecked = verify_position_review(
            document, review["position_review"], cert,
            read_json(folder / "position-plan.json"),
        )
        require(
            fingerprint(position) == cert.get("position_review_sha256")
            and position == {**rechecked, "pdf_sha256": cert["pdf_sha256"]},
            "整卷题位证书无效",
        )
    require(
        all(
            all(
                row.get(k) is True
                for k in ("readability_pass", "mathematical_pass", "points_appropriate")
            )
            for row in review["questions"]
        ),
        "样卷仍有不通过项",
    )


def publish(output, review_path, comparison_path, *, root=None):
    from core.release_checks import is_frozen_sample, require_release
    from gaokao import ROOT

    output = Path(output)
    root=root or ROOT
    student = read_json(output / "student-text.json")
    if student.get("release_rules") or is_frozen_sample(root,output):
        require_release(root,output)
    review = read_json(review_path)
    comparison = read_json(comparison_path)
    manifest = read_json(output / "review-manifest.json")
    source = output / "review-only/paper.pdf"
    require(
        digest(source) == manifest["pdf_sha256"] == review["pdf_sha256"],
        "PDF与审核文本不一致",
    )
    student = read_json(output / "student-text.json")
    require(fingerprint(student) == manifest["writing_sha256"], "中文题面已修改")
    raw = read_json(output / "raw-ai-candidate.json")
    require(
        fingerprint(raw) == manifest["candidate_sha256"],
        "数学候选或评分设计已修改，必须重新核查",
    )
    require(
        review["input_scope"] == "pdf_only"
        and review["reference_answers_read"] is False
        and review["internal_spec_read"] is False
        and review["proposer_design_read"] is False,
        "不满足考生视角独立盲审",
    )
    require(review.get("overall_pass") is True, "整卷考生视角/风格审查未通过，禁止发布")
    verify_blind_quality(raw, review)
    quality = None
    if raw.get("quality_benchmarks"):
        from core.quality_audit import publication_quality

        quality = publication_quality(output, review)
    position = None
    if raw["paper"]["mode"] == "full" or raw.get("position_pilot"):
        plan = read_json(output / "position-plan.json")
        position = verify_position_review(raw, review["position_review"], manifest, plan)
        position["pdf_sha256"] = manifest["pdf_sha256"]
    reviewed_pages = [
        {"number": p["number"], "sha256": p["sha256"]} for p in review["pages"]
    ]
    require(reviewed_pages == manifest["pages"], "未核对所有渲染页面")
    reviews = review["questions"]
    require(len(reviews) == manifest["question_count"], "独立审题漏题")
    require(
        [r["number"] for r in reviews] == list(range(1, len(reviews) + 1)),
        "审题题号错位",
    )
    for row in reviews:
        require(
            all(
                row.get(k) is True
                for k in ("readability_pass", "mathematical_pass", "points_appropriate")
            ),
            "独立审题不通过，不能发布",
        )
        require(
            row.get("conditions_understood")
            and row.get("request_understood")
            and row.get("independent_solution"),
            "审题缺少实际推理依据",
        )
        require(not row.get("blocking_issues"), "存在严重题面问题")
    require(
        comparison["pdf_sha256"] == manifest["pdf_sha256"]
        and comparison["student_review_sha256"] == fingerprint(review),
        "数学对照不对应当前PDF/盲审",
    )
    require(
        comparison["math_verification_sha256"]
        == fingerprint(read_json(output / "math-verification.json")),
        "数学计算记录变化",
    )
    require(
        comparison["all_consistent"] and len(comparison["questions"]) == len(reviews),
        "数学与考生理解未完成逐题对照",
    )
    require(
        all(r["passed"] and r.get("evidence") for r in comparison["questions"]),
        "逐题数学质量不通过",
    )
    calculations = read_json(output / "math-verification.json")
    if raw.get("evaluation_split_sha256"):
        dimensions = {"scope", "necessity", "sufficiency", "boundaries", "equality", "school_solution"}
        for index, (row, calculation) in enumerate(zip(comparison["questions"], calculations), 1):
            require(row.get("number") == index, "数学对照题号错位")
            if not calculation["all_tasks_program_complete"]:
                audit = row.get("argument_audit", {})
                require(
                    set(audit) == dimensions
                    and all(isinstance(v, str) and v.strip() for v in audit.values()),
                    "不完整程序覆盖须检查必要性、充分性、边界、等号与高中解法",
                )
    for row, calculation in zip(reviews, calculations):
        if student["questions"][row["number"] - 1]["kind"] == "multiple_choice":
            given = row.get("answer_key") or []
            require(
                set(given) <= set("ABCD") and len(given) == len(set(given))
                and len(given) in (2, 3),
                "多选独立答案集合不规范",
            )
            for key, task in zip("ABCD", calculation["tasks"]):
                if task.get("complete") and type(task.get("result")) is bool:
                    require(
                        (key in given) == task["result"],
                        "部分程序验证与多选独立答案不符",
                    )
        if calculation.get("answer_key"):
            given = row.get("answer_key")
            actual = (
                "".join(sorted(given))
                if isinstance(given, list)
                else "".join(sorted(given or ""))
            )
            require(actual == calculation["answer_key"], "PDF独立求解与选项答案不符")
    from .scoring import solution_book

    guide = comparison.get("scoring")
    if raw["paper"]["mode"] == "full" or raw["paper"].get("require_scoring"):
        require(guide is not None, "此卷需要逐步评分细则")
    if guide is not None:
        require(guide.get("paper_sha256") == manifest["pdf_sha256"], "评分细则对应其他卷面")
    answer_keys = [r.get("answer_key") for r in reviews]
    answer_keys = ["".join(key) if isinstance(key,list) else key for key in answer_keys]
    solutions = solution_book(student, raw, comparison.get("solution_revisions", {}), guide,
                              answer_keys=answer_keys)
    if student.get("release_rules"):
        from core.marking_standards import grading_findings

        rendered = {q["order"]:"\n".join(q["solution_paragraphs"]) for q in solutions["questions"]}
        defects = list(grading_findings("math",solutions["questions"],{},rendered))
        require(not defects,"数学解析评分格式错误："+str(defects))
    cert = {
        **manifest,
        **({"quality_audit_sha256": quality} if quality else {}),
        "published": True,
        "status": "独立AI考生审题及数学对照通过；教师与实测待审",
        "review_sha256": fingerprint(review),
        "mathematical_comparison_sha256": fingerprint(comparison),
        "formal_proof": False,
        "human_reviewed": False,
    }
    if student.get("qa_protocol") == "three-readers-v2":
        from core.review_board import LOCAL_QA_PASSED

        cert["local_qa_status"] = LOCAL_QA_PASSED
    render(solutions, output / "solutions.pdf", solutions=True)
    shutil.copyfile(source, output / "paper.pdf")  # Byte-identical reviewed artifact.
    if student.get("layout") == "math_compact":
        shutil.copyfile(source.with_suffix(".md"), output / "paper.md")
        layout_receipt = source.with_suffix(".layout.json")
        if layout_receipt.is_file():
            shutil.copyfile(layout_receipt, output / "paper.layout.json")
        figures = source.parent / "figures"
        if figures.is_dir():
            shutil.copytree(figures, output / "figures", dirs_exist_ok=True)
    atomic_json(output / "student-review.json", review)
    atomic_json(output / "mathematical-comparison.json", comparison)
    if position is not None:
        atomic_json(output / "position-review.json", position)
        cert["position_review_sha256"] = fingerprint(position)
    cert["solutions_sha256"] = digest(output / "solutions.pdf")
    if student.get("release_rules"):
        from core.publication_ledger import register

        register(root,"math",student,manifest["pdf_sha256"])
    atomic_json(output / "publication.json", cert)
    return cert
