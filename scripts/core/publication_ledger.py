
"""Persistent publication history and a single-subject production receipt."""
from datetime import date
import re

from analysis_db import fingerprint
from forecast_store import write_new
from gaokao import atomic_write, read_json, require
from storage import atomic_json


def paper_id(candidate):
    rows=candidate.get("questions",[])
    require(rows and all(isinstance(q.get("id"),str) for q in rows),"候选题须有唯一原创ID")
    prefixes={q["id"].rsplit(":",1)[0] for q in rows}
    require(len(prefixes)==1,"同一套试卷须共用一个原创ID前缀")
    return next(iter(prefixes))


def claim(path, subject, candidate):
    require(candidate.get("subject",candidate.get("paper",{}).get("subject",subject))==subject,
            "候选学科与任务不符")
    scope={"subject":subject,"paper_id":paper_id(candidate)}
    if path.is_file():
        require(read_json(path)==scope,"同一任务只接受一个学科的一套试卷；修订须沿用试卷 ID")
    else:
        write_new(path,scope)
    return scope


def history(root,subject):
    path=root/"data/ledger"/f"{subject}.json"
    return read_json(path)["entries"] if path.is_file() else []


def signatures(paper):
    rows=paper["questions"]
    materials_map=paper.get("materials",{})
    text_ids=[fingerprint({
        "stem":re.sub(r"\s+","",q["stem"]),
        "material":re.sub(r"\s+","",materials_map.get(q.get("material"),{}).get("text","")),
        "options":q.get("options",{}),"parts":q.get("parts",[]),
    }) for q in rows if len(q["stem"].strip())>15 or q.get("options") or q.get("parts")]
    declaration=paper.get("ledger_topics",{})
    require(isinstance(declaration,dict) and all(
        isinstance(key,str) and re.fullmatch(r"[a-z_]{2,32}",key) and isinstance(values,list) and
        1<=len(values)<=24 and all(isinstance(v,str) and 1<=len(v.strip())<=90 for v in values)
        for key,values in declaration.items()),"历史台账主题格式错误")
    canonical={v.casefold().strip() for values in declaration.values() for v in values}
    models={q[key].casefold().strip() for q in rows for key in ("experiment_archetype","model_fingerprint")
            if isinstance(q.get(key),str)}
    materials={v["source_title"] for v in paper.get("materials",{}).values() if v.get("source_title")}
    material_digests=sorted(fingerprint(re.sub(r"\s+","",v["text"])) for v in paper.get("materials",{}).values()
                            if len(v.get("text",""))>=100)
    return {"paper_id":paper_id(paper),"stems":sorted(text_ids),
            "declared_topics":declaration,"topic_index":sorted(canonical|models),
            "material_sha256":material_digests,"materials":sorted(materials)}


def reuse_findings(root,subject,paper,pdf_sha256=None):
    current=signatures(paper)
    for old in history(root,subject):
        if old["paper_id"]==current["paper_id"] and old["pdf_sha256"]==pdf_sha256:
            continue
        previous=old["paper_id"]
        if previous==current["paper_id"]:
            yield f"试卷ID {previous} 已发布"
        if overlap:=set(old["stems"]) & set(current["stems"]):
            yield f"与{previous}逐字重复{len(overlap)}道题"
        if overlap:=set(old["topic_index"]) & set(current["topic_index"]):
            yield f"与{previous}重复主题/实验/压轴模型：{'、'.join(sorted(overlap))}"
        if overlap:=set(old["materials"]) & set(current["materials"]):
            yield f"与{previous}重复材料：{'、'.join(sorted(overlap))}"
        if overlap:=set(old.get("material_sha256",[])) & set(current["material_sha256"]):
            yield f"与{previous}重复{len(overlap)}份材料正文"


def register(root,subject,paper,pdf_sha256,*,published_on=None):
    folder=root/"data/ledger"
    folder.mkdir(parents=True,exist_ok=True)
    entries=history(root,subject)
    row={**signatures(paper),"date":published_on or date.today().isoformat(),"pdf_sha256":pdf_sha256}
    if any(x["pdf_sha256"]==pdf_sha256 for x in entries):
        return
    findings=list(reuse_findings(root,subject,paper))
    require(not findings,"出版台账冲突："+"；".join(findings))
    entries.append(row)
    atomic_json(folder/f"{subject}.json",{"subject":subject,"entries":entries})
    md=[f"# {subject} 出卷台账"]
    for item in entries:
        md.extend(["",f"## {item['paper_id']} · {item['date']}",
                   "",f"卷面 SHA-256 {item['pdf_sha256']}",""])
        for key in ("topic_index","materials"):
            md.extend(f"- {value}" for value in item[key])
    atomic_write(folder/f"{subject}.md","\n".join(md)+"\n")
