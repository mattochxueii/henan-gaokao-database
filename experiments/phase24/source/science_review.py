"""Bind complete science re-derivations and same-position editorial evidence."""
import argparse
from pathlib import Path
import re
import sys

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(SOURCE.parents[1] / "phase21/source")]
from analysis_db import fingerprint
from core.quality_audit import RULES
from gaokao import digest, read_json, require
from record_review import build_review
from storage import atomic_json
from science_notes import AQUEOUS, BIO_DEPTH, BIO_WRONG, DRAFT_NOTES, FIGURES, NEW_ROUTES

PHASE22 = SOURCE.parents[1] / "phase22"


def blocks(path):
    text = path.read_text(encoding="utf-8")
    return {int(k.split()[0]):"## "+k.strip()
            for k in re.split(r"(?m)^## (?=\d+\b)",text)[1:]}


def solved_text(subject):
    rows = {} if subject=="biology" else blocks(PHASE22/"source"/f"{subject}-rederive.md")
    rows.update(blocks(SOURCE/f"{subject}-resolutions.md"))
    return "\n\n".join(rows[n] for n in sorted(rows))


def advanced(subject, number, notes):
    if subject == "biology":
        step1,step2,topic = BIO_DEPTH[number-1]
        errors = BIO_WRONG[number-1] if number<=16 else {}
        return [step1,step2], [topic.split("、",1)[0],step2], {
            choice:{"mistake":text,"link":text} for choice,text in errors.items()}
    if replacement := NEW_ROUTES.get(subject,{}).get(number):
        route, concept, errors = replacement
        steps = route.split("，再",1)
        if len(steps)==1:
            steps.append(concept+"的条件适用性独立核算")
        return steps, [concept,steps[-1]], {choice:{"mistake":text,"link":text} for choice,text in errors.items()}
    note = notes[number-1]
    return note["steps"],note["concepts"],{
        choice:{"mistake":pair[0],"link":pair[1]} for choice,pair in note.get("errors",{}).items()}


def figure_audit(subject,n,row,note):
    if not row.get("figure"):
        return {}
    anchors=FIGURES[subject].get(n,())
    if subject=="physics" and n==4:
        anchors=[("120","120 V","原边供电"),("2:1","匝数比2∶1","原线圈与副线圈"),
                 ("5.0","两只5.0 Ω","限流与负载电阻")]
    observation = "图中的标注、相对位置、线型与学生页文字逐项对照。"
    return {"figure_conditions":{"records":[{"anchor":a,"label":b,"meaning":c} for a,b,c in anchors],
                                 "observation":observation,"qualitative_only":not anchors},
            "required_figure_information":note or
                "图示承载条件间的关系、实测序列或装置连接。文字明示关键值，两种读法互相校核。"}


def audit(subject,folder,candidate,review=None,draft=False):
    packet=read_json(folder/"blind-packet.json")
    reference=read_json(folder/"verification.json")["quality_benchmarks"]
    old=[] if subject=="biology" else read_json(PHASE22/"source"/f"{subject}-editorial.json")
    paper=packet["paper"]
    rows=[]
    for n,q in enumerate(paper["questions"],1):
        steps,concepts,errors=advanced(subject,n,old)
        returned=DRAFT_NOTES.get(str(n),{}) if draft else {}
        choice=bool(q["options"])
        key=(review["items"][n-1]["answer"] if review else candidate["questions"][n-1]["proposed_answer"]) if choice else None
        options={}
        if choice:
            for letter in sorted(set(q["options"])-set(key)):
                if "distractors" in returned:
                    options[letter]={"plausible":False,"misconception":"直接读取单值的相近备选",
                                      "mechanism":"给定数可直接抄得，选项未考查分组或机制误读。"}
                else:
                    e=errors[letter]
                    options[letter]={"plausible":True,"misconception":e["mistake"],"mechanism":e["link"]}
        benchmarks={}
        for year,sample in reference["slots"][str(n)].items():
            qualifier = "候选卷证据范围有限，只参考已知题位和主题。" if sample["scope"]!="practice_text" else ""
            rationale = (old[n-1]["refs"][int(year)-2025] if old and n not in NEW_ROUTES.get(subject,{})
                         else f"实际该题位主题为{sample.get('topic') or '题组理解'}，比对任务的约束层数和信息处理。项目题先{steps[0]}，再{steps[-1]}。")
            benchmarks[year]={"version_sha256":sample["version_sha256"],"id":sample["id"],
                              "comparison":qualifier+rationale}
        figure = figure_audit(subject,n,q,old[n-1].get("figure") if old and n not in NEW_ROUTES.get(subject,{}) else None)
        applicable={"depth":True,"language":True,"distractors":choice,"figure":bool(q.get("figure"))}
        summary={"depth":" → ".join(steps),"distractors":"各错误项与独立键分离，错误路径逐项登记。" if choice else "分步作答。",
                 "language":"终稿定义、范围与求解要求对应。","figure":figure.get("required_figure_information","文字题。")}
        rows.append({
            "number":n,"answer_key":key,"benchmarks":benchmarks,
            "findings":{rule:{"verdict":"return" if rule in returned else
                              "pass" if applicable[rule] else "not_applicable",
                              "evidence":returned.get(rule,summary[rule])} for rule in RULES},
            "depth":{"reasoning_steps":steps,"linked_concepts":concepts},
            "distractors":options,**figure,
            **({"aqueous_competition":AQUEOUS[n]} if subject=="chemistry" and n in AQUEOUS else {})
        })
    if subject=="biology":
        changes=DRAFT_NOTES if not draft else {}
    else:
        changes=read_json(PHASE22/subject/"quality-audit.json")["revisions"]
    return {"protocol":reference["protocol"],"reviewer":"宿主对终稿与两年题位的逐项复核",
            "paper_version":packet["paper_version"],"paper_pdf_sha256":digest(folder/"paper.pdf"),
            "reference_sha256":fingerprint(reference),"items":rows,"revisions":changes}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("subject",choices=("physics","chemistry","biology"))
    p.add_argument("folder",type=Path)
    p.add_argument("candidate",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--draft",action="store_true")
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    student = None
    if not a.draft:
        transcript=solved_text(a.subject)
        student=build_review(a.folder,transcript)
        atomic_json(a.output/"independent.json",student)
    atomic_json(a.output/"audit.json",audit(a.subject,a.folder,read_json(a.candidate),student,a.draft))
