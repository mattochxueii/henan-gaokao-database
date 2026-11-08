"""Print-ready Chinese PDF and editable Markdown, using one verified run."""

import html
import os
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    KeepTogether,
    PageBreak,
)
from reportlab.lib.pagesizes import A4
from matplotlib.mathtext import math_to_image
from matplotlib.font_manager import FontProperties
from matplotlib.figure import Figure
from PIL import Image as PILImage
from gaokao import atomic_write
from analysis_db import fingerprint
from .quality import assert_fresh


class MathParagraph(Paragraph):
    """Handle ReportLab CJK inline-image wrapping without altering its dependency."""

    def wrap(self, availWidth, availHeight):
        try:
            return super().wrap(availWidth, availHeight)
        except TypeError as error:
            if "ord() expected a character" not in str(error):
                raise
            # CJK splitter calls ord('') on an image fragment that crosses a line.
            # Standard splitter accounts for image widths and splits long CJK words.
            from copy import copy

            self.style = copy(self.style)
            self.style.wordWrap = None
            return super().wrap(availWidth, availHeight)


SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉ₙₖⱼᵢ₊₋", "0123456789nkji+-")
SUPERSCRIPTS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻", "0123456789n+-")


def formatted_plain(text):
    # SimSun lacks U+2212 in this environment; retaining it silently drops minus signs.
    value = html.escape(text.replace("−", "-"))
    value = re.sub(
        r"[₀₁₂₃₄₅₆₇₈₉ₙₖⱼᵢ₊₋]+",
        lambda m: "<sub>" + m.group().translate(SUBSCRIPTS) + "</sub>",
        value,
    )
    return re.sub(
        r"[⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻]+",
        lambda m: "<super>" + m.group().translate(SUPERSCRIPTS) + "</super>",
        value,
    )


ANSWER_LABELS = {
    "seq_interlace": ["所求和"],
    "seq_reciprocal": ["通项aₙ", "所求有限和"],
    "seq_telescope": ["通项uₙ", "Tₙ", "最小正整数n"],
    "seq_alternating": ["通项aₙ", "所求前缀和"],
    "seq_optimize": ["最小值", "取等时aₖ"],
    "deriv_tangent": ["A", "B"],
    "deriv_logquad": ["最大值点x", "最大值", "c范围的含等号下界"],
    "deriv_cubic": ["第一分界c", "第二分界c"],
    "deriv_logbound": ["最优常数c"],
    "deriv_logroots": [
        "c范围的开下界",
        "c范围的开上界",
        "三根乘积",
        "附加条件下c",
        "x₁",
        "x₂",
        "x₃",
    ],
    "tetrahedron": ["点面距离关于h的表达式", "指定角下h", "指定角下的距离"],
    "ellipse_conjugate": [
        "不变面积",
        "PQ最小长度",
        "PQ最大长度",
        "中点轨迹横半轴平方",
        "中点轨迹纵半轴平方",
    ],
    "urn_mixture": ["首次红球概率", "首次红后选乙概率", "两次均红概率", "协方差"],
    "geometry_assertions": ["A项真值", "B项真值", "C项真值", "D项真值"],
    "logquad_assertions": ["A项真值", "B项真值", "C项真值", "D项真值"],
}


def chinese_font():
    candidates = [
        os.environ.get("HENAN_MATH_FONT", ""),
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if path and Path(path).is_file():
            try:
                pdfmetrics.registerFont(TTFont("HanMath", path, subfontIndex=0))
                return "HanMath"
            except Exception:
                continue
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


def figure_for(q, folder):
    family = q.get("family")
    if family is None and q.get("problem"):
        geometry = next(
            (t for t in q["problem"].get("tasks", []) if t.get("plane_points")), None
        )
        if geometry:
            fig = Figure(figsize=(4, 2.5), dpi=160)
            ax = fig.add_subplot(111, projection="3d")
            points = geometry["plane_points"]
            for label, point in zip("ABC", points):
                ax.text(*point, label)
            for i, j in ((0, 1), (1, 2), (2, 0)):
                ax.plot(*zip(points[i], points[j]), color="#213547")
            if geometry.get("point") is not None:
                ax.scatter(*geometry["point"], color="#213547")
                ax.text(*geometry["point"], "D")
            ax.set_axis_off()
            path = folder / (q["id"].replace(":", "-") + "-figure.png")
            fig.savefig(path, bbox_inches="tight", facecolor="white")
            return path
    if family not in ("tetrahedron", "ellipse_conjugate"):
        return None
    p = q["parameters"]
    a, b = p["a"], p["b"]
    fig = Figure(figsize=(4, 2.5), dpi=160)
    if family == "tetrahedron":
        ax = fig.add_subplot(111, projection="3d")
        vertices = {"O": (0, 0, 0), "A": (a, 0, 0), "B": (0, a, 0), "C": (0, 0, a)}
        for name, xyz in vertices.items():
            ax.text(*xyz, name)
        for start, end in [
            ("O", "A"),
            ("O", "B"),
            ("O", "C"),
            ("A", "B"),
            ("A", "C"),
            ("B", "C"),
        ]:
            pairs = list(zip(vertices[start], vertices[end]))
            ax.plot(*pairs, color="#213547", linewidth=1)
        ax.set_axis_off()
        ax.view_init(elev=22, azim=36)
    else:
        import numpy as np

        t = np.linspace(0, 2 * np.pi, 300)
        s = 0.6
        ax = fig.add_subplot(111)
        ax.plot(a * np.cos(t), b * np.sin(t), color="#213547")
        P = (a * np.cos(s), b * np.sin(s))
        Q = (-a * np.sin(s), b * np.cos(s))
        ax.plot([0, P[0], Q[0], 0], [0, P[1], Q[1], 0], color="#487f92")
        for name, point in [("O", (0, 0)), ("P", P), ("Q", Q)]:
            ax.annotate(name, point)
        ax.set_aspect("equal")
        ax.axis("off")
    path = folder / (q["id"].replace(":", "-") + "-figure.png")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    return path


def export_run(run, output):
    font = chinese_font()
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    normal = ParagraphStyle(
        "body", fontName=font, fontSize=11, leading=20, spaceAfter=6, wordWrap="CJK"
    )
    title = ParagraphStyle(
        "title",
        parent=normal,
        fontSize=19,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=16,
    )
    heading = ParagraphStyle(
        "heading", parent=normal, fontSize=13, leading=22, spaceBefore=10, spaceAfter=6
    )
    small = ParagraphStyle(
        "small",
        parent=normal,
        fontSize=9,
        leading=15,
        textColor=colors.HexColor("#425269"),
    )

    def paragraph(text, style=normal):
        chunks = []
        last = 0
        for match in re.finditer(r"\\\((.*?)\\\)", text, re.S):
            chunks.append(formatted_plain(text[last : match.start()]))
            formula = (
                match.group(1)
                .replace(r"\lor", r"\vee")
                .replace(r"\land", r"\wedge")
                .replace(r"\bmod", r"\mathrm{mod}\ ")
            )
            target = assets / (fingerprint(formula)[:18] + ".png")
            if not target.exists():
                math_to_image(
                    "$" + formula + "$",
                    target,
                    prop=FontProperties(size=12),
                    dpi=220,
                    format="png",
                    color="black",
                )
            with PILImage.open(target) as picture:
                width, height = picture.size
            scale = min(72 / 220, 460 / width)
            chunks.append(
                f'<img src="{target.as_posix()}" width="{width * scale:.2f}" height="{height * scale:.2f}" valign="middle"/>'
            )
            last = match.end()
        chunks.append(formatted_plain(text[last:]))
        return MathParagraph("".join(chunks).replace("\n", "<br/>"), style)

    def footer(canvas, doc):
        canvas.setFont(font, 8)
        mode_label = (
            "宿主AI动态命题" if run.get("generation_mode") == "ai" else "模板备用练习"
        )
        canvas.drawString(45, 24, "河南数学研究 · " + mode_label + " · 审阅用")
        canvas.drawRightString(A4[0] - 45, 24, str(doc.page))

    mode_label = (
        "AI动态命题" if run.get("generation_mode") == "ai" else "template模板备用模式"
    )
    exam = [
        paragraph(run["blueprint"]["title"], title),
        paragraph(
            f"共{len(run['questions'])}题，满分{run['structure']['points']}分。", small
        ),
        paragraph(
            mode_label + "。研究审阅版，尚未评定高质量高考模拟卷。2027结构为模拟设定。",
            small,
        ),
    ]
    if run["blueprint"]["mode"] == "full":
        exam.append(
            paragraph(
                "时间120分钟。多选题全对6分，仅选对1项2分、2项4分，错选0分。此部分评分为模拟约定。",
                small,
            )
        )
    answers = [paragraph(run["blueprint"]["title"] + "\n答案与质量报告", title)]
    md_exam = ["# " + run["blueprint"]["title"], ""]
    md_answers = ["# 答案与解析", ""]
    for q, v, event in zip(
        run["questions"],
        run["verifications"],
        [e for e in run["events"] if e["passed"]],
    ):
        assert_fresh(q, v)
        label = f"{q['order']}.（{q['points']}分）"
        question_label = label
        block = [paragraph(label, heading), paragraph(q["stem"])]
        md_exam.extend(["## " + label, "", q["stem"], ""])
        for key, option in (q["options"] or {}).items():
            block.append(paragraph(key + ". " + option["text"]))
            md_exam.extend([key + ". " + option["text"], ""])
        figure = figure_for(q, assets)
        if figure:
            block.append(Image(str(figure), width=240, height=150, kind="proportional"))
            block.append(
                paragraph("构型示意。空间图以h=a绘制，实际条件以题干为准。", small)
                if q.get("family") == "tetrahedron"
                else paragraph(
                    "由题设坐标绘制，比例仅供示意。"
                    if q.get("generation", {}).get("mode") == "ai"
                    else "参数构型示意，t遍历实数。",
                    small,
                )
            )
            md_exam.extend(["![构型示意](assets/" + figure.name + ")", ""])
        if q["kind"] == "constructed_response":
            block.extend(
                [
                    paragraph("答题区域（可另附纸）", small),
                    Spacer(1, 160 if run["blueprint"]["mode"] == "full" else 95),
                ]
            )
        exam.append(KeepTogether(block))
        if q["order"] < len(run["questions"]):
            exam.append(Spacer(1, 55 if q["kind"] == "constructed_response" else 10))
        answerblock = [
            paragraph(
                label
                + f" {q['module']} · 设计难度{q.get('difficulty_review', {}).get('estimate', q['difficulty'])}/5（待实测）",
                heading,
            )
        ]
        if q.get("generation", {}).get("mode") == "ai":
            answerblock.extend(
                [
                    paragraph(
                        "知识点：" + "、".join(q["design"]["knowledge_combination"]),
                        small,
                    ),
                    paragraph("命题设计与目的：" + q["design"]["structure"], small),
                    paragraph("推理路径：" + str(q["design"]["reasoning_path"]), small),
                ]
            )
        if v["option_key"]:
            answerblock.append(paragraph("参考选项 " + v["option_key"]))
        for index, value in enumerate(v["values_latex"], 1):
            labels = ANSWER_LABELS.get(q.get("family"), [])
            label = labels[index - 1] if index <= len(labels) else f"结果{index}"
            answerblock.append(paragraph(label + " " + r"\(" + value + r"\)"))
        answerblock.extend(paragraph(step) for step in v["steps"])
        answerblock.extend(
            [
                paragraph("验证状态 " + v["status"], small),
                paragraph(v["remaining_uncertainty"], small),
                paragraph(
                    (
                        "结构比较记录 "
                        if run.get("generation_mode") == "ai"
                        else "题面相似度最大值 "
                    )
                    + str(event["quality"]["duplicate"]["closest"]["score"])
                    + "。"
                    + q["difficulty_basis"],
                    small,
                ),
            ]
        )
        answers.append(KeepTogether(answerblock))
        md_answers.extend(
            [
                "## " + question_label,
                "",
                "选项 " + str(v["option_key"] or "见下述结果"),
                "",
            ]
        )
        for index, value in enumerate(v["values_latex"]):
            labels = ANSWER_LABELS.get(q.get("family"), [])
            label = labels[index] if index < len(labels) else f"结果{index + 1}"
            md_answers.append(label + " " + r"\(" + value + r"\)" + "\n")
        md_answers.extend(v["steps"] + ["", v["remaining_uncertainty"], ""])
    answers.extend([PageBreak(), paragraph("命题质量与使用边界", heading)])
    for text in run["limitations"] + run["blueprint"]["simulation_settings"]:
        answers.append(paragraph(text))
    answers.append(
        paragraph(
            "每道题的生成种子、草稿、独立求解结果、验证校验值和重试记录见run.json。修改题面后必须重新验证。"
        )
    )
    outputs = {}
    for name, story in (("paper", exam), ("solutions", answers)):
        path = output / (name + ".pdf")
        SimpleDocTemplate(
            str(path),
            pagesize=A4,
            rightMargin=45,
            leftMargin=45,
            topMargin=40,
            bottomMargin=42,
            title=run["blueprint"]["title"],
            author="河南数学命题研究原型",
        ).build(story, onFirstPage=footer, onLaterPages=footer)
        outputs[name + "_pdf"] = path.name
    atomic_write(output / "paper.md", "\n".join(md_exam) + "\n")
    atomic_write(output / "solutions.md", "\n".join(md_answers) + "\n")
    outputs.update(
        paper_editable="paper.md",
        solutions_editable="solutions.md",
        word_status="未生成DOCX。本环境未找到LibreOffice，无法完成文档技能要求的渲染核验。",
    )
    return outputs
