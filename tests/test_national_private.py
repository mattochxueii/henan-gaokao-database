"""Private integration checks; CI does not require owner keys or plaintext."""

import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap  # noqa: F401
import national_db as db
from gaokao import read_lines
from analysis_db import fingerprint


@unittest.skipUnless(db.available(ROOT), "全国私有数据未恢复")
class NationalPrivateTests(unittest.TestCase):
    def test_inventory_and_legacy(self):
        result = db.validate(ROOT)
        self.assertTrue(result["legacy_38_preserved"])
        self.assertEqual(result["new_occurrences"], 458)

    def test_I_is_continuous_and_full(self):
        filters = {"series": "cn-new-gaokao-1", "year_from": 2020, "year_to": 2026}
        rows = db.query(ROOT, **filters, include_quarantined=True)
        self.assertEqual({r["year"] for r in rows}, set(range(2020, 2027)))
        self.assertEqual(len(rows), 145)
        self.assertTrue(all(r["stem"] and r["source_locator"] for r in rows))
        strict = db.query(ROOT, **filters, verified_only=True)
        self.assertGreaterEqual(len(strict), 136)
        self.assertEqual(
            {r["occurrence_id"] for r in rows} - {r["occurrence_id"] for r in strict},
            {r["occurrence_id"] for r in rows if r.get("calibration", {}).get("body") == "pdf_conflict"},
        )

    def test_II_has_seven_years(self):
        rows = db.query(ROOT, series="cn-new-gaokao-2")
        self.assertEqual(len(rows), 145)
        self.assertEqual({r["year"] for r in rows}, set(range(2020, 2027)))

    def test_conflicted_paper_excluded_not_deleted(self):
        safe = db.query(ROOT, year=2023, series="cn-national-b")
        all_rows = db.query(
            ROOT, year=2023, series="cn-national-b", include_quarantined=True
        )
        self.assertEqual(len(safe), 23)
        self.assertEqual(len(all_rows), 46)
        self.assertTrue(all(r["track"] == "liberal" for r in safe))

    def test_source_answers_all_bound_without_authority_upgrade(self):
        rs = [r for r in db.rows(ROOT, calibrated=False) if not r["legacy"]]
        for r in rs:
            self.assertEqual(
                r["answer"]["question_version_sha256"], r["version_sha256"]
            )
            self.assertEqual(r["answer"]["authority"], "third_party")
            self.assertTrue(
                r["answer"]["reference_answer"] or r["answer"]["explanation"]
            )

    def test_annotations_are_bound(self):
        rs = db.rows(ROOT, calibrated=False)
        bound = [r for r in rs if r.get("national_analysis")]
        self.assertEqual(len(bound), 29)
        for r in bound:
            self.assertEqual(
                r["version_sha256"], r["national_analysis"]["version_sha256"]
            )

    def test_actual_reference_cap_and_no_old_blueprint(self):
        pack = db.reference_pack(ROOT, topic="数列", limit=20)
        from collections import Counter

        self.assertLessEqual(
            max(Counter(r["paper_id"] for r in pack["references"]).values()), 2
        )
        self.assertTrue(
            all(r.get("research_eligible", True) for r in pack["references"])
        )
        self.assertEqual(pack["target"]["primary_series"], "cn-new-gaokao-1")

    def test_sqlite_shared_master_keeps_occurrence_provenance(self):
        db.rebuild_index(ROOT)
        a = db.sqlite_query(ROOT, 2020, "cn-new-gaokao-1", 21)[0]
        b = db.sqlite_query(ROOT, 2020, "cn-new-gaokao-2", 22)[0]
        self.assertEqual(a["question_id"], b["question_id"])
        self.assertEqual(a["number"], 21)
        self.assertEqual(b["number"], 22)
        self.assertNotEqual(
            a["source_locator"]["pdf"]["path"], b["source_locator"]["pdf"]["path"]
        )
        self.assertTrue(b["parts"] and b["answer"]["explanation"])

    def test_all_original_ids_still_exist(self):
        old = list(read_lines(ROOT / "analysis/questions.jsonl"))
        actual = db.legacy_rows(ROOT)
        self.assertEqual({r["question_id"] for r in old}, {r["id"] for r in actual})
        for r in actual:
            self.assertEqual(fingerprint(r["candidate"]), r["version_sha256"])


if __name__ == "__main__":
    unittest.main()
