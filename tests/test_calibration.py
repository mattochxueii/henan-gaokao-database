"""Regressions for provenance, blind quality and student feedback."""

from pathlib import Path
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap  # noqa: F401

from gaokao import digest
from math_calibration import active_review, grade
from mathgen.research_quality import (
    DIMENSIONS,
    verify_blind_quality,
    require_specialty_certificates,
)
from mathgen.student_pdf import formula_image
from PIL import Image, ImageOps
from student_feedback import summary, validate


class CalibrationTests(unittest.TestCase):
    def test_split_transitively_holds_papers_and_validates_candidate_versions(self):
        from mathgen.evaluation import build_split, verify_candidate_references

        def row(paper, oid, master, equivalent=None):
            review = {"body": "pdf_matched", "answer": "independently_solved"}
            if equivalent:
                review["equivalence_id"] = equivalent
            return {
                "paper_id": paper, "occurrence_id": oid, "question_id": master,
                "version_sha256": oid + "-version", "calibration": review,
            }

        data = [
            row("A", "a1", "shared"), row("B", "b1", "shared"),
            row("B", "b2", "m2", "alias"), row("C", "c1", "m3", "alias"),
            row("C", "c2", "m4"), row("D", "d1", "m5"), row("E", "e1", "m6"),
        ]
        split = build_split(data, ["A"], [("c2", "d1")])
        self.assertEqual(set(split["holdout"]), {"a1", "b1", "b2", "c1", "c2", "d1"})
        self.assertEqual(set(split["reference"]), {"e1"})
        ref = {"occurrence_id": "e1", "version_sha256": "e1-version"}
        doc = {"evaluation_split_sha256": split["sha256"],
               "questions": [{"research_design": {"references": [ref]}}]}
        verify_candidate_references(doc, split)
        ref.update(occurrence_id="a1", version_sha256="a1-version")
        with self.assertRaises(ValueError):
            verify_candidate_references(doc, split)

    def test_program_scope_and_exact_operations(self):
        from mathgen.school_solver import coverage, extended_task

        proof = extended_task({"op": "reasoning"})
        support = extended_task({"op": "reasoning", "expression": "x**2"})
        exact = extended_task({
            "op": "first_sum_exceedance", "expression": "1/(k*(k+2))",
            "threshold": "2/3", "inclusive": True,
        })
        self.assertEqual(exact["result"], 11)
        self.assertEqual(coverage([proof])["status"], "independent_reasoning_only")
        self.assertEqual(coverage([proof, support, exact])["partial_tasks"], 1)
        self.assertEqual(coverage([exact])["status"], "complete_spec_checks")
        with self.assertRaises(ValueError):
            extended_task({"op": "first_sum_exceedance", "expression": "1/(k-1)", "threshold": "2"})
        swap = extended_task({
            "op": "finite_swap_probability", "labels": [1, 2, 3, 4, 5, 6],
            "team_size": 3, "given_total": 12, "target_total": 11, "ask": "conditional_probability",
        })
        self.assertEqual(swap["result"], "5/27")

    def test_flat_interval_is_not_strict_monotonicity(self):
        from mathgen.school_solver import extended_task

        result = extended_task({
            "op": "monotonicity_boolean", "expression": "4",
            "domain": ["0", "3"], "direction": "increasing",
        })
        self.assertIs(result["result"], False)

    def test_blank_csv_binds_paper_and_accepts_no_observations(self):
        from student_feedback import csv_rows, make_csv

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blank.csv"
            make_csv(path, "T1", "hash", {"1": "q1"})
            self.assertEqual(list(csv_rows(path, "T1", "hash", {"1": "q1"})), [])
            with self.assertRaises(ValueError):
                list(csv_rows(path, "T2", "hash", {"1": "q1"}))

    def test_repair_and_answer_bind_to_the_archived_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "page.pdf"
            source.write_bytes(b"source")
            locator = {"path": source.name, "sha256": digest(source), "page": 1}
            row = {
                "version_sha256": "original",
                "stem": "old",
                "options": {"A": "old A"},
                "source_locator": {"pdf": locator},
                "answer": {"status": "original"},
            }
            review = {
                "base_version_sha256": "original",
                "source": locator,
                "body": "pdf_repaired",
                "answer": "independently_solved",
                "stem_edits": [["old", "new"]],
                "option_edits": [["A", "old A", "new A"]],
                "solution": "Checked",
                "result": "A",
            }
            corrected = active_review(row, review, root, set())
            self.assertEqual(corrected["options"]["A"], "new A")
            self.assertNotEqual(corrected["version_sha256"], row["version_sha256"])
            self.assertEqual(
                corrected["version_sha256"],
                corrected["answer"]["question_version_sha256"],
            )
            self.assertEqual(grade(corrected), "source_and_solution_reviewed")
            self.assertEqual(row["stem"], "old")
            self.assertEqual(
                grade(
                    active_review(
                        row, {**review, "base_version_sha256": "stale"}, root, set()
                    )
                ),
                "unreviewed",
            )
            source.write_bytes(b"modified")
            with self.assertRaises(ValueError):
                active_review(row, review, root, set())

    def test_blind_review_gate_rejects_weak_or_clipped_items(self):
        document = {"research_protocol": "calibrated-v1", "paper": {"mode": "pilot"}}
        scores = dict.fromkeys(DIMENSIONS, 2)
        review = {
            "questions": [
                {
                    "number": 1,
                    "quality": scores,
                    "quality_evidence": "reproducible explanation",
                }
            ]
        }
        verify_blind_quality(document, review)
        scores["reading"] = 0
        with self.assertRaises(ValueError):
            verify_blind_quality(document, review)
        with self.assertRaises(ValueError):
            require_specialty_certificates(())

    def test_formula_retains_italic_terminal_glyph(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, term = Path(tmp) / "base.png", Path(tmp) / "term.png"
            formula_image("f(x)=", base)
            formula_image("f(x)=t", term)
            with Image.open(base) as before, Image.open(term) as after:
                ink = ImageOps.invert(after)
                self.assertGreater(
                    ink.getbbox()[2], ImageOps.invert(before).getbbox()[2] + 2
                )
                self.assertLess(ink.getbbox()[2], after.width)

    def test_feedback_rejects_inconsistent_scores_and_marks_small_samples(self):
        row = {
            "participant_code": "trial07",
            "paper_sha256": "fixture",
            "question_id": "q1",
            "seconds": 100,
            "score": 2,
            "status": "partial",
            "error_types": ["logic"],
            "reading_difficulty": 1,
            "method_note": "分类讨论",
        }
        points = {"q1": 5}
        self.assertIs(validate(row, "fixture", points), row)
        with self.assertRaises(ValueError):
            validate({**row, "status": "correct"}, "fixture", points)
        with self.assertRaises(ValueError):
            validate(row, "changed", points)
        observed = summary([row], points)
        self.assertIsNone(observed["questions"]["q1"]["calibration_hint"])
        self.assertEqual(summary([], points)["records"], 0)


if __name__ == "__main__":
    unittest.main()
