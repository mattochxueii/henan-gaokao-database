"""Build evidence and new English test from the material in this directory."""
import json
import re
import sys
from pathlib import Path

from language import (
    app_rubric, app_sample, application, cloze, cloze_items, cont_prompt,
    cont_rubric, cont_sample, continuation, gap, gap_keys, gap_options,
    grammar, grammar_keys,
)
from listening import items as heard
from listening import texts
from reading import reading, reading_items

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from analysis_db import fingerprint
from core.language_workflow import plan
from gaokao import digest, read_json

OUT = ROOT / "experiments/phase26/english"
WORK = Path(__file__).parent
CONTEXT = WORK / "authoring-context.json"
ID = "hn26-springmill-v1"


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def english_words(s):
    return len(re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*", s))


def build():
    blueprint = plan(ROOT, "english", "河南", 2027)
    context = read_json(CONTEXT)
    sections = {}
    for group in blueprint["sections"]:
        for n, points in enumerate(group["scores"], group["first"]):
            sections[n] = (group["id"], group["kinds"][0], points)
    mapping = [
        "参照 A 篇参赛费用和名额检索、B 篇按成长事件取证；保留报名条件与叙事顺序，改为磨坊入场和剧场画景。",
        "参照 B 篇翻谱者职业细节及 D 篇大众理解与概念区分；改写为刷子尺寸的误会和店内、家庭两种统计范围。",
        "参照课程规则、人与项目报道的材料功能；新卷通过活动预约方式的例外与讲解方法检验信息归属。",
        "参照 A 篇自行车活动和 D 篇前后研究的关系；本卷比较摆绳方向、暂停控制和未证机制，未沿用原研究。",
        "参照 A 篇志愿活动筛选、C 篇阅读介质比较及听力应答意图；重新设定场馆门票、绳结学习和音效制作。",
        "参照 B 篇经历揭示主题、D 篇具体例证的作用、应用文做选择并陈述理由；新题改为舞台远观、反馈自选偏差、给广播节目推荐物件。",
        "河南演练：A 篇四处景点筛选、D 篇研究目的及第二次到场的理由；用于核对英语语域、任务表述和研究设计题的难度。",
        "参照 A 篇场馆活动条件、Q30 语境义、D 篇实验程序与结论；本卷要求从 bakery 的指标含义和配对观看的控制条件界定结论。",
    ]
    papers = []
    for source, note in zip(sorted((ROOT / "data/papers/english").glob("*.json")), mapping, strict=True):
        doc = read_json(source)
        row = {"paper_id":doc["id"], "year":doc["year"], "exam_kind":doc["exam_kind"],
               "scope":"笔试正文47题" if doc.get("written_only") else "含听力的完整67题",
               "questions":len(doc["questions"]), "passages":len(doc["passages"]),
               "reading_words":[english_words(x) for x in list(doc["passages"].values())[:4]],
               "filename":source.relative_to(ROOT).as_posix(), "file_sha256":digest(source),
               "content_sha256":doc["content_sha256"], "passages_sha256":fingerprint(doc["passages"]),
               "listening_groups":len(doc.get("listening_transcript",{})),
               "reference_note":note}
        papers.append(row)
    evidence = {"series":"全国新高考Ⅰ卷／全国Ⅰ卷", "target_year":2027,
                "basis_year":2026, "official_papers":7, "adaptation_papers":1,
                "dna_path":"data/dna/english.json","dna_sha256":context["dna_sha256"],
                "blueprint_sha256":fingerprint(blueprint),
                "context_sha256":digest(CONTEXT),"context_query":context["query"],
                "context_formal_fulltext_references":len(context["references"]),
                "context_rehearsal_references":len(context["rehearsal_references"]),
                "platform_fulltext_corpus_sha256":fingerprint(context["language_corpus"]),
                "eight_paper_manifest_sha256":fingerprint(papers),"papers":papers}
    save(OUT / "source-binding.json", evidence)
    qlist, notes, materials, listening = [], [], {}, {}

    def q(n, mat, stem, answer, why, options=None, sample=None, rubric=None):
        section, kind, points = sections[n]
        row = dict(number=n,id=f"orig:english:{ID}:q{n:02d}",points=points,kind=kind,section=section,stem=stem,answer=answer)
        if mat:
            row["material"] = mat
        if options:
            row["options"] = dict(zip("ABCD",options))
        qlist.append(row)
        note = dict(number=n,answer=answer,reasoning=why)
        if sample:
            note["sample"] = sample
            note["rubric"] = [dict(points=p,step=step) for p,step in rubric]
        notes.append(note)

    first = 1
    for i, (size, story) in enumerate(zip(blueprint["listening_group_sizes"], texts, strict=True), 1):
        key = f"L{i:02d}"
        span = f"第{first}题" if size == 1 else f"第{first}至{first+size-1}题"
        intro = ("第一节，听下面5段对话，从每题所给的 A、B、C 三个选项中选出最佳选项。每段对话读两遍。\n" if i==1 else
                 "第二节，听下面5段对话或独白，从每题所给的 A、B、C 三个选项中选出最佳选项。每段材料读两遍。\n" if i==6 else "")
        materials[key] = {"title":f"Text {i}", "text":intro + f"听第{i}段材料，回答{span}。"}
        listening[key] = story
        for n in range(first, first+size):
            stem,opts,answer,why = heard[n-1]
            q(n,key,stem,answer,why,opts)
        first += size
    for key, start, end in (("A",21,23),("B",24,27),("C",28,31),("D",32,35)):
        materials[key] = {"title":key, "text":reading[key]}
        for n in range(start,end+1):
            stem,opts,answer,why=reading_items[n-21]
            q(n,key,stem,answer,why,opts)
    materials["S"] = {"title":"七选五", "text":"阅读下面短文，从短文后的选项中选出可以填入空白处的最佳选项。选项中有两项为多余选项。\n"+gap,"options":gap_options}
    for n,(answer,why) in enumerate(gap_keys,36):
        q(n,"S",f"第{n}空",answer,why)
    materials["T"] = {"title":"完形填空", "text":"阅读下面短文，从每题所给的 A、B、C、D 四个选项中选出可以填入空白处的最佳选项。\n"+cloze}
    for n,(opts,answer,why) in enumerate(cloze_items,41):
        q(n,"T",f"第{n}空",answer,why,opts)
    materials["U"] = {"title":"语法填空","text":"阅读下面短文，在空白处填入1个适当的单词或括号内单词的正确形式。\n"+grammar}
    for n,(answer,why) in enumerate(grammar_keys,56):
        q(n,"U",f"第{n}空",answer,why)
    q(66,None,application,"开放作答","围绕广播听众能听到什么安排信息。范文用翻书、转轮、盖章和还书期限把陌生声音落到具体校园物品上。",sample=app_sample,rubric=app_rubric)
    materials["V"] = {"title":"读后续写", "text":continuation}
    q(67,"V",cont_prompt,"开放作答","第一段从纸卷、胶带、有限时间和 May 无法站在手机照片旁展开；第二段落实新家厨房以及父亲与兄妹的反应。可以采用其他自洽情节。",sample=cont_sample,rubric=cont_rubric)
    candidate={"id":ID,"subject":"english","title":"2027年河南高考英语模拟试卷","blueprint_sha256":fingerprint(blueprint),
               "reference_scope":"fulltext","reference_notes":mapping,"materials":materials,"questions":qlist,"listening":listening,
               "provenance":{"dna_sha256":context["dna_sha256"],"context_sha256":digest(CONTEXT),
                             "quality_reference_sha256":fingerprint(context["quality_benchmarks"]),
                             "language_corpus_sha256":fingerprint(context["language_corpus"]),
                             "eight_paper_manifest_sha256":fingerprint(papers)}}
    save(OUT / "candidate.json",candidate)
    save(OUT / "author-solutions.json",{"role":"author","items":notes})
    print("Questions:",len(qlist),"Points:",sum(x["points"] for x in qlist))
    print("Reading words:", {k:english_words(v) for k,v in reading.items()})

if __name__=="__main__":
    build()
