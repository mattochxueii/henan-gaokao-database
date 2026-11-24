"""Date-bound scoring, playback, and science blueprint regressions."""
from decimal import Decimal
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import bootstrap
from core import batch_planner, exam_policy, exam_qa, language_workflow, review_board
from core import physics_corridor as physics
from core.language_render import render
from gaokao import ROOT, digest, read_json
from pypdf import PdfReader
from test_batch_review import physics_batch


def policy(subject, year, region="河南", series=None):
    series = series or (exam_policy.PHYSICS_SERIES if subject == "physics" else exam_policy.NATIONAL_SERIES)
    return exam_policy.resolve(ROOT,subject,year,region,series)


def policy_issues(snapshot, text):
    return list(exam_policy.conflicts(snapshot, [(0,text)]))


class Policy27Tests(TestCase):
    def test_henan_score_cutover_and_raw_listening_requirement(self):
        for year in (2025,2026):
            self.assertEqual(language_workflow.henan_english_score(102,year=year,listening=2),128)
        self.assertEqual(language_workflow.henan_english_score(102,year=2027,listening=24),126)
        self.assertEqual(language_workflow.henan_english_score(120,year=2028,listening=30),150)
        for listening in (None,31,-1):
            with self.assertRaises(ValueError):
                language_workflow.henan_english_score(102,year=2027,listening=listening)

    def test_conditional_region_series_and_year_axes(self):
        self.assertFalse(exam_policy.parameters(policy("english",2027,region="湖北"),"english_score"))
        self.assertFalse(exam_policy.parameters(policy("english",2027,region="北京",series="beijing"),"listening"))
        self.assertFalse(exam_policy.parameters(policy("physics",2027,region="安徽"),"multiple_choice"))
        self.assertFalse(exam_policy.parameters(policy("math",2023),"multiple_choice"))
        self.assertEqual(exam_policy.parameters(policy("math",2024),"multiple_choice")["partial_credit"],"variable")
        self.assertEqual(exam_policy.parameters(policy("physics",2025),"multiple_choice")["partial_credit"],3)

    def test_mixed_national_playback_years(self):
        for year, expected in ((2024,[1,2]),(2025,[1,2]),(2026,[2,2]),(2027,[2,2])):
            snapshot = policy("english",year)
            sections = exam_policy.parameters(snapshot,"listening")["sections"]
            self.assertEqual([section["repeats"] for section in sections],expected)
            self.assertFalse(policy_issues(snapshot,"\n".join(exam_policy.student_instructions(snapshot))))

    def test_2027_old_text_has_a_fatal_category(self):
        snap = policy("english",2027)
        for mistake in ("笔试 × 1.25","笔试分乘以１．２５","河南听力成绩不计入总分","第一节短对话仅读一遍",
                        "第一节录音播放1次","Each short dialogue will be read only once."):
            with self.subTest(mistake=mistake):
                draft = {"title":mistake,"exam_policy":snap,"questions":[{"kind":"single_choice","stem":"Where?"}]}
                gate = exam_qa.inspect(ROOT,"english",draft,["A"])
                self.assertEqual({i["rule"] for i in gate["issues"]},{"policy_conflict"})
                state = {"protocol":review_board.VERSION,"subject":"english","ids":["a"],"pdf_sha256":"digest",
                         "version":"v1","item_versions":{"1":"first"},"preflight":gate,"repair_slots":[1]*len(gate["issues"])}
                card = review_board.score_exam(state,[])
                self.assertEqual((card["final_score"],card["deductions"][0]["category"]),(0,"fatal"))

    def test_wrong_multiple_choice_or_missing_printed_instruction(self):
        for subject, mistake in (("math","部分选对得3分"),("physics","部分选对的得部分分"),
                                 ("physics","全部选对的得5分，选错得1分"),("english","第一节播放一遍")):
            self.assertTrue(policy_issues(policy(subject,2027),mistake))
        draft = {"title":"2027年英语","exam_policy":policy("english",2027),
                 "questions":[{"kind":"single_choice","stem":"When?"}]}
        gate = exam_qa.inspect(ROOT,"english",draft,["A"],header="学生卷另印一个错误卷头")
        self.assertFalse(gate["passed"])
        self.assertEqual(sum("学生PDF缺" in i["evidence"] for i in gate["issues"]),3)

    def test_actual_student_and_monitor_renders_switch_by_year(self):
        for year, first in ((2025,"一"),(2026,"两"),(2027,"两")):
            with self.subTest(year=year), TemporaryDirectory() as temp:
                root = Path(temp)
                paper = {"title":f"{year}年英语听力排版测试","subject":"english","points":30,"minutes":20,
                         "exam_policy":policy("english",year),"sections":[{"id":"listening","title":"听力"}],
                         "materials":{f"L{n}":{"title":f"Text {n}","text":""} for n in range(1,11)},
                         "questions":[{"number":n,"points":1.5,"section":"listening","kind":"single_choice",
                                       "stem":"Which room?","material":f"L{n}"} for n in range(1,11)]}
                render(paper,root/"paper")
                render(paper,root/"listening",listening={k:"A distinct recording." for k in paper["materials"]})
                student, monitor = [exam_policy.compact("".join(p.extract_text() for p in PdfReader(root/name).pages))
                                    for name in ("paper.pdf","listening.pdf")]
                for text in (student,monitor):
                    self.assertIn(f"每段录音播放{first}遍",text)
                    self.assertIn("每段录音播放两遍",text)
                    self.assertFalse(policy_issues(paper["exam_policy"],text))
                for sentence in exam_policy.student_instructions(paper["exam_policy"]):
                    self.assertIn(exam_policy.compact(sentence),student)
                self.assertNotIn("adistinctrecording",student)
                self.assertEqual("1.25" in student,year < 2027)

    def test_legacy_pdf_recheck_finds_old_regime_without_rewriting_record(self):
        previous = ROOT/"experiments/phase26/english/final"
        card = review_board.replay(previous/"board")
        initial = digest(previous/"paper.pdf")
        state = review_board.evidence(ROOT,previous,recheck_legacy_policy=True)
        failures = [row["evidence"] for row in state["preflight"]["issues"] if row["rule"]=="policy_conflict"]
        self.assertTrue(any("折算" in msg for msg in failures))
        self.assertTrue(any("播放次数" in msg for msg in failures))
        self.assertEqual(card,review_board.replay(previous/"board"))
        self.assertEqual(initial,digest(previous/"paper.pdf"))


class ScienceCorridor27Tests(TestCase):
    def test_each_batch_book_has_its_own_weight_and_distinct_finals(self):
        schedule = batch_planner.plan("physics",2)
        result = batch_planner.check(schedule,physics_batch(schedule))
        self.assertTrue(result["passed"],result["issues"])
        self.assertEqual([d["groups"] for d in result["allocations"]],[{"mechanics":42,"electromagnetism":40,"other":18}]*2)
        self.assertNotEqual(*[b["final"]["model"] for b in schedule["blueprints"]])

    def test_batch_rejects_complementary_skew_even_without_collision(self):
        schedule = batch_planner.plan("physics",2)
        rows = physics_batch(schedule)
        rows[0]["questions"][14].update(stem="自行车的加速度降为零",physics_module="mechanics")
        rows[1]["questions"][12].update(stem="电路的分流比",physics_module="electrostatics_circuits")
        gate = batch_planner.check(schedule,rows)
        self.assertFalse(gate["passed"])
        self.assertEqual({i["paper"] for i in gate["issues"] if i.get("rule")=="physics_weight"},{1,2})
        self.assertTrue(any("指定板块" in row["reason"] for row in gate["issues"]))

    def test_physics_weight_cannot_be_faked_with_an_unrelated_tag(self):
        rows = physics_batch(batch_planner.plan("physics",2))[0]["questions"]
        rows[4].update(physics_module="atomic")
        _,issues = physics.allocation(rows)
        self.assertTrue(any(n==5 and "实质标志" in text for n,_,text in issues))

    def test_combined_thermal_total_and_calculation_type(self):
        rows = physics_batch(batch_planner.plan("physics",2))[0]["questions"]
        for n in (1,10):
            rows[n-1].update(stem="气缸中理想气体的温度变化",physics_module="thermodynamics")
        rows[12]["parts"] = []
        rows[13]["parts"] = []
        _, issues = physics.allocation(rows)
        self.assertTrue(any(rule=="physics_weight" and "热学 14 分" in text for _,rule,text in issues))
        self.assertTrue(any(rule=="physics_calculation" and "力学综合" in text for _,rule,text in issues))

    def test_pi_regression_on_printed_single_pendulum_of_phase26(self):
        source = ROOT/"experiments/phase25/physics-batch/phase26/A/round3/candidate.json"
        item = read_json(source)["questions"][10]
        results = list(physics.pi_findings(item,item["proposed_answer"]))
        self.assertTrue(any("9.79" in text and "9.80" in text for text in results),results)

    def test_pi_operator_binds_blank_and_candidate_answer(self):
        item = {"stem":"圆周长 πd。①______ cm（保留三位有效数字）",
                "pi_checks":[{"blank":"①","expression":"3.118*pi"}]}
        self.assertTrue(any("9.79" in x and "9.80" in x for x in physics.pi_findings(item)))
        item["pi_checks"][0]["expression"] = "2*pi"
        self.assertEqual(physics.rounded("2*pi",3,True),[Decimal("6.28"),Decimal("6.28")])
        self.assertFalse(list(physics.pi_findings(item,"6.28")))
        self.assertTrue(list(physics.pi_findings(item,"给出 6.29 cm")))
        item["pi_checks"][0]["expression"] = "pi.__class__"
        self.assertTrue(any("无效" in x for x in physics.pi_findings(item,"6.28")))

    def test_pi_missing_or_unbound_record_cannot_pass(self):
        item = {"stem":"以圆周率计算，①______ m（保留两位小数）"}
        self.assertTrue(any("缺" in x for x in physics.pi_findings(item)))
        item["pi_checks"] = [{"blank":"②","expression":"pi"}]
        self.assertTrue(any("未绑定" in x for x in physics.pi_findings(item)))

    def test_chemistry_structure_not_only_crystal_front_context_and_blanks(self):
        rows = [{"stem":"求溶液组成 ____ ____ ____ ____","kind":"constructed_response"} for _ in range(18)]
        rows[0]["stem"] = "选择一种新能源装置"
        rows[2]["stem"] = "判断容量瓶的操作"
        rows[7]["stem"] = "依据晶胞判断晶体类型"
        rows[8]["stem"] = "由分子构型与杂化判断键角"
        self.assertFalse(exam_qa.corridor_findings("chemistry",{"questions":rows},[],[])[1])
        rows[0]["stem"],rows[8]["stem"],rows[16]["stem"] = "常规概念","简单代入","填 _____"
        _,findings = exam_qa.corridor_findings("chemistry",{"questions":rows},[],[])
        self.assertEqual({rule for _,rule,_ in findings},{"chemistry_structure","chemistry_front","chemistry_blanks"})
