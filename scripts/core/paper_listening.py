"""Add a cross-checked listening layer to an existing written-only English record."""
from pathlib import Path
from urllib.parse import urlsplit

from analysis_db import fingerprint
from core.paper_intake import PUBLIC, listening_fingerprint
from gaokao import read_json, relative_path, require
from storage import atomic_json


def attach(root, identifier, packet):
    path = relative_path(root / PUBLIC / "english", identifier+".json")
    paper=read_json(path)
    require(paper["id"]==identifier and paper["subject"]=="english" and paper.get("written_only"),
            "该英语卷已经有听力或标识不匹配")
    require(fingerprint(paper["questions"])==packet["written_sha256"]==paper["content_sha256"]
            and [q["number"] for q in paper["questions"]]==list(range(21,68)),
            "笔试正文版本发生变化")
    source=packet["source"]
    for item in ("questions_url","transcript_url","key_url"):
        url=urlsplit(source.get(item,""))
        require(url.scheme=="https" and url.hostname,"听力资料缺少对应来源")
    require(source.get("edition_alignment"),"需要说明题目、原文与题键如何对齐")
    questions=packet["questions"]
    groups=packet["groups"]
    require([q["number"] for q in questions]==list(range(1,21)),
            "听力须包含第 1–20 题")
    require(len(groups)==10 and [n for g in groups for n in g["numbers"]]==list(range(1,21))
            and all(len(g["text"].split())>=12 for g in groups),"听力原文或题组覆盖不完整")
    require(all(q["stem"].strip() and set(q["options"])==set("ABC") and q["answer"] in q["options"]
                and len(set(q["options"].values()))==3 and all(x.strip() for x in q["options"].values())
                and q["position"].strip() for q in questions),"听力题面、选项、题键或定位不完整")
    by_number={n:g for g in groups for n in g["numbers"]}
    transcripts={}
    for n,g in enumerate(groups,1):
        g["id"]=f"listening-{n:02d}"
        transcripts[g["id"]]=g["text"]
    new=[]
    for q in questions:
        n=q["number"]
        q={**q,"id":f"{identifier}:q{n:03d}","kind":"single_choice","points":1.5,
           "topic":"听力","listen_group":by_number[n]["id"],"source_url":source["questions_url"],
           "asset_refs":[],"usable_for_practice":True,"source_and_solution_reviewed":False}
        q["version_sha256"]=fingerprint(q)
        new.append(q)
    paper["written_sha256"]=paper["content_sha256"]
    paper["questions"]=new+paper["questions"]
    paper["listening_transcript"]=transcripts
    paper["listening_groups"]=[{k:v for k,v in g.items() if k!="text"} for g in groups]
    paper["listening_source"]=source
    paper["listening_sha256"]=listening_fingerprint(paper)
    paper["question_count"]=67
    paper["points"]=150
    paper["written_only"]=False
    paper["title"]=paper["title"].replace("（完整笔试）","")
    paper["content_sha256"]=fingerprint(paper["questions"])
    atomic_json(path,paper)
    return {"paper_id":identifier,"listening_questions":20,"full_questions":67,"script_groups":10}
