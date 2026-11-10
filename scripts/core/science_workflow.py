"""Plan, verify and render science exercises through a subject-specific gate."""

from collections import Counter
import math
from pathlib import Path
import re

from analysis_db import fingerprint
from core.catalog import catalog, query, use
from forecast_store import write_new
from gaokao import digest, read_json, relative_path, require
from subjects import SCIENCES, SUBJECTS, science_verifier

KINDS = ("single_choice","multiple_choice","fill_in","constructed_response")
VERSION = "science-workflow-v1"


def same_answer(first, second):
    if type(first) in (int,float) and type(second) in (int,float):
        return math.isfinite(first) and math.isfinite(second) and first==second
    if type(first) is not type(second):
        return False
    if isinstance(first,dict):
        return first.keys()==second.keys() and all(same_answer(v,second[k]) for k,v in first.items())
    if isinstance(first,list):
        return len(first)==len(second) and all(same_answer(a,b) for a,b in zip(first,second))
    return first==second


def plan(root, subject, region, year, mode="targeted", topics=()):
    require(subject in SCIENCES, "数学使用原有蓝图，语文和英语只登记学科")
    usages = use(root,subject,region,year)
    require(len(usages)==1, "地区和年份应有唯一适用省卷")
    mapping = usages[0]
    require(mapping["status"]!="historical_component", "旧理综分科不能充当独立选择性考试蓝图")
    knowledge = [x["title"] for x in catalog(root)["entities"]["KnowledgePoint"] if x["subject"]==subject]
    layout = mapping.get("structure")
    if mode == "standard":
        require(mapping["status"]=="historical_selective" and layout and layout.get("sections"),
                "暂无已核的同年同省完整卷面结构，使用专项训练")
    else:
        require(mode=="targeted", "概率研究使用独立命令")
    return {
        "workflow":VERSION,"subject":subject,"region":region,"year":year,"mode":mode,
        "mapping":mapping,"curriculum_topics":knowledge,"requested_topics":list(topics),
        "reference_candidates": [{k:q.get(k) for k in ("id","topic","source_url","review_status")}
                                 for q in query(root,subject,year=year,region=region,verified_only=True)],
        "structure":layout if mode=="standard" else None,
        "scope":"专项分数和时长由练习设定" if mode=="targeted" else "同年同省已见卷面结构，非官方原创卷",
    }


def normalize_subject_item(item, order, folder):
    kind = item.get("kind","single_choice" if item.get("options") else "constructed_response")
    options = item.get("options",{})
    points = item["points"]
    require(kind in KINDS and type(points) is int and 0<points<=30, "题型或分值无效")
    require((kind in KINDS[:2] and tuple(options)==tuple("ABCD")) or (kind in KINDS[2:] and not options),
            "选择题必须有顺序正确的四个选项")
    stem, parts = item["stem"], item.get("parts",[])
    require(isinstance(stem,str) and stem.strip() and all(p["label"] and p["text"] for p in parts),
            "题干或子问不完整")
    text = " ".join([stem,*options.values(),*(p["text"] for p in parts)])
    require(not re.search(r"【答案】|参考答案[：:]|(?:^|\s)solution:|\\begin\{",text,re.I), "学生版含泄漏或不支持的格式")
    figure = item.get("figure")
    if figure:
        require(isinstance(figure,dict) and figure.get("sha256"), "图像须有内容绑定")
        actual = relative_path(folder,figure["path"])
        require(actual.is_file() and not actual.is_symlink() and digest(actual)==figure["sha256"]
                and actual.suffix.lower() in (".png",".jpg",".jpeg"), "题图缺失或版本不符")
        figure = str(actual.resolve())
    return {"id":item["id"],"order":order,"kind":kind,"points":points,"stem":stem,
            "options":options,"parts":parts,"figure":figure}


def prepare(root, blueprint, candidate, output, figure_root=None):
    subject = blueprint["subject"]
    require(candidate["subject"]==subject, "候选学科与蓝图不符")
    questions = candidate["questions"]
    require(questions and isinstance(questions,list) and len(questions)<=50, "题量不合理")
    ids = [q["id"] for q in questions]
    require(len(ids)==len(set(ids)) and all(i.startswith("orig:"+subject+":") for i in ids),
            "原创 ID 不能跨学科或重复")
    visible, answers, checks = [],[],[]
    source_rows = query(root,subject,region=blueprint["region"],limit=10000)
    known_text = {re.sub(r"\W","", q.get("stem") or q.get("semantic_summary") or "") for q in source_rows}
    seen = set()
    solver = science_verifier(subject)
    for order,q in enumerate(questions,1):
        public = normalize_subject_item(q,order,figure_root or root)
        normalized = re.sub(r"\W","",public["stem"])
        require(normalized and normalized not in known_text and normalized not in seen, "题干与现存真题或同卷题完全重复")
        seen.add(normalized)
        require(isinstance(q["topic"],str) and q["topic"].strip(), "题目缺少学科知识标签")
        require(not blueprint["requested_topics"] or q["topic"] in blueprint["requested_topics"],
                "题目超出专项知识点范围")
        result = solver(q["problem"])
        require(same_answer(q["proposed_answer"],result["answer"]), "候选答案与独立程序不一致")
        require(result["checks"] and result["explanation"], "缺少程序验证依据")
        if public["kind"] in KINDS[:2]:
            require(isinstance(result["answer"],str) and result["answer"] and
                    len(set(result["answer"]))==len(result["answer"]) and
                    set(result["answer"])<=set(public["options"]) and
                    (len(result["answer"])==1)==(public["kind"]=="single_choice"), "选项键与题型不符")
        visible.append(public)
        answers.append(result["answer"])
        checks.append({"id":q["id"],"topic":q["topic"],"version_sha256":fingerprint(q),"verification":result})
    types = Counter(q["kind"] for q in visible)
    points = sum(q["points"] for q in visible)
    require(len({q["topic"] for q in questions})>1 or blueprint["mode"]!="standard", "整卷主题覆盖不足")
    if blueprint["mode"]=="standard":
        sections = blueprint["structure"]["sections"]
        by_kind = Counter()
        for q in visible:
            by_kind[q["kind"]] += q["points"]
        require(types == Counter({s["kind"]:s["count"] for s in sections})
                and by_kind == Counter({s["kind"]:s["points"] for s in sections})
                and points==blueprint["mapping"]["points"], "题型数量、分值或总分与已核卷面不符")
        offset = 0
        for section in blueprint["structure"]["source_details"]:
            count = section.get("count",section.get("questions",len(section.get("numbers",[]))))
            kind = {"experiment":"constructed_response","calculation":"constructed_response"}.get(
                section["kind"],section["kind"])
            group = visible[offset:offset+count]
            require(all(q["kind"]==kind for q in group), "题序与实际试卷题组不符")
            if "points_each" in section or "each" in section:
                each = section.get("points_each",section.get("each"))
                require(all(q["points"]==each for q in group), "单题分值与题组不符")
            if detail := section.get("individual_points",section.get("individual")):
                require([q["points"] for q in group]==detail, "已核逐题分值不符")
            offset += count
        minutes = blueprint["mapping"]["minutes"]
    else:
        minutes = candidate.get("minutes", max(5,len(visible)*6))
        require(type(minutes) is int and 0<minutes<=180, "专项练习时长无效")
    paper = {"title":SUBJECTS[subject]+("原创专项练习" if blueprint["mode"]=="targeted" else "原创模拟卷"),
             "minutes":minutes,"total_points":points,"questions":visible}
    output.mkdir(parents=True,exist_ok=False)
    packet = {"subject":subject,"paper":paper,"paper_version":fingerprint(paper)}
    write_new(output/"blind-packet.json",packet)
    from mathgen.student_pdf import render
    render(paper,output/"paper.pdf")
    write_new(output/"verification.json",{"blueprint":blueprint,"questions":checks,"answers":answers,
              "candidate_sha256":fingerprint(candidate),"paper_version":packet["paper_version"],
              "paper_pdf_sha256":digest(output/"paper.pdf")})
    return {"state":"await_independent_review","paper_version":packet["paper_version"],
            "questions":len(visible),"points":points,"pdf_sha256":digest(output/"paper.pdf")}


def adjudicate(folder, review):
    packet = read_json(folder/"blind-packet.json")
    checks = read_json(folder/"verification.json")
    require(review["paper_version"]==packet["paper_version"]==checks["paper_version"]==fingerprint(packet["paper"]),
            "独立审题与当前题面版本不匹配")
    require(digest(folder/"paper.pdf")==checks["paper_pdf_sha256"], "学生版与程序验证时的PDF不符")
    require(not (folder/"independent-review.json").exists(), "本版本已审查")
    require(review.get("input_scope")=="student_packet_only" and
            isinstance(review.get("reviewer"),str) and review["reviewer"].strip(), "须提供只看题面的独立审查记录")
    questions = packet["paper"]["questions"]
    judgments = {j["id"]:j for j in review["items"]}
    require(set(judgments)=={q["id"] for q in questions} and len(judgments)==len(review["items"]),
            "独立审核须覆盖每题")
    verified = []
    for q, answer, check in zip(questions,checks["answers"],checks["questions"],strict=True):
        j = judgments[q["id"]]
        require(j.get("approved") is True and isinstance(j.get("reasoning"),str) and j["reasoning"].strip()
                and same_answer(j["answer"],answer), "独立解答未与程序结果一致")
        if check["verification"]["unverified"]:
            require(isinstance(j.get("science_review"),str) and j["science_review"].strip(),
                    "程序覆盖外的科学判断须由审查者说明")
        verified.append({**q, "solution_paragraphs":[j["reasoning"]]})
    from mathgen.student_pdf import render
    render({**packet["paper"],"questions":verified},folder/"solutions.pdf",solutions=True)
    write_new(folder/"independent-review.json",review)
    write_new(folder/"visual-pending.json",{
        "review_sha256":fingerprint(review),"verification_sha256":fingerprint(checks),
        "paper_sha256":digest(folder/"paper.pdf"),"solutions_sha256":digest(folder/"solutions.pdf"),
    })
    return {"state":"await_visual_review","paper_sha256":digest(folder/"paper.pdf"),
            "solutions_sha256":digest(folder/"solutions.pdf"),"questions":len(questions)}


def publish(folder, visual):
    packet = read_json(folder/"blind-packet.json")
    review = read_json(folder/"independent-review.json")
    pending = read_json(folder/"visual-pending.json")
    require(visual["paper_version"]==packet["paper_version"]==review["paper_version"]==fingerprint(packet["paper"])
            and visual.get("passed") is True and visual.get("reviewer"), "缺少视觉审题")
    require(pending["review_sha256"]==fingerprint(review)
            and pending["verification_sha256"]==fingerprint(read_json(folder/"verification.json")),
            "审查或程序验证已改变")
    from pypdf import PdfReader
    for label in ("paper","solutions"):
        path = folder/(label+".pdf")
        require(visual[label+"_sha256"]==digest(path)==pending[label+"_sha256"]
                and visual[label+"_pages"]==len(PdfReader(path).pages)
                and visual.get(label+"_note"), "视觉记录与PDF版本或页数不符")
    record = {
        "status":"project_practice_independently_reviewed","subject":packet["subject"],
        "paper_version":packet["paper_version"],"question_ids":[q["id"] for q in packet["paper"]["questions"]],
        "review_sha256":fingerprint(review),"verification_sha256":pending["verification_sha256"],"visual":visual,
        "scope":"学科程序只覆盖明确模型。另有独立推理和PDF审题记录，教师与实测另行记录。",
    }
    write_new(folder/"publication.json",record)
    return record
