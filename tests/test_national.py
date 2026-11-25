"""Key-free adversarial tests for national ingestion and reference selection."""

import sys, unittest, tempfile, json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap  # noqa: F401
from gaokao import read_json, read_lines
from national_tex import parse, content_signature, subquestion_tree
from national_schema import validate_paper
from national_db import relevance, target, ALIASES
from storage import backup, restore
from cryptography.fernet import InvalidToken
import national_db as db
from national_quality import source_issues, research_eligible


class TexTests(unittest.TestCase):
    def paper(self, body, answer=""):
        return (
            r"\section{单选题}\begin{problem}"
            + body
            + r"\choices{A}{B}{C}{D}"
            + answer
            + r"\end{problem}"
        )

    def test_embedded_answer_never_enters_student_stem(self):
        rows = parse(self.paper("计算题", r"\begin{answer}B\end{answer}"))
        self.assertEqual(rows[0]["reference_answer"], "B")
        self.assertNotIn("answer", rows[0]["stem"])

    def test_answer_after_environment_is_associated(self):
        rows = parse(self.paper("第一题") + r"\begin{answer}A\end{answer}")
        self.assertEqual(rows[0]["reference_answer"], "A")

    def test_braced_solution_is_not_lost(self):
        rows = parse(self.paper("题目") + r"\solution{证明 \(\frac{1}{2}\)}")
        self.assertIn(r"\frac{1}{2}", rows[0]["explanation"])

    def test_nested_choice_braces_are_complete(self):
        text = r"\section{单选题}\begin{problem}求值\choices{\(\frac{1}{2}\)}{\(\sqrt{2}\)}{3}{4}\end{problem}"
        self.assertIn(r"\frac{1}{2}", parse(text)[0]["options"]["A"])

    def test_missing_fourth_choice_is_rejected(self):
        with self.assertRaises(ValueError):
            parse(r"\section{单选题}\begin{problem}题\choices{1}{2}{3}\end{problem}")

    def test_unclosed_formula_is_rejected(self):
        with self.assertRaises(ValueError):
            parse(self.paper(r"错误 \(x"))

    def test_unclosed_problem_is_rejected(self):
        with self.assertRaises(ValueError):
            parse(r"\section{单选题}\begin{problem}题")

    def test_unclosed_nested_parts_are_rejected(self):
        with self.assertRaises(ValueError):
            subquestion_tree(r"\begin{enumerate}\item 条件")

    def test_nested_parts_keep_last_outer_request(self):
        tree = subquestion_tree(
            r"\begin{enumerate}\item 第一问\begin{enumerate}\item 内一\item 内二\end{enumerate}\item 最后条件\end{enumerate}"
        )
        self.assertEqual(len(tree), 2)
        self.assertEqual(len(tree[0]["children"]), 2)
        self.assertIn("最后条件", tree[1]["text"])

    def test_separate_lists_do_not_overwrite_earlier_one(self):
        tree = subquestion_tree(
            r"\begin{enumerate}\item 一\end{enumerate}\begin{enumerate}\item 二\end{enumerate}"
        )
        self.assertEqual(len(tree), 2)

    def test_tables_are_retained(self):
        text = r"\section{填空题}\begin{problem}表\begin{tabular}{cc}1&2\\3&4\end{tabular}\end{problem}"
        self.assertEqual(len(parse(text)[0]["tables_latex"]), 1)

    def test_tikz_dependency_is_real_asset(self):
        text = r"\section{填空题}\begin{problem}图\texfigure{img/x.tex}\end{problem}"
        self.assertEqual(parse(text)[0]["assets"], ["img/x.tex"])

    def test_answer_figures_do_not_pollute_question_assets(self):
        rows = parse(
            self.paper("题", r"\begin{answer}A\bitmapfigure{ans.png}\end{answer}")
        )
        self.assertFalse(rows[0]["assets"])
        self.assertEqual(rows[0]["answer_assets"], ["ans.png"])

    def test_unknown_section_is_not_guessed(self):
        with self.assertRaises(ValueError):
            parse(r"\section{未知}\begin{problem}题\end{problem}")

    def test_same_math_style_normalizes(self):
        a = {"raw_problem_latex": r"\(x\geqslant\left(1\right)\)", "assets": []}
        b = {"raw_problem_latex": r"\(x\ge 1\)", "assets": []}
        # Parentheses themselves are not discarded; only TeX sizing commands are.
        b["raw_problem_latex"] = r"\(x\ge(1)\)"
        self.assertEqual(content_signature(a, {}), content_signature(b, {}))

    def test_changed_condition_is_not_duplicate(self):
        a = {"raw_problem_latex": r"\(x>1\)", "assets": []}
        b = {**a, "raw_problem_latex": r"\(x\ge1\)"}
        self.assertNotEqual(content_signature(a, {}), content_signature(b, {}))

    def test_changed_image_is_not_duplicate(self):
        a = {"raw_problem_latex": "同题", "assets": ["figure"]}
        self.assertNotEqual(
            content_signature(a, {"figure": "a"}), content_signature(a, {"figure": "b"})
        )


class NationalCatalogTests(unittest.TestCase):
    def test_henan_2020_and_2021_have_year_specific_math_evidence(self):
        uses = list(read_lines(ROOT / "data/national/catalog/paper-regions.jsonl"))
        for year, source in ((2020, "eol-2020-math-use"), (2021, "eol-2021-map")):
            found = [u for u in uses if u["region_id"] == "河南" and u["year"] == year]
            self.assertEqual(len(found), 2)
            self.assertTrue(all(source in u["evidence"] for u in found))
            self.assertTrue(
                all(u["usage_status"] == "cross_checked_third_party" for u in found)
            )

    def test_all_new_papers_have_content_backed_counts(self):
        papers = list(read_lines(ROOT / "data/national/catalog/papers.jsonl"))
        self.assertEqual(len(papers), 21)
        self.assertEqual(sum(p["question_count"] for p in papers), 458)

    def test_existing_math_papers_are_links_not_recollected(self):
        acquired = read_json(ROOT / "data/national/acquisition.json")["records"]
        self.assertFalse(
            any(
                r["year"] in (2025, 2026) and r["series_id"] == "cn-new-gaokao-1"
                for r in acquired
            )
        )

    def test_henan_2024_shares_I_paper(self):
        uses = list(read_lines(ROOT / "data/national/catalog/paper-regions.jsonl"))
        found = [u for u in uses if u["region_id"] == "河南" and u["year"] == 2024]
        self.assertEqual({u["paper_id"] for u in found}, {"2024-cn-math-new-gaokao-1"})
        self.assertEqual(found[0]["exam_system_id"], "legacy-3+x")

    def test_old_arts_and_science_separate(self):
        papers = list(read_lines(ROOT / "data/national/catalog/papers.jsonl"))
        self.assertEqual(
            len(
                [
                    p
                    for p in papers
                    if p["year"] == 2022 and p["series_id"] == "cn-national-b"
                ]
            ),
            2,
        )

    def test_same_name_different_years_have_different_identity(self):
        papers = list(read_lines(ROOT / "data/national/catalog/papers.jsonl"))
        self.assertEqual(len({p["id"] for p in papers}), 21)

    def test_year_structure_changes_are_preserved(self):
        papers = {
            p["id"]: p for p in read_lines(ROOT / "data/national/catalog/papers.jsonl")
        }
        self.assertEqual(papers["2023-cn-math-new-gaokao-1"]["question_count"], 22)
        self.assertEqual(papers["2024-cn-math-new-gaokao-1"]["question_count"], 19)

    def test_shared_question_occurrences_keep_their_numbers(self):
        occ = list(read_lines(ROOT / "data/national/catalog/occurrences.jsonl"))
        d = {o["id"]: o for o in occ}
        a = d["2020-cn-math-new-gaokao-1:q021"]
        b = d["2020-cn-math-new-gaokao-2:q022"]
        self.assertEqual(a["question_id"], b["question_id"])
        self.assertNotEqual(a["number"], b["number"])

    def test_current_rules_not_replaced_by_historical_sample_volume(self):
        policy = target(ROOT)
        modern = {
            "series_id": "cn-new-gaokao-1",
            "year": 2026,
            "kind": "fill_in",
            "curriculum_id": "math-2017-2020",
        }
        old = {
            "series_id": "cn-national-b",
            "year": 2023,
            "kind": "fill_in",
            "curriculum_id": "math-2003",
        }
        self.assertGreater(
            relevance(modern, policy)["score"], relevance(old, policy)["score"]
        )
        self.assertEqual(
            read_json(ROOT / "data/analysis/rules.json")["blueprint"]["total_points"], 150
        )

    def test_undefined_target_is_rejected(self):
        with self.assertRaises(ValueError):
            target(ROOT, region="某省", year=2040)

    def test_old_and_new_national_I_are_distinct(self):
        self.assertNotEqual(ALIASES["新高考Ⅰ卷"], ALIASES["旧全国Ⅰ卷"])

    def test_science_selective_requires_province(self):
        with self.assertRaises(ValueError):
            validate_paper(
                {
                    "id": "test",
                    "year": 2024,
                    "series_id": "test",
                    "subject": "physics",
                    "component": "selective_provincial",
                }
            )

    def test_composite_science_requires_parent(self):
        with self.assertRaises(ValueError):
            validate_paper(
                {
                    "id": "test",
                    "year": 2020,
                    "series_id": "test",
                    "subject": "chemistry",
                    "component": "composite_section",
                }
            )

    def test_english_components_are_not_conflated(self):
        with self.assertRaises(ValueError):
            validate_paper(
                {"id": "test", "year": 2024, "series_id": "test", "subject": "english"}
            )

    def test_wrong_subject_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_paper(
                {"id": "test", "year": 2024, "series_id": "test", "subject": "unknown"}
            )

    def test_wrong_math_track_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_paper(
                {
                    "id": "test",
                    "year": 2024,
                    "series_id": "test",
                    "subject": "math",
                    "track": "science_and_liberal_same",
                }
            )

    def test_curation_is_bound_to_pdf_and_tex(self):
        c = read_json(ROOT / "data/national/curation.json")["overrides"][0]
        self.assertEqual(len(c["pdf_sha256"]), 64)
        self.assertEqual(len(c["tex_sha256"]), 64)
        self.assertNotEqual(c["new_text"], c["old_text"])


class BackupTests(unittest.TestCase):
    def test_authenticated_roundtrip_and_wrong_key_fail(self):
        scratch = ROOT / "tests/.scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            p = Path(folder)
            source = p / "source"
            source.mkdir()
            (source / "manifest.json").write_text("{}", encoding="utf-8")
            (source / "question.json").write_text(
                '{"id":"test","stem":"真实测试夹具"}', encoding="utf-8"
            )
            key = p / "recovery.key"
            cipher = p / "archive.enc"
            meta = backup(source, cipher, key)
            result = restore(cipher, key, p / "restored", meta["files"])
            self.assertEqual(result["files"], 2)
            from cryptography.fernet import Fernet

            wrong = p / "wrong.key"
            wrong.write_bytes(Fernet.generate_key())
            with self.assertRaises(InvalidToken):
                restore(cipher, wrong, p / "wrong-output")

    def test_modified_plaintext_inventory_is_detected(self):
        scratch = ROOT / "tests/.scratch"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            p = Path(folder)
            source = p / "source"
            source.mkdir()
            (source / "manifest.json").write_text("{}", encoding="utf-8")
            meta = backup(source, p / "x.enc", p / "key.key")
            meta["files"][0]["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                restore(p / "x.enc", p / "key.key", p / "dest", meta["files"])


class SourceGateTests(unittest.TestCase):
    def test_shared_master_is_one_planning_reference(self):
        first = {
            "question_id": "shared",
            "paper_id": "series-I",
            "occurrence_id": "I:q021",
            "version_sha256": "x",
        }
        second = {
            **first,
            "paper_id": "series-II",
            "occurrence_id": "II:q022",
            "version_sha256": "y",
        }
        with patch.object(db, "query", return_value=[first, second]):
            self.assertEqual(db.reference_pack(ROOT)["references"], [first])

    def test_reference_pack_excludes_known_legacy_version_disputes(self):
        disputed = {
            "paper_id": "a",
            "occurrence_id": "a:q001",
            "version_sha256": "x",
            "curation": {"body_state": "存在版本冲突"},
        }
        good = {"paper_id": "b", "occurrence_id": "b:q001", "version_sha256": "y"}
        with patch.object(db, "query", return_value=[disputed, good]):
            pack = db.reference_pack(ROOT)
            self.assertEqual(pack["references"], [good])
            self.assertTrue(pack["known_disputed_versions_excluded"])

    def test_elementary_function_flag_is_not_derivative_evidence(self):
        row = {
            "id": "a",
            "occurrence_id": "a",
            "paper_id": "a",
            "number": 1,
            "year": 2020,
            "series_id": "cn-new-gaokao-1",
            "subject": "math",
            "stem": "已知函数的值，求数值",
            "topic_flags": ["函数与导数"],
        }
        with (
            patch.object(db, "rows", return_value=[row]),
            patch.object(db, "catalog", return_value=[]),
        ):
            self.assertEqual(db.query(ROOT, topic="导数"), [])
            self.assertEqual(len(db.query(ROOT, topic="函数")), 1)

    def test_new_key_must_be_outside_repository(self):
        from national_backup import create_national

        with self.assertRaisesRegex(ValueError, "仓库外"):
            create_national(ROOT, ROOT / "never-created.key")
        self.assertFalse((ROOT / "never-created.key").exists())

    def test_backup_version_cannot_escape_directory(self):
        from national_backup import create_national

        with self.assertRaisesRegex(ValueError, "版本名称"):
            create_national(
                ROOT, ROOT.parent / "never-created.key", version="../escape"
            )

    def test_planning_context_remains_within_model_budget(self):
        from mathgen.planner import context
        from mathgen.ai_provider import PROTOCOL

        prompt = json.dumps(
            {
                "research_context": context(ROOT),
                "task": "X" * 2000,
                "required_protocol": PROTOCOL,
            },
            ensure_ascii=False,
        )
        self.assertLess(len(prompt), 40000)

    def test_original_pdf_note_cannot_be_silently_promoted(self):
        self.assertFalse(
            research_eligible(
                {"issues": source_issues("other", "现稿无解；对应原PDF答案B")}
            )
        )

    def test_entire_corrupt_source_stays_quarantined_without_per_item_note(self):
        issues = source_issues("2023-cn-math-national-b-science", "普通答案D")
        self.assertIn("quarantined_source_content_conflict", issues)
        self.assertFalse(research_eligible({"issues": issues}))

    def test_alignment_warning_does_not_falsely_prove_content_error(self):
        self.assertTrue(
            research_eligible({"issues": ["native_pdf_text_alignment_needs_review"]})
        )

    def test_default_query_excludes_conflicts_but_explicit_investigation_preserves_them(
        self,
    ):
        row = {
            "id": "a",
            "occurrence_id": "a",
            "paper_id": "a",
            "number": 1,
            "year": 2023,
            "series_id": "cn-national-b",
            "subject": "math",
            "stem": "独立测试夹具",
            "issues": ["quarantined_source_content_conflict"],
        }
        with (
            patch.object(db, "rows", return_value=[row]),
            patch.object(db, "catalog", return_value=[]),
        ):
            self.assertEqual(db.query(ROOT), [])
            self.assertEqual(len(db.query(ROOT, include_quarantined=True)), 1)

    def test_negative_and_zero_limits_are_rejected(self):
        for limit in (0, -1):
            with self.assertRaises(ValueError):
                db.reference_pack(ROOT, limit=limit)
            with self.assertRaises(ValueError):
                db.query(ROOT, limit=limit)

    def test_reverse_year_range_rejected(self):
        with self.assertRaises(ValueError):
            db.query(ROOT, year_from=2026, year_to=2020)


if __name__ == "__main__":
    unittest.main()
