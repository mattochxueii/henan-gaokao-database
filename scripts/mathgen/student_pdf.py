"""Layer 3: render reviewed school-language text; internal specifications are forbidden here."""

from itertools import groupby
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.platypus import (
    SimpleDocTemplate,
    Spacer,
    KeepTogether,
    PageBreak,
    Image,
    HRFlowable,
    Table,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from matplotlib.mathtext import MathTextParser
from matplotlib.font_manager import FontProperties
from matplotlib import rc_context
from PIL import Image as PILImage, ImageOps
import numpy as np
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import proj3d
from analysis_db import fingerprint
from gaokao import require, atomic_write
from .cjk_layout import ExamParagraph, plain_markup
from .export import chinese_font, MathParagraph, formatted_plain

VERSION = "student-layout-v4"
MATH_RASTER = MathTextParser("agg")


def option_grid(options, width, compact=False):
    """Use the widest fitting row while keeping each label and answer together."""
    for columns in (4, 2, 1):
        usable = width / columns - 12
        if compact:
            for option in options:
                option.wrap(usable, 1000)
            lengths = [len(option.blPara.lines) for option in options]
            row_lines = sum(max(lengths[i:i + columns]) for i in range(0, len(lengths), columns))
            fits = row_lines <= (1 if columns == 4 else 3) and all(
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
                colWidths=[width / columns] * columns,
                hAlign="LEFT",
                style=style,
            )


def science_section_note(kind, group, partial_credit):
    total = sum(q["points"] for q in group)
    scores = {q["points"] for q in group}
    each = f"每小题{next(iter(scores))}分，" if len(scores) == 1 and kind.endswith("choice") else ""
    text = f"本大题共{len(group)}小题，{each}共{total}分。"
    if kind == "single_choice":
        return text + "在每小题给出的四个选项中，只有一项是符合题目要求的。"
    if kind == "multiple_choice":
        scoring = "部分选对得部分分" if partial_credit is None else f"选对但不全得{partial_credit}分"
        return text + f"在每小题给出的四个选项中，有多项符合题目要求。全部选对得满分，{scoring}，有选错的得0分。"
    return text + "按题意填写或作答。计算题须写出必要的文字说明、方程式和演算步骤。"


def formula_image(formula, filename):
    """Use the raster backend's ink bounds so italic glyphs are not clipped."""
    with rc_context({"mathtext.fontset": "stix"}):
        parsed = MATH_RASTER.parse(
            "$" + formula + "$", dpi=240, prop=FontProperties(size=12)
        )
    ink = PILImage.fromarray(np.asarray(parsed.image))
    ImageOps.invert(ink).save(filename)


def normalise_tex(text):
    """Expand TeX's single-token macro arguments, preserving their mathematical meaning."""
    require(
        not re.search(r"[\u3400-\u9fff]", text),
        "数学字体不支持公式内中文，须将中文说明移到正文，不能用缺字占位符发布",
    )
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


def render(paper, path, solutions=False):
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
    body = ParagraphStyle(
        "student-body",
        fontName=font,
        fontSize=11 if science_layout else 11.5,
        leading=16 if science_layout else 23,
        spaceAfter=3.5 if science_layout else 9,
        wordWrap="CJK",
        autoLeading="max" if science_layout else "",
    )
    heading = ParagraphStyle(
        "student-heading",
        parent=body,
        fontSize=12,
        leading=22,
        spaceBefore=8 if science_layout else 12,
        spaceAfter=3 if science_layout else 8,
        keepWithNext=True,
    )
    title = ParagraphStyle(
        "student-title",
        parent=body,
        fontSize=19,
        leading=29,
        alignment=TA_CENTER,
        spaceAfter=7 if science_layout else 14,
    )
    note = ParagraphStyle(
        "student-note", parent=body, fontSize=10, leading=15 if science_layout else 18,
        spaceAfter=5 if science_layout else 8,
    )

    def para(text, style=body):
        chunks = []
        at = 0
        plain = plain_markup if science_layout else formatted_plain
        for m in re.finditer(r"\\\((.*?)\\\)", text, re.S):
            chunks.append(plain(text[at : m.start()]))
            formula = normalise_tex(m.group(1).replace(r"\dfrac",r"\frac").replace(r"\tfrac",r"\frac"))
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
            scale = 72 / 240
            require(w * scale <= 480, "公式太长，应在中文写作层拆分后重新审查")
            chunks.append(
                f'<img src="{escape(filename.as_posix())}" width="{w * scale:.2f}" height="{h * scale:.2f}" valign="middle"/>'
            )
            at = m.end()
        chunks.append(plain(text[at:]))
        paragraph = ExamParagraph if science_layout else MathParagraph
        return paragraph("".join(chunks).replace("\n", "<br/>"), style)

    def footer(canvas, doc):
        canvas.setFont(font, 9)
        canvas.drawCentredString(A4[0] / 2, 22, f"第 {doc.page} 页")

    story = [para(paper["title"] + ("　参考答案与解析" if solutions else ""), title)]
    if not solutions:
        story.append(
            para(
                f"满分{paper['total_points']}分　　考试时间{paper['minutes']}分钟", note
            )
        )
        instruction = "请按题目要求作答。"
        if not science_layout and any(q["kind"] == "constructed_response" for q in paper["questions"]):
            instruction += "解答题须写出必要的文字说明、证明过程或演算步骤。"
        if not science_layout:
            story.append(para(instruction, note))
    previous = None
    section_titles = {
        "single_choice": "单项选择题",
        "multiple_choice": "多项选择题（全部选对得满分，部分选对得部分分，有选错得0分）",
        "fill_in": "填空题",
        "constructed_response": "解答题",
    }
    if science_layout:
        section_titles.update(multiple_choice="多项选择题", constructed_response="非选择题")
    groups = {kind: list(items) for kind, items in groupby(paper["questions"], key=lambda q: q["kind"])}
    section_number = 0
    md = ["# " + paper["title"], ""]
    if science_layout and not solutions:
        md += [f'满分{paper["total_points"]}分，考试时间{paper["minutes"]}分钟。', ""]
    for index, q in enumerate(paper["questions"]):
        require(
            not any(k in q for k in ("math_spec", "tasks", "design", "solver_record")),
            "排版输入混入内部数据",
        )
        if (
            q["kind"] == "constructed_response"
            and previous == q["kind"]
            and not science_layout
            and not solutions
        ):
            story.append(PageBreak())
        section = []
        if q["kind"] != previous and not solutions:
            section_number += 1
            prefix = (
                "一二三四"[section_number - 1] + "、" if section_number <= 4 else ""
            )
            label = prefix + section_titles[q["kind"]]
            section.append(para(label, heading))
            if science_layout:
                instructions = science_section_note(q["kind"], groups[q["kind"]], paper.get("partial_credit"))
                section.append(para(instructions, note))
                md.extend([f"## {label}", "", instructions, ""])
            previous = q["kind"]
        choice = q["kind"] in ("single_choice", "multiple_choice")
        number = f"{q['order']}."
        if not science_layout or not choice:
            number += f"（{q['points']}分）"
        block = section
        if not science_layout:
            block.append(para(number, heading))
        figures_in_md = []
        if solutions:
            solution = q["solution_paragraphs"]
            if science_layout:
                first = solution[0].replace("\n", " ", 1) if choice else solution[0]
                block.append(para(number + " " + first))
                solution = solution[1:]
            block.extend(para(p) for p in solution)
        else:
            block.append(para(number + " " + q["stem"] if science_layout else q["stem"]))
            if q.get("figure"):
                if isinstance(q["figure"], dict):
                    data = q["figure"]
                    require(data["type"] == "wireframe", "不支持的试卷图形")
                    figure = assets / (fingerprint(data)[:20] + "-figure.png")
                    fig = Figure(figsize=(4.5, 2.7), dpi=220)
                    ax = fig.add_subplot(111, projection="3d")
                    hidden = {frozenset(edge) for edge in data.get("hidden_edges", [])}
                    for a, b in data["edges"]:
                        ax.plot(
                            *zip(data["vertices"][a], data["vertices"][b]),
                            color="black",
                            linewidth=0.9,
                            linestyle="--" if frozenset((a, b)) in hidden else "-",
                        )
                    ax.view_init(*data.get("view_angles", (20, -55)))
                    ax.set_axis_off()
                    for name, point in data["vertices"].items():
                        px, py, _ = proj3d.proj_transform(*point, ax.get_proj())
                        if name in data.get("marked_points", ()):
                            ax.plot(*([value] for value in point), "ko", markersize=2.5)
                        display = re.sub(r"([A-Za-z])([0-9]+)", r"\1_{\2}", name)
                        ax.annotate(
                            "$" + display + "$",
                            (px, py),
                            xytext=data.get("label_offsets", {}).get(name, [3, 3]),
                            textcoords="offset points",
                            fontsize=11,
                        )
                    fig.savefig(figure, bbox_inches="tight", facecolor="white")
                else:
                    figure = Path(q["figure"])
                require(figure.is_file(), "图形资源缺失")
                if science_layout:
                    figures_in_md.append(figure.resolve().relative_to(path.parent.resolve()).as_posix())
                block.append(
                    Image(
                        str(figure), width=430 if science_layout else 250,
                        height=(94 if choice else 116) if science_layout else 155, kind="proportional"
                    )
                )
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
                    label=key+"．"+("" if value=="对应选项图" else value)
                    cells.append([para(label,note),Image(str(labeled[key]),width=218,height=94,kind="proportional")])
                block.append(Table([cells[i:i+2] for i in range(0,len(cells),2)],
                                   colWidths=[(A4[0]-100)/2]*2,hAlign="LEFT",
                                   style=[("VALIGN",(0,0),(-1,-1),"TOP")]))
            elif q["kind"] == "single_choice" or (science_layout and choice):
                block.append(option_grid(
                    [para(key + "．" + text) for key, text in q["options"].items()],
                    A4[0] - 2 * 44 - 12,
                    compact=science_layout,
                ))
            else:
                for key, text in q["options"].items():
                    block.append(para(key + "．" + text))
            if science_layout and not choice:
                # The opening and its figure follow each other; labeled subquestions can flow.
                story.append(KeepTogether(block))
                block = []
            block.extend(para(part["label"] + " " + part["text"]) for part in q["parts"])
            if q["kind"] == "fill_in" and "___" not in q["stem"]:
                block.append(para("答：________________。", note))
        if science_layout:
            if solutions or not choice:
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
        else:
            story.append(KeepTogether(block))
            if index + 1 < len(paper["questions"]):
                story.append(Spacer(1, 190 if q["kind"] == "constructed_response" else 8))
        md.extend([f"## {q['order']}.（{q['points']}分）", ""])
        md.extend(
            q.get("solution_paragraphs", [])
            if solutions
            else [
                q["stem"],
                *[f"![题图]({image})" for image in figures_in_md],
                *[f"![题图]({image.relative_to(path.parent).as_posix()})" for image in q.get("archive_figures",[])],
                *["%s．%s" % p for p in q["options"].items()],
                *[p["label"] + " " + p["text"] for p in q["parts"]],
            ]
        )
        md.append("")
    SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=44,
        rightMargin=44,
        topMargin=33 if science_layout else 38,
        bottomMargin=34 if science_layout else 42,
        title=paper["title"],
        author="理科模拟试卷" if science_layout else "数学模拟试卷",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    atomic_write(path.with_suffix(".md"), "\n".join(md).rstrip() + "\n")
    return path
