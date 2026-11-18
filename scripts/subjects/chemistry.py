"""Exact classroom chemistry calculations with an explicit reaction evidence boundary."""

from fractions import Fraction
from math import gcd, lcm, log10
import re

from sympy import Matrix

from subjects.chemistry_models import SOLVERS as ADDITIONAL_SOLVERS


SOURCES = {
    "oxalate": "https://demolab.chem.wisc.edu/titrations-the-reaction-between-oxalate-ion-with-permanganate/",
    "strong_titration": "https://openstax.org/books/chemistry-2e/pages/14-7-acid-base-titrations",
    "limewater": "https://www.chem.indiana.edu/faculty-research/faculty-resources/chemistry-demos/demo/limewater-as-indicator-of-carbon-dioxide-gas/",
    "carbonate": "https://teachersinstitute.yale.edu/curriculum/units/2000/6/00.06.04/3",
}

# Only registered species/conditions qualify for this prototype. The notation
# uses an explicit charge marker so Fe^2+ cannot be mistaken for an atom count.
SPECIES = {
    "MnO4^-", "C2O4^2-", "H^+", "Mn^2+", "CO2", "H2O",
    "H2PO4^-", "H3PO4", "OH^-", "Ag2O", "Cl^-", "AgCl", "Ag^+",
    "ClO^-", "I^-", "I2", "HClO", "SO4^2-", "Ba^2+", "HCO3^-", "BaSO4",
    "Ca^2+", "CaCO3",
}

# Keys describe reactants and conditions rather than a candidate answer. The
# coefficients themselves are independently solved from atom and charge rows.
REACTIONS = {
    "warm_dilute_sulfuric_acid_oxalate": (
        ("MnO4^-", "C2O4^2-", "H^+"), ("Mn^2+", "CO2", "H2O"),
    ),
    "dihydrogen_phosphate_base_hydrolysis": (
        ("H2PO4^-", "H2O"), ("H3PO4", "OH^-"),
    ),
    "silver_oxide_dilute_hcl": (
        ("Ag2O", "H^+", "Cl^-"), ("AgCl", "H2O"),
    ),
    "hypochlorite_hydroiodic_acid": (
        ("ClO^-", "I^-", "H^+"), ("I2", "Cl^-", "H2O"),
    ),
    "excess_hydrogen_sulfate_limited_barium_bicarbonate": (
        ("H^+", "SO4^2-", "Ba^2+", "HCO3^-"), ("BaSO4", "CO2", "H2O"),
    ),
    "aqueous_strong_acid_base": (
        ("H^+", "OH^-"), ("H2O",),
    ),
    "bicarbonate_with_acid": (
        ("HCO3^-", "H^+"), ("CO2", "H2O"),
    ),
    "limited_co2_in_clear_limewater": (
        ("Ca^2+", "OH^-", "CO2"), ("CaCO3", "H2O"),
    ),
}

# Oxidation-state differences give an independently testable electron count.
REDOX = {
    "warm_dilute_sulfuric_acid_oxalate": ("C2O4^2-", 2, "MnO4^-", 5),
    "hypochlorite_hydroiodic_acid": ("I^-", 1, "ClO^-", 2),
}

PHENOMENA = {
    "water_vapour_deposition": ("physical", "水的物态变化，物质仍为水。"),
    "tyndall_scattering": ("physical", "胶体粒子散射光，不涉及形成新物质。"),
    "dry_ice_fog": ("physical", "干冰升华使周围气体降温，水汽凝成液滴。"),
    "flower_peroxide_bleaching": ("chemical", "题述花色在双氧水中变化符合色素氧化的情境。"),
}

CONDITION_REASONS = {
    "dihydrogen_phosphate_base_hydrolysis": "H₂PO₄⁻接受水提供的质子，形成H₃PO₄和OH⁻。这一步水解并不说明溶液整体呈碱性。",
    "silver_oxide_dilute_hcl": "盐酸中的Cl⁻使银形成AgCl沉淀，不能将Ag⁺保留为最终产物。",
    "hypochlorite_hydroiodic_acid": "HI提供H⁺和I⁻，ClO⁻会将I⁻氧化成I₂，不能只写质子化。",
    "excess_hydrogen_sulfate_limited_barium_bicarbonate": "少量Ba(HCO₃)₂在酸过量条件下，每1份Ba²⁺伴随2份HCO₃⁻，两份HCO₃⁻均生成CO₂。",
}


def _species(value):
    if not isinstance(value, str) or value not in SPECIES:
        raise ValueError(f"化学式或离子未在已核证范围内：{value!r}")
    formula, _, ion = value.partition("^")
    atoms = {name: int(count or 1) for name, count in re.findall(r"([A-Z][a-z]?)(\d*)", formula)}
    charge = int(ion[:-1] or 1) * (1 if ion[-1] == "+" else -1) if ion else 0
    return atoms, charge


def _sides(problem):
    left, right = problem["reactants"], problem["products"]
    if not all(isinstance(x, list) and 0 < len(x) <= 8 for x in (left, right)):
        raise ValueError("反应物和生成物须为非空化学式列表")
    for value in left + right:
        _species(value)
    if len(set(left + right)) != len(left + right):
        raise ValueError("同种粒子不能重复输入或同时出现在净离子式两侧")
    return left, right


def _rows(left, right):
    parsed = [_species(value) for value in left + right]
    elements = sorted(set().union(*(atoms for atoms, _ in parsed)))
    signs = [1] * len(left) + [-1] * len(right)
    return [
        [sign * atoms.get(element, 0) for sign, (atoms, _) in zip(signs, parsed)]
        for element in elements
    ] + [[sign * charge for sign, (_, charge) in zip(signs, parsed)]]


def _primitive(left, right, medium=None):
    constraints = _rows(left, right)
    if medium == "excess_hydrogen_sulfate_limited_barium_bicarbonate":
        # The precipitation and acid reactions alone have two free extents.
        # One limiting Ba(HCO3)2 supplies both bicarbonates for each Ba ion.
        relation = {"Ba^2+": -2, "HCO3^-": 1}
        constraints.append([relation.get(species, 0) for species in left + right])
    basis = Matrix(constraints).nullspace()
    if len(basis) != 1:
        raise ValueError("无法从原子数及总电荷得到唯一的系数比例")
    values = basis[0]
    denominator = lcm(*(int(value.q) for value in values))
    numbers = [int(value * denominator) for value in values]
    if numbers[0] < 0:
        numbers = [-value for value in numbers]
    if min(numbers) <= 0:
        raise ValueError("配平方程要求所有输入粒子的系数为正")
    factor = gcd(*numbers)
    return [value // factor for value in numbers]


def _reaction(problem):
    medium = problem["medium"]
    if medium not in REACTIONS:
        raise ValueError("此反应条件未纳入核证模型")
    left, right = _sides(problem)
    known_left, known_right = REACTIONS[medium]
    if set(left) != set(known_left) or set(right) != set(known_right):
        raise ValueError("粒子与已核证的反应条件不一致")
    coefficients = _primitive(left, right, medium)
    answer = {"reactant_coefficients": coefficients[:len(left)], "product_coefficients": coefficients[len(left):]}
    checks = ["按元素列原子守恒方程", "总电荷守恒", "正整数最简系数比例唯一", "反应物与生成物符合指定模型条件"]
    if medium in REDOX:
        donor, lost, acceptor, gained = REDOX[medium]
        amounts = dict(zip(left, answer["reactant_coefficients"]))
        loss, gain = amounts[donor] * lost, amounts[acceptor] * gained
        if loss != gain:
            raise ValueError("独立氧化数核算不满足电子守恒")
        answer["electrons_transferred"] = loss
        checks.append("按氧化数变化分别核算失、得电子")
    return answer, checks


def _result(answer, checks, unverified, explanation, sources=()):
    return {
        "answer": answer, "checks": checks, "unverified": unverified,
        "explanation": explanation, "science_sources": list(sources),
    }


def _ionic_balance(problem):
    answer, checks = _reaction(problem)
    medium = problem["medium"]
    if medium == "warm_dilute_sulfuric_acid_oxalate":
        explanation = (
            "草酸根中每个碳的氧化数由＋3升至＋4，每个草酸根失2个电子。"
            "高锰酸根中锰由＋7降至＋2，每个高锰酸根得5个电子。"
            "以2个高锰酸根对应5个草酸根，电子转移数为10。"
            "碳、锰守恒给10个CO₂和2个Mn²⁺，再由氧、氢和电荷守恒得16个H⁺及8个H₂O。"
            "消耗2 mol MnO₄⁻时，对应转移10 mol电子。"
        )
        return _result(answer, checks, ["反应动力学及实测转化率不在程序验证范围"], explanation, [SOURCES["oxalate"]])
    return _result(answer, checks, ["实际平衡组成及反应速率未由配平确定"],
                   "按输入顺序给出两侧最简正整数系数。反应条件、原子和电荷均已逐项核对。")


def _ionic_choice(problem):
    choices = problem["choices"]
    if not isinstance(choices, dict) or set(choices) != set("ABCD"):
        raise ValueError("离子反应辨析须给出 A 至 D 四个选项")
    passed = []
    checks = []
    reasons = []
    for label, row in sorted(choices.items()):
        left, right = _sides(row)
        coeff = row["coefficients"]
        if not isinstance(coeff, list) or len(coeff) != len(left + right) or any(
            type(v) is not int or v <= 0 for v in coeff
        ):
            raise ValueError("候选离子方程式须给出完整的正整数系数")
        balanced = all(sum(c * v for c, v in zip(coeff, equation)) == 0 for equation in _rows(left, right))
        medium = row["medium"]
        if medium not in CONDITION_REASONS:
            raise ValueError("离子方程式选项条件未核证")
        lr, rr = REACTIONS[medium]
        feasible = set(left) == set(lr) and set(right) == set(rr)
        if feasible:
            correct = _primitive(left, right, medium)
            g = gcd(*coeff)
            feasible = [value // g for value in coeff] == correct
        checks.append(f"{label} 原子和电荷{'守恒' if balanced else '不守恒'}，指定条件{'吻合' if feasible else '不吻合'}")
        reasons.append(label + "项：" + CONDITION_REASONS[medium])
        if balanced and feasible:
            passed.append(label)
    if len(passed) != 1:
        raise ValueError("所给条件未产生唯一正确选项")
    return _result(passed[0], checks, ["仅核对规定的主要净反应，不判定微量组分"], " ".join(reasons))


def _phenomenon_choice(problem):
    options = problem["events"]
    if not isinstance(options, dict) or set(options) != set("ABCD") or any(
        key not in PHENOMENA for key in options.values()
    ):
        raise ValueError("需要四个已核证的现象选项")
    selection = [label for label, key in options.items() if PHENOMENA[key][0] == "chemical"]
    if len(selection) != 1:
        raise ValueError("所给现象未产生唯一化学变化选项")
    return _result(selection[0], ["检验是否生成新物质", "区分相变、散射和化学变化"],
                   ["没有从题述现象推断特定色素的结构或机理"],
                   " ".join(f"{label}项：{PHENOMENA[key][1]}" for label, key in sorted(options.items())))


def _positive_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("体积、浓度必须为有效正数")
    number = Fraction(str(value))
    if number <= 0:
        raise ValueError("体积、浓度必须为正")
    return number


def _neutralization_mix(problem):
    if (
        problem["acid"] != "HCl" or problem["base"] != "NaOH"
        or problem["temperature_c"] != 25 or problem["additive_volumes"] is not True
    ):
        raise ValueError("原型只核证25 ℃体积可加的稀盐酸和NaOH溶液")
    va, ca, vb, cb = (_positive_number(problem[key]) for key in (
        "acid_ml", "acid_mol_l", "base_ml", "base_mol_l"
    ))
    if max(ca, cb) > Fraction(1, 5):
        raise ValueError("超出原型稀溶液近似浓度上限")
    acid, base = va * ca / 1000, vb * cb / 1000
    excess = (base - acid) / ((va + vb) / 1000)
    if excess and abs(excess) < Fraction(1, 10**5):
        raise ValueError("过量浓度过小，须采用包含水自解离的完整模型")
    if not excess:
        ion, ph, display = "无", 7.0, "酸碱恰好等物质的量。"
    elif excess > 0:
        ion, ph = "OH⁻", 14 + log10(float(excess))
        display = f"OH⁻过量，浓度为{float(excess):.4g} mol/L。"
    else:
        ion, ph = "H⁺", -log10(float(-excess))
        display = f"H⁺过量，浓度为{float(-excess):.4g} mol/L。"
    return _result(
        {"excess_ion": ion, "excess_mol_l": float(abs(excess)), "pH": round(ph, 2)},
        ["mL换算为L", "根据H⁺与OH⁻的1∶1计量判定过量组分", "使用混合体积", "25 ℃下按稀溶液近似换算pH"],
        ["非理想活度及仪器误差未计入"],
        f"酸、碱物质的量分别为{float(acid):.4g} mol和{float(base):.4g} mol。{display}计算pH约为{ph:.2f}。",
        [SOURCES["strong_titration"]],
    )


def _carbon_dioxide_controls(problem):
    obs, cond = problem["observations"], problem["evidence_conditions"]
    expected_obs = {"sample_cloudy", "blank_cloudy", "positive_cloudy"}
    expected_cond = {"same_apparatus", "equal_reagents_except_sample", "aerosol_excluded",
                     "other_turbidity_causes_excluded", "initial_observation_only"}
    for given, expected in ((obs, expected_obs), (cond, expected_cond)):
        if not isinstance(given, dict) or set(given) != expected or any(type(value) is not bool for value in given.values()):
            raise ValueError("实验模型须逐项登记布尔观察、对照与排除条件")
    if not (all(cond.values()) and obs["sample_cloudy"] and obs["positive_cloudy"] and not obs["blank_cloudy"]):
        raise ValueError("给出的对照或排除条件不足以支持CO₂为检出成分")
    equation, checks = _reaction({
        "medium": "limited_co2_in_clear_limewater", "reactants": ["Ca^2+", "OH^-", "CO2"],
        "products": ["CaCO3", "H2O"],
    })
    return _result(
        {"inference": "支持含有二氧化碳，不能认定气体纯度", **equation},
        checks + ["正对照、空白对照与待测组结果相符", "核对干扰排除条件", "区分检出和纯度判定"],
        ["真实实验中排除干扰的有效性需要独立审阅", "未测定气体纯度和浓度"],
        "阳性对照变浑浊说明检测条件能响应CO₂，空白澄清支持浑浊并非装置或试剂造成。"
        "结合排除干扰的已知条件，待测组浑浊支持气体含CO₂，但不排除共存气体。"
        "少量CO₂通入石灰水时，Ca²⁺＋2OH⁻＋CO₂生成CaCO₃↓＋H₂O。",
        [SOURCES["limewater"], SOURCES["carbonate"]],
    )


def verify(problem):
    """Recompute the answer from structured conditions without reading a supplied key."""
    operations = {
        **ADDITIONAL_SOLVERS,
        "ionic_balance": _ionic_balance,
        "ionic_choice": _ionic_choice,
        "phenomenon_choice": _phenomenon_choice,
        "neutralization_mix": _neutralization_mix,
        "carbon_dioxide_controls": _carbon_dioxide_controls,
    }
    try:
        return operations[problem["op"]](problem)
    except (KeyError, TypeError, ZeroDivisionError, OverflowError) as error:
        raise ValueError("化学题验证参数缺失、类型错误或操作不受支持") from error
