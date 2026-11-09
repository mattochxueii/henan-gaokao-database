"""Host/API proposals -> mathematical specifications -> independent gates -> research papers."""

import ast
from collections import Counter
import json
import multiprocessing
import random
from pathlib import Path
import time
import sympy as s

from analysis_db import fingerprint
from gaokao import require, read_json
from storage import atomic_json
from .ai_spec import parse, solve_task, clean
from .ai_provider import HostAIProvider, OpenAIProvider
from .planner import plan, context
from .review import audit_item, MODULES

VERSION = "dynamic-pipeline-v3"
PROMPTS = {
    "evaluate": "计算下式的值",
    "equation": "在给定定义域内求方程的全部解",
    "system": "解方程组",
    "sum": "求有限和",
    "product": "求有限积",
    "recurrence": "求数列通项",
    "coefficient": "求展开式指定幂的系数",
    "derivative": "求导数",
    "extrema": "求最小值、最大值及取到的位置",
    "monotonicity": "求单调增减区间与驻点",
    "parameter_monotone": "求使函数在定义域内单调不减的参数范围",
    "parameter_bound": "求使下式在定义域内恒非负的参数范围",
    "nonnegative": "证明下式非负并讨论取等",
    "probability": "在等可能样本中求条件概率",
    "identity": "判断并证明恒等式",
    "comparison": "判断命题是否恒成立",
}
PROMPTS.update(
    {
        "recurrence_sum": "求递推数列的加权和",
        "root_count": "求方程在区间内不同实根的数量",
        "optimum": "求指定最值",
        "count": "求满足条件的有序结果数",
        "expectation": "求条件期望",
        "statistics": "求样本统计量",
        "vector": "计算或判断向量性质",
        "geometry": "求几何量",
        "intersection": "联立两曲线求指定交点量",
        "derivative_claim": "判断导数公式是否正确",
    }
)
PROMPTS.update(
    {
        "probability_claim": "判断给定概率是否正确",
        "point_on_curve": "判断点是否属于曲线",
    }
)


def maths(value):
    return r"\(" + s.latex(value) + r"\)"


def latex_source(source):
    """Render the original AST without evaluating away the question or truth value."""

    def visit(node):
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Name):
            return {"pi": r"\pi", "oo": r"\infty", "I": "i"}.get(node.id, node.id)
        if isinstance(node, ast.UnaryOp):
            return ("-" if isinstance(node.op, ast.USub) else "+") + visit(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Div):
                return r"\frac{" + left + "}{" + right + "}"
            if isinstance(node.op, ast.Pow):
                return r"\left(" + left + r"\right)^{" + right + "}"
            operator = {
                ast.Add: "+",
                ast.Sub: "-",
                ast.Mult: r"\cdot ",
                ast.Mod: r"\bmod ",
            }[type(node.op)]
            return r"\left(" + left + operator + right + r"\right)"
        if isinstance(node, ast.Call):
            args = [visit(a) for a in node.args]
            name = node.func.id
            if name == "sqrt":
                return r"\sqrt{" + args[0] + "}"
            if name == "abs":
                return r"\left|" + args[0] + r"\right|"
            if name == "factorial":
                return r"\left(" + args[0] + r"\right)!"
            if name == "binomial":
                return r"\binom{" + args[0] + "}{" + args[1] + "}"
            if name == "exp":
                return "e^{" + args[0] + "}"
            command = {
                "log": r"\ln",
                "sin": r"\sin",
                "cos": r"\cos",
                "tan": r"\tan",
                "u": "u",
                "im": r"\operatorname{Im}",
                "re": r"\operatorname{Re}",
                "conjugate": r"\overline",
            }[name]
            return command + r"\left(" + ",".join(args) + r"\right)"
        if isinstance(node, ast.Compare):
            operator = {
                ast.Eq: "=",
                ast.NotEq: r"\ne",
                ast.Lt: "<",
                ast.LtE: r"\leq",
                ast.Gt: ">",
                ast.GtE: r"\geq",
            }[type(node.ops[0])]
            return visit(node.left) + operator + " " + visit(node.comparators[0])
        if isinstance(node, ast.BoolOp):
            return (r"\land " if isinstance(node.op, ast.And) else r"\lor ").join(
                visit(v) for v in node.values
            )
        raise ValueError("无法排版该数学结构")

    parse(source)
    return visit(ast.parse(source, mode="eval").body)


def source_math(source):
    return r"\(" + latex_source(source) + r"\)"


def render_task(task):
    op = task["op"]
    require(op in PROMPTS, "不支持的数学任务")
    label = task.get("prompt", PROMPTS[op])
    if op == "optimum" and "prompt" not in task:
        label = "求最大值" if task.get("which", "maximum") == "maximum" else "求最小值"
    if op in ("recurrence", "recurrence_sum"):
        text = (
            source_math(task["relation"])
            + "=0，初值"
            + ", ".join(f"u({i})={v}" for i, v in task["initial"].items())
            + "，n为正整数。"
        )
        if "at" in task:
            text += f"求u({task['at']})。"
        if op == "recurrence_sum":
            text += (
                "求"
                + maths(
                    s.Sum(
                        s.Function("u")(parse("k")) * parse(task.get("weight", "1")),
                        (parse("k"), 1, parse(task["upper"])),
                    )
                )
                + "。"
            )
    elif op == "system":
        text = (
            "，".join(source_math(v) + "=0" for v in task["expressions"])
            + ", 未知量"
            + ",".join(task["variables"])
            + "为实数。"
        )
        if task.get("conditions"):
            text += (
                "附加限制" + ",".join(source_math(c) for c in task["conditions"]) + "。"
            )
    elif op in ("sum", "product"):
        index = parse(task.get("index", "k"))
        expr = parse(task["expression"])
        body = (s.Sum if op == "sum" else s.Product)(
            expr, (index, parse(str(task.get("lower", 1))), parse(str(task["upper"])))
        )
        sign = r"\sum" if op == "sum" else r"\prod"
        text = (
            r"\("
            + sign
            + "_{"
            + task.get("index", "k")
            + "="
            + str(task.get("lower", 1))
            + "}^{"
            + str(task["upper"])
            + "}"
            + latex_source(task["expression"])
            + r"\)"
            + "；n为正整数。"
        )
    elif op in ("probability", "count", "expectation", "probability_claim"):
        text = (
            "各变量独立等可能取值，"
            + "，".join(
                k + "∈" + maths(s.FiniteSet(*v))
                for k, v in task["sample_space"].items()
            )
            + "。"
        )
        if task.get("condition"):
            text += "已知" + source_math(task["condition"]) + "。"
        if op != "expectation":
            text += "目标事件为" + source_math(task["event"]) + "。"
        if op == "expectation":
            text += "随机变量为" + maths(parse(task["value"])) + "。"
        if op == "probability_claim":
            text += "概率是否等于" + maths(parse(task["claimed_probability"])) + "？"
    elif op == "statistics":
        text = (
            "样本数据"
            + str(task["data"])
            + "，求"
            + {"mean": "均值", "variance": "方差", "median": "中位数"}[
                task["statistic"]
            ]
            + "。"
        )
    elif op == "vector":
        text = (
            "向量u="
            + maths(s.Tuple(*task["u"]))
            + "，v="
            + maths(s.Tuple(*task["v"]))
            + "。"
            + {
                "dot": "求内积",
                "cosine_squared": "求夹角余弦的平方",
                "orthogonal": "是否互相垂直",
                "parallel": "是否互相平行",
                "cross_norm_squared": "求这两个向量张成的平行四边形面积的平方",
                "triangle_area_squared": "求这两个向量张成的三角形面积的平方",
            }[task["operation"]]
            + "。"
        )
    elif op == "geometry":
        if "plane_points" in task:
            text = (
                "平面由三点"
                + "，".join(
                    name + "=" + maths(s.Tuple(*point))
                    for name, point in zip("ABC", task["plane_points"])
                )
                + "确定。"
            )
            if task["operation"] == "plane_distance":
                text += "求点D=" + maths(s.Tuple(*task["point"])) + "到该平面的距离。"
            else:
                text += (
                    "求方向向量为"
                    + maths(s.Tuple(*task["direction"]))
                    + "的直线与该平面夹角的正弦。"
                )
        else:
            A, B, C = task["line"]
            text = (
                "求点"
                + maths(s.Tuple(*task["point"]))
                + "到直线"
                + maths(A * parse("x") + B * parse("y") + C)
                + "=0的距离。"
            )
    elif op == "intersection":
        text = (
            "两条曲线"
            + "，".join(source_math(v) + "=0" for v in task["curves"])
            + "。求"
            + {"count": "不同实交点数", "distance_squared": "两交点间距离的平方"}[
                task["ask"]
            ]
            + "。"
        )
    elif op == "derivative_claim":
        text = (
            "函数"
            + source_math(task["expression"])
            + "，导数是否恒等于"
            + source_math(task["claim_expression"])
            + "？"
        )
    elif op == "point_on_curve":
        text = (
            "点"
            + maths(s.Tuple(*task["point"]))
            + "是否属于曲线"
            + maths(parse(task["curve"]))
            + "=0？"
        )
    elif op == "identity":
        text = maths(parse(task["left"])) + "=" + maths(parse(task["right"])) + "。"
    elif op == "comparison":
        text = source_math(task["claim"]) + "。"
    else:
        text = source_math(task["expression"])
        if op in ("equation", "root_count"):
            text += "=0"
        if op == "coefficient":
            text += "，所求幂次" + str(task["power"])
        if "at" in task:
            text += "，指定值" + str(task["at"])
        if "domain" in task:
            lo, hi = task["domain"]
            opens = task.get("open", [True, True])
            domain = s.Interval(
                parse(str(lo)), parse(str(hi)), left_open=opens[0], right_open=opens[1]
            )
            text += "，" + task.get("variable", "x") + "∈" + maths(domain)
        if op in ("parameter_monotone", "parameter_bound"):
            text += "，参数" + task.get("parameter", "a") + "为实数"
        text += "。"
    return label + "。" + text


def rendered_question(candidate, order):
    problem = candidate["problem"]
    stem = problem.get("context", "")
    if problem.get("given_text"):
        stem += "\n" + problem["given_text"]
    tasks = problem["tasks"]
    stem += "\n" + "\n".join(
        f"（{i}）" + render_task(task) for i, task in enumerate(tasks, 1)
    )
    options = problem.get("options")
    if candidate["kind"] == "multiple_choice":
        stem = problem.get("context", "") + " 选择所有正确命题。"
        options = {
            key: {"text": render_task(task), "assertion": task}
            for key, task in problem["assertions"].items()
        }
    permutation = None
    if options:
        keys = list("ABCD")
        random.Random(
            int(fingerprint({"id": candidate["id"], "layout": "phase3-v1"})[:16], 16)
        ).shuffle(keys)
        if candidate.get("layout_correct_key") and candidate.get("layout_target"):
            keys.remove(candidate["layout_correct_key"])
            keys.insert(
                "ABCD".index(candidate["layout_target"]),
                candidate["layout_correct_key"],
            )
        permutation = dict(zip("ABCD", keys))
        options = {shown: options[original] for shown, original in permutation.items()}
    return {
        "id": candidate["id"],
        "order": order,
        "kind": candidate["kind"],
        "points": candidate["points"],
        "module": candidate["module"],
        "stem": stem,
        "options": options,
        "problem": problem,
        "design": candidate["design"],
        "difficulty": estimate_difficulty(candidate),
        "option_permutation": permutation,
        "layout_correct_key": candidate.get("layout_correct_key"),
        "layout_target": candidate.get("layout_target"),
        "difficulty_basis": "操作、量词和关联层数的设计判断，尚无考生得分率",
        "generation": {
            "mode": "ai",
            "provider": candidate["generation"]["provider"],
            "model_version": candidate["generation"].get(
                "model_version", "not_exposed_by_host"
            ),
            "raw_candidate_sha256": candidate.get("_raw_hash", fingerprint(candidate)),
        },
        "answer_domain": problem.get("answer_domain"),
    }


def estimate_difficulty(candidate):
    scores = {
        "evaluate": 1,
        "equation": 2,
        "sum": 2,
        "product": 2,
        "system": 3,
        "recurrence": 3,
        "coefficient": 2,
        "derivative": 2,
        "extrema": 3,
        "monotonicity": 3,
        "parameter_monotone": 4,
        "parameter_bound": 4,
        "nonnegative": 4,
        "probability": 2,
        "identity": 2,
        "comparison": 2,
    }
    scores.update(
        {
            "recurrence_sum": 4,
            "root_count": 3,
            "optimum": 3,
            "count": 2,
            "expectation": 3,
            "statistics": 1,
            "vector": 2,
            "geometry": 3,
            "intersection": 3,
            "derivative_claim": 2,
            "probability_claim": 3,
            "point_on_curve": 2,
        }
    )
    tasks = candidate["problem"].get("tasks", []) + list(
        candidate["problem"].get("assertions", {}).values()
    )
    base = max((scores.get(t["op"], 5) for t in tasks), default=1)
    return min(5, base + (1 if len(tasks) >= 3 else 0))


def structural_signature(candidate):
    expressions = []

    class EraseConstants(ast.NodeTransformer):
        def visit_Constant(self, node):
            return ast.copy_location(ast.Name(id="CONST", ctx=ast.Load()), node)

    tasks = candidate["problem"].get("tasks", []) + list(
        candidate["problem"].get("assertions", {}).values()
    )
    for task in tasks:
        row = {
            "op": task["op"],
            "ask": task.get("ask"),
            "operation": task.get("operation"),
            "statistic": task.get("statistic"),
            "domain_kind": [str(v) in ("oo", "-oo") for v in task.get("domain", [])],
            "conditions": sorted(task.get("sample_space", {})),
        }
        for key in (
            "expression",
            "relation",
            "claim",
            "left",
            "right",
            "event",
            "condition",
            "curve",
        ):
            if key in task:
                row[key] = ast.dump(
                    EraseConstants().visit(ast.parse(task[key], mode="eval")),
                    include_attributes=False,
                )
        if "expressions" in task:
            row["expressions"] = [
                ast.dump(
                    EraseConstants().visit(ast.parse(v, mode="eval")),
                    include_attributes=False,
                )
                for v in task["expressions"]
            ]
        if "curves" in task:
            row["curves"] = [
                ast.dump(
                    EraseConstants().visit(ast.parse(v, mode="eval")),
                    include_attributes=False,
                )
                for v in task["curves"]
            ]
        expressions.append(row)
    return fingerprint({"module": candidate["module"], "tasks": expressions})


def _worker(tasks, pipe):
    try:
        pipe.send({"ok": True, "tasks": [solve_task(t) for t in tasks]})
    except Exception as error:
        pipe.send({"ok": False, "reason": str(error)})
    finally:
        pipe.close()


def independent_solve(problem, timeout=18):
    tasks = problem.get("tasks", [])
    if "assertions" in problem:
        tasks = list(problem["assertions"].values())
    require(0 < len(tasks) <= 5, "题目任务数量异常")
    parent, child = multiprocessing.Pipe(duplex=False)
    process = multiprocessing.Process(target=_worker, args=(tasks, child))
    process.start()
    child.close()
    try:
        if not parent.poll(timeout):
            process.terminate()
            process.join()
            return {"ok": False, "reason": "独立求解超时"}
        result = parent.recv()
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join()
        return result
    finally:
        parent.close()


def review(question, solved):
    issues = []
    problem = question["problem"]
    kind = question["kind"]
    if question["module"] not in MODULES:
        issues.append("curriculum_module_unapproved")
    if "如图" in problem.get("context", "") and not problem.get("figure"):
        issues.append("missing_figure")
    if kind == "single_choice":
        if len(problem["tasks"]) != 1:
            issues.append("single_choice_multiple_demands")
        if any(word in question["stem"] for word in ("证明", "另请", "说明理由")):
            issues.append("response_kind_conflict")
        answers = solved.get("tasks", [])
        if answers:
            result = answers[0]["result"]
            try:
                target = parse(str(result))
            except (ValueError, SyntaxError):
                issues.append("single_choice_non_scalar")
                target = None
            values = []
            for key, option in (question["options"] or {}).items():
                try:
                    value = parse(option["semantic_value"])
                    values.append(value)
                    if option["text"] != maths(value):
                        issues.append("option_text_spec_mismatch")
                    if target is not None and not option.get("error_path"):
                        issues.append("missing_error_path")
                    if problem["tasks"][0]["op"] == "probability" and not (
                        0 <= value <= 1
                    ):
                        issues.append("option_out_of_range")
                    declared = problem.get("answer_domain")
                    if declared and not (
                        parse(str(declared[0])) <= value <= parse(str(declared[1]))
                    ):
                        issues.append("option_out_of_range")
                except Exception:
                    issues.append("invalid_option")
            if (
                target is not None
                and sum(s.simplify(v - target) == 0 for v in values) != 1
            ):
                issues.append("non_unique_correct_option")
            if len({str(s.simplify(v)) for v in values}) != 4:
                issues.append("equivalent_options")
    if kind == "multiple_choice":
        if set(problem.get("assertions", {})) != set("ABCD"):
            issues.append("missing_options")
        if not all(isinstance(row["result"], bool) for row in solved.get("tasks", [])):
            issues.append("unresolved_assertion")
        true = sum(row["result"] is True for row in solved.get("tasks", []))
        if not 2 <= true <= 3:
            issues.append("invalid_multi_choice_key")
    issues.extend(audit_item(question)["errors"])
    return {
        "passed": not issues and solved.get("ok", False),
        "errors": sorted(set(issues)),
        "version": "independent-review-v1",
        "scope": "数学规格与可计算格式，教师语义与实测仍待补充",
    }


def _answer_fragments(result):
    if isinstance(result, dict):
        labels = {
            "minimum": "最小下界",
            "maximum": "最大上界",
            "minimum_at": "取到最小值的位置",
            "maximum_at": "取到最大值的位置",
            "increasing": "单调增区间",
            "decreasing": "单调减区间",
            "critical": "驻点",
            "proved": "命题是否证成",
            "infimum": "下确界",
            "equality": "取等位置",
        }
        return [
            labels.get(key, key) + " " + part
            for key, value in result.items()
            for part in _answer_fragments(value)
        ]
    if isinstance(result, list):
        return [part for v in result for part in _answer_fragments(v)]
    if isinstance(result, bool):
        return ["成立" if result else "不成立"]
    try:
        return [maths(parse(str(result)))]
    except Exception:
        return [str(result)]


def verify_candidate(candidate, order, timeout=18, layout_target=None):
    question = rendered_question(candidate, order)
    solved = independent_solve(question["problem"], timeout)
    if solved.get("ok") and candidate["kind"] == "single_choice" and layout_target:
        try:
            target = parse(str(solved["tasks"][0]["result"]))
            matching = [
                k
                for k, v in candidate["problem"]["options"].items()
                if s.simplify(parse(v["semantic_value"]) - target) == 0
            ]
            if len(matching) == 1:
                prepared = {
                    **candidate,
                    "_raw_hash": fingerprint(candidate),
                    "layout_correct_key": matching[0],
                    "layout_target": layout_target,
                }
                question = rendered_question(prepared, order)
        except (ValueError, TypeError, SyntaxError):
            pass
    quality = review(question, solved)
    key = None
    if solved.get("ok"):
        if question["kind"] == "single_choice":
            try:
                target = parse(str(solved["tasks"][0]["result"]))
                key = "".join(
                    k
                    for k, v in question["options"].items()
                    if s.simplify(parse(v["semantic_value"]) - target) == 0
                )
            except Exception:
                pass
        elif question["kind"] == "multiple_choice":
            truth = {
                k: row["result"]
                for k, row in zip(question["problem"]["assertions"], solved["tasks"])
            }
            key = "".join(
                shown
                for shown, original in question["option_permutation"].items()
                if truth[original] is True
            )
    steps = []
    indexed = list(enumerate(solved.get("tasks", []), 1))
    if question["kind"] == "multiple_choice" and solved.get("ok"):
        original_rows = dict(zip(question["problem"]["assertions"], solved["tasks"]))
        indexed = [
            (f"现选项{shown}（原始命题{original}）", original_rows[original])
            for shown, original in question["option_permutation"].items()
        ]
    for number, row in indexed:
        label = number if isinstance(number, str) else f"独立求解第{number}项"
        steps.append(label + "。" + "；".join(_answer_fragments(row["result"])))
        steps.extend(row["steps"])
    result = {
        "question_sha256": fingerprint(question),
        "passed": quality["passed"],
        "status": (
            "已完成符号与数值交叉验证"
            if all(row["cross_checked"] for row in solved.get("tasks", []))
            else "已完成程序验证"
        )
        if quality["passed"]
        else "验证失败，禁止发布",
        "option_key": key,
        "values_latex": [],
        "steps": steps,
        "solver_record": solved,
        "formal_proof_passed": False,
        "independent_ai_review": "尚未完成",
        "remaining_uncertainty": "数学规格已独立计算；题意对应与高中解法需要独立AI审题，正式使用尚需教师审核。",
        "model_version": "not_exposed_by_host",
        "version": VERSION,
        "quality": quality,
    }
    return question, result


def paper_review(blueprint, questions, verifications):
    errors = []
    if len(questions) != len(blueprint["slots"]):
        errors.append("paper_missing_questions")
    if sum(q["points"] for q in questions) != blueprint["total_points"]:
        errors.append("paper_total_points")
    for slot, q in zip(blueprint["slots"], questions):
        if any(slot[key] != q[key] for key in ("kind", "points", "module")):
            errors.append("blueprint_mismatch")
    if not all(v["passed"] for v in verifications):
        errors.append("failed_question_in_paper")
    keys = [
        v["option_key"]
        for q, v in zip(questions, verifications)
        if q["kind"] == "single_choice"
    ]
    if len(keys) >= 6 and (
        max(Counter(keys).values(), default=0) > 4 or len(set(keys)) < 3
    ):
        errors.append("answer_position_pattern")
    if blueprint["mode"] == "full" and len({q["module"] for q in questions}) < 6:
        errors.append("module_coverage")
    signatures = [structural_signature(q) for q in questions]
    if len(signatures) != len(set(signatures)):
        errors.append("number_only_structure_repeat")
    estimates = []
    for q in questions:
        tasks = len(q["problem"].get("tasks", []))
        level = q["difficulty"]
        base = {
            "single_choice": 1.5,
            "multiple_choice": 3,
            "fill_in": 1.5,
            "constructed_response": 5,
        }[q["kind"]]
        factor = {
            "single_choice": 0.5,
            "multiple_choice": 0.7,
            "fill_in": 0.6,
            "constructed_response": 1.7,
        }[q["kind"]]
        estimates.append(
            base
            + factor * level
            + (0.7 * max(0, tasks - 1) if q["kind"] == "constructed_response" else 0)
        )
    return {
        "passed": not errors,
        "errors": errors,
        "questions": len(questions),
        "points": sum(q["points"] for q in questions),
        "kind_counts": dict(Counter(q["kind"] for q in questions)),
        "module_counts": dict(Counter(q["module"] for q in questions)),
        "estimated_minutes": round(sum(estimates), 1),
        "estimated_minutes_range": [
            round(sum(estimates) * 0.7),
            round(sum(estimates) * 1.4),
        ],
        "time_basis": "按题型基础时间、任务关联及设计复杂度估计。单选与解答题使用不同尺度，未经考生作答校准",
        "quality_rating": "研究审阅版，尚未认定为高质量高考模拟卷",
    }


def run_ai(
    root,
    provider,
    output,
    export=True,
    solver_timeout=18,
    pilot_certificate=None,
    specialty_certificates=(),
):
    require(not output.exists(), "输出目录已存在")
    research_context = context(
        root, include_local=not isinstance(provider, OpenAIProvider)
    )
    document = provider.propose(
        research_context,
        "依据研究上下文动态设计新数学结构，输出schema_version=2的JSON。数学规格、AI中文写作、排版必须分层，协议见writing-protocol.md。不给考生看AST、内部任务名或解题方法。禁止family。"
        + (
            "已提供5题样卷证书，可以按目标蓝图构造整卷。"
            if pilot_certificate or specialty_certificates
            else "本次只能先设计5题pilot，未完成PDF-only样卷审题前禁止生成整卷。"
        ),
    )
    if document.get("schema_version") == 2:
        from .exam_workflow import prepare

        manifest = prepare(
            root, document, output, pilot_certificate, specialty_certificates
        )
        return {
            "generation_mode": "ai",
            "provider": provider.name,
            "structure": {
                "questions": manifest["question_count"],
                "points": document["paper"]["total_points"],
                "passed": False,
            },
            "overall_status": "中文写作与程序支持通过；等待PDF-only独立考生审题",
            "review_manifest": manifest,
        }
    output.mkdir(parents=True)
    atomic_json(output / "raw-ai-proposal.json", document)
    proposed = document["blueprint"]
    blueprint = plan(
        root,
        proposed["mode"],
        proposed.get("profile", "host"),
        proposed.get("seed", 0),
        proposed=proposed["slots"],
    )
    blueprint["title"] = proposed.get("title", blueprint["title"]) + " · 研究审阅版"
    questions = []
    verifications = []
    events = []
    rejected = []
    count = sum(slot["kind"] == "single_choice" for slot in blueprint["slots"])
    target_letters = (list("ABCD") * ((count + 3) // 4))[:count]
    random.Random(int(fingerprint(blueprint)[:16], 16)).shuffle(target_letters)
    layouts = iter(target_letters)
    for i, slot in enumerate(blueprint["slots"], 1):
        layout_target = next(layouts) if slot["kind"] == "single_choice" else None
        candidates = [q for q in document["questions"] if q["slot"] == i]
        accepted = False
        for attempt in range(3):
            if attempt >= len(candidates):
                if (
                    not isinstance(provider, OpenAIProvider)
                    or provider.calls >= provider.max_calls
                ):
                    break
                feedback = {
                    "slot": i,
                    "blueprint": proposed,
                    "previous_candidate": candidates[-1] if candidates else None,
                    "independent_feedback": events[-1] if events else "缺少候选",
                }
                try:
                    revision = provider.propose(
                        research_context,
                        "修订失败题目，保持蓝图与槽位，不得读取或复用旧标准答案。反馈："
                        + json.dumps(feedback, ensure_ascii=False),
                    )
                    atomic_json(
                        output / f"raw-ai-revision-{i}-{attempt}.json", revision
                    )
                    candidates.extend(
                        q for q in revision["questions"] if q["slot"] == i
                    )
                except Exception as error:
                    events.append(
                        {
                            "slot": i,
                            "passed": False,
                            "reason": str(error),
                            "stage": "ai_feedback_retry",
                        }
                    )
                if attempt >= len(candidates):
                    break
            candidate = candidates[attempt]
            start = time.monotonic()
            try:
                require(
                    all(candidate[k] == slot[k] for k in ("kind", "points", "module")),
                    "候选与蓝图不符",
                )
                question, result = verify_candidate(
                    candidate, i, solver_timeout, layout_target
                )
                signature = structural_signature(question)
                if any(structural_signature(old) == signature for old in questions):
                    result["passed"] = False
                    result["quality"]["errors"].append("number_only_structure_repeat")
                event = {
                    "slot": i,
                    "candidate_id": candidate["id"],
                    "candidate_sha256": fingerprint(candidate),
                    "input_sha256": fingerprint(candidate["problem"]),
                    "output_sha256": fingerprint(result),
                    "elapsed_seconds": round(time.monotonic() - start, 3),
                    "result": result,
                }
                events.append(event)
                if result["passed"]:
                    questions.append(question)
                    verifications.append(result)
                    accepted = True
                    break
                rejected.append(event)
            except Exception as error:
                event = {
                    "slot": i,
                    "candidate_id": candidate.get("id"),
                    "reason": str(error),
                    "passed": False,
                }
                events.append(event)
                rejected.append(event)
            atomic_json(output / "events.json", events)
        if not accepted:
            atomic_json(output / "events.json", events)
            atomic_json(output / "rejected.json", rejected)
            raise ValueError(f"第{i}槽尚无可通过验证的AI题目，停止发布")
    report = paper_review(blueprint, questions, verifications)
    atomic_json(output / "rejected.json", rejected)
    require(report["passed"], "整卷审查失败 " + str(report["errors"]))
    record = {
        "schema_version": 2,
        "generation_mode": "ai",
        "provider": provider.name,
        "blueprint": blueprint,
        "research_context_sha256": fingerprint(research_context),
        "provenance": {
            **document["provenance"],
            "api_calls": getattr(
                provider, "calls", document["provenance"].get("api_calls", 0)
            ),
        },
        "questions": questions,
        "verifications": verifications,
        "events": events,
        "structure": report,
        "overall_status": "研究审阅版，程序通过，独立AI审题待完成",
        "limitations": [
            "程序验证范围为显式数学规格，未完成任意语义形式化证明",
            "创新程度与难度为设计判断，尚需教师审核与考生实测",
        ],
        "remote_model_calls": getattr(
            provider, "calls", document["provenance"].get("api_calls", 0)
        ),
        "proposal_revision_files": sorted(
            path.name for path in output.glob("raw-ai-revision-*.json")
        ),
    }
    atomic_json(output / "run.json", record)
    atomic_json(output / "quality-report.json", report)
    if export:
        record["export_status"] = "等待版本绑定的独立AI审题；运行review后导出研究审阅版"
        atomic_json(output / "run.json", record)
    return record
