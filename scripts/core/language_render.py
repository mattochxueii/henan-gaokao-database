"""Shared typesetting for Chinese and English handouts."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, SimpleDocTemplate
from gaokao import atomic_write, require
from mathgen.export import chinese_font
from core.editorial_rules import LAYOUT_MODES
from mathgen.student_pdf import AnswerSpace, answer_height


def render(paper, output, answers=None, *, listening=None):
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
            target.append(Paragraph(styled,styles[kind]))
            marker={"h1":"# ","h2":"## ","h3":"### ","text":""}[kind]
            md.append(marker+line)
    put(title,"h1")
    if listening:
        if not paper.get("archive_practice"):
            put("监考用。两节材料均读两遍。第一节每段后留10秒。第二节每组读前按每题5秒读题，读后按每题5秒作答。")
        for label,text in listening.items():
            put(paper["materials"][label]["title"],"h2")
            put(text)
    else:
        if answers:
            put("项目参考评分。开放性试题允许依据合理、表达准确的不同答案。")
        else:
            put(f'满分{paper["points"]}分　考试时间{paper["minutes"]}分钟')
            if paper["subject"]=="english" and not paper.get("archive_practice"):
                put("听力30分，笔试120分。河南计入高考文化成绩的外语分为笔试原始分 × 1.25 后四舍五入。")
        seen_sections, seen_materials=set(),set()
        sections={key["id"]:key for key in paper["sections"]}
        for q in paper["questions"]:
            if q["section"] not in seen_sections:
                put(sections[q["section"]]["title"],"h2")
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
                    put("范文","h3")
                    put(sample)
                continue
            block=[]
            if (name:=q.get("material")) and name not in seen_materials:
                material=paper["materials"][name]
                # Keep a short listening label with the first question in its group.
                intro = block if q["section"] == "listening" else flow
                put(material["title"],"h2",intro)
                put(material["text"],"text",intro)
                for key,line in material.get("options",{}).items():
                    put(f"{key}. {line}")
                seen_materials.add(name)
            if q["kind"]=="grammar_gap":
                put(f'{n}. ____________________', "text")
                continue
            put(f'{n}.（{q["points"]:g}分）{q["stem"]}', "h3" if q.get("options") else "text",block)
            for figure in q.get("archive_figures",[]):
                block.append(Image(str(figure),width=340,height=145,kind="proportional"))
                md.append(f"![题图]({figure.relative_to(output.parent).as_posix()})")
            options=list(q.get("options",{}).items())
            if paper.get("archive_practice") and paper["subject"]=="english" and all(len(v)<38 for _,v in options):
                for i in range(0,len(options),2):
                    put("　　".join(f"{k}. {v}" for k,v in options[i:i+2]),target=block)
            else:
                for key,line in options:
                    put(f"{key}. {line}",target=block)
            if practice and (height := answer_height(q)):
                block.append(AnswerSpace(n, height, spaces))
            flow.append(KeepTogether(block))
            if q["kind"] not in ("single_choice","multiple_choice","gap_match","grammar_gap"):
                flow.append(Spacer(1,9))
    def footer(canvas,doc):
        canvas.setFont(font,9)
        canvas.drawCentredString(A4[0]/2,23,f"第 {doc.page} 页")
    SimpleDocTemplate(str(output.with_suffix(".pdf")),pagesize=A4,topMargin=39,bottomMargin=44,
                      leftMargin=49,rightMargin=49,title=title).build(flow,onFirstPage=footer,onLaterPages=footer)
    atomic_write(output.with_suffix(".md"),"\n\n".join(md)+"\n")


def export_docx(markdown, output):
    from docx import Document
    from docx.oxml.ns import qn
    doc=Document()
    normal=doc.styles["Normal"]
    normal.font.name="Calibri"
    fonts=normal.element.get_or_add_rPr().rFonts
    fonts.set(qn("w:eastAsia"),"Microsoft YaHei")
    for line in Path(markdown).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        lead, sep, text=line.partition(" ")
        if sep and lead in ("#","##","###"):
            doc.add_heading(text,len(lead)-1)
        else:
            doc.add_paragraph(line)
    doc.save(output)
