"""Layer 3: render reviewed school-language text; internal specifications are forbidden here."""

from itertools import groupby
import logging
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.platypus import (
    SimpleDocTemplate,
    Flowable,
    Spacer,
    KeepTogether,
    Image,
    HRFlowable,
    Table,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from matplotlib.mathtext import MathTextParser
from matplotlib.font_manager import FontProperties
from matplotlib import rc_context
from PIL import Image as PILImage, ImageOps
import numpy as np
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import proj3d
from analysis_db import fingerprint
from gaokao import require, atomic_write, digest
from core.editorial_rules import LAYOUT_MODES, REVISION, inline_response_only, item_text, notation_issues
from storage import atomic_json
from .cjk_layout import ExamParagraph, plain_markup
from .export import chinese_font

VERSION = "student-layout-v8"
MATH_RASTER = MathTextParser("agg")
FORMULA_DPI = 360
_SUB_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
PROSE_TRIANGLE = re.compile(
    r"△\s*([A-Z](?:['′]|[0-9]+|[₀-₉]+)?(?:[A-Z](?:['′]|[0-9]+|[₀-₉]+)?){2})(?![A-Za-z0-9])"
)
_DISPLAY_SPLIT = re.compile(r"\\\[(.*?)\\\]|\$\$(.*?)\$\$", re.S)
_MATH_SPAN = re.compile(r"\\\[.*?\\\]|\$\$.*?\$\$|\\\(.*?\\\)", re.S)


def formula_font_size(formula):
    # Superscript fractions need a larger base so the numerator survives print reduction.
    for group in re.finditer(r"\^\{((?:[^{}]|\{[^{}]*\})*)\}",formula):
        if re.search(r"\\[dt]?frac\b",group[1]):
            return 15
    return 12


def option_grid(options, width, compact=False):
    """Use the widest fitting row while keeping each label and answer together."""
    layouts = [(1/4,)*4, (.5,.5)]
    if compact:
        layouts.extend([(.54,.46), (.46,.54)])
    layouts.append((1,))
    for ratios in layouts:
        columns = len(ratios)
        widths = [width * ratio for ratio in ratios]
        usable = width / columns - 12
        if compact:
            for i, option in enumerate(options):
                option.wrap(widths[i % columns] - 12, 1000)
            lengths = [len(option.blPara.lines) for option in options]
            fits = all(length == 1 for length in lengths) and all(
                line.extraSpace >= -1e-6 for option in options for line in option.blPara.lines
            )
        else:
            fits = all(
                item.wrap(usable, 1000)[1] <= item.style.leading * 1.05 for item in options
            )
        if columns == 1 or fits:
            style = [("VALIGN", (0, 0), (-1, -1), "TOP")]
            if compact:
                style += [
                    ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ]
            return Table(
                [options[i:i + columns] for i in range(0, len(options), columns)],
                colWidths=widths,
                hAlign="LEFT",
                style=style,
            )


def science_section_note(kind, group, partial_credit=None, *, exam_policy=None, subject=None):
    total = sum(q["points"] for q in group)
    scores = {q["points"] for q in group}
    each = f"每小题{next(iter(scores))}分，" if len(scores) == 1 and kind.endswith("choice") else ""
    text = f"本大题共{len(group)}小题，{each}共{total}分。"
    if kind == "single_choice":
        return text + "在每小题给出的四个选项中，只有一项是符合题目要求的。"
    if kind == "multiple_choice":
        from core.exam_policy import parameters

        rule = parameters(exam_policy, "multiple_choice")
        if rule and scores == {rule["full_credit"]}:
            scoring = rule["instruction"]
        else:  # Older editions and exercises may define individual scoring.
            partial = "部分选对得部分分" if partial_credit is None else f"选对但不全得{partial_credit}分"
            scoring = f"全部选对得满分，{partial}，有选错的得0分。"
        return text + "在每小题给出的四个选项中，有多项符合题目要求。" + scoring
    text += "按题意填写或作答。"
    if subject in (None,"physics"):
        text += "计算题须写出必要的文字说明、方程式和演算步骤。"
    return text


class QuestionStart(Flowable):
    def __init__(self, number):
        super().__init__()
        self.number = number

    def draw(self):
        self.canv.question_starts.append(self.number)


class BlankCalculationSpace(Flowable):
    """An empty writable area with faint corners, measured on the printed page."""
    def __init__(self, number, height_cm, placements, *, continuation=False):
        super().__init__()
        self.number = number
        self.writable = height_cm * cm
        self.height = self.writable + 8
        self.placements = placements
        self.continuation = continuation

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return self.width, self.height

    def split(self, avail_width, avail_height):
        return []

    def draw(self):
        from core.exam_pages import calculation_corners

        canvas = self.canv
        placement = self.record()
        if hasattr(canvas,"calculation_areas"):
            left,bottom = canvas.absolutePosition(0,4)
            canvas.calculation_areas.append((left,bottom,self.width,bottom+self.writable,placement))
        else:
            calculation_corners(canvas,0,4,self.width,self.height-4)

    def record(self):
        placement = {"number":self.number,"page":self.canv.getPageNumber(),
                     "height_cm":round(self.writable/cm,2),"continuation":self.continuation}
        self.placements.append(placement)
        return placement


class LinedWritingSpace(BlankCalculationSpace):
    def split(self, avail_width, avail_height):
        # Split long prose areas at a natural page boundary with a usable block on each page.
        minimum = min(2.75 * cm, self.writable / 2)
        if self.continuation or self.writable < 4*cm or avail_height < minimum + 8:
            return []
        first = min(avail_height-8, self.writable-minimum)
        return [type(self)(self.number, first/cm, self.placements),
                type(self)(self.number, (self.writable-first)/cm, self.placements, continuation=True)]

    def draw(self):
        canvas=self.canv
        canvas.saveState()
        canvas.setStrokeGray(.71)
        canvas.setLineWidth(.4)
        for y in range(8,int(self.height)-3,19):
            canvas.line(0,y,self.width,y)
        canvas.restoreState()
        self.record()


def answer_height(q):
    if q["kind"] not in ("constructed_response","response","writing"):
        return 0
    points = q["points"]
    if q.get("response_area") == "calculation":
        return 5
    # A blank in just one part must not suppress the workspace for a later proof.
    if inline_response_only(q):
        return 0
    if points <= 9:
        return 4
    if points <= 13:
        return 7
    if points >= 25:
        return 18
    return 9.6 if points <= 15 else 10.4


def formula_image(formula, filename):
    """Use the raster backend's ink bounds so italic glyphs are not clipped."""
    with rc_context({"mathtext.fontset": "stix"}):
        parsed = MATH_RASTER.parse(
            "$" + formula + "$", dpi=FORMULA_DPI, prop=FontProperties(size=formula_font_size(formula))
        )
    ink = PILImage.fromarray(np.asarray(parsed.image))
    ImageOps.invert(ink).save(filename, format="PNG")


def normalise_prose_triangles(text):
    """Rewrite full-width △ABC outside math delimiters as \\(\\triangle ABC\\)."""
    if not text or "△" not in text:
        return text

    def _replace_segment(segment):
        def _sub(match):
            verts = match.group(1).translate(_SUB_DIGITS).replace("′", "'")
            verts = re.sub(r"([A-Za-z])([0-9]+)", r"\1_{\2}", verts)
            return r"\(\triangle " + verts + r"\)"

        return PROSE_TRIANGLE.sub(_sub, segment)

    out = []
    at = 0
    for match in _MATH_SPAN.finditer(text):
        out.append(_replace_segment(text[at:match.start()]))
        out.append(match.group(0))
        at = match.end()
    out.append(_replace_segment(text[at:]))
    return "".join(out)


def normalise_tex(text):
    """Expand TeX's single-token macro arguments, preserving their mathematical meaning."""
    require(
        not re.search(r"[\u3400-\u9fff]", text),
        "数学字体不支持公式内中文，须将中文说明移到正文，不能用缺字占位符发布",
    )
    text = re.sub(r"\\complement(?![A-Za-z])",lambda _:r"\mathrm{∁}",text)
    text = re.sub(
        r"\\(le|ge)(?![A-Za-z])", lambda m: r"\leq" if m[1] == "le" else r"\geq", text
    )

    def atom(start):
        while start < len(text) and text[start].isspace():
            start += 1
        require(start < len(text), "公式命令缺少参数")
        if text[start] == "{":
            depth = 1
            end = start + 1
            while end < len(text) and depth:
                if text[end] == "{":
                    depth += 1
                elif text[end] == "}":
                    depth -= 1
                end += 1
            require(depth == 0, "公式花括号不匹配")
            return text[start + 1 : end - 1], end
        if text[start] == "\\":
            m = re.match(r"\\[A-Za-z]+", text[start:])
            require(m, "公式控制字符不合法")
            return m[0], start + len(m[0])
        return text[start], start + 1

    at = 0
    out = []
    while at < len(text):
        m = re.match(
            r"\\(frac|binom|sqrt|mathbb|mathbf|mathcal|boldsymbol|mathrm|overline)(?![A-Za-z])",
            text[at:],
        )
        if not m:
            out.append(text[at])
            at += 1
            continue
        command = m[1]
        at += len(m[0])
        prefix = "\\" + command
        if command == "sqrt" and at < len(text) and text[at] == "[":
            end = text.find("]", at)
            require(end >= 0, "根式次数不完整")
            prefix += text[at : end + 1]
            at = end + 1
        arguments = []
        for _ in range(2 if command in ("frac", "binom") else 1):
            value, at = atom(at)
            arguments.append("{" + normalise_tex(value) + "}")
        out.append(prefix + "".join(arguments))
    return "".join(out)


def draw_figure(data, image=None):
    fig = Figure(figsize=(4.8, 2.65), dpi=250)
    if data["type"] == "wireframe":
        from .wireframe import check_projection, hidden_edges

        ax = fig.add_subplot(111, projection="3d")
        ax.set_proj_type("ortho")
        angles=data.get("view_angles",(20,-55))
        ax.view_init(*angles)
        elevation,azimuth=np.radians(angles)
        direction=np.array([np.cos(elevation)*np.cos(azimuth),np.cos(elevation)*np.sin(azimuth),np.sin(elevation)])
        points=np.asarray(list(data["vertices"].values()),dtype=float)
        mins, maxs = points.min(axis=0), points.max(axis=0)
        center=(mins+maxs)/2
        span=np.maximum(maxs-mins,1e-9)
        half=span*0.55
        hidden=hidden_edges(data["vertices"],data["edges"],center+100*float(np.max(span))*direction)
        for a,b in data["edges"]:
            (line,) = ax.plot(*zip(data["vertices"][a], data["vertices"][b]),
                              color="black", linewidth=1.15)
            if frozenset((a,b)) in hidden:
                line.set_dashes((5, 4))
        ax.set_xlim(center[0]-half[0], center[0]+half[0])
        ax.set_ylim(center[1]-half[1], center[1]+half[1])
        ax.set_zlim(center[2]-half[2], center[2]+half[2])
        ax.set_box_aspect(span)
        ax.set_axis_off()
        ax.apply_aspect()
        check_projection(data["vertices"],data["edges"],ax.get_proj(),ax.transData)
        for name, point in data["vertices"].items():
            px,py,_ = proj3d.proj_transform(*point, ax.get_proj())
            if name in data.get("marked_points", ()):
                ax.plot(*([value] for value in point), "ko", markersize=3)
            if data.get("show_vertex_labels", True):
                display = re.sub(r"([A-Za-z])([0-9]+)", r"\1_{\2}", name)
                ax.annotate("$" + display + "$", (px,py),
                            xytext=data.get("label_offsets", {}).get(name,[3,3]),
                            textcoords="offset points", fontsize=12)
        for mark in data.get("labels", []):
            edge = mark.get("edge")
            if not edge:
                continue
            require(any(set(edge) == set(pair) for pair in data["edges"]), "尺寸标注须绑定图中棱")
            midpoint = np.mean([data["vertices"][name] for name in edge], axis=0)
            px, py, _ = proj3d.proj_transform(*midpoint, ax.get_proj())
            center_x, center_y, _ = proj3d.proj_transform(*center, ax.get_proj())
            outward = np.array([px-center_x,py-center_y])
            norm = np.linalg.norm(outward)
            offset = 12*outward/norm if norm else (0,12)
            ax.annotate("$" + mark["math"] + "$", (px, py),
                        xytext=offset,textcoords="offset points",ha="center",va="center",fontsize=11)
    else:
        require(data["type"] == "coordinate", "不支持的试卷图形")
        ax = fig.add_subplot()
        fig.subplots_adjust(left=.12,right=.93,bottom=.13,top=.90)
        ax.set(xlim=data["xlim"],ylim=data["ylim"],xticks=[],yticks=[])
        ax.set_aspect("equal", adjustable="box")
        ax.set_axis_off()
        if data.get("axes", True):
            xmin,xmax=data["xlim"]
            ymin,ymax=data["ylim"]
            for start,end,label in [((xmin,0),(xmax,0),"$x$"), ((0,ymin),(0,ymax),"$y$")]:
                ax.annotate("", end, start, arrowprops={"arrowstyle":"->","lw":.8})
                ax.text(*end,label,fontsize=12)
        for segment in data["paths"]:
            ax.plot(*zip(*segment["points"]),color="black",lw=1.1,
                    linestyle="--" if segment.get("dashed") else "-")
        for mark in data.get("labels", []):
            ax.annotate("$"+mark["math"]+"$",mark["at"],
                        xytext=mark.get("offset",[3,3]),textcoords="offset points",fontsize=11)
            if mark.get("dot"):
                ax.plot(*mark["at"],"ko",markersize=2.8)
    if image is not None:
        fig.savefig(image,bbox_inches="tight",pad_inches=.13,facecolor="white")



def render(paper, path, solutions=False, *, layout_mode=None):
    from functools import partial
    from core.exam_pages import ExamPages
    from core.exam_policy import guess_snapshot
    from gaokao import ROOT

    policy = paper.get("exam_policy")
    if not policy and paper.get("subject") in ("math", "physics"):
        policy = guess_snapshot(ROOT, paper["subject"], paper.get("title",""))
    mode = layout_mode or paper.get("layout_mode", "exam")
    require(mode in LAYOUT_MODES, "排版模式须为 practice 或 exam")
    practice = not solutions and mode == "practice"
    placements = []
    if paper.get("edition_rules") == REVISION and paper.get("subject") == "math":
        for q in paper["questions"]:
            text = " ".join(q.get("solution_paragraphs", [])) if solutions else item_text(q, options=True)
            issue = notation_issues(text)
            require(not issue, issue)

    require(
        not any(k in paper for k in ("math_spec", "tasks", "design", "verifications")),
        "排版器禁止接收内部数学规格",
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    assets = path.parent / "assets"
    assets.mkdir(exist_ok=True)
    font = chinese_font()
    science_layout = paper.get("layout") == "science"
    math_compact = paper.get("layout") == "math_compact"
    physics_layout = science_layout and paper.get("subject") == "physics"
    dense_chemistry = science_layout and paper.get("subject") == "chemistry"
    margin = 38 if dense_chemistry else 44
    compact = science_layout or math_compact or not solutions
    science_key = compact and solutions
    body = ParagraphStyle(
        "student-body",
        fontName=font,
        fontSize=10.5 if science_key else 10.8 if dense_chemistry else 11 if compact else 11.5,
        leading=20 if solutions else 15 if dense_chemistry else 16,
        spaceAfter=3 if science_key else 3.5 if compact else 9,
        wordWrap="CJK",
        autoLeading="max",
    )
    if solutions:
        body.allowOrphans=0
        body.allowWidows=0
    heading = ParagraphStyle(
        "student-heading",
        parent=body,
        fontSize=12,
        leading=22,
        spaceBefore=8 if compact else 12,
        spaceAfter=3 if compact else 8,
        keepWithNext=True,
    )
    title = ParagraphStyle(
        "student-title",
        parent=body,
        fontSize=19,
        leading=29,
        alignment=TA_CENTER,
        spaceAfter=7 if compact else 14,
    )
    note = ParagraphStyle(
        "student-note", parent=body, fontSize=10, leading=15 if compact else 18,
        spaceAfter=5 if compact else 8,
    )
    note_keep = ParagraphStyle("student-note-keep", parent=note, keepWithNext=True)

    response_line = ParagraphStyle("response-blank", parent=body,
                                   leading=18.5 if dense_chemistry else 20, spaceAfter=5,
                                   allowOrphans=0, allowWidows=0)
    avail_width = A4[0] - 2 * margin

    def compile_formula(raw_formula, *, display=False):
        formula = normalise_tex(raw_formula.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac"))
        formula = re.sub(
            r"\\(mathbb|mathbf|mathcal|boldsymbol|mathrm|overline)\s+([A-Za-z])",
            r"\\\1{\2}",
            formula,
        )
        # TeX permits single-token arguments; normalize them for mathtext.
        formula = re.sub(r"\\sqrt([A-Za-z0-9])", r"\\sqrt{\1}", formula)
        formula = re.sub(
            r"\\frac([A-Za-z0-9])([A-Za-z0-9])", r"\\frac{\1}{\2}", formula
        )
        formula = re.sub(
            r"\\frac\{([^{}]+)\}([A-Za-z0-9])", r"\\frac{\1}{\2}", formula
        )
        formula = re.sub(r"\\frac([A-Za-z0-9])\{", r"\\frac{\1}{", formula)
        require(
            not re.search(
                r"\\(?:land|lor|wedge|vee|operatorname)|\*\*|Interval", formula
            ),
            "不合格公式禁止排版",
        )
        filename = assets / (
            fingerprint({"math": formula, "font": 12, "layout": VERSION})[:20]
            + ".png"
        )
        if not filename.exists():
            formula_image(formula, filename)
        with PILImage.open(filename) as im:
            w, h = im.size
        scale = 72 / FORMULA_DPI
        w_pt, h_pt = w * scale, h * scale
        require(w_pt <= (640 if display else 480), "公式太长，应在中文写作层拆分后重新审查")
        return filename, w_pt, h_pt

    def _is_large_reference_formula(raw_formula, h_pt):
        if r"\sum" in raw_formula and re.search(r"\\[dt]?frac\b", raw_formula):
            return True
        if re.search(r"\\sqrt\s*\{[^}]*(?:\\[dt]?frac|\\sum)", raw_formula):
            return True
        if h_pt >= 28 and re.search(r"\\[dt]?frac\b", raw_formula) and ("=" in raw_formula or r"\approx" in raw_formula):
            return True
        return False

    def display_images(raw_formula):
        lines = [part.strip() for part in re.split(r"\\\\", raw_formula.strip()) if part.strip()]
        flowables = [Spacer(1, 3)]
        max_w = avail_width - 4
        for part in lines:
            filename, w_pt, h_pt = compile_formula(part, display=True)
            if w_pt > max_w:
                ratio = max_w / w_pt
                w_pt, h_pt = max_w, h_pt * ratio
            flowables.append(Image(str(filename), width=w_pt, height=h_pt, hAlign="CENTER"))
            if len(lines) > 1:
                flowables.append(Spacer(1, 2))
        flowables.append(Spacer(1, 3))
        return flowables

    def para(text, style=body):
        text = normalise_prose_triangles(text)
        chunks = []
        at = 0
        tallest = 0
        plain = plain_markup
        for m in re.finditer(r"\\\((.*?)\\\)", text, re.S):
            chunks.append(plain(text[at : m.start()]))
            filename, w_pt, h_pt = compile_formula(m.group(1), display=False)
            tallest = max(tallest, h_pt)
            chunks.append(
                f'<img src="{escape(filename.as_posix())}" width="{w_pt:.2f}" height="{h_pt:.2f}" valign="middle"/>'
            )
            at = m.end()
        chunks.append(plain(text[at:]))
        if tallest+5 > style.leading:
            # ReportLab's first line starts at fontSize below the flowable top,
            # so increasing baseline spacing alone leaves tall ink above it.
            style = ParagraphStyle("tall-inline",parent=style,leading=tallest+5,
                                   spaceBefore=max(style.spaceBefore,tallest/2))
        return ExamParagraph("".join(chunks).replace("\n", "<br/>"), style)

    def block_flowables(text, style=body):
        """Render paragraphs while promoting explicit display math and oversized reference formulas."""
        text = normalise_prose_triangles(text)
        out = []

        def emit_prose_chunk(chunk):
            if not chunk:
                return
            lines = chunk.split("\n")
            buffered = []

            def flush():
                if buffered:
                    joined = "\n".join(buffered)
                    if joined.strip():
                        out.append(para(joined, style))
                    buffered.clear()

            for line in lines:
                solo = re.fullmatch(r"\s*\\\((.*?)\\\)\s*", line, re.S)
                if solo and (len(lines) > 1 or re.search(r"\\(?:sum|[dt]?frac|sqrt|rightleftharpoons|Delta)\b", solo.group(1))):
                    flush()
                    out.extend(display_images(solo.group(1)))
                    continue
                promoted = False
                cursor = 0
                pending = ""
                for m in re.finditer(r"\\\((.*?)\\\)", line, re.S):
                    inner = m.group(1)
                    _, _, h_pt = compile_formula(inner, display=True)
                    if _is_large_reference_formula(inner, h_pt):
                        promoted = True
                        before = pending + line[cursor:m.start()]
                        if before.strip():
                            buffered.append(before.rstrip())
                        flush()
                        out.extend(display_images(inner))
                        pending = ""
                        cursor = m.end()
                if promoted:
                    tail = line[cursor:]
                    if tail.strip() and not re.fullmatch(r"[\s。；，、.]+", tail):
                        buffered.append(tail.lstrip())
                else:
                    buffered.append(line)
            flush()

        at = 0
        for m in _DISPLAY_SPLIT.finditer(text):
            emit_prose_chunk(text[at:m.start()])
            raw_display = m.group(1) if m.group(1) is not None else m.group(2)
            out.extend(display_images(raw_display))
            at = m.end()
        tail = text[at:]
        if at and tail and re.fullmatch(r"[\s。；，、.]+", tail):
            tail = ""
        emit_prose_chunk(tail)
        return out or [para(text, style)]

    if math_compact and solutions:
        subtitle = ParagraphStyle("math-solution-subtitle", parent=title, fontSize=13,
                                  leading=19, spaceAfter=12)
        story = [para(paper["title"], title), para("参考答案与评分标准", subtitle)]
    else:
        story = [para(paper["title"] + ("　参考答案与解析" if solutions else ""), title)]
    if not solutions:
        story.append(
            para(
                f"满分{paper['total_points']}分　　考试时间{paper['minutes']}分钟", note
            )
        )
        instruction = "请按题目要求作答。"
        if not compact and any(q["kind"] == "constructed_response" for q in paper["questions"]):
            instruction += "解答题须写出必要的文字说明、证明过程或演算步骤。"
        if not compact:
            story.append(para(instruction, note))
        if mode=="exam":
            story.append(para(f"本试卷共{len(paper['questions'])}题。请在答题卡相应位置作答。",note))
        if paper.get("subject")=="chemistry" and (masses:=paper.get("relative_atomic_masses")):
            from core.chemistry_data import sort_atomic_masses

            ordered = sort_atomic_masses(masses)
            pairs = "　".join(f"<nobr>{plain_markup(f'{k}—{v}')}</nobr>" for k, v in ordered.items())
            story.append(ExamParagraph(plain_markup("可能用到的相对原子质量：") + pairs, note))
    previous = None
    section_titles = {
        "single_choice": "单项选择题",
        "multiple_choice": "多项选择题",
        "fill_in": "填空题",
        "constructed_response": "解答题",
    }
    if compact:
        section_titles.update(multiple_choice="多项选择题")
    if science_layout:
        section_titles.update(constructed_response="非选择题")
    groups = {kind: list(items) for kind, items in groupby(paper["questions"], key=lambda q: q["kind"])}
    section_number = 0
    md = ["# " + paper["title"], ""]
    if math_compact and solutions:
        md += ["参考答案与评分标准", ""]
    if compact and not solutions:
        md += [f'满分{paper["total_points"]}分，考试时间{paper["minutes"]}分钟。', ""]
        if mode=="exam":
            md += [f"本试卷共{len(paper['questions'])}题。请在答题卡相应位置作答。",""]
        if paper.get("subject")=="chemistry" and (masses:=paper.get("relative_atomic_masses")):
            from core.chemistry_data import sort_atomic_masses

            ordered = sort_atomic_masses(masses)
            md += ["可能用到的相对原子质量：" + "　".join(f"{k}—{v}" for k, v in ordered.items()), ""]
    is_science = science_layout or paper.get("subject") in ("physics", "chemistry", "biology")
    for index, q in enumerate(paper["questions"]):
        require(
            not any(k in q for k in ("math_spec", "tasks", "design", "solver_record")),
            "排版输入混入内部数据",
        )
        section = []
        if q["kind"] != previous and (not solutions or math_compact or science_layout):
            section_number += 1
            prefix = (
                "一二三四"[section_number - 1] + "、" if section_number <= 4 else ""
            )
            label = prefix + section_titles[q["kind"]]
            section.append(para(label, heading))
            if solutions:
                md.extend([f"## {label}", ""])
                if q["kind"] == "constructed_response":
                    if math_compact:
                        from core.marking_standards import MATH_EQUIVALENCE

                        section.append(para(MATH_EQUIVALENCE, note_keep))
                        md.extend([MATH_EQUIVALENCE, ""])
                    elif science_layout:
                        from core.marking_standards import science_equivalence

                        equiv = science_equivalence(paper.get("subject"))
                        section.append(para(equiv, note_keep))
                        md.extend([equiv, ""])
            elif compact or q["kind"] == "multiple_choice":
                if math_compact and q["kind"] in ("fill_in", "constructed_response"):
                    group = groups[q["kind"]]
                    prompt = (("请将答案填在横线上。" if practice else "请将答案填在答题卡的相应位置。") if q["kind"] == "fill_in"
                              else "解答应写出文字说明、证明过程或演算步骤。")
                    each = ""
                    if q["kind"] == "fill_in" and len({item["points"] for item in group}) == 1:
                        each = f"每小题{group[0]['points']}分，"
                    instructions = f"本大题共{len(group)}小题，{each}共{sum(item['points'] for item in group)}分。" + prompt
                else:
                    instructions = science_section_note(q["kind"], groups[q["kind"]], paper.get("partial_credit"),
                                                        exam_policy=policy,subject=paper.get("subject"))
                section.append(para(instructions, note))
                md.extend([f"## {label}", "", instructions, ""])
            previous = q["kind"]
        choice = q["kind"] in ("single_choice", "multiple_choice")
        number = f"{q['order']}."
        if not compact or (not choice and not (math_compact and q["kind"] == "fill_in")):
            number += f"（{q['points']}分）"
        block = section
        if not compact:
            block.append(para(number, heading))
        figures_in_md = []
        solution_figs_in_md = []
        md_solution_paragraphs = []

        def append_table(table):
            from core.native_tables import pdf_table

            if table.get("caption"):
                block.append(para(table["caption"], note))
            block.append(pdf_table(table, para, A4[0] - 2 * margin - 12))

        if solutions:
            raw_solution = list(q["solution_paragraphs"])
            if is_science:
                from core.chemistry_data import format_science_rubric

                raw_solution = [
                    format_science_rubric(p) if p.lstrip().startswith("评分参考") else p
                    for p in raw_solution
                ]
            md_solution_paragraphs = [normalise_prose_triangles(p) for p in raw_solution]
            solution = list(raw_solution)
            if compact:
                first = solution[0].replace("\n", " ", 1) if choice else solution[0]
                block.extend(block_flowables(number + " " + first))
                solution = solution[1:]
            if sol_table := q.get("solution_table"):
                append_table(sol_table)
            for p in solution:
                block.extend(block_flowables(p))
            for fig_entry in q.get("solution_figures", []):
                caption = None
                if isinstance(fig_entry, dict) and fig_entry.get("type") in ("wireframe", "coordinate"):
                    caption = fig_entry.get("caption")
                    directory = path.parent / "figures" if compact else assets
                    directory.mkdir(exist_ok=True)
                    fig_path = directory / (fingerprint(fig_entry)[:20] + "-solution-figure.png")
                    draw_figure(fig_entry, fig_path)
                elif isinstance(fig_entry, dict):
                    caption = fig_entry.get("caption")
                    fig_path = Path(fig_entry["path"])
                    if not fig_path.is_absolute():
                        fig_path = path.parent / fig_path
                    require(fig_path.is_file(), "答案图形资源缺失")
                    if fig_entry.get("sha256"):
                        require(digest(fig_path) == fig_entry["sha256"], "答案图形哈希不符")
                else:
                    fig_path = Path(fig_entry)
                    if not fig_path.is_absolute():
                        fig_path = path.parent / fig_path
                    require(fig_path.is_file(), "答案图形资源缺失")
                if caption:
                    block.append(para(caption, note))
                block.append(Image(str(fig_path), width=420 if compact else 340,
                                   height=160, kind="proportional"))
                try:
                    rel = fig_path.resolve().relative_to(path.parent.resolve()).as_posix()
                except ValueError:
                    rel = fig_path.as_posix()
                solution_figs_in_md.append((caption, rel))
        else:
            if practice:
                block.append(QuestionStart(q["order"]))
            block.extend(block_flowables(number + " " + q["stem"] if compact else q["stem"]))
            if q.get("table"):
                append_table(q["table"])
            if (data := q.get("figure")):
                if isinstance(data, dict):
                    directory = path.parent / "figures" if math_compact else assets
                    directory.mkdir(exist_ok=True)
                    figure = directory / (fingerprint(data)[:20] + "-figure.png")
                    draw_figure(data, figure)
                else:
                    figure = Path(data)
                require(figure.is_file(), "图形资源缺失")
                if compact:
                    figures_in_md.append(figure.resolve().relative_to(path.parent.resolve()).as_posix())
                if math_compact:
                    height_limit = 105 if choice else 139
                elif physics_layout:
                    height_limit = 82 if choice else 107
                else:
                    height_limit = 94 if choice else 116
                block.append(Image(str(figure), width=430 if compact else 290,
                                   height=height_limit, kind="proportional"))
            figures = q.get("archive_figures",[])
            captions = q.get("archive_figure_captions",[])
            labeled = {label:picture for picture,label in zip(figures,captions) if label in q["options"]}
            separate_options = not (labeled and set(labeled)==set(q["options"]))
            for figure_index, figure in enumerate(figures):
                caption = captions[figure_index] if figure_index < len(captions) else None
                if not separate_options and caption in labeled:
                    continue
                if caption:
                    block.append(para(caption,note))
                block.append(Image(str(figure),width=355,height=155,kind="proportional"))
            if not separate_options:
                cells=[]
                for key,value in q["options"].items():
                    label=key+". "+("" if value=="对应选项图" else value)
                    cells.append([para(label,note),Image(str(labeled[key]),width=218,height=94,kind="proportional")])
                block.append(Table([cells[i:i+2] for i in range(0,len(cells),2)],
                                   colWidths=[(A4[0]-100)/2]*2,hAlign="LEFT",
                                   style=[("VALIGN",(0,0),(-1,-1),"TOP")]))
            elif q["kind"] == "single_choice" or (compact and choice):
                block.append(option_grid(
                    [para(key + ". " + text) for key, text in q["options"].items()],
                    A4[0] - 2 * margin - 12,
                    compact=compact,
                ))
            else:
                for key, text in q["options"].items():
                    block.append(para(key + ". " + text))
            height = answer_height(q) if practice else 0
            part_blocks = [
                block_flowables(
                    part["label"] + " " + part["text"],
                    response_line if practice and "___" in part["text"] else body,
                )
                for part in q["parts"]
            ]
            keep_response = height > 0 or ((physics_layout or math_compact) and not choice and bool(part_blocks))
            if compact and not choice and not keep_response:
                # The figure and first subquestion stay with their stem.
                story.append(KeepTogether(block + (part_blocks[0] if part_blocks else [])))
                block, part_blocks = [], part_blocks[1:]
            for pb in part_blocks:
                block.extend(pb)
            if q["kind"] == "fill_in" and practice and "___" not in q["stem"]:
                block.append(para("答：________________。", note))
            if height:
                block.append(BlankCalculationSpace(q["order"], height, placements))
            if keep_response:
                # Leave the extended calculation and its blank together when they fit a sheet.
                story.append(KeepTogether(block))
                block = []
        if compact:
            if solutions or not choice:
                if (math_compact or science_layout) and solutions and choice and len(block) >= 2:
                    story.append(KeepTogether(block[:2]))
                    block = block[2:]
                story.extend(block)
            else:
                story.append(KeepTogether(block))
            if index + 1 < len(paper["questions"]):
                story.append(Spacer(1, 5 if solutions else 4))
        elif solutions:
            # Keep each solution together when it fits a page; long solutions may split.
            story.append(KeepTogether(block))
            if index + 1 < len(paper["questions"]):
                story.append(Spacer(1, 12))
        md.extend([f"## {number}" if math_compact and q["kind"] == "fill_in" else f"## {q['order']}.（{q['points']}分）", ""])
        from core.native_tables import markdown_table
        md.extend(
            [
                *(markdown_table(q["solution_table"]) if q.get("solution_table") else []),
                *md_solution_paragraphs,
                *[line for cap, rel in solution_figs_in_md for line in ([cap, f"![答案图]({rel})"] if cap else [f"![答案图]({rel})"])],
            ]
            if solutions
            else [
                normalise_prose_triangles(q["stem"]),
                *(markdown_table(q["table"]) if q.get("table") else []),
                *[f"![题图]({image})" for image in figures_in_md],
                *[f"![题图]({image.relative_to(path.parent).as_posix()})" for image in q.get("archive_figures",[])],
                *["%s. %s" % (k, normalise_prose_triangles(v)) for k, v in q["options"].items()],
                *[p["label"] + " " + normalise_prose_triangles(p["text"]) for p in q["parts"]],
            ]
        )
        md.append("")
    SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=33 if compact else 38,
        bottomMargin=52 if solutions else (34 if compact else 42),
        title=paper["title"],
        author="理科模拟试卷" if science_layout else "数学模拟试卷",
    ).build(story, canvasmaker=partial(ExamPages,footer_font=font))
    atomic_write(path.with_suffix(".md"), "\n".join(md).rstrip() + "\n")
    if not solutions:
        layout_meta = {"mode": mode, "paper_sha256": digest(path), "answer_areas": placements}
        if mode == "exam" and paper.get("subject") == "math":
            from core.exam_qa import math_exam_pagination_warnings, pdf_page_fill_ratio
            from pypdf import PdfReader

            page_count = len(PdfReader(path).pages)
            fill = pdf_page_fill_ratio(path, -1)
            layout_meta.update(pages=page_count, last_page_fill_ratio=round(fill, 4))
            for _, _, msg in math_exam_pagination_warnings(path):
                logging.warning("%s", msg)
        atomic_json(path.with_suffix(".layout.json"), layout_meta)
    return path
