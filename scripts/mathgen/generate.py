"""Parameter sampling and problem drafting. Never calls the independent solver."""

import random
import sympy as sp

n, k = sp.symbols("n k", integer=True, positive=True)

FAMILIES = {
    "seq_interlace": ("数列", 1),
    "seq_reciprocal": ("数列", 2),
    "seq_alternating": ("数列", 4),
    "seq_telescope": ("数列", 3),
    "seq_optimize": ("数列", 5),
    "deriv_tangent": ("函数与导数", 1),
    "deriv_logquad": ("函数与导数", 2),
    "deriv_cubic": ("函数与导数", 3),
    "deriv_logbound": ("函数与导数", 4),
    "deriv_logroots": ("函数与导数", 5),
    "complex_norm": ("集合与复数", 1),
    "integer_set": ("集合与复数", 1),
    "trig_square": ("三角与向量", 2),
    "vector_sum": ("三角与向量", 2),
    "ellipse_chord": ("解析几何", 2),
    "urn_pair": ("概率统计", 2),
    "positive_roots": ("函数与导数", 3),
    "trig_count": ("三角与向量", 2),
    "geometry_assertions": ("立体几何", 3),
    "binomial": ("排列组合", 2),
    "variance": ("概率统计", 1),
    "urn_mixture": ("概率统计", 3),
    "tetrahedron": ("立体几何", 4),
    "ellipse_conjugate": ("解析几何", 4),
    "logquad_assertions": ("函数与导数", 3),
    "exp_peak": ("函数与导数", 3),
}


def latex(value):
    return sp.latex(sp.sympify(value))


def math(value):
    return r"\(" + latex(value) + r"\)"


def draft(family, seed, kind="constructed_response", points=10):
    rng = random.Random(seed)
    a, b, m = rng.randint(2, 5), rng.randint(2, 4), rng.randint(4, 8)
    p = {"a": a, "b": b, "m": m}
    u, v = a, a + b
    if family == "seq_interlace":
        text = (
            f"数列满足a₁={u}，a₂={v}，且对每个正整数n有aₙ₊₂=aₙ+2。求前{2 * m}项的和。"
        )
        values = [m * (u + v) + 2 * m * (m - 1)]
    elif family == "seq_reciprocal":
        text = (
            f"正项数列a₁={a}，aₙ₊₁=aₙ/(1+aₙ)。求"
            + math(sp.Symbol("a_n"))
            + f"及"
            + math(sp.Sum(sp.Symbol("a_k") * sp.Symbol("a_{k+1}"), (k, 1, m)))
            + "。"
        )
        values = [sp.Rational(a) / (1 + a * (n - 1)), a - sp.Rational(a, 1 + a * m)]
    elif family == "seq_alternating":
        text = f"数列满足a₁={a + 3}，aₙ₊₁={b}aₙ+({b + 1})(-1)ⁿ。求通项aₙ及前{m}项和。"
        values = [
            (a + 2) * b ** (n - 1) + (-1) ** (n - 1),
            (a + 2) * (b**m - 1) // (b - 1) + (1 - (-1) ** m) // 2,
        ]
    elif family == "seq_telescope":
        text = (
            f"数列u₁=2，uₙ₊₁=uₙ+2(n+1)。令Tₙ="
            + math(sp.Sum(1 / sp.Symbol("u_k"), (k, 1, n)))
            + f"。求uₙ、Tₙ及使Tₙ>1-1/{m}的最小正整数n。"
        )
        values = [n * (n + 1), n / (n + 1), m]
    elif family == "seq_optimize":
        text = (
            f"正项数列的前{m}项满足"
            + math(sp.Sum(sp.Symbol("a_k"), (k, 1, m)))
            + f"={a * m}。求"
            + math(sp.Sum(k**2 / sp.Symbol("a_k"), (k, 1, m)))
            + "的最小值，并写出所有取等的前"
            + str(m)
            + "项。"
        )
        values = [sp.Rational(m * (m + 1) ** 2, 4 * a), sp.Rational(2 * a, m + 1) * k]
    elif family == "exp_peak":
        text = (
            "求函数"
            + math(sp.Symbol("x") * sp.exp(-sp.Symbol("x") / a))
            + "（x∈R）的最大值。"
        )
        values = [a / sp.E]
    elif family == "logquad_assertions":
        text = f"设f(x)=ln x-({a}/2)x²（x>0）。选择所有正确命题。"
        values = [1, 1, 1, 0]
        p["statements"] = [
            "f在" + math(1 / sp.sqrt(a)) + "处取得最大值",
            "最大值为" + math(-(sp.log(a) + 1) / 2),
            "f′在定义域内严格递减",
            "f在定义域内的最小值可以取到",
        ]
    elif family == "deriv_tangent":
        text = (
            f"函数f(x)=x³+Ax²+B在x={a}处的切线为y={b}。求(A,B)，并给出f的全部单调区间。"
        )
        values = [-sp.Rational(3 * a, 2), b + sp.Rational(a**3, 2)]
    elif family == "deriv_logquad":
        text = f"设c>0，f(x)=ln x-cx²（x>0）。求最大值及取到最大值的x；再求使f(x)≤-1/2对所有x>0成立的c的范围。"
        values = [
            1 / sp.sqrt(2 * sp.Symbol("c", positive=True)),
            -(sp.log(2 * sp.Symbol("c", positive=True)) + 1) / 2,
            sp.Rational(1, 2),
        ]
    elif family == "deriv_cubic":
        text = f"设c≥0，f(x)=x³-3cx。讨论f在[-{a},{a}]上的最大值M(c)，写明所有分界点。"
        # Branch coefficients and breakpoints are verified independently.
        values = [sp.Rational(a * a, 4), a * a]
    elif family == "deriv_logbound":
        text = "求实数c的最大值，使ln x≥c(x-1)/(x+1)对所有x≥1成立。证明所得常数最优。"
        values = [2]
    elif family == "deriv_logroots":
        text = "设F(x)=(ln x)³-3ln x-c（x>0）。(1)求F(x)=0有三个互异正根的c的范围；(2)记三根x₁<x₂<x₃，证明乘积为1；(3)若x₁x₃=x₂²，求c和三根。"
        values = [-2, 2, 1, 0, sp.exp(-sp.sqrt(3)), 1, sp.exp(sp.sqrt(3))]
    elif family == "complex_norm":
        text = f"复数z满足z+共轭z={2 * a}，且|z-{b}|²={(a - b) ** 2 + m}。求(Im z)²。"
        values = [m]
    elif family == "integer_set":
        text = f"集合A={{x∈Z|(x-{a})(x-{a + m})≤0}}，B为{b}的整数倍的集合。求A中不属于B的元素个数。"
        values = [sum(t % b != 0 for t in range(a, a + m + 1))]
    elif family == "trig_square":
        text = r"已知\(t\in(0,\pi/2)\)，且\(\sin t+\cos t=\sqrt{6}/2\)。求\(\sin 2t\)。"
        values = [sp.Rational(1, 2)]
    elif family == "vector_sum":
        text = f"向量u=({a},1)，v=(1,t)，且u⊥v。求|u+v|²。"
        values = [2 * (a * a + 1)]
    elif family == "ellipse_chord":
        a = a + b
        p["a"] = a
        text = (
            f"椭圆"
            + math(sp.Symbol("x") ** 2 / (a * a) + sp.Symbol("y") ** 2 / (b * b))
            + "=1被直线y="
            + str(sp.Rational(b, 2))
            + "截得的弦长是多少？"
        )
        values = [a * sp.sqrt(3)]
    elif family == "urn_pair":
        text = f"袋中有{a}个红球、{b}个蓝球，各球等可能取到。无放回连续取2球，求恰好一红一蓝的概率。"
        values = [sp.Rational(2 * a * b, (a + b) * (a + b - 1))]
    elif family == "positive_roots":
        text = "关于x的方程x²-2tx+t=0有两个互异正实根。t的取值范围的有限端点是多少？"
        values = [1]
    elif family == "trig_count":
        text = r"方程\(\sin(2x)=1/2\)在\(0<x<2\pi\)内有多少个解？"
        values = [4]
    elif family == "geometry_assertions":
        text = f"空间取O=(0,0,0)，A=({a},0,0)，B=(0,{a},0)，C=(0,0,{b})，M为AB中点。选择所有正确命题。"
        p["statements"] = ["OA垂直平面OBC", "CM平行AB", "CM垂直AB", "OA平行CM"]
        values = [1, 0, 1, 0]
    elif family == "binomial":
        text = (
            f"求"
            + math((sp.Symbol("x") + 1 / sp.Symbol("x")) ** (2 * b))
            + f"展开式中x²的系数。"
        )
        values = [sp.binomial(2 * b, b - 1)]
    elif family == "variance":
        text = (
            f"某组数据X的均值为{a}，方差为{b}。每个数据改为Y={m}X-{a}，求新数据的方差。"
        )
        values = [m * m * b]
    elif family == "urn_mixture":
        text = "先等可能选甲、乙之一，再从选中的袋中有放回抽两次。甲袋红球概率1/3，乙袋红球概率2/3。记两次红球指示量为I₁,I₂。(1)求首次红球的概率；(2)已知首次红球，求选中乙袋的概率；(3)求两次均红概率，判断I₁,I₂是否独立并求其协方差。"
        values = [
            sp.Rational(1, 2),
            sp.Rational(2, 3),
            sp.Rational(5, 18),
            sp.Rational(1, 36),
        ]
    elif family == "tetrahedron":
        text = f"O=(0,0,0)，A=({a},0,0)，B=(0,{a},0)，C=(0,0,h)，h>0。M,N分别为AC,BC中点。(1)证明MN∥AB；(2)用h表示O到平面ABC距离；(3)若直线OC与平面ABC夹角的正弦为1/√3，求h及上述距离。"
        h = sp.Symbol("h", positive=True)
        values = [a * h / sp.sqrt(a * a + 2 * h * h), a, a / sp.sqrt(3)]
    elif family == "ellipse_conjugate":
        # a>b is enforced here, not assumed from random sampling.
        p["a"], p["b"] = a + b, b
        a = p["a"]
        text = (
            f"椭圆"
            + math(sp.Symbol("x") ** 2 / (a * a) + sp.Symbol("y") ** 2 / (b * b))
            + "=1上取P=("
            + str(a)
            + "cos t,"
            + str(b)
            + "sin t)，Q=(-"
            + str(a)
            + "sin t,"
            + str(b)
            + "cos t)，t∈R，O为原点。(1)证明△OPQ面积不变并求其值；(2)求PQ长度范围；(3)求中点M轨迹的方程并说明是否取遍。"
        )
        values = [
            sp.Rational(a * b, 2),
            b * sp.sqrt(2),
            a * sp.sqrt(2),
            sp.Rational(a * a, 2),
            sp.Rational(b * b, 2),
        ]
    else:
        raise ValueError("不支持的题目族 " + family)
    return {
        "family": family,
        "parameters": p,
        "stem": text,
        "proposed_values": [str(sp.sympify(v)) for v in values],
        "kind": kind,
        "points": points,
        "module": FAMILIES[family][0],
        "difficulty": FAMILIES[family][1],
        "difficulty_basis": "基于方法层数、分类和量词复杂度的设计等级，未经考生实测",
        "options": None,
        "generation": {
            "backend": "runtime_parameterized_family",
            "seed": seed,
            "host_authored_design_revision": "v1",
            "model_version": "not_exposed_by_host",
        },
    }


def add_options(question, seed):
    from .review import misconception_options

    rng = random.Random(seed)
    values = [sp.sympify(x) for x in question["proposed_values"]]
    if question["kind"] == "single_choice":
        target = values[0]
        options = misconception_options(question, target)
        rng.shuffle(options)
        question["options"] = {
            key: {"text": math(v), "semantic_value": str(v), "error_path": reason}
            for key, (v, reason) in zip("ABCD", options)
        }
    elif question["kind"] == "multiple_choice":
        question["stem"] = question["stem"].replace("选择所有正确命题。", "")
        question["stem"] += " 判断下列命题，选择所有正确选项。"
        if question["family"] in ("geometry_assertions", "logquad_assertions"):
            claims = question["parameters"]["statements"]
            truth = values
        elif question["family"] == "seq_interlace":
            a, b, m = (question["parameters"][v] for v in ("a", "b", "m"))
            claims = [
                "题中所求和为" + math(values[0]),
                "奇数项构成公比为2的等比数列",
                "偶数项构成公差为2的等差数列",
                "整个数列一定是等差数列",
            ]
            truth = [1, 0, 1, 0]
        elif question["family"] == "variance":
            a, b, m = (question["parameters"][v] for v in ("a", "b", "m"))
            claims = [
                "新数据的均值为" + str(m * a - a),
                "新数据的方差为" + str(m * m * b),
                "新数据的标准差为" + str(m * b),
                "新数据的方差受平移常数影响",
            ]
            truth = [1, 1, 0, 0]
        else:
            raise ValueError("该题目族尚不支持多选命题")
        question["options"] = {
            key: {"text": v, "assertion_index": i}
            for i, (key, v) in enumerate(zip("ABCD", claims))
        }
        question["proposal_truth_mask"] = [int(t) for t in truth]
    return question
