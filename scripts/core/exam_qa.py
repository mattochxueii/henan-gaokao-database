"""Deterministic preflight. Warnings measure wording, not correctness or student difficulty."""
from itertools import combinations
import json
import math
from pathlib import Path
import re

from analysis_db import fingerprint
from gaokao import digest, read_json, relative_path, require
from core import exam_policy, language_corridor, physics_corridor
from core.editorial_rules import coverage, item_text, notation_issues
from core.science_dna import STANDARD_LAYOUT

ABSOLUTE = re.compile(r"只能|一定|所有|必然|永远|从不|(?i:\balways\b|\bnever\b)")
ABSTRACT = re.compile(r"某(?:种)?(?:植物|物质|激素|林地)|(?:物质|激素|溶质)\s*[A-Z]\b")
OPTICS = r"折射|光纤|全反射|光程|干涉条纹|衍射|透镜成像|光路"
CONSTANTS = {"h": 6.62607015e-34, "e": 1.602176634e-19, "c": 299792458,
             "k_B": 1.380649e-23, "N_A": 6.02214076e23}

# Match prose labels, not unit substrings, chemical formulae or variable letters.
ENGLISH_LABELS = re.compile(
    r"(?<![a-zA-Z])(?:air|liquids?|flux|LDR|water|voltage|current|ground|switch|"
    r"input|output|sensor|source|detector|resistor|capacitor|legend)(?![a-zA-Z])", re.I)
LABEL_KEY = "gaokao.figure_labels"


def label_hits(labels, subject):
    if subject == "english":
        return []
    return sorted({word for label in labels for word in ENGLISH_LABELS.findall(label)})


def required_figure_issues(subject, questions):
    """Count actual nonchoice slots, independently of illustrated choice slots."""
    nonchoice = [n for n,q in enumerate(questions, 1)
                 if q["kind"] not in ("single_choice","multiple_choice") and q.get("figure")]
    issues = []
    rules = STANDARD_LAYOUT.get(subject)
    if rules:
        for n in rules["required_figure_positions"]:
            if n not in nonchoice:
                issues.append((n, "nonchoice_figure", f"第{n}题缺必配非选择题图"))
        if len(nonchoice) < rules["nonchoice_figures_minimum"]:
            issues.append((0, "nonchoice_figure_count",
                           f"非选择配图位置 {nonchoice}，要求至少 {rules['nonchoice_figures_minimum']} 题"))
    elif subject == "math":
        for n,q in enumerate(questions, 1):
            text = item_text(q)
            solid = q.get("module") == "立体几何" or re.search(r"棱锥|棱柱|正方体|长方体|四面体|二面角|异面直线|外接球|两平面夹角",text)
            referenced = re.search(r"如图|图中|图示|见图|读图|所示图像",text)
            figure = q.get("figure")
            if (q.get("figure_required") or solid or referenced) and not figure:
                issues.append((n, "geometry_figure", f"第{n}题的空间关系或图示条件缺少示意图"))
            elif solid and (not isinstance(figure,dict) or figure.get("type")!="wireframe"):
                issues.append((n, "solid_wireframe", "立体几何须用 3D wireframe，不能使用平面坐标图"))
    return nonchoice, issues


def printed_figure_labels(figure, folder):
    """Read the artist strings embedded in the very PNG referenced by the student packet."""
    from PIL import Image
    path = relative_path(folder, figure["path"])
    require(path.is_file() and digest(path) == figure["sha256"], "送审题图缺失或哈希已改变")
    with Image.open(path) as im:
        encoded = im.info.get(LABEL_KEY)
    if encoded is None:
        return None
    labels = json.loads(encoded)
    require(isinstance(labels, list) and all(isinstance(x,str) for x in labels), "图中文字清单损坏")
    return labels


_VERTEX_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉′", "0123456789'")


def wireframe_undefined_vertices(question, figure):
    """Return labeled wireframe vertex names that never appear in question stem or parts."""
    if not isinstance(figure, dict) or figure.get("type") != "wireframe":
        return []
    if not figure.get("show_vertex_labels", True):
        return []
    text = item_text(question)
    cleaned = re.sub(r"\\mathbb\s*(?:\{\s*[A-Z]\s*\}|[A-Z])", " ", text)
    cleaned = re.sub(r"\\[A-Za-z]+", " ", cleaned)
    cleaned = cleaned.translate(_VERTEX_SUB)
    cleaned = re.sub(r"([A-Z])_\{?([0-9]+)\}?", r"\1\2", cleaned)
    cleaned = re.sub(r"([A-Z])\^\{?('+)\}?", r"\1\2", cleaned)
    declared = set(re.findall(r"[A-Z](?![a-z])(?:[0-9]+|'+)?", cleaned))
    missing = []
    for name in figure.get("vertices", {}):
        norm = str(name).translate(_VERTEX_SUB)
        norm = re.sub(r"_\{?([0-9]+)\}?", r"\1", norm)
        norm = re.sub(r"\^\{?('+)\}?", r"\1", norm)
        if norm not in declared:
            missing.append(str(name))
    return missing


def figure_edge_clipping(path, border=2, threshold=35):
    """Scan the outermost 1-2 px edges of a PNG figure for clipped non-background ink."""
    import numpy as np
    from PIL import Image

    with Image.open(path) as im:
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            bg_img = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            rgb = Image.alpha_composite(bg_img, rgba).convert("RGB")
        else:
            rgb = im.convert("RGB")
        arr = np.asarray(rgb, dtype=np.int16)
    h, w, _ = arr.shape
    if h < border * 2 + 2 or w < border * 2 + 2:
        return []
    corners = np.array([arr[0, 0], arr[0, -1], arr[-1, 0], arr[-1, -1]])
    bg = np.median(corners, axis=0)
    if float(bg.mean()) < 200.0:
        bg = np.array([255, 255, 255])
    ink = np.max(np.abs(arr - bg), axis=2) > threshold
    edges = (
        ("top", int(ink[:border, :].sum())),
        ("bottom", int(ink[-border:, :].sum())),
        ("left", int(ink[:, :border].sum())),
        ("right", int(ink[:, -border:].sum())),
    )
    return [side for side, count in edges if count >= 2]


def pdf_page_fill_ratio(pdf_path, page_index=-1):
    """Estimate vertical body coverage ratio (0..1) on a rendered exam PDF page."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    if not reader.pages:
        return 0.0
    page = reader.pages[page_index]
    height = float(page.mediabox.height)
    top_cut = height - 33.0
    bottom_cut = 34.0
    usable = max(top_cut - bottom_cut, 1.0)
    ys = []

    def _visit(text, cm, tm, font, size):
        if text and text.strip():
            y = float(cm[5]) + float(tm[5])
            if y > 28.0:
                ys.append(y)

    page.extract_text(visitor_text=_visit)
    content = page.get_contents()
    if content is not None:
        stack = []
        tx = ty = 0.0
        for operands, op in content.operations:
            if op == b"q":
                stack.append((tx, ty))
            elif op == b"Q" and stack:
                tx, ty = stack.pop()
            elif op == b"cm" and len(operands) == 6:
                tx += float(operands[4])
                ty += float(operands[5])
            elif op == b"Do":
                if ty > 28.0:
                    ys.append(ty)
            elif op in (b"m", b"l") and len(operands) >= 2:
                y = ty + float(operands[1])
                if y > 28.0:
                    ys.append(y)
    if not ys:
        return 0.0
    lowest = max(bottom_cut, min(top_cut, min(ys)))
    return max(0.0, min(1.0, (top_cut - lowest) / usable))


def math_exam_pagination_warnings(pdf_path):
    """Warn when a math exam-mode PDF exceeds 4 pages, especially with a sparse odd-page orphan tail."""
    from pypdf import PdfReader

    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        return []
    pages = len(PdfReader(str(pdf_path)).pages)
    if pages <= 4:
        return []
    fill = pdf_page_fill_ratio(pdf_path, -1)
    if pages % 2 == 1 and fill < 0.35:
        return [(0, "math_exam_pagination",
                 f"数学考场版共 {pages} 页，出现奇数页孤尾（末页内容占比约 {fill:.0%} < 35%），建议收紧版面或图高以压回 4 页")]
    return [(0, "math_exam_pagination",
             f"数学考场版共 {pages} 页，超过常规 4 页篇幅（末页内容占比约 {fill:.0%}），建议复核分页密度")]


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


CHEM_STRUCTURE = {
    "晶体": r"晶胞|晶格|晶体结构",
    "原子": r"电子排布|电子云|能级|电离能|电子跃迁",
    "成键": r"杂化|分子构型|价层电子对|键角|[σπ]键|配位|共价键|范德华|氢键|分子间作用",
}
CHEM_FRONT = {
    "STSE": r"绿色化学|资源化|社会生产|节能减排|再生利用|材料回收|废水|污染|食品|低碳|新能源|碳排放",
    "基础实验操作": r"实验装置|实验操作|分液|洗涤|蒸馏|容量瓶|量筒|滴定管|气密性|过滤|称量|检漏|洗气",
}
CHEM_BLANK_LIMITS = (4, 12)


def corridor_findings(subject, paper, answers, fields):
    rows = paper["questions"]
    evidence = {}
    findings = []
    if subject == "physics":
        evidence, findings = physics_corridor.allocation(rows)
        for n, (question, answer) in enumerate(zip(rows,answers,strict=True), 1):
            findings.extend((n, "physics_pi", note) for note in physics_corridor.pi_findings(question,answer))
    elif subject == "chinese":
        findings.extend(language_corridor.chinese_findings(paper, fields))
    elif subject == "english":
        findings.extend(language_corridor.english_findings(paper, answers, fields))
    elif subject == "chemistry":
        structure = {module: [n for n,q in enumerate(rows, 1) if re.search(pattern, item_text(q))]
                     for module,pattern in CHEM_STRUCTURE.items()}
        front = {module: [n for n,q in enumerate(rows[:5], 1) if re.search(pattern, item_text(q))]
                 for module,pattern in CHEM_FRONT.items()}
        if not {"原子", "成键"}.intersection(k for k, v in structure.items() if v):
            findings.append((0, "chemistry_structure", "选必2须有晶胞以外的原子或成键知识"))
        elif len({n for hits in structure.values() for n in hits}) < 2:
            findings.append((0, "chemistry_structure", "选必2须有至少两道实质题目"))
        for module,hits in front.items():
            if not hits:
                findings.append((0, "chemistry_front", f"前五题缺{module}设问"))
        low, high = CHEM_BLANK_LIMITS
        blanks = {n:len(re.findall(r"_{3,}", item_text(q))) for n,q in enumerate(rows,1) if 15<=n<=18}
        for n, count in blanks.items():
            if not low <= count <= high:
                findings.append((n, "chemistry_blanks", f"第{n}题有 {count} 个嵌入空，要求 {low}–{high} 个"))
        evidence = {"structure":structure,"first_five":front,"nonchoice_blanks":{str(n):c for n,c in blanks.items()}}
    return evidence, findings


def inspect(root, subject, paper, answers, *, header=None, observations=(), policy_snapshot=None,
            figure_folder=None, listening=None, enforce_corridors=False, release_artifacts=None):
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
            if re.search(r"原子核|α 衰变|原子能级|能级跃迁|发射光谱|逸出功|光电子|能级.{0,12}跃迁",t) and n not in result["coverage"]["原子物理"]:
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
    nonchoice, missing = required_figure_issues(subject,rows)
    for number, rule, fact in missing:
        issue(number,rule,fact)
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
        figure = q.get("figure")
        if subject=="math" and isinstance(figure,dict) and figure.get("type")=="wireframe":
            from mathgen.student_pdf import draw_figure

            try:
                draw_figure(figure)
            except (ValueError,KeyError,TypeError) as error:
                issue(n,"wireframe_projection",str(error))
            if undefined := wireframe_undefined_vertices(q, figure):
                issue(n, "wireframe_undefined_vertex",
                      "立体几何配图含题干未定义顶点（疑似辅助点/辅助线泄题）：" + "、".join(undefined))
        if isinstance(figure,dict) and figure.get("type") in ("coordinate","wireframe"):
            labels = [entry.get("math","") for entry in figure.get("labels",[])]
            labels.extend(figure.get("vertices",{}))
            labels.append(figure.get("caption_math",""))
            if words := label_hits(labels,subject):
                issue(n,"figure_language","示意图标注需中文化："+"、".join(words))
        if isinstance(figure,dict) and figure_folder and figure.get("path") and figure.get("sha256"):
            labels = printed_figure_labels(figure, figure_folder)
            if labels is None:
                warnings.append({"number":n,"rule":"figure_labels_unavailable",
                                 "evidence":"原图无导出文字层，须在独立印刷审稿中逐图核读"})
            elif words := label_hits(labels,subject):
                issue(n,"figure_language","题图中须改写的英文标签："+"、".join(words))
            fig_path = relative_path(figure_folder, figure["path"])
            if fig_path.suffix.lower() == ".png":
                if clipped := figure_edge_clipping(fig_path):
                    issue(n, "figure_edge_clipped",
                          f"题图边缘（{', '.join(clipped)}）检测到非背景像素被画布截断，请导出时加 bbox_inches=\"tight\", pad_inches=0.1")
        if scoped and n in STANDARD_LAYOUT[subject]["embedded_blanks"] and not re.search(r"_{3,}",stem):
            issue(n,"missing_blank","指定题位没有嵌入式答位")
    if scoped and len(illustrated)<STANDARD_LAYOUT[subject]["choice_figures_minimum"]:
        issue(0,"figures",f"配图选择题仅 {illustrated}")
    if subject=="math" and re.search(r"(?:选对但不全|部分选对)(?:的)?得\s*3\s*分",header or ""):
        issue(0,"scoring","数学卷出现旧物理计分文案")
    snapshot = paper.get("exam_policy")
    fields = list(language_corridor.student_fields(paper))
    listen_slots = {}
    for n, row in enumerate(rows[:20],1):
        if row.get("material"):
            listen_slots.setdefault(row["material"],n)
    fields.extend((listen_slots.get(key,0),text) for key,text in (listening or {}).items())
    if snapshot:
        expected = exam_policy.resolve(root, subject, snapshot["year"], snapshot["region"], snapshot["series"])
        if snapshot != expected:
            issue(0, "policy_conflict", "卷面绑定的考制与当前政策表不同")
        title_year = re.match(r"\s*(20\d{2})\s*年", paper.get("title",""))
        if title_year and int(title_year[1]) != snapshot["year"]:
            issue(0, "policy_conflict", "标题年份与送审目标年份不同")
        instructions = list(fields)
        if header is not None:
            instructions.append((0, header))
            printed = exam_policy.compact(header)
            for note in exam_policy.student_instructions(expected):
                if exam_policy.compact(note) not in printed:
                    issue(0, "policy_conflict", "学生PDF缺本年度标准文案：" + note)
        for n, reason in dict.fromkeys(exam_policy.conflicts(expected, instructions)):
            issue(n, "policy_conflict", reason)
    elif enforce_corridors:
        issue(0, "policy_conflict", "标准卷缺按目标年份、地区及卷系绑定的考制")
    corridor = {}
    if enforce_corridors:
        corridor, violations = corridor_findings(subject, paper, answers, fields)
        for n, rule, fact in violations:
            issue(n, rule, fact)
        if subject == "english":
            warnings.extend(language_corridor.spelling_warnings(fields))
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
    if release_artifacts is not None:
        from core.release_checks import findings, math_point_warnings

        for number, rule, fact in findings(subject,paper,answers,header=header or "",
                                           listening=listening,artifacts=release_artifacts):
            issue(number,rule,fact)
        if subject=="math":
            warnings.extend({"number":n,"rule":rule,"evidence":fact}
                            for n,rule,fact in math_point_warnings(rows,release_artifacts.get("solutions",{})))
    if subject == "math":
        from core.release_checks import SUBJECT_COUNTS, math_coverage_warnings

        if len(rows) == SUBJECT_COUNTS["math"]:
            warnings.extend({"number": n, "rule": rule, "evidence": fact}
                            for n, rule, fact in math_coverage_warnings(rows))
        if paper.get("layout_mode", "exam") == "exam":
            student_pdf = (release_artifacts or {}).get("student_pdf")
            if not student_pdf and figure_folder:
                for candidate_pdf in (Path(figure_folder) / "paper.pdf", Path(figure_folder) / "review-only" / "paper.pdf"):
                    if candidate_pdf.is_file():
                        student_pdf = candidate_pdf
                        break
            if student_pdf and Path(student_pdf).is_file():
                warnings.extend({"number": n, "rule": rule, "evidence": fact}
                                for n, rule, fact in math_exam_pagination_warnings(student_pdf))
    return {"policy_sha256":fingerprint(policy_snapshot if policy_snapshot is not None else policies(root,subject)),"issues":issues,"warnings":warnings,
            "coverage":result["coverage"],"choice_figures":illustrated,"nonchoice_figures":nonchoice,
            "wrong_options":wrong,"absolute_wrong_options":absolutes,"abstract_mentions":abstract,
            "absolute_wrong_fraction":absolutes/wrong if wrong else None,
            "abstract_per_question":abstract/len(rows),"passed":not issues,
            **({"corridor":corridor,"exam_policy_sha256":fingerprint(snapshot)} if enforce_corridors else {})}


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


def exam_axes(ax, xlabel, ylabel):
    """Set a Cartesian exam plot's standard arrowheads, grid and axis labels."""
    from matplotlib.ticker import AutoMinorLocator

    ax.set(xlabel=xlabel,ylabel=ylabel)
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    ax.grid(which="minor",alpha=.15,linewidth=.35)
    for axis in ("top","right"):
        ax.spines[axis].set_visible(False)
    for start,end in (((.97,0),(1.02,0)),((0,.97),(0,1.02))):
        ax.annotate("",end,start,xycoords="axes fraction",
                    annotation_clip=False,arrowprops={"arrowstyle":"->","lw":.9})
    return ax


def save_figure(fig,path,*,subject=None,cartesian=False):
    from matplotlib.text import Text
    collisions=figure_collisions(fig)
    require(not collisions,"图件文字交叠："+str(collisions))
    labels = [t.get_text() for t in fig.findobj(Text) if t.get_visible() and t.get_text().strip()
              and (t.axes is None or t.axes.get_visible())]
    if subject:
        bad = label_hits(labels,subject)
        require(not bad,"题图中须改写的英文标签："+"、".join(bad))
    if cartesian:
        require(all(ax.get_xlabel().strip() and ax.get_ylabel().strip() for ax in fig.axes),
                "数据坐标图须标双轴、物理量和适用单位")
        require(not any(re.search(r"\d(?:mm|nm|kPa|mWb|m²)(?![A-Za-z])",label) for label in labels),
                "数据标注的数值与单位须留细空格")
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    metadata = {LABEL_KEY:json.dumps(labels,ensure_ascii=False)} if path.suffix.lower()==".png" else None
    fig.savefig(path,dpi=fig.dpi,bbox_inches="tight",pad_inches=0.1,facecolor="white",metadata=metadata)
