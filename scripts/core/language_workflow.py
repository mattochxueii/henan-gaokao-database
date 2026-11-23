"""Evidence-based blueprints and review gates for Chinese and English."""
from decimal import Decimal, ROUND_HALF_UP
from itertools import groupby
from pathlib import Path

from analysis_db import fingerprint
from core.paper_intake import dna
from forecast_store import write_new
from gaokao import digest, read_json, require

LANGUAGES = ("chinese", "english")
ROOT_DATA = Path("data/language-blueprints.json")
OBJECTIVE = ("single_choice", "gap_match", "multiple_choice", "grammar_gap", "recitation")


def plan(root, subject, region, year):
    evidence = read_json(root / ROOT_DATA)[subject]
    historical = evidence["years"]
    require(region == "河南" and (str(year) in historical or year == 2027), "缺该地区年度的主科标准蓝图")
    basis = min(year, 2026)
    version = historical[str(basis)]
    features = dna(root,subject)
    return {"subject":subject,"region":region,"year":year,"basis_year":basis,
            "series":"cn-new-gaokao-1","minutes":evidence["minutes"],
            "points":150,"sections":version["sections"],"sources":version["sources"],
            "historical_traits":version["traits"],"listening_group_sizes":version.get("listening_group_sizes"),"dna":features,
            "fulltext_supported":bool(features["references"])}


def henan_english_score(written):
    require(0 <= written <= 120, "笔试原始分满分120")
    return int((Decimal(str(written)) * Decimal("1.25")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def prepare(root, blueprint, candidate, output):
    from core.language_render import render
    subject = blueprint["subject"]
    require(candidate["subject"] == subject and candidate.get("blueprint_sha256") == fingerprint(blueprint),
            "候选须绑定本学科题位与参考画像")
    require(candidate.get("reference_scope") == ("fulltext" if blueprint["fulltext_supported"] else "structure_only"),
            "原文覆盖与参考范围不符")
    require(candidate.get("reference_notes") and all(isinstance(x,str) and x.strip() for x in candidate["reference_notes"]),
            "必须说明真题特征及原创差异")
    questions, materials = candidate["questions"], candidate["materials"]
    required_points = [score for sec in blueprint["sections"] for score in sec["scores"]]
    require([q["number"] for q in questions] == list(range(1,len(required_points)+1))
            and [q["points"] for q in questions] == required_points and sum(required_points) == 150,"题号或分值不符")
    used = set()
    for section in blueprint["sections"]:
        for num in range(section["first"], section["first"] + len(section["scores"])):
            q=questions[num-1]
            require(q["section"] == section["id"] and q["kind"] in section["kinds"]
                    and q["stem"].strip() and q["answer"] not in (None,"",[],{}),"题型、题干或答案不符")
            require(q["id"]==f'orig:{subject}:{candidate["id"]}:q{num:02d}',"原创ID或题序错误")
            require(not any(s in q["stem"] for s in ("参考答案：", "Answer key:", "评分细则：")), "学生题面混入答案")
            if q["kind"] in ("single_choice","gap_match","multiple_choice"):
                opts=q.get("options") or materials.get(q.get("material"), {}).get("options",{})
                key=q["answer"]
                require(isinstance(key,str) and key and set(key)<=set(opts)
                        and len(set(key))==len(key) and (len(key)>1)==(q["kind"]=="multiple_choice")
                        and len(set(opts.values()))==len(opts),"客观题键错误或重复选项")
                if subject == "english" and q["kind"] == "single_choice":
                    require(set(opts)==set("ABC" if section["id"]=="listening" else "ABCD"), "英语选项数与题组不符")
            if name := q.get("material"):
                require(name in materials and materials[name]["text"].strip(), "对应材料缺失")
                used.add(name)
            if section["id"] != "recitation":
                require(q.get("material") or section["id"] in ("application",),"阅读、语言或写作题须含材料")
    for name, material in materials.items():
        if material.get("options"):
            keys=[q["answer"] for q in questions if q.get("material")==name]
            require(len(keys)==len(set(keys)) and len(material["options"]) > len(keys),
                    "共享选项题有重复答案或无备选干扰项")
    require(used == set(materials), "存在错配或未使用的材料")
    scripts=candidate.get("listening",{})
    if subject=="english":
        group_ids = [q["material"] for q in questions[:20]]
        sizes=[sum(1 for _ in grp) for _,grp in groupby(group_ids)]
        require((not blueprint["listening_group_sizes"] or sizes==blueprint["listening_group_sizes"])
                and list(dict.fromkeys(group_ids)) == list(scripts) and all(v.strip() for v in scripts.values()),
                "缺听力文本或听力次序错配")
    public = {"subject":subject,"title":candidate["title"],"minutes":blueprint["minutes"],
              "points":150,"sections":blueprint["sections"],"materials":materials,
              "questions":[{k:v for k,v in q.items() if k in {"number","id","points","kind","section","stem","material","options"}}
                           for q in questions]}
    reference=candidate.get("quality_benchmarks")
    if reference:
        public["quality_reference_sha256"]=fingerprint(reference)
    packet={"paper":public,"paper_version":fingerprint(public)}
    output.mkdir(parents=True,exist_ok=False)
    render(public, output/"paper")
    write_new(output/"blind-packet.json",packet)
    write_new(output/"listening-review.json",scripts)
    write_new(output/"verification.json",{"paper_version":packet["paper_version"],"paper_sha256":digest(output/"paper.pdf"),
              **({"quality_benchmarks":reference} if reference else {}),
              "expected":[q["answer"] for q in questions],"blueprint_sha256":fingerprint(blueprint),
              "listening_sha256":fingerprint(scripts),"reference_notes":candidate["reference_notes"],
              "reference_scope":candidate["reference_scope"]})
    return {"state":"await_independent_review","paper_version":packet["paper_version"],"questions":len(questions)}


def review(folder, doc):
    from core.language_render import render
    packet=read_json(folder/"blind-packet.json")
    public=packet["paper"]
    verification=read_json(folder/"verification.json")
    require(not (folder/"independent-review.json").exists(), "本版本已完成复核")
    require(doc["paper_version"]==packet["paper_version"]==verification["paper_version"]==fingerprint(public)
            and verification["paper_sha256"]==digest(folder/"paper.pdf"),"学生卷版本错误")
    listening=read_json(folder/"listening-review.json")
    require(fingerprint(listening)==verification["listening_sha256"],"听力内容版本错配")
    require(doc["input_scope"]=="student_materials_and_listening_only" and doc["reviewer"].strip(),"缺独立审阅声明")
    require(len(doc["items"]) == len(public["questions"]), "审查题目不齐")
    explanations={}
    for q, expected, result in zip(public["questions"],verification["expected"],doc["items"],strict=True):
        label=q["number"]
        require(result["number"]==label and result.get("ambiguity") is False and result["reasoning"].strip(),
                f"第{label}题有歧义、错位或无复核依据")
        require(result["answer"]==expected,f"第{label}题答案复核不一致")
        if q["kind"] not in OBJECTIVE:
            rubric=result.get("rubric") or []
            require(rubric and all(type(r["points"]) in (int,float) and r["points"]>0 and r["step"].strip() for r in rubric)
                    and sum(r["points"] for r in rubric)==q["points"],f"第{label}题缺评分步骤")
            if q["kind"]=="writing":
                sample=result.get("sample","")
                if public["subject"]=="english":
                    valid_sample = len(sample.split()) >= (70 if q["section"]=="application" else 130)
                else:
                    valid_sample = len("".join(sample.split())) >= 800
                require(valid_sample,f"第{label}题范文缺失或过短")
        explanations[label]=result
    render(public,folder/"solutions",explanations)
    if listening:
        render(public,folder/"listening-script",listening=listening)
    write_new(folder/"independent-review.json",doc)
    names=["paper","solutions"]+(["listening-script"] if listening else [])
    write_new(folder/"review-binding.json",{"review_sha256":fingerprint(doc),
              "pdf":{name:digest(folder/(name+".pdf")) for name in names}})
    return {"state":"await_visual_review","paper_version":packet["paper_version"]}


def publish(folder, record):
    from pypdf import PdfReader
    packet=read_json(folder/"blind-packet.json")
    checked=read_json(folder/"independent-review.json")
    bind=read_json(folder/"verification.json")
    require(record["paper_version"]==packet["paper_version"]==checked["paper_version"]==bind["paper_version"]
            ==fingerprint(packet["paper"]) and record["reviewer"].strip(),"发布须绑定独立审题版本")
    reviewed = read_json(folder/"review-binding.json")
    require(reviewed["review_sha256"] == fingerprint(checked), "复核内容发生变化")
    names=["paper","solutions"]
    if packet["paper"]["subject"]=="english":
        names.append("listening-script")
    for name in names:
        path=folder/(name+".pdf")
        notes=record["artifacts"][name]
        require(notes["sha256"]==digest(path)==reviewed["pdf"][name] and len(notes["pages"])==len(PdfReader(path).pages)
                and all(n.strip() for n in notes["pages"]),"须逐页核对最终PDF")
    require(record["artifacts"]["paper"]["sha256"]==bind["paper_sha256"],"发布学生卷已变更")
    result={**record,"review_sha256":fingerprint(checked),"status":"reviewed","reference_scope":bind["reference_scope"]}
    if packet["paper"].get("quality_reference_sha256"):
        from core.quality_audit import publication_quality

        result["quality_audit_sha256"]=publication_quality(folder, checked)
    write_new(folder/"publication.json",result)
    return result
