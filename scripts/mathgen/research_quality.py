"""Research design and separate blind quality requirements for calibrated papers."""

from pathlib import Path

from gaokao import read_json, require

PROTOCOL = "calibrated-v1"
DIMENSIONS = (
    "concept_depth",
    "reasoning",
    "model",
    "breakthrough",
    "flexibility",
    "progression",
    "computation",
    "reading",
    "points",
    "originality",
)


def uses_protocol(document):
    return document.get("research_protocol") == PROTOCOL


def verify_design(root, document):
    if not uses_protocol(document):
        return
    from math_calibration import grade
    from national_db import rows

    by_id = {
        row["occurrence_id"]: row
        for row in rows(root)
        if grade(row) == "source_and_solution_reviewed"
    }
    for question in document["questions"]:
        design = question.get("research_design", {})
        refs = design.get("references", [])
        require(
            refs and design.get("novel_structure") and design.get("reasoning_target"),
            "逐题须说明新结构、推理目标和真题依据",
        )
        for ref in refs:
            row = by_id.get(ref["occurrence_id"])
            require(
                row and row["version_sha256"] == ref["version_sha256"],
                "真题依据未复核或版本变化",
            )
            require(
                ref.get("transfer") and ref.get("structural_difference"),
                "缺少命题机制及结构差异说明",
            )


def verify_blind_quality(document, review):
    if not uses_protocol(document):
        return
    for row in review["questions"]:
        quality = row.get("quality", {})
        require(set(quality) == set(DIMENSIONS), "盲审质量维度不完整")
        require(
            all(type(score) is int and 0 <= score <= 2 for score in quality.values()),
            "质量评分须为0至2",
        )
        floor = 10 if document["paper"]["mode"] == "full" and row["number"] <= 4 else 13
        require(
            sum(quality.values()) >= floor
            and all(quality[key] >= 1 for key in ("reasoning", "reading", "points")),
            "专项质量未达到预设门槛",
        )
        require(row.get("quality_evidence"), "盲审质量结论须有具体依据")


def require_specialty_certificates(paths):
    from .exam_workflow import verify_certificate

    groups = set()
    for path in paths:
        folder = Path(path).parent
        document = read_json(folder / "raw-ai-candidate.json")
        cert = read_json(path)
        require(
            uses_protocol(document)
            and cert.get("published") is True
            and cert["question_count"] == 5
            and cert["kind"] == "pilot",
            "整卷仅接受已通过校准流程的五题专项卷",
        )
        verify_certificate(folder, cert)
        verify_blind_quality(document, read_json(folder / "student-review.json"))
        modules = {question["module"] for question in document["questions"]}
        require(len(modules) == 1, "专项卷须按一个明确模块认证")
        groups.update(modules)
    require(
        len(paths) == 3 and groups == {"数列", "导数", "解析几何"},
        "数列、导数、解析几何三个专项均须通过后才可生成整卷",
    )
