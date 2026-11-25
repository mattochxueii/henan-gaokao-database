"""Paper-position and structural gates for new, independently reviewed exams."""

import ast
from collections import defaultdict
from itertools import combinations
import re
import sympy as s

from analysis_db import fingerprint
from gaokao import require
from .ai_spec import parse

VERSION = "paper-quality-v1"
MOVES = {
    "recall", "substitute", "routine_algebra", "routine_calculus",
    "representation", "restrict_domain", "model", "compare",
    "branch", "invariant", "counterexample", "necessity", "sufficiency",
    "endpoint", "optimality", "construct",
}
ROUTINE = {"recall", "substitute", "routine_algebra", "routine_calculus"}
DEMANDING = {"branch", "invariant", "counterexample", "necessity", "sufficiency",
             "endpoint", "optimality", "construct"}
ROLES = {"foundation": 1, "transfer": 2, "challenge": 3}
SCORE_ENDPOINTS = (13, 17)


def expression_key(expression, *, equation=False):
    """Canonicalise common school expressions, including scaled polynomial equations."""
    if equation:
        left, sep, right = expression.partition("=")
        expr = parse(left) - parse(right) if sep else parse(left)
        try:
            expr = s.Poly(expr, *sorted(expr.free_symbols, key=str)).monic().as_expr()
        except (s.PolynomialError, IndexError, ZeroDivisionError):
            expr = s.factor(s.expand_trig(expr))
            if expr.could_extract_minus_sign():
                expr = -expr
    else:
        expr = s.trigsimp(parse(expression))
    return s.srepr(expr)


def visible_equations(question):
    """Recognise displayed conic equations without depending on author's tags."""
    keys = set()
    for formula in question["writing"]["formulae"].values():
        latex = formula.get("latex", "")
        latex = re.sub(r"\\frac\s*\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", latex)
        latex = re.sub(r"\\frac\s*([xy]\^2)\{?([0-9]+)\}?", r"(\1)/(\2)", latex)
        latex = re.sub(r"([xy])\^\{2\}", r"\1^2", latex)
        latex = re.sub(r"\s+", "", latex).replace("xy", "x*y")
        latex = re.sub(r"(?<=[0-9)])(?=[xy])", "*", latex)
        if not re.fullmatch(r"[xy0-9().+*/^=-]+", latex) or "=" not in latex:
            continue
        if not {"x", "y"} <= set(latex) or ("^2" not in latex and "x*y" not in latex):
            continue
        try:
            keys.add(("equation", expression_key(latex.replace("^", "**"), equation=True)))
        except (ValueError, TypeError, SyntaxError):
            continue
    return keys


def objects(question):
    structures = question["placement"]["structures"]
    exact = visible_equations(question)
    for obj in structures.get("objects", []):
        kind, expression = obj["kind"], obj["expression"]
        require(kind in ("equation", "function", "recurrence", "finite_model")
                and isinstance(expression, str) and expression.strip(), "数学对象签名无效")
        if kind == "finite_model":
            key = expression
        else:
            key = expression_key(expression, equation=kind in {"equation", "recurrence"})
        exact.add((kind, key))
    return exact


def task_shape(question):
    tasks = question.get("math_spec", {}).get("tasks", [])
    if len(tasks) != 1 or tasks[0].get("op") not in {
        "equation", "root_count", "extrema", "monotonicity_boolean", "derivative",
    }:
        return None
    task = tasks[0]
    expression = task.get("expression")
    if not isinstance(expression, str):
        return None
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) < 10:
        return None

    class Parameters(ast.NodeTransformer):
        def visit_Constant(self, node):
            if type(node.value) in (int, float):
                return ast.Name(id="_parameter", ctx=ast.Load())
            return node

        def visit_BinOp(self, node):
            if isinstance(node.op, ast.Pow):
                node.left = self.visit(node.left)
                return node
            return self.generic_visit(node)

    return task["op"], ast.dump(Parameters().visit(tree))


def structure_conflicts(questions):
    signatures = []
    for q in questions:
        obj = q["placement"]["structures"]
        require(all(isinstance(obj.get(k), str) and obj[k].strip()
                    for k in ("model", "goal")), "缺少结构模型或推理目标")
        require(isinstance(obj.get("route"), list) and obj["route"]
                and all(isinstance(k, str) and k.strip() for k in obj["route"]),
                "缺少有序的关键转化")
        signatures.append((q["order"], obj, objects(q), task_shape(q)))
    pairs = []
    for (a, x, left, lshape), (b, y, right, rshape) in combinations(signatures, 2):
        shared = left & right
        same_route = x["route"] == y["route"] and (
            x["model"] == y["model"] and x["goal"] == y["goal"]
            or len(x["route"]) >= 2 and x["model"] == y["model"]
        )
        scaled_task = lshape is not None and lshape == rshape and x["goal"] == y["goal"]
        if shared or same_route or scaled_task:
            pairs.append({"numbers": [a, b],
                          "same_object": sorted(key for _, key in shared),
                          "repeated_route": same_route, "parameter_only_task_shape": scaled_task})
    return pairs


def reasoning_profile(moves):
    """Credit linked reasoning with mathematical evidence; routine steps stay routine."""
    require(isinstance(moves, list) and moves, "缺少独立解题步骤")
    profiles = []
    demanding_kinds = set()
    for step in moves:
        kind = step["kind"]
        predecessors = step.get("after", [])
        routine = step.get("routine", False)
        require(kind in MOVES and isinstance(step.get("evidence"), str)
                and step["evidence"].strip() and type(routine) is bool, "缺少可复查的推理步骤")
        require(isinstance(predecessors, list)
                and all(type(n) is int and 1 <= n <= len(profiles) for n in predecessors),
                "推理依赖须指向之前的步骤")
        prior = max((profiles[n - 1] for n in predecessors), default=0)
        profiles.append(prior + (kind not in ROUTINE and not routine))
        if not routine and kind in DEMANDING:
            demanding_kinds.add(kind)
    depth = max(profiles)
    demanding = len(demanding_kinds)
    band = 1 if depth == 0 else 2
    if depth >= 2 and demanding:
        band = 3
    if depth >= 3 and demanding >= 2:
        band = 4
    return {"band": band, "linked_depth": depth, "distinct_demanding_moves": demanding}


def placement_report(document, review, plan=None):
    """Run the same position gate on a plan and on independently observed routes."""
    independently_reviewed = review is not None
    by_kind = defaultdict(list)
    planned = document["questions"]
    require(all(isinstance(q.get("placement"), dict) for q in planned), "整卷缺少逐题题位计划")
    examined = review["questions"] if independently_reviewed else [
        {"number": q["order"], **q["placement"]} for q in planned
    ]
    require([r["number"] for r in examined] == [q["order"] for q in planned],
            "整卷审核须覆盖所有题位")
    rows, failures = [], []
    for q, observed in zip(planned, examined, strict=True):
        position = q["placement"]
        role = position["role"]
        require(role in ROLES and isinstance(position.get("purpose"), str)
                and position["purpose"].strip(), "缺少题位功能")
        expected = reasoning_profile(position["moves"])
        result = reasoning_profile(observed["moves"])
        band = result["band"]
        min_minutes, max_minutes = observed["minutes"]
        require(type(min_minutes) is int and type(max_minutes) is int
                and 0 < min_minutes <= max_minutes, "仅接受带范围的编辑估时")
        if band < ROLES[role]:
            failures.append({"reason": "position_role_mismatch", "numbers": [q["order"]]})
        if q["kind"] == "constructed_response":
            minimum = 4 if q["points"] >= SCORE_ENDPOINTS[1] else 3
            if q["points"] >= SCORE_ENDPOINTS[0] and band < minimum:
                failures.append({"reason": "high_marks_shallow_reasoning", "numbers": [q["order"]]})
        by_kind[q["kind"]].append((q["order"], band))
        rows.append({"number": q["order"], "role": role, "band": band,
                     "minutes": [min_minutes, max_minutes], "planned": expected, **result})
    if document["paper"]["mode"] == "full":
        for section in by_kind.values():
            if len(section) < 3:
                continue
            tail = section[-min(3, len(section)):]
            bands = [b for _, b in tail]
            if max(bands) < 3 or sum(b >= 2 for b in bands) < 2:
                failures.append({"reason": "section_tail_flat", "numbers": [n for n, _ in tail]})
        if len({row["band"] for row in rows}) < 3:
            failures.append({"reason": "paper_gradient_flat", "numbers": []})
        lower = sum(row["minutes"][0] for row in rows)
        upper = sum(row["minutes"][1] for row in rows)
        minutes = document["paper"]["minutes"]
        if lower > minutes or upper * 2 < minutes:
            failures.append({"reason": "time_range_implausible", "numbers": []})
    else:
        lower = sum(row["minutes"][0] for row in rows)
        upper = sum(row["minutes"][1] for row in rows)
    conflicts = structure_conflicts(planned)
    allowed = {}
    if independently_reviewed:
        allowed = {tuple(r["numbers"]): r for r in review.get("intentional_links", [])}
    for pair in conflicts:
        link = allowed.get(tuple(pair["numbers"]), {})
        authorised = (link.get("necessary") is True and link.get("evidence")
                      and pair["numbers"] in document.get("coverage_plan", {}).get("intentional_links", []))
        if not authorised and (independently_reviewed or pair["numbers"] not in
                               document.get("coverage_plan", {}).get("intentional_links", [])):
            failures.append({"reason": "structural_repetition", **pair})
    result = {"version": VERSION, "items": rows, "conflicts": conflicts, "failures": failures,
              "candidate_sha256": fingerprint(document), "estimated_minutes": [lower, upper],
              "time_basis": "editorial_range_without_student_data",
              "scope": "题位推理与计划对照；编辑估时与层级不代表真实得分、区分度或作答时间。"}
    if plan is not None:
        require(plan["candidate_sha256"] == result["candidate_sha256"], "题位方案已过期")
    return result


def verify_position_review(document, review, manifest, plan):
    require(review.get("pdf_sha256") == manifest["pdf_sha256"]
            and review.get("student_review_independent") is True
            and review.get("empirical") is False, "整卷审核须绑定已审学生卷面与估时范围")
    result = placement_report(document, review, plan)
    require(not result["failures"], "整卷题位或数学结构审核未通过：" + str(result["failures"]))
    return result


def assess_external(claim, *, independent_answer=None, actual_students=0,
                    concrete_evidence=None, observed_fact=None):
    """Keep observable claims and editorial judgements separate."""
    kind = claim["kind"]
    if kind == "answer":
        require(independent_answer is not None, "数学答案须独立求出")
        proposed = parse(claim["value"])
        verified = parse(independent_answer)
        return "数学事实成立" if s.simplify(proposed - verified) == 0 else "数学事实错误"
    if kind == "empirical":
        return "暂时无法确认" if actual_students else "主观判断，证据不足"
    if kind == "observed":
        return ("暂时无法确认" if observed_fact is None else
                "数学事实成立" if observed_fact else "数学事实错误")
    require(kind == "editorial", "未知审稿意见类别")
    return "有具体依据的命题质量问题" if concrete_evidence else "主观判断，证据不足"
