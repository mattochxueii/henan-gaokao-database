"""Structured comparisons with explicit limits on the originality claim."""

import ast
from collections import Counter
from difflib import SequenceMatcher
from analysis_db import fingerprint
from .dynamic import structural_signature
from .quality import normalize


def features(question):
    problem = question["problem"]
    tasks = problem.get("tasks", []) + list(problem.get("assertions", {}).values())
    return {
        "condition_structure": [sorted(t.keys()) for t in tasks],
        "mathematical_operations": [
            t["op"] + ":" + str(t.get("operation", t.get("ask", ""))) for t in tasks
        ],
        "reasoning_path": question["design"]["reasoning_path"],
        "knowledge_combination": question["design"]["knowledge_combination"],
        "setting_and_ask": problem.get("context", ""),
        "structure_sha256": structural_signature(question),
    }


def compare(left, right):
    a, b = features(left), features(right)
    same = a["structure_sha256"] == b["structure_sha256"]
    operations_a = set(a["mathematical_operations"])
    operations_b = set(b["mathematical_operations"])
    overlap = len(operations_a & operations_b) / max(
        1, len(operations_a | operations_b)
    )
    knowledge = len(
        set(a["knowledge_combination"]) & set(b["knowledge_combination"])
    ) / max(1, len(set(a["knowledge_combination"]) | set(b["knowledge_combination"])))
    text = SequenceMatcher(
        None, normalize(a["setting_and_ask"]), normalize(b["setting_and_ask"])
    ).ratio()
    return {
        "same_structure_after_erasing_numbers": same,
        "operation_overlap": round(overlap, 3),
        "knowledge_overlap": round(knowledge, 3),
        "setting_similarity": round(text, 3),
        "classification": "同结构仅改参数，不能视作高创新"
        if same
        else "结构存在差异，仍需专家判断创新程度",
        "left": left["id"],
        "right": right["id"],
    }


def cohort_report(question, pool, analyses):
    comparisons = [
        compare(question, other) for other in pool if other["id"] != question["id"]
    ]
    strongest = max(
        comparisons,
        key=lambda c: (
            c["same_structure_after_erasing_numbers"],
            c["operation_overlap"],
            c["knowledge_overlap"],
        ),
        default=None,
    )
    evidence = [
        {
            "question_id": r["question_id"],
            "candidate_sha256": r["candidate_sha256"],
            "common_method": r["key_idea"],
            "module": r["knowledge"]["module"],
        }
        for r in analyses
        if r["knowledge"]["module"] == question["module"]
    ]
    return {
        "question_id": question["id"],
        "features": features(question),
        "closest_new_item": strongest,
        "source_method_comparisons": evidence,
        "generation_mode": "ai",
        "basis": "表达式AST消除数值、任务依赖、核心运算、知识组合、情境与问法联合检查",
        "limitations": [
            "原始真题尚无统一语义AST，跨真题比较依赖版本绑定的知识与方法分析",
            "经典方法可以重用，结构不同不等于高创新",
            "未检索全网，不能证明首次出现",
        ],
    }


def paper_difference(a, b):
    comparisons = [compare(x, y) for x, y in zip(a["questions"], b["questions"])]
    equal = sum(c["same_structure_after_erasing_numbers"] for c in comparisons)
    module_changes = sum(
        x["module"] != y["module"] for x, y in zip(a["questions"], b["questions"])
    )
    signatures_a = {structural_signature(q) for q in a["questions"]}
    signatures_b = {structural_signature(q) for q in b["questions"]}
    jaccard = len(signatures_a & signatures_b) / max(
        1, len(signatures_a | signatures_b)
    )
    return {
        "passed": equal <= len(comparisons) // 2
        and module_changes >= 5
        and jaccard < 0.5,
        "same_slot_same_structure": equal,
        "module_position_changes": module_changes,
        "structure_set_overlap": round(jaccard, 4),
        "slot_comparisons": comparisons,
        "claim": "比较数学图和知识搭配，不能以随机种子变化作为差异证据",
    }
