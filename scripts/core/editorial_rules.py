"""Content checks for the current standard-paper edition and its PDF review."""
from math import isfinite
import re

REVISION = "gaokao-edition-rules-v1"
LAYOUT_MODES = ("practice", "exam")
PHYSICS = {
    "力学": r"加速度|动量|机械能|向心|受力|弹簧|摩擦",
    "天体与引力": r"卫星|万有引力",
    "静电与电路": r"电势|电容|静电|电阻",
    "磁场与洛伦兹力": r"带电粒子.{0,70}磁场|电荷量.{0,65}正粒子|洛伦兹力",
    "电磁感应与交变": r"感应电流|变压器|交变电流",
    "热学": r"理想气体|热力学",
    "光学与机械波": r"机械波|驻波|折射|光的干涉|光路",
    "原子物理": r"光电效应|遏止电压|原子能级|原子核",
}
DEVICES = {
    "弹簧": r"弹簧|弹性簧片",
    "气缸活塞": r"气缸|活塞",
    "光电门": r"光电门",
    "平行板电容器": r"平行板电容器",
    "变压器": r"变压器",
    "导轨线框": r"导轨.{0,35}线框|线框.{0,35}导轨",
}
EXP_LOG = r"e\s*\^|\\(?:e?exp|ln|log)(?![A-Za-z])|指数函数|对数函数"
MATH_NOTATION = re.compile(
    r"\\setminus\b|\\smallsetminus\b|\b[A-Z]\s*\^\s*(?:\{\s*[cC]\s*\}|[cC](?![A-Za-z]))"
)
GLYPHS = {"−": "-", "＝": "=", "＋": "+", "．": ".", "²": "^2", "³": "^3", "×": "x"}


def item_text(question, *, options=False):
    stem = [question["stem"], *(p["text"] for p in question.get("parts", []))]
    if options:
        choices = question.get("options") or {}
        stem.extend(choices.values() if isinstance(choices, dict) else choices)
    return " ".join(stem)


def normal(text):
    return "".join(text.translate(str.maketrans(GLYPHS)).split()).casefold()


def notation_issues(text):
    return "数学补集用 \\complement_U，事件对立用 \\overline{}" if MATH_NOTATION.search(text) else None


def _positions(paper):
    return [(n, q, item_text(q)) for n, q in enumerate(paper["questions"], 1)]


def coverage(subject, paper):
    rows = _positions(paper)
    hits = {}
    duplicates = {}
    if subject == "physics":
        hits = {label: [n for n, _, text in rows if re.search(pattern, text)]
                for label, pattern in PHYSICS.items()}
        duplicates = {label: ns for label, pattern in DEVICES.items()
                      if len(ns := [n for n, _, text in rows if re.search(pattern, text)]) > 2}
    elif subject == "math":
        hits = {
            "指数或对数函数": [n for n, q, t in rows if re.search(EXP_LOG, item_text(q, options=True))],
            "常规导数工具": [n for n, _, t in rows if re.search(r"导数|切线斜率|曲线.{0,55}切线|\(f'\(", t)],
            "立体几何选填": [n for n, q, t in rows if q.get("kind") != "constructed_response"
                        and q.get("module") == "立体几何" and re.search(r"棱柱|棱锥|二面角|球|正方体|平行|垂直", t)],
            "平均数之外的统计量": [n for n, q, t in rows if q.get("module") == "统计与概率"
                           and re.search(r"方差|标准差|中位数|频率|分位数|列联表|相关系数", t)],
        }
    elif subject == "chemistry":
        experimental = [(n, text) for n, q, text in rows if q.get("kind") == "constructed_response"
                        and re.search(r"样品|样液|清洗液|同批", text) and re.search(r"滴定|吸光度|测定", text)]
        patterns = {
            "仪器": r"滴定管|量筒|玻璃仪器|烧杯|容量瓶",
            "分离操作": r"过滤|分液|萃取|离心",
            "现象": r"颜色|变色|终点现象|沉淀现象|气泡",
            "定量及误差": r"(?:偏高|偏低|误差|校正)",
        }
        hits = {
            "STSE前段": [n for n, _, t in rows[:5] if re.search(r"回收|储氢|脱硫|废水|尾气|清洁能源|工业", t)],
            "实验装置辨析": [n for n, q, t in rows[:5] if q.get("figure")
                         and re.search(r"滴定管|尖嘴|分液漏斗|装置", t)],
            "综合实验": [n for n, t in experimental if all(re.search(v, t) for v in patterns.values())],
        }
    missing = [label for label, ns in hits.items() if not ns]
    return {"coverage": hits, "missing": missing, "overused_devices": duplicates}


def paper_issues(subject, paper):
    if paper.get("edition_rules") != REVISION or not paper.get("standard"):
        return []
    result = coverage(subject, paper)
    missing = result["missing"]
    problems = []
    if len(missing) >= (3 if subject == "physics" else 1):
        problems.append("整卷主干板块缺失：" + "、".join(missing))
    for device, numbers in result["overused_devices"].items():
        problems.append(f"器具 {device} 超过两题，第" + "、".join(map(str, numbers)) + "题")
    if subject == "biology":
        count = sum(q["kind"] == "single_choice" and bool(q.get("figure")) for q in paper["questions"])
        if count < 5:
            problems.append("生物学标准卷须至少五道选择题使用参与推理的图")
    return problems


def figure_issues(question, row):
    figure = question.get("figure") or question.get("archive_figures") or question.get("figures")
    stem = item_text(question)
    if not figure:
        return ["题干引用图示条件而题图缺失"] if re.search(r"如图|图示|图中|见图", stem) else []
    evidence = row.get("figure_conditions")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("records"), list) or not evidence.get("observation"):
        return ["缺图文条件和终稿图件观察记录"]
    records = evidence["records"]
    if not records:
        if not evidence.get("qualitative_only") or re.search(
                r"(?:数值|棱长|间距|坐标|长度|方程|读数|位置).{0,6}(?:如图|图示|见图)|(?:如图|图示|见图).{0,6}(?:棱长|方程|标出的长度)", stem):
            return ["图中关键数值、方程或部件未逐项双明示"]
        return []
    issues = []
    for item in records:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ("anchor", "label", "meaning")):
            issues.append("图文记录须提供文字锚点、实际图标及物理或数学含义")
        elif normal(item["anchor"]) not in normal(stem):
            issues.append("图中条件未在考生正文独立明示：" + item["anchor"])
        elif isinstance(figure, dict) and figure.get("type") in {"wireframe","coordinate"}:
            found = {normal(m["math"]) for m in figure.get("labels", [])}
            if caption := figure.get("caption_math"):
                found.add(normal(caption))
            if normal(item["label"]) not in found:
                issues.append("制图说明中的关键标注与实际图件不符：" + item["label"])
    return issues


def _finite(value, low, high):
    return type(value) in (int, float) and isfinite(value) and low <= value <= high


def _carbonate_matches(balance):
    if not isinstance(balance, dict):
        return False
    values = tuple(balance.get(key) for key in (
        "bicarbonate", "neutralized", "carbonate_solid", "carbonate_liquid",
        "magnesium_solid", "hydroxide_total",
    ))
    if not all(_finite(value, 0, float("inf")) for value in values):
        return False
    bicarbonate, neutralized, solid, liquid, magnesium, hydroxide = values
    return (bicarbonate > 0 and magnesium > 0 and neutralized == bicarbonate
            and solid + liquid == neutralized and hydroxide == neutralized + 2 * magnesium)


def _pilot_matches(pilot):
    if not isinstance(pilot, dict) or not isinstance(pilot.get("samples"), list):
        return False
    ph = pilot.get("selected_pH")
    second = pilot.get("secondary_pH")
    al_limit = pilot.get("max_al")
    mg_limit = pilot.get("min_mg")
    if not all((_finite(ph, 0, 14), _finite(second, 0, 14),
                _finite(al_limit, 0, 100), _finite(mg_limit, 0, 100))):
        return False
    rows = {}
    for row in pilot["samples"]:
        if not isinstance(row, list) or len(row) != 3:
            return False
        measured, al, mg = row
        if not all((_finite(measured, 0, 14), _finite(al, 0, 100), _finite(mg, 0, 100))) or measured in rows:
            return False
        rows[measured] = (al, mg)
    feasible = [measured for measured, (al, mg) in rows.items() if al <= al_limit and mg >= mg_limit]
    return bool(feasible and min(feasible) == ph and second in rows and second > ph
                and rows[second][0] > rows[ph][0] and rows[second][1] < rows[ph][1])


def solution_competition(question, row):
    text = item_text(question, options=True)
    if re.search(r"忽略.{0,18}(?:两性|羟基配合)", text):
        return "真实溶液体系不能跳过两性重溶或羟基配合平衡"
    if not re.search(r"除铝|除镁|硬水|选择性沉淀|pCl|K_\{?\\?(?:mathrm\{)?sp", text):
        return None
    proof = row.get("aqueous_competition")
    if not isinstance(proof, dict) or not all(isinstance(proof.get(k), str) and proof[k].strip()
               for k in ("pH_scope", "order", "competing_path", "quantity_check")):
        return "缺目标 pH、竞争顺序、竞争反应及定量核对"
    if "HCO_3" in text and "Mg(OH)" in text:
        if not (all(term in proof["competing_path"] for term in ("HCO", "CO", "OH"))
                and _carbonate_matches(proof.get("carbonate_balance"))):
            return "强碱体系须核对 HCO₃⁻ 全部去质子化、碳酸根分配和沉镁的 OH⁻ 用量"
    if "除铝" in text:
        if "重溶" not in proof["competing_path"] and "Al(OH)4" not in proof["competing_path"]:
            return "分段除铝须核对高 pH 的两性重溶"
        if "溶解态" in text and not _pilot_matches(proof.get("hydroxide_pilot")):
            return "分段除铝除镁须用同一组实测型数据核对首段阈值与后段铝回溶、镁析出"
    return None
