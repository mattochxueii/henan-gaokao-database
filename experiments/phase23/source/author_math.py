"""Host-authored Phase 23 items compiled into the established student/spec format."""
import argparse
import math
from pathlib import Path
import re
import sys

SOURCE=Path(__file__).resolve().parent
ROOT=SOURCE.parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
import bootstrap
from analysis_db import fingerprint
from gaokao import digest, read_json
from math_calibration import grade
from math_trends import SNAPSHOT
from national_db import rows
from storage import atomic_json


def calculate(expr):
    return {"op":"evaluate","expression":expr}


def check(expr, expected):
    return {"op":"claim","calculation":calculate(expr),"expected":expected}


def inspect_math(**facts):
    return {"op":"reasoning","algebra_checks":facts}


def figure(xlim,ylim,paths,marks,*,axes=True):
    return {"type":"coordinate","xlim":xlim,"ylim":ylim,"axes":axes,
            "paths":[{"points":p} for p in paths],
            "labels":[{"math":name,"at":coords,"offset":offset,"dot":dot} for name,coords,offset,dot in marks]}


def triangle():
    return figure([-1,7],[-.6,4], [[(0,0),(6,0),(2,3.2),(0,0)],[(2,3.2),(2.55,0)]],[
        ("A",(2,3.2),[0,4],False),("B",(0,0),[-12,-9],False),
        ("D",(2.55,0),[-2,-12],True),("C",(6,0),[6,-9],False)],axes=False)


def foci():
    return figure([-1,5],[-.9,3.35], [[(0,0),(4,0)],[(0,0),(1.7,2.2),(4,0)]],[
        ("A",(0,0),[-13,-13],True),("B",(4,0),[5,-13],True),
        ("P",(1.7,2.2),[1,5],True),("4",(2,0),[-3,-16],False)],axes=False)


def prism():
    return {"type":"wireframe",
            "vertices":{"A":[0,0,0],"B":[4,0,0],"C":[0,4,0],"A1":[0,0,4],"B1":[4,0,4],
                        "C1":[0,4,4],"M":[4/3,4/3,4/3],"P":[2,2,4],"Q":[2/3,2/3,8/3]},
            "edges":[list(name) for name in ("AB","BC","CA","AM","PQ")]+[
                ["A1","B1"],["B1","C1"],["C1","A1"],["A","A1"],["B","B1"],["C","C1"],["A1","B"],["A1","C"]],
            "hidden_edges":[["C","A"],["A","M"],["P","Q"],["A1","C"]],
            "marked_points":["M","P","Q"],"view_angles":[24,-38],
            "label_offsets":{"A":[-12,-4],"B":[8,-6],"C":[6,0],"A1":[-19,5],
                             "B1":[10,3],"C1":[7,5],"M":[-10,-11],"P":[-5,8],"Q":[-5,7]},
            "caption_math":"AB=AC=AA_1=4"}


def frustum():
    base = {"A":[-2,-2,0],"B":[2,-2,0],"C":[2,2,0],"D":[-2,2,0]}
    top = {key+"1":[x/2,y/2,3] for key,(x,y,_) in base.items()}
    ring = ["AB","BC","CD","DA"]
    edges = [list(side) for side in ring] + [[a+"1",b+"1"] for a,b in ring]
    return {"type":"wireframe","vertices":{**base,**top},"edges":edges+[[k,k+"1"] for k in base],
            "hidden_edges":[["C","D"],["D","A"],["D","D1"]],"view_angles":[22,-67],"show_vertex_labels":False,
            "labels":[{"math":"4","at":[0,-2,0],"offset":[0,-13]},
                      {"math":"2","at":[0,-1,3],"offset":[-3,4]},
                      {"math":"h=3","at":[2,0,1.55],"offset":[16,0]}]}


def parabola():
    a,b=(1+math.sqrt(5))/2,(1-math.sqrt(5))/2
    p=(-1,1)
    return figure([-2.5,4.3],[-2.6,3.9],
                  [[(t*t/4,t) for t in [i/20 for i in range(-49,74)]],
                   [p,(a*a,2*a)],[p,(b*b,2*b)],[(b*b,2*b),(a*a,2*a)],
                   [(-2.45,-.45),(.50,2.50)]],
                  [("P",p,[-14,5],True),("A",(a*a,2*a),[3,4],True),("B",(b*b,2*b),[4,-9],True),
                   (r"\ell:\ x-y=-2",(-2.35,2.95),[3,2],False),("O",(0,0),[-10,-13],False)])


def tangent_model():
    return figure([-.6,4.6],[-.5,4.6],
                  [[(u/100,100/u) for u in range(24,450)],
                   [(0,4),(1,0)],[(0,1),(4,0)]],
                  [("O",(0,0),[-11,-10],False),("Q",(.8,.8),[5,4],True),
                   (r"H:xy=1",(2.7,1/2.7),[5,7],False),
                   ("P_1",(.5,2),[4,4],True),("P_2",(2,.5),[0,7],True)])


def text_tokens(text, gallery):
    def push(match):
        token=f"f{len(gallery)+1}"
        gallery[token]={"kind":"notation","latex":match[1]}
        return "{{"+token+"}}"
    return re.sub(r"\\\((.*?)\\\)",push,text)


def make_item(n, edition, record, archive, slot, *, kind, points, basis=None):
    module, stem, solution, moves, tasks, parts, marks, options, pictured = record
    gallery={}
    given={"givens":{"statement":stem,"asks":list(parts)},"symbols":[],"tasks":tasks}
    if kind=="multiple_choice":
        given["assertions"]=dict(zip("ABCD",tasks,strict=True))
        given["tasks"]=[]
    opts={}
    if kind=="single_choice":
        given["options"]={k:{"semantic_value":opt[1]} for k,opt in zip("ABCD",options,strict=True)}
        opts={k:text_tokens(r"\("+opt[0]+r"\)",gallery) for k,opt in zip("ABCD",options,strict=True)}
    elif options:
        opts={k:text_tokens(opt,gallery) for k,opt in zip("ABCD",options,strict=True)}
    shown=text_tokens(stem,gallery)
    asks=[{"text":text_tokens(x,gallery),"task_refs":[j]} for j,x in enumerate(parts)]
    writing={"version":1,"spec_sha256":fingerprint(given),"stem":shown,"parts":asks,"options":opts,
             "formulae":gallery,"condition_anchors":[shown],"request_anchors":[asks[-1]["text"] if asks else shown],
             "used_symbols":[],"definitions":[],"figure":pictured,"figure_required":bool(pictured)}
    time=[2,4] if slot<=6 else [4,7] if slot<=14 else [9,13] if slot<=17 else [13,19]
    roles="foundation" if slot in {1,2,3,4,5,6,13} else "challenge" if slot in {8,11,14,18,19} else "transfer"
    reps=[{"kind":name,"evidence":ev,"after":[i] if i else []} for i,(name,ev) in enumerate(moves)]
    paper_source=next(archive[year,slot] for year in (2025,2024,2026) if (year,slot) in archive)
    rec={"id":f"orig:ai:phase23:{edition}:q{n:02d}","order":n,"kind":kind,"points":points,"module":module,
         "math_spec":given,"writing":writing,"solution":{"paragraphs":solution},
         "assessment":{"level":1 if roles=="foundation" else 3 if roles=="transfer" else 4,
                       "estimated_minutes":sum(time)//2,"part_points":[sum(p for p,_ in group) for group in marks],
                       "points_justification":moves[-1][1],"linked_progression":moves[-1][1],
                       "dimensions":{**dict.fromkeys(("knowledge","condition_comprehension","modeling",
                           "logical_reasoning","calculation","integration","breakthrough_visibility"),2),
                           "source_level_difference":moves[-1][1]},"empirical":False},
         "research_design":{"references":[{"occurrence_id":paper_source["occurrence_id"],
                            "version_sha256":paper_source["version_sha256"],
                            "transfer":moves[0][1],"structural_difference":moves[-1][1]}],
                            "novel_structure":stem,"reasoning_target":moves[-1][1]},
         "generation":{"provider":"host_ai","template_calls":0,"original_edition":"phase23"},
         "placement":{"role":roles,"purpose":moves[-1][1],"moves":reps,"minutes":time,
                      "structures":{"model":module+" "+moves[0][1],"goal":moves[-1][1],
                                    "route":[ev for _,ev in moves],"objects":[]}}}
    if basis:
        rec["trend_basis"]=basis
    rubric=[{"part":i,"points":p,"criterion":desc} for i,group in enumerate(marks,1) for p,desc in group]
    if not rubric:
        criterion=("全部选对的得6分，部分选对的得部分分，有选错的得0分。" if kind=="multiple_choice" else "答案正确。")
        rubric=[{"points":points,"criterion":criterion}]
    return rec,{"number":n,"steps":rubric}


def document(context_path, mode, destination, draft=False):
    from math_items import standard, trend, first_draft

    ctx=read_json(context_path)
    archive={(q["year"],q["number"]):q for q in rows(ROOT)
             if q["series_id"]=="cn-new-gaokao-1" and grade(q)=="source_and_solution_reviewed"}
    reference=ctx["quality_benchmarks"]
    if mode=="standard":
        data=standard()
        if draft:
            data=first_draft(data)
        slots=list(range(1,20))
        kinds=["single_choice"]*8+["multiple_choice"]*3+["fill_in"]*3+["constructed_response"]*5
        points=[5]*8+[6]*3+[5]*3+[13,15,15,17,17]
        title="河南新高考数学标准模拟卷"
        pack={}
        items=data
        cards=[None]*len(items)
        duration=120
    else:
        items,cards=trend()
        slots=[11,14,18,19]
        kinds=["multiple_choice","fill_in","constructed_response","constructed_response"]
        points=[6,5,17,17]
        title="2027 河南数学趋势研判专题"
        pack={"edition":"trend_pack"}
        duration=55
    compiled=[make_item(n,mode,r,archive,slot,kind=kind,points=p,basis=card)
              for n,(r,slot,kind,p,card) in enumerate(zip(items,slots,kinds,points,cards,strict=True),1)]
    questions,rubric=map(list,zip(*compiled,strict=True))
    doc={"schema_version":2,"research_protocol":"calibrated-v1",
         "paper":{"mode":"full" if mode=="standard" else "mixed","title":title,
                  "study_id":"HN23-M150-v3" if mode=="standard" else "HN23-T45-v2",
                  "minutes":duration,"total_points":sum(points),"require_scoring":True,**pack},
         "provenance":{"mode":"ai","provider":"host_ai","model_version":"Codex host",
                        "template_calls":0,"api_calls":0,"dna_sha256":ctx["dna_sha256"],
                        "context_sha256":digest(context_path),
                        "quality_reference_sha256":fingerprint(reference),
                        "revision":"draft" if draft else "reviewed_candidate"},
         "coverage_plan":{"basis":"2024–2026全国Ⅰ卷正文、DNA与目标近年19题制。",
                          "gaps":{},"concentration":{"函数与导数":"分根、切线、区间逼近三种推理任务依题位区分。",
                                                   "解析几何":"焦距和角度、弦切互换、局部与全局极值分开。",
                                                   "统计与概率":"分组记录、条件空间和截尾停止事件分开。"},
                          "progression":"从基础应用到分类、可达性、全称证明，逐段抬升。",
                          "intentional_links":[]},"questions":questions}
    if mode=="trend":
        doc["trend_snapshot_sha256"]=digest(ROOT/SNAPSHOT)
        doc["quality_benchmarks"]={**reference,
            "benchmark_slots":{str(n):slot for n,slot in enumerate(slots,1)},
            "slots":{str(n):reference["slots"][str(slot)] for n,slot in enumerate(slots,1)}}
    atomic_json(destination,doc)
    atomic_json(destination.with_name(destination.stem+"-rubric.json"),rubric)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("context",type=Path)
    parser.add_argument("mode",choices=("standard","trend"))
    parser.add_argument("destination",type=Path)
    parser.add_argument("--draft",action="store_true")
    a=parser.parse_args()
    document(a.context,a.mode,a.destination,a.draft)
