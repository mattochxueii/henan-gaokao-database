import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analysis_db import fingerprint
from core.quality_audit import RULES, VERSION, bound_reference, evaluate, position_reference, publication_quality, submit
from gaokao import digest
from storage import atomic_json


class EditorialGateTests(unittest.TestCase):
    def setUp(self):
        self.reference = {"protocol":VERSION,"subject":"physics","slots":{
            str(n): {str(year):{"version_sha256":str(year)*16} for year in (2025,2026)}
            for n in range(1,5)
        }}
        self.paper = {"questions":[
            {"id":f"q{n}","kind":"single_choice","stem":f"题目 {n}",
             "options":dict(zip("ABCD",("0.50","1.00","1.50","2.00"))),"figure":n==4}
            for n in range(1,5)
        ],"quality_reference_sha256":fingerprint(self.reference)}
        self.review = {"items":[{"id":f"q{n}","answer":"A"} for n in reversed(range(1,5))]}
        self.pdf = b"fixture"
        self.doc = {"protocol":VERSION,"reference_sha256":fingerprint(self.reference),
                    "paper_version":fingerprint(self.paper),"reviewer":"editor","items":[]}
        for n in range(1,5):
            self.doc["items"].append({
                "number":n,"answer_key":"A",
                "benchmarks":{year:{**sample,"comparison":"从图中读取拐点再推理守恒。"}
                              for year,sample in self.reference["slots"][str(n)].items()},
                "findings":{rule:{"verdict":"not_applicable" if rule=="figure" and n!=4 else "pass",
                                  "evidence":"证据：横轴和纵轴的刻度给出末态物理量。"} for rule in RULES},
                "depth":{"reasoning_steps":["读横轴的量","用末态反求"],"linked_concepts":["图像","动量定理"]},
                "distractors":{key:{"plausible":True,"misconception":"漏项",
                                    "mechanism":f"{key}按错误的对象取速度。"} for key in "BCD"},
                "required_figure_information":"题干未给出断点处的时刻和速度。",
            })
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"paper.pdf"
            path.write_bytes(self.pdf)
            self.doc["paper_pdf_sha256"]=digest(path)

    def audit(self, *, review=True, prior=None):
        return evaluate(self.reference,self.paper,fingerprint(self.paper),self.doc["paper_pdf_sha256"],self.doc,
                        review=self.review if review else None,prior=prior)

    def test_same_position_candidate_and_original_series_are_bound(self):
        with self.assertRaisesRegex(ValueError,"同题位"):
            bound_reference({"quality_benchmarks":self.reference},{"provenance":{}})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            directory=root/"data/papers/physics"
            directory.mkdir(parents=True)
            for year, kind, region in [(2025,"official_exam","河南"),(2026,"official_exam","河南"),
                                       (2025,"adaptation_exam","河南"),(2026,"official_exam","湖北")]:
                doc={"year":year,"subject":"physics","series_id":"cn-ha-physics-selective","exam_kind":kind,
                     "regions":[region],"id":f"{year}-{kind}-{region}","source":{"url":"https://example.test/exam"},
                     "questions":[{"id":f"{year}-q","number":1,"stem":"测试真题","version_sha256":"v1",
                                   "kind":"single_choice","points":4,"usable_for_practice":year==2025}]}
                doc["content_sha256"]=fingerprint(doc["questions"])
                atomic_json(directory/(doc["id"]+".json"),doc)
            reference=position_reference(root,"physics")
        self.assertEqual(reference["slots"]["1"]["2026"]["scope"],"limited_position_evidence")
        self.assertEqual(len(reference["slots"]["1"]),2)

    def test_wrong_option_paths_fail_even_if_verdict_calls_them_credible(self):
        item=self.doc["items"][3]
        item["distractors"]["B"]["plausible"]=False
        self.review["items"][0]["answer"]="D"
        result=self.audit()
        self.assertEqual(result["status"],"returned")
        self.assertTrue(any(r["rule"]=="distractors" and "B项" in r["reason"] for r in result["failures"]))
        self.assertTrue(any("独立答案" in r["reason"] for r in result["failures"]))

    def test_shallow_and_decorative_draft_requires_changed_item(self):
        item=self.doc["items"][3]
        item["depth"]["reasoning_steps"]=["一步代入"]
        item["findings"]["figure"]={"verdict":"return","evidence":"题干已复述图的全部数据。"}
        first=self.audit(review=False)
        self.assertEqual({r["rule"] for r in first["failures"]},{"figure","depth"})
        item["depth"]["reasoning_steps"].append("比较末态与丢失阶段。")
        item["findings"]["figure"]["verdict"]="pass"
        self.doc["revisions"]={"4":{"figure":"移除条件复述。","depth":"结合两个阶段重新求量。"}}
        self.assertEqual(self.audit(prior=first)["status"],"returned")
        self.paper["questions"][3]["stem"]="改写了题干，采用图中的隐含边界。"
        self.doc["paper_version"]=fingerprint(self.paper)
        self.assertEqual(self.audit(prior=first)["status"],"accepted")

    def test_missing_and_changed_audit_cannot_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/"paper.pdf").write_bytes(self.pdf)
            atomic_json(folder/"blind-packet.json",{"paper":self.paper,"paper_version":self.doc["paper_version"]})
            atomic_json(folder/"verification.json",{"paper_version":self.doc["paper_version"],
                        "paper_pdf_sha256":self.doc["paper_pdf_sha256"],"quality_benchmarks":self.reference})
            with self.assertRaisesRegex(ValueError,"禁止发布"):
                publication_quality(folder,self.review)
            self.assertEqual(submit(folder,self.doc,review=self.review)["status"],"accepted")
            self.assertEqual(publication_quality(folder,self.review),fingerprint(self.doc))
            changed=copy.deepcopy(self.doc)
            changed["items"][0]["findings"]["language"]["verdict"]="return"
            atomic_json(folder/"quality-audit.json",changed)
            with self.assertRaisesRegex(ValueError,"禁止发布"):
                publication_quality(folder,self.review)

    def test_incorrect_source_version_and_weak_language_are_fatal(self):
        self.doc["items"][0]["benchmarks"]["2026"]["version_sha256"]="different"
        self.doc["items"][2]["findings"]["language"]={"verdict":"return","evidence":"重复泄露推导条件。"}
        result=self.audit()
        self.assertEqual({r["rule"] for r in result["failures"]},{"depth","language"})
