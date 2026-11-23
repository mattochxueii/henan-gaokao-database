"""Conservative source-conflict gates, independent of parser success."""

import re

VERSION = "national-source-gate-v1"
QUARANTINED_PAPERS = {
    "2023-cn-math-national-b-science": {
        "reason": "已实际对照PDF发现多处条件、选项错误；全卷隔离，逐题修订前禁止作命题依据",
        "confirmed_different_numbers": [1, 2, 5, 8, 9, 11, 12, 13, 14, 16],
        "evidence": "reports/phase5-source-conflicts.md",
    }
}


def source_issues(paper_id, answer_text):
    issues = []
    if re.search(
        r"现稿|原PDF|无正确选项|题面修订|原题条件|原卷.{0,10}差异|版本差异|补充.{0,8}条件|题干.{0,8}缺|选项.{0,8}不匹配",
        answer_text,
    ):
        issues.append("upstream_version_note_requires_review")
    if paper_id in QUARANTINED_PAPERS:
        issues.append("quarantined_source_content_conflict")
    return issues


def research_eligible(row):
    if practice_reviewed(row):
        return True
    return not any(
        x in row.get("issues", [])
        for x in (
            "quarantined_source_content_conflict",
            "upstream_version_note_requires_review",
            "calibration_source_conflict",
        )
    )


def practice_reviewed(row):
    """A version-bound, practice-only disposition from comparison of two candidate page images."""
    review = row.get("practice_review") or {}
    return (set(row.get("issues", [])) == {"calibration_source_conflict"}
            and review.get("decision") == "usable_for_practice"
            and review.get("version_sha256") == row.get("version_sha256")
            and review.get("basis") == "visual_crosscheck")
