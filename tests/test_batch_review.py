import copy
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bootstrap
from gaokao import ROOT
from core import batch_planner as batch
from core import exam_qa as qa
from core import review_board as board
from core import physics_corridor


def question(stem):
    return {"kind":"single_choice","stem":stem,"options":{"A":"可能","B":"必然","C":"所有样本","D":"较大"},
            "parts":[],"figure":None}


def state():
    return {"subject":"physics","ids":["a","b","c","d"],"pdf_sha256":"a"*64,"pages":1,
            "item_versions":{str(i):str(i) for i in range(1,5)},"rules":qa.policies(ROOT,"physics"),
            "preflight":{"passed":True,"issues":[]}}


def reports(s):
    items=[{"number":n,"answer":"A","reasoning":"从输入条件独立解出电流","comparison":"与两年该题位比较",
            "steps":["辨认回路"],"concepts":["电荷守恒"]} for n in range(1,5)]
    return [{"identity":"isolated-"+r,"role":r,"pdf_sha256":s["pdf_sha256"],"items":copy.deepcopy(items),
             "findings":[],"pages":[{"number":1,"note":"核对标签"}]} for r in board.ROLES]


def physics_batch(schedule):
    modules = ["optics_waves","atomic","astronomy","thermodynamics","mechanics","electrostatics_circuits",
               "magnetic_force","mechanics","induction_ac","optics_waves","mechanics","electrostatics_circuits",
               "mechanics","mechanics","induction_ac"]
    contexts = [
        ["折射棱镜水中排查","遏止电压改变","卫星绕木星","气缸放在晾晒区","惯性座椅安全带","固定电路的阻值",
         "磁场环路上的转弯","跑道机械能分段变化","电磁感应线圈方向","机械波的小船振动","加速度计插片",
         "测电阻刻度配置","动力模型车的动能","运动控制轮接近边沿","感应电动势的正负"],
        ["偏振光发讯速率","核反应的质量亏损","双星绕共同中心","理想气体的活塞比值","踏板产生的反向力与速度",
         "电势上升梯度图","载流导线磁场定位","闸门冲击的动量变化","交流电配套电压校准","透镜拼接光斑",
         "用动量测发射方向","电容量程误差界限","轨道交叉时的受力","摩擦换向临界","交变电流变压器的功率曲线"],
    ]
    role_slots = {n:role for role,(n,_) in physics_corridor.ROLE_SLOTS.items()}
    candidates = []
    for index, (blueprint, texts) in enumerate(zip(schedule["blueprints"],contexts,strict=True)):
        rows = []
        for n,(module,text,points) in enumerate(zip(modules,texts,physics_corridor.POINTS,strict=True),1):
            row = {**question(text),"physics_module":module,"points":points,
                   "design":{key:f"{key}{text}" for key in ("model","scene","action","representation")}}
            if n >= 13:
                row["parts"] = [{"text":"判断转折。"},{"text":"分析末态。"}]
            if n in role_slots:
                role = role_slots[n]
                row.update(batch_role=role,design=blueprint[role])
            rows.append(row)
        candidates.append({"subject":"physics","questions":rows})
    return candidates


class QualityTests(unittest.TestCase):
    def test_registered_subjects_and_ids(self):
        for name in batch.BRIEFS:
            rules=qa.policies(ROOT,name)
            self.assertTrue(any(r["subject"]==name for r in rules))

    def test_optics_is_not_waves_and_devices_once_per_item(self):
        rows=[question("弹簧、弹簧与机械波"),question("弹簧"),question("弹簧")]
        r=qa.inspect(ROOT,"physics",{"questions":rows},["A"]*3)
        self.assertFalse(r["passed"])
        self.assertEqual(r["coverage"]["光学"],[])
        self.assertEqual([i["number"] for i in r["issues"] if i["rule"]=="device"],[3])

    def test_measured_language_counts_only_wrong_options(self):
        q=question("用某植物检验物质 M，比较某林地样方")
        r=qa.inspect(ROOT,"biology",{"questions":[q]},["B"])
        self.assertEqual((r["wrong_options"],r["absolute_wrong_options"],r["abstract_mentions"]),(3,1,3))

    def test_old_scoring_and_notation(self):
        q=question(r"求 U\setminus A")
        r=qa.inspect(ROOT,"math",{"questions":[q]},["A"],header="选对但不全得3分")
        self.assertTrue({"notation","scoring"}<=set(i["rule"] for i in r["issues"]))

    def test_printed_constant_without_author_annotation(self):
        self.assertTrue(list(qa.printed_constant_errors("普朗克常量取 6.0×10^-34 J·s")))
        self.assertFalse(list(qa.printed_constant_errors("真空光速取 299792 km/s")))

    def test_actual_stopping_slope(self):
        def p(hz,v):
            return {"frequency":{"reading":hz,"anchor":hz,"scale":1e14},
                    "voltage":{"reading":v,"anchor":v,"scale":1}}
        obs={"number":1,"symbol":"h","method":"stopping_slope","measurements":[p("6.00","0.50"),p("9.00","1.70")]}
        q=question("6.00 9.00 0.50 1.70")
        r=qa.inspect(ROOT,"physics",{"questions":[q]},["A"],observations=[obs])
        self.assertIn("constant",[i["rule"] for i in r["issues"]])
        obs["measurements"][1]=p("9.00","1.74")
        with self.assertRaises(ValueError):qa.inspect(ROOT,"physics",{"questions":[q]},["A"],observations=[obs])
        q["stem"]=q["stem"].replace("1.70","1.74")
        r=qa.inspect(ROOT,"physics",{"questions":[q]},["A"],observations=[obs])
        self.assertNotIn("constant",[i["rule"] for i in r["issues"]])

    def test_bbox_legend_and_labels(self):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        f=Figure(figsize=(4,3));FigureCanvasAgg(f)
        a=f.subplots();a.bar([1],[76],label="ABA");a.set_ylim(0,100)
        a.legend(loc="center",bbox_to_anchor=(1,76),bbox_transform=a.transData)
        a.text(1,76,"76",va="center",ha="center")
        self.assertTrue(any("Legend" in pair for pair in qa.figure_collisions(f)))
        self.assertTrue(any("bar end" in pair for pair in qa.figure_collisions(f)))
        a.get_legend().remove();a.texts[0].set_position((1,83))
        self.assertFalse(qa.figure_collisions(f))


class BoardTests(unittest.TestCase):
    def test_revision_of_shared_passage_keeps_other_questions_locked(self):
        before=state()
        before["local_versions"]={str(n):f"body{n}" for n in (1,2,3)}
        before["material_groups"]={"1":"cloze","2":"cloze","3":"article"}
        rs=reports(before)
        rs[0]["findings"]=[{"number":2,"category":"fatal","rule":"all.solution","evidence":"缺少介词"}]
        prior=board.score_exam(before,rs)
        revised=copy.deepcopy(before)
        revised["item_versions"].update({"1":"passage-v2-1","2":"passage-v2-2"})
        self.assertEqual(board.score_exam(revised,reports(revised),prior)["status"],"eligible")
        revised["local_versions"]["1"]="modified-locked-question"
        with self.assertRaisesRegex(ValueError,"锁定"):
            board.score_exam(revised,reports(revised),prior)
        revised["local_versions"]["1"]="body1"
        revised["item_versions"]["3"]="unrelated-passage"
        with self.assertRaisesRegex(ValueError,"锁定"):
            board.score_exam(revised,reports(revised),prior)

    def test_fatal_veto_even_if_only_one(self):
        s=state();rs=reports(s)
        rs[0]["findings"]=[{"number":2,"category":"fatal","rule":"all.solution","evidence":"两个独立正确选项"}]
        r=board.score_exam(s,rs)
        self.assertEqual((r["final_score"],r["status"],r["locked"]),(0,"returned",[1,3,4]))

    def test_threshold_and_deduplication(self):
        s=state();rs=reports(s)
        f=[{"number":i,"category":"depth","rule":"physics.algebra","evidence":"一次代入即可完成"} for i in range(1,5)]
        rs[1]["findings"]=f
        rs[0]["findings"]=[dict(f[0],evidence="重复确认第1题")]
        r=board.score_exam(s,rs)
        self.assertEqual((r["final_score"],r["status"]),(84,"returned"))
        rs[1]["findings"][-1].update(category="weak",rule="all.absolute")
        self.assertEqual(board.score_exam(s,rs)["status"],"eligible")

    def test_locks_and_three_round_limit(self):
        s=state();rs=reports(s)
        rs[0]["findings"]=[{"number":1,"category":"fatal","rule":"all.solution","evidence":"无解"}]
        r=board.score_exam(s,rs)
        s["item_versions"]["3"]="bad"
        with self.assertRaises(ValueError):board.score_exam(s,rs,r)
        s["item_versions"]["3"]="3";s["item_versions"]["1"]="two"
        r=board.score_exam(s,rs,r)
        s["item_versions"]["1"]="three"
        r=board.score_exam(s,rs,r)
        self.assertEqual(r["status"],"rejected")
        with self.assertRaises(ValueError):board.score_exam(s,rs,r)

    def test_wrong_hash_reader_and_missing_page(self):
        for defect in ("hash","role","pages","item"):
            s=state();rs=reports(s)
            if defect=="hash":rs[0]["pdf_sha256"]="stale"
            if defect=="role":rs[1]["identity"]=rs[0]["identity"]
            if defect=="pages":rs[2]["pages"]=[]
            if defect=="item":rs[1]["items"].pop()
            with self.assertRaises(ValueError):board.score_exam(s,rs)

    def test_machine_before_board(self):
        s=state();s["preflight"]={"passed":False,"issues":[{"number":1,"rule":"constant","evidence":"单位错"}]}
        with self.assertRaises(ValueError):board.score_exam(s,reports(s))
        self.assertEqual(board.score_exam(s,[])["status"],"returned")

    def test_actual_blind_answer_disagrees(self):
        s=state();s["choice_keys"]={"1":"B"}
        self.assertEqual(board.score_exam(s,reports(s))["final_score"],0)

    def test_open_recitation_accepts_only_complete_verified_cells(self):
        s=state()
        s["exact_keys"]={"1":["舟过江声急","云开暮色寒","远树浮山外","归人到渡头"]}
        s["exact_key_variants"]={"1":[["舟过江声急","云开暮色寒","潮平两岸阔","风正一帆悬"]]}
        replies=reports(s)
        answer=replies[0]["items"][0]
        answer["answer"]="（1）舟过江声急，云开暮色寒。（2）潮平两岸阔，风正一帆悬。"
        self.assertEqual(board.score_exam(s,replies)["status"],"eligible")
        answer["answer"]=["舟过江声急云","开暮色寒","潮平两岸阔","风正一帆悬"]
        self.assertEqual(board.score_exam(s,replies)["fatal_count"],1)


class BatchTests(unittest.TestCase):
    def test_capacity_and_all_subjects(self):
        for subject in batch.BRIEFS:
            p=batch.plan(subject,3)
            self.assertEqual(len(p["blueprints"]),3)
        with self.assertRaises(ValueError):batch.plan("physics",4)

    def test_reserves_disjoint_and_checks_content(self):
        p=batch.plan("physics",2)
        cs=physics_batch(p)
        self.assertTrue(batch.check(p,cs)["passed"])
        cs[0]["questions"][7]["stem"]="物体以2米每秒向右运动，求刚到右端时的动量变化"
        cs[1]["questions"][7]["stem"]=cs[0]["questions"][7]["stem"].replace("2","3")
        self.assertIn("跨卷设计或文字撞车",[x["reason"] for x in batch.check(p,cs)["issues"]])
        cs[1]["questions"][7]["stem"]="完全换一个关于运动的叙述"
        cs[1]["questions"][7]["design"]=cs[0]["questions"][7]["design"]
        self.assertIn("跨卷设计或文字撞车",[x["reason"] for x in batch.check(p,cs)["issues"]])

class WorkflowTests(unittest.TestCase):
    def test_plan_and_host_resume(self):
        from core.batch_runner import run
        from forecast_store import write_new
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);f=base/"schedule.json"
            write_new(f,batch.plan("physics",2))
            r=run(ROOT,f,2027,base/"ctx",base/"job",None)
            self.assertEqual(r["state"],"await_host_author")
            self.assertEqual(len(r["required"]),2)

    def test_collision_replay_on_actual_stage_one_formulas(self):
        a="A、B、C 的体积、压强坐标依次为（V₀，2p₀）、（2V₀，p₀）、（2V₀，2p₀），A到B沿直线"
        b=r"B 为 \((V_0,2p_0)\)，C 为 \((2V_0,p_0)\)，B 到 C 为直线"
        self.assertTrue(batch.implied_models(a)&batch.implied_models(b))
        self.assertFalse(batch.implied_models("刚性容器在恒压下排气"))

    def test_math_reuses_resolved_conditions(self):
        q={"writing":{"stem":"圆的半径为 {{f1}}。","parts":[{"text":"求 {{f2}}"}],
                      "formulae":{"f1":{"latex":"r"},"f2":{"latex":"M"}}}}
        self.assertEqual(batch.question_text(q),"圆的半径为 r。 求 M")

    def test_units_make_one_fragment(self):
        from mathgen.cjk_layout import measured_markup
        line=measured_markup("压强90 kPa，g=10 m/s²。")
        self.assertIn("<nobr>90&nbsp;kPa</nobr>",line)
        self.assertIn("<nobr>10&nbsp;m/s<super>2</super></nobr>",line)

    def test_readers_receive_only_allowlisted_fields(self):
        from unittest.mock import patch
        from core.review_board import blind_bundle
        with tempfile.TemporaryDirectory() as t:
            f=Path(t);(f/"paper.pdf").write_bytes(b"pdf-only")
            (f/"independent-review.json").write_text("private-answer",encoding="utf8")
            s=state();s["rules"]=[];s["subject"]="physics"
            with patch("core.review_board.evidence",return_value=s):
                payload=blind_bundle(ROOT,f,"solver")
            self.assertEqual(set(payload),{"role","rules","benchmarks","listening_script","student_pdf"})
            self.assertEqual(payload["student_pdf"],b"pdf-only")
            self.assertNotIn("private-answer",str(payload))

    def test_replay_refuses_tampered_card(self):
        from forecast_store import write_new
        from storage import atomic_json
        s=state();raw=reports(s)
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            r=board.score_exam(s,raw)
            write_new(folder/"round1.json",{"state":s,"reports":raw})
            write_new(folder/"scorecard-round1.json",r)
            self.assertEqual(board.replay(folder)["status"],"eligible")
            r["final_score"]=84;atomic_json(folder/"scorecard-round1.json",r)
            with self.assertRaises(ValueError):board.replay(folder)

    def test_rejects_unsigned_scored_publication(self):
        with tempfile.TemporaryDirectory() as t, self.assertRaises(ValueError):
            board.authorize(ROOT,Path(t))
