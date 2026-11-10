import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap  # noqa: F401

from mathgen.paper_quality import assess_external, placement_report, reasoning_profile, verify_position_review


def move(kind, after=()):
    return {"kind": kind, "after": list(after), "evidence": kind + " 的可核查依据"}


ROUTINE = [move("routine_calculus"), move("substitute", [1])]
TRANSFER = [move("representation"), move("routine_algebra", [1])]
CHALLENGE = [move("necessity"), move("branch", [1]), move("sufficiency", [2])]


def question(n, kind="single_choice", role="foundation", moves=None, points=5):
    return {
        "order": n, "kind": kind, "points": points,
        "writing": {"formulae": {}},
        "placement": {
            "role": role, "purpose": "区分推理能力", "moves": moves or ROUTINE,
            "minutes": [6, 12],
            "structures": {"model": str(n), "goal": "result", "route": [str(n)]},
        },
    }


def document(*questions, mode="pilot"):
    return {"paper": {"mode": mode, "minutes": 60}, "questions": list(questions)}


class PaperQualityTests(unittest.TestCase):
    def test_late_single_choice_rejects_simple_derivative_even_with_good_item_score(self):
        q = question(8, role="challenge", moves=CHALLENGE)
        doc = document(q)
        plan = placement_report(doc, None)
        self.assertFalse(plan["failures"])
        reviewed = {"pdf_sha256": "same", "empirical": False, "student_review_independent": True,
                    "questions": [{"number": 8, "moves": ROUTINE, "minutes": [4, 6], "quality_score": 19}]}
        with self.assertRaisesRegex(ValueError, "position_role_mismatch"):
            verify_position_review(doc, reviewed, {"pdf_sha256": "same"}, plan)

    def test_last_fill_rejects_only_direct_inequality_under_challenge_role(self):
        basic = [move("recall"), move("substitute", [1])]
        q = question(14, "fill_in", "challenge", basic)
        self.assertEqual(placement_report(document(q), None)["failures"][0]["reason"],
                         "position_role_mismatch")

    def test_equivalent_ellipse_in_displayed_formula_is_detected(self):
        a, b = question(11), question(18)
        a["writing"]["formulae"]["f1"] = {"latex": r"\frac{x^2}{4}+y^2=1"}
        b["writing"]["formulae"]["f2"] = {"latex": "x^2+4y^2=4"}
        self.assertIn("structural_repetition", [p["reason"] for p in placement_report(document(a, b), None)["failures"]])

    def test_parameter_changes_do_not_create_a_different_structure(self):
        a, b = question(1), question(2)
        for q, c, d in [(a, 2, 4), (b, 3, 9)]:
            q["math_spec"] = {"tasks": [{"op": "equation", "expression": f"(x+{c})**2-{d}"}]}
        report = placement_report(document(a, b), None)
        self.assertTrue(report["conflicts"][0]["parameter_only_task_shape"])

    def test_high_marks_require_linked_nonroutine_reasoning(self):
        q = question(18, "constructed_response", "foundation", points=17)
        self.assertEqual(placement_report(document(q), None)["failures"][0]["reason"],
                         "high_marks_shallow_reasoning")

    def test_standard_variants_of_formal_reasoning_do_not_inflate_band(self):
        simple = [move("representation"), {**move("branch", [1]), "routine": True},
                  {**move("endpoint", [2]), "routine": True}]
        self.assertEqual(reasoning_profile(simple)["band"], 2)

    def test_section_tail_gate_with_individually_acceptable_questions(self):
        rows = [question(1), question(2, moves=CHALLENGE),
                question(3, moves=TRANSFER), question(4), question(5), question(6)]
        report = placement_report(document(*rows, mode="full"), None)
        self.assertEqual([r["reason"] for r in report["failures"]], ["section_tail_flat"])
        rows[3]["placement"]["moves"] = CHALLENGE
        rows[4]["placement"]["moves"] = TRANSFER
        self.assertFalse(placement_report(document(*rows, mode="full"), None)["failures"])

    def test_external_trig_answer_is_checked_independently(self):
        self.assertEqual(assess_external({"kind": "answer", "value": "4*pi/3"},
                                        independent_answer="pi/3"), "数学事实错误")

    def test_no_student_data_means_no_equating(self):
        self.assertEqual(assess_external({"kind": "empirical", "value": "120/150"},
                                         actual_students=0), "主观判断，证据不足")

    def test_exact_recurrence_threshold_and_cubic_critical_level(self):
        from mathgen.school_solver import extended_task

        a = extended_task({"op": "recurrence_first_window", "expression": "abs(x-1)+x/2",
                           "initial": 0, "pivot": "2/3", "tolerance": "2**(-50)"})
        self.assertEqual(a["result"], 52)
        b = extended_task({"op": "odd_cubic_level_parameter_square",
                           "linear_coefficient": 12, "distinct_roots": 4})
        self.assertEqual(b["result"], "256")
