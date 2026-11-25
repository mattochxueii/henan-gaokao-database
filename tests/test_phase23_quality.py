import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analysis_db import fingerprint
from core.language_workflow import plan, prepare
from core.practice_workbook import authoring_context
from core.quality_audit import MAIN_VERSION, bound_reference, evaluate
from gaokao import ROOT, digest, read_json
from math_trends import SIGNALS, SNAPSHOT, V3, V3_SHA256, bind_pack_positions, score, validate_snapshot


def audit_fixture(subject):
    sample = {"version_sha256": "source-version"}
    reference = {"protocol": MAIN_VERSION, "subject": subject, "slots": {"1": {"2025": sample, "2026": sample}}}
    paper = {"materials":{"m":{"text":"总体差异缩小，但农村地区的差异仍大。"}},
             "questions":[{"id":"q", "kind":"single_choice", "stem":"下列说法正确的是",
                           "material":"m","section":"information",
                           "options":dict(zip("ABCD",("a","b","c","d"),strict=True))}]}
    wrong = {key:{"plausible": True,"misconception":"量词范围混淆","mechanism":"将总体措辞移到农村地区",
                 "subtle": True,"trap":"scope","unchanged":"保留主题与缩小描述",
                 "distortion":"将总体范围缩为农村"} for key in "BCD"}
    row = {"number":1,"benchmarks": {year: {**sample,"comparison":"需要对照句中范围和例外。"} for year in ("2025","2026")},
           "depth":{"reasoning_steps":["定位转折","缩小适用范围"],"linked_concepts":["总体","子群"]},
           "findings":{rule:{"verdict":"not_applicable" if rule=="figure" else "pass",
                            "evidence":"保留论断范围与限制。"} for rule in ("distractors","depth","figure","language")},
           "distractors":wrong,
           "language_style":{"natural":True,"register":"信息类论述","evidence":"先写观察，再限制外推。"},
           "reading_turn":{"span":"农村地区的差异仍大","from":"转折前的总体结果","to":"总体结果不能替代子群结论"}}
    document = {"protocol":MAIN_VERSION,"reference_sha256":fingerprint(reference),
                "paper_version":fingerprint(paper),"paper_pdf_sha256":"pdf","reviewer":"test","items":[row]}
    review = {"items":[{"number":1,"answer":"A"}]}
    return reference,paper,document,review


def evaluate_fixture(reference, paper, doc, review):
    doc["paper_version"] = fingerprint(paper)
    return evaluate(reference,paper,doc["paper_version"],"pdf",doc,review=review)


class MainPaperGates(unittest.TestCase):
    def test_language_context_attaches_four_real_fulltext_papers_each(self):
        for subject, expected in (("chinese", 23), ("english", 67)):
            with self.subTest(subject=subject):
                context = authoring_context(ROOT, subject, limit=250)
                corpus = context["language_corpus"]
                rehearsal = context["rehearsal_references"]
                self.assertEqual([r["year"] for r in corpus], [2024,2025,2026,2025])
                self.assertEqual([r["exam_kind"] for r in corpus], ["official_exam"]*3+["adaptation_exam"])
                self.assertEqual(len(rehearsal), expected)
                self.assertTrue(all(r["stem"] and "answer" not in r for r in rehearsal))
                self.assertTrue(all((ROOT/r["path"]).is_file() for r in corpus))
                reference = context["quality_benchmarks"]
                self.assertEqual(reference["protocol"], MAIN_VERSION)
                self.assertTrue(all(len(r)==2 for r in reference["slots"].values()))
                if subject == "chinese":
                    self.assertEqual(reference["slots"]["22"]["2025"]["reference_number"], 23)
                    self.assertEqual(reference["slots"]["22"]["2025"]["reference_section"], "essay")
                    self.assertEqual(reference["slots_by_basis_year"]["2025"]["22"]["2026"]["alignment"],
                                     "same_section_only")
                candidate = {"reference_scope":"fulltext",
                             "provenance":{"language_corpus_sha256":fingerprint(corpus),
                                           "quality_reference_sha256":fingerprint(reference)}}
                self.assertEqual(bound_reference(context, candidate), reference)
                with self.assertRaisesRegex(ValueError, "四套"):
                    bound_reference({**context,"rehearsal_references":[]}, candidate)
                blueprint = plan(ROOT,subject,"河南",2027)
                with self.assertRaisesRegex(ValueError, "全文"):
                    prepare(ROOT, blueprint, {"subject":subject,"blueprint_sha256":fingerprint(blueprint),
                                               "reference_scope":"structure_only"}, ROOT / "not-created")

    def test_same_language_gate_catches_template_and_implausible_option(self):
        for subject in ("chinese", "english"):
            with self.subTest(subject=subject):
                reference, paper, doc, review = audit_fixture(subject)
                valid = evaluate_fixture(reference,paper,doc,review)
                self.assertEqual(valid["status"], "accepted")
                paper["questions"][0]["stem"] += " 作为一名AI，让我们一起来思考。"
                doc["items"][0]["distractors"]["D"]["subtle"] = False
                doc["items"][0]["reading_turn"]["span"] = "材料中根本没有的句子"
                failures = evaluate_fixture(reference,paper,doc,review)["failures"]
                self.assertEqual({r["rule"] for r in failures}, {"language","distractors","depth"})

    def test_classical_register_and_unbound_material(self):
        reference,paper,doc,review = audit_fixture("chinese")
        paper["questions"][0]["section"]="classical"
        paper["materials"]["m"]["text"] += "不由得感慨。"
        doc["items"][0]["language_style"]["classical_checked"]=True
        self.assertTrue(any("白话拟古" in r["reason"]
                            for r in evaluate_fixture(reference,paper,doc,review)["failures"]))
        paper["questions"][0].pop("material")
        self.assertTrue(any(r["rule"]=="depth"
                            for r in evaluate_fixture(reference,paper,doc,review)["failures"]))

    def test_math_checks_the_observed_route_and_three_dimensional_figure(self):
        reference,paper,doc,_ = audit_fixture("math")
        reference["benchmark_slots"]={"1":16}
        doc["reference_sha256"]=fingerprint(reference)
        paper["benchmark_slots"]={"1":16}
        q = paper["questions"][0]
        q.update(kind="constructed_response", module="立体几何", stem="如图，证明线面平行。", options={})
        row = doc["items"][0]
        row.update(math_depth={"linked_turns":["建立表示","用先前关系比较"],
                               "routine_shortcut_rejected":"只读图不能证明"},
                   distractors={})
        row["findings"]["distractors"]["verdict"]="not_applicable"
        review = {"questions":[{"number":1,"moves":[{"kind":"routine_algebra","evidence":"代入"}]}]}
        failures = evaluate_fixture(reference,paper,doc,review)["failures"]
        self.assertEqual({r["rule"] for r in failures},{"figure","depth"})
        q["figure"]={"type":"wireframe"}
        row["findings"]["figure"]["verdict"]="pass"
        row["required_figure_information"]="图给定AB长度及投影的位置。"
        review["questions"][0]["moves"] += [
            {"kind":"representation","evidence":"建立棱柱坐标"},
            {"kind":"invariant","evidence":"法向固定","after":[2]},
        ]
        self.assertEqual(evaluate_fixture(reference,paper,doc,review)["status"],"accepted")


class MathTrendPilot(unittest.TestCase):
    def test_frozen_evidence_and_v3_are_cross_bound(self):
        actual = validate_snapshot(ROOT)
        self.assertEqual(digest(ROOT / V3), V3_SHA256)
        self.assertEqual(digest(ROOT / SNAPSHOT), "0d7d54bd820d4f572aba59f3e6e7e5346ae55cad0e55696d55ebad0b955ed8a0")
        self.assertEqual(len(read_json(ROOT / SIGNALS / "position-comparison.json")["papers"]),5)
        self.assertEqual(sum(e["decision"] == "abstain" for e in actual["entries"]),3)

    def test_after_exam_scoring_requires_two_markers_in_the_same_item(self):
        snapshot = validate_snapshot(ROOT)
        allowed = {n for e in snapshot["entries"] if e["decision"]=="register" for n in e["criterion"]["positions"]}
        packet = {"target":snapshot["target"],"published":"2027-06-07",
                  "source_url":"https://example.test/synthetic","nineteen_item_structure":True,
                  "items":[{"number":n,"locator":f"合成验证第{n}题","reasoning":"该记录只测试规则。",
                            "markers":["reuse_previous_relation"] if n==18 else
                                      ["feasibility_proof"] if n==19 else []}
                           for n in sorted(allowed)]}
        result = score(snapshot,packet)
        self.assertEqual(result["entries"][0]["verdict"],"落空")
        packet["items"][-1]["markers"].append("reuse_previous_relation")
        self.assertEqual(score(snapshot,packet)["entries"][0]["matching_numbers"],[19])
        stale = {**packet,"published":"2026-06-07"}
        with self.assertRaisesRegex(ValueError, "考后"):
            score(snapshot,stale)
        self.assertEqual(score(snapshot,{**packet,"nineteen_item_structure":False})["entries"],[])

    def test_trend_slot_does_not_accept_the_wrong_kind(self):
        reference = {"slots":{"14":{"2025":{"kind":"fill_in"}}}}
        candidate = {"paper":{"edition":"trend_pack"},"quality_benchmarks":{"benchmark_slots":{"1":14}},
                     "questions":[{"order":1,"kind":"multiple_choice"}]}
        with self.assertRaisesRegex(ValueError,"题型"):
            bind_pack_positions(reference,candidate)
        fixed = copy.deepcopy(candidate)
        fixed["questions"][0]["kind"]="fill_in"
        self.assertEqual(bind_pack_positions(reference,fixed)["slots"],{"1":reference["slots"]["14"]})


if __name__ == "__main__":
    unittest.main()
