"""Independent calculations for school-language exams; receives mathematical inputs only."""

import multiprocessing
import sympy as s
from .ai_spec import parse, solve_task, FUNCTIONS, extrema, numeric_check, clean

FUNCTIONS["indicator"] = lambda condition: s.Piecewise((1, condition), (0, True))
VERSION = "school-solver-v2"


def coverage(rows):
    complete = sum(r.get("complete") is True for r in rows)
    supported = sum(
        r.get("complete") is not True and bool(set(r.get("facts", ())) - {"scope"})
        for r in rows
    )
    total = len(rows)
    return {
        "total_tasks": total,
        "complete_tasks": complete,
        "partial_tasks": supported,
        "independent_reasoning_tasks": total - complete - supported,
        "status": "complete_spec_checks" if total and complete == total
        else "partial_support" if complete or supported else "independent_reasoning_only",
    }


def extended_task(t):
    op = t["op"]
    x = s.Symbol("x", real=True)
    from .school_ops import solve_extra, UnsupportedOperation

    try:
        return solve_extra(t)
    except UnsupportedOperation:
        pass
    if op == "monotonicity_boolean":
        expr = parse(t["expression"])
        domain = s.Interval(
            parse(str(t["domain"][0])),
            parse(str(t["domain"][1])),
            left_open=True,
            right_open=True,
        )
        d = s.diff(expr, x)
        from sympy.calculus.util import continuous_domain

        if continuous_domain(expr, x, domain) != domain:
            raise ValueError("题设区间不在连续定义域内")
        if t["direction"] not in ("increasing", "decreasing"):
            raise ValueError("单调方向无效")
        forbidden = s.solveset(
            d < 0 if t["direction"] == "increasing" else d > 0, x, domain=domain
        )
        if forbidden.is_empty is None:
            raise ValueError("单调性真值未确定")
        # A derivative of one sign is insufficient on a flat interval.
        zero = s.solveset(d, x, domain=domain)
        if forbidden.is_empty and zero is not s.S.EmptySet and not isinstance(zero, s.FiniteSet):
            if not isinstance(zero, s.Interval):
                raise ValueError("不能判定是否存在常值子区间")
        return {
            "result": bool(forbidden.is_empty) and (zero is s.S.EmptySet or isinstance(zero, s.FiniteSet)),
            "complete": True,
            "facts": {"derivative": str(d), "violating_set": str(forbidden)},
        }
    if op == "root_count_claim":
        roots = s.solveset(parse(t["expression"]), x, domain=s.S.Reals)
        if not isinstance(roots, s.FiniteSet):
            raise ValueError("解集未完整确定")
        return {
            "result": len(roots) == t["claimed_count"],
            "complete": True,
            "facts": {"roots": str(roots)},
        }
    if op == "polynomial_implication":
        variables = [s.Symbol(v, real=True) for v in t["variables"]]
        scope = {str(v): v for v in variables}
        eqs = [parse(e, scope) for e in t["equalities"]]
        auxiliaries = []
        for i, e in enumerate(t.get("nonzero", [])):
            z = s.Dummy("inv" + str(i))
            auxiliaries.append(z)
            eqs.append(z * parse(e, scope) - 1)
        basis = s.groebner(eqs, *(auxiliaries + variables))
        remainder = basis.reduce(parse(t["conclusion"], scope))[1]
        if remainder != 0:
            raise ValueError("蕴含未被代数消元证成")
        return {
            "result": True,
            "complete": True,
            "facts": {"ideal_remainder": str(remainder)},
        }
    if op == "root_pair_bound":
        positive = s.Symbol("x", positive=True)
        expr = parse(t["expression"], {"x": positive})
        h = s.expand_log(
            expr.subs(positive, parse(t["transformation"], {"x": positive})) - expr,
            force=True,
        )
        derivative = s.factor(s.diff(h, positive))
        return {
            "result": None,
            "complete": False,
            "requires_independent_reasoning": True,
            "facts": {
                "derivative": str(s.diff(expr, positive)),
                "comparison": str(h),
                "comparison_derivative": str(derivative),
                "at_pivot": str(s.simplify(h.subs(positive, parse(t["pivot"])))),
            },
            "scope": "只核查比较函数代数及导数，零点位置推理必须由独立PDF审题者完成",
        }
    row = solve_task(t)
    row["complete"] = True
    return row


def _worker(spec, pipe):
    try:
        if assertions := spec.get("assertions"):
            if set(assertions) != set("ABCD"):
                raise ValueError("选项验证必须对应A、B、C、D")
            tasks = [assertions[key] for key in "ABCD"]
        else:
            tasks = spec["tasks"]
        rows = [extended_task(t) for t in tasks]
        if not rows:
            raise ValueError("数学任务不能为空")

        def serialise(value):
            if isinstance(value, dict):
                return {str(k): serialise(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [serialise(v) for v in value]
            return clean(value)

        pipe.send(
            serialise(
                {
                    "program_checks_passed": True,
                    "tasks": rows,
                    "all_tasks_program_complete": all(r.get("complete") for r in rows),
                    "program_coverage": coverage(rows),
                    "program_scope": "已运行的规格检查无错误；完整性须看program_coverage，题面与推理仍须独立核对",
                    "version": VERSION,
                    "formal_proof": False,
                }
            )
        )
    except Exception as e:
        pipe.send(
            {"program_checks_passed": False, "reason": str(e), "version": VERSION}
        )
    finally:
        pipe.close()


def solve_spec(spec, timeout=30):
    a, b = multiprocessing.Pipe(duplex=False)
    p = multiprocessing.Process(target=_worker, args=(spec, b))
    p.start()
    b.close()
    try:
        if not a.poll(timeout):
            p.terminate()
            p.join()
            return {"program_checks_passed": False, "reason": "独立数学求解超时"}
        result = a.recv()
        p.join(2)
        if p.is_alive():
            p.terminate()
            p.join()
        return result
    finally:
        a.close()
