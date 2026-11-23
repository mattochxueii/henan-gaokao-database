"""Chemistry failure cases are computed from the actual structured questions."""

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import bootstrap  # noqa: F401
from core.catalog import query, science_evidence
from core.science_workflow import plan, prepare, same_answer
from gaokao import read_json
from student_feedback import checked_questions
from subjects.chemistry import verify

TRIAL = ROOT/"experiments/phase15/chemistry"


class ChemistryQualityTests(unittest.TestCase):
    def setUp(self):
        self.candidate=read_json(TRIAL/"candidates.json")
        self.problems=[q["problem"] for q in self.candidate["questions"]]

    def test_archives_separate_chemistry_layout_and_quarantine(self):
        for year in (2025,2026):
            evidence=science_evidence(ROOT,"chemistry",year)
            self.assertEqual([q["number"] for q in evidence["items"]],list(range(1,19)))
            self.assertEqual(sum(q["points"] for q in evidence["items"][:14]),42)
            blocked={q["number"] for q in evidence["items"] if q["state"]=="quarantined"}
            self.assertFalse(blocked & {q["number"] for q in query(ROOT,"chemistry",year=year,verified_only=True)})
        with self.assertRaises(ValueError):
            science_evidence(ROOT,"chemistry",2025,region="河北")
        self.assertEqual(plan(ROOT,"chemistry","河南",2027,"standard")["structure_year"], 2026)

    def test_electrons_and_double_keys(self):
        p=self.problems[0]
        self.assertEqual(verify(p)["answer"],"B")
        p["options"]["B"]="one_e_per_cu"
        with self.assertRaisesRegex(ValueError,"无正确项"):
            verify(p)
        p["options"]["B"]="two_e_per_cu"
        p["options"]["A"]="zinc_anode_oxidizes"
        with self.assertRaisesRegex(ValueError,"多项"):
            verify(p)

    def test_balanced_reaction_does_not_confirm_wrong_medium(self):
        p={"op":"ionic_balance","medium":"silver_oxide_dilute_hcl",
           "reactants":["Ag2O","H^+"],"products":["Ag^+","H2O"]}
        with self.assertRaisesRegex(ValueError,"反应条件"):
            verify(p)
        p.update(reactants=["Ag2O","H^+","Cl^-"],products=["AgCl","H2O"])
        self.assertEqual(verify(p)["answer"]["reactant_coefficients"],[1,2,2])

    def test_structure_geometry_and_cell(self):
        self.assertEqual(verify(self.problems[1])["answer"],"C")
        q={"op":"vsepr","molecule":"BF3","isolated_neutral_molecule":True}
        self.assertEqual(verify(q)["answer"]["shape"],"trigonal_planar")
        q={"op":"cubic_occupancy","type":"rock_salt","conventional_cell":True,
           "sites":{"Na":{"edge":12,"body":1},"Cl":{"corner":8,"face":6}}}
        self.assertEqual(verify(q)["answer"],{"Na":4,"Cl":4})
        q["sites"]["Cl"]["face"]=5
        with self.assertRaisesRegex(ValueError,"占位"):
            verify(q)

    def test_missing_equilibrium_assumption_and_distinct_states(self):
        q=self.problems[2]
        self.assertEqual(verify(q)["answer"]["Q_after"],"49/200")
        self.assertEqual(verify(q)["answer"]["dimer_final"],"1/16")
        q["volume_ratio"]=1
        self.assertEqual(verify(q)["answer"]["direction"],"unchanged")
        q.pop("isothermal")
        with self.assertRaisesRegex(ValueError,"isothermal"):
            verify(q)

    def test_recovery_cannot_prove_identification(self):
        p=self.problems[3]
        answer=verify(p)["answer"]
        self.assertEqual(answer["spike_recovery_percent"],100)
        self.assertFalse(same_answer(answer,{**answer,"native_vitamin_c_identified":True}))
        p["blank_ml"]=7
        with self.assertRaisesRegex(ValueError,"不自洽"):
            verify(p)

    def test_organic_formula_and_reaction_extent(self):
        p=self.problems[4]
        self.assertEqual(verify(p)["answer"]["formula"],"C4H8O2")
        p["formula_claim"]="C4H10O2"
        with self.assertRaisesRegex(ValueError,"分子式"):
            verify(p)
        p.pop("formula_claim")
        p["hydroxide_mol"]=0.010
        with self.assertRaisesRegex(ValueError,"碱不足"):
            verify(p)

    def test_release_binds_student_figure_and_40_points(self):
        self.assertEqual(sum(checked_questions(TRIAL)[1].values()),40)
        with TemporaryDirectory() as tmp:
            c=self.candidate
            c["questions"][3].pop("figure")
            with self.assertRaisesRegex(ValueError,"题图"):
                prepare(ROOT,plan(ROOT,"chemistry","河南",2026),c,Path(tmp)/"out",TRIAL)
