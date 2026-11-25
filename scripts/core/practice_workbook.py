"""Compose traceable practice papers from the shared plaintext archive."""
import json
from pathlib import Path
import re
from shutil import copyfile

from analysis_db import fingerprint
from core.paper_intake import PAPER_SUBJECTS, dna, research
from gaokao import digest, read_json, relative_path, require
from storage import atomic_json
from subjects import SCIENCES


def authoring_context(root, subject, *, topic=None, source_id=None, limit=12):
    require(type(limit) is int and limit > 0, "对照样本数须为正整数")
    profile = root / "data/dna" / f"{subject}.json"
    current = dna(root,subject,tracked_only=True)
    require(profile.is_file() and fingerprint(read_json(profile)) == fingerprint(json.loads(json.dumps(current))),
            "命题画像缺失或过期，先运行 audit_core_papers.py --write-profiles")
    pool = research(root,subject,topic=topic,limit=None)
    if source_id and subject in SCIENCES:
        pool += research(root,subject,topic=topic,limit=None,exam_kind="adaptation_exam")
    evidence = current["henan_selective_profile"] if subject in SCIENCES else current["national_first_profile"]
    if source_id:
        references = [q for q in pool if q.get("occurrence_id",q["id"]) == source_id]
        require(len(references)==1,"指定原题不存在、处于隔离或不在正式卷范围")
    else:
        recent = [row for row in evidence["by_year"] if row["year"] >= 2024]
        require(recent,"没有目标卷系的近年正文")
        strata = [[q for q in pool if q["paper_id"] == row["paper_id"]] for row in recent]
        strata = [group for group in strata if group]
        if strata and limit < sum(map(len, strata)):
            slots, remaining = divmod(limit, len(strata))
            representative = []
            for i, group in enumerate(strata):
                count = min(len(group), slots + (i < remaining))
                if count == 1:
                    representative.append(group[:1])
                elif count > 1:
                    representative.append([group[j * (len(group) - 1) // (count - 1)] for j in range(count)])
            strata = representative
        references = [group[i] for i in range(max(map(len,strata),default=0))
                      for group in strata if i<len(group)][:limit]
    require(references,"找不到该考点的可用正文")
    answer_fields = {"answer", "reviewed_answer", "curation", "explanation", "analysis",
                     "candidate", "rubric", "answer_variants", "scoring", "legacy"}
    result = {"subject":subject,"dna_sha256":digest(profile),
            "query":{"topic":topic,"source_id":source_id,"limit":limit},
            "guidance":evidence["aggregate"]["authoring"],
            "references":[{k:v for k,v in q.items() if k not in answer_fields} for q in references]}
    if not topic and not source_id:
        from core.quality_audit import position_reference
        from core.publication_ledger import history

        from core.exam_qa import policies
        result["publication_history"] = history(root,subject)
        result["anti_patterns"] = policies(root, subject)
        result["quality_benchmarks"] = position_reference(root, subject)
        if subject in ("chinese","english"):
            from core.language_workflow import fulltext_corpus

            corpus = fulltext_corpus(root, subject)
            result["language_corpus"] = corpus
            if subject=="chinese":
                from core.chinese_corpus import manifest

                result["classical_corpus"]=manifest(root)
            result["rehearsal_references"] = [
                {k: v for k, v in q.items() if k not in answer_fields}
                for q in research(root, subject, year=2025, region="河南", limit=None,
                                  exam_kind="adaptation_exam")
                if q["paper_id"] == f"2025-ha-{subject}-adaptation"
                and q["asset_root"] == f"data/papers/{subject}"
            ] if corpus else []
    if subject in SCIENCES:
        result["paper_layout"] = evidence["aggregate"]["paper_layout"]
    return result



def validate_authoring_context(root, subject, context_file, candidate):
    from core.quality_audit import bound_reference

    packet = read_json(context_file)
    actual = authoring_context(root, subject, **packet["query"])
    years = {2025,2026} if subject in SCIENCES else {2024,2025,2026}
    require(fingerprint(actual) == fingerprint(packet) and packet["subject"] == subject
            and not packet["query"]["topic"] and not packet["query"]["source_id"]
            and years <= {q["year"] for q in packet["references"]},
            "整卷上下文须覆盖目标卷系完整年份范围，并绑定当前命题画像")
    proof = candidate.get("provenance",{})
    require(proof.get("dna_sha256") == actual["dna_sha256"]
            and proof.get("context_sha256") == digest(context_file), "候选须绑定当前命题上下文")
    return bound_reference(actual,candidate)


def selection(root, subject, *, year=None, region=None, kind=None, topic=None,
              question_ids=(), limit=6, adaptation=False, paper_id=None):
    require(subject in PAPER_SUBJECTS and limit>0, "学科或选题数无效")
    pool=research(root,subject,year=year,region=region,topic=topic,limit=None,paper_id=paper_id,
                  exam_kind="adaptation_exam" if adaptation else "official_exam")
    if question_ids:
        by_id={q.get("occurrence_id",q["id"]):q for q in pool}
        require(len(set(question_ids))==len(question_ids) and all(n in by_id for n in question_ids),
                "指定题目重复、不在筛选范围内或已隔离")
        chosen=[by_id[n] for n in question_ids]
    else:
        chosen=[q for q in pool if not kind or q["kind"]==kind][:limit]
    require(chosen,"没有符合条件且可用于练习的真题")
    # Linked gaps share a single option bank. Preserve all gaps and source numbering.
    linked_topics={"七选五","语法填空","完形填空","听力"}
    expanded={}
    for q in chosen:
        if q.get("topic") in linked_topics and (link:=q.get("passage") or q.get("listen_group")):
            for peer in pool:
                if peer["paper_id"]==q["paper_id"] and (peer.get("passage") or peer.get("listen_group"))==link:
                    expanded[peer["number"],peer["paper_id"]] = peer
        else:
            expanded[q["number"],q["paper_id"]] = q
    return list(expanded.values())


def clean_english_passage(text):
    # Preserve headings and adjoining copy from line-wrapped PDF transcriptions.
    lines=[line.strip() for line in text.splitlines() if line.strip()
           and re.sub(r"\s","",line)!="学科网（北京）股份有限公司"]
    result=[]
    paragraph=[]
    for line in lines:
        heading = (" — " in line and line.split(" — ",1)[0].isupper()) or line.startswith("[Chart:")
        if paragraph and (heading or paragraph[-1].endswith((".", "?", "!", "]"))):
            result.append(" ".join(paragraph))
            paragraph=[]
        paragraph.append(line)
    if paragraph:
        result.append(" ".join(paragraph))
    return "\n".join(result)



ARCHIVE_MATH = re.compile(r"\\\((.*?)\\\)|(?<!\\)\$([^$\n]+)\$", re.S)
ARCHIVE_TEXT = re.compile(r"\\text\{([^{}]*[\u3400-\u9fff][^{}]*)\}|([\u3400-\u9fff]+)")


def archive_math_text(text, *, bare_formula=False):
    """Adapt legacy TeX and unsupported glyphs at export time only."""
    from mathgen.export import SUBSCRIPTS

    def prose(value):
        value = re.sub(
            r"([A-Za-z0-9Α-Ωα-ω]?)([₀₁₂₃₄₅₆₇₈₉ₙₖⱼᵢ₊₋]+)",
            lambda match: r"\(" + (match[1] or "{}") + "_{" + match[2].translate(SUBSCRIPTS) + r"}\)",
            value,
        )
        return re.sub(r"∛(\d+|[A-Za-z])",r"\\(\\sqrt[3]{\1}\\)",value.replace("−","-"))

    def formula(value):
        if ARCHIVE_TEXT.search(value):
            # Sizing commands require both ends in one math span. The delimiter
            # characters themselves must survive a split around Chinese text.
            value = re.sub(r"\\(?:left|right)\b","",value)
        pieces = []
        start = 0
        for match in ARCHIVE_TEXT.finditer(value):
            if fragment := value[start:match.start()].strip():
                pieces.append(r"\("+fragment+r"\)")
            pieces.append(prose(match[1] or match[2]))
            start = match.end()
        if fragment := value[start:].strip():
            pieces.append(r"\("+fragment+r"\)")
        return "".join(pieces)

    def math_fragment(value):
        return formula(value.replace("−","-").replace("∛",r"\sqrt[3]"))

    if bare_formula and not ARCHIVE_MATH.search(text) and (
        re.search(r"\\[A-Za-z]+",text)
        or (not re.search(r"[\u3400-\u9fff]",text) and re.search(r"[_^]",text))
    ):
        return math_fragment(text)
    pieces = []
    start = 0
    for match in ARCHIVE_MATH.finditer(text):
        pieces.extend((prose(text[start:match.start()]),math_fragment(match[1] or match[2])))
        start = match.end()
    return "".join((*pieces,prose(text[start:])))


def archive_math_answer(answer, reasoning):
    if not isinstance(answer,str) or answer.strip().casefold()!="corrected":
        return archive_math_text(answer) if isinstance(answer,str) else answer
    # Use an explicit final selection. For worked answers leave the key empty and use the full explanation.
    if match := re.search(r"(?:故选|应选|选)\s*([A-D]{1,4})[。.!]?\s*$",reasoning or ""):
        return match[1]
    return None


def render_archive(root, subject, rows, output, *, title, minutes, reference=None, changes=None):
    require(not output.exists(),"试卷输出必须使用新目录")
    require(type(minutes) is int and minutes>0 and title.strip(),"缺试卷标题或用时")
    output.mkdir(parents=True)
    source_records=[]
    materials={}
    questions=[]
    keys=[]
    listening={}
    for n,q in enumerate(rows,1):
        original=q.get("occurrence_id",q["id"])
        provenance={"number":n,"id":original,"version_sha256":q["version_sha256"],
                    "position":q.get("position") or q.get("source_locator"),"url":q["source"]["url"]}
        source_records.append(provenance)
        item={"number":n,"order":n,"id":q["id"],"stem":q["stem"],"points":q["points"],
              "kind":q["kind"],"options":q.get("options") or {},"section":"practice"}
        if q.get("listening_text"):
            grouped=f'{q["paper_id"]}:{q["listen_group"]}'
            materials.setdefault(grouped,{"title":f'{q["year"]} 年听力原题组',
                                          "text":"请根据本组录音作答。"})
            item["material"]=grouped
            listening[grouped]=q["listening_text"]
        passage = q.get("passage_text")
        if passage:
            key=q["paper_id"]+":"+q["passage"]
            caption=f'{q["year"]} 年原卷材料 · 原题 {q["number"]}'
            if subject=="english":
                passage=clean_english_passage(passage)
            materials.setdefault(key,{"title":caption,"text":passage})
            item["material"]=key
        figures=[]
        captions=[]
        for asset in q.get("asset_refs",[]):
            rel=asset.get("plaintext_path") if subject=="math" and q.get("legacy") is not None else asset.get("path")
            require(rel, "档案题图没有可排版衍生文件")
            image=relative_path(root / q["asset_root"],rel)
            require(image.suffix.lower() in (".png",".jpg",".jpeg"),"该档案题图目前需导出 PNG")
            require(image.is_file(),"档案题图缺失")
            image_output=output/"figures"/image.name
            image_output.parent.mkdir(exist_ok=True)
            if not image_output.exists():
                copyfile(image,image_output)
            figures.append(image_output)
            captions.append(asset.get("caption"))
        if figures:
            item["archive_figures"]=figures
            item["archive_figure_captions"]=captions
        answer=q.get("reviewed_answer") or q.get("answer")
        reasoning=q.get("explanation")
        if isinstance(answer,dict):
            reasoning=answer.get("explanation") or reasoning
            answer=answer.get("reference_answer") or answer.get("option") or answer.get("value_latex")
        if subject=="math" and not changes:
            stem = re.sub(r"\s*\[图[：:][^\]\r\n]+\]", "", item["stem"])
            if q.get("parts"):
                stem = re.split(r"[（(]\s*子[项項]\s*[）)]",stem,maxsplit=1)[0].rstrip()
            if item["options"]:
                stem = re.sub(r"[（(]\s*\\(?:q?quad)\s*[）)]","",stem)
            item["stem"] = archive_math_text(stem)
            item["options"] = {key:archive_math_text(value,bare_formula=True)
                               for key,value in item["options"].items()}
            answer = archive_math_answer(answer,reasoning)
            reasoning = archive_math_text(reasoning or "")
        keys.append({"number":n,"answer":answer,"reasoning":reasoning or "",
                     "points":q["points"],"reference":provenance})
        require(answer is not None or reasoning,"原题答解空缺")
        if subject=="math" or subject in SCIENCES:
            item["parts"]=[{"label":v.get("label",f"（{i}）") if isinstance(v,dict) else f"（{i}）",
                            "text":v if isinstance(v,str) else v["text"]}
                           for i,v in enumerate(q.get("parts") or [],1)]
            if subject=="math" and not changes:
                for part in item["parts"]:
                    part["text"] = archive_math_text(part["text"])
        questions.append(item)
    paper={"title":title,"subject":subject,"sections":[{"id":"practice","title":"练习题"}],
           "minutes":minutes,"points":sum(q["points"] for q in questions),"questions":questions,
           "materials":materials,"archive_practice":True}
    if subject=="math" or subject in SCIENCES:
        from mathgen.student_pdf import render
        paper["total_points"]=paper["points"]
        for item in questions:
            item["kind"]={"response":"constructed_response","short_answer":"fill_in"}.get(item["kind"],item["kind"])
        render(paper,output/"paper.pdf")
    else:
        from core.language_render import render
        render(paper,output/"paper")
        if listening:
            render(paper,output/"listening-script",listening=listening)
    atomic_json(output/"answer-packet.json",keys)
    manifest={"subject":subject,"title":title,"points":paper["points"],"minutes":minutes,
              "question_count":len(keys),"paper_sha256":digest(output/"paper.pdf"),
              "mode":"adaptation" if changes else "archive_selection","references":source_records,
              "source_context":reference,"changes":changes,"answers_sha256":fingerprint(keys)}
    atomic_json(output/"manifest.json",manifest)
    return manifest


def adaptive_workbook(root,subject,packet,output,figure_root=None):
    source_id=packet["source_id"]
    context=authoring_context(root,subject,source_id=source_id)
    require(packet["dna_sha256"]==context["dna_sha256"],"改编未绑定当前命题画像")
    source=context["references"][0] if subject in SCIENCES else {}
    row=selection(root,subject,question_ids=[source_id],adaptation=source.get("exam_kind")=="adaptation_exam")[0]
    require(packet["source_version_sha256"]==row["version_sha256"],"改编引用的原题版本已改变")
    change=packet["comparison"]
    require(all(isinstance(change.get(k),str) and change[k].strip() for k in
                ("preserved_thinking","changed_condition_or_context","difficulty_basis")),
            "改编缺少思维、实质变化与难度依据")
    items=packet["questions"]
    require(items and all(q.get("stem") and q.get("answer") not in (None,"",[],{})
                          and q.get("explanation") and q.get("points",0)>0 for q in items),
            "改编题缺少题面、答案、解析或分值")
    def text_shape(stem):
        return re.sub(r"[\d０-９]+(?:[.．][\d０-９]+)?|\s+", "",stem)

    require(all(text_shape(q["stem"])!=text_shape(row["stem"]) for q in items),
            "题干与原题相同或只替换了数字")
    require(all(not q.get("passage") or packet.get("passages",{}).get(q["passage"]) for q in items),
            "改编共享材料缺失")
    if subject in SCIENCES:
        from core.science_workflow import plan, prepare

        candidate={**packet,"subject":subject,
                   "questions":[{**q,"id":f"orig:{subject}:adapt:{source_id}:{i}",
                                 "proposed_answer":q["answer"]} for i,q in enumerate(items,1)]}
        blueprint=plan(root,subject,"河南",packet.get("target_year",row["year"]),"targeted")
        result=prepare(root,blueprint,candidate,output,figure_root)
        atomic_json(output/"adaptation.json",{"source_id":source_id,"source_version_sha256":row["version_sha256"],
                    "source_url":row["source"]["url"],"comparison":change,"dna_sha256":context["dna_sha256"]})
        return result
    practice=[{**q,"number":i,"paper_id":"adapted","id":f"orig:adapt:{source_id}:{i}",
               "version_sha256":fingerprint(q),"position":f"改编第 {i} 题",
               "source":row["source"],"passage_text":packet.get("passages",{}).get(q.get("passage")),
               "year":row["year"]}
              for i,q in enumerate(items,1)]
    return render_archive(root,subject,practice,output,title=packet["title"],minutes=packet["minutes"],
                          reference={"id":source_id,"version_sha256":row["version_sha256"],
                                     "position":row.get("position") or row.get("source_locator"),"url":row["source"]["url"]},
                          changes=change)


def review_workbook(output,review):
    manifest=read_json(output/"manifest.json")
    keys=read_json(output/"answer-packet.json")
    require(not (output/"publication.json").exists(),"试卷已有核对记录")
    require(review["paper_sha256"]==manifest["paper_sha256"]==digest(output/"paper.pdf")
            and fingerprint(keys)==manifest["answers_sha256"],"题面或参考答解版本不符")
    require(review["input_scope"]=="student_pdf" and
            [x["number"] for x in review["items"]]==list(range(1,len(keys)+1)),
            "缺考生卷逐题核对")
    solutions={}
    for key,row in zip(keys,review["items"],strict=True):
        require(row.get("answer") and row.get("reasoning") and row.get("consistent") is True,
                "存在缺失或未核对的题目")
        original=key["answer"]
        if isinstance(original,str) and re.fullmatch(r"[A-G]{1,4}",original):
            require(original==row["answer"],"独立选择与档案答案不符")
        steps=row.get("rubric",[])
        require(not steps or sum(x["points"] for x in steps)==key["points"],"评分分值不匹配")
        solutions[key["number"]]={**row,"points":key["points"]}
    if manifest["subject"]=="math" or manifest["subject"] in SCIENCES:
        from mathgen.student_pdf import render
        questions=[{"id":str(r["number"]),"order":r["number"],"kind":"constructed_response","points":r["points"],
                    "solution_paragraphs":[r["answer"],r["reasoning"],
                        *[f'{step["points"]:g}分　{step["step"]}' for step in r.get("rubric",[])]]}
                   for r in solutions.values()]
        if manifest["subject"]=="math" and manifest["mode"]=="archive_selection":
            for question in questions:
                question["solution_paragraphs"] = [archive_math_text(text) for text in question["solution_paragraphs"]]
        render({"title":manifest["title"],"questions":questions},output/"solutions.pdf",solutions=True)
    else:
        from core.language_render import render
        blocks=[{"number":n,"points":r["points"],"section":"practice"} for n,r in solutions.items()]
        render({"title":manifest["title"],"subject":manifest["subject"],"archive_practice":True,
                "sections":[{"id":"practice","title":"逐题答解"}],"questions":blocks},output/"solutions",solutions)
    atomic_json(output/"review.json",review)
    result={**manifest,"answer_pdf_sha256":digest(output/"solutions.pdf"),"review_sha256":fingerprint(review)}
    atomic_json(output/"publication.json",result)
    return result
