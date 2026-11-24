"""Shared typesetting for Chinese and English handouts."""
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import textsplit
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Flowable, Image, KeepTogether, Paragraph, Spacer, SimpleDocTemplate
from reportlab.platypus import paragraph
from gaokao import atomic_write, require
from core.editorial_rules import LAYOUT_MODES, inline_response_only
from core.exam_policy import listening_notes, parameters

NUMBERED_BLANK = re.compile(r"(\[\d+\])[ \t]+(_{2,})")

# Extend ReportLab's CJK line-breaking set with the full-width punctuation used in these papers.
CHINESE_CLOSING = "，；：！？）》”’"
textsplit.ALL_CANNOT_START += CHINESE_CLOSING
paragraph.ALL_CANNOT_START += CHINESE_CLOSING

class ManuscriptLines(Flowable):
    """One writing row per flowable permits natural page breaks at row boundaries."""
    def __init__(self, row, columns=25):
        super().__init__()
        self.row, self.columns = row, columns

    def wrap(self, width, height):
        self.width = width
        self.height = min(width/self.columns, 20) + 4
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeGray(.77)
        canvas.setLineWidth(.35)
        w = self.width/self.columns
        canvas.grid([i*w for i in range(self.columns+1)], [2, self.height-2])
        canvas.restoreState()


def render(paper, output, answers=None, *, listening=None):
    from mathgen.export import chinese_font
    from mathgen.student_pdf import AnswerSpace, answer_height
    mode = paper.get("layout_mode", "practice")
    require(mode in LAYOUT_MODES, "排版模式须为 practice 或 exam")
    practice = mode=="practice" and not answers and not listening
    spaces = []
    title=paper["title"]+(" · 听力朗读稿" if listening else " · 答案与评分参考" if answers else "")
    font=chinese_font()
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
            styled=escape(line)
            for token in ("u","strong","em","sub","sup"):
                replacement={"strong":"b","em":"i"}.get(token,token)
                styled=styled.replace(f"&lt;{token}&gt;",f"<{replacement}>").replace(f"&lt;/{token}&gt;",f"</{replacement}>")
            if paper["subject"]=="english":
                styled=NUMBERED_BLANK.sub(r"\1&nbsp;\2",styled)
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
                put(note, "h2")
            put(paper["materials"][label]["title"],"h2")
            put(text)
    else:
        if answers:
            put("项目参考评分。开放性试题允许依据合理、表达准确的不同答案。")
        else:
            put(f'满分{paper["points"]}分　考试时间{paper["minutes"]}分钟')
            if note := parameters(policy, "english_score").get("header"):
                put(note)
        listening_instructions = listening_notes(policy)
        seen_sections, seen_materials=set(),set()
        sections={key["id"]:key for key in paper["sections"]}
        for q in paper["questions"]:
            material_lead = []
            if q["section"] not in seen_sections:
                keep_lead = (not answers and q["section"]!="listening"
                             and (q.get("material") not in seen_materials and q.get("material")
                                  or q["kind"]=="writing"))
                put(sections[q["section"]]["title"],"h2",material_lead if keep_lead else flow)
                seen_sections.add(q["section"])
            n=q["number"]
            if answers:
                response=answers[n]
                put(f'{n}.（{q["points"]:g}分）',"h3")
                key=response["answer"]
                put("答案："+("；".join(key) if isinstance(key,list) else str(key)))
                put(response["reasoning"])
                for item in response.get("rubric",[]):
                    put(f'{item["points"]:g}分　{item["step"]}')
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
                put(f'{n}. ____________________', "text")
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
            put(f'{n}.（{q["points"]:g}分）'+"\n".join(main), "h3" if q.get("options") else "text",block)
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
            if practice and not essay_grid and not continuation and (height := answer_height(q)):
                block.append(AnswerSpace(n, 6.3 if letter else height, spaces))
            if letter:
                put("\n".join(prompt[cut+1:]),target=block)
            flow.append(KeepTogether(block))
            if continuation:
                for opening in prompt[-2:]:
                    paragraph=[]
                    put(opening,target=paragraph)
                    paragraph.append(AnswerSpace(n,8.5,spaces))
                    flow.append(KeepTogether(paragraph))
            if essay_grid:
                flow.extend(ManuscriptLines(row) for row in range(36))
            if q["kind"] not in ("single_choice","multiple_choice","gap_match","grammar_gap"):
                flow.append(Spacer(1,9))
    def footer(canvas,doc):
        canvas.setFont(font,9)
        canvas.drawCentredString(A4[0]/2,23,f"第 {doc.page} 页")
    SimpleDocTemplate(str(output.with_suffix(".pdf")),pagesize=A4,topMargin=39,bottomMargin=44,
                      leftMargin=49,rightMargin=49,title=title).build(flow,onFirstPage=footer,onLaterPages=footer)
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
    grid=set()
    keep_with_options=set()
    source=Path(markdown)
    packet=source.parent/"blind-packet.json"
    paper=read_json(packet)["paper"] if packet.is_file() else {}
    science=paper.get("subject") in STANDARD_LAYOUT
    markers=r"</?(?:u|em|strong|sub|sup)>"
    if science:
        from PIL import Image as PillowImage
        from mathgen.student_pdf import answer_height, formula_image, normalise_tex

        markers+=r"|\\\(.*?\\\)"
    inline_markup=re.compile(f"({markers})")
    if source.name=="paper.md" and paper:
        if paper.get("layout_mode")=="practice":
            for q in paper["questions"]:
                if science:
                    if q.get("parts") and (height := answer_height(q)):
                        last=q["parts"][-1]
                        prompts[last["label"]+" "+last["text"].splitlines()[-1]]=round(height/.67)
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
    for index, line in enumerate(lines):
        lead, sep, text=line.partition(" ")
        heading=sep and lead in ("#","##","###")
        content=text if heading else line
        following = lines[index+1] if index+1<len(lines) else ""
        if science and (image := re.fullmatch(r"!\[题图\]\(([^)]+)\)",content)):
            path=relative_path(source.parent,image[1])
            with PillowImage.open(path) as picture:
                w,h=picture.size
            para=doc.add_paragraph()
            para.alignment=WD_ALIGN_PARAGRAPH.CENTER
            para.add_run().add_picture(str(path),width=Cm(min(16.4,4.9*w/h)))
            continue
        if heading:
            short_example = (content=="范文" and source.name=="solutions.md"
                             and paper.get("subject")=="english")
        para=doc.add_paragraph(style={"#":"Title","##":"Heading 1","###":"Heading 2"}[lead] if heading else "Normal")
        if heading and lead=="#":para.alignment=WD_ALIGN_PARAGRAPH.CENTER
        active=set()
        printable = NUMBERED_BLANK.sub(r"\1" + "\N{NO-BREAK SPACE}" + r"\2",content)
        for fragment in inline_markup.split(printable):
            if re.fullmatch(r"</?(?:u|em|strong|sub|sup)>",fragment):
                tag=fragment.strip("</>")
                if fragment.startswith("</"):active.discard(tag)
                else:active.add(tag)
            elif science and fragment.startswith(r"\(") and fragment.endswith(r"\)"):
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
                run.italic="em" in active
                run.bold=True if "strong" in active else None
                run.font.subscript="sub" in active
                run.font.superscript="sup" in active
        line_count=prompts.get(content,0)
        option_chain = re.match(r"^[A-G](?:\. |．)",content) and re.match(r"^[A-G](?:\. |．)",following)
        passage_label = re.fullmatch(r"材料[一二三][:：]?|听第\s*\d+\s*段材料.*",content)
        if line_count or content in keep_with_options or option_chain or passage_label or (
                short_example and following and not following.startswith("#")):
            para.paragraph_format.keep_with_next=True
        if science and following.startswith("![题图]("):
            para.paragraph_format.keep_with_next=True
        if short_example:
            para.paragraph_format.keep_together=True
        for idx in range(line_count):
            p=doc.add_paragraph()
            p.paragraph_format.space_after=Pt(0)
            p.paragraph_format.line_spacing=Pt(21)
            p.paragraph_format.keep_with_next=not science and idx+1 < line_count
        if content in grid:
            table=doc.add_table(rows=36,cols=25)
            table.autofit=False
            borders=OxmlElement("w:tblBorders")
            for side in ("top","left","bottom","right","insideH","insideV"):
                edge=OxmlElement("w:"+side)
                for key,val in (("val","single"),("sz","3"),("color","B0B0B0")):edge.set(qn("w:"+key),val)
                borders.append(edge)
            table._tbl.tblPr.append(borders)
            for row in table.rows:
                row.height=Cm(.63)
                row.height_rule=WD_ROW_HEIGHT_RULE.EXACTLY
                row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    doc.save(output)
