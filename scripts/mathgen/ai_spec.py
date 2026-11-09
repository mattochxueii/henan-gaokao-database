"""A restricted mathematical language, independent of proposal answers and template families."""

import ast
import itertools
import math
from fractions import Fraction

import sympy as s
from sympy.calculus.util import continuous_domain

SYMBOLS = {
    name: s.Symbol(name, real=True) for name in ("x", "y", "a", "b", "t", "c", "p", "q")
}
SYMBOLS.update(
    {name: s.Symbol(name, integer=True, positive=True) for name in ("n", "k", "j", "m")}
)
FUNCTIONS = {
    "sqrt": s.sqrt,
    "log": s.log,
    "exp": s.exp,
    "sin": s.sin,
    "cos": s.cos,
    "tan": s.tan,
    "abs": s.Abs,
    "factorial": s.factorial,
    "binomial": s.binomial,
    "floor": s.floor,
    "conjugate": s.conjugate,
    "re": s.re,
    "im": s.im,
}
CONSTANTS = {"pi": s.pi, "E": s.E, "I": s.I, "oo": s.oo}
MAX_EXPR = 1400


def parse(text, extra=None):
    if not isinstance(text, str) or len(text) > MAX_EXPR:
        raise ValueError("表达式类型或长度不允许")
    nodes = ast.parse(text, mode="eval")
    if sum(1 for _ in ast.walk(nodes)) > 220:
        raise ValueError("表达式过于复杂")
    names = {**SYMBOLS, **CONSTANTS, **(extra or {})}

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float, bool):
            return s.Rational(
                str(int(node.value) if type(node.value) == bool else node.value)
            )
        if isinstance(node, ast.Name) and node.id in names:
            return names[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.UAdd, ast.USub, ast.Not)
        ):
            value = visit(node.operand)
            if isinstance(node.op, ast.Not):
                return s.Not(value)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left, right = visit(node.left), visit(node.right)
            operations = {
                ast.Add: lambda: left + right,
                ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right,
                ast.Div: lambda: left / right,
            }
            if type(node.op) in operations:
                return operations[type(node.op)]()
            if isinstance(node.op, ast.Pow):
                if right.is_number and (not right.is_real or abs(right) > 150):
                    raise ValueError("指数超限")
                return left**right
            if isinstance(node.op, ast.Mod):
                return s.Mod(left, right)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            functions = {**FUNCTIONS, "u": s.Function("u")}
            if node.func.id in functions and 1 <= len(node.args) <= 2:
                return functions[node.func.id](*map(visit, node.args))
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = visit(node.left), visit(node.comparators[0])
            comparisons = {
                ast.Eq: s.Eq,
                ast.NotEq: s.Ne,
                ast.Lt: s.Lt,
                ast.LtE: s.Le,
                ast.Gt: s.Gt,
                ast.GtE: s.Ge,
            }
            if type(node.ops[0]) in comparisons:
                return comparisons[type(node.ops[0])](left, right)
        if isinstance(node, ast.BoolOp):
            return (s.And if isinstance(node.op, ast.And) else s.Or)(
                *map(visit, node.values)
            )
        raise ValueError("表达式含不允许的结构")

    return visit(nodes.body)


def interval(task):
    bounds = task.get("domain", ["-oo", "oo"])
    return s.Interval(
        parse(str(bounds[0])),
        parse(str(bounds[1])),
        left_open=task.get("open", [True, True])[0],
        right_open=task.get("open", [True, True])[1],
    )


def maths(value):
    return r"\(" + s.latex(value) + r"\)"


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def extrema(expr, var, domain):
    if continuous_domain(expr, var, domain) != domain:
        raise ValueError("函数在题设定义域内不连续或实数域不匹配")
    derivative = s.diff(expr, var)
    critical = s.solveset(derivative, var, domain=domain)
    if derivative == 0:
        return {
            "minimum": expr,
            "maximum": expr,
            "critical": [],
            "candidates": [(domain.start, expr, False)],
        }
    if not isinstance(critical, s.FiniteSet) and critical is not s.S.EmptySet:
        raise ValueError("临界点无法完整求解，保留待审")
    candidates = [
        (point, s.simplify(expr.subs(var, point)), True) for point in critical
    ]
    for point, opened, direction in (
        (domain.start, domain.left_open, "+"),
        (domain.end, domain.right_open, "-"),
    ):
        value = (
            s.limit(expr, var, point, dir=direction)
            if opened
            else s.simplify(expr.subs(var, point))
        )
        candidates.append((point, value, not opened))
    values = [row[1] for row in candidates]
    if any(v.has(s.nan, s.zoo) for v in values):
        raise ValueError("边界值未确定")
    minimum = min(values, key=lambda v: float(v))
    maximum = max(values, key=lambda v: float(v))
    return {
        "minimum": minimum,
        "maximum": maximum,
        "critical": list(critical),
        "candidates": candidates,
    }


def numeric_check(expr, var, derivative=None, domain=None):
    """Independent numerical interpretation through mpmath, not the symbolic derivative."""
    import mpmath as mp

    domain = domain or s.Interval(-2, 2)
    low = -5 if domain.start is -s.oo else float(domain.start)
    high = 5 if domain.end is s.oo else float(domain.end)
    function = s.lambdify(var, expr, modules="mpmath")
    checks = []
    for index in range(1, 10):
        point = low + (high - low) * index / 10
        if derivative is None:
            checks.append(math.isfinite(float(function(point))))
        else:
            h = mp.mpf("0.000001")
            finite_difference = (function(point + h) - function(point - h)) / (2 * h)
            exact = s.lambdify(var, derivative, modules="mpmath")(point)
            checks.append(
                abs(float(finite_difference - exact)) < 1e-4 * (1 + abs(float(exact)))
            )
    return bool(checks) and all(checks)


def check_domain_syntax(task):
    variable = SYMBOLS.get(task.get("variable", "x"), SYMBOLS["x"])
    domain = interval(task)
    for field in ("expression", "left", "right", "claim"):
        source = task.get(field)
        if not isinstance(source, str):
            continue
        for node in ast.walk(ast.parse(source, mode="eval")):
            denominator = None
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                denominator = node.right
            if (
                isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Pow)
                and isinstance(node.right, ast.UnaryOp)
                and isinstance(node.right.op, ast.USub)
            ):
                denominator = node.left
            if denominator is not None:
                value = parse(ast.unparse(denominator))
                if variable in value.free_symbols:
                    zeros = s.solveset(value, variable, domain=domain)
                    if zeros is not s.S.EmptySet:
                        raise ValueError("原始表达式分母在定义域内为0")


def solve_task(task):
    check_domain_syntax(task)
    return _solve_task(task)


def _solve_task(task):
    """Only the problem task is received. Claimed answers are never passed here."""
    op = task["op"]
    steps = []
    cross = None
    scope = "exact"
    var = SYMBOLS.get(task.get("variable", "x"), SYMBOLS["x"])
    if op == "evaluate":
        expr = parse(task["expression"])
        replacements = {
            SYMBOLS[key]: parse(str(value)) for key, value in task.get("at", {}).items()
        }
        value = s.simplify(expr.subs(replacements))
        if value.free_symbols or value.has(s.zoo, s.nan):
            raise ValueError("数值任务含未定义变量或非法值")
        result = value
        steps = [f"代入题设条件，化简 {maths(expr)}，得到 {maths(value)}。"]
        cross = None  # Exact arithmetic is a program check, not an independent numerical proof.
    elif op in ("equation", "root_count"):
        expr = parse(task["expression"])
        roots = s.solveset(expr, var, domain=interval(task))
        if not isinstance(roots, s.FiniteSet) and roots is not s.S.EmptySet:
            raise ValueError("方程解集未完整确定")
        if task.get("unique") and len(roots) != 1:
            raise ValueError("所求量不唯一或无解")
        result = list(sorted(roots, key=lambda p: float(p)))
        if task.get("unique"):
            result = result[0]
        if op == "root_count":
            result = len(roots)
        steps = [
            f"将条件移项并因式分解为 {maths(s.factor(expr))}=0，限制在题设区间内，得到 {maths(roots)}。"
        ]
        cross = all(
            abs(complex(s.N(expr.subs(var, root), 35))) < 1e-20 for root in roots
        )
    elif op == "system":
        variables = [SYMBOLS[name] for name in task["variables"]]
        expressions = [parse(expr) for expr in task["expressions"]]
        roots = s.solve(expressions, variables, dict=True)
        roots = [
            row
            for row in roots
            if all(
                bool(parse(condition).subs(row))
                for condition in task.get("conditions", [])
            )
        ]
        if not roots or (task.get("unique") and len(roots) != 1):
            raise ValueError("方程组无解或不唯一")
        result = [{str(k): s.simplify(v) for k, v in row.items()} for row in roots]
        if any(any(v.free_symbols for v in row.values()) for row in roots):
            raise ValueError("方程组解含自由参数")
        if not all(
            s.simplify(expr.subs(row)) == 0 for row in roots for expr in expressions
        ):
            raise ValueError("方程组回代失败")
        cross = None
        steps = ["联立全部条件消元，逐个解回代原方程组。", str(clean(result))]
    elif op in ("sum", "product"):
        expr = parse(task["expression"])
        index = SYMBOLS[task.get("index", "k")]
        low = parse(str(task.get("lower", 1)))
        high = parse(str(task["upper"]))
        expr = s.expand(s.radsimp(expr))
        result = s.simplify(
            (s.summation if op == "sum" else s.product)(expr, (index, low, high))
        )
        if op == "sum" and result.has(s.Sum):
            for term in s.Add.make_args(expr):
                for primitive in (term, -term):
                    if (
                        s.simplify(primitive.subs(index, index + 1) - primitive - expr)
                        == 0
                    ):
                        result = s.simplify(
                            primitive.subs(index, high + 1) - primitive.subs(index, low)
                        )
                        break
        if result.has(s.Sum, s.Product):
            raise ValueError("有限和或积未能化简")
        steps = [
            f"先分解通项 {maths(s.factor(expr))}，按有限{'和' if op == 'sum' else '积'}边界计算，保留末项，得到 {maths(result)}。"
        ]
        checks = []
        for size in (2, 3, 5, 9):
            hi = int(high.subs(SYMBOLS["n"], size))
            lo = int(low)
            if hi - lo > 200:
                raise ValueError("枚举超限")
            terms = [
                expr.subs({index: j, SYMBOLS["n"]: size}) for j in range(lo, hi + 1)
            ]
            independent = sum(terms) if op == "sum" else math.prod(terms)
            checks.append(
                s.simplify(independent - result.subs(SYMBOLS["n"], size)) == 0
            )
        cross = all(checks)
    elif op in ("recurrence", "recurrence_sum"):
        n = SYMBOLS["n"]
        u = s.Function("u")
        relation = parse(task["relation"])
        initial = {u(int(i)): parse(value) for i, value in task["initial"].items()}
        try:
            formula = s.rsolve(relation, u(n), initial)
        except (AttributeError, NotImplementedError):
            formula = None
        derived_steps = []
        if formula is None:
            forward = s.solve(relation, u(n + 1))
            if len(forward) != 1:
                raise ValueError("无法消去下一项")
            A = s.diff(forward[0], u(n))
            B = s.simplify(forward[0] - A * u(n))
            if A.has(u(n)) or B.has(u(n)):
                raise ValueError("非线性递推尚需其他验证策略")
            k, j = SYMBOLS["k"], SYMBOLS["j"]
            first = min(int(i) for i in task["initial"])
            product = s.simplify(s.product(A.subs(n, k), (k, first, n - 1)))
            forcing = s.simplify(B.subs(n, j) / product.subs(n, j + 1))
            formula = s.simplify(
                product * (initial[u(first)] + s.summation(forcing, (j, first, n - 1)))
            )
            if formula.has(s.Sum, s.Product, s.nan, s.zoo):
                raise ValueError("变换后的有限和仍未解出")
            derived_steps = [
                "改写为下一项等于当前项的倍数加驱动项。令乘积权重Pₙ="
                + maths(product)
                + "，两边除以Pₙ₊₁后相邻差为"
                + maths(forcing)
                + "，累加恢复通项。"
            ]
        if formula is None:
            raise ValueError("递推式未独立求解")
        result = s.simplify(formula)
        residual = relation.replace(
            lambda z: z.func == u, lambda z: result.subs(n, z.args[0])
        )
        if s.simplify(residual) != 0:
            raise ValueError("通项不满足递推")
        steps = derived_steps + [
            f"独立求解递推后，通项为 {maths(result)}。将n与n+1分别代入，原递推的差化为0；首项逐项回代也成立。"
        ]
        if "at" in task:
            result = s.simplify(result.subs(n, int(task["at"])))
            steps.append(f"代入n={task['at']}，得到{maths(result)}。")
        if op == "recurrence_sum":
            k = SYMBOLS["k"]
            term = formula.subs(n, k) * parse(task.get("weight", "1"))
            result = s.simplify(s.summation(term, (k, 1, parse(task["upper"]))))
            if result.has(s.Sum):
                raise ValueError("递推加权和未能化简")
            steps.append(
                "将独立求出的通项代入加权和，拆项求和并保留有限边界，得到"
                + maths(result)
                + "。"
            )
        # Recurrence forward stepping is independent of rsolve's construction.
        left = u(n + 1)
        forward = s.solve(relation, left)
        values = {
            int(i): v for i, v in ((j, parse(v)) for j, v in task["initial"].items())
        }
        cross = bool(forward) and all(
            formula.subs(n, j) == v for j, v in values.items()
        )
        if forward:
            first = min(values)
            current = values[first]
            for j in range(first, first + 8):
                current = s.simplify(forward[0].subs({u(n): current, n: j}))
                cross = cross and s.simplify(current - formula.subs(n, j + 1)) == 0
    elif op == "coefficient":
        expr = parse(task["expression"])
        power = int(task["power"])
        result = s.expand(expr).coeff(var, power)
        steps = [f"展开式中指数等于{power}的项才有贡献，提取系数得到{maths(result)}。"]
        cross = None
    elif op == "derivative":
        expr = parse(task["expression"])
        domain = interval(task)
        if continuous_domain(expr, var, domain) != domain:
            raise ValueError("定义域不符")
        derivative = s.factor(s.diff(expr, var))
        result = (
            derivative.subs(var, parse(str(task["at"]))) if "at" in task else derivative
        )
        steps = [f"在题设定义域内求导并因式分解，得到 {maths(derivative)}。"]
        if "at" in task:
            steps.append(f"代入指定横坐标，得到{maths(result)}。")
        cross = numeric_check(expr, var, derivative, domain)
    elif op in ("extrema", "optimum", "monotonicity"):
        expr = parse(task["expression"])
        domain = interval(task)
        details = extrema(expr, var, domain)
        derivative = s.factor(s.diff(expr, var))
        increasing = s.solve_univariate_inequality(
            derivative > 0, var, relational=False
        ).intersect(domain)
        decreasing = s.solve_univariate_inequality(
            derivative < 0, var, relational=False
        ).intersect(domain)
        critical = sorted(details["critical"], key=float)
        for i, point in enumerate(critical):
            left = critical[i - 1] if i else domain.start
            right = critical[i + 1] if i + 1 < len(critical) else domain.end
            tests = [
                point - 1 if left is -s.oo else (left + point) / 2,
                point + 1 if right is s.oo else (right + point) / 2,
            ]
            signs = [
                s.sign(derivative.subs(var, t))
                for t in tests
                if t in domain and t != point
            ]
            if 1 in signs:
                increasing = s.Union(increasing, s.FiniteSet(point))
            if -1 in signs:
                decreasing = s.Union(decreasing, s.FiniteSet(point))
        if op == "optimum":
            result = details[task.get("which", "maximum")]
        elif op == "monotonicity":
            result = {
                "increasing": increasing,
                "decreasing": decreasing,
                "critical": details["critical"],
            }
        else:
            result = {key: details[key] for key in ("minimum", "maximum")}
            result["minimum_at"] = [
                p
                for p, v, attained in details["candidates"]
                if v == details["minimum"] and attained
            ]
            result["maximum_at"] = [
                p
                for p, v, attained in details["candidates"]
                if v == details["maximum"] and attained
            ]
        steps = [
            f"定义域内连续，导数为{maths(derivative)}，驻点为{maths(s.FiniteSet(*details['critical']))}。",
            f"导数为正的区间为{maths(increasing)}，为负的区间为{maths(decreasing)}。",
        ]
        if op in ("extrema", "optimum"):
            steps.append("逐一比较驻点值、端点值与开端点极限。" + str(clean(result)))
        cross = numeric_check(expr, var, derivative, domain)
    elif op in ("parameter_monotone", "parameter_bound"):
        expr = parse(task["expression"])
        domain = interval(task)
        parameter = SYMBOLS[task.get("parameter", "a")]
        target = s.diff(expr, var) if op == "parameter_monotone" else expr
        coefficient = s.diff(target, parameter)
        if s.diff(coefficient, parameter) != 0:
            raise ValueError("仅对参数线性的量词任务有完整消元支持")
        rest = s.simplify(target.subs(parameter, 0))
        if s.simplify(target - coefficient * parameter - rest) != 0:
            raise ValueError("参数非线性")
        positive = s.solve_univariate_inequality(coefficient > 0, var, relational=False)
        negative = s.solve_univariate_inequality(coefficient < 0, var, relational=False)
        ratio = s.cancel(-rest / coefficient)
        bounds = extrema(ratio, var, domain)
        if domain.is_subset(positive):
            result = s.Interval(bounds["maximum"], s.oo)
        elif domain.is_subset(negative):
            result = s.Interval(-s.oo, bounds["minimum"])
        else:
            raise ValueError("参数系数变号，尚需分区消元，禁止直接发布")
        steps = [
            f"将要求化为{maths(coefficient)}a+({maths(rest)})≥0，对题设区间内每个x成立。",
            f"利用系数的固定符号，等价于a相对于{maths(ratio)}的全域界。",
            f"求该比值的驻点和边界极限，得到参数范围{maths(result)}。边界处仍满足弱不等式。",
        ]
        cross = numeric_check(ratio, var, s.diff(ratio, var), domain)
    elif op == "nonnegative":
        expr = parse(task["expression"])
        domain = interval(task)
        info = extrema(expr, var, domain)
        if info["minimum"] < 0:
            raise ValueError("待证明不等式存在负值")
        result = {
            "proved": True,
            "infimum": info["minimum"],
            "equality": [
                p for p, v, attained in info["candidates"] if v == 0 and attained
            ],
        }
        steps = [
            f"令两边之差为g(x)={maths(expr)}。导数为{maths(s.factor(s.diff(expr, var)))}。",
            f"检查驻点与全部边界，最小下界为{maths(info['minimum'])}，故差非负；取等点如上。",
        ]
        cross = numeric_check(expr, var, s.diff(expr, var), domain)
    elif op in ("probability", "count", "expectation", "probability_claim"):
        domains = task["sample_space"]
        if math.prod(len(v) for v in domains.values()) > 30000:
            raise ValueError("样本空间超过限制")
        tuples = list(itertools.product(*domains.values()))
        names = list(domains)
        event = parse(task["event"])
        condition = parse(task.get("condition", "1==1"))
        good = total = 0
        for values in tuples:
            at = {SYMBOLS[k]: v for k, v in zip(names, values)}
            if bool(condition.subs(at)):
                total += 1
                good += bool(event.subs(at))
        if total == 0:
            raise ValueError("条件事件概率为0")
        result = s.Rational(good, total)
        probability = result
        if op == "count":
            result = s.Integer(good)
        if op == "probability_claim":
            result = bool(
                s.simplify(probability - parse(task["claimed_probability"])) == 0
            )
        if op == "expectation":
            random_variable = parse(task["value"])
            result = s.simplify(
                sum(
                    random_variable.subs({SYMBOLS[k]: v for k, v in zip(names, values)})
                    for values in tuples
                    if bool(
                        condition.subs({SYMBOLS[k]: v for k, v in zip(names, values)})
                    )
                )
                / total
            )
        # Fraction normalization reuses the enumerated counts; it is not a second
        # symbolic/numeric solution. Keep the verification level conservative.
        if Fraction(good, total) != Fraction(
            int(s.numer(probability)), int(s.denom(probability))
        ):
            raise ValueError("概率有理数归一化失败")
        cross = None
        steps = [
            f"按题设等可能样本逐项枚举。条件下共{total}个有序结果，其中{good}个满足目标事件，故概率为{maths(probability)}。"
        ]
        if op == "probability_claim":
            steps.append(
                "与所给概率比较，该命题" + ("成立。" if result else "不成立。")
            )
        if op not in ("probability", "probability_claim"):
            steps = [
                f"逐个计入满足条件的有序结果，计算{'数量' if op == 'count' else '随机变量数值的算术平均'}，得到{maths(result)}。"
            ]
    elif op == "statistics":
        data = [parse(str(v)) for v in task["data"]]
        mean = sum(data) / len(data)
        kind = task["statistic"]
        result = (
            mean
            if kind == "mean"
            else s.simplify(sum((v - mean) ** 2 for v in data) / len(data))
            if kind == "variance"
            else sorted(data, key=float)[len(data) // 2]
        )
        if kind == "median" and len(data) % 2 == 0:
            ordered = sorted(data, key=float)
            result = (ordered[len(data) // 2 - 1] + ordered[len(data) // 2]) / 2
        steps = [
            f"样本量为{len(data)}，先排序或求均值{maths(mean)}，依照统计量定义得到{maths(result)}。"
        ]
        cross = None
    elif op in (
        "vector",
        "geometry",
        "intersection",
        "derivative_claim",
        "point_on_curve",
    ):
        if op == "vector":
            u = s.Matrix([parse(str(v)) for v in task["u"]])
            v = s.Matrix([parse(str(v)) for v in task["v"]])
            operation = task["operation"]
            if operation == "dot":
                result = u.dot(v)
            elif operation == "cosine_squared":
                result = u.dot(v) ** 2 / (u.dot(u) * v.dot(v))
            elif operation == "orthogonal":
                result = bool(u.dot(v) == 0)
            elif operation == "parallel":
                result = bool(u.cross(v) == s.zeros(3, 1))
            elif operation == "cross_norm_squared":
                result = u.cross(v).dot(u.cross(v))
            elif operation == "triangle_area_squared":
                result = u.cross(v).dot(u.cross(v)) / 4
            else:
                raise ValueError("向量操作未支持")
        elif op == "geometry":
            operation = task["operation"]
            if operation == "point_line_distance":
                px, py = map(s.Rational, task["point"])
                A, B, C = map(s.Rational, task["line"])
                result = abs(A * px + B * py + C) / s.sqrt(A * A + B * B)
            else:
                A, B, C = [
                    s.Matrix([parse(str(v)) for v in point])
                    for point in task["plane_points"]
                ]
                normal = (B - A).cross(C - A)
                norm = s.sqrt(normal.dot(normal))
                if norm == 0:
                    raise ValueError("三点不能确定平面")
                if operation == "plane_distance":
                    P = s.Matrix(task["point"])
                    result = s.simplify(abs(normal.dot(P - A)) / norm)
                elif operation == "line_plane_sine":
                    d = s.Matrix(task["direction"])
                    result = s.simplify(abs(normal.dot(d)) / (norm * s.sqrt(d.dot(d))))
                else:
                    raise ValueError("空间几何操作未支持")
        elif op == "intersection":
            x, y = SYMBOLS["x"], SYMBOLS["y"]
            roots = s.solve([parse(v) for v in task["curves"]], (x, y), dict=True)
            roots = [r for r in roots if all(v.is_real is True for v in r.values())]
            if task["ask"] == "count":
                result = len(roots)
            elif task["ask"] == "distance_squared" and len(roots) == 2:
                result = s.simplify(
                    sum((roots[0][z] - roots[1][z]) ** 2 for z in (x, y))
                )
            else:
                raise ValueError("交点数量不满足设问")
        elif op == "point_on_curve":
            curve = parse(task["curve"])
            x, y = SYMBOLS["x"], SYMBOLS["y"]
            result = bool(
                s.simplify(curve.subs({x: task["point"][0], y: task["point"][1]})) == 0
            )
        else:
            actual = s.diff(parse(task["expression"]), var)
            result = bool(s.simplify(actual - parse(task["claim_expression"])) == 0)
        result = s.simplify(result) if not isinstance(result, bool) else result
        cross = None
        steps = [
            "按坐标、内积、平面法向量或联立消元定义独立计算。结果为"
            + str(clean(result))
            + "。"
        ]
    elif op == "identity":
        left = parse(task["left"])
        right = parse(task["right"])
        residual = s.trigsimp(s.simplify(left - right))
        if residual != 0:
            raise ValueError("恒等命题不成立或无法证明")
        result = True
        cross = None
        steps = [f"将左减右，通分或使用恒等式得到{maths(residual)}，故恒等式成立。"]
    elif op == "comparison":
        relation = parse(task["claim"])
        if relation in (s.true, s.false):
            result = bool(relation)
            cross = None
        elif isinstance(relation, s.Equality):
            residual = s.trigsimp(s.simplify(relation.lhs - relation.rhs))
            if residual == 0:
                result = True
                cross = None
            else:
                free = sorted(residual.free_symbols, key=str)
                counterexample = None
                for values in itertools.product((1, 2, 3, 5), repeat=len(free)):
                    row = dict(zip(free, values))
                    if s.simplify(residual.subs(row)) != 0:
                        counterexample = row
                        break
                if counterexample is None:
                    raise ValueError("命题真值待审")
                result = False
                cross = None
        else:
            raise ValueError("带自由变量的不等命题尚待量词验证")
        steps = ["逐项代入条件计算命题真值。" + str(result)]
    else:
        raise ValueError("不支持的自由数学规格操作 " + str(op))
    if cross is False:
        raise ValueError("独立数值或枚举交叉检查失败")
    return {
        "result": clean(result),
        "steps": steps,
        "status": "已完成符号与数值交叉验证" if cross else "已完成程序验证",
        "programmatically_verified": True,
        "formal_proof": False,
        "cross_checked": bool(cross),
        "scope": scope,
        "engine": "SymPy "
        + s.__version__
        + " / independent finite difference or enumeration",
    }
