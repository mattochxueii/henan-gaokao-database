"""Independent derivations. Does not read generator claims, options, or solutions."""

import itertools
import sympy as s

n, k = s.symbols("n k", integer=True, positive=True)
x = s.Symbol("x", real=True)


def solve(family, p):
    a, b, m = (p[v] for v in ("a", "b", "m"))
    checks = []
    proof = False
    if family == "seq_interlace":
        vals = [s.summation((a + (a + b) + 4 * k), (k, 0, m - 1))]
        steps = [
            f"奇数项a₂ⱼ₋₁={a}+2(j-1)，偶数项a₂ⱼ={a + b}+2(j-1)。",
            f"相邻两项之和为{2 * a + b}+4(j-1)，j从1取到{m}，故总和为{m}×{2 * a + b}+4×{m}×{m - 1}/2={vals[0]}。",
        ]
    elif family == "seq_reciprocal":
        formula = 1 / (s.Rational(1, a) + n - 1)
        vals = [
            formula,
            s.summation(formula.subs(n, k) * formula.subs(n, k + 1), (k, 1, m)),
        ]
        checks.append(s.simplify(1 / formula.subs(n, n + 1) - 1 / formula - 1) == 0)
        steps = [
            f"取倒数得1/aₙ₊₁=1/aₙ+1，所以1/aₙ=1/{a}+n-1，通项为{a}/[1+{a}(n-1)]。",
            f"将原递推移项，aₖ-aₖ₊₁=aₖ²/(1+aₖ)=aₖaₖ₊₁。",
            f"从k=1加到{m}，中间项全部抵消，得到a₁-a{m + 1}={a}-{s.Rational(a, 1 + a * m)}={s.simplify(vals[1])}。",
        ]
    elif family == "seq_alternating":
        # Solve two-step recurrence, not the generator's closed-form construction.
        c = a + 3
        z = s.Function("z")
        formula = s.rsolve(z(n + 1) - b * z(n) - (b + 1) * (-1) ** n, z(n), {z(1): c})
        vals = [formula, s.summation(formula, (n, 1, m))]
        checks.append(
            s.simplify(formula.subs(n, n + 1) - b * formula - (b + 1) * (-1) ** n) == 0
        )
        steps = [
            f"令cₙ=aₙ-(-1)ⁿ⁻¹。代入原递推可得cₙ₊₁={b}cₙ，且c₁={a + 2}。",
            f"所以cₙ={a + 2}×{b}ⁿ⁻¹，aₙ={a + 2}×{b}ⁿ⁻¹+(-1)ⁿ⁻¹。代回原递推与首项均相符。",
            f"前{m}项的等比部分和为({a + 2})({b}^{m}-1)/({b}-1)；交错部分和为[1-(-1)^{m}]/2。相加为{s.simplify(vals[1])}。",
        ]
    elif family == "seq_telescope":
        u = 2 + s.summation(2 * (k + 1), (k, 1, n - 1))
        total = s.summation(1 / u.subs(n, k), (k, 1, n))
        # Strict inequality is checked at the adjacent integer boundary.
        first = next(
            j for j in range(1, 100) if total.subs(n, j) > 1 - s.Rational(1, m)
        )
        vals = [u, total, first]
        checks.extend(
            [
                total.subs(n, first - 1) <= 1 - s.Rational(1, m),
                total.subs(n, first) > 1 - s.Rational(1, m),
            ]
        )
        steps = [
            "累加递推得到uₙ=n(n+1)。",
            "1/[k(k+1)]=1/k-1/(k+1)，所以Tₙ=n/(n+1)。",
            f"严格不等式化为n+1>{m}，最小整数n={m}，边界n={m - 1}只能取等。",
        ]
    elif family == "seq_optimize":
        W = s.summation(k, (k, 1, m))
        C = a * m
        equality = C * k / W
        vals = [W**2 / C, equality]
        checks.extend(
            [
                s.summation(equality, (k, 1, m)) == C,
                s.summation(k * k / equality, (k, 1, m)) == W**2 / C,
            ]
        )
        proof = True
        steps = [
            f"记W=1+…+{m}={W}，C=Σaₖ={C}，T=Σk²/aₖ。由平方和非负，Σ(k/√aₖ-W√aₖ/C)²=T-W²/C≥0。因此T≥{W}²/{C}={vals[0]}。",
            f"等号当且仅当k/aₖ为同一正常数。由总和得aₖ=({C}/{W})k，对k=1,…,{m}均为正且满足总和，代入达到下界。",
            "程序验证等号构造及其代入值。全体正项上的下界依赖上述不等式证明。",
        ]
    elif family == "exp_peak":
        f = x * s.exp(-x / a)
        checks.append(s.simplify(s.diff(f, x) - s.exp(-x / a) * (1 - x / a)) == 0)
        vals = [f.subs(x, a)]
        proof = True
        steps = [
            f"f′(x)=exp(-x/{a})(1-x/{a})。指数因子始终正，导数在x<{a}为正、x>{a}为负，所以在x={a}唯一取得全局最大值{a}/e。"
        ]
    elif family == "logquad_assertions":
        f = s.log(x) - s.Rational(a, 2) * x * x
        root = 1 / s.sqrt(a)
        checks.extend(
            [
                s.simplify(s.diff(f, x).subs(x, root)) == 0,
                s.simplify(s.diff(f, x, 2) + a + 1 / x**2) == 0,
                s.simplify(f.subs(x, root) + (s.log(a) + 1) / 2) == 0,
            ]
        )
        vals = [1, 1, 1, 0]
        proof = True
        steps = [
            f"f′=1/x-{a}x，唯一正零点为1/√{a}；f″=-1/x²-{a}<0，所以导数严格递减，零点为全局最大点。",
            f"代入得最大值-(ln {a}+1)/2。x趋于0的正侧时f趋于负无穷，所以无可取的最小值。",
        ]
    elif family == "deriv_tangent":
        A, B = s.symbols("A B")
        f = x**3 + A * x * x + B
        result = s.solve([s.diff(f, x).subs(x, a), f.subs(x, a) - b], (A, B))
        vals = [result[A], result[B]]
        checks.append(s.factor(s.diff(f.subs(result), x)) == 3 * x * (x - a))
        steps = [
            "水平切线要求f′(a)=0、f(a)=b。联立求两个系数。",
            f"代回得f′(x)=3x(x-{a})。增区间为(-∞,0)、({a},∞)，减区间为(0,{a})。端点的区间合并按单调定义处理。",
        ]
    elif family == "deriv_logquad":
        c = s.Symbol("c", positive=True)
        f = s.log(x) - c * x * x
        root = 1 / s.sqrt(2 * c)
        vals = [root, s.simplify(f.subs(x, root)), s.Rational(1, 2)]
        checks.extend(
            [
                s.simplify(s.diff(f, x).subs(x, root)) == 0,
                s.simplify(s.diff(f, x, 2) + 2 * c + 1 / x**2) == 0,
            ]
        )
        proof = True
        steps = [
            "f′=1/x-2cx，在唯一正零点前正后负，故为全局最大点。",
            "最大值为-(ln(2c)+1)/2。它≤-1/2等价于ln(2c)≥0，即c≥1/2。",
        ]
    elif family == "deriv_cubic":
        t = s.Symbol("t", nonnegative=True)
        # t=sqrt(c)/a compares interior critical value with right endpoint.
        checks.append(
            s.expand((2 * t - 1) * (t + 1) ** 2 - (2 * t**3 + 3 * t * t - 1)) == 0
        )
        vals = [s.Rational(a * a, 4), a * a]
        proof = True
        steps = [
            f"f′=3(x²-c)。当0≤c≤{a * a}时内部极大点为-√c，候选最大值是2c√c与{a**3}-{3 * a}c。",
            f"令t=√c/{a}，两者之差除以{a**3}为(2t-1)(t+1)²，故切换点c={s.Rational(a * a, 4)}。",
            f"M(c)分三段为 {a**3}-{3 * a}c（0≤c≤{s.Rational(a * a, 4)}），2c√c（{s.Rational(a * a, 4)}≤c≤{a * a}），{3 * a}c-{a**3}（c≥{a * a}）。交界处值相同。",
        ]
    elif family == "deriv_logbound":
        g = s.log(x) - 2 * (x - 1) / (x + 1)
        checks.append(s.simplify(s.diff(g, x) - (x - 1) ** 2 / (x * (x + 1) ** 2)) == 0)
        vals = [2]
        proof = True
        steps = [
            "c=2时差函数在x=1为0，导数为(x-1)²/[x(x+1)²]≥0，所以全域成立。",
            "若c>2，差函数在1的右导数1-c/2<0，故足够靠近1的右侧取负值，不能成立。",
        ]
    elif family == "deriv_logroots":
        t = s.Symbol("t", real=True)
        f = t**3 - 3 * t
        checks.extend(
            [s.diff(f, t) == 3 * t * t - 3, f.subs(t, -1) == 2, f.subs(t, 1) == -2]
        )
        roots = s.solve(f, t)
        vals = [-2, 2, 1, 0] + [s.exp(r) for r in sorted(roots, key=lambda r: float(r))]
        proof = True
        steps = [
            "令t=ln x，实数t与正数x一一对应。g(t)=t³-3t在(-∞,-1)、(1,∞)递增，在(-1,1)递减，极值2、-2。",
            "因此恰有三个互异正根当且仅当-2<c<2，端点会产生重根。",
            "由三次方程韦达定理，三个t根之和为0，故三个x根之积为exp(0)=1。",
            "附加条件结合乘积得x₂³=1，所以x₂=1、t₂=0、c=0，另两根为exp(±√3)。",
        ]
    elif family == "complex_norm":
        y = s.Symbol("y", real=True)
        z = a + s.I * y
        equation = s.expand_complex((z - b) * s.conjugate(z - b) - ((a - b) ** 2 + m))
        vals = [s.solve(equation, y * y)[0]]
        steps = [
            f"由z+共轭z={2 * a}得Re z={a}。令z={a}+yi，模平方条件成为({a}-{b})²+y²={(a - b) ** 2 + m}，因此y²={vals[0]}。"
        ]
    elif family == "integer_set":
        domain = s.solve_univariate_inequality(
            (x - a) * (x - a - m) <= 0, x, relational=False
        )
        selected = [j for j in range(-50, 51) if j in domain and j % b]
        vals = [len(selected)]
        steps = [
            f"二次不等式给出{a}≤x≤{a + m}，取其中整数再剔除{b}的整倍数，保留{selected}，共{len(selected)}个。"
        ]
    elif family == "trig_square":
        vals = [(s.sqrt(6) / 2) ** 2 - 1]
        steps = [
            "两边平方并用sin²t+cos²t=1，得到sin 2t=(sin t+cos t)²-1。给定和在第一象限的可取范围内。"
        ]
    elif family == "vector_sum":
        t = s.Symbol("t", real=True)
        u = s.Matrix([a, 1])
        v = s.Matrix([1, t])
        root = s.solve(u.dot(v), t)[0]
        vals = [s.expand((u + v).dot(u + v)).subs(t, root)]
        steps = [
            f"垂直要求u·v={a}+t=0，故t={-a}。和向量为({a + 1},{1 - a})，长度平方为({a + 1})²+({1 - a})²={vals[0]}。"
        ]
    elif family == "ellipse_chord":
        # Substitute y=b/2, solve the quadratic for both endpoints.
        roots = s.solve(x * x / a**2 + s.Rational(1, 4) - 1, x)
        vals = [max(roots) - min(roots)]
        steps = [
            f"代入y={s.Rational(b, 2)}，纵坐标项为1/4，所以x²=3×{a * a}/4。两个端点横坐标为±{s.Rational(a, 2)}√3，弦长为{a}√3。"
        ]
    elif family == "urn_pair":
        # Enumerate labelled draws, independently from combinatorial formula.
        balls = list(range(a + b))
        good = total = 0
        for first, second in itertools.permutations(balls, 2):
            total += 1
            good += (first < a) != (second < a)
        vals = [s.Rational(good, total)]
        steps = [
            f"给每球编号，有序不放回二元组总数为{a + b}×{a + b - 1}={total}。两颜色不同有2×{a}×{b}={good}种，概率为{good}/{total}={vals[0]}。程序逐组枚举也得到相同计数。"
        ]
    elif family == "positive_roots":
        t = s.Symbol("t", real=True)
        region = s.reduce_inequalities([t > 0, t * t - t > 0], t)
        vals = [1]
        checks.append(
            s.solve_univariate_inequality(t * t - t > 0, t, relational=False).intersect(
                s.Interval.open(0, s.oo)
            )
            == s.Interval.open(1, s.oo)
        )
        proof = True
        steps = [
            "两根互异实根要求判别式4t(t-1)>0；两根为正还要求和2t>0、积t>0。合并得到t>1，有限端点1不取。"
        ]
    elif family == "trig_count":
        # Independent period-by-period roots in the doubled angle interval.
        roots = {s.pi / 12 + j * s.pi for j in range(-2, 4)} | {
            5 * s.pi / 12 + j * s.pi for j in range(-2, 4)
        }
        vals = [sum(bool(0 < r < 2 * s.pi) for r in roots)]
        steps = [
            "令u=2x，则0<u<4π。每个完整周期sin u=1/2有两解，两个周期共4解，均不在端点。"
        ]
    elif family == "geometry_assertions":
        A = s.Matrix([a, 0, 0])
        B = s.Matrix([0, a, 0])
        C = s.Matrix([0, 0, b])
        M = (A + B) / 2
        cm = M - C
        ab = B - A
        truth = [
            A.dot(B) == 0 and A.dot(C) == 0,
            cm.cross(ab) == s.zeros(3, 1),
            cm.dot(ab) == 0,
            A.cross(cm) == s.zeros(3, 1),
        ]
        vals = [int(v) for v in truth]
        steps = [
            "用坐标向量判断。OA与OB、OC均垂直，故垂直于其张成平面；CM·AB=0；另外两个平行条件的叉积均不为零。"
        ]
    elif family == "binomial":
        vals = [s.expand((x + 1 / x) ** (2 * b)).coeff(x, 2)]
        steps = [
            f"从{2 * b}个因子中选j个x⁻¹，通项x指数为{2 * b}-2j。令它为2得j={b - 1}，系数为组合数C({2 * b},{b - 1})={vals[0]}。程序用完全展开独立提取同一系数。"
        ]
    elif family == "variance":
        vals = [m * m * b]
        checks.append(
            s.simplify(s.expand((m * (x - a)) ** 2) - m * m * (x - a) ** 2) == 0
        )
        steps = [
            f"EY={m}×{a}-{a}={m * a - a}，所以Y-EY={m}(X-EX)。平方取平均得到VarY={m}²×{b}={vals[0]}，标准差为{m}√{b}。"
        ]
    elif family == "urn_mixture":
        p1, p2 = s.Rational(1, 3), s.Rational(2, 3)
        marginal = (p1 + p2) / 2
        joint = (p1 * p1 + p2 * p2) / 2
        vals = [marginal, (p2 / 2) / marginal, joint, joint - marginal * marginal]
        checks.append(joint != marginal * marginal)
        steps = [
            "全概率公式算一次红球概率。用贝叶斯公式算首次红后选乙的概率。",
            "同一袋被固定，两次抽取只在给定袋时独立；无条件两次均红为(p甲²+p乙²)/2。",
            "与边际概率乘积不等，所以无条件不独立。协方差为联合概率减边际乘积。",
        ]
    elif family == "tetrahedron":
        h = s.Symbol("h", positive=True)
        A = s.Matrix([a, 0, 0])
        B = s.Matrix([0, a, 0])
        C = s.Matrix([0, 0, h])
        normal = (B - A).cross(C - A)
        norm = s.sqrt(normal.dot(normal))
        distance = s.simplify(abs(normal.dot(A)) / norm)
        sine = s.simplify(abs(normal.dot(C)) / norm / h)
        height = s.solve(sine**2 - s.Rational(1, 3), h)[0]
        vals = [distance, height, s.simplify(distance.subs(h, height))]
        checks.append(
            s.simplify((B + C) / 2 - (A + C) / 2 - (B - A) / 2) == s.zeros(3, 1)
        )
        steps = [
            "中点向量MN=AB/2，且MN在底边上方、与AB不同线，所以平行。",
            f"用AB×AC可取法向量(h,h,{a})，平面方程hx+hy+{a}z={a}h。",
            f"点O到面的距离为{a}h/√({a * a}+2h²)。直线OC的单位方向为(0,0,1)，线面角正弦为{a}/√({a * a}+2h²)。",
            f"其平方等于1/3给出3×{a * a}={a * a}+2h²，h>0故h={a}，距离={s.simplify(vals[2])}。",
        ]
    elif family == "ellipse_conjugate":
        t = s.Symbol("t", real=True)
        P = s.Matrix([a * s.cos(t), b * s.sin(t)])
        Q = s.Matrix([-a * s.sin(t), b * s.cos(t)])
        det = s.trigsimp(s.det(s.Matrix.hstack(P, Q)))
        mid = (P + Q) / 2
        checks.extend(
            [
                det == a * b,
                s.trigsimp(
                    mid[0] ** 2 / (s.Rational(a * a, 2))
                    + mid[1] ** 2 / (s.Rational(b * b, 2))
                )
                == 1,
            ]
        )
        length2 = s.trigsimp((P - Q).dot(P - Q))
        checks.append(
            s.trigsimp(length2 - (a * a + b * b + (a * a - b * b) * s.sin(2 * t))) == 0
        )
        vals = [
            det / 2,
            b * s.sqrt(2),
            a * s.sqrt(2),
            s.Rational(a * a, 2),
            s.Rational(b * b, 2),
        ]
        proof = True
        steps = [
            f"为书写简洁，记长半轴a={a}、短半轴b={b}。面积为行列式绝对值的一半，sin²+cos²消去参数，得ab/2={vals[0]}。",
            "长度平方为a²+b²+(a²-b²)sin2t，所以范围是[√2b,√2a]且两端可取。",
            "中点为(a/√2 cos(t+π/4),b/√2 sin(t+π/4))。参数平移遍历整个圆，故轨迹椭圆取遍。",
        ]
    else:
        raise ValueError("独立求解器不支持该题目族")
    return {
        "values": [s.simplify(v) for v in vals],
        "steps": steps,
        "checks": [bool(c) for c in checks],
        "reasoning_review_required": proof,
    }
