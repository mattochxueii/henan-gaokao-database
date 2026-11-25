"""Allocation and rounding rules for a 100-point Henan standard simulation."""
import ast
from collections import Counter
from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext
import re

from core.editorial_rules import item_text
from gaokao import require

LIMITS = {"mechanics": (35, 46), "electromagnetism": (38, 50), "other": (12, 20)}
GROUP_LABELS = {"mechanics": "力学（含天体）", "electromagnetism": "电磁学", "other": "光、热、波及近代物理"}
MODULE = {
    "mechanics": ("mechanics", r"运动|加速度|速度|动量|动能|机械能|受力|摩擦|惯性|机械功|力学|力传感器"),
    "astronomy": ("mechanics", r"卫星|天体|行星|探测器.{0,15}轨道|万有引力|引力常量|双星|宇宙速度"),
    "electrostatics_circuits": ("electromagnetism", r"电路|电场|电势|电阻|电容|电荷|电流表|欧姆|伏安"),
    "magnetic_force": ("electromagnetism", r"洛伦兹|磁场|安培力|磁感应强度|磁偏转"),
    "induction_ac": ("electromagnetism", r"变压器|交变电流|交流电|感应电(?:动势|流|压)|磁通量|电磁感应|涡流|楞次"),
    "thermodynamics": ("other", r"气缸|理想气体|温度|热力学|内能|热量|蒸发|分子热运动"),
    "optics_waves": ("other", r"波长|光路|偏振光|透镜|折射|全反射|干涉|衍射|机械波|驻波|波速"),
    "atomic": ("other", r"光电效应|普朗克|逸出功|光电子|能级|原子核|原子光谱|遏止电压|跃迁|衰变|核反应"),
}
THERMAL_MAX = 12
CALCULATIONS = (13, 14, 15)
POINTS = (4,)*7 + (6,)*3 + (6, 9, 10, 12, 17)
ROLE_SLOTS = {"experiment_1": (11, "mechanics"), "experiment_2": (12, "electromagnetism"),
              "mechanics_calculation": (14, "mechanics"), "final": (15, "electromagnetism")}
SLOT_EXAMPLE = ("other", "other", "mechanics", "other", "mechanics", "electromagnetism",
                "electromagnetism", "mechanics", "electromagnetism", "other",
                "mechanics", "electromagnetism", "mechanics", "mechanics", "electromagnetism")


def allocation(questions):
    totals = dict.fromkeys(LIMITS, 0)
    modules = Counter()
    issues = []
    main_topics = {}
    if tuple(q.get("points") for q in questions) != POINTS:
        issues.append((0, "physics_weight", "河南物理标准卷的十五个题位分值与走廊蓝图不符"))
    for number, question in enumerate(questions, 1):
        module = question.get("physics_module")
        points = question.get("points")
        if not isinstance(module, str) or module not in MODULE or type(points) is not int or points <= 0:
            issues.append((number, "physics_weight", "须按实际主考内容声明一个有分值的 physics_module"))
            continue
        group, pattern = MODULE[module]
        if not re.search(pattern, item_text(question)):
            issues.append((number, "physics_weight", f"题干和子问未检出模块 {module} 的实质标志"))
            continue
        totals[group] += points
        modules[module] += points
        main_topics[str(number)] = group
    for group, (low, high) in LIMITS.items():
        if not low <= totals[group] <= high:
            issues.append((0, "physics_weight", f"{GROUP_LABELS[group]}实际 {totals[group]} 分，要求 {low}–{high} 分"))
    if modules["thermodynamics"] > THERMAL_MAX:
        issues.append((0, "physics_weight", f"热学 {modules['thermodynamics']} 分，最多 {THERMAL_MAX} 分"))
    if not any(main_topics.get(str(n)) == "electromagnetism" for n in CALCULATIONS):
        issues.append((0, "physics_calculation", "第 13–15 题缺电磁学计算大题"))
    if not any(main_topics.get(str(n)) == "mechanics" and len(questions[n-1].get("parts", [])) >= 2
               for n in CALCULATIONS):
        issues.append((0, "physics_calculation", "第 13–15 题缺至少两问的力学综合计算题"))
    return {"groups": totals, "modules": dict(modules), "question_groups": main_topics}, issues


PRECISION = re.compile(r"(?:保留|精确到|取)\s*([一二两三四五六七八九1-9])\s*位\s*(有效数字|小数)")
PRECISION_DIGIT = dict(zip("一二两三四五六七八九", (1, 2, 2, 3, 4, 5, 6, 7, 8, 9), strict=True))
PI = re.compile(r"π|\\pi\b|圆周率|圆周长")
BLANK = re.compile(r"([①-⑳])?_{3,}")
PENDULUM_SLOPE = re.compile(r"斜率(?:取|为|=)\s*(\d+(?:\.\d+)?)")
NUMBER = re.compile(r"(?<![A-Za-z0-9.])[-−+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def evaluate(formula, pi):
    """Use a small arithmetic grammar and decimal literals for reproducible rounding."""
    require(isinstance(formula, str) and len(formula) <= 160, "π 表达式过长或缺失")
    tree = ast.parse(formula, mode="eval")
    require(len(list(ast.walk(tree))) <= 60, "π 表达式过于复杂")
    uses_pi = any(isinstance(node, ast.Name) and node.id == "pi" for node in ast.walk(tree))
    require(uses_pi, "表达式未使用 pi")

    def value(node):
        if isinstance(node, ast.Name) and node.id == "pi":
            return pi
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Decimal(ast.get_source_segment(formula, node))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -value(node.operand) if isinstance(node.op, ast.USub) else value(node.operand)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sqrt":
            require(len(node.args) == 1 and not node.keywords, "sqrt 只接受一个参数")
            return value(node.args[0]).sqrt()
        if isinstance(node, ast.BinOp):
            first, second = value(node.left), value(node.right)
            if isinstance(node.op, ast.Add):
                return first + second
            if isinstance(node.op, ast.Sub):
                return first - second
            if isinstance(node.op, ast.Mult):
                return first * second
            if isinstance(node.op, ast.Div):
                return first / second
            if isinstance(node.op, ast.Pow):
                require(second == second.to_integral() and -12 <= second <= 12, "指数须为小整数")
                return first ** int(second)
        raise ValueError("仅接受数字、pi、四则、整数幂和 sqrt")

    return value(tree.body)


def rounded(formula, digits, significant):
    values = []
    with localcontext() as ctx:
        ctx.prec = 42
        for pi in ("3.14", "3.1416"):
            raw = evaluate(formula, Decimal(pi))
            require(raw.is_finite() and abs(raw.adjusted()) <= 18, "复算值超出量程")
            scale = raw.adjusted() - digits + 1 if significant and raw else -digits
            values.append(raw.quantize(Decimal(1).scaleb(scale), rounding=ROUND_HALF_UP))
    return values


def numeric_answer(answer, key, offset):
    value = answer.get(key) if isinstance(answer, dict) else answer
    if type(value) in (int, float):
        return Decimal(str(value)) if not offset else None
    if isinstance(value, str):
        value = re.split(r"[；;]",value)
    if isinstance(value,list) and len(value) > offset and type(value[offset]) in (str,int,float):
        hits = NUMBER.findall(str(value[offset]))
        if len(hits) == 1:
            return Decimal(hits[0].replace("−","-"))
    return None


def pi_findings(question, answer=None):
    records = question.get("pi_checks", [])
    if not isinstance(records,list):
        yield "pi_checks 须按空位记录"
        return
    specs = {}
    for row in records:
        blank = row.get("blank") if isinstance(row,dict) else None
        if not isinstance(blank,str) or not re.fullmatch(r"[①-⑳]",blank) or blank in specs:
            yield "π 复算记录须有不同的空位圈号"
            return
        specs[row["blank"]] = row.get("expression")
    intro = question["stem"]
    counter = 0
    parts = [(None,intro), *((part.get("label"),part["text"]) for part in question.get("parts", []))]
    pendulum = re.search(r"单摆|摆球|小角度自由摆动",intro)
    slope = PENDULUM_SLOPE.search(intro) if pendulum else None
    for key, text in parts:
        matches = list(BLANK.finditer(text))
        for i, match in enumerate(matches):
            number = match[1] or chr(ord("①") + counter)
            counter += 1
            end = matches[i+1].start() if i+1 < len(matches) else len(text)
            before = text[matches[i-1].end() if i else 0:match.start()]
            after = text[match.end():end]
            precision = PRECISION.search(after) or (PRECISION.search(text) if len(matches)==1 else None) or PRECISION.search(intro)
            based_on_pendulum = slope and "重力加速度" in before
            if number not in specs and not (precision and (PI.search(text) or PI.search(intro) or based_on_pendulum)):
                continue
            if based_on_pendulum and number not in specs:
                specs[number] = f"4*pi**2/{slope[1]}"
            if not precision or number not in specs:
                yield f"空位 {number} 缺题面精度或绑定的 π 复算表达式"
                continue
            formula = specs.pop(number)
            digit = PRECISION_DIGIT.get(precision[1], precision[1])
            try:
                a, b = rounded(formula, int(digit), precision[2] == "有效数字")
                if based_on_pendulum and [a,b] != rounded(f"4*pi**2/{slope[1]}", int(digit), precision[2] == "有效数字"):
                    yield f"空位 {number} 的复算表达式与单摆题面斜率不符"
                elif a != b:
                    yield f"空位 {number} 用 3.14 与 3.1416 分别得 {a} 和 {b}，进位不一致"
                elif answer is not None and numeric_answer(answer,key,i) != a:
                    yield f"空位 {number} 的候选数值答案与复算结果 {a} 不符"
            except (SyntaxError, ValueError, DecimalException):
                yield f"空位 {number} 的 π 复算表达式无效"
    for number in specs:
        yield f"π 复算记录 {number} 未绑定到印出的空位"
