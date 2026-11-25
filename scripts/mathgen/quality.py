"""Verification gates, expression parsing, and provenance checks."""

import ast
from difflib import SequenceMatcher
import re
import sympy as s

from analysis_db import fingerprint
from .generate import draft, add_options
from .solve import solve

SYMBOLS = {
    "n": s.Symbol("n", integer=True, positive=True),
    "k": s.Symbol("k", integer=True, positive=True),
    "c": s.Symbol("c", positive=True),
    "h": s.Symbol("h", positive=True),
    "pi": s.pi,
    "x": s.Symbol("x", real=True),
}


def equation_cardinality(left, right="0"):
    roots = s.solveset(
        expression(left) - expression(right), SYMBOLS["x"], domain=s.S.Reals
    )
    if roots is s.S.EmptySet:
        return {"state": "no_solution", "roots": []}
    if isinstance(roots, s.FiniteSet):
        return {
            "state": "unique" if len(roots) == 1 else "multiple",
            "roots": [str(v) for v in roots],
        }
    return {"state": "infinite_or_unresolved", "roots": str(roots)}


def expression(text):
    """Small arithmetic grammar. Never evaluate Python or unrestricted sympify."""
    tree = ast.parse(text, mode="eval")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return s.Rational(str(node.value))
        if isinstance(node, ast.Name) and node.id in SYMBOLS:
            return SYMBOLS[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                if right.is_number and abs(right) > 1000:
                    raise ValueError("指数超过验证限制")
                return left**right
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and len(node.args) == 1
            and not node.keywords
        ):
            functions = {"sqrt": s.sqrt, "log": s.log, "exp": s.exp}
            if node.func.id in functions:
                return functions[node.func.id](visit(node.args[0]))
        raise ValueError("公式含不允许的结构")

    if len(text) > 2000:
        raise ValueError("公式长度超过限制")
    return visit(tree.body)


def normalize(text):
    # Remove instructions while retaining mathematical operators and structure.
    for instruction in (
        "判断下列命题，选择所有正确选项。",
        "选择所有正确命题。",
        "判断成立的命题。",
    ):
        text = text.replace(instruction, "")
    text = re.sub(r"\d+(?:\.\d+)?", "#", text)
    text = re.sub(r"\b[A-Za-z]\b", "v", text)
    return re.sub(r"[\s，。；：,.()\[\]]+", "", text)


def duplicate_check(question, originals, peers=()):
    text = normalize(question["stem"])
    candidates = [(q["id"], q["candidate"]["stem"]) for q in originals]
    candidates += [(q["id"], q["stem"]) for q in peers]
    scores = [
        {
            "id": key,
            "score": round(SequenceMatcher(None, text, normalize(stem)).ratio(), 4),
        }
        for key, stem in candidates
    ]
    closest = max(
        scores, key=lambda item: item["score"], default={"id": None, "score": 0}
    )
    return {
        "closest": closest,
        "threshold": 0.78,
        "passed": closest["score"] < 0.78,
        "method": "去除通用作答提示、归一化数字与单字母，保留数学结构后比较顺序相似度",
        "limitation": "局部文本检测，不能证明全球原创性；题目族设计须另经推理审查",
    }


def verify(question):
    family = question["family"]
    expected = draft(
        family, question["generation"]["seed"], question["kind"], question["points"]
    )
    expected = add_options(expected, question["generation"]["seed"] + 1)
    # Ensure the visible question and semantic parameters describe the same item.
    canonical = all(
        question[key] == expected[key] for key in ("stem", "parameters", "options")
    )
    solved = solve(family, question["parameters"])
    proposed = [expression(text) for text in question["proposed_values"]]
    actual = solved["values"]
    match = len(proposed) == len(actual) and all(
        s.simplify(a - b) == 0 for a, b in zip(proposed, actual)
    )
    option_key = None
    valid_options = True
    if question["kind"] == "single_choice":
        truth = {
            key: s.simplify(expression(value["semantic_value"]) - actual[0]) == 0
            for key, value in question["options"].items()
        }
        valid_options = sum(truth.values()) == 1
        option_key = "".join(key for key, value in truth.items() if value)
    elif question["kind"] == "multiple_choice":
        if family in ("geometry_assertions", "logquad_assertions"):
            mask = [bool(v) for v in actual]
        elif family == "seq_interlace":
            mask = [True, False, True, False]
        elif family == "variance":
            mask = [True, True, False, False]
        else:
            raise ValueError("该题目族尚无独立多选命题求解器")
        valid_options = (
            sum(mask) >= 2
            and sum(mask) < 4
            and [int(v) for v in mask] == question["proposal_truth_mask"]
        )
        option_key = "".join(key for key, value in zip("ABCD", mask) if value)
    passed = canonical and match and all(solved["checks"]) and valid_options
    return {
        "question_sha256": fingerprint(question),
        "passed": passed,
        "status": "symbolic_checks_and_reasoning_review"
        if solved["reasoning_review_required"]
        else "programmatically_verified",
        "canonical_text_matches_spec": canonical,
        "proposal_matches_independent_solution": match,
        "option_count_valid": valid_options,
        "option_key": option_key,
        "values": [str(v) for v in actual],
        "values_latex": [s.latex(v) for v in actual],
        "steps": solved["steps"],
        "program_checks": solved["checks"],
        "engine": "SymPy " + s.__version__,
        "verification_revision": "solver-v1",
        "remaining_uncertainty": "全域符号证明的文字推理已经AI复核，尚无人类盲审与考生实测"
        if solved["reasoning_review_required"]
        else "程序仅验证当前数学规格及标准题面，未证明教育测量质量",
        "independence": "独立求解函数仅接收题目族和参数，不能读取草稿答案；与生成器使用不同计算路径",
        "reasoning_review": {
            "reviewer": "Codex",
            "model_version": "not_exposed_by_host",
            "independent_human": False,
        },
    }


def assert_fresh(question, verification):
    if (
        fingerprint(question) != verification["question_sha256"]
        or not verification["passed"]
    ):
        raise ValueError("题目修改或验证失败，必须重新求解")
