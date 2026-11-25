"""Regressions from the 2027 science publication workflow."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bootstrap
from core import exam_policy, review_board, science_workflow
from core.language_render import export_docx
from docx import Document
from gaokao import ROOT, read_json, write_json
from PIL import Image


class SciencePublicationTests(TestCase):
    def test_standard_policy_attached_after_initializing_the_paper(self):
        policy = exam_policy.resolve(ROOT, "physics", 2027, "河南", exam_policy.PHYSICS_SERIES)
        section = {"kind": "single_choice", "count": 2, "points": 8, "points_each": 4}
        blueprint = {"subject": "physics", "region": "河南", "mode": "standard",
                     "structure": {"sections": [section], "source_details": [section]},
                     "requested_topics": [], "structure_minutes": 75, "exam_policy": policy}
        questions = [
            {"id": f"orig:physics:test:{n}", "kind": "single_choice", "points": 4,
             "topic": topic, "stem": stem, "options": dict(zip("ABCD", ("1", "2", "3", "4"))),
             "proposed_answer": "A", "physics_module": module, "verification_mode": "independent_review",
             "independent_check": {"checks": {"derivation": "归纳每一项"}, "parts": {"overall": "核对"}}}
            for n, (topic, stem, module) in enumerate((
                ("电路", "判断串联电阻。", "electrostatics_circuits"),
                ("动能", "判断两物体的动能。", "mechanics")), 1)
        ]
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "output"
            with patch.object(science_workflow, "query", return_value=[]), \
                    patch.object(science_workflow, "check_standard_layout"), \
                    patch("mathgen.student_pdf.render", side_effect=lambda _, path: path.write_bytes(b"pdf")):
                science_workflow.prepare(ROOT, blueprint, {
                    "subject": "physics", "questions": questions,
                    "quality_benchmarks": {"review_board": review_board.VERSION},
                }, folder)
            paper = read_json(folder / "blind-packet.json")["paper"]
            self.assertEqual(paper["exam_policy"], policy)
            self.assertEqual(paper["qa_protocol"], review_board.VERSION)
            self.assertEqual(paper["questions"][1]["physics_module"], "mechanics")

    def test_science_word_includes_editable_stems_figures_and_formula(self):
        questions = [
            {"order": 1, "kind": "constructed_response", "points": 6,
             "stem": "记录速率", "parts": [{"label": "（1）", "text": "速率为________。"}]},
            {"order": 2, "kind": "constructed_response", "points": 12,
             "stem": "计算动能", "parts": [{"label": "（1）", "text": "求初始动能。"}]},
        ]
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            write_json(folder / "blind-packet.json", {"paper": {
                "layout_mode": "practice", "subject": "physics", "questions": questions}})
            Image.new("RGB", (80, 24), "white").save(folder / "figure.png")
            source = folder / "paper.md"
            source.write_text(
                r"计算动能。\(E=\frac{mv^2}{2}\)" + "\n![题图](figure.png)\n"
                "（1） 速率为________。\n（1） 求初始动能。\n", encoding="utf-8")
            output = folder / "paper.docx"
            export_docx(source, output)
            doc = Document(output)
            self.assertEqual(len(doc.inline_shapes), 2)
            self.assertEqual(doc.paragraphs[0].text, "计算动能。")
            self.assertIn("（1） 速率为________。", doc.paragraphs[2].text)
            self.assertEqual(doc.paragraphs[3].text, "（1） 求初始动能。")
            (workspace,)=doc.paragraphs[4:]
            self.assertFalse(workspace.text)
            self.assertIsNone(workspace._p.find(".//{*}pBdr"))
            self.assertTrue(all(not p.text for p in doc.paragraphs[4:]))
