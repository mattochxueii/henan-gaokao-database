"""Regression tests use public evidence and synthetic outcomes, without private material."""

from datetime import date
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
import bootstrap  # noqa: F401

from forecast_model import annual_blocks, backtest, contemporaneous_observations, eligible, evidence_by_date, loss, predict
from forecast_modes import attach_mode
from forecast_research import score_future
from forecast_store import envelope, frozen, inputs, materialize, write_new


def row(year, series, value, available=None, groups=()):
    return {"paper_id":f"{year}-{series}","year":year,"series":series,
            "available_on":available or f"{year}-07-01","question_groups":list(groups),
            "events":{"paper.compact":value},"shares":{}}


class ForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec, cls.docs, cls.entries = inputs(ROOT)

    def test_future_reviews_and_project_labels_cannot_leak(self):
        history = [row(2022,"I",0),row(2023,"I",1),
                   row(2024,"I",1,"2026-11-10"),row(2026,"I",1)]
        self.assertEqual([x["year"] for x in eligible(history,"2025-12-31",2026)],[2022,2023])
        docs = evidence_by_date(self.docs,"2025-12-31",2026)
        self.assertNotIn("review-2026",docs)
        self.assertIn("national-plan-2025",docs)
        self.assertNotIn("henan-2027-registration",docs)

    def test_later_article_about_older_exam_is_not_admitted_retroactively(self):
        dated = contemporaneous_observations(self.entries,self.docs)
        admitted = eligible(dated,"2023-12-31",2024)
        self.assertNotIn("core-2023-I",{r["paper_id"] for r in admitted})
        self.assertIn("core-2023-II",{r["paper_id"] for r in admitted})
        self.assertIn("core-2023-I",{r["paper_id"] for r in eligible(dated,"2024-12-31",2025)})

    def test_transitive_equivalent_papers_reduce_effective_blocks(self):
        records = [row(2020,"I",0,groups=["A"]),row(2020,"II",1,groups=["A"]),
                   row(2021,"I",1,groups=["A","B"]),row(2022,"II",1,groups=["B"])]
        result = annual_blocks(records,"paper.compact","I")
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["years"],[2020,2021,2022])
        self.assertAlmostEqual(result[0]["value"],7/9)
        with self.assertRaisesRegex(ValueError,"同卷重复"):
            eligible([records[0],records[0]],"2023-12-31",2024)

    def test_missing_is_not_negative_and_causes_abstention(self):
        records = [row(2020,"I",1),row(2021,"I",None),row(2022,"II",1),row(2023,"I",None)]
        result = predict(self.spec,self.docs,records,year=2024,cutoff="2023-12-31",series="I")
        entry = next(x for x in result["predictions"] if x["target"]=="paper.compact")
        self.assertIsNone(entry["probabilities"]["frequency"])
        self.assertEqual(entry["unknown_paper_observations"],2)
        self.assertEqual(entry["frequency_missing_label_range"],[0.5,5/6])

    def test_only_contemporaneous_target_scored_in_public_backtest(self):
        dated = contemporaneous_observations(self.entries,self.docs)
        run = backtest(self.spec,self.docs,dated)
        self.assertEqual(run["metrics"]["frequency"]["n"],7)
        self.assertEqual(run["metrics"]["curriculum"]["n"],0)
        self.assertEqual({item["target"] for f in run["folds"] for item in f["scored"]},{"paper.compact"})
        self.assertEqual(loss(0.75,1)["brier"],0.0625)

    def test_snapshot_refuses_overwrite_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"snapshot.json"
            record=envelope({"target_year":2027,"as_of":"2026-11-10"})
            write_new(path,record)
            self.assertEqual(frozen(path),record)
            with self.assertRaisesRegex(ValueError,"不可覆盖"):
                write_new(path,record)
            path.write_text(path.read_text().replace("2027","2028"),encoding="utf8")
            with self.assertRaisesRegex(ValueError,"完整性"):
                frozen(path)

    def test_future_outcome_requires_exam_and_correct_series(self):
        candidate=envelope({"target_year":2027,"as_of":"2026-11-10","series":"I",
             "target_spec_sha256":"fixed","predictions":[
                {"target":"t","probabilities":{"frequency":0.75},"primary_score_share_bounds":None}
             ]})
        result={"exam_date":"2027-06-07","published_on":"2027-06-08","target_year":2027,
                "subject":"math","region":"河南","series":"I","series_confirmed":True,
                "independent_review":True,"paper_version_sha256":"fixture","target_spec_sha256":"fixed",
                "official_identity_url":"https://example.test/fixture","events":{"t":1}}
        with self.assertRaisesRegex(ValueError,"考试之后"):
            score_future(candidate,result,date(2027,6,6))
        with self.assertRaisesRegex(ValueError,"适用卷"):
            score_future(candidate,{**result,"series":"II"},date(2027,6,9))
        self.assertEqual(score_future(candidate,result,date(2027,6,9))["binary_scores"][0]["brier"],0.0625)

    def test_generation_modes_keep_frozen_experiment_separate(self):
        candidate={"schema_version":2,"paper":{"mode":"pilot","title":"数学题"},
                   "forecast_snapshot_sha256":"frozen",
                   "questions":[{"id":"q","module":"函数",
                        "forecast_targets":[{"id":"module.functions","why":"极值条件"}]}]}
        context={"snapshot_sha256":"frozen","eligible_targets":{"module.functions":{}}}
        visible={"stem":"已知函数","parts":[],"kind":"single_choice"}
        with patch("mathgen.editorial.compile_writing",return_value=visible):
            run=attach_mode(candidate,"forecast-research",context)
            self.assertIn("概率预测研究实验",run["paper"]["title"])
            self.assertEqual(run["forecast_research"]["questions"][0]["targets"],["module.functions"])
            with self.assertRaisesRegex(ValueError,"主模块"):
                attach_mode({**candidate,"questions":[{**candidate["questions"][0],"module":"立体几何"}]},
                            "forecast-research",context)
            with self.assertRaisesRegex(ValueError,"独立于预测"):
                attach_mode(run,"standard")

    def test_public_sqlite_has_dated_evidence_and_rolls_back_invalid_data(self):
        dated = contemporaneous_observations(self.entries,self.docs)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            path=root/"good.sqlite"
            counts=materialize(path,self.spec,self.docs,[],dated,[])
            self.assertEqual(counts["exam_feature"],0)
            self.assertEqual(counts["feature_observation"],len(self.entries))
            with closing(sqlite3.connect(path)) as db:
                self.assertGreater(db.execute("SELECT COUNT(*) FROM policy_document").fetchone()[0],0)
            bad=root/"bad.sqlite"
            malformed=[{**dated[0],"events":{"unknown.target":1}}]
            with self.assertRaises(sqlite3.IntegrityError):
                materialize(bad,self.spec,self.docs,[],malformed,[])
            self.assertFalse(bad.exists())
