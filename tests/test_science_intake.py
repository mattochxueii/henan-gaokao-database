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


if __name__ == "__main__":
    unittest.main()
