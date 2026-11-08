"""Adversarial editorial, PDF-review and independent calculation regressions; no private key."""

import copy, json, tempfile, unittest, sys, shutil, hashlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap
import sympy as s
from gaokao import read_json, digest
from analysis_db import fingerprint
from storage import atomic_json
from mathgen.editorial import compile_writing
from mathgen.notation import latex
from mathgen.school_solver import solve_spec, extended_task
from mathgen.exam_workflow import publish, prepare, verify_certificate
from mathgen.student_pdf import normalise_tex

SCRATCH = ROOT / "tests/.scratch"
SCRATCH.mkdir(exist_ok=True)
PILOT = ROOT / "experiments/phase4/pilot-v2"


def document():
    return read_json(ROOT / "experiments/phase4/proposals/pilot.json")


def question(number=0):
    return copy.deepcopy(document()["questions"][number])


def shifted_review(folder):
    return read_json(folder / "student-review.json")


class WritingTests(unittest.TestCase):
    def test_separate_writing_request_omits_answers_and_design(self):
        from mathgen.writing_packet import request, attach

        d = document()
        packet = request(d, {"version": "test"})
        for row in packet["questions"]:
            self.assertNotIn("solution", row)
            self.assertNotIn("assessment", row)
            for option in row["math_spec"].get("options", {}).values():
                self.assertEqual(set(option), {"semantic_value"})
        response = {
            "questions": [
                {"id": q["id"], "writing": q["writing"]} for q in d["questions"]
            ]
        }
        self.assertEqual(attach(d, response), d)

    def test_sequence_subscripts(self):
        self.assertEqual(
            latex("u(n+1)==(n+1)*u(n)+factorial(n+1)"),
            r"u_{n+1}=\left(n+1\right)u_{n}+(n+1)!",
        )

    def test_redundant_parentheses_removed_without_solving_question(self):
        value = latex("((x*x)+2*x+1)/(x+1)")
        self.assertIn("x^{2}", value)
        self.assertNotIn("left", value)
        self.assertIn(r"\frac", value)
        self.assertNotEqual(value, "x+1")

    def test_boolean_is_not_student_formula(self):
        with self.assertRaises(ValueError):
            latex("(x>0) and (y>0)")

    def test_unhandled_formula_never_falls_back_to_source(self):
        for source in ("unknown(x)", "x.__class__", "x%2", "[x,y]"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                latex(source)

    def test_compiled_text_has_no_internal_task_labels(self):
        for q in document()["questions"]:
            visible = compile_writing(q)
            encoded = json.dumps(visible, ensure_ascii=False)
            self.assertNotIn("tasks", encoded)
            self.assertNotIn("目标事件", encoded)
            self.assertNotIn("指定值", encoded)

    def test_raw_program_expression_is_blocked(self):
        for text in ("u(n+1)", "sqrt(2)", "x**2", "semantic_value", "目标事件为1=1"):
            q = question()
            q["writing"]["stem"] += text
            with self.subTest(text=text), self.assertRaises(ValueError):
                compile_writing(q)

    def test_nested_raw_parentheses_are_blocked(self):
        q = question()
        q["writing"]["stem"] += "((((x+1))))"
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_missing_given_condition_is_blocked(self):
        q = question(3)
        q["writing"]["stem"] = q["writing"]["stem"].replace("{{init}}", "")
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_formula_and_spec_mismatch_is_blocked(self):
        q = question()
        q["writing"]["formulae"]["oa"]["source"] = "99"
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_unknown_symbol_is_blocked(self):
        q = question()
        q["math_spec"]["givens"]["oa"] = "q"
        q["writing"]["formulae"]["oa"]["source"] = "q"
        q["writing"]["spec_sha256"] = fingerprint(q["math_spec"])
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_raw_latex_bypass_is_blocked(self):
        q = question()
        q["writing"]["stem"] += r"\(q=3\)"
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_unclear_request_is_blocked(self):
        q = question(3)
        q["writing"]["parts"][0]["text"] = "计算即可。"
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_hint_is_blocked(self):
        q = question()
        q["writing"]["stem"] = "试用换元。" + q["writing"]["stem"]
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_inflated_score_without_depth_is_blocked(self):
        q = question(3)
        q["points"] = 15
        q["assessment"]["part_points"] = [7, 8]
        q["assessment"]["level"] = 1
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_disconnected_parts_are_blocked(self):
        q = question(3)
        q["assessment"]["linked_progression"] = ""
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_spec_revision_invalidates_writing(self):
        q = question()
        q["math_spec"]["tasks"][0]["expression"] = "3+5"
        with self.assertRaises(ValueError):
            compile_writing(q)

    def test_tex_shorthand_is_semantics_preserving(self):
        self.assertEqual(
            normalise_tex(r"\frac{\sqrt2}2+\frac\pi4+\binom62"),
            r"\frac{\sqrt{2}}{2}+\frac{\pi}{4}+\binom{6}{2}",
        )

    def test_missing_macro_argument_is_blocked(self):
        with self.assertRaises(ValueError):
            normalise_tex(r"\frac{2}")


class ReleaseTests(unittest.TestCase):
    def fixture(self):
        tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name) / "pilot"
        shutil.copytree(PILOT, out, ignore=shutil.ignore_patterns("assets", "pages"))
        review = read_json(PILOT / "student-review.json")
        comparison = read_json(PILOT / "mathematical-comparison.json")
        atomic_json(out / "review.json", review)
        atomic_json(out / "comparison.json", comparison)
        return out, review, comparison

    def check(self, out, review, comparison):
        atomic_json(out / "review.json", review)
        atomic_json(out / "comparison.json", comparison)
        return publish(out, out / "review.json", out / "comparison.json")

    def test_full_paper_is_blocked_until_pilot(self):
        d = document()
        d["paper"]["mode"] = "full"
        with (
            tempfile.TemporaryDirectory(dir=SCRATCH) as folder,
            self.assertRaises(ValueError),
        ):
            prepare(ROOT, d, Path(folder) / "out")

    def test_pdf_change_invalidates_review(self):
        out, r, c = self.fixture()
        p = out / "review-only/paper.pdf"
        p.write_bytes(p.read_bytes() + b"tampered")
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_visible_text_change_invalidates_review(self):
        out, r, c = self.fixture()
        d = read_json(out / "student-text.json")
        d["questions"][0]["stem"] = "换题"
        atomic_json(out / "student-text.json", d)
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_unblinded_review_cannot_release(self):
        out, r, c = self.fixture()
        r["internal_spec_read"] = True
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_missing_page_review_cannot_release(self):
        out, r, c = self.fixture()
        r["pages"] = r["pages"][:-1]
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_score_review_failure_cannot_release(self):
        out, r, c = self.fixture()
        r["questions"][0]["points_appropriate"] = False
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_whole_paper_failure_cannot_release(self):
        out, r, c = self.fixture()
        r["overall_pass"] = False
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_stale_mathematics_comparison_cannot_release(self):
        out, r, c = self.fixture()
        c["math_verification_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_wrong_independent_answer_key_cannot_release(self):
        out, r, c = self.fixture()
        r["questions"][0]["answer_key"] = "C"
        c["student_review_sha256"] = fingerprint(r)
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_raw_math_and_score_revision_cannot_release(self):
        out, r, c = self.fixture()
        d = read_json(out / "raw-ai-candidate.json")
        d["questions"][0]["points"] = 17
        atomic_json(out / "raw-ai-candidate.json", d)
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_published_pdf_is_the_actual_reviewed_byte_stream(self):
        out, r, c = self.fixture()
        with patch(
            "mathgen.dynamic.render_task",
            side_effect=AssertionError("raw renderer called"),
        ):
            certificate = self.check(out, r, c)
        self.assertEqual(digest(out / "paper.pdf"), r["pdf_sha256"])
        self.assertTrue(certificate["published"])
        verify_certificate(out, certificate)

    def test_altered_solution_invalidates_pilot_certificate(self):
        out, r, c = self.fixture()
        cert = read_json(out / "publication.json")
        p = out / "solutions.pdf"
        p.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            verify_certificate(out, cert)

    def test_known_partial_multichoice_cannot_be_overridden_by_ai(self):
        out, r, c = self.fixture()
        rows = read_json(out / "math-verification.json")
        rows[1]["answer_key"] = None
        atomic_json(out / "math-verification.json", rows)
        r["questions"][1]["answer_key"] = "BCD"
        c["student_review_sha256"] = fingerprint(r)
        c["math_verification_sha256"] = fingerprint(rows)
        with self.assertRaises(ValueError):
            self.check(out, r, c)

    def test_published_certificate_rejects_changed_raw_spec(self):
        out, r, c = self.fixture()
        d = read_json(out / "raw-ai-candidate.json")
        d["questions"][0]["points"] = 99
        atomic_json(out / "raw-ai-candidate.json", d)
        with self.assertRaises(ValueError):
            verify_certificate(out, read_json(out / "publication.json"))

    def test_published_certificate_rejects_changed_calculations(self):
        out, r, c = self.fixture()
        d = read_json(out / "math-verification.json")
        d[0]["answer_key"] = "D"
        atomic_json(out / "math-verification.json", d)
        with self.assertRaises(ValueError):
            verify_certificate(out, read_json(out / "publication.json"))


class IndependentMathTests(unittest.TestCase):
    def test_added_shift_in_weighted_sum_is_not_ignored(self):
        row = extended_task(
            {
                "op": "recurrence_sum",
                "relation": "2*u(n+1)-3*u(n)-2",
                "initial": {"1": "1"},
                "weight": "k",
                "additive_shift": "2",
                "upper": "n",
            }
        )
        n = s.Symbol("n", integer=True, positive=True)
        # Target comes from an independently computed 2-term expansion: 1*(1+2)+2*(5/2+2)=12.
        expr = s.sympify(row["result"], locals={"n": n})
        self.assertEqual(s.simplify(expr.subs(n, 2)), 12)

    def test_second_order_recurrence_is_cross_checked(self):
        row = extended_task(
            {
                "op": "linear_recurrence",
                "relation": "u(n+2)-3*u(n+1)+2*u(n)-2**n",
                "initial": {"1": "1", "2": "2"},
            }
        )
        n = s.Symbol("n", integer=True, positive=True)
        expr = s.sympify(row["result"], locals={"n": n})
        self.assertEqual(expr.subs(n, 3), 6)
        self.assertEqual(expr.subs(n, 4), 18)

    def test_alternating_sum_avoids_shared_symbolic_failure(self):
        row = extended_task(
            {
                "op": "series_claim",
                "expression": "(-1)**(k-1)*(k+1)",
                "upper": "2*n",
                "claim": "-n",
            }
        )
        self.assertTrue(row["result"])

    def test_laurent_coefficient_does_not_evaluate_at_zero(self):
        row = extended_task(
            {"op": "coefficient", "expression": "(x-1/x)**6", "power": 2}
        )
        self.assertEqual(row["result"], "15")
        with self.assertRaises(ValueError):
            extended_task({"op": "coefficient", "expression": "1/(x-1)", "power": 2})

    def test_multiple_models_with_one_value_are_valid(self):
        row = extended_task(
            {
                "op": "constrained_value",
                "variables": ["x"],
                "equations": ["x*x-1"],
                "value": "x*x",
                "unique_value": True,
            }
        )
        self.assertEqual(row["result"], "1")
        with self.assertRaises(ValueError):
            extended_task(
                {
                    "op": "constrained_value",
                    "variables": ["x"],
                    "equations": ["x*x-1"],
                    "value": "x",
                    "unique_value": True,
                }
            )

    def test_reasoning_is_not_silently_a_program_proof(self):
        row = extended_task(
            {
                "op": "reasoning",
                "expression": "log(x)-2*(x-1)/(x+1)",
                "positive_x": True,
            }
        )
        self.assertFalse(row["complete"])
        self.assertIsNone(row["result"])
        self.assertFalse(row["formal_proof"])

    def test_data_correction_uses_both_moments(self):
        self.assertEqual(
            extended_task(
                {
                    "op": "data_correction_variance",
                    "n": 10,
                    "recorded_mean": "8",
                    "recorded_variance": "6",
                    "recorded": "4",
                    "correct": "14",
                }
            )["result"],
            "7",
        )

    def test_diagram_geometry_volume(self):
        row = extended_task(
            {
                "op": "tetrahedron_volume",
                "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 3]],
            }
        )
        self.assertEqual(row["result"], "1/2")

    def test_source_override_does_not_mutate_original_analysis(self):
        from mathgen.planner import context

        before = digest(ROOT / "analysis/questions.jsonl")
        c = context(ROOT)
        corrected = next(
            r
            for r in c["analyses"]
            if r["question_id"] == "2025-cn-math-national-1:q015"
        )
        self.assertEqual(corrected["knowledge"]["module"], "概率统计")
        self.assertEqual(digest(ROOT / "analysis/questions.jsonl"), before)


if __name__ == "__main__":
    unittest.main()
