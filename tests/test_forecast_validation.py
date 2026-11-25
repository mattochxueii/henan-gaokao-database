"""Research replay and label regressions that run without a private archive."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from forecast_labels import compare_pairs, proxy
from forecast_modes import research_context
from forecast_store import envelope, write_new
from forecast_validation import COMPACT, eligible_for_fold, replay, run, validate_observations
from gaokao import read_json


def observation(year, series, value, available=None, groups=()):
    return {"paper_id": f"{year}-{series}", "year": year, "series": series,
            "raw_available_on": available, "dated_source": "https://example.test/archive" if available else None,
            "events": {"structure.sequence_recurrence": value},
            "labels_produced_on": "2026-11-10", "label_protocol": "math-validation-v1",
            "paper_version_sha256": "test", "question_groups": list(groups)}


class ForecastValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = read_json(ROOT / "forecast/validation/protocol.json")

    def test_common_scoring_rows_and_year_weighting(self):
        result = run(ROOT)["as_of_dated_replay"][COMPACT]
        scores = result["scores"]
        self.assertEqual((result["n"], result["year_blocks"]), (7, 4))
        self.assertTrue(all(set(row["p"]) == scores.keys() for row in result["scored"]))
        self.assertEqual(scores["even"]["year_equal"]["brier"], .25)
        self.assertAlmostEqual(scores["legacy_policy_break"]["paper_equal"]["brier"], .25754408735215356)
        self.assertGreater(scores["legacy_policy_break"]["year_equal"]["log_loss"],
                           scores["even"]["year_equal"]["log_loss"])
        self.assertNotEqual(scores["legacy_policy_break"]["paper_equal"], scores["legacy_policy_break"]["year_equal"])
        self.assertLess(scores["last_year"]["leave_one_evaluation_year"][2024]["brier"], .05)

    def test_future_publication_and_related_questions_are_excluded(self):
        rows = [observation(2020,"I",0,"2020-07-01",("shared",)),
                observation(2021,"I",0,"2021-07-01"), observation(2022,"I",1,"2024-01-01"),
                observation(2022,"II",1), observation(2023,"I",1,"2023-06-08")]
        eligible = eligible_for_fold(rows,"2022-12-31",2023,{"shared"})
        self.assertEqual([r["year"] for r in eligible],[2021])

    def test_raw_dates_differ_from_label_creation_and_unknown_is_not_negative(self):
        rows = [observation(2020,"I",0,"2020-07-01"), observation(2021,"I",1,"2021-06-10"),
                observation(2022,"I",0,"2022-06-10"), observation(2023,"I",1,"2023-06-10"),
                observation(2024,"I",None,"2024-06-10")]
        output = replay(self.protocol,[],rows)["structure.sequence_recurrence"]
        self.assertEqual(output["n"],1)
        self.assertEqual(output["scored"][0]["training_dates"]["2022-I"],"2022-06-10")
        self.assertEqual(output["outcomes"],{"0":0,"1":1})
        self.assertEqual(output["discrimination_status"],"outcome_does_not_vary")
        self.assertEqual(output["external_increments"]["policy_active_pairs"],0)
        with self.assertRaisesRegex(ValueError,"倒填"):
            validate_observations(self.protocol,[{**rows[0],"labels_produced_on":"2020-07-01"}],
                                  dated_structure=False)

    def test_dated_source_binding_catches_backdated_archive(self):
        from gaokao import digest
        folder = ROOT / "forecast/validation"
        fake = {"protocol_sha256": digest(folder/"protocol.json"),
                "dates_sha256": digest(folder/"paper-dates.json"),
                "observations":[observation(2020,"I",0,"2020-01-01")]}
        with self.assertRaisesRegex(ValueError,"日期与带日期来源"):
            run(ROOT,fake)

    def test_recurrence_criterion_is_scoped_to_actual_shifted_terms(self):
        specs = self.protocol["targets"][1:]
        a = proxy({"stem":r"数列满足 \(a_{n+1}=a_n+1\)。", "parts":["求通项"], "kind":"constructed_response"},specs)
        b = proxy({"stem":r"等比数列 \(a_n\)。", "parts":[r"求 \(a_na_{n+1}\) 的和"], "kind":"fill_in"},specs)
        self.assertEqual(a["structure.sequence_recurrence"],1)
        self.assertEqual(b["structure.sequence_recurrence"],0)
        self.assertIsNone(b["method.explicit_proof"])

    def test_single_class_perfect_agreement_is_not_reliable(self):
        result = compare_pairs([(0,0)]*10 + [(None,1)])
        self.assertEqual((result["comparable"],result["review_positive"],result["agreement"]),(10,0,1))
        self.assertIsNone(result["cohen_kappa"])
        self.assertFalse(result["repeatable_for_exploration"])
        self.assertAlmostEqual(compare_pairs([(0,0),(1,0),(1,1),(1,1)])["cohen_kappa"], .5)

    def test_snapshot_labels_remain_exploratory_and_abstentions_are_excluded(self):
        def item(key,support,p):
            return {"target":key,"title":key,"layer":"method","support":support,
                    "probabilities":{"frequency":p,"recent":p}}
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "snapshot.json"
            write_new(p,envelope({"run_id":"t","as_of":"2026-11-10","target_year":2027,"series":"I",
                                  "predictions":[item("a","estimated",.6),item("b","insufficient",None)]}))
            result = research_context(p)
            self.assertEqual(result["target_evidence_tiers"],{"a":"exploratory","b":"abstained"})
            self.assertEqual(result["prospective_calibration"],"unavailable")
            self.assertEqual(set(result["eligible_targets"]),{"a"})
