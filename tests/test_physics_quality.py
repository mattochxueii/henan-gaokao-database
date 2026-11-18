"""Regressions for physics source and original exercise quality."""

from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import bootstrap  # noqa: F401
from core.catalog import physics_evidence, query
from core.science_workflow import plan, prepare, same_answer
from gaokao import read_json
from student_feedback import checked_questions, feedback_document
from subjects.physics import verify

EXPERIMENT = ROOT/"experiments/phase14/physics"


class PhysicsQualityTests(unittest.TestCase):
    def setUp(self):
        self.candidate = read_json(EXPERIMENT/"candidates.json")
        self.problems = [q["problem"] for q in self.candidate["questions"]]

    def test_selective_evidence_and_isolation(self):
        for year in (2025,2026):
            record = physics_evidence(ROOT,year)
            self.assertEqual([q["number"] for q in record["items"]],list(range(1,16)))
            self.assertEqual(sum(q["points"] for q in record["items"]),100)
            self.assertEqual(physics_evidence(ROOT,year,12)["items"][0]["state"],"quarantined")
            self.assertNotIn(12,[q["number"] for q in query(ROOT,"physics",year=year,verified_only=True)])
        with self.assertRaises(ValueError):
            physics_evidence(ROOT,2026,region="河北")
        with self.assertRaises(ValueError):
            physics_evidence(ROOT,2027)

    def test_braking_rejects_valid_algebraic_root_outside_stage(self):
        from sympy import sqrt
        spec = self.problems[3]
        late = (10+2*sqrt(13))/3
        self.assertEqual((5*late-3*late**2/4).simplify(),4)
        self.assertGreater(late,10/3)
        self.assertEqual(verify(spec)["answer"]["target_time_after_switch"],"10/3 - 2*sqrt(13)/3")
        spec["target"]["value"] = 15
        with self.assertRaisesRegex(ValueError,"可达"):
            verify(spec)
        spec["target"]["value"] = "43/3"
        self.assertEqual(verify(spec)["answer"]["target_time_after_switch"],"10/3")

    def test_axis_and_range_errors(self):
        graph = self.problems[1]
        graph["velocity_axis"] = "km/h"
        with self.assertRaisesRegex(ValueError,"velocity_axis"):
            verify(graph)
        circuit = self.problems[2]
        circuit["voltage_range"]["value"] = 2.5
        with self.assertRaisesRegex(ValueError,"超量程"):
            verify(circuit)

    def test_omitted_sign_case_and_contact_rejected(self):
        spec = self.problems[4]
        answer = verify(spec)["answer"]
        self.assertEqual(answer["spots_m"],{"positive":"1/50","negative":"-1/50"})
        missing = deepcopy(answer)
        del missing["spots_m"]["negative"]
        self.assertFalse(same_answer(answer,missing))
        spec["gap"]["value"] = ".010"
        with self.assertRaisesRegex(ValueError,"撞板"):
            verify(spec)

    def test_evidence_bounds_and_missing_assumptions(self):
        circuit = self.problems[2]
        observed = verify(circuit)["answer"]
        self.assertTrue(observed["within_tolerance"])
        self.assertFalse(observed["open_in_range"])
        self.assertFalse(same_answer(observed,{**observed,"evidence":"all_currents_proven"}))
        circuit["tolerance"]["value"] = ".024"
        self.assertFalse(verify(circuit)["answer"]["within_tolerance"])
        del circuit["ideal_meters"]
        with self.assertRaisesRegex(ValueError,"ideal_meters"):
            verify(circuit)

    def test_gate_requires_figure_and_exact_answer(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)/"job"
            blueprint = plan(ROOT,"physics","河南",2026)
            with self.assertRaisesRegex(ValueError,"题图"):
                prepare(ROOT,blueprint,self.candidate,out,Path(tmp))
            self.candidate["questions"][4]["proposed_answer"]["spots_m"].pop("negative")
            with self.assertRaisesRegex(ValueError,"答案"):
                prepare(ROOT,blueprint,self.candidate,out,EXPERIMENT)
            self.assertFalse(out.exists())

    def test_published_feedback_can_bind(self):
        sha, points = checked_questions(EXPERIMENT)
        self.assertEqual(len(sha),64)
        self.assertEqual(sum(points.values()),40)
        self.assertEqual(len(feedback_document(EXPERIMENT)["questions"]),5)
