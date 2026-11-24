"""Evidence-based blueprints and review gates for Chinese and English."""
from itertools import groupby
from pathlib import Path

from analysis_db import fingerprint
from core import exam_policy
from core.paper_intake import PUBLIC, dna, documents
from forecast_store import write_new
from gaokao import ROOT, digest, read_json, require

LANGUAGES = ("chinese", "english")
ROOT_DATA = Path("data/language-blueprints.json")
OBJECTIVE = ("single_choice", "gap_match", "multiple_choice", "grammar_gap", "recitation")


def fulltext_corpus(root, subject):
    ids = [f"{year}-cn-{subject}-national-1" for year in (2024,2025,2026)]
    ids.append(f"2025-ha-{subject}-adaptation")
    papers = {d["id"]: (path, d) for path, d in documents(root, subject)
              if path.is_relative_to(root / PUBLIC) and d["id"] in ids}
    if set(papers) != set(ids):
        return []
    corpus = []
    for identifier in ids:
        path, d = papers[identifier]
        questions = d["questions"]
        if (not d.get("passages") or not questions
                or any(not q.get("usable_for_practice") or not q.get("stem") for q in questions)
                or (subject == "english" and (d.get("written_only")
                    or len(d.get("listening_transcript",{})) != 10))):
            return []
        corpus.append({"id":identifier,"year":d["year"],"exam_kind":d["exam_kind"],
                       "path":path.relative_to(root).as_posix(),
                       "url":d["source"]["url"],"questions":len(questions),
                       "content_sha256":d["content_sha256"],
                       "materials_sha256":fingerprint(d["passages"]),
                       "listening_sha256":d.get("listening_sha256")})
    return corpus


def plan(root, subject, region, year):
    evidence = read_json(root / ROOT_DATA)[subject]
    historical = evidence["years"]
    latest = max(map(int, historical))
    require(region == "河南" and (str(year) in historical or latest < year <= 2200), "缺该地区年度的主科标准蓝图")
    basis = min(year, latest)
    version = historical[str(basis)]
    features = dna(root,subject)
    corpus = fulltext_corpus(root,subject)
    return {"subject":subject,"region":region,"year":year,"basis_year":basis,
            "series":"cn-new-gaokao-1","minutes":evidence["minutes"],
            "points":150,"sections":version["sections"],"sources":version["sources"],
            "historical_traits":version["traits"],"listening_group_sizes":version.get("listening_group_sizes"),"dna":features,
            "fulltext_supported":bool(corpus), "language_corpus":corpus,
            "exam_policy":exam_policy.resolve(root, subject, year, region, exam_policy.NATIONAL_SERIES)}


def henan_english_score(written, *, year=2026, listening=None, root=ROOT):
    snapshot = exam_policy.resolve(root, "english", year, "河南", exam_policy.NATIONAL_SERIES)
    return exam_policy.english_score(snapshot, written, listening)


def validate_structure(blueprint, candidate):
    subject = blueprint["subject"]
    require(candidate["subject"] == subject and candidate.get("blueprint_sha256") == fingerprint(blueprint),
            "候选须绑定本学科题位与参考画像")
    require(blueprint["fulltext_supported"] and candidate.get("reference_scope") == "fulltext",
            "语英标准卷须以本学科三套正式卷和河南演练卷的全文为依据")
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
            if "answer_variants" in q:
                primary = q["answer"]
                variants = q["answer_variants"]
                require(q["kind"] == "recitation" and isinstance(primary, list)
                        and all(isinstance(value, str) and value.strip() for value in primary)
                        and isinstance(variants, list) and variants
                        and all(isinstance(key, list) and len(key) == len(primary)
                                and all(isinstance(value, str) and value.strip() for value in key)
                                for key in variants)
                        and len({tuple(key) for key in [primary, *variants]}) == len(variants) + 1,
                        "开放默写备选答案须逐空登记且不得重复")
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
        require(len(sizes) == 10 and sizes[:5] == [1] * 5
                and (not blueprint["listening_group_sizes"] or sizes==blueprint["listening_group_sizes"])
                and list(dict.fromkeys(group_ids)) == list(scripts) and all(v.strip() for v in scripts.values()),
                "缺听力文本或听力次序错配")
    else:
        require(not scripts, "语文片段不应含听力材料")


def student_paper(blueprint, candidate, layout_mode):
    from core.review_board import VERSION

    fields = {"number", "id", "points", "kind", "section", "stem", "material", "options",
              "grammar_tag", "recitation_sources"}
    public = {"subject":blueprint["subject"],"title":candidate["title"],"minutes":blueprint["minutes"],
              "points":150,"sections":blueprint["sections"],"materials":candidate["materials"],"layout_mode":layout_mode,
              "questions":[{k:v for k,v in q.items() if k in fields} for q in candidate["questions"]],
              "exam_policy":blueprint["exam_policy"]}
    reference=candidate.get("quality_benchmarks")
    if reference:
        public["quality_reference_sha256"]=fingerprint(reference)
        if reference.get("review_board") == VERSION:
            public["qa_protocol"] = VERSION
    return public


def prepare(root, blueprint, candidate, output, *, layout_mode="practice"):
    from core.language_render import render

    validate_structure(blueprint, candidate)
    public = student_paper(blueprint, candidate, layout_mode)
    reference = candidate.get("quality_benchmarks")
    scripts = candidate.get("listening", {})
    variants = {str(q["number"]): q["answer_variants"] for q in candidate["questions"] if q.get("answer_variants")}
    packet={"paper":public,"paper_version":fingerprint(public)}
    output.mkdir(parents=True,exist_ok=False)
    render(public, output/"paper")
    write_new(output/"blind-packet.json",packet)
    write_new(output/"listening-review.json",scripts)
    write_new(output/"verification.json",{"paper_version":packet["paper_version"],"paper_sha256":digest(output/"paper.pdf"),
              **({"quality_benchmarks":reference} if reference else {}),
              **({"exact_key_variants":variants} if variants else {}),
              "expected":[q["answer"] for q in candidate["questions"]],"blueprint_sha256":fingerprint(blueprint),
              "listening_sha256":fingerprint(scripts),"reference_notes":candidate["reference_notes"],
              "reference_scope":candidate["reference_scope"]})
    return {"state":"await_independent_review","paper_version":packet["paper_version"],"questions":len(public["questions"])}


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
        variants = verification.get("exact_key_variants", {}).get(str(label), [])
        require(result["answer"] in [expected, *variants], f"第{label}题答案复核不一致")
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
    if packet["paper"].get("qa_protocol") == "three-readers-v2":
        from core.review_board import LOCAL_QA_PASSED

        result["local_qa_status"] = LOCAL_QA_PASSED
    write_new(folder/"publication.json",result)
    return result
