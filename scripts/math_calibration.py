"""Bind source reviews, repairs and original analyses to exact archived versions."""

import re

from analysis_db import fingerprint
from gaokao import digest, read_lines, relative_path, require

LEDGER = "national/research/calibration.jsonl"
ANALYSIS_FIELDS = (
    "knowledge",
    "methods",
    "competencies",
    "condition_design",
    "breakthrough",
    "solution_path",
    "computation",
    "misconception",
    "integration",
    "context",
    "progression",
    "difficulty",
    "related",
    "design_value",
)


def load(root):
    path = root / LEDGER
    result = {}
    if path.is_file():
        for row in read_lines(path):
            key = row["occurrence_id"]
            require(key not in result, "重复的真题复核记录：" + key)
            result[key] = row
    return result


def grade(row):
    """Separate source review, independent solution and known conflict."""
    if row.get("curation", {}).get("body_state") == "存在版本冲突":
        return "source_conflict"
    if any(
        issue in row.get("issues", [])
        for issue in (
            "quarantined_source_content_conflict",
            "upstream_version_note_requires_review",
            "calibration_source_conflict",
        )
    ):
        return "source_conflict"
    review = row.get("calibration", {})
    if review.get("body") in ("pdf_matched", "pdf_repaired"):
        return (
            "source_and_solution_reviewed"
            if review.get("answer") == "independently_solved"
            else "source_reviewed"
        )
    return "unreviewed"


def active_review(row, review, evidence_root, checked_sources):
    """Apply a scoped correction only with a valid base version and intact source bytes."""
    if review is None or review["base_version_sha256"] != row["version_sha256"]:
        return row
    source = review["source"]
    locator = row["source_locator"]
    if "pdf" in locator:
        anchors = {locator["pdf"]["path"]: locator["pdf"]["sha256"]}
    else:
        anchors = {f["path"]: f["sha256"] for f in locator.get("source_files", [])}
    path, expected = source["path"], source["sha256"]
    require(
        anchors.get(path) == expected and source["page"] > 0, "复核来源未绑定存档版本"
    )
    if (path, expected) not in checked_sources:
        file = relative_path(evidence_root, path)
        require(file.is_file() and digest(file) == expected, "复核来源文件缺失或已改变")
        checked_sources.add((path, expected))
    require(
        review["body"] in ("pdf_matched", "pdf_repaired", "pdf_conflict"),
        "非法题面复核状态",
    )
    require(
        review["answer"] in ("unreviewed", "independently_solved", "conflict"),
        "非法答案复核状态",
    )
    result = {**row, "calibration": review}
    if review["body"] == "pdf_conflict":
        return {
            **result,
            "issues": [*row.get("issues", []), "calibration_source_conflict"],
        }
    if review["body"] == "pdf_repaired":
        stem = row["stem"]
        for old, new in review["stem_edits"]:
            require(old and stem.count(old) == 1, "题面更正未命中唯一版本")
            stem = stem.replace(old, new, 1)
        require(stem != row["stem"], "题面未产生新版本")
        options = dict(row["options"])
        for key, old, new in review.get("option_edits", ()):
            require(options.get(key) == old, "选项更正未命中原文")
            options[key] = new
        version_material = {
            "base": row["version_sha256"],
            "stem": stem,
            "pdf": expected,
        }
        if options != row["options"]:
            version_material["options"] = options
        result.update(
            stem=stem,
            options=options,
            base_version_sha256=row["version_sha256"],
            version_sha256=fingerprint(version_material),
            source_locator={**locator, "calibrated_pdf_page": source["page"]},
            answer=None,
        )
        for key in (
            "raw_problem_latex",
            "searchable_analysis",
            "national_analysis",
            "candidate",
            "analysis",
        ):
            result.pop(key, None)
        result["formulas"] = [
            a or b
            for a, b in re.findall(
                r"\\\((.*?)\\\)|\\\[(.*?)\\\]",
                "\n".join((stem, *options.values())),
                re.S,
            )
        ]
        if review.get("remove_editorial_assets"):
            result["asset_refs"] = []
    if review["answer"] == "independently_solved":
        require(
            review.get("solution") and review.get("result"), "独立复核缺少推导或结果"
        )
        result["reviewed_answer"] = {
            "question_version_sha256": result["version_sha256"],
            "reference_answer": review["result"],
            "explanation": review["solution"],
            "status": "独立AI重解；非官方答案",
            "authority": "independent_ai_review",
        }
        if (
            review["body"] == "pdf_repaired"
            or review.get("answer_disposition") == "replace"
        ):
            result["answer"] = result["reviewed_answer"]
    if analysis := review.get("deep_analysis"):
        require(all(analysis.get(key) for key in ANALYSIS_FIELDS), "深度分析字段不完整")
        result["deep_analysis"] = {
            **analysis,
            "version_sha256": result["version_sha256"],
            "evidence": source,
            "human_reviewed": False,
            "classification": "content_based_editorial_inference",
        }
    return result


def apply(root, data):
    records = load(root)
    if not records:
        return data
    from national_db import private_folder
    from storage import reference_directory

    folders = {False: private_folder(root)}
    if any(row["legacy"] and row["occurrence_id"] in records for row in data):
        folders[True] = reference_directory(root)
    checked = {False: set(), True: set()}
    return [
        active_review(
            row,
            records.get(row["occurrence_id"]),
            folders.get(row["legacy"]),
            checked[row["legacy"]],
        )
        for row in data
    ]
