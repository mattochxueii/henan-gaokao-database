from copy import deepcopy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import bootstrap
from analysis_db import fingerprint
from core import language_workflow as exam
from core import paper_intake as store
from gaokao import read_json
from pypdf import PdfReader


class CorePapersTest(unittest.TestCase):
    def test_blueprints_and_local_score(self):
        for subject,n,mins in (("chinese",22,150),("english",67,120)):
            by_year=[exam.plan(ROOT,subject,"河南",y) for y in (2024,2025,2026,2027)]
            self.assertEqual(sum(len(s["scores"]) for s in by_year[-1]["sections"]),n)
            self.assertTrue(all(d["minutes"]==mins for d in by_year))
            self.assertEqual(by_year[-1]["basis_year"],2026)
        self.assertEqual(exam.henan_english_score(102),128)
        self.assertEqual(exam.henan_english_score(120),150)
        with self.assertRaises(ValueError):
            exam.henan_english_score(121)

    def test_plaintext_intake_dna_conflict_and_scope(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            paper={"id":"test-2026-cn-zh","subject":"chinese","year":2026,"series_id":"qa-example",
                   "title":"软件验收合成卷","exam_kind":"official_exam","regions":["河南"],"question_count":1,"points":3,
                   "source":{"title":"本项目合成","url":"https://example.invalid","rights_basis":"自创"},
                   "passages":{"a":"图书馆晚上开门。"},"questions":[
                     {"number":1,"kind":"single_choice","points":3,"stem":"何时开门？","passage":"a",
                      "options":{"A":"上午","B":"晚上","C":"下午","D":"中午"},"answer":"B","position":"1","features":["显式信息"]}]}
            drop=deepcopy(paper)
            drop["questions"][0]["stem"]=None
            with self.assertRaises(ValueError):
                store.ingest(root,drop)
            store.ingest(root,paper)
            (q,)=store.research(root,"chinese",region="河南")
            self.assertEqual((q["answer"],q["passage_text"]),("B","图书馆晚上开门。"))
            self.assertEqual(store.dna(root,"chinese")["positions"][1]["features"],{"显式信息":1})
            english={**paper,"id":"test-en-adaptation","subject":"english","exam_kind":"adaptation_exam","written_only":True}
            store.ingest(root,english)
            self.assertFalse(store.research(root,"english"))
            self.assertEqual(len(store.research(root,"english",exam_kind="adaptation_exam")),1)
            with self.assertRaises(ValueError):
                store.ingest(root,english)

    def test_delivered_papers_contain_material_and_reject_wrong_answers(self):
        for subject, count, required in (("chinese",22,"同一条河"), ("english",67,"retired engineers")):
            folder=ROOT/"experiments"/"phase17"/subject
            paper=read_json(folder/"blind-packet.json")["paper"]
            self.assertEqual(len(paper["questions"]),count)
            self.assertEqual(sum(q["points"] for q in paper["questions"]),150)
            text="".join(p.extract_text() for p in PdfReader(folder/"paper.pdf").pages)
            self.assertIn(required,text)
            self.assertNotIn("答案：",text)
            if subject=="english":
                self.assertNotIn("I would have, but the repair shop",text)
                self.assertTrue((folder/"listening-script.pdf").is_file())
            with TemporaryDirectory() as temp:
                tmp=Path(temp)/"draft"
                draft=read_json(folder/"candidate.json")
                result=exam.prepare(ROOT,exam.plan(ROOT,subject,"河南",2026),draft,tmp)
                review=read_json(folder/"independent-review.json")
                self.assertEqual(review["paper_version"],result["paper_version"])
                review["items"][0]["answer"]="Z"
                with self.assertRaisesRegex(ValueError,"答案复核不一致"):
                    exam.review(tmp,review)

    def test_empty_full_paper_rejected(self):
        blueprint=exam.plan(ROOT,"chinese","河南",2026)
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,"题号或分值"):
                exam.prepare(ROOT,blueprint,{"subject":"chinese","blueprint_sha256":fingerprint(blueprint),
                             "reference_scope":"structure_only","reference_notes":["测试"],"questions":[],"materials":{}},Path(temp)/"draft")
