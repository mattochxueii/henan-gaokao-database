from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import bootstrap
from pypdf import PdfReader
from reportlab.lib.units import cm

from core.exam_qa import required_figure_issues
from core.practice_workbook import archive_math_text
from core.release_checks import math_notation_findings, math_overlap_findings, math_point_warnings
from gaokao import read_json
from gaokao_platform import main
from math_skill import main as math_main
from mathgen.student_pdf import draw_figure, formula_font_size, normalise_tex, render
from mathgen.wireframe import hidden_edges


def cube():
    vertices={"A":(0,0,0),"B":(1,0,0),"C":(1,1,0),"D":(0,1,0),
              "A1":(0,0,1),"B1":(1,0,1),"C1":(1,1,1),"D1":(0,1,1)}
    edges=[(a,b) for a in vertices for b in vertices if a<b
           and sum(x!=y for x,y in zip(vertices[a],vertices[b]))==1]
    return vertices,edges


def item(number,stem,kind="constructed_response",**fields):
    return {"order":number,"points":5 if kind!="constructed_response" else 15,"stem":stem,
            "kind":kind,"parts":[],"options":{},**fields}


def paper(rows):
    return {"title":"排版测试","total_points":sum(q["points"] for q in rows),"minutes":120,
            "subject":"math","layout":"math_compact","questions":rows}


def horizontal_rules(page):
    # Track ReportLab's saved translation matrix to test actual page coordinates.
    stack=[]
    tx=ty=0
    start=None
    for values,op in page.get_contents().operations:
        if op==b"q":
            stack.append((tx,ty))
        elif op==b"Q":
            tx,ty=stack.pop()
        elif op==b"cm":
            tx+=float(values[4])
            ty+=float(values[5])
        elif op==b"m":
            start=float(values[0]),float(values[1])
        elif op==b"l" and start and abs(start[1]-float(values[1]))<.001:
            yield tx+start[0],tx+float(values[0]),ty+start[1]


class HardeningTests(TestCase):
    def test_front_back_and_interior_diagonals_and_projection(self):
        vertices,edges=cube()
        front,back,body=("A1","B"),("D1","C"),("A1","C")
        hidden=hidden_edges(vertices,[front,back,body],(.5,-4,.5))
        self.assertNotIn(frozenset(front),hidden)
        self.assertIn(frozenset(back),hidden)
        self.assertIn(frozenset(body),hidden)
        with self.assertRaisesRegex(ValueError,"view_angles"):
            draw_figure({"type":"wireframe","vertices":vertices,"edges":edges,"view_angles":[0,0]})
        draw_figure({"type":"wireframe","vertices":vertices,"edges":edges,"view_angles":[23,-57]})
        (_,issues)=required_figure_issues("math",[
            item(1,"如图，正方体",figure={"type":"coordinate"}),item(2,"如图，正方体",figure={"type":"wireframe"})])
        self.assertEqual([(n,rule) for n,rule,_ in issues],[(1,"solid_wireframe")])

    def test_exam_fill_in_instruction_and_compact_labels(self):
        with TemporaryDirectory() as tmp:
            file=Path(tmp)/"paper.pdf"
            q=item(1,"选择正确结果。","single_choice",options=dict(zip("ABCD",["10","20","30","40"])))
            fill=item(2,"写出结果。","fill_in")
            render(paper([q,fill]),file,layout_mode="exam")
            page=PdfReader(file).pages[0].extract_text()
            self.assertIn("请将答案填在答题卡的相应位置",page)
            self.assertIn("A.",page)
            self.assertNotIn("A .",page)
            self.assertNotIn("填在横线上",page)
            render(paper([fill]),file,layout_mode="practice")
            self.assertIn("请将答案填在横线上",PdfReader(file).pages[0].extract_text())
            from mathgen.cjk_layout import plain_markup
            self.assertEqual(plain_markup("___"),plain_markup("____________"))

    def test_lone_practice_area_reaches_safe_margin_without_lines(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"paper.pdf"
            render(paper([item(1,"写出推导。")]),path,layout_mode="practice")
            page=PdfReader(path).pages[0]
            self.assertIn("写出推导",page.extract_text())
            strokes=list(horizontal_rules(page))
            corners=[y for x,end,y in strokes if abs(abs(end-x)-9)<.1]
            self.assertAlmostEqual(min(corners),1.5*cm,places=2)
            self.assertFalse(any(abs(end-x)>20 for x,end,_ in strokes))
            self.assertGreater(read_json(path.with_suffix(".layout.json"))["answer_areas"][0]["height_cm"],15)
            render(paper([item(1,"写出推导。"),item(2,"证明结论。")]),path,layout_mode="practice")
            self.assertEqual([r["height_cm"] for r in read_json(path.with_suffix(".layout.json"))["answer_areas"]],[9.6,9.6])

    def test_tables_centered_and_high_equations_have_room_in_answers(self):
        self.assertEqual(normalise_tex(r"\triangle ABC"),r"\triangle ABC")
        self.assertGreater(formula_font_size(r"e^{\frac{11}{12}+\frac{1}{12n}}"),formula_font_size("e^x"))
        self.assertEqual(formula_font_size(r"x^{2}+\frac{1}{3}"),12)
        table={"headers":["方案","次数"],"rows":[["甲","4"],["乙","8"]]}
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"paper.pdf"
            q=item(1,"观察表格。",table=table,solution_table=table,solution_paragraphs=[
                r"第一行 \(1\)。",r"第二行 \(\sum_{k=1}^n\frac{k^2+1}{2k}\)。",
                r"第三行 \(e^{\frac{11}{12}+\frac{1}{12n}}\)。"])
            for solutions in (False,True):
                render(paper([q]),path,solutions=solutions)
                page=PdfReader(path).pages[0]
                lines=[(x,end) for x,end,_ in horizontal_rules(page) if abs(end-x)>200]
                self.assertEqual(len(lines),3)
                for x,end in lines:
                    self.assertAlmostEqual(x+end,float(page.mediabox.width),places=2)
                if solutions:
                    positions={}
                    def visit(text, cm, tm, font, size):
                        for word in ("第一行","第二行","第三行"):
                            if word in text:
                                positions[word]=cm[5]+tm[5]
                    page.extract_text(visitor_text=visit)
                    self.assertGreaterEqual(positions["第一行"]-positions["第二行"],19)
                    self.assertGreaterEqual(positions["第二行"]-positions["第三行"],19)

    def test_notation_order_unused_symbol_and_cross_question_rules(self):
        found=list(math_notation_findings(1,r"直线 \(1\) 恒过；k=1..n-1，a!=b、a>=0、a<=2、\binom{n}{2}、\mathbb{C}_U、锐二面角"))
        self.assertEqual(len(found),5)
        self.assertFalse(list(math_notation_findings(1,r"直线 \(l\) 恒过；\mathrm{C}_n^2、\complement_U A、两平面夹角")))
        rows=[
            item(1,r"函数 \(f(x)=2x^3+x\)，设 \(f'(x)\) 为其导函数。求切线斜率。",
                 "single_choice",options=dict(zip("ABCD",["1","3",r"\(\frac{3}{2}\)","4"]))),
            item(2,"求曲线的切线方程，考查计数原理。","fill_in"),
            item(3,"求二项式展开式系数。","fill_in"),
            item(4,r"函数 \(g(t)=5t^3+3t\)，求范围。"),
            item(5,r"已知三角形 \(a=3\)，\(b=4\)。","fill_in"),
            item(6,r"已知三角形 \(a=3\)，\(b=4\)。"),
        ]
        findings=list(math_overlap_findings(rows,[q["stem"] for q in rows]))
        self.assertEqual({rule for _,rule,_ in findings},{"math_tangent_overlap","math_fill_topic_overlap",
            "math_cross_section_model","math_numeric_order","math_unused_function"})
        self.assertEqual(sum(rule=="math_cross_section_model" for _,rule,_ in findings),2)
        clean=[item(1,r"设 \(f'(x)\) 为其导函数。求 \(f'(1)\)。","single_choice",
                    options=dict(zip("ABCD",["4","3","2","1"])))]
        self.assertFalse(list(math_overlap_findings(clean,[clean[0]["stem"]])))
        self.assertTrue(list(math_point_warnings(rows,{4:"交于 K。\n评分：求出交点 M。"})))
        self.assertFalse(list(math_point_warnings(rows,{4:"交于 K。\n评分：求出交点 K。"})))

    def test_generate_requires_opt_in_before_template_can_run(self):
        with TemporaryDirectory() as tmp, self.assertLogs(level="ERROR") as log:
            target=Path(tmp)/"paper"
            args=["generate","--mode","full","--output",str(target)]
            for extra in ([],["--engine","template"],["--engine","ai","--allow-template-fallback"]):
                self.assertNotEqual(math_main(args+extra),0)
                self.assertFalse(target.exists())
            self.assertTrue(all("gaokao_platform.py simulate math" in line for line in log.output))

    def test_archive_math_text_keeps_indices_and_moves_chinese_outside_math(self):
        text=archive_math_text(r"$F_1\perp\text{平面 }ABC$，∛5，−2")
        self.assertEqual(text,r"\(F_1\perp\)平面 \(ABC\)，\(\sqrt[3]{5}\)，-2")

    def test_archive_math_prose_renders_unicode_subscripts_as_math(self):
        text = archive_math_text(r"焦点F₁，数列aₙ₋₁、aₙ₊₁，记作P₀和P₉；\(F_2\)不变。")
        self.assertEqual(
            text, r"焦点\(F_{1}\)，数列\(a_{n-1}\)、\(a_{n+1}\)，记作\(P_{0}\)和\(P_{9}\)；\(F_2\)不变。"
        )

    def test_three_national_papers_export_through_cli(self):
        with TemporaryDirectory() as tmp:
            for paper_id,count in (("2024-cn-math-new-gaokao-1",19),
                                   ("2025-cn-math-national-1",19),
                                   ("2026-cn-math-national-1",16)):
                with self.subTest(paper=paper_id), redirect_stdout(StringIO()):
                    output=Path(tmp)/paper_id
                    self.assertEqual(main(["assemble","math",str(output),"--paper-id",paper_id,"--limit","100"]),0)
                    manifest=read_json(output/"manifest.json")
                    self.assertEqual(manifest["question_count"],count)
                    if paper_id.startswith("2026"):
                        self.assertEqual({int(row["id"][-3:]) for row in manifest["references"]},
                                         set(range(1,20))-{9,12,18})
                    pages = PdfReader(output/"paper.pdf").pages
                    self.assertGreater(len(pages),1)
                    markdown = (output/"paper.md").read_text(encoding="utf-8")
                    self.assertNotIn("（子项）", markdown)
                    keys=read_json(output/"answer-packet.json")
                    self.assertTrue(all(row["answer"]!="corrected" for row in keys))
                    if paper_id.startswith("2024"):
                        archive = Path(__file__).resolve().parents[1]/"data"/"papers"/"math"/f"{paper_id}.json"
                        q11 = next(q for q in read_json(archive)["questions"] if q["number"]==11)
                        figure = Path(q11["asset_refs"][0]["plaintext_path"]).name
                        self.assertTrue((output/"figures"/figure).is_file())
                        self.assertIn(f"![题图](figures/{figure})", markdown)
                        self.assertNotIn("q11_fig1.png","".join(page.extract_text() for page in pages))
                        self.assertNotRegex(markdown, r"\[图[：:]")
                        self.assertEqual(keys[8]["answer"],"BC")
                        self.assertIsNone(keys[14]["answer"])
                        self.assertIn("c=2√2",keys[14]["reasoning"])
