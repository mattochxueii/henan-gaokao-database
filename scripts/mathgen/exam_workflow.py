"""Three-layer exam workflow with an immutable PDF-only student review gate."""

from pathlib import Path
import json, shutil, subprocess
from analysis_db import fingerprint
from gaokao import require, read_json, digest
from storage import atomic_json
from .editorial import compile_writing
from .student_pdf import render
from .school_solver import solve_spec
from .research_quality import (
    PROTOCOL,
    require_specialty_certificates,
    uses_protocol,
    verify_blind_quality,
    verify_design,
)

VERSION = "exam-workflow-v1"


def prepare(root, document, output, pilot_certificate=None, specialty_certificates=()):
    output = Path(output)
    require(not output.exists(), "使用新目录保留旧候选和失败记录")
    require(document.get("schema_version") == 2, "须提供带中文写作层的v2候选")
    require(document.get("research_protocol") in (None, PROTOCOL), "未知的研究命题协议")
    require(
        document["provenance"]["mode"] == "ai"
        and document["provenance"]["template_calls"] == 0,
        "不是AI动态创作候选",
    )
    mode = document["paper"]["mode"]
    verify_design(root, document)
    if mode == "full" and uses_protocol(document):
        require_specialty_certificates(specialty_certificates)
    elif mode == "full":
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
    output.mkdir(parents=True)
    atomic_json(output / "raw-ai-candidate.json", document)
    presentation = {
        "title": document["paper"]["title"],
        "minutes": document["paper"]["minutes"],
        "total_points": document["paper"]["total_points"],
        "questions": [],
    }
    verification = []
    failures = []
    for q in document["questions"]:
        try:
            require("family" not in q, "禁止模板题目族伪装AI")
            student = compile_writing(q)
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
        require(
            fingerprint(compile_writing(q)) == fingerprint(visible),
            "写作文本已变化，必须回到题面核查",
        )
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
    require(
        fingerprint(read_json(folder / "raw-ai-candidate.json"))
        == cert["candidate_sha256"],
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


def publish(output, review_path, comparison_path):
    output = Path(output)
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
    for row, calculation in zip(reviews, calculations):
        if student["questions"][row["number"] - 1]["kind"] == "multiple_choice":
            given = row.get("answer_key") or []
            require(
                set(given) <= set("ABCD") and len(given) in (2, 3),
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
    shutil.copyfile(source, output / "paper.pdf")  # Byte-identical reviewed artifact.
    atomic_json(output / "student-review.json", review)
    atomic_json(output / "mathematical-comparison.json", comparison)
    cert = {
        **manifest,
        "published": True,
        "status": "独立AI考生审题及数学对照通过；教师与实测待审",
        "review_sha256": fingerprint(review),
        "mathematical_comparison_sha256": fingerprint(comparison),
        "formal_proof": False,
        "human_reviewed": False,
    }
    document = read_json(output / "raw-ai-candidate.json")
    solutions = {
        **student,
        "questions": [{k: v for k, v in q.items()} for q in student["questions"]],
    }
    byid = {q["id"]: q for q in document["questions"]}
    for q, reviewed in zip(solutions["questions"], reviews):
        revision = comparison.get("solution_revisions", {}).get(str(q["order"]))
        q["solution_paragraphs"] = (
            revision["paragraphs"]
            if revision
            else byid[q["id"]]["solution"]["paragraphs"]
        )
    render(solutions, output / "solutions.pdf", solutions=True)
    cert["solutions_sha256"] = digest(output / "solutions.pdf")
    atomic_json(output / "publication.json", cert)
    return cert
