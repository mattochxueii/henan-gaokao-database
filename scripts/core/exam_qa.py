"""Deterministic preflight. Warnings measure wording, not correctness or student difficulty."""
from itertools import combinations
import math
from pathlib import Path
import re

from analysis_db import fingerprint
from gaokao import read_json, require
from core.editorial_rules import coverage, item_text, notation_issues
from core.science_dna import STANDARD_LAYOUT

ABSOLUTE = re.compile(r"只能|一定|所有|必然|永远|从不|(?i:\balways\b|\bnever\b)")
ABSTRACT = re.compile(r"某(?:种)?(?:植物|物质|激素|林地)|(?:物质|激素|溶质)\s*[A-Z]\b")
OPTICS = r"折射|光纤|全反射|光程|干涉条纹|衍射|透镜成像|光路"
CONSTANTS = {"h": 6.62607015e-34, "e": 1.602176634e-19, "c": 299792458,
             "k_B": 1.380649e-23, "N_A": 6.02214076e23}


def policies(root, subject):
    entries = read_json(root / "data/qa/anti-patterns.json")["entries"]
    require(len({r["id"] for r in entries}) == len(entries), "排雷编号重复")
    for r in entries:
        require(r["subject"] in {"all","physics","chemistry","biology","math","english","chinese"}
                and r["severity"] in {"major","fatal"} and r["check"].strip()
                and r["counterexample"].strip(), "排雷条目不完整")
    return [r for r in entries if r["subject"] in (subject,"all")]


def constant_value(obs, text):
    """An inferred constant must cite the measured operands in the printed stem."""
    if obs.get("method") == "stopping_slope":
        pairs=obs["measurements"]
        require(len(pairs)==2, "光电常数须有两组电压与频率")
        for pair in pairs:
            for field in ("frequency","voltage"):
                entry=pair[field]
                require(entry["anchor"] and entry["anchor"] in text and
                        str(entry["reading"]) in entry["anchor"] and
                        entry["scale"] in (1,1e3,1e6,1e9,1e12,1e14,1e15),
                        "常量反推未绑定实际卷面读数或数量级")
        def difference(field):
            return sum(sign*float(p[field]["reading"])*p[field]["scale"] for sign,p in zip((-1,1),pairs))
        df=difference("frequency")
        require(obs["symbol"]=="h" and df!=0,"错误常量或相同光频")
        return CONSTANTS["e"]*difference("voltage")/df
    return obs["value"]


# Only explicit named constants with recognizable SI units or converted km/s enter this check.
# A calibration stated indirectly is handled by constant_value and the solver's independent read.
NAMED_CONSTANT = re.compile(
    r"(?P<name>普朗克常量|元电荷|(?:真空|空气中)?光速)\s*(?:[hce]\s*)?(?:取为|取|约为|为|=|≈)\s*"
    r"(?P<num>\d+(?:\.\d+)?)\s*(?:(?:×|\*|\\times)\s*10\s*\^\s*\{?(?P<power>[-−+]?\d+)\}?)?"
    r"\s*(?P<unit>km/s|m/s|J[·⋅\s]*s|C)(?![A-Za-z])"
)


def printed_constant_errors(text):
    simple=text.replace(r"\(","").replace(r"\)","").replace(r"\,"," ").replace(r"\mathrm{","").replace("} "," ")
    names={"普朗克常量":"h","元电荷":"e"}
    for match in NAMED_CONSTANT.finditer(simple):
        key=names.get(match["name"],"c")
        expected_unit={"h":{"J·s","J⋅s","Js"},"e":{"C"},"c":{"m/s","km/s"}}[key]
        unit=match["unit"].replace(" ","")
        value=float(match["num"])*10**int((match["power"] or "0").replace("−","-"))
        if unit=="km/s":value*=1000
        if unit not in expected_unit or abs(value/CONSTANTS[key]-1)>0.01+1e-12:
            yield f"题面标称 {match[0]} 与约定单位或常量超出1%容差"

def inspect(root, subject, paper, answers, *, header="", observations=(), policy_snapshot=None):
    rows = paper["questions"]
    require(rows and len(rows) == len(answers), "答案和题目须逐项对应")
    issues, warnings, wrong, absolutes, abstract = [], [], 0, 0, 0
    def issue(number, rule, fact):
        issues.append({"number":number, "rule":rule, "evidence":fact})
    result = coverage(subject, paper)
    if subject == "physics":
        result["coverage"]["光学"] = [n for n,q in enumerate(rows,1) if re.search(OPTICS,item_text(q))]
        result["coverage"].pop("光学与机械波",None)
        for n,q in enumerate(rows,1):
            t=item_text(q)
            if re.search(r"原子核|α 衰变|原子能级|能级跃迁|发射光谱",t) and n not in result["coverage"]["原子物理"]:
                result["coverage"]["原子物理"].append(n)
            if re.search(r"洛伦兹|偏转区|离子.{0,30}速度选择器|均匀磁场.{0,28}半周",t) and n not in result["coverage"]["磁场与洛伦兹力"]:
                result["coverage"]["磁场与洛伦兹力"].append(n)
            if re.search(r"每匝磁通量|感应电动势|检测线圈|感应电压",t) and n not in result["coverage"]["电磁感应与交变"]:
                result["coverage"]["电磁感应与交变"].append(n)
            if re.search(r"双星|引力常量",t) and n not in result["coverage"]["天体与引力"]:
                result["coverage"]["天体与引力"].append(n)
    if subject == "chemistry":
        result["coverage"]["物质结构"]=[n for n,q in enumerate(rows,1) if re.search(r"晶胞|配位|杂化|分子构型|电子排布",item_text(q))]
    for name,hits in result["coverage"].items():
        if not hits:
            issue(0,"coverage","未在题干或设问中检出："+name)
    for name,ns in result["overused_devices"].items():
        for n in ns[2:]:
            issue(n,"device",f"{name} 实际出现在题号 {ns}")
    scoped = subject in STANDARD_LAYOUT
    illustrated = []
    for n,(q,answer) in enumerate(zip(rows,answers,strict=True),1):
        stem=item_text(q)
        abstract += len(ABSTRACT.findall(stem))
        if ABSTRACT.search(stem):
            warnings.append({"number":n,"rule":"abstract","evidence":ABSTRACT.findall(stem)})
        if subject=="math" and notation_issues(item_text(q,options=True)):
            issue(n,"notation","补集或对立事件符号偏离约定")
        opts=q.get("options") or {}
        if opts and isinstance(answer,str):
            pairs=opts.items() if isinstance(opts,dict) else zip("ABCDEFG",opts)
            for key,t in pairs:
                if key not in answer:
                    wrong+=1
                    if ABSOLUTE.search(t):
                        absolutes+=1
                        warnings.append({"number":n,"rule":"absolute","option":key,"evidence":t})
        if opts and q.get("figure"):
            illustrated.append(n)
        if scoped and n in STANDARD_LAYOUT[subject]["embedded_blanks"] and not re.search(r"_{3,}",stem):
            issue(n,"missing_blank","指定题位没有嵌入式答位")
    if scoped and len(illustrated)<STANDARD_LAYOUT[subject]["choice_figures_minimum"]:
        issue(0,"figures",f"配图选择题仅 {illustrated}")
    if subject=="math" and re.search(r"(?:选对但不全|部分选对)(?:的)?得\s*3\s*分",header):
        issue(0,"scoring","数学卷出现旧物理计分文案")
    measured={obs["number"] for obs in observations}
    if subject=="physics":
        for n,q in enumerate(rows,1):
            statement=item_text(q)
            if ("遏止电压" in statement and re.search(r"光频|频率",statement)
                    and re.search(r"普朗克|斜率|标定|校准",statement) and n not in measured):
                issue(n,"constant","光电斜率标定缺少可复算的频率、电压读数")
    for obs in observations:
        n=obs["number"]
        require(type(n) is int and 1<=n<=len(rows) and obs["symbol"] in CONSTANTS, "常数记录无效")
        value=constant_value(obs,item_text(rows[n-1]))
        if not math.isfinite(value) or abs(value/CONSTANTS[obs["symbol"]]-1)>0.01+1e-12:
            issue(n,"constant",f"{obs['symbol']}={value}，超过标准值的 1% 容差")
    return {"policy_sha256":fingerprint(policy_snapshot if policy_snapshot is not None else policies(root,subject)),"issues":issues,"warnings":warnings,
            "coverage":result["coverage"],"choice_figures":illustrated,
            "wrong_options":wrong,"absolute_wrong_options":absolutes,"abstract_mentions":abstract,
            "absolute_wrong_fraction":absolutes/wrong if wrong else None,
            "abstract_per_question":abstract/len(rows),"passed":not issues}


def figure_collisions(fig, tolerance_px=1):
    """Return unintended intersections in display coordinates after the final layout."""
    from matplotlib.text import Text
    from matplotlib.transforms import Bbox
    from matplotlib.container import BarContainer
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    legends=[leg for ax in fig.axes if (leg:=ax.get_legend()) is not None and leg.get_visible()]
    legends.extend(leg for leg in fig.legends if leg.get_visible())
    labels=[t for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()
            and (t.axes is None or t.axes.get_visible())]
    # Legend text legitimately lives inside its own box, but can hit other labels.
    boxes=[(t.get_text(), t.get_window_extent(renderer), t) for t in labels]
    findings=[]
    def intersects(a,b):
        box=Bbox.intersection(a,b)
        return box is not None and box.width>tolerance_px and box.height>tolerance_px
    for (one,a,_),(two,b,_) in combinations(boxes,2):
        if intersects(a,b):
            findings.append((one,two))
    for leg in legends:
        members=set(leg.findobj(Text))
        for label,box,t in boxes:
            if t not in members and intersects(box,leg.get_window_extent(renderer)):
                findings.append((label,"Legend"))
    for ax in fig.axes:
        for group in ax.containers:
            if isinstance(group,BarContainer):
                for bar in group.patches:
                    box=bar.get_window_extent(renderer)
                    y=ax.transData.transform((bar.get_x(),bar.get_y()+bar.get_height()))[1]
                    top=Bbox.from_extents(box.x0,y-1.5,box.x1,y+1.5)
                    for label,b,_ in boxes:
                        if intersects(top,b):
                            findings.append((label,"bar end"))
    return findings


def save_figure(fig,path):
    collisions=figure_collisions(fig)
    require(not collisions,"图件文字交叠："+str(collisions))
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=fig.dpi,facecolor="white")
