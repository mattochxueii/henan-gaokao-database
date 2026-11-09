"""Key-free public runtime tests. Import fixtures use project-authored data."""

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gaokao import digest, read_json, read_lines
from local_archive import install, read_bundle
from local_data import prepare
from national_db import query, sqlite_query, validate
from mathgen.planner import context, plan


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "database"
        self.root.mkdir()
        for name in ("sample-data", "analysis", "national"):
            shutil.copytree(ROOT / name, self.root / name)
        shutil.copyfile(ROOT / "database.json", self.root / "database.json")

    def document(self):
        _, tables, rows = read_bundle(self.root / "sample-data")
        paper = {**tables["papers"][0], "id": "local:proof", "question_count": 1}
        row = {
            **rows[0],
            "id": "local:proof:q001",
            "occurrence_id": "local:proof:001",
            "paper_id": paper["id"],
            "source_locator": {"source_id": "local:test", "page": 1},
        }
        return {
            "dataset_id": "local-proof-v1",
            "papers": [paper],
            "sources": [{"id": "local:test", "kind": "test_authored"}],
            "records": [row],
        }

    def test_key_free_query(self):
        self.assertEqual(validate(self.root)["question_occurrences"], 5)
        (row,) = sqlite_query(self.root, 2026, "project-original", 1)
        self.assertEqual(row["record_origin"], "original_sample")
        self.assertTrue(row["stem"] and row["answer"]["explanation"])
        self.assertEqual(query(self.root, series="cn-new-gaokao-1"), [])
        catalogue = list(read_lines(self.root / "national/source-catalog.jsonl"))
        self.assertGreaterEqual(len(catalogue), 23)
        self.assertTrue(
            all(
                p["availability"] == "source_only" and p["bundled_questions"] == 0
                for p in catalogue
            )
        )

    def test_import_updates_index_and_rejects_duplicate(self):
        self.assertEqual(len(sqlite_query(self.root, 2026, "project-original", 1)), 1)
        path = Path(self.tmp.name) / "bundle"
        prepare(self.document(), path)
        install(self.root, path)
        self.assertEqual(len(sqlite_query(self.root, 2026, "project-original", 1)), 2)
        with self.assertRaises(ValueError):
            install(self.root, path)

    def test_old_version_with_resealed_file_is_rejected(self):
        path = Path(self.tmp.name) / "bundle"
        prepare(self.document(), path)
        question = path / "questions.jsonl"
        (row,) = read_lines(question)
        question.write_text(
            json.dumps({**row, "stem": "不同题面"}) + "\n", encoding="utf-8"
        )
        manifest = read_json(path / "manifest.json")
        item = next(x for x in manifest["files"] if x["path"] == "questions.jsonl")
        item.update(sha256=digest(question), bytes=question.stat().st_size)
        (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "题面版本与内容不符"):
            install(self.root, path)

    def test_tampered_seed_blocks_cached_query(self):
        sqlite_query(self.root, 2026, "project-original", 1)
        file = self.root / "sample-data/questions.jsonl"
        file.write_bytes(file.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "校验失败"):
            sqlite_query(self.root, 2026, "project-original", 1)

    def test_unregistered_source_rejected(self):
        path = Path(self.tmp.name) / "bundle"
        doc = copy.deepcopy(self.document())
        doc["sources"] = []
        with self.assertRaisesRegex(ValueError, "来源未登记"):
            prepare(doc, path)
        self.assertFalse(path.exists())

    def test_six_subject_components(self):
        from national_schema import validate_paper

        base = {"id": "fixture", "year": 2026, "series_id": "fixture-series"}
        details = {
            "math": {"track": "unified"},
            "chinese": {},
            "english": {"component": "speaking_listening"},
            "physics": {
                "component": "selective_provincial",
                "region_id": "河南",
                "authoring_body": "fixture",
            },
            "chemistry": {
                "component": "composite_section",
                "parent_paper_id": "fixture-parent",
            },
            "biology": {
                "component": "composite_section",
                "parent_paper_id": "fixture-parent",
            },
        }
        for subject, attributes in details.items():
            with self.subTest(subject=subject):
                self.assertTrue(
                    validate_paper({**base, "subject": subject, **attributes})
                )

    def test_api_context_excludes_import(self):
        path = Path(self.tmp.name) / "bundle"
        prepare(self.document(), path)
        install(self.root, path)
        local = context(self.root)["national_archive"]
        remote = context(self.root, include_local=False)["national_archive"]
        self.assertIn("local:proof", {p["id"] for p in local["papers"]})
        self.assertNotIn("local:proof", {p["id"] for p in remote["papers"]})
        self.assertNotIn("bounded_reference_packs", remote)
        self.assertEqual(plan(self.root, "full")["total_points"], 150)


if __name__ == "__main__":
    unittest.main()
