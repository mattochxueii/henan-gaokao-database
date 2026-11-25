
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import bootstrap
from pypdf import PdfReader

from core import chinese_corpus, language_render, marking_standards, publication_ledger, review_board, review_probe
from core.native_tables import normalize_table
from core.release_checks import VERSION, choice_findings, layout_evidence, leaked_blanks, listening_words
from gaokao import ROOT, read_json
from mathgen.student_pdf import formula_image, normalise_tex, render, science_section_note
from mathgen.wireframe import hidden_edges


def simple(number=1):
    return {"id":f"orig:chinese:fixture:q{number:02}","number":number,"points":8,"kind":"response",
            "section":"essay" if number==22 else "classical",
            "stem":"结合<dot>礼</dot>字和<wave>文辞简练</wave>分析。请在答题卡的相应位置作答。"}


class ReleaseLogicTests(TestCase):
    def test_math_progression_uses_bound_part_labels_and_text(self):
        from core.release_checks import math_checks

        rows=[{"stem":"求值","parts":[]} for _ in range(19)]
        rows[17]["parts"]=[{"label":f"（{n}）","text":"求范围"} for n in range(1,4)]
        texts=["双曲线、抛物线、正态分布和数列"]*19
        self.assertNotIn("math_progression",{issue[1] for issue in math_checks({},rows,texts)})
        rows[17]["parts"][2]["text"]=""
        self.assertIn("math_progression",{issue[1] for issue in math_checks({},rows,texts)})

    def test_choices_detect_four_consecutive_keys_and_accept_balanced(self):
        rows=[{"kind":"single_choice"}]*8
        self.assertFalse(list(choice_findings(rows,list("ABCDABCD"),"math")))
        actual=list(choice_findings(rows,list("ABBBBDCA"),"math"))
        self.assertIn("answer_streak",{x[1] for x in actual})

    def test_blank_leak_requires_the_relevant_step(self):
        q={"stem":"步骤2氧化；步骤5将羰基还原。","parts":[{"text":"步骤5的反应类型为①________。"}]}
        self.assertEqual(list(leaked_blanks(q,["还原反应"])),[("①","还原反应")])
        self.assertFalse(list(leaked_blanks({**q,"stem":"步骤2还原；步骤5处理。"},["还原反应"])))

    def test_marking_templates_and_choice_partial_credit(self):
        templates=marking_standards.language_template
        self.assertIn("20～16 / 15～11 / 10～6 / 5～0",templates("chinese",22,60)[0])
        self.assertIn("每少50字扣1分","".join(templates("chinese",22,60)))
        self.assertIn("超过三处不给分","".join(templates("chinese",10,3)))
        self.assertIn("有错字、漏字、添字","".join(templates("chinese",17,6)))
        self.assertIn("综合评分","".join(templates("chinese",9,8)))
        self.assertEqual(len(templates("english",66,15)),7)
        self.assertIn("权重40%","".join(templates("english",67,25)))
        self.assertIn("得3分",marking_standards.math_choice("multiple_choice","AB",6))
        self.assertIn("得2分",marking_standards.math_choice("multiple_choice","BCD",6))
        self.assertIn("得4分",marking_standards.math_choice("multiple_choice","BCD",6))
        self.assertNotIn("等价",marking_standards.math_choice("single_choice","A",5))
        with self.assertRaises(ValueError):
            marking_standards.math_choice("multiple_choice","AA",6)

    def test_timing_and_anchor_defects(self):
        requirements=review_probe.instructions("physics")
        probe={"role":"pedagogy","dimensions":{d:"根据终版卷面逐题核对过依据" for d in requirements["dimensions"]},
               "difficulty_probe":{"minutes":{mode:{block:14 for block in requirements["blocks"]}
                                              for mode in requirements["profiles"]},
                                   "gate_items":[{"number":n,"reasoning":"逐段对照能量与受力条件",
                                                  **{flag:False for flag in requirements["gate_flags"]}}
                                                 for n in requirements["gate_items"]]}}
        self.assertFalse(list(review_probe.reply_findings("physics",probe)))
        probe["difficulty_probe"]["minutes"]["advanced"]["single"]=9
        probe["difficulty_probe"]["gate_items"][0]["recalled_routine"]=True
        self.assertEqual({r[1] for r in review_probe.reply_findings("physics",probe)},
                         {"board.timing_floor","board.anchor_failed"})
        self.assertIn("board.eight_dimensions",{r[1] for r in review_probe.reply_findings("math",{"role":"visual"})})

    def test_probe_is_a_fatal_board_decision(self):
        roles=review_board.ROLES
        state={"subject":"math","ids":list(range(1,20)),"version":"paper-v1",
               "protocol":review_board.VERSION,"release_rules":VERSION,
               "pdf_sha256":"f"*64,"pages":1,"rules":[],
               "preflight":{"passed":True,"issues":[]},"item_versions":{str(n):str(n) for n in range(1,20)}}
        reports=[{"role":role,"identity":role,"pdf_sha256":"f"*64,
                  "items":[{"number":n,"answer":"1","reasoning":"独立核对","comparison":"证据","steps":2,"concepts":1}
                           for n in range(1,20)],"findings":[],"pages":[{"number":1,"note":"已读"}]}
                 for role in roles]
        card=review_board.score_exam(state,reports)
        self.assertEqual((card["status"],card["final_score"]),("returned",0))
        self.assertGreater(card["fatal_count"],0)
        self.assertIn("board.timing_missing",{x["rule"] for x in card["deductions"]})

    def test_external_probe_can_require_repair_without_free_text_findings(self):
        from core.external_review import PROTOCOL, effective_findings, repair_targets

        card={"subject":"physics","ids":list(range(1,16)),"paper_version":"paper",
              "pdf_sha256":"f"*64,"release_rules":VERSION}
        reply={"protocol":PROTOCOL,"paper_version":"paper","pdf_sha256":"f"*64,"model_family":"external",
               "model":"test","findings":[],"dimensions":{},"difficulty_probe":{}}
        self.assertTrue(all(x["severity"]=="fatal" for x in effective_findings(reply,card)))
        self.assertEqual(repair_targets([reply],card,[]),({15},False))

    def test_only_one_logical_paper_in_a_session(self):
        with TemporaryDirectory() as folder:
            session=Path(folder)/"receipt.json"
            candidate={"subject":"physics","questions":[{"id":"orig:physics:test:q1"}]}
            original=publication_ledger.claim(session,"physics",candidate)
            self.assertEqual(publication_ledger.claim(session,"physics",candidate),original)
            with self.assertRaisesRegex(ValueError,"同一任务"):
                publication_ledger.claim(session,"physics",{**candidate,"questions":[{"id":"orig:physics:test2:q1"}]})
            with self.assertRaisesRegex(ValueError,"同一任务"):
                publication_ledger.claim(session,"math",{"subject":"math","questions":[{"id":"orig:math:test:q1"}]})

    def test_ledger_detects_repeat_ignoring_the_new_id(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            paper={"questions":[{"id":"orig:physics:one:q1","stem":"逐段计算线圈分段运动，比较对应的电压峰值。",
                                 "experiment_archetype":"two-signal-phase"}]}
            publication_ledger.register(root,"physics",paper,"1"*64,published_on="2026-11-24")
            self.assertEqual(publication_ledger.history(root,"physics")[0]["date"],"2026-11-24")
            self.assertFalse(list(publication_ledger.reuse_findings(root,"physics",paper,"1"*64)))
            updated={"questions":[{**paper["questions"][0],"id":"orig:physics:two:q1"}]}
            self.assertEqual(len(list(publication_ledger.reuse_findings(root,"physics",updated))),2)

    def test_memorization_confirms_exact_characters_and_no_duplicate_author(self):
        titles=[{"title":"阿房宫赋","author":"杜牧"},{"title":"赤壁赋","author":"苏轼"},
                {"title":"春江花月夜","author":"张若虚"}]
        key=["歌台暖响","春光融融","寄蜉蝣于天地","渺沧海之一粟","江畔何人初见月","江月何年初照人"]
        self.assertFalse(list(chinese_corpus.recitation_findings(ROOT,titles,key)))
        broken=[*key[:-1],"江月何年初照入"]
        self.assertTrue(list(chinese_corpus.recitation_findings(ROOT,titles,broken)))
        self.assertTrue(list(chinese_corpus.recitation_findings(ROOT,[titles[0],titles[1],titles[0]],key)))

    def test_corpus_volume_and_reading_length(self):
        records=chinese_corpus.manifest(ROOT)
        self.assertEqual(records["required-memorization.json"]["entries"],60)
        chosen=chinese_corpus.catalog(ROOT,"classical-unfamiliar-pool.json")
        prose=[r for r in chosen if r["kind"]=="prose"]
        self.assertTrue(30<=len(prose)<=40)
        self.assertTrue(all(520<=len(chinese_corpus.plain(x["text"]))<=750 and x["collection"] for x in prose))
        self.assertLess(sum((ROOT/value["path"]).stat().st_size for value in records.values()),500_000)

    def test_tts_only_has_speaker_lines(self):
        with TemporaryDirectory() as folder:
            output=Path(folder)/"listening-tts.txt"
            language_render.export_tts({"L01":"M: At 10:45?\nW: Yes, I'll be there.","L02":"W: Here is the report."},output)
            self.assertEqual(output.read_text(encoding="utf-8"),"M: At 10:45?\nW: Yes, I'll be there.\n\nW: Here is the report.\n")
            self.assertEqual(listening_words({"L01":"M: At 10:45?\nW: Yes, I'll be there."}),6)
            with self.assertRaisesRegex(ValueError,"说话人"):
                language_render.export_tts({"L01":"监考：每段播放两遍"},output)


class ReleaseRenderTests(TestCase):
    def test_practice_writing_grid_and_exam_direction_are_printed(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            questions=[simple(13),simple(22)]
            paper={"layout_mode":"practice","title":"排版验收","minutes":150,"points":150,"subject":"chinese",
                   "sections":[{"id":"classical","title":"文言文阅读"},{"id":"essay","title":"写作"}],
                   "materials":{},"questions":questions}
            language_render.render(paper,root/"practice")
            self.assertEqual(layout_evidence(root/"practice.pdf"),
                             {"essay_grid_cells":1000,"essay_columns_and_rows":{20:50},"essay_800_mark":True})
            practice="\n".join(page.extract_text() for page in PdfReader(root/"practice.pdf").pages)
            self.assertNotIn("答题卡",practice)
            self.assertIn("共",practice)
            language_render.render({**paper,"layout_mode":"exam"},root/"exam")
            self.assertEqual(layout_evidence(root/"exam.pdf")["essay_grid_cells"],0)
            exam="\n".join(page.extract_text() for page in PdfReader(root/"exam.pdf").pages)
            self.assertIn("请在答题卡相应位置作答",exam)
            self.assertIn("礼",exam)
            self.assertIn("文辞简练",exam)

    def test_optical_visibility_figure_edges_ignore_legacy_dashes(self):
        vertices={"A":(0,0,0),"B":(4,0,0),"C":(4,4,0),"D":(0,4,0),"P":(0,0,3),"M":(0,2,1.5)}
        hidden=hidden_edges(vertices,[("P","A"),("P","D"),("C","D"),("M","C")],(6,-6,4))
        self.assertNotIn(frozenset(("P","A")),hidden)
        self.assertTrue({frozenset(e) for e in [("P","D"),("C","D"),("M","C")]}<=hidden)

    def test_complement_glyph_and_centered_triangle_render(self):
        with TemporaryDirectory() as folder:
            from PIL import Image

            tex=normalise_tex(r"\complement_U A\quad \triangle ABC")
            self.assertIn("∁",tex)
            self.assertNotIn("mathbb{C}",tex)
            image=Path(folder)/"glyph.png"
            formula_image(tex,image)
            with Image.open(image) as glyph:
                self.assertGreater(glyph.width,50)

    def test_native_science_table_is_selectable_and_editable(self):
        from docx import Document
        from forecast_store import write_new

        with TemporaryDirectory() as folder:
            root=Path(folder)
            cells=normalize_table({"headers":["组别","温度（℃）"],"rows":[["甲","24"],["乙","30"]],"caption":"表1"})
            q={"id":"orig:biology:table:q1","order":1,"kind":"constructed_response","points":8,
               "stem":"如表所示，计算两组的温度差。","parts":[],"options":{},"table":cells}
            paper={"layout_mode":"exam","layout":"science","subject":"biology","title":"表格验收",
                   "minutes":5,"total_points":8,"questions":[q]}
            render(paper,root/"paper.pdf")
            text=PdfReader(root/"paper.pdf").pages[0].extract_text()
            self.assertIn("组别",text)
            self.assertIn("24",text)
            self.assertNotIn("计算题须写出",text)
            write_new(root/"blind-packet.json",{"paper":paper})
            language_render.export_docx(root/"paper.md",root/"paper.docx")
            self.assertEqual(Document(root/"paper.docx").tables[0].cell(1,1).text,"24")
            with self.assertRaisesRegex(ValueError,"列数"):
                normalize_table({"headers":["甲","乙"],"rows":[["24"]]})

    def test_strict_english_checks_available_typed_font(self):
        with TemporaryDirectory() as folder:
            with mock.patch.dict("os.environ",{"GAOKAO_TIMES_NEW_ROMAN":str(Path(folder)/"absent.ttf")}):
                self.assertEqual(language_render.english_font(),"Times-Roman")
                with self.assertRaisesRegex(ValueError,"Times New Roman"):
                    language_render.english_font(strict=True)

    def test_science_instructions_restrict_the_calculation_note(self):
        rows=[{"points":20}]
        self.assertIn("计算题须写出",science_section_note("constructed_response",rows,subject="physics"))
        for s in ("chemistry","biology"):
            self.assertNotIn("计算题须写出",science_section_note("constructed_response",rows,subject=s))

    def test_cartesian_figure_requires_labeled_axes_then_saves(self):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from core.exam_qa import exam_axes, save_figure

        with TemporaryDirectory() as folder:
            path=Path(folder)/"plot.png"
            fig=Figure(figsize=(5,3))
            FigureCanvasAgg(fig)
            ax=fig.subplots()
            ax.plot([0,1],[1,2])
            with self.assertRaisesRegex(ValueError,"双轴"):
                save_figure(fig,path,subject="physics",cartesian=True)
            exam_axes(ax,r"$t$ / s",r"$x$ / m")
            save_figure(fig,path,subject="physics",cartesian=True)
            self.assertTrue(path.exists())
