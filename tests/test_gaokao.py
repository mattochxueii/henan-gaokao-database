import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from cli import extract, question_result, summaries
from gaokao import digest, import_file, load, load_solutions, read_json, register, write_json
from reference import reference_rows

MATH = "2025-cn-math-national-1"
OTHER_MATH = "2026-cn-math-national-1"


class CatalogTests(unittest.TestCase):
    def test_local_candidate_is_queryable_without_promoting_it_to_official(self):
        sources, papers, _, entries = load(ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
            local = Path(directory)
            source_file = local / "scan.jpg"
            source_file.write_bytes(b"synthetic test fixture")
            write_json(local / "manifest.json", {
                "schema_version": 1, "scope": "local_reference",
                "papers": {MATH: {"source_id": "math-2025-21", "version": "test_candidate",
                                  "pages": [{"page": 1, "image": "scan.jpg", "width": 10, "height": 10}],
                                  "source_files": [{"path": "scan.jpg", "sha256": digest(source_file)}]}},
            })
            question_path = local / "questions" / "2025" / "math" / f"{MATH}.jsonl"
            question_path.parent.mkdir(parents=True)
            candidate = {"original_number": "1", "stem": "Synthetic question", "page": 1,
                         "end_page": 1, "review_status": "candidate_pages_checked",
                         "rendering": "normalized_from_candidate", "formulas": ["x^2"],
                         "options": dict(zip("ABCD", "1234")), "assets": []}
            question_path.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
            row = next(row for row in entries if row["id"] == f"{MATH}:q001")
            refs = reference_rows(local, sources, papers, entries, check_hash=True)
            result = question_result(row, papers[MATH], sources, None, refs[row["id"]])
            self.assertEqual(result["stem"], candidate["stem"])
            self.assertEqual(result["source_locator"]["source_id"], "math-2025-21")
            self.assertTrue(result["candidate_content_complete"])
            self.assertFalse(result["content_complete"])
            candidate["options"].pop("D")
            question_path.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "选项不完整"):
                reference_rows(local, sources, papers, entries)

    def test_math_solutions_are_distinct_from_complete_questions(self):
        sources, _, _, rows = load(ROOT)
        solutions = load_solutions(ROOT, rows, sources)
        cohort = [row for row in rows if row["paper_id"] in {MATH, OTHER_MATH}]
        self.assertEqual(len(cohort), 38)
        self.assertTrue(all(row["id"] in solutions for row in cohort))
        self.assertEqual(solutions[f"{MATH}:q001"]["result"], {"option": "C", "value_latex": "1"})
        self.assertEqual(solutions[f"{OTHER_MATH}:q018"]["status"], "conditional_on_candidate")

    def test_kind_filter_respects_complete_only(self):
        command = [sys.executable, str(ROOT / "scripts" / "cli.py"), "query",
                   "--year", "2025", "--subject", "math", "--kind", "fill_in"]
        result = subprocess.run(command, capture_output=True, check=True, encoding="utf-8")
        self.assertEqual([row["original_number"] for row in json.loads(result.stdout)], ["12", "13", "14"])
        complete = subprocess.run(command + ["--complete-only"], capture_output=True, check=True, encoding="utf-8")
        expected = [row for row in json.loads(result.stdout) if row["content_complete"]]
        self.assertEqual(json.loads(complete.stdout), expected)

    def test_collection_and_structure(self):
        sources, papers, records, rows = load(ROOT, check_hash=True)
        self.assertGreaterEqual(len(sources), 12)
        cohort = {(p["year"], p["subject"]) for p in papers.values()
                  if p["year"] in (2025, 2026) and "cn-ha" in p["regions"]}
        self.assertTrue({(year, subject) for year in (2025, 2026) for subject in
                         ("chinese", "math", "english", "physics", "chemistry", "biology")} <= cohort)
        for key in (MATH, OTHER_MATH):
            items = [q for q in rows if q["paper_id"] == key]
            self.assertEqual([q["original_number"] for q in items], list(map(str, range(1, 20))))
            self.assertEqual(sum(q["points"] for q in items), 150)
        self.assertEqual(len(summaries(papers, records, rows)), len(papers))

    def test_cli_search(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "cli.py"), "query",
             "--year", "2026", "--subject", "math", "--region", "cn-ha", "--number", "17"],
            capture_output=True, check=True, encoding="utf-8",
        )
        [item] = json.loads(result.stdout)
        self.assertEqual(item["id"], f"{OTHER_MATH}:q017")
        self.assertEqual(item["points"], 15)
        self.assertTrue(item["sources"])


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "data/metadata", self.root / "data/metadata",
                        ignore=shutil.ignore_patterns("files", ".intake.lock"))
        self.input = self.root / "sample.pdf"
        self.input.write_bytes(b"%PDF-1.4\nsynthetic fixture only\n")
        self.receipt_file = self.root / "receipt.json"
        self.receipt = {
            "role": "paper", "source_id": "jin-2025-math-paper", "acquired_on": "2026-11-06",
            "rights": "rightsholder_permission", "evidence": "Synthetic permission for test fixture",
            "rights_holder": "Test fixture author", "allow_local_storage": True,
            "allow_redistribution": False, "allow_derivatives": True, "variant": "retypeset",
        }

    def import_sample(self, key=MATH):
        write_json(self.receipt_file, self.receipt)
        return import_file(self.root, key, self.input, self.receipt_file)

    def test_repeat_and_cross_paper_deduplication(self):
        first = self.import_sample()
        self.assertEqual(first, self.import_sample())
        self.receipt["source_id"] = "jin-2026-math-paper"
        second = self.import_sample(OTHER_MATH)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["path"], second["path"])
        self.assertEqual(first["sha256"], digest(self.input))
        self.assertEqual(len(list(self.root.glob(".local-data/intake/originals/**/*.pdf"))), 1)
        self.assertEqual(len(load(self.root, check_hash=True)[2]), 2)

    def test_refuse_missing_permission_before_copy(self):
        self.receipt["allow_local_storage"] = False
        with self.assertRaisesRegex(ValueError, "本地保存权限"):
            self.import_sample()
        self.assertFalse((self.root / ".local-data/intake/originals").exists())

    def test_conflicting_retry_preserves_receipt(self):
        first = self.import_sample()
        self.receipt["allow_redistribution"] = True
        with self.assertRaisesRegex(ValueError, "收据不同"):
            self.import_sample()
        self.assertEqual(load(self.root)[2], [first])

    def test_validate_rejects_modified_blob(self):
        record = self.import_sample()
        (self.root / record["path"]).write_bytes(self.input.read_bytes().replace(b"fixture", b"damaged"))
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            load(self.root, check_hash=True)

    def test_register_is_idempotent_and_rejects_mock_paper(self):
        original = self.root / "data/metadata" / "papers" / f"{MATH}.json"
        self.assertEqual(register(self.root, original), MATH)
        value = read_json(original)
        value["session"] = "mock"
        attempt = self.root / "mock.json"
        write_json(attempt, value)
        with self.assertRaisesRegex(ValueError, "正式主考卷"):
            register(self.root, attempt)

    def test_extractor_retains_blank_middle_page_and_provenance(self):
        record = self.import_sample()
        with patch("cli.shutil.which", return_value="pdftotext"), patch("cli.subprocess.run") as run:
            run.return_value.stdout = "第一页\f\f第三页\f".encode("utf-8")
            result = extract(self.root, [record], record["id"])
        value = read_json(self.root / result["path"])
        self.assertEqual(value["source_sha256"], record["sha256"])
        self.assertEqual([page["needs_ocr"] for page in value["pages"]], [False, True, False])
        self.assertEqual(value["status"], "待校对")

    def test_bad_pdf_rejected_before_copy(self):
        self.input.write_bytes(b"<html>not a PDF</html>")
        with self.assertRaisesRegex(ValueError, "文件头不匹配"):
            self.import_sample()
        self.assertFalse((self.root / ".local-data/intake/originals").exists())

    def test_index_with_stem_is_rejected(self):
        path = self.root / "data/questions" / "2025" / "math" / f"{MATH}.jsonl"
        path.parent.mkdir(parents=True)
        source = ROOT / path.relative_to(self.root)
        row = json.loads(source.read_text(encoding="utf-8").splitlines()[0])
        row["stem"] = "Synthetic fixture"
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "索引记录不得夹带"):
            load(self.root)


if __name__ == "__main__":
    unittest.main()
