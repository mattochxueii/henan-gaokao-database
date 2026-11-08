"""Prepare answer-free AI writing requests and attach a separately authored writing layer."""

import copy
from analysis_db import fingerprint
from gaokao import require
from .editorial import compile_writing


def request(document, rules):
    questions = []
    for q in document["questions"]:
        spec = copy.deepcopy(q["math_spec"])
        if spec.get("options"):
            spec["options"] = {
                k: {"semantic_value": v["semantic_value"]}
                for k, v in spec["options"].items()
            }
        questions.append(
            {
                "id": q["id"],
                "kind": q["kind"],
                "points": q["points"],
                "math_spec": spec,
                "original_spec_sha256": fingerprint(q["math_spec"]),
            }
        )
    return {
        "version": "AI-school-writing-request-v1",
        "questions": questions,
        "language_rules": rules,
        "instructions": "逐题只写自然中文的条件与设问，用formulae形成常用高中记号。不得添加解题提示、结果或验证术语。输出writing字段并绑定original_spec_sha256。"
        "条件、顺序、放回与定义域不能为简练而改变。无法明确转换时退回，不输出AST。",
        "proposer_answers_included": False,
        "proposer_design_included": False,
    }


def attach(document, response):
    result = copy.deepcopy(document)
    byid = {row["id"]: row for row in response["questions"]}
    require(
        set(byid) == {q["id"] for q in result["questions"]},
        "写作结果漏题或混入其他试卷",
    )
    for q in result["questions"]:
        q["writing"] = byid[q["id"]]["writing"]
        require(
            q["writing"]["spec_sha256"] == fingerprint(q["math_spec"]),
            "写作层不对应本版数学条件",
        )
        compile_writing(q)
    return result
