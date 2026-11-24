"""Phase 16 admissions and chemistry release regression tests."""
from copy import deepcopy
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap  # noqa: F401
from PIL import Image
from analysis_db import fingerprint
from core.catalog import DATA, query
from core.science_intake import import_electronic
from core.science_workflow import adjudicate, check_publication, plan, prepare
from gaokao import read_json
from storage import atomic_json


class ScienceIntakeTests(unittest.TestCase):
    def test_tracked_science_retains_missing_figure_item_and_siblings(self):
        from core.paper_intake import dna, research
        from core.science_intake import import_plain
        from core.practice_workbook import selection

        with TemporaryDirectory() as temp:
            root=Path(temp)
            (root/DATA).mkdir(parents=True)
            shutil.copyfile(ROOT/DATA/"catalog.json",root/DATA/"catalog.json")
            item={"number":1,"kind":"single_choice","points":4,"stem":"自制测试题",
                  "position":"测试第 1 页","options":dict(zip("ABCD","甲乙丙丁")),"answer":"A"}
            doc={"id":"2025-cn-ha-physics-selective","year":2025,"subject":"physics","title":"合成测试",
                 "series_id":"cn-ha-physics-selective","regions":["河南"],"exam_kind":"official_exam",
                 "source":{"title":"合成测试","url":"https://example.invalid"},"question_count":15,"points":100,
                 "missing_numbers":list(range(3,16)),
                 "questions":[item,{**item,"number":2,"stem":"测试题图缺失","requires_figure":True}]}
            mismatch={**doc,"regions":["湖北"]}
            with self.assertRaisesRegex(ValueError,"分开编号"):
                import_plain(root,mismatch,track=True)
            result=import_plain(root,doc,track=True)
            self.assertEqual((result["installed"],result["eligible"]),(2,1))
            self.assertEqual(query(root,"physics",year=2025)[0]["answer"],"A")
            self.assertEqual([row["number"] for row in selection(root,"physics")],[1])
            _, blocked=research(root,"physics",include_incomplete=True)
            self.assertTrue(blocked["missing_figure"])
            self.assertFalse(blocked["usable_for_practice"])
            profile=dna(root,"physics")["henan_selective_profile"]
            self.assertEqual([q["practice_eligible"] for q in profile["by_year"][0]["items"]],[True,False])

    def test_electronic_markdown_and_figures_with_two_admission_levels(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            root = folder / "db"
            (root / DATA).mkdir(parents=True)
            for name in ("catalog.json", "chemistry-evidence.json"):
                shutil.copyfile(ROOT / DATA / name, root / DATA / name)
            source = {"title": "合成数据，测试导入", "url": "https://example.invalid/q",
                      "rights_basis": "测试自制材料"}
            entry = {"number": 3, "kind": "single_choice", "points": 3,
                     "options": dict(zip("ABCD", "甲乙丙丁")), "images": ["graph.png"],
                     "conflict_note": "测试：标点差异，不影响解答。"}
            blocked = {**entry, "number": 4, "conflict_note": "测试：试剂存在分歧。",
                       "conflict_severity": "material", "images": []}
            doc = {"subject": "chemistry", "year": 2026, "title": "合成测试",
                   "source": source, "dataset_id": "quick-intake-test", "questions": [entry, blocked]}
            info = folder / "fixture.json"
            atomic_json(info, doc)
            md = folder / "fixture.md"
            md.write_text("## 3\n合成题面，需见附图。\n### 答案\nA\n## 4\n合成冲突。\n### 答案\nC\n", encoding="utf8")
            with self.assertRaisesRegex(ValueError, "原页或题图缺失"):
                import_electronic(root, info, md, folder)
            (folder / "graph.png").write_text("伪造图片", encoding="utf8")
            with self.assertRaisesRegex(ValueError, "图片无法读取"):
                import_electronic(root, info, md, folder)
            Image.new("RGB", (32, 32), "white").save(folder / "graph.png")
            self.assertEqual(import_electronic(root, info, md, folder), {"installed": 2, "quarantined": 1})
            (q,) = query(root, "chemistry", year=2026, verified_only=True)
            self.assertEqual((q["number"], q["answer"], q["stem"]), (3, "A", "合成题面，需见附图。"))
            self.assertTrue(q["usable_for_practice"])
            self.assertFalse(q["strict_official_verified"])
            self.assertEqual(q["conflict_note"], entry["conflict_note"])
            self.assertTrue((root / q["local_bundle_path"] / q["asset_refs"][0]["path"]).is_file())
            self.assertEqual(query(root, "chemistry", year=2026, official_only=True), [])
            # Exercise the stronger intake contract using a simulated official source.
            Image.new("RGB", (32, 32), "white").save(folder / "page.png")
            official = {**entry, "number": 5, "images": [], "official_page": "page.png",
                        "page": 2, "stem": "合成的官方分级测试题干", "answer": "B"}
            doc.update(dataset_id="quick-intake-official-shape", questions=[official])
            atomic_json(info, doc)
            with self.assertRaisesRegex(ValueError, "官方分级"):
                import_electronic(root, info, images=folder)
            doc["source"]["authority"] = "official"
            atomic_json(info, doc)
            import_electronic(root, info, images=folder)
            (q,) = query(root, "chemistry", year=2026, official_only=True)
            self.assertTrue(q["strict_official_verified"])
            self.assertIn("official_page_sha256", q)


class SciencePublicationTests(unittest.TestCase):
    def test_independent_channel_does_not_require_an_operator_but_binds_review(self):
        trial = ROOT / "experiments/phase16/henan-chem-100"
        candidate = read_json(trial / "source/candidates.json")
        answer = read_json(trial / "independent-review.json")["items"][0]
        candidate["questions"] = candidate["questions"][:1]
        blueprint = plan(ROOT, "chemistry", "河南", 2027, "targeted")
        with TemporaryDirectory() as temp:
            folder = Path(temp) / "draft"
            q = candidate["questions"][0]
            self.assertNotIn("problem", q)
            invalid = deepcopy(candidate)
            invalid["questions"][0]["independent_check"]["parts"] = {}
            with self.assertRaisesRegex(ValueError, "全部子问"):
                prepare(ROOT, blueprint, invalid, folder)
            receipt = prepare(ROOT, blueprint, candidate, folder)
            self.assertEqual(receipt["state"], "await_independent_review")
            self.assertFalse((folder / "solutions.pdf").exists())
            review = {"paper_version":receipt["paper_version"], "input_scope":"student_packet_only",
                      "reviewer":"合成测试", "items":[answer]}
            wrong = deepcopy(review)
            wrong["items"][0]["answer"] = "A"
            with self.assertRaisesRegex(ValueError, "答案一致"):
                adjudicate(folder, wrong)
            copied = deepcopy(review)
            copied["items"][0]["independent_check"] = q["independent_check"]
            with self.assertRaisesRegex(ValueError, "原样复制"):
                adjudicate(folder, copied)
            self.assertEqual(adjudicate(folder, review)["state"], "await_visual_review")
            self.assertTrue((folder / "solutions.pdf").is_file())

    def test_actual_chemistry_publication_and_bound_source(self):
        folder = ROOT / "experiments/phase16/henan-chem-100"
        paper = check_publication(folder, read_json(folder / "publication.json"))
        self.assertEqual((paper["total_points"], paper["minutes"]), (100, 75))
        self.assertEqual([q["points"] for q in paper["questions"]], [3] * 14 + [14, 14, 15, 15])
        receipt = read_json(folder / "verification.json")
        self.assertEqual(receipt["candidate_sha256"], fingerprint(read_json(folder / "source/candidates.json")))
        self.assertTrue(all(q["verification_mode"] == "independent_review" for q in receipt["questions"]))


class ScienceLayoutTests(unittest.TestCase):
    def test_layout_gate_rejects_missing_figures_blanks_and_detached_guidance(self):
        from core.science_dna import STANDARD_LAYOUT
        from core.science_workflow import blank_numbers, check_standard_layout, standard_presentation

        questions = [
            {"kind": "single_choice" if i <= 7 else "multiple_choice" if i <= 10 else "constructed_response",
             "figure": {"path": "drawn.png"} if i <= 6 or i >= 11 else None,
             "stem": "如图判断。" if i <= 6 else "阅读题干\n完成任务。",
             "options": {}, "parts": [{"label": "（1）", "text": r"取____\(\mathrm{m/s}\)，再求____。"}]
             if i in (11, 12) else []} for i in range(1, 16)
        ]
        questions = [standard_presentation(q) for q in questions]
        rules = STANDARD_LAYOUT["physics"]
        self.assertEqual(blank_numbers(questions[10]), ["①","②"])
        self.assertNotIn("\n", questions[10]["stem"])
        check_standard_layout(questions,rules)
        for index, changes, message in (
            (5, {"figure": None}, "至少有 6"),
            (0, {"stem": "由已知条件作答"}, "题干须指向"),
            (7, {"stem": "全选对得 6 分。然后作答。"}, "栏目统一"),
            (10, {"parts":[]}, "填空横线"),
        ):
            broken = questions[:]
            broken[index] = {**broken[index], **changes}
            with self.subTest(message=message), self.assertRaisesRegex(ValueError,message):
                check_standard_layout(broken,rules)

    def test_formula_punctuation_and_blank_stay_in_one_fragment_group(self):
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from mathgen.cjk_layout import ExamParagraph, plain_markup
        from mathgen.export import chinese_font

        font = chinese_font()
        style = ParagraphStyle("narrow-exam",fontName=font,fontSize=11,wordWrap="CJK",leading=16)
        with TemporaryDirectory() as temp:
            image = Path(temp) / "expression.png"
            Image.new("L",(150,52),"white").save(image)
            formula = f'<img src="{image.as_posix()}" width="27" height="9" valign="middle"/>'
            p = ExamParagraph("甲甲甲" + formula + "，可知。",style)
            p.wrap(pdfmetrics.stringWidth("甲甲甲",font,11)+28,100)
            self.assertFalse(any(f.text.startswith("，") and w.words[0] is f
                                 for w in p.blPara.lines for f in w.words))
            self.assertTrue(any(any(getattr(f,"cbDefn",None) for f in w.words)
                                and "".join(f.text for f in w.words).startswith("，")
                                for w in p.blPara.lines))
            q = ExamParagraph(plain_markup("实测速度为①________") + formula + "。",style)
            q.wrap(93,150)
            runs = [w.words for w in q.blPara.lines if any(f.us_lines for f in w.words)]
            self.assertEqual(len(runs),1)
            self.assertEqual("".join(f.text for f in runs[0] if f.us_lines),"\xa0"*8)
            self.assertTrue(any(getattr(f,"cbDefn",None) for f in runs[0]))

    def test_compact_exam_keeps_heading_with_question_and_counts_once(self):
        from pypdf import PdfReader
        from mathgen.student_pdf import render

        options = dict(zip("ABCD", "甲乙丙丁"))
        questions = [
            {"order":i,"kind":kind,"points":points,"stem":"以压强变化判断反应。",
             "options": options if i<=2 else {},
             "parts":[{"label":"（1）","text":"测得值为①________。"}] if i>2 else []}
            for i, (kind,points) in enumerate(
                [("single_choice",4),("multiple_choice",6),*([("constructed_response",10)]*5)],1)
        ]
        with TemporaryDirectory() as temp:
            path = Path(temp) / "paper.pdf"
            render({"layout":"science","title":"理科排版测试","total_points":60,"minutes":75,
                    "partial_credit":3,"questions":questions},path,layout_mode="exam")
            pdf = PdfReader(path)
            self.assertEqual(len(pdf.pages),1)
            text = pdf.pages[0].extract_text()
            self.assertIn("三、非选择题",text)
            self.assertRegex(text,r"(?m)^1\.[ \t]*以")
            self.assertIn("3.（10分）",text)
            self.assertEqual("".join(text.split()).count("选对但不全得3分"),1)


if __name__ == "__main__":
    unittest.main()
