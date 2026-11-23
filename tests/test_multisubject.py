"""Cross-subject regression tests using originals and an explicitly synthetic fixture."""

from contextlib import closing
import copy
from pathlib import Path
import shutil
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap  # noqa: F401
from analysis_db import fingerprint
from core.catalog import DATA, import_science, query, rebuild, use
from core.science_forecast import forecast, score
from core.science_workflow import adjudicate, plan, prepare, publish, same_answer
from gaokao import digest, read_json
from local_archive import public_edition, write_bundle
from national_db import available as math_available
from subjects import SCIENCES, science_verifier


def example(subject, filename="candidates.json"):
    return read_json(ROOT / "experiments/phase13" / subject / filename)


class MultisubjectTests(unittest.TestCase):
    def test_exam_year_province_and_legacy(self):
        for subject in SCIENCES:
            with self.subTest(subject=subject):
                exact, = use(ROOT, subject, "河南", 2026)
                self.assertEqual((exact["status"], exact["points"], exact["minutes"]),
                                 ("historical_selective", 100, 75))
                sections = plan(ROOT, subject, "河南", 2026, "standard")["structure"]["sections"]
                self.assertEqual(sum(x["points"] for x in sections), 100)
                self.assertEqual(use(ROOT, subject, "河南", 2024)[0]["status"], "historical_component")
                future = plan(ROOT, subject, "河南", 2027, "standard")
                self.assertEqual(future["structure_year"], 2026)
                self.assertEqual(future["structure"]["sections"], sections)
                for region, year in (("河北",2026),("河南",2024)):
                    with self.assertRaises(ValueError):
                        plan(ROOT, subject, region, year, "standard")

    def test_solvers_and_cross_subject_rejection(self):
        for subject in SCIENCES:
            questions = example(subject)["questions"]
            for q in questions:
                with self.subTest(question=q["id"]):
                    actual = science_verifier(subject)(q["problem"])
                    self.assertTrue(same_answer(actual["answer"], q["proposed_answer"]))
                    self.assertTrue(actual["checks"])
                    for other in set(SCIENCES) - {subject}:
                        with self.assertRaises((ValueError,KeyError)):
                            science_verifier(other)(q["problem"])
        self.assertTrue(same_answer(12,12.0))
        self.assertFalse(same_answer(True,1))

    def test_reject_unsupported_assumptions(self):
        for subject in SCIENCES:
            with self.subTest(subject=subject):
                q = example(subject)["questions"][0]["problem"]
                q["op"] = "unknown"
                with self.assertRaises((ValueError, KeyError)):
                    science_verifier(subject)(q)

    def test_stage_bound_to_rendered_version(self):
        candidate = example("physics")
        review = example("physics","review.json")
        with TemporaryDirectory() as temp:
            out = Path(temp) / "exercise"
            blueprint = plan(ROOT,"physics","河南",2026)
            broken = copy.deepcopy(candidate)
            broken["questions"][0]["proposed_answer"] = {"velocity_m_s":4}
            with self.assertRaises(ValueError):
                prepare(ROOT,blueprint,broken,out)
            prepared = prepare(ROOT,blueprint,candidate,out)
            review = {**review, "paper_version": prepared["paper_version"]}
            with self.assertRaises(OSError):
                publish(out,{})
            with self.assertRaises(ValueError):
                adjudicate(out,{**review,"paper_version":"0"*64})
            adjudicate(out,review)
            from pypdf import PdfReader

            artifact = example("physics","publication.json")["visual"]
            fresh = {**artifact, "paper_version": prepared["paper_version"]}
            for kind in ("paper", "solutions"):
                pdf = out / f"{kind}.pdf"
                fresh[f"{kind}_sha256"] = digest(pdf)
                fresh[f"{kind}_pages"] = len(PdfReader(pdf).pages)
            with self.assertRaisesRegex(ValueError, "PDF版本或页数不符"):
                publish(out, {**fresh, "paper_sha256": "0"*64})
            self.assertEqual(publish(out,fresh)["status"],"project_practice_independently_reviewed")

    def test_committed_pdf_and_versions(self):
        for subject in SCIENCES:
            receipt = example(subject,"publication.json")
            self.assertEqual(receipt["review_sha256"],fingerprint(example(subject,"review.json")))
            self.assertEqual(receipt["verification_sha256"],fingerprint(example(subject,"verification.json")))
            for label in ("paper","solutions"):
                path = ROOT / "experiments/phase13" / subject / (label+".pdf")
                self.assertEqual(receipt["visual"][label+"_sha256"],digest(path))

    def test_forecast_does_not_pool_subjects_or_year_duplicates(self):
        mapping, = use(ROOT,"physics","河南",2026)
        series = mapping["series_id"]
        observation = {"year":2026,"available_on":"2026-06-20","paper_id":mapping["paper_id"],
                       "review_state":"independently_coded","version_sha256":"a"*64,
                       "source_url":"https://example.invalid/synthetic",
                       "values":{"physics:mechanics":1}}
        doc = {"subject":"physics","region":"河南","series_id":series,
               "targets":["physics:mechanics"],"observations":[observation]}
        snapshot = forecast(ROOT,"physics","河南",2027,"2026-11-10",doc)
        self.assertIsNone(snapshot["payload"]["predictions"][0]["p"])
        self.assertEqual(snapshot["payload"]["predictions"][0]["observed_rate"],1)
        self.assertEqual(snapshot["payload"]["scored_cases"],0)
        for override in ({"region":"河北"},{"subject":"biology"},{"targets":["math:mechanics"]},
                         {"observations":[observation,observation]}):
            with self.assertRaises(ValueError):
                forecast(ROOT,"physics","河南",2027,"2026-11-10",{**doc,**override})
        with self.assertRaises(ValueError):
            score(snapshot,{"subject":"biology"})

    def test_local_rights_and_quarantine(self):
        with TemporaryDirectory() as temp:
            parent = Path(temp)
            root = parent / "project"
            (root / DATA).mkdir(parents=True)
            shutil.copyfile(ROOT / DATA / "catalog.json",root / DATA / "catalog.json")
            mapping, = use(root,"physics","河南",2026)
            pid = mapping["paper_id"]
            paper = {"id":pid,"subject":"physics","year":2026,"series_id":mapping["series_id"],
                     "exam_system_id":"new-3+1+2","question_count":1,"component":"selective_provincial",
                     "region_id":"河南","authoring_body":"河南省","reported_name":"仅供软件测试的模拟登记"}
            rel = {"paper_id":pid,"subject":"physics","year":2026,"region_id":"河南",
                   "exam_system_id":"new-3+1+2","evidence":["hn-2026"]}
            q = {"id":"synthetic:physics:test","stem":"用于软件测试的合成题。","options":{},"parts":[],
                 "formulas":[],"asset_refs":[],"content_complete":True,"review_status":"quarantined"}
            version = fingerprint(q)
            source = {"id":"test-local","rights":"unresolved","rights_basis":"项目自建测试数据"}
            tables = {"papers":[paper],"paper-regions":[rel],"sources":[source],"questions":[q],
                      "occurrences":[{"id":"test:occ","paper_id":pid,"question_id":q["id"],"number":1,
                       "points":4,"kind":"fill_in","version_sha256":version,"answer_id":"test:ans",
                       "source_locator":{"source_id":"test-local","page":1}}],
                      "answers":[{"id":"test:ans","occurrence_id":"test:occ","version_sha256":version,
                                  "payload":{"answer":"2"}}]}
            bundle = parent/"bundle"
            bundle.mkdir()
            write_bundle(bundle,"synthetic-physics","local-only",tables)
            with self.assertRaises(ValueError):
                import_science(root,bundle)
            source["rights"] = "local_copy_authorized"
            write_bundle(bundle,"synthetic-physics","local-only",tables)
            self.assertEqual(import_science(root,bundle),{"installed":1,"quarantined":1})
            self.assertEqual(query(root,"physics"),[])
            with self.assertRaises(ValueError):
                import_science(root,bundle)

    def test_relational_index_preserves_existing_math_ids(self):
        with TemporaryDirectory() as temp:
            target = Path(temp) / "view.sqlite"
            report = rebuild(ROOT,target)
            self.assertTrue(report["foreign_keys_valid"])
            self.assertEqual(report["subjects"],6)
            if public_edition(ROOT):
                self.assertEqual(report["science"],0)
            else:
                from core.paper_intake import documents
                from subjects import SCIENCES
                tracked = sum(len(paper["questions"]) for subject in SCIENCES for _,paper in documents(ROOT,subject))
                self.assertEqual(report["science"],19+tracked)
                expected = math_available(ROOT)
                self.assertEqual(report["math_archive_available"],expected)
                self.assertEqual(report["math"],496 if expected else 0)
                self.assertEqual(report["math_version_binding"] is not None,expected)
            with closing(sqlite3.connect(target)) as db:
                n = db.execute("SELECT count(*) FROM answer a JOIN question q ON a.question_id=q.id AND a.version=q.version").fetchone()[0]
                self.assertGreater(n,0)
                generated = db.execute("SELECT count(*) FROM entity WHERE kind='GeneratedQuestion'").fetchone()[0]
                self.assertEqual(generated,19)
                if not public_edition(ROOT) and tracked:
                    record=db.execute("SELECT subject, number FROM question WHERE id=?",
                        ("2025-ha-physics-adaptation:q001",)).fetchone()
                    self.assertEqual(record,("physics",1))


if __name__ == "__main__":
    unittest.main()
