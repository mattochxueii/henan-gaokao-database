from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bootstrap  # noqa: F401
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import proj3d
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.lib.styles import ParagraphStyle

from core import exam_qa, marking_standards, science_workflow
from core.chemistry_data import (
    ATOMIC_NUMBERS,
    format_science_rubric,
    formula_molar_mass,
    sort_atomic_masses,
)
from core.exam_qa import (
    figure_edge_clipping,
    math_exam_pagination_warnings,
    pdf_page_fill_ratio,
    wireframe_undefined_vertices,
)
from core.release_checks import (
    VERSION as RELEASE_VERSION,
    chemistry_convention_findings,
    chemistry_equation_integrity_findings,
    chemistry_molar_mass_findings,
    chemistry_overlap_findings,
    choice_findings,
    findings as release_findings,
    math_checks,
    math_chi_square_findings,
    math_coverage_warnings,
    math_notation_findings,
)
from gaokao import ROOT, digest, read_json, write_json
from mathgen.cjk_layout import ExamParagraph, plain_markup
from mathgen.exam_workflow import verify_solution_consistency
from mathgen.export import chinese_font
from mathgen.student_pdf import (
    draw_figure,
    formula_image,
    normalise_prose_triangles,
    render,
)


def _item(number, stem, kind="constructed_response", **fields):
    return {
        "id": f"orig:math:v102:q{number:02}",
        "order": number,
        "points": 5 if kind != "constructed_response" else 15,
        "stem": stem,
        "kind": kind,
        "parts": [],
        "options": {},
        **fields,
    }


def _horizontal_rules(page):
    stack = []
    tx = ty = 0.0
    start = None
    for values, op in page.get_contents().operations:
        if op == b"q":
            stack.append((tx, ty))
        elif op == b"Q":
            tx, ty = stack.pop()
        elif op == b"cm":
            tx += float(values[4])
            ty += float(values[5])
        elif op == b"m":
            start = float(values[0]), float(values[1])
        elif op == b"l" and start and abs(start[1] - float(values[1])) < 0.001:
            yield tx + start[0], tx + float(values[0]), ty + start[1]


class Module1RenderingTests(TestCase):
    def test_wireframe_uses_ortho_and_proportional_box_aspect(self):
        prism = {
            "type": "wireframe",
            "view_angles": [20, -55],
            "vertices": {
                "A": (0, 0, 0),
                "B": (6, 0, 0),
                "C": (2, 4, 0),
                "A1": (1, 0, 1.5),
                "B1": (7, 0, 1.5),
                "C1": (3, 4, 1.5),
            },
            "edges": [
                ("A", "B"), ("B", "C"), ("C", "A"),
                ("A1", "B1"), ("B1", "C1"), ("C1", "A1"),
                ("A", "A1"), ("B", "B1"), ("C", "C1"),
            ],
        }
        with mock.patch.object(Figure, "savefig", autospec=True) as save:
            draw_figure(prism, "unused.png")
        ax = save.call_args.args[0].axes[0]
        self.assertEqual(ax.name, "3d")
        M = ax.get_proj()
        # Verify equal scale across x, y, z axes under orthographic projection.
        el, az = np.radians((20, -55))
        R = np.array([
            [-np.sin(az), np.cos(az), 0.0],
            [-np.sin(el) * np.cos(az), -np.sin(el) * np.sin(az), np.cos(el)],
        ])
        origin = np.array(proj3d.proj_transform(0, 0, 0, M)[:2])
        unit_pts = [np.array(proj3d.proj_transform(*v, M)[:2]) for v in np.eye(3)]
        disp = ax.transData.transform(np.vstack([origin, *unit_pts]))
        actual = [np.linalg.norm(disp[i] - disp[0]) for i in (1, 2, 3)]
        expected = [np.linalg.norm(R @ v) for v in np.eye(3)]
        ratios = [a / e for a, e in zip(actual, expected)]
        self.assertAlmostEqual(ratios[0], ratios[1], places=4)
        self.assertAlmostEqual(ratios[1], ratios[2], places=4)
        # Parallel vertical edges of a cube must remain strictly parallel (no perspective taper).
        cube_verts = {
            "A": (0, 0, 0), "B": (1, 0, 0), "C": (1, 1, 0), "D": (0, 1, 0),
            "A1": (0, 0, 1), "B1": (1, 0, 1), "C1": (1, 1, 1), "D1": (0, 1, 1),
        }
        cube_edges = [
            (a, b) for a in cube_verts for b in cube_verts
            if a < b and sum(x != y for x, y in zip(cube_verts[a], cube_verts[b])) == 1
        ]
        with mock.patch.object(Figure, "savefig", autospec=True) as save_cube:
            draw_figure({"type": "wireframe", "vertices": cube_verts, "edges": cube_edges, "view_angles": [23, -57]}, "unused.png")
        cax = save_cube.call_args.args[0].axes[0]
        CM = cax.get_proj()
        a0 = cax.transData.transform(proj3d.proj_transform(0, 0, 0, CM)[:2])
        a1 = cax.transData.transform(proj3d.proj_transform(0, 0, 1, CM)[:2])
        c0 = cax.transData.transform(proj3d.proj_transform(1, 1, 0, CM)[:2])
        c1 = cax.transData.transform(proj3d.proj_transform(1, 1, 1, CM)[:2])
        self.assertAlmostEqual(float(np.linalg.norm((a1 - a0) - (c1 - c0))), 0.0, places=5)

    def test_formula_image_preserves_italic_i_and_e_distinct_from_upright(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for italic, upright in (
                ("i", r"\mathrm{i}"),
                ("e", r"\mathrm{e}"),
                (r"\sum_{i=1}^{n} x_i", r"\sum_{\mathrm{i}=1}^{n} x_{\mathrm{i}}"),
            ):
                p1, p2 = root / "a.png", root / "b.png"
                formula_image(italic, p1)
                formula_image(upright, p2)
                self.assertNotEqual(p1.read_bytes(), p2.read_bytes(), (italic, upright))

    def test_prose_triangle_auto_normalization_in_pdf_and_markdown(self):
        raw = r"在△ABC与△TAB中，证明△OAB面积相等，并比较△A₁B₁C₁，保留\(\triangle XYZ\)和△H。"
        norm = normalise_prose_triangles(raw)
        self.assertIn(r"\(\triangle ABC\)", norm)
        self.assertIn(r"\(\triangle TAB\)", norm)
        self.assertIn(r"\(\triangle OAB\)", norm)
        self.assertIn(r"\(\triangle A_{1}B_{1}C_{1}\)", norm)
        self.assertIn(r"\(\triangle XYZ\)", norm)
        self.assertIn("△H", norm)
        with TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "paper.pdf"
            paper = {
                "title": "三角规范测试",
                "total_points": 15,
                "minutes": 120,
                "subject": "math",
                "layout": "math_compact",
                "questions": [_item(1, "在△ABC中求△OAB的面积。", solution_paragraphs=["在△TAB中计算。"])],
            }
            render(paper, pdf, solutions=False)
            self.assertNotIn("△ABC", PdfReader(pdf).pages[0].extract_text())
            self.assertIn(r"\(\triangle ABC\)", pdf.with_suffix(".md").read_text(encoding="utf-8"))
            sol = Path(tmp) / "solutions.pdf"
            render(paper, sol, solutions=True)
            self.assertIn(r"\(\triangle TAB\)", sol.with_suffix(".md").read_text(encoding="utf-8"))

    def test_solutions_do_not_reprint_question_table_unless_solution_table_given(self):
        stem_table = {"headers": ["样品", "pH"], "rows": [["甲", "3.6"], ["乙", "5.2"]], "caption": "表1 原题数据"}
        sol_table = {"headers": ["步骤", "结论"], "rows": [["①", "沉淀完全"]], "caption": "表2 答案汇总"}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            q_no_sol_table = _item(1, "根据表1回答。", table=stem_table, solution_paragraphs=["答案为3.6。"])
            paper = {
                "title": "答案表格测试",
                "total_points": 15,
                "minutes": 75,
                "subject": "chemistry",
                "layout": "science",
                "questions": [q_no_sol_table],
            }
            sol_pdf = root / "sol1.pdf"
            render(paper, sol_pdf, solutions=True)
            lines = [(x, end) for x, end, _ in _horizontal_rules(PdfReader(sol_pdf).pages[0]) if abs(end - x) > 200]
            self.assertEqual(len(lines), 0)
            self.assertNotIn("原题数据", sol_pdf.with_suffix(".md").read_text(encoding="utf-8"))
            self.assertNotIn("原题数据", PdfReader(sol_pdf).pages[0].extract_text())

            q_with_sol_table = {**q_no_sol_table, "solution_table": sol_table}
            sol_pdf2 = root / "sol2.pdf"
            render({**paper, "questions": [q_with_sol_table]}, sol_pdf2, solutions=True)
            lines2 = [(x, end) for x, end, _ in _horizontal_rules(PdfReader(sol_pdf2).pages[0]) if abs(end - x) > 200]
            self.assertEqual(len(lines2), 3)
            md2 = sol_pdf2.with_suffix(".md").read_text(encoding="utf-8")
            self.assertIn("答案汇总", md2)
            self.assertNotIn("原题数据", md2)

    def test_solution_figures_render_in_pdf_md_and_science_workflow(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fig_file = root / "organic_route.png"
            img = Image.new("RGB", (240, 100), "white")
            ImageDraw.Draw(img).rectangle([30, 20, 210, 80], outline="black", width=2)
            img.save(fig_file)
            sha = digest(fig_file)
            q = _item(
                18,
                "写出目标有机物的合成路线。",
                solution_paragraphs=["（1）结构简式与合成路线见下图。"],
                solution_figures=[{"path": str(fig_file), "sha256": sha, "caption": "图1 合成路线参考"}],
            )
            paper = {
                "title": "有机答案图测试",
                "total_points": 15,
                "minutes": 75,
                "subject": "chemistry",
                "layout": "science",
                "questions": [q],
            }
            sol_pdf = root / "solutions.pdf"
            render(paper, sol_pdf, solutions=True)
            page = PdfReader(sol_pdf).pages[0]
            self.assertGreaterEqual(len(page.images), 1)
            md = sol_pdf.with_suffix(".md").read_text(encoding="utf-8")
            self.assertIn("图1 合成路线参考", md)
            self.assertIn("![答案图](", md)
            # Wrong sha256 must be rejected.
            bad_q = {**q, "solution_figures": [{"path": str(fig_file), "sha256": "0" * 64}]}
            with self.assertRaisesRegex(ValueError, "哈希"):
                render({**paper, "questions": [bad_q]}, root / "bad.pdf", solutions=True)

            # End-to-end check inside science_workflow.adjudicate
            folder = root / "chem-run"
            folder.mkdir()
            src_fig = folder / "sol_q1.png"
            img.save(src_fig)
            packet_paper = {
                "subject": "chemistry",
                "title": "化学测试",
                "minutes": 30,
                "total_points": 14,
                "layout": "science",
                "layout_mode": "exam",
                "questions": [{
                    "id": "orig:chemistry:test:q1",
                    "order": 1,
                    "kind": "constructed_response",
                    "points": 14,
                    "stem": "推断有机产物。",
                    "options": {},
                    "parts": [{"label": "（1）", "text": "写出合成路线。"}],
                    "figure": None,
                }],
            }
            from analysis_db import fingerprint

            pver = fingerprint(packet_paper)
            write_json(folder / "blind-packet.json", {"subject": "chemistry", "paper": packet_paper, "paper_version": pver})
            render(packet_paper, folder / "paper.pdf")
            pdf_sha = digest(folder / "paper.pdf")
            write_json(folder / "verification.json", {
                "blueprint": {"mode": "targeted"},
                "questions": [{"id": "orig:chemistry:test:q1", "verification_mode": "program", "verification": {"unverified": []}}],
                "answers": [{"（1）": "见合成路线"}],
                "paper_version": pver,
                "paper_pdf_sha256": pdf_sha,
            })
            review = {
                "paper_version": pver,
                "paper_pdf_sha256": pdf_sha,
                "input_scope": "student_packet_only",
                "reviewer": "test-reviewer",
                "items": [{
                    "id": "orig:chemistry:test:q1",
                    "approved": True,
                    "answer": {"（1）": "见合成路线"},
                    "reasoning": "按取代—氧化—酯化三步完成。",
                    "rubric": [{"points": 14, "step": "写出H2O2、Al3+、2.7×10^-3、Co3O4、Kp1的对应步骤"}],
                    "solution_figures": [{"path": "sol_q1.png", "sha256": sha, "caption": "图S1 有机结构与路线"}],
                }],
            }
            science_workflow.adjudicate(folder, review)
            self.assertTrue((folder / "figures" / f"{sha}.png").is_file())
            sol_md = (folder / "solutions.md").read_text(encoding="utf-8")
            self.assertIn("![答案图](figures/", sol_md)
            self.assertIn("图S1 有机结构与路线", sol_md)
            self.assertIn(r"\(\mathrm{H_2O_2}\)", sol_md)
            self.assertIn(r"\(\mathrm{Al}^{3+}\)", sol_md)
            self.assertIn(r"\(2.7\times 10^{-3}\)", sol_md)
            self.assertIn(r"\(\mathrm{Co_3O_4}\)", sol_md)
            self.assertIn(r"\(K_{p1}\)", sol_md)

    def test_science_equivalence_split_once_per_section_and_rubric_subscripts(self):
        phys = marking_standards.science_equivalence("physics")
        chem = marking_standards.science_equivalence("chemistry")
        bio = marking_standards.science_equivalence("biology")
        self.assertEqual(len({phys, chem, bio}), 3)
        self.assertIn("物理量", phys)
        self.assertIn("配平", chem)
        self.assertIn("等价结构简式", chem)
        self.assertIn("专业术语", bio)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper = {
                "title": "化学答案去重测试",
                "total_points": 32,
                "minutes": 75,
                "subject": "chemistry",
                "layout": "science",
                "questions": [
                    _item(1, "单选题。", "single_choice", points=3, options=dict(zip("ABCD", "1234")),
                          solution_paragraphs=["A　解析。"]),
                    _item(2, "非选择1。", points=14, solution_paragraphs=[
                        "解析1。",
                        "评分参考　写出H2O2、Al3+、2.7×10^-3、Co3O4、Kp1（14分）。",
                    ]),
                    _item(3, "非选择2。", points=15, solution_paragraphs=["解析2。", "评分参考　配平正确（15分）。"]),
                ],
            }
            sol_pdf = root / "solutions.pdf"
            render(paper, sol_pdf, solutions=True)
            sol_md = sol_pdf.with_suffix(".md").read_text(encoding="utf-8")
            self.assertEqual(sol_md.count(chem), 1)
            self.assertIn("## 二、非选择题", sol_md)
            self.assertNotIn("物理量的等价单位", sol_md)
            # Bare ASCII tokens in rubric must be converted to formula images in PDF, not bare text.
            extracted = "\n".join(p.extract_text() for p in PdfReader(sol_pdf).pages)
            self.assertEqual(extracted.count("评分总则："), 1)
            for bare in ("H2O2", "Al3+", "2.7×10^-3", "Co3O4", "Kp1"):
                self.assertNotIn(bare, extracted)

    def test_chemistry_atomic_masses_sorted_and_nonbreaking(self):
        unsorted = {"Cu": 64, "Ti": 48, "O": 16, "Fe": 56, "H": 1, "C": 12, "N": 14, "S": 32, "Ba": 137}
        ordered = sort_atomic_masses(unsorted)
        self.assertEqual(list(ordered), ["H", "C", "N", "O", "S", "Ti", "Fe", "Cu", "Ba"])
        # Check ExamParagraph wrapping never splits any "Sym—Mass" pair across lines at narrow widths.
        font = chinese_font()
        style = ParagraphStyle("mass-test", fontName=font, fontSize=10, leading=15, wordWrap="CJK")
        pairs = "　".join(f"<nobr>{plain_markup(f'{k}—{v}')}</nobr>" for k, v in ordered.items())
        for width in (140, 175, 210, 260):
            p = ExamParagraph(plain_markup("可能用到的相对原子质量：") + pairs, style)
            p.wrap(width, 1000)
            lines = ["".join(word.text for word in line.words) for line in p.blPara.lines]
            for k, v in ordered.items():
                self.assertTrue(any(f"{k}—{v}" in line for line in lines), (width, k, v, lines))
        with TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "chem.pdf"
            paper = {
                "title": "化学卷头排序测试",
                "total_points": 3,
                "minutes": 75,
                "subject": "chemistry",
                "layout": "science",
                "relative_atomic_masses": unsorted,
                "questions": [_item(1, "选择题。", "single_choice", points=3, options=dict(zip("ABCD", "1234")))],
            }
            render(paper, pdf, layout_mode="exam")
            text = PdfReader(pdf).pages[0].extract_text()
            positions = [text.index(f"{k}—{ordered[k]}") for k in ordered]
            self.assertEqual(positions, sorted(positions))

    def test_display_formulas_solution_bottom_margin_and_math_exam_pagination_warning(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 1. Display formulas + safe bottom margin (>= 18-20 pt above footer top ~31 pt)
            long_paras = [
                r"参考公式：\(\hat{b}=\frac{\sum_{i=1}^{n}(x_i-\bar{x})(y_i-\bar{y})}{\sum_{i=1}^{n}(x_i-\bar{x})^2}\)",
                r"\[\chi^2=\frac{n(ad-bc)^2}{(a+b)(c+d)(a+c)(b+d)}\]",
                r"\[\mathrm{CO(g)+2H_2(g)\rightleftharpoons CH_3OH(g)} \\ \mathrm{CO_2(g)+H_2(g)\rightleftharpoons CO(g)+H_2O(g)}\]",
                *[f"推导第{i}步：由已知条件化简得恒等式成立，结合单调性与边界讨论给出完整解答过程。" for i in range(1, 55)],
            ]
            sol_paper = {
                "title": "展示公式与页脚安全距测试",
                "total_points": 15,
                "minutes": 120,
                "subject": "math",
                "layout": "math_compact",
                "questions": [_item(1, "推导。", solution_paragraphs=long_paras)],
            }
            sol_pdf = root / "solutions.pdf"
            render(sol_paper, sol_pdf, solutions=True)
            reader = PdfReader(sol_pdf)
            self.assertGreaterEqual(len(reader.pages), 2)
            # On page 1, find lowest body baseline (excluding footer y <= 28).
            body_ys = []

            def visit(text, cm, tm, font, size):
                if text and text.strip():
                    y = float(cm[5]) + float(tm[5])
                    if y > 28:
                        body_ys.append(y)

            reader.pages[0].extract_text(visitor_text=visit)
            # Footer baseline is 22 pt (9pt font -> top ~31 pt); body lowest baseline >= 50 pt gives >= 19 pt gap.
            self.assertGreaterEqual(min(body_ys), 50.0)

            # 2. Math exam 4 pages emits no warning; 5 pages with sparse odd 5th page (<35% fill) emits orphan-tail warning.
            filler = "已知函数满足连续可导条件，结合图像与代数变形讨论单调性、极值点与零点分布。"
            four_page_paper = {
                "title": "四页正常测试",
                "total_points": 150,
                "minutes": 120,
                "subject": "math",
                "layout": "math_compact",
                "questions": [_item(i, f"第{i}题：{filler * (10 if i < 19 else 2)}") for i in range(1, 20)],
            }
            exam4 = root / "exam4.pdf"
            render(four_page_paper, exam4, layout_mode="exam")
            self.assertEqual(len(PdfReader(exam4).pages), 4)
            self.assertEqual(math_exam_pagination_warnings(exam4), [])

            five_page_paper = {
                "title": "分页告警测试",
                "total_points": 150,
                "minutes": 120,
                "subject": "math",
                "layout": "math_compact",
                "questions": [
                    _item(i, f"第{i}题：{filler * (10 if i < 20 else 2)}")
                    for i in range(1, 21)
                ],
            }
            exam_pdf = root / "exam5.pdf"
            with self.assertLogs(level="WARNING") as logs:
                render(five_page_paper, exam_pdf, layout_mode="exam")
            pages = len(PdfReader(exam_pdf).pages)
            self.assertEqual(pages, 5)
            fill = pdf_page_fill_ratio(exam_pdf, -1)
            self.assertLess(fill, 0.35)
            warnings = math_exam_pagination_warnings(exam_pdf)
            self.assertTrue(warnings)
            self.assertEqual(warnings[0][1], "math_exam_pagination")
            self.assertIn("孤尾", warnings[0][2])
            self.assertTrue(any("孤尾" in line for line in logs.output))
            self.assertGreater(pdf_page_fill_ratio(exam_pdf, 0), 0.7)


class Module2MathAndChoiceGateTests(TestCase):
    def test_wireframe_undefined_vertex_spoiler_blocked(self):
        cube_verts = {
            "A": (0, 0, 0), "B": (2, 0, 0), "C": (2, 2, 0), "D": (0, 2, 0),
            "A1": (0, 0, 2), "B1": (2, 0, 2), "C1": (2, 2, 2), "D1": (0, 2, 2),
            "E": (0, 1, 1), "O": (1, 1, 0),
        }
        edges = [
            ("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"),
            ("A1", "B1"), ("B1", "C1"), ("C1", "D1"), ("D1", "A1"),
            ("A", "A1"), ("B", "B1"), ("C", "C1"), ("D", "D1"),
            ("O", "E"),
        ]
        fig = {"type": "wireframe", "vertices": cube_verts, "edges": edges, "view_angles": [23, -57]}
        q_spoiler = _item(
            16,
            r"如图，在正方体 \(ABCD-A_1B_1C_1D_1\) 中，点 \(E\) 为 \(AD_1\) 中点。",
            figure=fig,
        )
        self.assertEqual(wireframe_undefined_vertices(q_spoiler, fig), ["O"])
        report = exam_qa.inspect(ROOT, "math", {"questions": [q_spoiler]}, ["ok"])
        self.assertIn("wireframe_undefined_vertex", {x["rule"] for x in report["issues"]})
        q_clean = {**q_spoiler, "parts": [{"label": "（1）", "text": r"设 \(AC\) 与 \(BD\) 交于点 \(O\)，证明 \(OE\) 平行于平面。"}]}
        self.assertEqual(wireframe_undefined_vertices(q_clean, fig), [])

    def test_chi_square_recalculation_and_sympy_revision_consistency(self):
        # Exact: 100*(40*30-10*20)^2/(50*50*60*40) = 50/3 ≈ 16.667
        # Buggy 10x error: 200*(70*40-30*60)^2/(100*100*110*90) = 200/99, or 100/11 wrongly written as 1000/11.
        # Construct exact 100/11 case: n=110, a=40, b=15, c=15, d=40 -> 110*(1600-225)^2/(55*55*55*55)...
        # Use n=110, a=40, b=10, c=20, d=40 -> 110*(1600-200)^2 / (50*60*60*50) = 110*1960000/9000000 = 2156/90.
        # Simple exact 100/11: n=100, a=40, b=15, c=15, d=30? Check n=110, a=35, b=15, c=15, d=45 ->
        # Actually use n=100, a=35, b=15, c=20, d=30 -> 100*(1050-300)^2/(50*50*55*45) = 100*562500/6187500 = 100/11!
        good_sol = r"由列联表得 \(\chi^2=\frac{100\times(35\times 30-15\times 20)^2}{50\times 50\times 55\times 45}=\frac{100}{11}\approx 9.091\)。"
        self.assertEqual(list(math_chi_square_findings(17, {}, good_sol)), [])
        bad_10x = r"由列联表得 \(\chi^2=\frac{100\times(35\times 30-15\times 20)^2}{50\times 50\times 55\times 45}=\frac{1000}{11}\approx 90.909\)。"
        bad_rules = {r for _, r, _ in math_chi_square_findings(17, {}, bad_10x)}
        self.assertIn("math_chi_square_mismatch", bad_rules)
        over_bound = r"由列联表得 \(\chi^2=\frac{100\times(35\times 30-15\times 20)^2}{50\times 50\times 55\times 45}=\frac{1200}{11}\approx 109.09\)。"
        self.assertIn("math_chi_square_bound", {r for _, r, _ in math_chi_square_findings(17, {}, over_bound)})

        # Table-based cross-check without expanded fraction.
        q_table = _item(17, "独立性检验。", table={
            "headers": ["组别", "合格", "不合格", "合计"],
            "rows": [["甲", "35", "15", "50"], ["乙", "20", "30", "50"], ["合计", "55", "45", "100"]],
        })
        self.assertEqual(list(math_chi_square_findings(17, q_table, r"计算得 \(\chi^2=\frac{100}{11}\)。")), [])
        self.assertTrue(list(math_chi_square_findings(17, q_table, r"计算得 \(\chi^2=\frac{1000}{11}\)。")))

        # verify_solution_consistency: SymPy verified 100/11 vs tampered solution_revisions 1000/11.
        student = {"questions": [q_table]}
        raw = {"questions": [q_table]}
        calcs = [{"tasks": [{"complete": True, "result": "100/11"}]}]
        good_revs = {"17": {"paragraphs": [r"由独立性检验得 \(\chi^2=\frac{100}{11}\approx 9.091\)。"]}}
        bad_revs = {"17": {"paragraphs": [r"由独立性检验得 \(\chi^2=\frac{1000}{11}\approx 90.909\)。"]}}
        self.assertEqual(
            verify_solution_consistency(student, raw, calcs, good_revs, {"questions": [{**q_table, "solution_paragraphs": good_revs["17"]["paragraphs"]}]}),
            [],
        )
        conflicts = verify_solution_consistency(student, raw, calcs, bad_revs, {"questions": [{**q_table, "solution_paragraphs": bad_revs["17"]["paragraphs"]}]})
        self.assertIn("math_solution_revision_conflict", {r for _, r, _ in conflicts})

    def test_math_notation_structure_ai_traces_multichoice_mix_and_coverage_warnings(self):
        # Notation findings
        dirty = (
            r"补集 ℂ_U A，\(bcos C + ln x\)，导数 f´(x)，集合 {x∈ℤ : x>0}。"
            r"则下列结论成立，模长 ||AB|，定义 \(k-\)调和，轴向量 \(\overrightarrow{Cz}\)。"
        )
        rules = {r for _, r, _ in math_notation_findings(1, dirty)}
        self.assertTrue({
            "math_complement_notation",
            "math_italic_function",
            "math_acute_prime",
            "math_set_colon",
            "math_period_before_ze",
            "math_abs_typo",
            "math_mode_hyphen",
            "math_axis_vector",
        } <= rules)
        clean = r"补集 \(\complement_U A\)，\(b\cos C + \ln x\)，导数 \(f'(x)\)，集合 \(\{x\in\mathbb{Z}\mid x>0\}\)，则下列结论成立，\(|AB|\)，定义 \(k\)-调和，沿 \(Cz\) 轴正方向。"
        self.assertEqual(list(math_notation_findings(1, clean)), [])

        # Missing contingency table, AI stem opener, single-choice interval spoiler
        rows = [_item(i, "普通题目。") for i in range(1, 20)]
        rows[0] = _item(
            1,
            r"若实数 \(a\) 的取值范围为 \((m, +\infty)\)，其中 \(m\) 等于",
            "single_choice",
            options=dict(zip("ABCD", ["1", "2", "3", "4"])),
        )
        rows[15] = _item(16, "本题研究函数零点与单调性关系。")
        rows[16] = _item(17, "统计调查得到如下2×2列联表，判断是否有关联。")
        texts = [q["stem"] for q in rows]
        check_rules = {r for _, r, _ in math_checks({}, rows, texts)}
        self.assertTrue({
            "math_missing_contingency_table",
            "math_ai_stem_opener",
            "math_interval_spoiler",
        } <= check_rules)
        rows[16]["table"] = {"headers": ["组", "是", "否"], "rows": [["甲", "10", "5"], ["乙", "8", "7"]]}
        self.assertNotIn("math_missing_contingency_table", {r for _, r, _ in math_checks({}, rows, texts)})

        # Math 3 multiple-choice must mix 2-option and 3-option
        mc_rows = [_item(i, "多选。", "multiple_choice", options=dict(zip("ABCD", "1234"))) for i in (9, 10, 11)]
        self.assertIn("math_multiple_choice_mix", {r for _, r, _ in choice_findings(mc_rows, ["ABC", "ABD", "BCD"], "math")})
        self.assertIn("math_multiple_choice_mix", {r for _, r, _ in choice_findings(mc_rows, ["AB", "BC", "CD"], "math")})
        self.assertNotIn("math_multiple_choice_mix", {r for _, r, _ in choice_findings(mc_rows, ["AB", "BCD", "AC"], "math")})

        # Math coverage warnings: line & circle + solids of revolution (probability red balls must not count!)
        plain_rows = [_item(i, "袋中有3个红球和2个白球，已知椭圆方程。") for i in range(1, 20)]
        warn_rules = {r for _, r, _ in math_coverage_warnings(plain_rows)}
        self.assertEqual(warn_rules, {"math_line_circle_missing", "math_revolution_solid_missing"})
        plain_rows[2]["stem"] = "已知圆的方程为 x^2+y^2-4x=0，直线与圆相切。"
        plain_rows[5]["stem"] = "正四棱锥的外接球表面积为 16π。"
        self.assertEqual(list(math_coverage_warnings(plain_rows)), [])

    def test_single_choice_absence_streak_and_prompt_polarity(self):
        # 14 chemistry single-choice: Q1-Q11 missing D + all 14 asking "正确的是"
        chem_rows = [
            _item(i, f"第{i}题，下列说法正确的是", "single_choice", options=dict(zip("ABCD", "1234")))
            for i in range(1, 15)
        ]
        answers_no_d_streak = list("ABCABCABCABDDD")
        found = {r for _, r, _ in choice_findings(chem_rows, answers_no_d_streak, "chemistry")}
        self.assertIn("answer_option_absent_streak", found)
        self.assertIn("choice_prompt_polarity", found)

        # Balanced options & mixed reverse prompts pass
        chem_rows[3]["stem"] = "第4题，下列说法错误的是"
        chem_rows[9]["stem"] = "第10题，下列叙述不正确的是"
        balanced_answers = list("ABCDABCDABCDAB")
        self.assertEqual(list(choice_findings(chem_rows, balanced_answers, "chemistry")), [])


class Module3ChemistryAndPngGateTests(TestCase):
    def test_png_edge_clipping_detection(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Clipped PNG: draw dark ink touching left edge (x=0..1)
            clipped_path = root / "clipped.png"
            im = Image.new("RGB", (200, 120), "white")
            ImageDraw.Draw(im).line([(0, 20), (0, 90)], fill="black", width=2)
            im.save(clipped_path)
            self.assertIn("left", figure_edge_clipping(clipped_path))

            # Clean matplotlib figure exported with bbox_inches="tight", pad_inches=0.1
            clean_path = root / "clean.png"
            fig = Figure(figsize=(4, 2.5), dpi=150)
            FigureCanvasAgg(fig)
            ax = fig.subplots()
            ax.plot([0, 1, 2], [0, 2, 1])
            ax.set_xlabel("t / s")
            ax.set_ylabel("c / (mol/L)")
            fig.savefig(clean_path, bbox_inches="tight", pad_inches=0.1, facecolor="white")
            self.assertEqual(figure_edge_clipping(clean_path), [])

            # Inspect flags clipped figure on science question
            q = _item(
                1,
                "如图所示曲线。",
                "single_choice",
                options=dict(zip("ABCD", "1234")),
                figure={"path": "clipped.png", "sha256": digest(clipped_path)},
            )
            res = exam_qa.inspect(ROOT, "chemistry", {"questions": [q]}, ["A"], figure_folder=root)
            self.assertIn("figure_edge_clipped", {x["rule"] for x in res["issues"]})

    def test_chemistry_molar_mass_verification(self):
        # Mohr's salt missing 6H2O: 284 vs 392.125 -> fatal!
        self.assertAlmostEqual(formula_molar_mass("(NH4)2Fe(SO4)2·6H2O"), 392.125, places=2)
        bad = list(chemistry_molar_mass_findings(16, "称取莫尔盐 (NH4)2Fe(SO4)2·6H2O (M = 284 g/mol) 样品。"))
        self.assertEqual([r for _, r, _ in bad], ["chemistry_molar_mass"])
        good1 = list(chemistry_molar_mass_findings(16, r"称取 \(\mathrm{(NH_4)_2Fe(SO_4)_2\cdot 6H_2O}\)（\(M=392\,\mathrm{g\cdot mol^{-1}}\)）。"))
        good2 = list(chemistry_molar_mass_findings(16, "胆矾 CuSO₄·5H₂O（M = 250 g/mol）。"))
        self.assertEqual(good1, [])
        self.assertEqual(good2, [])

    def test_chemistry_conventions_missing_symbol_and_same_paper_collisions(self):
        dirty = "产物含 AlO2- 与 AlO_2^-，该分子杂化方式及价层排布式如下，合成恶嗪酮，含 0.5 N_A 个分子。"
        conv_rules = {r for _, r, _ in chemistry_convention_findings(3, dirty)}
        self.assertEqual(conv_rules, {
            "chemistry_legacy_aluminate",
            "chemistry_molecular_hybridization",
            "chemistry_valence_config_term",
            "chemistry_oxazinone_typo",
            "chemistry_bare_na",
        })
        clean = r"产物含 \([\mathrm{Al(OH)_4}]^-\)，中心原子的杂化方式及价层电子排布式如下，合成噁嗪酮，含 \(0.5N_{\mathrm{A}}\) 个分子。"
        self.assertEqual(list(chemistry_convention_findings(3, clean)), [])

        # Missing reaction connector
        self.assertTrue(list(chemistry_equation_integrity_findings(15, "焙烧反应：Mg(OH)2 MgO+H2O")))
        self.assertTrue(list(chemistry_equation_integrity_findings(15, r"方程为 \(\mathrm{Mg(OH)_2}\ \mathrm{MgO}+\mathrm{H_2O}\)。")))
        self.assertEqual(list(chemistry_equation_integrity_findings(15, r"方程为 \(\mathrm{Mg(OH)_2}=\mathrm{MgO}+\mathrm{H_2O}\)。")), [])
        self.assertEqual(list(chemistry_equation_integrity_findings(15, r"产物为 \(\mathrm{(CH_3)_2CHCOOH+(CH_3)_2CHCH_2OH}\)。")), [])

        # Same-paper collisions: reversible reaction reuse, organic scaffold >=2, acid/salt family >=3
        rows = [
            _item(1, r"反应 \(\mathrm{CO(g)+2H_2(g)\rightleftharpoons CH_3OH(g)}\) 在恒容容器中进行。", "single_choice", options=dict(zip("ABCD", "1234"))),
            _item(2, "利用呋喃二甲酸制备聚酯材料，用草酸滴定。", "single_choice", options=dict(zip("ABCD", "1234"))),
            _item(3, "以草酸钠为基准物标定高锰酸钾。", "single_choice", options=dict(zip("ABCD", "1234"))),
            _item(15, "用 H2C2O4 溶液还原浸出钴酸锂。", "constructed_response"),
            _item(17, "工业合成甲醇：CO + 2H₂ ⇌ CH₃OH  ΔH = -90.8 kJ/mol。", "constructed_response"),
            _item(18, "设计由生物质合成呋喃二甲酸的路线。", "constructed_response"),
        ]
        overlap_rules = {r for _, r, _ in chemistry_overlap_findings(rows, [q["stem"] for q in rows])}
        self.assertEqual(overlap_rules, {
            "chemistry_duplicate_reversible_reaction",
            "chemistry_organic_scaffold_overlap",
            "chemistry_acid_salt_cluster",
        })

    def test_anti_patterns_contain_v102_general_entries(self):
        math_ids = {e["id"] for e in exam_qa.policies(ROOT, "math")}
        chem_ids = {e["id"] for e in exam_qa.policies(ROOT, "chemistry")}
        self.assertTrue({"math.degenerate-boundary", "math.prob-rule-wording", "math.upright-ie"} <= math_ids)
        self.assertTrue({
            "chemistry.phenol-nitration",
            "chemistry.figure-answer-leak",
            "chemistry.element-infer-leak",
            "chemistry.cell-face-vs-center",
            "chemistry.polymer-end-bonds",
            "chemistry.bulb-condenser-mount",
            "chemistry.amide-rubric",
            "chemistry.inorganic-only-reagent",
        } <= chem_ids)
        self.assertEqual(len(ATOMIC_NUMBERS), 118)
