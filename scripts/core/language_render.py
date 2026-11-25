"""Shared typesetting for Chinese and English handouts."""
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import textsplit
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Flowable, Image, KeepTogether, Paragraph, Spacer, SimpleDocTemplate, Table
from reportlab.platypus import paragraph
from gaokao import atomic_write, require
from core.editorial_rules import LAYOUT_MODES, inline_response_only
from core.exam_policy import listening_notes, parameters

NUMBERED_BLANK = re.compile(r"(\[\d+\])[ \t]+(_{2,})")

# Extend ReportLab's CJK line-breaking set with the full-width punctuation used in these papers.
CHINESE_CLOSING = "，；：！？）》”’"
textsplit.ALL_CANNOT_START += CHINESE_CLOSING
paragraph.ALL_CANNOT_START += CHINESE_CLOSING


def marked_text(markup):
    def replace(match):
        kind, content = match.groups()
        require(re.fullmatch(r"[\u3400-\u9fff，。；、！？：]+",content),"着重号和波浪线须包裹连续中文")
        return "".join(c+f'<onDraw name="exam_{kind}"/>' for c in content)
    return re.sub(r"&lt;(dot|wave)&gt;(.*?)&lt;/\1&gt;",replace,markup)


def install_marks(canvas):
    def position():
        info=canvas._curr_tx_info
        return info["cur_x"],info["cur_y"],info["tx"]._fontsize

    def dot(canvas, kind, label):
        x,y,em=position()
        canvas.circle(x-em/2,y-1.8,.65,stroke=0,fill=1)

    def wave(canvas, kind, label):
        x,y,em=position()
        path=canvas.beginPath()
        path.moveTo(x-em,y-2)
        for i in range(1,5):
            path.lineTo(x-em+i*em/4,y-2+(.72 if i%2 else 0))
        canvas.saveState()
        canvas.setLineWidth(.45)
        canvas.drawPath(path)
        canvas.restoreState()

    canvas.setNamedCB("exam_dot",dot)
    canvas.setNamedCB("exam_wave",wave)

class ManuscriptLines(Flowable):
    """One writing row per flowable permits natural page breaks at row boundaries."""
    def __init__(self, row, columns=20, scale=True):
        super().__init__()
        self.row, self.columns = row, columns
        self.scale=scale

    def wrap(self, width, height):
        self.width = width if self.scale else min(width,360)
        self.height = min(width/self.columns, 20) + 4
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeGray(.77)
        canvas.setLineWidth(.35)
        w = self.width/self.columns
        canvas.grid([i*w for i in range(self.columns+1)], [2, self.height-2])
        if self.scale and self.row in (10,20,30,40):
            from mathgen.export import chinese_font

            canvas.setFont(chinese_font(),8)
            canvas.setFillGray(.4)
            canvas.drawString(self.width+3,2,f"{'▲' if self.row==40 else ''}{self.row*self.columns}字")
        canvas.restoreState()


def english_font(strict=False):
    import os
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    configured=os.environ.get("GAOKAO_TIMES_NEW_ROMAN")
    path=Path(configured) if configured else Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts/times.ttf"
    if not path.is_file():
        require(not strict,"新版英语卷须配置合法本机 Times New Roman 字体（GAOKAO_TIMES_NEW_ROMAN）")
        return "Times-Roman"
    font="GaokaoTimesNewRoman"
    if font not in pdfmetrics.getRegisteredFontNames():
        face=TTFont(font,str(path))
        require(b"timesnewroman" in face.face.name.lower().replace(b" ",b""),
                "英语字体文件须为 Times New Roman")
        pdfmetrics.registerFont(face)
    return font


def export_tts(listening,path):
    groups=[]
    for passage in listening.values():
        turns=[]
        for line in passage.splitlines():
            line=line.strip()
            if not line:
                continue
            match=re.fullmatch(r"([MW]):\s*(\S.*)",line)
            require(match,"听力朗读文本须提供逐行的 M: / W: 说话人")
            turns.append(f"{match[1]}: {match[2]}")
        require(turns,"听力段落为空")
        groups.append("\n".join(turns))
    require(groups,"缺听力朗读文本")
    atomic_write(path,"\n\n".join(groups)+"\n")


def render(paper, output, answers=None, *, listening=None):
    from mathgen.export import chinese_font
    from mathgen.student_pdf import LinedWritingSpace, answer_height
    from core.marking_standards import generated_only, language_template
    from core.release_checks import CARD
    mode = paper.get("layout_mode", "exam")
    require(mode in LAYOUT_MODES, "排版模式须为 practice 或 exam")
    practice = mode=="practice" and not answers and not listening
    spaces = []
    title=paper["title"]+(" · 听力朗读稿" if listening else " · 答案与评分参考" if answers else "")
    font=chinese_font()
    english=paper["subject"]=="english"
    roman=english_font(strict=bool(paper.get("release_rules"))) if english else None
    styles={
        "h1":ParagraphStyle("ExamTitle",fontName=font,fontSize=19,leading=28,alignment=1,spaceAfter=13,keepWithNext=True),
        "h2":ParagraphStyle("ExamSection",fontName=font,fontSize=13,leading=19,spaceBefore=11,spaceAfter=7,keepWithNext=True),
        "h3":ParagraphStyle("ExamItem",fontName=font,fontSize=10.7,leading=17,spaceBefore=5,spaceAfter=2,
                            wordWrap="CJK" if paper["subject"]=="chinese" else None,keepWithNext=True),
        "text":ParagraphStyle("ExamBody",fontName=font,fontSize=10.7,leading=17,spaceAfter=5,
                              wordWrap="CJK" if paper["subject"]=="chinese" else None),
    }
    flow, md=[],[]
    def put(text, kind="text", target=None):
        target = flow if target is None else target
        for line in text.splitlines():
            if not line.strip():
                continue
            if practice and CARD.search(line):
                line=CARD.sub("",line).lstrip("。，；、 ")
                if not line.strip():
                    continue
            styled=escape(line)
            styled=marked_text(styled)
            for token in ("u","strong","em","sub","sup"):
                replacement={"strong":"b","em":"i"}.get(token,token)
                styled=styled.replace(f"&lt;{token}&gt;",f"<{replacement}>").replace(f"&lt;/{token}&gt;",f"</{replacement}>")
            if english:
                styled=re.sub(r"(?<=[A-Za-z])\s*（([^（）]+)）",r" (\1)",styled)
                styled=NUMBERED_BLANK.sub(r"\1&nbsp;\2",styled)
                styled="".join(fragment if fragment.startswith("<") else re.sub(
                    r"[\x20-\x7e]+",lambda m:f'<font name="{roman}">{m[0]}</font>',fragment)
                    for fragment in re.split(r"(<[^>]+>)",styled))
            target.append(Paragraph(styled,styles[kind]))
            marker={"h1":"# ","h2":"## ","h3":"### ","text":""}[kind]
            md.append(marker+line)
    put(title,"h1")
    policy = paper.get("exam_policy")
    if listening:
        by_recording = {}
        offset = 0
        for note, section in zip(listening_notes(policy, invigilator=True).values(),
                                 parameters(policy, "listening").get("sections", []), strict=True):
            by_recording[offset] = note
            offset += section["recordings"]
        for index,(label,text) in enumerate(listening.items()):
            if note := by_recording.get(index):
                put(note.replace("监考：","录音提示："), "h2")
            put(paper["materials"][label]["title"],"h2")
            put(text)
    else:
        if answers:
            put("本答案及评分参考供阅卷使用。开放性试题允许依据合理、表达准确的不同答案。")
        else:
            put(f'满分{paper["points"]}分　考试时间{paper["minutes"]}分钟')
            if note := parameters(policy, "english_score").get("header"):
                put(note)
            put(f"本试卷共{len(paper['questions'])}题。"+("请在答题卡相应位置作答。" if mode=="exam" else ""))
        listening_instructions = listening_notes(policy)
        seen_sections, seen_materials=set(),set()
        sections={key["id"]:key for key in paper["sections"]}
        gap_lines=[]
        for q in paper["questions"]:
            material_lead = []
            if q["section"] not in seen_sections:
                keep_lead = (not answers and q["section"]!="listening"
                             and (q.get("material") not in seen_materials and q.get("material")
                                  or q["kind"]=="writing"))
                put(sections[q["section"]]["title"],"h2",material_lead if keep_lead else flow)
                if not answers and english and (q["section"].startswith("reading") or q["section"]=="gap_match"):
                    text=("阅读下列短文，从每题所给的四个选项中选出最佳选项。" if q["section"].startswith("reading") else
                          "阅读下面短文，从短文后的选项中选出可以填入空白处的最佳选项。选项中有两项为多余选项。")
                    put(text,target=material_lead if keep_lead else flow)
                seen_sections.add(q["section"])
            n=q["number"]
            if answers:
                response=answers[n]
                put(f'{n}.（{q["points"]:g}分）',"h3")
                key=response["answer"]
                put("答案："+("；".join(key) if isinstance(key,list) else str(key)))
                put(response["reasoning"])
                if not paper.get("release_rules") or not generated_only(paper["subject"],n):
                    for item in response.get("rubric",[]):
                        put(f'{item["points"]:g}分　{item["step"]}')
                if paper.get("release_rules"):
                    for line in language_template(paper["subject"],n,q["points"]):
                        put(line)
                if sample:=response.get("sample"):
                    example = [] if paper["subject"]=="english" else flow
                    put("范文","h3",example)
                    put(sample,target=example)
                    if example is not flow:
                        flow.append(KeepTogether(example))
                continue
            block=[]
            if q["section"] == "listening" and n in listening_instructions:
                put(listening_instructions[n], "text", block)
            if (name:=q.get("material")) and name not in seen_materials:
                material=paper["materials"][name]
                if q["section"]=="listening":
                    put(material["title"],"h2",block)
                    put(material["text"],"text",block)
                else:
                    lines = [line for line in material["text"].splitlines() if line.strip()]
                    first = 2 if len(lines)>1 and len(lines[0])<100 and len(lines[1])<650 else 1
                    if q["section"]=="poetry" and len(material["text"])<=650:
                        first = len(lines)
                    put(material["title"],"h2",material_lead)
                    put("\n".join(lines[:first]),"text",material_lead)
                    flow.append(KeepTogether(material_lead))
                    material_lead = []
                    put("\n".join(lines[first:]))
                for key,line in material.get("options",{}).items():
                    put(f"{key}. {line}")
                seen_materials.add(name)
            block.extend(material_lead)
            if q["kind"]=="grammar_gap":
                if practice:
                    put(f'{n}. ____________________', "text", gap_lines)
                    if len(gap_lines)==10:
                        flow.append(Table(list(zip(gap_lines[:5],gap_lines[5:])),colWidths=(235,235)))
                continue
            prompt = q["stem"].splitlines()
            english_writing = practice and paper["subject"]=="english" and q["kind"]=="writing"
            letter = english_writing and q["section"]=="application" and any(t.startswith("Dear ") for t in prompt)
            continuation = english_writing and q["section"]=="continuation" and len(prompt)>=3 and all(
                t and t[0].isascii() and t[0].isalpha() for t in prompt[-2:])
            if letter:
                cut = next(i for i,t in enumerate(prompt) if t.startswith("Dear "))
                main = prompt[:cut+1]
            elif continuation:
                main = prompt[:-2]
            else:
                main = prompt
            main=[re.sub(r"^第\s*\d+\s*(?:空|题)[，：:。 ]*", "", t) for t in main] if english else main
            if english and q["kind"] in ("gap_match","single_choice") and (
                    q["section"]=="cloze" or (q["kind"]=="gap_match" and re.match(r"选择能填入短文第",main[0]))):
                main=[""]
            if not english and q.get("options") and not re.search(r"（[\s　]*）[。]?$",main[-1]):
                main[-1]+="（　　）"
            score="" if english and q["kind"]!="writing" else f'（{q["points"]:g}分）'
            put(f'{n}.{score}'+"\n".join(main), "h3" if q.get("options") else "text",block)
            for figure in q.get("archive_figures",[]):
                block.append(Image(str(figure),width=340,height=145,kind="proportional"))
                md.append(f"![题图]({figure.relative_to(output.parent).as_posix()})")
            options=list(q.get("options",{}).items())
            if paper["subject"]=="english" and q["section"]=="cloze" and options:
                put("　　 ".join(f"{k}. {v}" for k,v in options),target=block)
            elif paper["subject"]=="english" and all(len(v)<38 for _,v in options):
                for i in range(0,len(options),2):
                    put("　　".join(f"{k}. {v}" for k,v in options[i:i+2]),target=block)
            else:
                for key,line in options:
                    put(f"{key}. {line}",target=block)
            essay_grid = practice and paper["subject"] == "chinese" and q["section"] == "essay"
            if practice and not english and n==20 and "字" in q["stem"]:
                block.extend(ManuscriptLines(row,scale=False) for row in (1,2))
            elif practice and not english and n==13:
                for part in (1,2):
                    put(f"（{part}）",target=block)
                    block.append(LinedWritingSpace(n,2.4,spaces))
            elif practice and not english and n==10:
                block.append(LinedWritingSpace(n,.9,spaces))
            elif practice and not essay_grid and not continuation and ((height := answer_height(q)) or (
                    not english and n in (4,5,8,9,14,16,18,21))):
                block.append(LinedWritingSpace(n, 6.3 if letter else height or 3.0, spaces))
            if letter:
                put("\n".join(prompt[cut+1:]),target=block)
            flow.append(KeepTogether(block))
            if continuation:
                for opening in prompt[-2:]:
                    paragraph=[]
                    put(opening,target=paragraph)
                    paragraph.append(LinedWritingSpace(n,8.5,spaces))
                    flow.append(KeepTogether(paragraph))
            if essay_grid:
                flow.extend(ManuscriptLines(row) for row in range(1,51))
            if q["kind"] not in ("single_choice","multiple_choice","gap_match","grammar_gap"):
                flow.append(Spacer(1,9))
    def footer(canvas,doc):
        install_marks(canvas)
    from functools import partial
    from core.exam_pages import ExamPages

    SimpleDocTemplate(str(output.with_suffix(".pdf")),pagesize=A4,topMargin=39,bottomMargin=44,
                      leftMargin=49,rightMargin=49,title=title).build(
                          flow,onFirstPage=footer,onLaterPages=footer,canvasmaker=partial(ExamPages,footer_font=font))
    atomic_write(output.with_suffix(".md"),"\n\n".join(md)+"\n")


def export_docx(markdown, output):
    from io import BytesIO
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_ROW_HEIGHT_RULE
    from docx.shared import Cm, Pt, RGBColor
    from gaokao import read_json, relative_path
    from core.science_dna import STANDARD_LAYOUT
    doc=Document()
    section=doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin=section.right_margin=Cm(1.8)
    section.top_margin=section.bottom_margin=Cm(1.8)
    for name,size in (("Normal",11),("Title",19),("Heading 1",14),("Heading 2",11)):
        style=doc.styles[name]
        style.font.name="Times New Roman"
        style.font.size=Pt(size)
        style.font.color.rgb=RGBColor.from_string("181818")
        style.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"),"宋体")
        style.paragraph_format.space_after=Pt(4)
        style.paragraph_format.widow_control=True
    footer=section.footer.paragraphs[0]
    footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
    page=OxmlElement("w:fldSimple")
    page.set(qn("w:instr"),"PAGE")
    footer._p.append(page)
    prompts={}
    calculation_spaces={}
    grid=set()
    keep_with_options=set()
    source=Path(markdown)
    packet=source.parent/"blind-packet.json"
    math_packet=source.parent/"student-text.json"
    paper=(read_json(packet)["paper"] if packet.is_file() else
           read_json(math_packet) if math_packet.is_file() else {})
    formula_paper=paper.get("subject") in STANDARD_LAYOUT or paper.get("subject")=="math"
    math_student=paper.get("subject")=="math" and source.name=="paper.md"
    if paper.get("subject")=="math":
        for style_name in ("Title","Heading 1","Heading 2"):
            props=doc.styles[style_name].element.get_or_add_pPr()
            for border in props.findall(qn("w:pBdr")):
                props.remove(border)
            doc.styles[style_name].paragraph_format.space_before=Pt(7)
    markers=r"</?(?:u|em|strong|sub|sup|dot|wave)>"
    if formula_paper:
        from PIL import Image as PillowImage
        from mathgen.student_pdf import answer_height, formula_image, normalise_tex

        markers+=r"|\\\(.*?\\\)"
    inline_markup=re.compile(f"({markers})")
    if source.name=="paper.md" and paper:
        if paper.get("layout_mode")=="practice":
            for q in paper["questions"]:
                if formula_paper:
                    if height := answer_height(q):
                        if q.get("parts"):
                            last=q["parts"][-1]
                            label=last["label"]+" "+last["text"].splitlines()[-1]
                        else:
                            label=q["stem"].splitlines()[-1]
                        calculation_spaces[label]=height
                    continue
                first,*rest=q["stem"].strip().splitlines()
                last=(rest[-1] if rest else f'{q["number"]}.（{q["points"]:g}分）{first}').strip()
                if q.get("options"):
                    keep_with_options.add(last)
                if q["section"]=="essay":
                    grid.add(last)
                elif q["section"]=="application" and any(line.startswith("Dear ") for line in rest):
                    prompts[next(line for line in rest if line.startswith("Dear "))]=8
                elif q["section"]=="continuation" and len(rest)>=2:
                    prompts.update({line:8 for line in rest[-2:]})
                elif q["kind"]=="response" and not inline_response_only(q):
                    prompts[last]=4
    lines = [line for line in source.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    short_example = False
    table_until=-1
    in_question=False
    for index, line in enumerate(lines):
        if index<table_until:
            continue
        lead, sep, text=line.partition(" ")
        heading=sep and lead in ("#","##","###")
        content=text if heading else line
        following = lines[index+1] if index+1<len(lines) else ""
        if heading:
            in_question=math_student and bool(re.match(r"^\d+[.．]",content))
        keep_math_group=in_question and following and not following.startswith("#")
        if formula_paper and content.startswith("| ") and re.fullmatch(r"\|(?:\s*---\s*\|)+",following):
            def cells(text):
                return [part.strip().replace(r"\|","|") for part in re.split(r"(?<!\\)\|",text)[1:-1]]

            data=[cells(content)]
            table_until=index+2
            while table_until<len(lines) and lines[table_until].startswith("| "):
                data.append(cells(lines[table_until]))
                table_until+=1
            native=doc.add_table(rows=len(data),cols=len(data[0]))
            borders=OxmlElement("w:tblBorders")
            for edge in ("top","bottom"):
                line_element=OxmlElement("w:"+edge)
                line_element.set(qn("w:val"),"single")
                line_element.set(qn("w:sz"),"8")
                borders.append(line_element)
            native._tbl.tblPr.append(borders)
            native.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
            for r,values in enumerate(data):
                for c,value in enumerate(values):
                    cell=native.cell(r,c)
                    cell.text=value
                    if r==0:
                        border=OxmlElement("w:tcBorders")
                        bottom=OxmlElement("w:bottom")
                        bottom.set(qn("w:val"),"single")
                        bottom.set(qn("w:sz"),"4")
                        border.append(bottom)
                        cell._tc.get_or_add_tcPr().append(border)
            continue
        if formula_paper and (image := re.fullmatch(r"!\[题图\]\(([^)]+)\)",content)):
            path=relative_path(source.parent,image[1])
            with PillowImage.open(path) as picture:
                w,h=picture.size
            para=doc.add_paragraph()
            para.alignment=WD_ALIGN_PARAGRAPH.CENTER
            para.add_run().add_picture(str(path),width=Cm(min(16.4,4.9*w/h)))
            if keep_math_group:
                para.paragraph_format.keep_with_next=True
            continue
        if heading:
            short_example = (content=="范文" and source.name=="solutions.md"
                             and paper.get("subject")=="english")
        para=doc.add_paragraph(style={"#":"Title","##":"Heading 1","###":"Heading 2"}[lead] if heading else "Normal")
        if heading and lead=="#":para.alignment=WD_ALIGN_PARAGRAPH.CENTER
        active=set()
        printable = NUMBERED_BLANK.sub(r"\1" + "\N{NO-BREAK SPACE}" + r"\2",content)
        for fragment in inline_markup.split(printable):
            if re.fullmatch(r"</?(?:u|em|strong|sub|sup|dot|wave)>",fragment):
                tag=fragment.strip("</>")
                if fragment.startswith("</"):active.discard(tag)
                else:active.add(tag)
            elif formula_paper and fragment.startswith(r"\(") and fragment.endswith(r"\)"):
                png=BytesIO()
                formula=normalise_tex(fragment[2:-2].replace(r"\dfrac",r"\frac").replace(r"\tfrac",r"\frac"))
                formula_image(formula,png)
                png.seek(0)
                with PillowImage.open(png) as picture:
                    width=picture.width
                png.seek(0)
                para.add_run().add_picture(png,width=Pt(min(width*72/240,452)))
            else:
                run=para.add_run(fragment)
                run.underline="u" in active
                if "dot" in active or "wave" in active:
                    from docx.enum.text import WD_UNDERLINE

                    run.underline=WD_UNDERLINE.DOTTED if "dot" in active else WD_UNDERLINE.WAVY
                run.italic="em" in active
                run.bold=True if "strong" in active else None
                run.font.subscript="sub" in active
                run.font.superscript="sup" in active
        line_count=prompts.get(content,0)
        if height := calculation_spaces.get(content):
            para.paragraph_format.keep_with_next=True
            blank=doc.add_paragraph()
            blank.paragraph_format.line_spacing=Cm(height)
            blank.paragraph_format.space_after=Pt(0)
        option_chain = re.match(r"^[A-G](?:\. |．)",content) and re.match(r"^[A-G](?:\. |．)",following)
        passage_label = re.fullmatch(r"材料[一二三][:：]?|听第\s*\d+\s*段材料.*",content)
        if line_count or keep_math_group or content in keep_with_options or option_chain or passage_label or (
                short_example and following and not following.startswith("#")):
            para.paragraph_format.keep_with_next=True
        if formula_paper and following.startswith("![题图]("):
            para.paragraph_format.keep_with_next=True
        if short_example:
            para.paragraph_format.keep_together=True
        for idx in range(line_count):
            p=doc.add_paragraph()
            p.paragraph_format.space_after=Pt(0)
            p.paragraph_format.line_spacing=Pt(21)
            p.paragraph_format.keep_with_next=not formula_paper and idx+1 < line_count
            border=OxmlElement("w:pBdr")
            bottom=OxmlElement("w:bottom")
            bottom.set(qn("w:val"),"single")
            bottom.set(qn("w:sz"),"3")
            border.append(bottom)
            p._p.get_or_add_pPr().append(border)
        if content in grid:
            table=doc.add_table(rows=50,cols=20)
            table.autofit=False
            borders=OxmlElement("w:tblBorders")
            for side in ("top","left","bottom","right","insideH","insideV"):
                edge=OxmlElement("w:"+side)
                for key,val in (("val","single"),("sz","3"),("color","B0B0B0")):edge.set(qn("w:"+key),val)
                borders.append(edge)
            table._tbl.tblPr.append(borders)
            for idx,row in enumerate(table.rows,1):
                row.height=Cm(.63)
                row.height_rule=WD_ROW_HEIGHT_RULE.EXACTLY
                row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
                if idx in (10,20,30,40):
                    row.cells[-1].paragraphs[0].add_run(f"{'▲' if idx==40 else ''}{idx*20}字").font.size=Pt(7)
    doc.save(output)
