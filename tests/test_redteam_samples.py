
"""Immutable adversarial samples must fail the live gates but replay historical receipts."""
from pathlib import Path
from subprocess import check_output
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import bootstrap
from analysis_db import fingerprint
from core import board_cycle, language_workflow, review_board, science_workflow
from gaokao import ROOT
from mathgen import exam_workflow

SAMPLES=ROOT/"samples/2027-henan"
COMMON="terminology"
EXPECTED={
    "chinese":{(1,"answer_distribution","B有5/9"),(21,"chinese_paragraph_quote","“留”"),
               (17,"chinese_imagery","犬"),(22,"chinese_essay_bands","17～20"),
               (22,"chinese_essay_grid","900格")},
    "math":{(18,"math_progression","第三问"),(18,"math_conic_coverage","椭圆"),
            (16,"math_radical",r"\frac8{\sqrt{82}}"),(4,"math_defensive_variance","1/n"),
            *((n,"math_choice_equivalence","可接受数学等价写法") for n in range(1,9))},
    "english":{(1,"english_listening_length","842词"),(56,"english_grammar_prompts","5空，无提示词5空"),
               (41,"english_cross_item_leak","comparable"),(66,"english_language_weight","33%"),
               (67,"english_language_weight","12%"),(66,"english_printed_credit","预印"),
               (1,"english_invigilator","监考：")},
    "physics":{(13,"physics_dc_share","19分"),(13,"physics_core_topics","induction_rod"),
               (12,"physics_experiment_overlap","第11、12题"),(7,"physics_radical_decimal","小数"),
               (1,"physics_visible_uv","4.2 eV")},
    "chemistry":{(1,"chemistry_periodic","元素周期律"),(5,"chemistry_ionic_judgment","离子方程式"),
                (15,"chemistry_inorganic_arrow",r"\to"),(18,"answer_leak","③"),
                (1,"science_wrong_instructions","计算题"),(1,COMMON,"氧化数"),(17,COMMON,"气体活度")},
    "biology":{(15,"biology_molecular_genetics","主干"),(21,"biology_bioengineering","主干"),
               (1,"biology_hedged_keys","6/16"),(1,"science_wrong_instructions","计算题"),
               (17,"biology_table_reference","表格"),(5,COMMON,"同源体"),(7,COMMON,"居群"),(19,COMMON,"腐屑")},
}
FIXED={
    "samples/2027-henan":(298,"69d0e6ad06bb2590d4326242a278323968f2b11e74fede0aa751b5f8d35343da"),
    "data/papers":(289,"1fc1bccc8adeff02be99e39cf409571e4a296c3f57b3ca846060a0bb6940b1f5"),
    "forecast/frozen/henan-2027-math-v3.json":(1,"e9a448a61a6ab9764f1152dedbee973f5fcf4b769769440d25ffd1e0646c19fb"),
    "forecast/preregistered/2027-math-trends.json":(1,"5558b150e8ca4b413f7bdaee69c97d548a40431a3e4293cae93eb5e4c13230b3"),
}


class SampleRedTeamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audits={s:review_board.evidence(ROOT,SAMPLES/s,enforce_release=True)["preflight"] for s in EXPECTED}

    def test_all_six_fail_with_exact_item_evidence(self):
        for subject, triples in EXPECTED.items():
            with self.subTest(subject=subject):
                gate=self.audits[subject]
                self.assertFalse(gate["passed"])
                for n, identifier, evidence in sorted(triples):
                    self.assertTrue(any(i["number"]==n and i["rule"]==identifier and evidence in i["evidence"]
                                        for i in gate["issues"]), (subject,n,identifier,evidence,gate["issues"]))

    def test_live_board_does_not_open_review_inbox_or_rescore_old_samples(self):
        with TemporaryDirectory() as scratch:
            inbox=Path(scratch)/"inbox"
            for subject in EXPECTED:
                with self.subTest(subject=subject):
                    report=board_cycle.cycle(ROOT,SAMPLES/subject,inbox)
                    self.assertEqual(report["state"],"returned")
                    self.assertEqual(report["issues"],self.audits[subject]["issues"])
                    self.assertFalse(inbox.exists())

    def test_publish_stops_before_accepting_an_obsolete_certificate(self):
        for subject in EXPECTED:
            with self.subTest(subject=subject), self.assertRaisesRegex(ValueError,"标准发布硬安检失败"):
                folder=SAMPLES/subject
                if subject=="math":
                    exam_workflow.publish(folder,None,None)
                else:
                    publish=language_workflow.publish if subject in ("chinese","english") else science_workflow.publish
                    publish(folder,None)

    def test_historical_board_results_can_still_be_replayed(self):
        for subject in EXPECTED:
            with self.subTest(subject=subject):
                result=review_board.replay(SAMPLES/subject/"board")
                self.assertTrue(review_board.successful(result["status"]))

    def test_protected_corpus_samples_and_forecast_match_baseline_git_bytes(self):
        for name,expected in FIXED.items():
            root=ROOT/name
            files=root.rglob("*") if root.is_dir() else [root]
            paths=sorted(p.relative_to(ROOT).as_posix() for p in files if p.is_file())
            # Pin baseline blobs while honoring .gitattributes for preexisting CRLF checkout text.
            hashes=check_output(["git","hash-object","--stdin-paths"],cwd=ROOT,
                                input=("\n".join(paths)+"\n").encode()).decode().splitlines()
            members=list(zip(paths,hashes,strict=True))
            self.assertEqual((len(members),fingerprint(members)),expected,name)
