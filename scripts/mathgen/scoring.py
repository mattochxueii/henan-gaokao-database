"""Version-bound project marking guides for original practice papers."""

from analysis_db import fingerprint
from gaokao import digest, read_json, require
from storage import atomic_json


def scoring_by_number(document, guide):
    require(guide.get("authority") == "project", "评分细则必须标为项目自拟")
    rows = guide["questions"]
    questions = document["questions"]
    require(
        [r["number"] for r in rows] == [q["order"] for q in questions],
        "评分题号缺失或错序",
    )
    for row, q in zip(rows, questions):
        steps = row["steps"]
        require(
            steps and all(
                type(step["points"]) is int and step["points"] > 0
                and isinstance(step["criterion"], str) and step["criterion"].strip()
                for step in steps
            ) and sum(step["points"] for step in steps) == q["points"],
            "评分步骤必须具体且总分正确",
        )
        if q["kind"] == "constructed_response":
            parts = len(q["writing"]["parts"])
            require(
                len(steps) > parts
                and {step.get("part") for step in steps} == set(range(1, parts + 1)),
                "解答题每一问须有具体评分步骤",
            )
            if document["paper"].get("require_scoring"):
                require(
                    [sum(s["points"] for s in steps if s["part"] == n)
                     for n in range(1, parts + 1)] == q["assessment"]["part_points"],
                    "评分细则与各问分值不一致",
                )
    return {r["number"]: r for r in rows}


def solution_book(student, document, revisions, guide=None, *, answer_keys=None):
    from core.marking_standards import math_choice

    rubric = scoring_by_number(document, guide) if guide is not None else {}
    solutions = []
    for visible, authored in zip(student["questions"], document["questions"], strict=True):
        require(visible["id"] == authored["id"], "解析与题面不匹配")
        number = visible["order"]
        updated = revisions.get(str(number))
        paragraphs = updated["paragraphs"] if updated else authored["solution"]["paragraphs"]
        require(paragraphs and all(p.strip() for p in paragraphs), "解析正文缺失")
        if authored.get("trend_basis"):
            card = authored["trend_basis"]
            labels = "、".join(card["evidence"])
            paragraphs = [*paragraphs, f"【命题依据卡】{card['strength']}。证据编号 {labels}。",
                          f"本题避开“{card['surface']}”的表层套路。{card['retained']}",
                          card["difference"]]
        if student.get("release_rules") and visible["kind"].endswith("_choice"):
            paragraphs = [*paragraphs, math_choice(visible["kind"], answer_keys[number-1], visible["points"])]
        elif visible["kind"] == "fill_in":
            paragraphs = [*paragraphs, f"答对得{visible['points']}分，答错或不答得0分。"]
        elif guide is not None:
            paragraphs = list(paragraphs)
            for step in rubric[number]["steps"]:
                part = f"（{step['part']}）" if step.get("part") else ""
                paragraphs.append(f"评分{part}　{step['points']}分　{step['criterion']}")
        solutions.append({**visible, "solution_paragraphs": paragraphs})
    return {**student, "questions": solutions}


def render_edition(source, edition, output):
    from .exam_workflow import verify_certificate
    from .student_pdf import render

    cert = read_json(source / "publication.json")
    verify_certificate(source, cert)
    require(edition["paper_sha256"] == cert["pdf_sha256"], "评分解析对应其他卷面")
    require(not output.exists(), "请使用新的评分解析目录")
    raw = read_json(source / "raw-ai-candidate.json")
    comparison = read_json(source / "mathematical-comparison.json")
    revisions = {**comparison.get("solution_revisions", {}), **edition.get("solution_revisions", {})}
    visible=read_json(source/"student-text.json")
    keys=None
    if visible.get("release_rules"):
        reviewed=read_json(source/"student-review.json")
        keys=[q.get("answer_key") for q in reviewed["questions"]]
        keys=["".join(key) if isinstance(key,list) else key for key in keys]
    book = solution_book(visible, raw, revisions, edition, answer_keys=keys)
    output.mkdir(parents=True)
    pdf = render(book, output / "solutions.pdf", solutions=True)
    result = {
        "paper_sha256": cert["pdf_sha256"], "source_certificate_sha256": fingerprint(cert),
        "solutions_sha256": digest(pdf), "edition_sha256": fingerprint(edition),
        "authority": "project",
    }
    atomic_json(output / "scoring.json", edition)
    atomic_json(output / "solution-edition.json", result)
    return result
