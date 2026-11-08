"""General mathematical operations for new specifications; no question text or proposed answers."""

import itertools, math
from collections import defaultdict
import sympy as s
from .ai_spec import parse, extrema, clean, numeric_check


class UnsupportedOperation(Exception):
    pass


def packed(result, complete=True, **facts):
    return {
        "result": clean(result),
        "complete": complete,
        "facts": clean(facts),
        "formal_proof": False,
    }


def level_count(expr, x, domain, level):
    from sympy.calculus.util import continuous_domain

    if not domain.is_subset(continuous_domain(expr, x, s.S.Reals)):
        raise ValueError("函数在区间不连续")
    d = s.diff(expr, x)
    if d == 0:
        raise ValueError("常函数零点不能作为有限根计数")
    critical = s.solveset(d, x, domain=domain)
    if not isinstance(critical, s.FiniteSet) and critical is not s.S.EmptySet:
        raise ValueError("驻点未完全确定")
    interior = sorted(
        [c for c in critical if c not in (domain.start, domain.end)], key=float
    )
    points = [domain.start, *interior, domain.end]
    values = [
        s.limit(expr, x, p, dir="+")
        if p == domain.start
        else s.limit(expr, x, p, dir="-")
        if p == domain.end
        else s.simplify(expr.subs(x, p))
        for p in points
    ]
    count = sum(1 for p in interior if s.simplify(expr.subs(x, p) - level) == 0)
    for a, b in zip(values, values[1:]):
        if min(a, b) < level < max(a, b):
            count += 1
    if not domain.left_open and s.simplify(values[0] - level) == 0:
        count += 1
    if not domain.right_open and s.simplify(values[-1] - level) == 0:
        count += 1
    return count, points, values


def solve_extra(t):
    op = t["op"]
    x = s.Symbol("x", real=True)
    if op == "data_correction_variance":
        n = t["n"]
        m = parse(str(t["recorded_mean"]))
        v = parse(str(t["recorded_variance"]))
        old = parse(str(t["recorded"]))
        new = parse(str(t["correct"]))
        mean = s.simplify((n * m - old + new) / n)
        variance = s.simplify((n * (v + m * m) - old * old + new * new) / n - mean**2)
        return packed(
            variance,
            corrected_mean=mean,
            corrected_second_moment=(n * (v + m * m) - old * old + new * new) / n,
        )
    if op == "graph_transform_value":
        expr = parse(t["expression"])
        scale = parse(t["horizontal_scale"])
        shift = parse(t["left_shift"])
        if scale <= 0:
            raise ValueError("横坐标伸缩倍率须为正")
        transformed = expr.subs(x, x / scale + shift)
        return packed(
            s.simplify(transformed.subs(x, parse(t["at"]))),
            transformed_expression=transformed,
        )
    if (
        op in ("linear_recurrence", "recurrence_transform")
        or op == "recurrence_sum"
        and "additive_shift" in t
    ):
        n = s.Symbol("n", integer=True, positive=True)
        u = s.Function("u")
        relation = parse(t["relation"], {"n": n})
        initial = {u(int(k)): parse(str(v)) for k, v in t["initial"].items()}
        solution = s.rsolve(relation, u(n), initial)
        if solution is None:
            raise ValueError("未求出递推通项")

        def apply(expr):
            return expr.replace(
                lambda a: getattr(a, "func", None) == u,
                lambda a: solution.subs(n, a.args[0]),
            )

        residual = s.simplify(apply(relation))
        if residual != 0 or any(
            s.simplify(solution.subs(n, int(k)) - parse(str(v))) != 0
            for k, v in t["initial"].items()
        ):
            raise ValueError("递推残差或初值失败")
        shifts = [
            int(s.simplify(a.args[0] - n))
            for a in relation.atoms(s.Function)
            if a.func == u
        ]
        order = max(shifts)
        known = {u(int(k)): parse(str(v)) for k, v in t["initial"].items()}
        for i in range(1, 9):
            next_term = u(i + order)
            equation = relation.subs(n, i).subs(known)
            possible = s.solve(equation, next_term)
            if len(possible) != 1:
                raise ValueError("前向递推不唯一")
            known[next_term] = possible[0]
            if s.simplify(possible[0] - solution.subs(n, i + order)) != 0:
                raise ValueError("通项与前向递推不一致")
        if op == "recurrence_transform":
            return packed(
                s.simplify(apply(parse(t["transformation"], {"n": n}))),
                recurrence_solution=solution,
                residual=0,
            )
        if op == "recurrence_sum":
            k = s.Symbol("k", integer=True, positive=True)
            expression = (solution.subs(n, k) + parse(t["additive_shift"])) * parse(
                t["weight"], {"k": k}
            )
            total = s.summation(expression, (k, 1, parse(t["upper"], {"n": n})))
            return packed(
                s.simplify(total),
                recurrence_solution=solution,
                additive_shift=t["additive_shift"],
            )
        return packed(solution, residual=0, forward_terms=list(known.values()))
    if op == "tetrahedron_volume":
        a, b, c, d = [
            s.Matrix([parse(str(v)) for v in point]) for point in t["vertices"]
        ]
        determinant = s.det(s.Matrix.hstack(b - a, c - a, d - a))
        return packed(s.Abs(determinant) / 6, determinant=determinant)
    if op == "moment_transform_claim":
        n = int(t["n"])
        mean = parse(str(t["mean"]))
        variance = parse(str(t["variance"]))
        if n < 1 or variance < 0 or n == 1 and variance != 0:
            raise ValueError("不存在满足条件的样本")
        first = n * mean
        second = n * (variance + mean**2)
        scale = parse(str(t.get("scale", 1)))
        shift = parse(str(t.get("shift", 0)))
        transformed_first = scale * first + n * shift
        transformed_second = (
            scale**2 * second + 2 * scale * shift * first + n * shift**2
        )
        if "append" in t:
            value = parse(str(t["append"]))
            transformed_first += value
            transformed_second += value**2
            n += 1
        m = s.simplify(transformed_first / n)
        v = s.simplify(transformed_second / n - m**2)
        target = m if t["statistic"] == "mean" else v
        return packed(
            s.simplify(target - parse(str(t["expected"]))) == 0,
            computed_mean=m,
            computed_variance=v,
            scope="由原始一阶、二阶矩独立重算，未使用命题者答案作为求值依据",
        )
    if op == "coefficient":
        expression = s.expand(parse(t["expression"]))
        for term in s.Add.make_args(expression):
            coefficient, power = term.as_coeff_exponent(x)
            if coefficient.has(x) or power.is_integer is not True:
                raise ValueError("不是有限整数幂展开式")
        return packed(
            expression.coeff(x, t["power"]),
            scope="有限展开式含正负整数幂的系数核查，不在x=0求值",
        )
    if op == "claim":
        from .school_solver import extended_task

        actual = extended_task(t["calculation"])
        if not actual.get("complete"):
            raise ValueError("命题真值尚未完全计算")
        return packed(
            s.simplify(parse(str(actual["result"])) - parse(t["expected"])) == 0,
            calculation=actual,
        )
    if op == "root_statistic":
        domain = s.Interval(
            parse(str(t["domain"][0])),
            parse(str(t["domain"][1])),
            left_open=True,
            right_open=True,
        )
        roots = s.solveset(parse(t["expression"]), x, domain=domain)
        if not isinstance(roots, s.FiniteSet):
            raise ValueError("根集不完整")
        result = sum(roots) if t["statistic"] == "sum" else s.prod(roots)
        return packed(result, roots=roots)
    if op == "quadratic_focus_claim":
        poly = s.Poly(parse(t["expression"]), x)
        if poly.degree() != 2:
            raise ValueError("不是抛物线")
        a, b, c = poly.all_coeffs()
        h = -b / (2 * a)
        k = c - b * b / (4 * a)
        focus = [h, k + 1 / (4 * a)]
        return packed(
            all(s.simplify(v - parse(str(w))) == 0 for v, w in zip(focus, t["focus"])),
            focus=focus,
        )
    if op == "tangent_count_claim":
        row = solve_extra({**t, "op": "tangent_through", "ask": "all"})
        return packed(len(row["result"]) == t["claimed_count"], tangent_data=row)
    if op == "tangent_line_claim":
        polynomial = s.Poly(parse(t["expression"]) - parse(t["line_expression"]), x)
        return packed(
            s.discriminant(polynomial.as_expr(), x) == 0,
            discriminant=s.discriminant(polynomial.as_expr(), x),
        )
    if op == "reasoning":
        scope = {"x": s.Symbol("x", positive=True)} if t.get("positive_x") else {}
        expression = parse(t["expression"], scope) if "expression" in t else None
        facts = {}
        if expression is not None:
            variable = scope.get("x", x)
            facts = {
                "expression": str(expression),
                "derivative": str(s.factor(s.diff(expression, variable))),
            }
        for name, source in t.get("algebra_checks", {}).items():
            facts[name] = str(s.simplify(parse(source, scope)))
        return packed(
            None,
            complete=False,
            scope="仅支持性符号计算，未求解全部证明，须独立PDF推理",
            **facts,
        )
    if op == "constrained_value":
        variables = [s.Symbol(v, real=True) for v in t["variables"]]
        env = {str(v): v for v in variables}
        solutions = s.solve(
            [parse(e, env) for e in t["equations"]], variables, dict=True
        )
        solutions = [
            row
            for row in solutions
            if all(bool(parse(c, env).subs(row)) for c in t.get("conditions", []))
        ]
        if not solutions:
            raise ValueError("约束无解")
        if len(solutions) != 1 and not t.get("unique_value"):
            raise ValueError("约束未产生唯一对象")
        results = [s.simplify(parse(t["value"], env).subs(row)) for row in solutions]
        if any(s.simplify(v - results[0]) != 0 for v in results):
            raise ValueError("约束下所求值不唯一")
        result = results[0]
        if result.free_symbols:
            raise ValueError("所求值未确定")
        return packed(result, solutions=solutions)
    if op == "trig_reconstruct":
        v = parse(t["sin"])
        c = s.sqrt(1 - v * v) * (1 if t["quadrant"] in (1, 4) else -1)
        theta = s.Symbol("t", real=True)
        shift = parse(t["shift"])
        expr = s.expand_trig(
            parse(t["target"], {"t": theta}).subs(theta, theta - shift)
        )
        result = s.simplify(expr.subs({s.sin(theta): v, s.cos(theta): c}))
        if result.free_symbols:
            raise ValueError("三角重构未完成")
        return packed(result, sine=v, cosine=c)
    if op == "tangent_through":
        expr = parse(t["expression"])
        d = s.diff(expr, x)
        px, py = map(parse, t["point"])
        roots = s.solveset(expr + (px - x) * d - py, x, domain=s.S.Reals)
        if not isinstance(roots, s.FiniteSet):
            raise ValueError("切点未完整求出")
        slopes = sorted(set(s.simplify(d.subs(x, c)) for c in roots), key=float)
        if t.get("ask") == "unique_slope" and len(slopes) != 1:
            raise ValueError("切线斜率不唯一")
        return packed(
            slopes[0] if t.get("ask") == "unique_slope" else slopes,
            contact_points=list(roots),
        )
    if op == "parameter_endpoint":
        from .ai_spec import solve_task

        row = solve_task({**t, "op": "parameter_bound"})
        # Recompute from coefficient and full-domain extrema; do not parse an arbitrary printed set.
        a = s.Symbol(t.get("parameter", "a"), real=True)
        expr = parse(t["expression"], {str(a): a})
        coefficient = s.diff(expr, a)
        rest = s.simplify(expr - a * coefficient)
        domain = s.Interval(
            parse(str(t["domain"][0])),
            parse(str(t["domain"][1])),
            left_open=True,
            right_open=True,
        )
        bound = extrema(s.simplify(-rest / coefficient), x, domain)
        return packed(
            bound["maximum"]
            if t.get("ask", "minimum") == "minimum"
            else bound["minimum"],
            interval_result=row["result"],
        )
    if op in ("level_count", "level_count_claim", "level_classification"):
        expr = parse(t["expression"])
        domain = s.Interval(
            parse(str(t.get("domain", [0, "oo"])[0])),
            parse(str(t.get("domain", [0, "oo"])[1])),
            left_open=True,
            right_open=True,
        )
        if op == "level_classification":
            _, points, values = level_count(expr, x, domain, s.Integer(0))
            levels = sorted(set(v for v in values if v.is_finite), key=float)
            cuts = [-s.oo, *levels, s.oo]
            regions = []
            for lo, hi in zip(cuts, cuts[1:]):
                sample = (
                    hi - 1 if lo == -s.oo else lo + 1 if hi == s.oo else (lo + hi) / 2
                )
                count, _, _ = level_count(expr, x, domain, sample)
                regions.append(
                    {"level_interval": str(s.Interval.open(lo, hi)), "roots": count}
                )
            regions.extend(
                {"level": str(c), "roots": level_count(expr, x, domain, c)[0]}
                for c in levels
            )
            return packed(regions, critical_points=points, branch_limits=values)
        count, points, values = level_count(expr, x, domain, parse(t["level"]))
        return packed(
            count == t["claimed_count"] if op == "level_count_claim" else count,
            critical_points=points,
            branch_limits=values,
        )
    if op == "series_claim":
        n = s.Symbol("n", integer=True, positive=True)
        k = s.Symbol("k", integer=True, positive=True)
        expr = parse(t["expression"], {"k": k, "n": n})
        upper = parse(t["upper"], {"n": n})
        lower = parse(t.get("lower", "1"))
        if lower == 1 and (upper.is_even or upper.is_odd):
            j = s.Symbol("j", integer=True, positive=True)
            pair = s.simplify(expr.subs(k, 2 * j - 1) + expr.subs(k, 2 * j))
            m = upper / 2 if upper.is_even else (upper - 1) / 2
            actual = s.summation(pair, (j, 1, m)) + (
                expr.subs(k, upper) if upper.is_odd else 0
            )
        else:
            actual = s.summation(expr, (k, lower, upper))
        for value in (1, 2, 4, 7):
            direct = sum(
                expr.subs({k: i, n: value})
                for i in range(int(lower), int(upper.subs(n, value)) + 1)
            )
            if s.simplify(direct - actual.subs(n, value)) != 0:
                raise ValueError("级数公式与逐项计算不一致")
        residual = s.simplify(actual - parse(t["claim"], {"n": n}))
        if residual == 0:
            return packed(True, sum=actual, residual=0)
        counter = next(
            (i for i in range(1, 12) if s.simplify(residual.subs(n, i)) != 0), None
        )
        if counter is None:
            raise ValueError("级数命题尚未完全判定")
        return packed(False, sum=actual, counterexample_n=counter)
    if op in ("distribution", "bernoulli_distribution"):
        if op == "distribution":
            names = list(t["sample_space"])
            tuples = itertools.product(*t["sample_space"].values())
            counts = defaultdict(lambda: s.Integer(0))
            total = 0
            expr = parse(t["value"])
            condition = parse(t["condition"])
            from .ai_spec import SYMBOLS

            for values in tuples:
                at = {SYMBOLS[k]: v for k, v in zip(names, values)}
                if bool(condition.subs(at)):
                    counts[s.simplify(expr.subs(at))] += 1
                    total += 1
            if total == 0:
                raise ValueError("条件事件概率为0")
            distribution = {v: s.Rational(c, total) for v, c in counts.items()}
        else:
            p = parse(t["p"])
            n = t["trials"]
            distribution = {
                k: s.binomial(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)
            }
        mean = s.simplify(sum(v * p for v, p in distribution.items()))
        variance = s.simplify(sum((v - mean) ** 2 * p for v, p in distribution.items()))
        return packed(
            {
                "distribution": {
                    str(k): v
                    for k, v in sorted(
                        distribution.items(), key=lambda kv: float(kv[0])
                    )
                },
                "expectation": mean,
                "variance": variance,
            },
            normalisation=s.simplify(sum(distribution.values())),
        )
    if op in (
        "plane_parallel",
        "plane_angle",
        "parameter_plane_parallel",
        "plane_perpendicular_parameter",
    ):

        def vector(v):
            return s.Matrix([parse(str(c)) for c in v])

        def normal(points):
            A, B, C = map(vector, points)
            n = (B - A).cross(C - A)
            if n.dot(n) == 0:
                raise ValueError("平面退化")
            return n

        N = normal(t["plane"])
        if op == "plane_parallel":
            A, B = map(vector, t["line"])
            res = s.simplify((B - A).dot(N))
            inplane = s.simplify((A - vector(t["plane"][0])).dot(N)) == 0
            return packed(res == 0 and not inplane, normal=list(N), dot=res)
        if op == "plane_angle":
            M = normal(t["other_plane"])
            cos = s.simplify(s.Abs(N.dot(M)) / s.sqrt(N.dot(N) * M.dot(M)))
            return packed(cos, normal_one=list(N), normal_two=list(M))
        a = s.Symbol("t", real=True)
        env = {"t": a}
        point = s.Matrix([parse(c, env) for c in t["moving_point"]])
        if op == "parameter_plane_parallel":
            d = point - vector(t["anchor"])
            condition = s.simplify(d.dot(N))
        else:
            A, B = map(vector, t["second_plane_fixed"])
            M = (B - A).cross(point - A)
            condition = s.simplify(N.dot(M))
        solutions = s.solve(condition, a)
        domain = s.Interval(*map(lambda z: parse(str(z)), t["parameter_domain"]))
        solutions = [v for v in solutions if v in domain]
        return packed(solutions, orthogonality_equation=condition, normal=list(N))
    if op == "simplex_inradius":
        vertices = [s.Matrix([parse(str(v)) for v in p]) for p in t["vertices"]]
        edges = [
            s.simplify((a - b).dot(a - b))
            for a, b in itertools.combinations(vertices, 2)
        ]
        if t.get("regular_edge_squared") and any(
            s.simplify(e - parse(t["regular_edge_squared"])) != 0 for e in edges
        ):
            raise ValueError("坐标模型与正四面体棱长不一致")
        a, b, c, d = vertices
        volume = s.Abs(s.det(s.Matrix.hstack(b - a, c - a, d - a))) / 6
        area = sum(
            s.sqrt((q - p).cross(r - p).dot((q - p).cross(r - p))) / 2
            for p, q, r in itertools.combinations(vertices, 3)
        )
        return packed(
            s.simplify(3 * volume / area),
            volume=volume,
            surface_area=area,
            edge_squares=edges,
        )
    if op == "sequence_minimum":
        n = s.Symbol("n", integer=True, positive=True)
        real = s.Symbol("x", positive=True)
        expr = parse(t["expression"], {"n": n})
        ratio = s.factor(expr.subs(n, n + 1) / expr)
        delta = s.factor(ratio - 1)
        num, den = s.fraction(delta)
        if not num.is_polynomial(n) or not den.is_polynomial(n):
            raise ValueError("离散比值不是可判定有理式")
        zeros = s.solveset(num, n, domain=s.Interval(1, s.oo))
        poles = s.solveset(den, n, domain=s.Interval(1, s.oo))
        if not isinstance(zeros, s.FiniteSet) or poles is not s.S.EmptySet:
            raise ValueError("比值分段未完整确定")
        candidates = {1}
        for z in zeros:
            candidates.update(
                i for i in range(max(1, int(s.floor(z)) - 1), int(s.floor(z)) + 3)
            )
        limit = s.limit(expr, n, s.oo)
        if limit is not s.oo:
            raise ValueError("尾部最小值尚需独立分析")
        pairs = [(i, s.simplify(expr.subs(n, i))) for i in sorted(candidates)]
        minimum = min(v for i, v in pairs)
        return packed(
            {"minimum": minimum, "at": [i for i, v in pairs if v == minimum]},
            ratio=ratio,
            ratio_thresholds=list(zeros),
            tail_limit=limit,
        )
    if op == "line_section":
        k = s.Symbol(t["parameter"], real=True)
        env = {str(k): k}
        y = s.Symbol("y", real=True)
        curve = parse(t["curve"], env)
        line = parse(t["line"], env)
        dependent = t.get("eliminate", "y")
        dep = {"x": x, "y": y}[dependent]
        ind = {"x": y, "y": x}[dependent]
        line_solution = s.solve(line, dep)
        if len(line_solution) != 1:
            raise ValueError("直线参数模型无效")
        poly = s.Poly(
            s.together(curve.subs(dep, line_solution[0])).as_numer_denom()[0], ind
        )
        if poly.degree() != 2:
            raise ValueError("不是二次曲线弦")
        aa, bb, cc = poly.all_coeffs()
        delta = s.factor(bb * bb - 4 * aa * cc)
        centre_ind = -bb / (2 * aa)
        centre_dep = s.simplify(line_solution[0].subs(ind, centre_ind))
        roots = s.solve(poly.as_expr(), ind)
        vertices = [
            s.Matrix([r, line_solution[0].subs(ind, r)])
            if ind == x
            else s.Matrix([line_solution[0].subs(ind, r), r])
            for r in roots
        ]
        area2 = s.factor(s.det(s.Matrix.hstack(*vertices)) ** 2 / 4)
        X, Y = s.symbols("X Y", real=True)
        mx, my = (centre_ind, centre_dep) if ind == x else (centre_dep, centre_ind)
        locus = s.factor(
            s.resultant(
                s.together(mx - X).as_numer_denom()[0],
                s.together(my - Y).as_numer_denom()[0],
                k,
            )
        )
        result = {
            "section_polynomial": poly.as_expr(),
            "discriminant": delta,
            "midpoint": [mx, my],
            "midpoint_locus": locus,
            "area_squared": area2,
        }
        if t.get("optimise_area_squared_parameter"):
            z = s.Symbol("t", positive=True)
            disc = s.simplify(delta.subs(k, s.sqrt(z)))
            domain = s.solve_univariate_inequality(
                disc > 0, z, relational=False
            ).intersect(s.Interval(0, s.oo))
            if not isinstance(domain, s.Interval):
                raise ValueError("参数域不能完整处理")
            bound = extrema(s.simplify(area2.subs(k, s.sqrt(z))), z, domain)
            result.update(
                area_maximum=s.sqrt(bound["maximum"]),
                optimal_parameter_squares=[
                    p for p, v, a in bound["candidates"] if v == bound["maximum"] and a
                ],
                admissible_squared_parameter=domain,
            )
        return packed(
            result,
            complete=False,
            scope="消元和最值支持完成；轨迹范围、垂直弦等边界需独立PDF证明复核",
        )
    raise UnsupportedOperation(op)
