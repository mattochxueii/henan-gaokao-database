"""Offline review transport, local decision semantics and Skill installation."""
import contextlib
from copy import deepcopy
from io import StringIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import bootstrap
from analysis_db import fingerprint
from core import board_cycle, exam_qa, external_review, review_board
from gaokao import ROOT, digest, read_json, write_json
from gaokao_platform import main
from install_skill import install


def board_state():
    return {"protocol":review_board.VERSION,"subject":"english","ids":["a","b"],"version":"v1",
            "pdf_sha256":"a"*64,"pages":1,"item_versions":{"1":"first","2":"second"},
            "rules":exam_qa.policies(ROOT,"english"),"preflight":{"passed":True,"issues":[],"coverage":{}},
            "choice_keys":{"1":"A"}}


def blind_reports(state):
    items = [{"number":n,"answer":"A","reasoning":"Test solution","comparison":"Test position",
              "steps":["read and infer"],"concepts":["cohesion"]} for n in (1,2)]
    return [{"identity":"fixture-"+role,"role":role,"pdf_sha256":state["pdf_sha256"],"items":deepcopy(items),
             "findings":[],"pages":[{"number":1,"note":"fixture page"}]} for role in review_board.ROLES]


def response(local, n=1, rule="english.distractor"):
    return {"protocol":external_review.PROTOCOL,"paper_version":local["paper_version"],"pdf_sha256":local["pdf_sha256"],
            "model_family":"test-fixture","model":"test-model",
            "findings":[{"number":n,"rule":rule,"severity":"major","evidence":"The option repeats the stem.",
                         "revision":"Use an alternate plausible reading."}]}


class ExternalReview27Tests(TestCase):
    def test_offline_live_export_limits_contents(self):
        source = ROOT/"experiments/phase26/english/final"
        with TemporaryDirectory() as temp:
            out = Path(temp)/"blind"
            with contextlib.redirect_stdout(StringIO()):
                rc = main(["export-external-review",str(source),str(out)])
            self.assertEqual(rc,0)
            self.assertEqual({p.name for p in out.iterdir()},
                             {"student.pdf","student.md","instructions.md","policy-check.json","position-summaries.json",
                              "anti-patterns.json","findings-template.json","listening.md"})
            self.assertEqual(digest(out/"student.pdf"),digest(source/"paper.pdf"))
            self.assertEqual(read_json(out/"policy-check.json")["policy"]["year"],2027)
            self.assertNotIn("reference_answer",(out/"position-summaries.json").read_text(encoding="utf-8"))
            self.assertNotIn("答案：",(out/"student.md").read_text(encoding="utf-8"))

    def test_local_pass_hides_rating_but_replays_actual_debits(self):
        state = board_state()
        reports = blind_reports(state)
        reports[1]["findings"] = [{"number":1,"category":"weak","rule":"english.distractor","evidence":"weak option"}]
        card = review_board.score_exam(state,reports)
        self.assertEqual(card["final_score"],97)
        decision = review_board.decision_view(card)
        self.assertEqual(decision["state"],"LOCAL_QA_PASSED")
        self.assertNotIn("score",decision)
        self.assertEqual(decision["scorecard"],"board/scorecard-round1.json")

    def test_external_findings_restart_and_lock_after_three_rounds(self):
        state = board_state()
        local = review_board.score_exam(state,blind_reports(state))
        local["round"],local["cycle_round"] = 3,3
        new = deepcopy(state)
        new["item_versions"]["1"] = "changed"
        new["version"],new["pdf_sha256"] = "v2","b"*64
        new["external_feedback"] = [response(local)]
        result = review_board.score_exam(new,blind_reports(new),local)
        self.assertEqual((result["round"],result["cycle_round"],result["status"]),(4,1,"LOCAL_QA_PASSED"))
        new["item_versions"]["2"] = "wrong edit"
        with self.assertRaisesRegex(ValueError,"锁定"):
            review_board.score_exam(new,blind_reports(new),local)

    def test_global_layout_defect_keeps_all_questions_locked(self):
        state = board_state()
        local = review_board.score_exam(state,blind_reports(state))
        new = deepcopy(state)
        new["version"],new["pdf_sha256"] = "v2","b"*64
        new["external_feedback"] = [response(local,0,"exam.policy")]
        self.assertEqual(review_board.score_exam(new,blind_reports(new),local)["status"],"LOCAL_QA_PASSED")
        new["item_versions"]["1"]="rewritten"
        with self.assertRaisesRegex(ValueError,"锁定"):
            review_board.score_exam(new,blind_reports(new),local)

    def test_import_returns_repair_slots_and_blocks_authorization(self):
        with TemporaryDirectory() as temp, patch("core.review_board.evidence",return_value=board_state()):
            root = Path(temp)
            state = board_state()
            card = review_board.record(ROOT,root,blind_reports(state))
            self.assertEqual(review_board.authorize(ROOT,root),fingerprint(card))
            data = response(card)
            reply = root/"response.json"
            write_json(reply,data)
            with contextlib.redirect_stdout(StringIO()):
                rc = main(["import-external-review",str(root),str(reply)])
            self.assertEqual(rc,0)
            decision = board_cycle.cycle(ROOT,root,root/"inbox")
            self.assertEqual((decision["review_state"],decision["rewrite"],decision["locked"]),
                             ("EXTERNAL_REVIEW_RETURNED",[1],[2]))
            self.assertEqual(external_review.import_reply(ROOT,root,data)["decision"],decision)
            self.assertEqual(len(list((root/"external-reviews").glob("*.json"))),1)
            with self.assertRaisesRegex(ValueError,"外部盲审"):
                review_board.authorize(ROOT,root)
            data["pdf_sha256"]="stale"
            with self.assertRaisesRegex(ValueError,"版本"):
                external_review.import_reply(ROOT,root,data)

    def test_next_folder_applies_receipts_and_replays_the_linked_repair(self):
        with TemporaryDirectory() as temp:
            old, new = (Path(temp)/name for name in ("before","after"))
            old.mkdir()
            new.mkdir()
            first = board_state()
            with patch("core.review_board.evidence",return_value=first):
                card = review_board.record(ROOT,old,blind_reports(first))
                external_review.import_reply(ROOT,old,response(card))
            next_state = deepcopy(first)
            next_state["version"] = "v2"
            next_state["pdf_sha256"] = "b"*64
            next_state["item_versions"]["1"]="repaired question"
            with patch("core.review_board.evidence",return_value=next_state):
                result = review_board.record(ROOT,new,blind_reports(next_state),old)
                self.assertEqual(review_board.authorize(ROOT,new),fingerprint(result))
            self.assertEqual(result["round"],2)
            self.assertEqual(review_board.replay(new/"board"),result)
            self.assertEqual(review_board.replay(old/"board"),card)

    def test_clean_reply_and_global_content_scope(self):
        state = board_state()
        local = review_board.score_exam(state,blind_reports(state))
        data = response(local,0)
        with self.assertRaisesRegex(ValueError,"承接题号"):
            external_review.validate(data,local,state["rules"])
        data["findings"][0]["repair_numbers"]=[2]
        self.assertEqual(external_review.repair_targets([data],local,state["rules"]),({2},False))
        data["findings"]=[]
        self.assertEqual(external_review.repair_targets([data],local,state["rules"]),(set(),False))


class SkillInstall27Tests(TestCase):
    def test_cli_installs_only_platform_and_launches_subjects(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)/".claude"/"skills"
            command = [sys.executable,str(ROOT/"scripts/install_skill.py"),"--destination",str(root)]
            result = subprocess.run(command,capture_output=True,encoding="utf-8")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual([p.name for p in root.iterdir()],["gaokao-platform"])
            script = root/"gaokao-platform/scripts/run.py"
            result = subprocess.run([sys.executable,str(script),"subjects"],cwd=temp,
                                    capture_output=True,encoding="utf-8")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('"biology"',result.stdout)
            self.assertIn('"chinese"',result.stdout)
            self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)

    def test_cross_windows_drive_install_link(self):
        with TemporaryDirectory() as temp:
            target = Path(temp)/"gaokao-platform"
            with patch("install_skill.os.path.relpath",side_effect=ValueError("different drive")):
                info = install(ROOT,target)
            self.assertEqual(info["database_link_type"],"absolute")
            self.assertEqual(Path(read_json(target/"database-link.json")["absolute_database_root"]),ROOT)
            result = subprocess.run([sys.executable,str(target/"scripts/run.py"),"subjects"],
                                    capture_output=True,encoding="utf-8")
            self.assertEqual(result.returncode,0,result.stderr)

    def test_existing_custom_install_is_preserved(self):
        with TemporaryDirectory() as temp:
            target = Path(temp)/"gaokao-platform"
            target.mkdir()
            (target/"SKILL.md").write_text("custom",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"已有不同内容"):
                install(ROOT,target)
            self.assertEqual((target/"SKILL.md").read_text(encoding="utf-8"),"custom")
