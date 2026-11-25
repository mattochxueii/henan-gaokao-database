"""Regressions for print space and the standard-paper edition rules."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from core.editorial_rules import REVISION, coverage, figure_issues, paper_issues, solution_competition
from analysis_db import fingerprint
from core.quality_audit import _paper_inputs
from gaokao import digest, read_json
from storage import atomic_json
from mathgen.student_pdf import render, science_section_note


def question(stem, *, kind="single_choice", points=5, module="", figure=None):
    return {"stem": stem, "kind": kind, "points": points, "module": module,
            "parts": [], "options": {}, "figure": figure}


class EditionRulesTests(unittest.TestCase):
    def test_exam_is_default_and_practice_measures_answer_space(self):
        items = [
            question("写出推导。", kind="constructed_response", points=12),
            question("证明结论。", kind="constructed_response", points=17),
            question("试剂为①________。", kind="constructed_response", points=9),
        ]
        for i, row in enumerate(items, 1):
            row["order"] = i
        paper = {"subject": "math", "layout": "math_compact", "title": "作答位置验收",
                 "total_points": 38, "minutes": 60, "questions": items}
        with TemporaryDirectory() as directory:
            practice = Path(directory) / "practice.pdf"
            exam = Path(directory) / "exam.pdf"
            render(paper, practice, layout_mode="practice")
            render(paper, exam)
            sizes = read_json(practice.with_suffix(".layout.json"))
            self.assertEqual(sizes["mode"], "practice")
            self.assertEqual(sizes["paper_sha256"], digest(practice))
            actual = {i: sum(row["height_cm"] for row in sizes["answer_areas"] if row["number"] == i)
                      for i in (1, 2, 3)}
            self.assertGreaterEqual(actual[1],7)
            self.assertGreaterEqual(actual[2],10.4)
            self.assertEqual(actual[3],0)
            self.assertEqual(read_json(exam.with_suffix(".layout.json"))["answer_areas"], [])
            text = "".join(page.extract_text() for page in PdfReader(exam).pages)
            self.assertIn("试剂为", text)

    def test_published_edition_uses_its_pdf_even_with_an_old_local_preview(self):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            blank = {}
            atomic_json(directory / "raw-ai-candidate.json", blank)
            atomic_json(directory / "student-text.json", blank)
            old = directory / "review-only/paper.pdf"
            old.parent.mkdir()
            old.write_bytes(b"old local review copy")
            released = directory / "paper.pdf"
            released.write_bytes(b"current released PDF bytes")
            atomic_json(directory / "review-manifest.json", {
                "candidate_sha256": fingerprint(blank), "writing_sha256": fingerprint(blank),
                "pdf_sha256": digest(released)})
            with self.assertRaisesRegex(ValueError, "PDF已修改"):
                _paper_inputs(directory)
            atomic_json(directory / "publication.json", {"published": True})
            self.assertEqual(_paper_inputs(directory)[-1], digest(released))
            released.write_bytes(b"changed release")
            with self.assertRaisesRegex(ValueError, "PDF已修改"):
                _paper_inputs(directory)

    def test_scoring_varies_by_subject(self):
        from core import exam_policy
        from gaokao import ROOT

        items = [question("选择", kind="multiple_choice", points=6)]
        math = exam_policy.resolve(ROOT, "math", 2027, "河南", exam_policy.NATIONAL_SERIES)
        physics = exam_policy.resolve(ROOT, "physics", 2027, "河南", exam_policy.PHYSICS_SERIES)
        self.assertIn("全部选对的得6分，部分选对的得部分分，有选错的得0分",
                      science_section_note("multiple_choice", items, exam_policy=math))
        self.assertIn("选对但不全得3分", science_section_note("multiple_choice", items, exam_policy=physics))

    def test_nonstandard_notation_is_rejected_before_render_in_both_versions(self):
        q = question(r"求 \(U\setminus A\)。")
        q["order"] = 1
        paper = {"subject": "math", "edition_rules": REVISION, "questions": [q]}
        with TemporaryDirectory() as directory:
            target = Path(directory) / "paper.pdf"
            with self.assertRaisesRegex(ValueError, "complement"):
                render(paper, target)
            q["solution_paragraphs"] = [r"\(P(Y^c)=1/4\)。"]
            with self.assertRaisesRegex(ValueError, "overline"):
                render(paper, target, solutions=True)
            self.assertFalse(target.exists())

    def test_pooled_variance_and_solid_geometry_small_item_are_required(self):
        q = [
            question(r"由函数 \(y=x-\ln x\) 的两条切线斜率求截距。", kind="fill_in"),
            question("计算合并组的方差", module="统计与概率"),
            question("求棱台外接球半径", kind="fill_in", module="立体几何"),
        ]
        paper = {"edition_rules": REVISION, "standard": True, "questions": q}
        self.assertFalse(paper_issues("math", paper))
        q[1]["stem"] = "计算两个班合并的平均数"
        q[2]["kind"] = "constructed_response"
        errors = " ".join(paper_issues("math", paper))
        self.assertIn("立体几何选填", errors)
        self.assertIn("平均数之外", errors)

    def test_three_missing_physics_modules_and_three_uses_of_device(self):
        q = [question("在弹簧作用下求加速度") for _ in range(3)]
        paper = {"edition_rules": REVISION, "standard": True, "questions": q}
        self.assertEqual(coverage("physics", paper)["overused_devices"], {"弹簧": [1, 2, 3]})
        self.assertEqual(len(paper_issues("physics", paper)), 2)
        self.assertFalse(paper_issues("physics", {**paper, "edition_rules": None}))

    def test_critical_value_must_appear_in_the_stem_and_figure(self):
        q = question("如图，求正方体的体积。", figure={
            "type": "wireframe", "labels": [{"math": "4"}]})
        self.assertTrue(figure_issues(q, {}))
        row = {"figure_conditions": {"observation": "检查了最终页的关键标注和图形。",
              "records": [{"anchor": "棱长为4", "label": "4", "meaning": "正方体的棱长"}]}}
        self.assertIn("未在考生正文", " ".join(figure_issues(q, row)))
        q["stem"] += "棱长为4。"
        self.assertFalse(figure_issues(q, row))
        q["figure"]["labels"][0]["math"] = "5"
        self.assertIn("不符", " ".join(figure_issues(q, row)))

    def test_balanced_but_incomplete_hard_water_reaction_is_rejected(self):
        q = question(r"硬水中Mg(OH)_2沉淀，HCO_3^-转化为碳酸根。")
        proof = {"pH_scope": "终态12.5", "order": "去质子化后按固相分配",
                 "competing_path": "HCO3 + OH → CO3 + H2O", "quantity_check": "强碱消耗对比",
                 "carbonate_balance": {"bicarbonate": 2, "neutralized": 1, "carbonate_solid": 1,
                                       "carbonate_liquid": 0, "magnesium_solid": 1, "hydroxide_total": 3}}
        self.assertIn("全部去质子化", solution_competition(q, {"aqueous_competition": proof}))
        proof["carbonate_balance"].update(neutralized=2, carbonate_liquid=1, hydroxide_total=4)
        self.assertIsNone(solution_competition(q, {"aqueous_competition": proof}))

    def test_selective_precipitation_checks_amphoteric_redissolution_and_threshold_data(self):
        q = question("测溶解态金属，除铝后除镁。")
        pilot = {"samples": [[4.5,44,100],[5.5,2,100],[6,1,100],[10.5,78,.6]],
                 "max_al": 2, "min_mg": 98, "selected_pH": 6, "secondary_pH": 10.5}
        proof = {"pH_scope": "5.5后升到10.5", "order": "先过滤再升pH",
                 "competing_path": "高pH铝重溶", "quantity_check": "比较各已测pH",
                 "hydroxide_pilot": pilot}
        self.assertIn("阈值", solution_competition(q, {"aqueous_competition": proof}))
        pilot["selected_pH"] = 5.5
        self.assertIsNone(solution_competition(q, {"aqueous_competition": proof}))
        q["stem"] += "忽略铝的两性溶解。"
        self.assertIn("不能跳过", solution_competition(q, {"aqueous_competition": proof}))


if __name__ == "__main__":
    unittest.main()
