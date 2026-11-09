"""Layer 3: render reviewed school-language text; internal specifications are forbidden here."""

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
from .export import chinese_font, MathParagraph, formatted_plain

VERSION = "student-layout-v3"
MATH_RASTER = MathTextParser("agg")


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
    body = ParagraphStyle(
        "student-body",
        fontName=font,
        fontSize=11.5,
        leading=23,
        spaceAfter=9,
        wordWrap="CJK",
    )
    heading = ParagraphStyle(
        "student-heading",
        parent=body,
        fontSize=12,
        leading=22,
        spaceBefore=12,
        spaceAfter=8,
        keepWithNext=True,
    )
    title = ParagraphStyle(
        "student-title",
        parent=body,
        fontSize=19,
        leading=29,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    note = ParagraphStyle(
        "student-note", parent=body, fontSize=10, leading=18, spaceAfter=8
    )

    def para(text, style=body):
        chunks = []
        at = 0
        for m in re.finditer(r"\\\((.*?)\\\)", text, re.S):
            chunks.append(formatted_plain(text[at : m.start()]))
            formula = normalise_tex(m.group(1))
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
                f'<img src="{filename.as_posix()}" width="{w * scale:.2f}" height="{h * scale:.2f}" valign="middle"/>'
            )
            at = m.end()
        chunks.append(formatted_plain(text[at:]))
        return MathParagraph("".join(chunks).replace("\n", "<br/>"), style)

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
        if any(q["kind"] == "constructed_response" for q in paper["questions"]):
            instruction += "解答题须写出必要的文字说明、证明过程或演算步骤。"
        story.append(para(instruction, note))
    previous = None
    section_titles = {
        "single_choice": "单项选择题",
        "multiple_choice": "多项选择题（全部选对得满分，部分选对得部分分，有选错得0分）",
        "fill_in": "填空题",
        "constructed_response": "解答题",
    }
    section_number = 0
    md = ["# " + paper["title"], ""]
    for q in paper["questions"]:
        require(
            not any(k in q for k in ("math_spec", "tasks", "design", "solver_record")),
            "排版输入混入内部数据",
        )
        if (
            q["kind"] == "constructed_response"
            and previous == q["kind"]
            and not solutions
        ):
            story.append(PageBreak())
        section = None
        if q["kind"] != previous and not solutions:
            section_number += 1
            prefix = (
                "一二三四"[section_number - 1] + "、" if section_number <= 4 else ""
            )
            section = para(prefix + section_titles[q["kind"]], heading)
            previous = q["kind"]
        block = ([section] if section else []) + [
            para(f"{q['order']}.（{q['points']}分）", heading)
        ]
        if solutions:
            block.extend(para(p) for p in q["solution_paragraphs"])
        else:
            block.append(para(q["stem"]))
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
                    ax.view_init(20, -55)
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
                block.append(
                    Image(str(figure), width=250, height=155, kind="proportional")
                )
            if q["kind"] == "single_choice":
                block.append(
                    Table(
                        [
                            [
                                para(key + "．" + text)
                                for key, text in q["options"].items()
                            ]
                        ],
                        colWidths=[122] * 4,
                        hAlign="LEFT",
                    )
                )
            else:
                for key, text in q["options"].items():
                    block.append(para(key + "．" + text))
            for part in q["parts"]:
                block.append(para(part["label"] + " " + part["text"]))
            if q["kind"] == "fill_in" and "___" not in q["stem"]:
                block.append(para("答：________________。", note))
        if solutions:
            # Keep each solution together when it fits a page; long solutions may split.
            story.append(KeepTogether(block))
            story.append(Spacer(1, 12))
        else:
            story.append(KeepTogether(block))
            story.append(Spacer(1, 190 if q["kind"] == "constructed_response" else 8))
        md.extend([f"## {q['order']}.（{q['points']}分）", ""])
        md.extend(
            q.get("solution_paragraphs", [])
            if solutions
            else [
                q["stem"],
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
        topMargin=38,
        bottomMargin=42,
        title=paper["title"],
        author="数学模拟试卷",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    atomic_write(path.with_suffix(".md"), "\n".join(md).rstrip() + "\n")
    return path
