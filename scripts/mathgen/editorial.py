"""AI writing is a separate artifact, bound to the mathematical specification."""

import re
import ast
from analysis_db import fingerprint
from gaokao import require
from .notation import latex

VERSION = "student-writing-v1"
KINDS = {"single_choice", "multiple_choice", "fill_in", "constructed_response"}
BANNED = (
    "目标事件",
    "有序结果数",
    "指定值",
    "附加限制",
    "独立求解",
    "数学规格",
    "逐项代入条件",
    "SymPy",
    "Interval(",
    "True",
    "False",
    "task_refs",
    "semantic_value",
    "选择所有正确命题",
)
HINTS = (
    "试用",
    "利用错位相减",
    "可用变换",
    "通过换元",
    "注意分子",
    "须同时注意",
    "先确定",
    "再研究",
    "消去非齐次",
    "利用恒等式",
)
TOKEN = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")


def text_content(writing):
    return "\n".join(
        [
            writing["stem"],
            *(p["text"] for p in writing.get("parts", [])),
            *writing.get("options", {}).values(),
        ]
    )


def compile_writing(question):
    spec = question["math_spec"]
    writing = question["writing"]
    require(writing.get("spec_sha256") == fingerprint(spec), "内部规格与题面绑定已失效")
    raw = text_content(writing)
    definitions = writing.get("definitions", [])
    require(
        bool(writing.get("condition_anchors")) and bool(writing.get("request_anchors")),
        "条件/设问清单缺失",
    )
    for anchor in writing["condition_anchors"] + writing["request_anchors"]:
        require(anchor in raw, "必要条件或答题要求缺失：" + anchor)
    require(question["kind"] in KINDS, "题型无效")
    for item in definitions:
        require(item["anchor"] in raw and item["symbol"], "记号未定义")
    known = {x["symbol"] for x in definitions}
    require(set(writing.get("used_symbols", [])) <= known, "存在未定义符号")
    formulae = writing.get("formulae", {})
    used = set(TOKEN.findall(raw))
    require(used == set(formulae), "公式遗漏或无关公式")
    snippets = {}
    for name, entry in formulae.items():
        if entry.get("kind") == "notation":
            value = entry["latex"]
            require(
                not any(
                    c in value for c in ("**", "factorial(", "sqrt(", "log(", "u(")
                ),
                "不允许原始程序记号",
            )
            require(
                len(value) < 500
                and not re.search(r"\\(?:land|lor|wedge|vee|operatorname)", value),
                "记号公式含程序逻辑",
            )
        else:
            path = entry.get("given")
            require(path in spec.get("givens", {}), "公式缺少原始条件来源")
            require(entry["source"] == spec["givens"][path], "公式与条件语义不一致")
            names = {
                n.id
                for n in ast.walk(ast.parse(entry["source"], mode="eval"))
                if isinstance(n, ast.Name)
            }
            allowed = {
                "I",
                "E",
                "pi",
                "oo",
                "sqrt",
                "abs",
                "factorial",
                "binomial",
                "sin",
                "cos",
                "tan",
                "log",
                "exp",
            }
            require(
                names <= known | allowed,
                "公式存在未定义符号：" + str(names - known - allowed),
            )
            value = latex(entry["source"])
        snippets[name] = r"\(" + value + r"\)"

    def substitute(text):
        require(
            r"\(" not in text and r"\)" not in text,
            "公式须进入已绑定的写作公式表，禁止旁路",
        )
        require(
            not any(word in text for word in BANNED + HINTS),
            "题面泄漏程序术语或解题路径",
        )
        require(
            not re.search(
                r"(?:sqrt|factorial|log|u)\s*\(|\*\*|==|!=|\\(?:land|lor|wedge|vee)",
                text,
            ),
            "题面泄漏内部表达式",
        )
        require(text.count(r"\(") == text.count(r"\)"), "公式边界错误")
        require(
            not re.search(r"\([^()\n]{0,40}\([^()\n]{0,40}\([^()\n]{0,40}\(", text),
            "不必要嵌套括号",
        )
        return TOKEN.sub(lambda m: snippets[m.group(1)], text)

    stem = substitute(writing["stem"])
    parts = []
    for i, part in enumerate(writing.get("parts", []), 1):
        require(
            part.get("task_refs")
            and all(0 <= v < len(spec.get("tasks", [])) for v in part["task_refs"]),
            "设问未对应验证任务",
        )
        parts.append({"label": f"（{i}）", "text": substitute(part["text"])})
        for task_index in part["task_refs"]:
            op = spec["tasks"][task_index]["op"]
            if op == "sum":
                require(
                    "和" in parts[-1]["text"] or r"\sum" in parts[-1]["text"],
                    "内部求和与中文设问不一致",
                )
            if op == "product":
                require(
                    "积" in parts[-1]["text"] or r"\prod" in parts[-1]["text"],
                    "内部求积与中文设问不一致",
                )
            if op in ("sum", "recurrence_sum"):
                require("乘积" not in parts[-1]["text"], "内部求和与中文求积冲突")
    options = {k: substitute(v) for k, v in writing.get("options", {}).items()}
    if question["kind"] in ("single_choice", "multiple_choice"):
        require(set(options) == set("ABCD") and not parts, "选择题选项/设问格式无效")
        require(
            not any(word in stem for word in ("证明", "写出过程", "说明理由")),
            "选择题与作答要求冲突",
        )
    elif question["kind"] == "constructed_response":
        require(len(parts) >= 2, "解答题需关联且递进的设问")
    else:
        require(not options, "非选择题混入选项")
    assessment = question["assessment"]
    require(
        assessment.get("points_justification")
        and len(assessment.get("dimensions", {})) >= 8,
        "分值难度依据不足",
    )
    if question["kind"] == "constructed_response":
        require(
            sum(assessment.get("part_points", [])) == question["points"],
            "子问分值不匹配",
        )
        require(assessment.get("linked_progression"), "解答题缺少递进关系")
        require(
            assessment.get("level", 0) >= 3 or question["points"] <= 10,
            "简单直接计算与高分冲突",
        )
    covered = set()
    for part in writing.get("parts", []):
        covered.update(part["task_refs"])
    if parts:
        require(covered == set(range(len(spec["tasks"]))), "有验证任务未对应设问")
    result = {
        "id": question["id"],
        "order": question["order"],
        "kind": question["kind"],
        "points": question["points"],
        "stem": stem,
        "parts": parts,
        "options": options,
        "figure": writing.get("figure"),
    }
    return result
