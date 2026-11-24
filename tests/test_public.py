"""Public CI regressions. All fixtures are synthetic or original AI work, no recovery key."""

import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / "tests/.scratch"
SCRATCH.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))
import bootstrap
import sympy as s
from analysis_db import fingerprint
from gaokao import load, read_json
from mathgen.ai_provider import (
    HostAIProvider,
    OpenAIProvider,
    ProviderError,
    select_provider,
    validate_document,
)
from mathgen.ai_spec import solve_task, parse
from mathgen.dynamic import (
    verify_candidate,
    rendered_question,
    independent_solve,
    structural_signature,
    paper_review,
    latex_source,
)
from mathgen.novelty import compare, paper_difference
from mathgen.review import audit_item
from mathgen.generate import draft, add_options
from mathgen.quality import verify, assert_fresh
from storage import backup, restore


def fixture():
    return {
        "id": "synthetic:ai:fixture:v1",
        "slot": 1,
        "kind": "single_choice",
        "points": 5,
        "module": "集合与复数",
        "generation": {"provider": "host_ai"},
        "design": {
            "structure": "合成算术",
            "reasoning_path": "独立加法",
            "knowledge_combination": ["加法"],
        },
        "problem": {
            "context": "合成回归样本",
            "tasks": [{"op": "evaluate", "expression": "2+3"}],
            "options": {
                k: {
                    "text": r"\(" + str(v) + r"\)",
                    "semantic_value": str(v),
                    "error_path": "合成错误路径",
                }
                for k, v in zip("ABCD", (5, 6, 4, 3))
            },
        },
    }


class DefectRegressionTests(unittest.TestCase):
    def test_key_leak_in_regular_data_or_log_is_detected(self):
        from security_scan import scan_blob

        synthetic = b"synthetic-recovery-token-not-a-real-key"
        for name in ("metadata/data.json", "reports/log.txt"):
            found = scan_blob(name, b"prefix " + synthetic, (synthetic,))
            self.assertFalse(found["passed"])
            self.assertIn("credential_content", found["codes"])
            self.assertNotIn(synthetic.decode(), json.dumps(found))

    def test_key_path_and_private_key_payload_are_detected(self):
        from security_scan import scan_blob

        self.assertFalse(scan_blob("backup/recovery.key", b"example")["passed"])
        self.assertFalse(
            scan_blob("data.txt", b"-----BEGIN" + b" PRIVATE KEY-----")["passed"]
        )

    def test_probability_options_are_legal_for_many_seeds(self):
        for seed in range(20):
            q = add_options(draft("urn_pair", seed, "single_choice"), seed + 1)
            self.assertTrue(audit_item(q)["passed"])
            self.assertTrue(
                all(0 <= parse(v["semantic_value"]) <= 1 for v in q["options"].values())
            )

    def test_trigonometric_options_are_legal(self):
        q = add_options(draft("trig_square", 17, "single_choice"), 18)
        self.assertTrue(
            all(-1 <= parse(v["semantic_value"]) <= 1 for v in q["options"].values())
        )

    def test_bad_probability_option_is_rejected(self):
        q = fixture()
        q["module"] = "概率统计"
        q["problem"]["tasks"] = [
            {"op": "probability", "sample_space": {"x": [0, 1]}, "event": "x==1"}
        ]
        q["problem"]["options"]["A"] = {
            "text": r"\(-1\)",
            "semantic_value": "-1",
            "error_path": "故意非法测试",
        }
        _, v = verify_candidate(q, 1)
        self.assertFalse(v["passed"])
        self.assertIn("option_out_of_range", v["quality"]["errors"])

    def test_equivalent_correct_options_are_rejected(self):
        q = fixture()
        q["problem"]["options"]["B"] = {
            "text": r"\(5\)",
            "semantic_value": "10/2",
            "error_path": "重复答案",
        }
        _, v = verify_candidate(q, 1)
        self.assertFalse(v["passed"])
        self.assertIn("non_unique_correct_option", v["quality"]["errors"])

    def test_single_choice_proof_demand_is_rejected(self):
        q = fixture()
        q["problem"]["context"] = "计算后另请证明全部范围"
        _, v = verify_candidate(q, 1)
        self.assertFalse(v["passed"])

    def test_duplicate_instructions_are_rejected(self):
        q = rendered_question(fixture(), 1)
        q["stem"] = "选择所有正确命题。选择所有正确命题。"
        self.assertIn("duplicate_instructions", audit_item(q)["errors"])

    def test_missing_figure_is_rejected(self):
        q = fixture()
        q["problem"]["context"] = "如图计算"
        _, v = verify_candidate(q, 1)
        self.assertIn("missing_figure", v["quality"]["errors"])

    def test_missing_formula_is_rejected(self):
        q = fixture()
        q["problem"]["tasks"][0]["expression"] = ""
        with self.assertRaises((ValueError, SyntaxError)):
            verify_candidate(q, 1)

    def test_cancellation_cannot_hide_domain_hole(self):
        with self.assertRaisesRegex(ValueError, "分母"):
            solve_task({"op": "identity", "left": "x/x", "right": "1"})

    def test_wrong_derivative_shared_with_generator_is_caught(self):
        with patch("mathgen.ai_spec.s.diff", return_value=s.Integer(0)):
            with self.assertRaisesRegex(ValueError, "交叉"):
                solve_task(
                    {
                        "op": "derivative",
                        "expression": "x*x",
                        "domain": ["-2", "2"],
                        "open": [False, False],
                    }
                )

    def test_wrong_proposed_answer_is_not_read_by_solver(self):
        q = fixture()
        q["claimed_answer"] = "99"
        _, v = verify_candidate(q, 1)
        self.assertTrue(v["passed"])
        self.assertEqual(v["solver_record"]["tasks"][0]["result"], "5")

    def test_modified_body_invalidates_cached_verification(self):
        q, v = verify_candidate(fixture(), 1)
        q["stem"] += "新增条件"
        with self.assertRaises(ValueError):
            assert_fresh(q, v)

    def test_ai_does_not_call_template_generator(self):
        with (
            patch(
                "mathgen.generate.draft", side_effect=AssertionError("template called")
            ),
            patch(
                "mathgen.providers.FamilyProvider.propose",
                side_effect=AssertionError("template called"),
            ),
        ):
            from mathgen.dynamic import run_ai

            with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
                record = run_ai(
                    ROOT,
                    HostAIProvider(
                        ROOT / "experiments/phase3/proposals/acceptance5.json"
                    ),
                    Path(folder) / "new",
                    export=False,
                )
                self.assertEqual(record["generation_mode"], "ai")
                self.assertTrue(all("family" not in q for q in record["questions"]))

    def test_template_disguised_as_ai_is_rejected(self):
        doc = {
            "schema_version": 1,
            "blueprint": {},
            "questions": [{**fixture(), "family": "seq_interlace"}],
        }
        with self.assertRaises(ValueError):
            validate_document(doc)

    def test_number_only_changes_keep_same_structure(self):
        a = fixture()
        b = copy.deepcopy(a)
        b["problem"]["tasks"][0]["expression"] = "8+9"
        b["id"] = "synthetic:modified"
        self.assertTrue(compare(a, b)["same_structure_after_erasing_numbers"])

    def test_new_model_changes_structure(self):
        a = fixture()
        b = copy.deepcopy(a)
        b["problem"]["tasks"][0] = {
            "op": "equation",
            "expression": "x*x-2",
            "unique": True,
            "domain": ["0", "2"],
        }
        self.assertNotEqual(structural_signature(a), structural_signature(b))

    def test_wrong_syllabus_is_rejected(self):
        q = fixture()
        q["module"] = "大学高等数学"
        _, v = verify_candidate(q, 1)
        self.assertFalse(v["passed"])

    def test_unsupported_proof_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            solve_task({"op": "integral", "expression": "x"})

    def test_rendering_keeps_question_not_its_answer(self):
        text = latex_source("abs((1+I)/(1-I))**2")
        self.assertIn("frac", text)
        self.assertNotEqual(text, "1")
        self.assertIn("=", latex_source("(-1)**3-3*(-1)==2"))
        self.assertNotIn("True", latex_source("(-1)**3-3*(-1)==2"))

    def test_optimum_explicitly_names_maximum(self):
        q = fixture()
        q["problem"]["tasks"] = [
            {
                "op": "optimum",
                "which": "maximum",
                "expression": "x*x",
                "domain": ["0", "1"],
                "open": [False, False],
            }
        ]
        self.assertIn("求最大值", rendered_question(q, 1)["stem"])

    def test_conditional_probability_golden_result(self):
        task = {
            "op": "probability",
            "sample_space": {"x": [1, 2, 3, 4, 5, 6], "y": [1, 2, 3, 4, 5, 6]},
            "condition": "x!=y",
            "event": "x+y==7",
        }
        self.assertEqual(solve_task(task)["result"], "1/5")
        self.assertFalse(solve_task(task)["cross_checked"])

    def test_probability_claim_explains_probability_separately_from_truth(self):
        row = solve_task(
            {
                "op": "probability_claim",
                "sample_space": {"x": [0, 1]},
                "event": "x==1",
                "claimed_probability": "1/2",
            }
        )
        self.assertIs(row["result"], True)
        self.assertNotIn("True", " ".join(row["steps"]))
        self.assertIn(r"\frac{1}{2}", " ".join(row["steps"]))

    def test_reordered_multiple_choice_solutions_name_current_letters(self):
        raw = read_json(ROOT / "experiments/phase3/proposals/fullA.json")["questions"][
            8
        ]
        q, v = verify_candidate(raw, 9)
        for shown, original in q["option_permutation"].items():
            row = v["solver_record"]["tasks"]["ABCD".index(original)]
            expected = f"现选项{shown}（原始命题{original}）。" + (
                "成立" if row["result"] else "不成立"
            )
            self.assertIn(expected, v["steps"])

    def test_stationary_point_without_extremum_is_handled(self):
        result = solve_task({"op": "monotonicity", "expression": "x**3-3*x*x+3*x"})[
            "result"
        ]
        self.assertEqual(result["increasing"], "Interval(-oo, oo)")
        self.assertEqual(result["decreasing"], "EmptySet")

    def test_parameter_boundary_included(self):
        result = solve_task(
            {
                "op": "parameter_monotone",
                "expression": "a*log(x)-x",
                "domain": ["1", "3"],
                "open": [False, False],
            }
        )
        self.assertEqual(result["result"], "Interval(3, oo)")

    def test_trigonometric_root_count_keeps_each_level(self):
        task = {
            "op": "root_count",
            "expression": "(sin(x)-1)*(2*sin(x)+1)",
            "domain": ["0", "2*pi"],
            "open": [False, True],
        }
        self.assertEqual(str(solve_task(task)["result"]), "3")

    def test_cross_validation_is_not_formal_proof(self):
        record = solve_task({"op": "derivative", "expression": "x*x"})
        self.assertFalse(record["formal_proof"])
        self.assertTrue(record["cross_checked"])

    def test_simple_arithmetic_is_not_overstated_as_dual_proof(self):
        record = solve_task({"op": "evaluate", "expression": "2+3"})
        self.assertEqual(record["status"], "已完成程序验证")
        self.assertFalse(record["cross_checked"])

    def test_solver_timeout_is_blocked(self):
        record = independent_solve(
            {"tasks": [{"op": "evaluate", "expression": "2+3"}]}, timeout=0
        )
        self.assertFalse(record["ok"])
        self.assertIn("超时", record["reason"])

    def test_fallback_is_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ProviderError):
                select_provider("ai")
            self.assertEqual(
                select_provider("ai", allow_template_fallback=True).name, "template"
            )

    def test_host_bad_json_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            path = Path(folder) / "bad.json"
            path.write_text("{not-json")
            with self.assertRaises(ProviderError):
                HostAIProvider(path)

    def test_api_timeout_has_bounded_retry_and_no_secret_in_error(self):
        secret = "unit-test-secret-do-not-log"

        def timeout(*args, **kwargs):
            raise TimeoutError(secret)

        provider = OpenAIProvider("test-model", max_calls=2, transport=timeout)
        with patch.dict(os.environ, {"OPENAI_API_KEY": secret}):
            with self.assertRaises(ProviderError) as error:
                provider.propose({}, "JSON test")
        self.assertEqual(provider.calls, 2)
        self.assertNotIn(secret, str(error.exception))

    def test_api_malformed_response_is_rejected(self):
        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        provider = OpenAIProvider(
            "test-model",
            max_calls=1,
            transport=lambda *a, **k: Response(b'{"status":"completed","output":[]}'),
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic"}):
            with self.assertRaises(ProviderError):
                provider.propose({}, "JSON test")

    def test_api_total_budget_cannot_reset_between_proposals(self):
        document = read_json(ROOT / "experiments/phase3/proposals/acceptance5.json")
        payload = json.dumps(
            {
                "status": "completed",
                "output": [
                    {"content": [{"type": "output_text", "text": json.dumps(document)}]}
                ],
            }
        ).encode()

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        provider = OpenAIProvider(
            "synthetic-model", max_calls=1, transport=lambda *a, **k: Response(payload)
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic"}):
            self.assertEqual(
                provider.propose({}, "JSON test")["provenance"]["api_calls"], 1
            )
            with self.assertRaises(ProviderError):
                provider.propose({}, "JSON again")
        self.assertEqual(provider.calls, 1)

    def test_api_revises_a_math_failure_within_shared_budget(self):
        from mathgen.dynamic import run_ai

        original = read_json(ROOT / "experiments/phase3/proposals/acceptance5.json")
        bad = copy.deepcopy(original)
        bad["questions"][0]["problem"]["tasks"][0]["op"] = "unsupported_proof"
        replies = iter([bad, original])

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.close()

        def transport(*args, **kwargs):
            body = {
                "status": "completed",
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": json.dumps(next(replies))}
                        ]
                    }
                ],
            }
            return Response(json.dumps(body).encode())

        provider = OpenAIProvider("synthetic-model", max_calls=2, transport=transport)
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic"}),
            tempfile.TemporaryDirectory(dir=SCRATCH) as folder,
        ):
            record = run_ai(ROOT, provider, Path(folder) / "new", export=False)
            self.assertEqual(record["remote_model_calls"], 2)
            self.assertEqual(len(record["questions"]), 5)
            self.assertTrue(record["proposal_revision_files"])
            self.assertTrue(read_json(Path(folder) / "new/rejected.json"))

    def test_review_cannot_attest_another_candidate_version(self):
        from mathgen.attestation import attest

        q, v = verify_candidate(fixture(), 1)
        record = {"generation_mode": "ai", "questions": [q], "verifications": [v]}
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            p = Path(folder)
            (p / "run.json").write_text(json.dumps(record), encoding="utf-8")
            (p / "review.json").write_text(
                json.dumps(
                    {"questions": [{"candidate_sha256": "wrong", "status": "pass"}]}
                )
            )
            with self.assertRaises(ValueError):
                attest(p / "run.json", p / "review.json", export=False)

    def test_comparison_command_does_not_swallow_variable(self):
        text = latex_source("x!=y")
        self.assertNotIn(r"\ney", text)
        self.assertIn(r"\ne ", text)

    def test_pdf_handles_logic_symbols_and_inline_image_wrap(self):
        from mathgen.export import export_run
        from pypdf import PdfReader

        q, v = verify_candidate(fixture(), 1)
        # Synthetic long mixed CJK/image paragraph exercises the earlier layout crash.
        q["stem"] = (
            "公式换行回归。" + r"\(x\ne y\lor (x\bmod 2)=0\land y>0\)" + "检查边界。"
        ) * 8
        v["question_sha256"] = fingerprint(q)
        record = {
            "generation_mode": "ai",
            "blueprint": {
                "mode": "acceptance",
                "title": "排版测试",
                "simulation_settings": [],
            },
            "structure": {"points": 5},
            "questions": [q],
            "verifications": [v],
            "events": [
                {"passed": True, "quality": {"duplicate": {"closest": {"score": 0}}}}
            ],
            "limitations": [],
        }
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            with self.assertRaises(ValueError):
                export_run(record, Path(folder))
            # The legacy renderer remains available for template-only regression fixtures.
            record["generation_mode"] = "template"
            export_run(record, Path(folder))
            self.assertGreater(len(PdfReader(Path(folder) / "paper.pdf").pages), 0)

    def test_secret_paths_are_excluded(self):
        import subprocess

        tracked = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=ROOT, text=True
        ).split("\0")
        self.assertFalse(
            any(p.endswith(".key") or p.startswith(".private/") for p in tracked if p)
        )

    def test_encrypted_fixture_restores_with_separate_key(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as folder:
            p = Path(folder)
            source = p / "source"
            source.mkdir()
            (source / "manifest.json").write_text('{"synthetic":true}')
            record = backup(source, p / "backup.enc", p / "separate.key")
            restore(
                p / "backup.enc", p / "separate.key", p / "restored", record["files"]
            )
            self.assertEqual(
                (p / "restored/manifest.json").read_text(), '{"synthetic":true}'
            )

    def test_two_full_ai_papers_have_distinct_structures(self):
        a = read_json(ROOT / "experiments/phase3/proposals/fullA.json")
        b = read_json(ROOT / "experiments/phase3/proposals/fullB.json")
        a = {
            "questions": [
                rendered_question(q, i + 1) for i, q in enumerate(a["questions"])
            ]
        }
        b = {
            "questions": [
                rendered_question(q, i + 1) for i, q in enumerate(b["questions"])
            ]
        }
        self.assertTrue(paper_difference(a, b)["passed"])

    def test_150_structure_failure_is_detected(self):
        plan = {
            "mode": "full",
            "slots": [{"kind": "single_choice", "points": 5, "module": "集合与复数"}],
            "total_points": 150,
        }
        q = rendered_question(fixture(), 1)
        report = paper_review(plan, [q], [{"passed": True, "option_key": "A"}])
        self.assertFalse(report["passed"])
        self.assertIn("paper_total_points", report["errors"])


if __name__ == "__main__":
    unittest.main()
