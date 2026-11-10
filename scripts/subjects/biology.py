"""Check bounded high-school biology tasks without inferring unstated mechanisms."""

from collections import Counter
from fractions import Fraction
from itertools import product
import re


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, name):
    _require(type(value) in (int, str), f"{name}须为整数或精确数字字符串")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{name}不是可计算的数值") from exc


def _result(answer, checks, explanation):
    return {
        "answer": answer,
        "checks": checks,
        "unverified": [],
        "explanation": explanation,
    }


def _gametes(genotype):
    _require(
        isinstance(genotype, str) and re.fullmatch(r"[Aa]{2}[Bb]{2}", genotype),
        "亲本必须给出完整的 A/a 和 B/b 二倍体基因型",
    )
    return product(genotype[:2], genotype[2:])


def _mendelian(problem):
    for name in ("independent_loci", "complete_dominance", "equal_viability"):
        _require(problem.get(name) is True, f"未确认本算子的遗传假设 {name}")
    parents = problem.get("parents")
    _require(isinstance(parents, list) and len(parents) == 2, "须有两个亲本")
    counts = Counter()
    for (left_a, left_b), (right_a, right_b) in product(*map(_gametes, parents)):
        child = "".join(sorted((left_a, right_a)) + sorted((left_b, right_b)))
        counts[child] += 1

    excluded = problem.get("exclude")
    _require(
        isinstance(excluded, list)
        and all(isinstance(g, str) and g in counts for g in excluded)
        and len(excluded) == len(set(excluded)),
        "筛除条件须为不重复且能产生的完整基因型",
    )
    total = sum(counts.values())
    kept = {g: n for g, n in counts.items() if g not in excluded}
    retained = sum(kept.values())
    _require(retained > 0, "所求条件事件概率为零")
    both_dominant = sum(n for g, n in kept.items() if "A" in g and "B" in g)
    answer = {
        "筛除比例": str(Fraction(total - retained, total)),
        "保留者中AaBb比例": str(Fraction(kept.get("AaBb", 0), retained)),
        "保留者中双显性比例": str(Fraction(both_dominant, retained)),
    }
    distribution = "、".join(f"{g} 为 {Fraction(n, total)}" for g, n in sorted(counts.items()))
    return _result(
        answer,
        ["两对常染色体等位基因独立分配", "配子组合逐项枚举", "剔除后以非零条件事件重新归一化"],
        f"按每对等位基因等概率分离，两亲本配子独立组合。合子分布为{distribution}。"
        f"剔除指定基因型后，用各目标在保留合子中的组合数除以保留组合总数 {retained}。"
        "这一概率计算限于题设独立分配、完全显性和筛选前等存活率。",
    )


_CONTROLS = {
    "seed_lot", "temperature_c", "duration_h", "seeds_per_dish",
    "illumination", "solution_ml",
}


def _germination_group(group):
    _require(isinstance(group, dict), "每组需给出处理、控制条件和重复数据")
    controls = group.get("controls")
    _require(isinstance(controls, dict) and set(controls) == _CONTROLS, "实验控制条件不完整")
    for key in ("seed_lot", "illumination"):
        _require(isinstance(controls[key], str) and controls[key].strip(), f"{key} 未明确")
    _require(_number(controls["duration_h"], "处理时长") > 0, "处理时长须为正")
    _require(_number(controls["solution_ml"], "溶液体积") > 0, "溶液体积须为正")
    _number(controls["temperature_c"], "温度")
    seeds = controls["seeds_per_dish"]
    _require(type(seeds) is int and seeds > 0, "每皿种子数须为正整数")
    repeats = group.get("germinated_per_dish")
    _require(
        isinstance(repeats, list) and len(repeats) >= 3
        and all(type(n) is int and 0 <= n <= seeds for n in repeats),
        "每组至少三皿，且每皿萌发数须介于零与初始种子数之间",
    )
    salt = _number(group.get("nacl_g_per_l"), "NaCl 浓度")
    _require(salt >= 0, "浓度不可为负")
    return controls, salt, len(repeats), Fraction(sum(repeats), len(repeats) * seeds)


def _experiment(problem):
    _require(problem.get("case") == "salt_germination", "不支持该实验模型")
    _require(
        problem.get("random_allocation") is True and problem.get("independent_dishes") is True,
        "组间随机分配和培养皿独立重复须明确",
    )
    groups = problem.get("groups")
    _require(isinstance(groups, dict) and set(groups) == {"control", "treatment"}, "须有对照与处理两组")
    c_controls, c_salt, c_repeats, control = _germination_group(groups["control"])
    t_controls, t_salt, t_repeats, treatment = _germination_group(groups["treatment"])
    _require(c_controls == t_controls and c_repeats == t_repeats, "无关变量及重复数须一致")
    _require(c_salt == 0 and t_salt > 0, "该题型要求零盐对照和正浓度处理")
    direction = "较低" if treatment < control else "较高" if treatment > control else "相同"
    answer = {
        "对照萌发率": str(control),
        "处理萌发率": str(treatment),
        "差值（处理－对照，百分点）": str(100 * (treatment - control)),
        "自变量": "NaCl 浓度",
        "能否单独证明 Na⁺ 毒害": "不能",
        "证据边界": "只支持题设条件下的观测差异",
    }
    return _result(
        answer,
        ["逐皿数据合法且含独立重复", "对照组只改变 NaCl 浓度", "按总萌发数和总播种数核算比例"],
        f"各组将萌发数相加，除以该组播种总数。处理组观测萌发率{direction}。"
        "随机分配和同等培养条件支持比较这次盐处理的效应。"
        "这组数据不能判定是渗透效应还是离子效应，也不能推出任意浓度、品种或处理时间下的规律。",
    )


def _osmosis(problem):
    _require(problem.get("case") == "initial_osmosis", "不支持该概念模型")
    _require(
        all(problem.get(key) is True for key in ("living_cells", "sucrose_impermeant", "initial_only")),
        "须明确活细胞、蔗糖在该时间内不可透及只讨论初始阶段",
    )
    cell = _number(problem.get("cell_psi_mpa"), "细胞水势")
    x = _number(problem.get("x_psi_mpa"), "X 溶液水势")
    y = _number(problem.get("y_psi_mpa"), "Y 溶液水势")
    truths = {
        "x_out_y_in": x < cell < y,
        "x_in_y_out": y < cell < x,
        "both_out": max(x, y) < cell,
        "both_in": min(x, y) > cell,
    }
    choices = problem.get("option_models")
    _require(
        isinstance(choices, dict) and set(choices) == set("ABCD")
        and all(isinstance(v, str) for v in choices.values()) and set(choices.values()) == set(truths),
        "选择题须含四个不同的允许水流模型",
    )
    correct = [letter for letter, model in choices.items() if truths[model]]
    _require(len(correct) == 1, "给定水势不能唯一支持四个初始水流选项之一")
    return _result(
        correct[0],
        ["核对初始水势次序", "逐项比较跨膜净水流", "四选项唯一真值"],
        "题设规定水的净移动方向由高水势一侧指向低水势一侧。分别比较细胞与 X、Y 溶液的"
        "初始水势即可判定。这一步没有推出最终水分平衡状态或是否发生质壁分离。",
    )


def verify(problem):
    """Verify one supported structured biology problem and explain its scope."""
    _require(isinstance(problem, dict), "生物题条件须为对象")
    operation = problem.get("op")
    solvers = {
        "mendelian_cross": _mendelian,
        "single_factor_experiment": _experiment,
        "concept_inference": _osmosis,
    }
    _require(isinstance(operation, str) and operation in solvers, "不支持的生物验证操作")
    return solvers[operation](problem)
