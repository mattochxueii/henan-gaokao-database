"""Content-length and three-section integration tests on synthetic test fixtures."""
import contextlib
from copy import deepcopy
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import bootstrap
from core import exam_qa, language_corridor as language, language_sections, language_workflow, review_board
from core.practice_workbook import authoring_context
from gaokao import ROOT, digest, read_json, write_json
from gaokao_platform import main


def chinese_draft():
    draft = read_json(ROOT/"experiments/phase26/chinese/source/final-candidate.json")
    for material, count in (("map",1650),("story",1650),("classic",600)):
        draft["materials"][material]["text"] = ("春风拂柳晴光映入桥窗"*(count//10+2))[:count]
    for n in (12,15):
        draft["questions"][n-1]["stem"] = "下列说法不正确的一项是（　　）"
    item = draft["questions"][16]
    item["stem"] = item["stem"].replace("苏轼《念奴娇·赤壁怀古》","王安石《泊船瓜洲》")
    item["recitation_sources"] = [
        {"author":"李白","title":"蜀道难"},{"author":"苏轼","title":"赤壁赋"},{"author":"王安石","title":"泊船瓜洲"}]
    for value in [*draft["questions"],*draft["materials"].values()]:
        for key in ("stem","text"):
            if key in value:
                value[key] = value[key].replace("‘","“").replace("’","”")
        for k,text in value.get("options",{}).items():
            value["options"][k] = text.replace("‘","“").replace("’","”")
    return draft


WORDS = "When local people examine public evidence they may change priorities after hearing thoughtful testimony from three nearby communities"
GRAMMAR = [
    ("each [56] ____ (carry) a letter", "carrying", "nonfinite", "ing"),
    ("The museum [57] ____ (receive) it last spring.", "received", "finite", "tense"),
    ("It was [58] ____ urgent delivery.", "an", "determiner", "article"),
    ("The boy [59] ____ letter was red waited.", "whose", "clause", "relative"),
    ("It was a [60] ____ (science) test.", "scientific", "conversion", "adjective"),
    ("They tried [61] ____ (remove) the label.", "to remove", "nonfinite", "infinitive"),
    ("It matched the guide's record [62] ____ (exact).", "exactly", "conversion", "adverb"),
    ("They took pride [63] ____ it.", "in", "preposition", "collocation"),
    ("The result [64] ____ (record) before lunch.", "was recorded", "finite", "passive"),
    ("They stored two [65] ____ (tablet) there.", "tablets", "inflection", "number"),
]


def english_draft():
    draft = read_json(ROOT/"experiments/phase26/english/candidate-final.json")
    draft["materials"]["L01"]["text"] = "听第1段录音，回答第1题。"
    for key in "ABCD":
        draft["materials"][key]["text"] = (WORDS+". ")*20
    for number, quoted in ((26,"I knew because I had painted them"),(33,"a small journey")):
        item = draft["questions"][number-1]
        item["stem"] = item["stem"].replace(f"'{quoted}'",f"“{quoted}”")
    draft["materials"]["U"]["text"] = " ".join(x[0] for x in GRAMMAR)
    for q, (_, answer, category, form) in zip(draft["questions"][55:65],GRAMMAR,strict=True):
        q.update(answer=answer,grammar_tag={"category":category,"form":form})
    return draft


def lang_rules(subject,draft):
    fields = list(language.student_fields(draft))
    return exam_qa.corridor_findings(subject,draft,[q["answer"] for q in draft["questions"]],fields)[1]


class LanguageCorridor27Tests(TestCase):
    def test_numbered_blank_does_not_break_in_print(self):
        from pypdf import PdfReader
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from core.language_render import render
        from mathgen.export import chinese_font

        width=A4[0]-2*(49+6)
        def measure(text):
            return stringWidth(text,chinese_font(),10.7)
        prefix=""
        while measure(prefix+"x [45]") <= width:
            prefix+="x "
        self.assertGreater(measure(prefix+"[45] ____"),width)
        paper={"subject":"english","title":"Grammar exercise","minutes":5,"points":1,
               "sections":[{"id":"cloze","title":"Cloze"}],
               "materials":{"story":{"title":"Text","text":prefix+"[45] ____ in this sentence."}},
               "questions":[{"number":45,"points":1,"section":"cloze","kind":"single_choice",
                             "material":"story","stem":"Choose the word."}]}
        with TemporaryDirectory() as d:
            name=Path(d)/"sample"
            render(paper,name)
            text=PdfReader(name.with_suffix(".pdf")).pages[0].extract_text()
            self.assertRegex(text,r"\[45\][^\S\r\n]+____")

    def test_chinese_limits_count_each_passage_once(self):
        draft = chinese_draft()
        self.assertFalse(lang_rules("chinese",draft))
        draft["materials"]["map"]["text"] = "春"*1599
        draft["materials"]["story"]["text"] = "春"*2301
        draft["questions"][0]["stem"] += "夏"*600
        self.assertEqual([(n,code) for n,code,_ in lang_rules("chinese",draft)],
                         [(1,"chinese_volume"),(6,"chinese_volume")])

    def test_classical_title_and_hidden_whole_text(self):
        draft = chinese_draft()
        draft["materials"]["classic"]["text"] += "（节选自《庖丁解牛》）"
        self.assertTrue(any(code=="chinese_classical" for _,code,_ in lang_rules("chinese",draft)))
        draft["materials"]["classic"]["text"] = "学不可以已。青，取之于蓝，而青于蓝。"
        self.assertEqual(language.familiar_material(draft["materials"]["classic"]),"劝学")
        self.assertIsNone(language.familiar_material({"title":"读书随想","text":"少年只引《师说》中一句作注。"}))

    def test_negative_questions_and_true_recitation_repeat(self):
        draft = chinese_draft()
        for n in (12,15):
            draft["questions"][n-1]["stem"] = "下列说法最恰当的一项是（　　）"
        draft["questions"][16]["recitation_sources"][-1]["author"] = "苏东坡"
        issues = lang_rules("chinese",draft)
        self.assertEqual({(n,code) for n,code,_ in issues},
                         {(12,"chinese_prompt"),(15,"chinese_prompt"),(17,"chinese_recitation")})
        self.assertTrue(any("重复" in reason for _,_,reason in issues))

    def test_chinese_quote_gate_on_passage_question_and_option(self):
        draft = chinese_draft()
        draft["materials"]["map"]["text"] += "文中‘一级引文’"
        draft["questions"][1]["stem"] += "‘一级’"
        draft["questions"][2]["options"]["B"] += "有‘例子’"
        self.assertEqual({n for n,code,_ in lang_rules("chinese",draft) if code=="chinese_quote"},{1,2,3})
        self.assertFalse(language.primary_single_quote("他说：“所谓‘清流’，由此得名。”",chinese=True))

    def test_english_words_and_separate_sentence_lengths(self):
        draft = english_draft()
        self.assertFalse(lang_rules("english",draft),lang_rules("english",draft))
        draft["materials"]["C"]["text"] = "One quick test. "*120
        result = lang_rules("english",draft)
        self.assertTrue(any(code=="english_sentence" and evidence.startswith("C") for _,code,evidence in result))
        self.assertFalse(any(code=="english_volume" for _,code,_ in result))
        draft["materials"]["C"]["text"] = "A sentence."
        self.assertTrue(any(code=="english_volume" for _,code,_ in lang_rules("english",draft)))

    def test_english_grammar_concentration_and_wrong_surface_tag(self):
        draft = english_draft()
        grammar = draft["materials"]["U"]
        grammar["text"] = grammar["text"].replace("It was a [60] ____ (science) test.","They enjoyed [60] ____ (test) it.")
        for n, key in ((60,"testing"),(61,"removing")):
            draft["questions"][n-1].update(answer=key,grammar_tag={"category":"nonfinite","form":"ing"})
        issues = lang_rules("english",draft)
        self.assertTrue(any(n==61 and "超过 2" in detail for n,_,detail in issues))
        self.assertTrue(any("至少覆盖两种" in detail for _,_,detail in issues))
        draft["questions"][55]["grammar_tag"] = {"category":"finite","form":"passive"}
        self.assertTrue(any(n==56 and "语形" in evidence for n,_,evidence in lang_rules("english",draft)))

    def test_english_grammar_missing_clause_and_blank_number(self):
        draft = english_draft()
        draft["questions"][58]["grammar_tag"] = {"category":"pronoun","form":"relative_reference"}
        self.assertTrue(any("含谓语、非谓语、词性转换和从句" in e for _,_,e in lang_rules("english",draft)))
        draft["materials"]["U"]["text"] = draft["materials"]["U"]["text"].replace("[64]", "[63]")
        self.assertTrue(any("不重复" in e for _,_,e in lang_rules("english",draft)))

    def test_time_quotes_and_american_spelling(self):
        self.assertTrue(language.dotted_time("We leave at 13.45 tomorrow."))
        self.assertTrue(language.dotted_time("10.45"))
        self.assertFalse(language.dotted_time("It starts at 13:45 and then lasts 10.45 minutes."))
        self.assertFalse(language.dotted_time("The line was about 13.45 m; the ticket costs $10.45."))
        self.assertTrue(language.primary_single_quote("They described the policy as 'hard to use'.",chinese=False))
        self.assertFalse(language.primary_single_quote("The guide's book holds students’ papers.",chinese=False))
        self.assertFalse(language.primary_single_quote('She said, "Call the test \'Home\'," and left.',chinese=False))
        self.assertTrue(list(language.spelling_warnings([(1,"The colour and grey tones match.")])))


def write_fragments(folder, subject, draft):
    paths = [folder/f"part{n}.json" for n in (1,2,3)]
    for index, members in enumerate(language_sections.PARTS[subject],1):
        questions = [q for q in draft["questions"] if q["section"] in members]
        keys = {q["material"] for q in questions if q.get("material")}
        part = {"protocol":language_sections.PROTOCOL,"paper_id":draft["id"],"subject":subject,"part":f"part{index}",
                "questions":questions,"materials":{k:v for k,v in draft["materials"].items() if k in keys},
                "reference_notes":["按同一题组的蓝图设置测试素材。"]}
        if index == 1:
            part["title"] = draft["title"]
            if subject == "english":
                part["listening"] = draft["listening"]
        write_json(paths[index-1],part)
    context = folder/"context.json"
    write_json(context,authoring_context(ROOT,subject))
    return paths, context


class Merge27Tests(TestCase):
    def test_chinese_merge_runs_through_unified_cli(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            paths, ctx = write_fragments(folder,"chinese",chinese_draft())
            merged = folder/"candidate.json"
            with contextlib.redirect_stdout(StringIO()):
                rc = main(["merge-sections","chinese","2027",str(merged),*map(str,reversed(paths)),"--context",str(ctx)])
            self.assertEqual(rc,0)
            data = read_json(merged)
            self.assertEqual([q["number"] for q in data["questions"]],list(range(1,23)))
            self.assertEqual(sum(q["points"] for q in data["questions"]),150)
            self.assertEqual(data["provenance"]["context_sha256"],digest(ctx))
            language_workflow.validate_structure(language_workflow.plan(ROOT,"chinese","河南",2027),data)

    def test_english_merge_keeps_listening_keys_in_student_order_and_simulates(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            original = english_draft()
            original["listening"] = dict(reversed(list(original["listening"].items())))
            paths, ctx = write_fragments(folder,"english",original)
            candidate = folder/"candidate.json"
            result = language_sections.merge(ROOT,"english",2027,paths,ctx,candidate)
            data = read_json(candidate)
            self.assertEqual((result["questions"],result["points"]),(67,150))
            self.assertEqual(list(data["listening"]),[f"L{n:02d}" for n in range(1,11)])
            self.assertEqual(len(data["provenance"]["section_sha256"]),3)
            out = folder/"review"
            from unittest.mock import patch

            with contextlib.redirect_stdout(StringIO()), patch(
                    "core.language_render.english_font",return_value="Times-Roman"):
                rc = main(["simulate","english","2027",str(candidate),str(out),"--context",str(ctx)])
            self.assertEqual(rc,0)
            state = review_board.evidence(ROOT,out)
            self.assertFalse(state["preflight"]["passed"])
            self.assertEqual({i["rule"] for i in state["preflight"]["issues"]},
                             {"english_listening_length","english_cross_item_leak"})
            self.assertEqual(state["protocol"],review_board.VERSION)

    def test_merge_rejects_cross_section_wrong_score_and_duplicate_part(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            paths, ctx = write_fragments(folder,"chinese",chinese_draft())
            out = folder/"candidate.json"
            first = read_json(paths[0])
            bad = deepcopy(first)
            bad["questions"][0]["points"] += 1
            write_json(paths[0],bad)
            with self.assertRaisesRegex(ValueError,"逐题分值"):
                language_sections.merge(ROOT,"chinese",2027,paths,ctx,out)
            bad = deepcopy(first)
            bad["questions"][0]["material"]="classic"
            write_json(paths[0],bad)
            with self.assertRaisesRegex(ValueError,"跨片段"):
                language_sections.merge(ROOT,"chinese",2027,paths,ctx,out)
            with self.assertRaisesRegex(ValueError,"各提供"):
                language_sections.merge(ROOT,"chinese",2027,[paths[0],paths[0],paths[2]],ctx,out)
            self.assertFalse(out.exists())

    def test_merge_rejects_low_volume_and_keeps_existing_output(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            draft = chinese_draft()
            draft["materials"]["map"]["text"]="缩短。"
            paths, ctx = write_fragments(folder,"chinese",draft)
            out = folder/"candidate.json"
            write_json(out,{"existing":True})
            with self.assertRaisesRegex(ValueError,"合卷硬安检失败"):
                language_sections.merge(ROOT,"chinese",2027,paths,ctx,out)
            self.assertEqual(read_json(out),{"existing":True})
