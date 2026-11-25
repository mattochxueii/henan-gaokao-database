"""Guard the feature evidence and anonymous trial interfaces with synthetic fixtures."""

from pathlib import Path
import csv
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from feature_benchmark import coded, diagnostics, predict, score
from gaokao import read_json
from analysis_db import fingerprint
from student_feedback import csv_rows, make_csv, summary, validate


class FeatureBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.rubric = read_json(ROOT / "forecast/benchmark/rubric.json")

    def predict(self, stem, *, options=None, parts=None, kind="fill_in"):
        return predict({"stem":stem,"kind":kind,"options":options or {},"parts":parts or []},self.rubric)["labels"]

    def test_subtraction_is_not_shifted_index_and_option_is_evidence(self):
        key = "structure.sequence_recurrence"
        self.assertIsNone(self.predict(r"数列 \(b_n=a_n-6\)，求前项和。")[key])
        self.assertEqual(self.predict("记数列前n项和",options={"C":r"\(S_{n+2}=S_{n+1}+S_n\)"})[key],1)
        self.assertEqual(self.predict(r"按以下方式依次构造点 \(P_n\)，从 \(P_{n-1}\) 作直线后反射。证明数列的性质。")[key],1)

    def test_shared_object_does_not_imply_explicit_dependence(self):
        key = "method.explicit_dependence"
        kwargs = {"kind":"constructed_response"}
        self.assertIsNone(self.predict("给定函数",parts=["求极值点","研究该函数零点"],**kwargs)[key])
        self.assertEqual(self.predict("给定函数",parts=["求极值点","利用（1）的结果，证明有界"],**kwargs)[key],1)

    def test_abstention_affects_recall_and_rare_agreement(self):
        metrics = diagnostics([(None,1),(1,1),(0,0)])
        self.assertEqual(metrics["recall_with_abstentions"],.5)
        self.assertEqual(metrics["coverage_of_reference"],2/3)
        self.assertIsNone(diagnostics([(0,0)]*10)["cohen_kappa"])

    def test_binding_and_related_papers_cannot_straddle_split(self):
        row = {"stem":"计算2+2","kind":"fill_in","options":{},"parts":[]}
        packet = {"rubric_version":self.rubric["version"],"questions":{"a":row,"b":row}}
        model = coded(packet,self.rubric)
        def metadata(q, partition):
            return {"occurrence_id":q,"paper_id":q,"paper_group":"shared","partition":partition,
                    "strata":["random"],"prompt_sha256":fingerprint(row)}
        key = {"rubric_sha256":"hash","questions":{"a":metadata("a","development"),"b":metadata("b","holdout")}}
        with self.assertRaisesRegex(ValueError,"题群"):
            score(packet,self.rubric,key,model,model,model,model)
        key["questions"]["b"]["partition"] = "development"
        self.assertTrue(all(not g["official_forecast_admitted"]
                            for g in score(packet,self.rubric,key,model,model,model,model)["gates"].values()))

    def test_trial_import_new_and_old_csv_and_zero_observations(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"blank.csv"
            make_csv(path,"trial","hash",{"1":"a"},extended=True)
            self.assertEqual(list(csv_rows(path,"trial","hash",{"1":"a"})),[])
            with path.open(encoding="utf-8-sig",newline="") as handle:
                reader = csv.DictReader(handle)
                row = next(reader)
            row.update(participant_code="anon1",seconds="61",score="2",status="partial",
                       reading_difficulty="1",scoring_issue="1",reasoning_load="3",calculation_load="0")
            with path.open("w",encoding="utf-8-sig",newline="") as handle:
                writer = csv.DictWriter(handle,fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            observations = [validate(r,"hash",{"a":5}) for r in csv_rows(path,"trial","hash",{"1":"a"})]
            result = summary(observations,{"a":5},design={"a":{"module":"数列","assessment":{"estimated_minutes":1}}})
            item = result["questions"]["a"]
            self.assertEqual((item["median_seconds_over_editorial_estimate"],item["scoring_issue_reports"]),(1,1))
            self.assertEqual(item["interpretation"],"small_sample_only")
            self.assertIsNone(item["calibration_hint"])
            self.assertEqual(summary([],{"a":5})["questions"],{})
