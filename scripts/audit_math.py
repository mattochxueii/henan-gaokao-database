"""Targeted symbolic cross-checks of version-sensitive original candidate conditions."""

import bootstrap
import itertools
import sympy as s
from analysis_db import research
from gaokao import ROOT
from storage import atomic_json


def main():
    rows = {q["id"]: q for q in research(ROOT)}
    results = []

    def add(year, number, description, value, passed):
        q = rows[f"{year}-cn-math-national-1:q{number:03d}"]
        results.append(
            {
                "question_id": q["id"],
                "candidate_sha256": q["analysis"]["candidate_sha256"],
                "description": description,
                "computed": str(value),
                "passed": bool(passed),
                "scope": "显式转录条件的程序复算，题面页图仍由AI视觉审阅",
                "source_id": q["candidate"]["source_id"],
                "page": q["candidate"]["page"],
            }
        )

    centers = [s.pi / 3 + j * s.pi / 2 for j in range(-3, 4)]
    minimum = min(c for c in centers if c > 0)
    add(2025, 4, "当前中心族的最小正横坐标", minimum, minimum == s.pi / 3)
    wind = s.Matrix([-3, -1]) + s.Matrix([1, 3])
    speed = s.sqrt(wind.dot(wind))
    add(2025, 6, "按页图两个有向箭头求真实风速", speed, speed == 2 * s.sqrt(2))
    # Bottom triangle A(0,sqrt3/2), B(-1/2,0), C(1/2,0), D(0,0).
    B = s.Matrix([-s.Rational(1, 2), 0, 0])
    C = s.Matrix([s.Rational(1, 2), 0, 0])
    AD = s.Matrix([0, -s.sqrt(3) / 2, 0])
    up = s.Matrix([0, 0, 1])
    normal = AD.cross(up)
    add(
        2025,
        9,
        "BC垂直AD与侧棱；CC1方向在AA1D平面内",
        "B,C成立",
        (C - B).dot(AD) == 0 and (C - B).dot(up) == 0 and up.dot(normal) == 0,
    )
    A = s.pi / 12
    Bangle = 5 * s.pi / 12
    add(
        2025,
        11,
        "已证明C为直角后的正弦和与边平方和",
        s.simplify(s.sin(A) + s.sin(Bangle)),
        s.simplify(s.sin(A) + s.sin(Bangle) - s.sqrt(6) / 2) == 0,
    )
    chi = s.Rational(1000 * (20 * 20 - 180 * 780) ** 2, 200 * 800 * 800 * 200)
    add(
        2025,
        15,
        "列联表卡方与所用0.001临界值",
        chi,
        chi == s.Rational(6125, 8) and chi > s.Rational(10828, 1000),
    )
    z = 3 + 2 * s.I
    village = s.simplify((z + 3) / (z - s.I))
    jin = s.simplify((z + 3) / (z - 1))
    add(
        2026,
        9,
        "D项在两份原始候选上的真值",
        "z-i: " + str(village) + "; z-1: " + str(jin),
        village == 2 and jin == 2 - s.I,
    )
    e = s.sqrt(1 + s.Rational(5, 6))
    add(
        2026,
        12,
        "当前系数5的离心率，另一版系数3单独计算",
        e,
        s.simplify(e - s.sqrt(s.Rational(11, 6))) == 0,
    )
    values = [-2 * s.cos(a * 2 * s.pi / 3) for a in (-2, -1, 1, 2)]
    add(
        2026,
        13,
        "偶性和单调性推理允许的全部整数频率代入目标值",
        values,
        all(v == 1 for v in values),
    )
    p = s.Rational(1, 3)
    N = 4
    distribution = [(1 - p) ** (j - 1) * p for j in range(1, N)] + [(1 - p) ** (N - 1)]
    add(
        2026,
        17,
        "枚举截断停止规则后分布归一和末项",
        distribution,
        sum(distribution) == 1 and distribution[-1] == s.Rational(8, 27),
    )
    for kval, mval in itertools.product(range(4), repeat=2):
        if kval + mval <= N - 1:
            tail = lambda t: sum(distribution[t:])
            assert s.simplify(tail(kval + mval) / tail(kval) - tail(mval)) == 0
    slope = s.sqrt(5) / 2
    t = s.Symbol("t")
    roots = s.solve((3 + 4 * slope * slope) * t * t - 6 * t - 9, t)
    v, u = min(roots), max(roots)
    add(
        2026,
        18,
        "Q第三象限版面积根比；P第三象限版将要求负根和",
        roots,
        s.simplify(u + 2 * v) == 0 and u + v > 0,
    )
    assert all(item["passed"] for item in results)
    atomic_json(
        ROOT / "reports/original-math-checks.json",
        {
            "checks": results,
            "passed": len(results),
            "whole_paper_proofs_programmatically_verified": False,
            "human_reviewed": False,
        },
    )
    print(f"{len(results)} targeted candidate checks passed")


if __name__ == "__main__":
    main()
