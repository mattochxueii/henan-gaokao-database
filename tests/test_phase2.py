import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap
from cryptography.fernet import Fernet, InvalidToken
from analysis_db import research, rules, fingerprint
from gaokao import read_json
from storage import backup, restore, inventory
from mathgen.generate import FAMILIES, draft, add_options
from mathgen.pipeline import blueprint, structure_check, run, custom_blueprint
from mathgen.quality import (
    verify,
    assert_fresh,
    duplicate_check,
    equation_cardinality,
    expression,
)

WORK = ROOT.parents[1] / "work"
WORK.mkdir(exist_ok=True)


class DatabaseResearchTests(unittest.TestCase):
    def test_tracked_files_have_no_credentials(self):
        from security_scan import scan_blob

        token = Fernet.generate_key()
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=ROOT, text=True
        ).split("\0")
        paths = {ROOT / p for p in tracked if p and (ROOT / p).is_file()}
        for path in paths:
            report = scan_blob(
                path.relative_to(ROOT).as_posix(), path.read_bytes(), (token,)
            )
            self.assertTrue(
                report["passed"], report["path"] + ":" + ",".join(report["codes"])
            )

    def test_all_38_have_content_and_bound_analysis(self):
        rows = research(ROOT)
        self.assertEqual(len(rows), 38)
        for q in rows:
            self.assertTrue(q["candidate"]["stem"])
            self.assertEqual(
                q["analysis"]["candidate_sha256"], fingerprint(q["candidate"])
            )
            self.assertFalse(q["curation"]["official_exam_body_confirmed"])
            self.assertEqual(len(q["analysis"]["evidence"]), 1)

    def test_sequence_research_uses_actual_knowledge(self):
        rows = research(ROOT, topic="数列")
        self.assertEqual(
            {q["id"] for q in rows},
            {
                "2025-cn-math-national-1:q013",
                "2025-cn-math-national-1:q016",
                "2026-cn-math-national-1:q007",
                "2026-cn-math-national-1:q014",
            },
        )
        self.assertIn(
            "a_{n+1}",
            next(q for q in rows if q["id"].endswith("q016"))["candidate"]["stem"],
        )

    def test_version_specific_answers_and_conflicts(self):
        rows = {q["id"]: q for q in research(ROOT)}
        self.assertEqual(
            rows["2025-cn-math-national-1:q004"]["curation"][
                "answer_for_current_candidate"
            ]["option"],
            "C",
        )
        self.assertEqual(
            rows["2026-cn-math-national-1:q009"]["curation"][
                "answer_for_current_candidate"
            ]["option"],
            "ACD",
        )
        self.assertIn(
            "Q",
            rows["2026-cn-math-national-1:q018"]["candidate"]["subquestions"][1][
                "text"
            ],
        )
        self.assertIn(
            "P在第三象限",
            rows["2026-cn-math-national-1:q018"]["curation"]["version_conflict"][
                "finding"
            ],
        )

    def test_rule_evidence_classes(self):
        r = rules(ROOT)
        classes = {v["class"] for v in r["requirements"]}
        self.assertTrue(
            {
                "official_requirement",
                "direct_candidate_fact",
                "limited_sample_observation",
                "unverified_hypothesis",
                "simulation_setting",
            }
            <= classes
        )
        self.assertFalse(r["blueprint"]["official_2027_structure_verified"])

    def test_every_comparison_is_version_bound(self):
        rows = {q["id"]: q for q in research(ROOT)}
        for item in rows.values():
            comparison = item["analysis"]["comparison"]
            other = rows[comparison["related_ids"][0]]
            self.assertEqual(
                comparison["related_candidate_sha256"], fingerprint(other["candidate"])
            )
            self.assertTrue(comparison["similarity"])
            self.assertTrue(comparison["difference"])

    def test_priority_symbolic_audit_bound_to_candidates(self):
        rows = {q["id"]: q for q in research(ROOT)}
        checks = read_json(ROOT / "tests/fixtures/original-math-checks.json")["checks"]
        self.assertEqual(len(checks), 10)
        for check in checks:
            self.assertTrue(check["passed"])
            self.assertEqual(
                check["candidate_sha256"],
                fingerprint(rows[check["question_id"]]["candidate"]),
            )


class MathematicalTests(unittest.TestCase):
    def test_every_registered_family_at_multiple_seeds(self):
        for seed in (17, 37, 101, 20261107):
            for family in FAMILIES:
                with self.subTest(family=family, seed=seed):
                    kind = (
                        "multiple_choice"
                        if family in ("geometry_assertions", "logquad_assertions")
                        else "constructed_response"
                    )
                    q = add_options(draft(family, seed, kind), seed + 1)
                    self.assertTrue(verify(q)["passed"])

    def test_single_multiple_fill_and_constructed(self):
        for kind, family in [
            ("single_choice", "complex_norm"),
            ("multiple_choice", "seq_interlace"),
            ("fill_in", "exp_peak"),
            ("constructed_response", "deriv_logroots"),
        ]:
            q = add_options(draft(family, 11, kind), 12)
            self.assertTrue(verify(q)["passed"])

    def test_wrong_answer_rejected_and_fresh_revision_verified(self):
        q = add_options(draft("seq_reciprocal", 13), 14)
        bad = copy.deepcopy(q)
        bad["proposed_values"][0] = "999"
        self.assertFalse(verify(bad)["passed"])
        repaired = add_options(draft("seq_reciprocal", 10020), 10021)
        self.assertTrue(verify(repaired)["passed"])
        self.assertNotEqual(fingerprint(bad), fingerprint(repaired))

    def test_modification_invalidates_old_verification(self):
        q = add_options(draft("complex_norm", 13), 14)
        result = verify(q)
        q["stem"] += "附加未审条件"
        with self.assertRaisesRegex(ValueError, "重新求解"):
            assert_fresh(q, result)
        self.assertFalse(verify(q)["passed"])

    def test_ambiguous_duplicate_option_rejected(self):
        q = add_options(draft("complex_norm", 13, "single_choice"), 14)
        keys = list(q["options"])
        q["options"][keys[1]] = copy.deepcopy(q["options"][keys[0]])
        self.assertFalse(verify(q)["passed"])

    def test_missing_or_changed_condition_rejected(self):
        q = add_options(draft("tetrahedron", 13), 14)
        q["parameters"]["a"] = 0
        with self.assertRaises(Exception):
            verify(q)

    def test_real_no_solution_and_multiple_solution_detection(self):
        self.assertEqual(equation_cardinality("x*x+1")["state"], "no_solution")
        self.assertEqual(equation_cardinality("x*x-1")["state"], "multiple")
        self.assertEqual(equation_cardinality("x*x")["state"], "unique")

    def test_expression_rejects_code(self):
        for text in (
            "__import__('os').system('whoami')",
            "sqrt(x,1)",
            "x.__class__",
            "2**999999",
        ):
            with self.assertRaises((ValueError, SyntaxError)):
                expression(text)

    def test_duplicate_detection_ignores_numeric_substitution(self):
        q = add_options(draft("complex_norm", 11), 12)
        same = copy.deepcopy(q)
        same["id"] = "orig:previous"
        same["stem"] = same["stem"].replace("求", "求")
        self.assertFalse(duplicate_check(q, [], [same])["passed"])
        changed = add_options(draft("complex_norm", 37), 38)
        self.assertFalse(duplicate_check(changed, [], [same])["passed"])

    def test_150_points_structure_and_bad_score_rejected(self):
        plan = blueprint(ROOT, "full")
        qs = [
            add_options(
                draft(slot["family"], 100 + i, slot["kind"], slot["points"]), 101 + i
            )
            for i, slot in enumerate(plan["slots"])
        ]
        self.assertEqual(structure_check(plan, qs)["points"], 150)
        qs[-1]["points"] = 1
        with self.assertRaises(ValueError):
            structure_check(plan, qs)

    def test_custom_topic_type_count_difficulty(self):
        plan = custom_blueprint(ROOT, "导数", 1, "constructed_response", 4)
        self.assertEqual(len(plan["slots"]), 1)
        self.assertEqual(FAMILIES[plan["slots"][0]["family"]][1], 4)
        self.assertEqual(
            custom_blueprint(ROOT, "等比数列", 1, "constructed_response", 4)["slots"][
                0
            ]["family"],
            "seq_alternating",
        )
        with self.assertRaises(ValueError):
            custom_blueprint(ROOT, "数列", 20, "single_choice", None)

    def test_every_delivered_question_reverified(self):
        for folder in ("sequence", "derivative", "mixed", "full"):
            record = read_json(ROOT / "tests/fixtures" / folder / "run.json")
            for q, v in zip(record["questions"], record["verifications"]):
                with self.subTest(q=q["id"]):
                    assert_fresh(q, v)
                    self.assertTrue(verify(q)["passed"])


class PrivateStorageTests(unittest.TestCase):
    def test_concurrent_backups_do_not_replace_the_winner(self):
        from concurrent.futures import ThreadPoolExecutor

        with tempfile.TemporaryDirectory(dir=WORK) as folder:
            directory = Path(folder)
            source = directory / "source"
            source.mkdir()
            (source / "manifest.json").write_text("{}", encoding="utf-8")
            archive = directory / "backup.enc"

            def attempt(number):
                key = directory / f"key-{number}.key"
                try:
                    return key, backup(source, archive, key)
                except (OSError, ValueError):
                    return None

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(attempt, (1, 2)))
            winners = [result for result in results if result]
            self.assertEqual(len(winners), 1)
            self.assertEqual(len(list(directory.glob("*.key"))), 1)
            key, record = winners[0]
            restore(archive, key, directory / "restored", record["files"])

    def test_backup_roundtrip_and_wrong_key(self):
        with tempfile.TemporaryDirectory(dir=WORK) as folder:
            directory = Path(folder)
            source = directory / "source"
            source.mkdir()
            (source / "manifest.json").write_text('{"test":true}', encoding="utf-8")
            (source / "q.json").write_text('{"stem":"合成测试"}', encoding="utf-8")
            archive = directory / "test.enc"
            key = directory / "test.key"
            result = backup(source, archive, key)
            restored = directory / "restored"
            restore(archive, key, restored, result["files"])
            self.assertEqual(inventory(source), inventory(restored))
            wrong = directory / "wrong.key"
            wrong.write_bytes(Fernet.generate_key())
            with self.assertRaises(InvalidToken):
                restore(archive, wrong, directory / "bad")

    def test_restore_rejects_escape_and_preserves_existing(self):
        with tempfile.TemporaryDirectory(dir=WORK) as folder:
            directory = Path(folder)
            key = Fernet.generate_key()
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as z:
                z.writestr("../escape.txt", "bad")
            archive = directory / "bad.enc"
            archive.write_bytes(Fernet(key).encrypt(buffer.getvalue()))
            keyfile = directory / "key"
            keyfile.write_bytes(key)
            with self.assertRaises(ValueError):
                restore(archive, keyfile, directory / "new")
            self.assertFalse((directory / "escape.txt").exists())
            directory.joinpath("existing").mkdir()
            with self.assertRaises(ValueError):
                restore(archive, keyfile, directory / "existing")

    def test_inventory_mismatch_rejected(self):
        with tempfile.TemporaryDirectory(dir=WORK) as folder:
            directory = Path(folder)
            source = directory / "source"
            source.mkdir()
            (source / "manifest.json").write_text("{}")
            archive = directory / "data.enc"
            key = directory / "key"
            backup(source, archive, key)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                restore(archive, key, directory / "target", [])
            self.assertFalse((directory / "target").exists())

    def test_relocated_skill_and_plaintext_database_need_no_recovery_key(self):
        with tempfile.TemporaryDirectory(prefix="relocated-", dir=WORK) as folder:
            checkout = Path(folder) / "checkout"
            for name in ("data","scripts","skills"):
                shutil.copytree(ROOT/name,checkout/name,ignore=shutil.ignore_patterns("__pycache__"))
            if (ROOT/".deps").is_dir():
                shutil.copytree(ROOT/".deps",checkout/".deps")
            def command(*args):
                result = subprocess.run(
                    [sys.executable,*map(str,args)],cwd=checkout,capture_output=True,encoding="utf-8"
                )
                self.assertEqual(result.returncode,0,result.stderr)
                return json.loads(result.stdout)

            destination = checkout/".agents"/"skills"
            command("scripts/install_skill.py","--destination",destination)
            runner = destination/"gaokao-platform/scripts/run.py"
            (row,) = command(runner,"research","math","--year",2025,"--region","河南","--limit",1)
            self.assertIn("5i",row["stem"])
            self.assertEqual(row["year"],2025)
            self.assertFalse((checkout/".private").exists())
            made=command(runner,"math","generate","--engine","template","--allow-legacy-template","--mode","sequence","--seed",20261123,
                         "--no-export","--output","scratch/sequence")
            self.assertEqual(made["structure"]["questions"],5)
            verified=command(runner,"math","verify","scratch/sequence/run.json")
            self.assertTrue(all(row["passed"] for row in verified))


class OutputTests(unittest.TestCase):
    def test_eight_pdfs_text_and_page_bounds(self):
        from pypdf import PdfReader

        for name in ("sequence", "derivative", "mixed", "full"):
            directory = ROOT / "tests/fixtures" / name
            for kind in ("paper", "solutions"):
                reader = PdfReader(directory / (kind + ".pdf"))
                self.assertGreater(len(reader.pages), 0)
                text = "\n".join(page.extract_text() for page in reader.pages)
                self.assertIn("河南", text)
                self.assertNotIn("Traceback", text)
                for page in reader.pages:
                    self.assertAlmostEqual(
                        float(page.mediabox.width), 595.2756, places=2
                    )
                    self.assertGreater(
                        len(page.extract_text().strip()), 80, "发现只剩页脚的空白页"
                    )
            self.assertTrue((directory / "paper.md").is_file())

    def test_unicode_subscripts_have_explicit_layout_markup(self):
        from mathgen.export import formatted_plain

        self.assertEqual(
            formatted_plain("aₙ₊₁=x³"), "a<sub>n+1</sub>=x<super>3</super>"
        )
        self.assertEqual(formatted_plain("S=3/4−1/n"), "S=3/4-1/n")
