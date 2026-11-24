"""Assemble three independently authored language blocks into a standard candidate."""
from analysis_db import fingerprint
from core import exam_qa, language_workflow
from core.practice_workbook import validate_authoring_context
from forecast_store import write_new
from gaokao import CODE, digest, read_json, require

PROTOCOL = "gaokao-language-part-v1"
PARTS = {
    "chinese": (("information", "literary"), ("classical", "poetry", "recitation"), ("language", "essay")),
    "english": (("listening",), ("reading", "gap_match"), ("cloze", "grammar", "application", "continuation")),
}


def merge(root, subject, year, files, context, output):
    require(subject in PARTS and len(files) == 3, "语英须提供三个不同片段")
    blueprint = language_workflow.plan(root, subject, "河南", year)
    sources = [read_json(path) for path in files]
    by_part = {doc["part"]:doc for doc in sources}
    require(set(by_part) == {"part1","part2","part3"}, "须各提供 part1、part2、part3")
    metadata = by_part["part1"]
    identifier = metadata["paper_id"]
    require(isinstance(identifier,str) and CODE.fullmatch(identifier)
            and isinstance(metadata["title"],str) and metadata["title"].strip(), "第一个片段须有统一卷 ID 与卷名")
    questions, materials, listening, notes = [], {}, {}, []
    fields = {"protocol", "part", "subject", "paper_id", "title", "reference_notes", "questions", "materials", "listening"}
    for index, section_ids in enumerate(PARTS[subject],1):
        part = by_part[f"part{index}"]
        require(part.keys() <= fields and part["protocol"] == PROTOCOL and part["subject"] == subject
                and part["paper_id"] == identifier and (index == 1 or "title" not in part),
                f"part{index} 字段、学科或试卷 ID 不匹配")
        fragment = part["questions"]
        expected = [(section["first"] + offset, section["id"], score)
                    for section in blueprint["sections"] if section["id"] in section_ids
                    for offset, score in enumerate(section["scores"])]
        require([(q["number"],q["section"],q["points"]) for q in fragment] == expected,
                f"part{index} 题号、题组或逐题分值不符")
        passages = part["materials"]
        passed = {}
        for q in fragment:
            if name := q.get("material"):
                require(name in passages and passed.setdefault(name,q["section"]) == q["section"],
                        f"part{index} 跨片段或跨题组引用材料")
        require(set(passages) == passed.keys() and not (passages.keys() & materials.keys()),
                f"part{index} 材料 ID 重复或未使用")
        questions.extend(fragment)
        materials.update(passages)
        references = part["reference_notes"]
        require(isinstance(references,list) and references and all(isinstance(s,str) and s.strip() for s in references),
                f"part{index} 缺真题特征和原创差异说明")
        notes.extend(references)
        if scripts := part.get("listening"):
            require(subject == "english" and index == 1, "听力稿只能出现在英语 part1")
            group_ids = list(dict.fromkeys(q["material"] for q in fragment))
            require(isinstance(scripts,dict) and set(scripts) == set(group_ids), "十组听力稿与题组未对应")
            listening = {key:scripts[key] for key in group_ids}
    reference = read_json(context)
    candidate = {
        "id":identifier,"subject":subject,"title":metadata["title"],
        "blueprint_sha256":fingerprint(blueprint),"reference_scope":"fulltext",
        "reference_notes":notes,"materials":materials,"questions":questions,
        "provenance":{"context_sha256":digest(context),"dna_sha256":reference["dna_sha256"],
                      "quality_reference_sha256":fingerprint(reference["quality_benchmarks"]),
                      "language_corpus_sha256":fingerprint(reference["language_corpus"]),
                      "section_sha256":{part["part"]:fingerprint(part) for part in sources}},
    }
    if listening:
        candidate["listening"] = listening
    language_workflow.validate_structure(blueprint,candidate)
    validate_authoring_context(root,subject,context,candidate)
    paper = language_workflow.student_paper(blueprint,candidate,"practice")
    qa = exam_qa.inspect(root,subject,paper,[q["answer"] for q in questions],
                         listening=listening,enforce_corridors=True)
    require(qa["passed"], "合卷硬安检失败：" + "；".join(f'第{i["number"]}题 {i["evidence"]}' for i in qa["issues"]))
    write_new(output,candidate)
    return {"state":"merged","output":str(output),"questions":len(questions),"points":paper["points"],
            "policy_year":year,"candidate_sha256":digest(output)}
