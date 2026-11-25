
"""Versioned, fail-closed blind reader protocol for the current standard release."""
from gaokao import require

DIMENSIONS = {
    "correctness":"逐题独立求解，核对条件、定义域、特殊情形和答案唯一性。",
    "curriculum":"核对考试政策、高中教材口径、标准常量和等价解。",
    "marking":"核对分值、给分节点、预印格式及多种正确表达。",
    "depth":"核对题位功能、推理转折、干扰项及压轴区分度。",
    "balance":"核对板块分布、跨题重复、答案偏态及材料扎堆。",
    "language":"核对语义、术语、引文、图文一致与信息泄露。",
    "visual":"逐页核对字体、图表、标注、折行与作答区域。",
    "time":"分别估算中等生与尖子生的分块用时，并核对拉分题。",
}
BLOCKS = {
    "chinese":{"reading","classics","language","essay"},
    "math":{"single","multiple","fill","solutions"},
    "english":{"listening","reading","language","writing"},
    "physics":{"single","multiple","experiments","calculations"},
    "chemistry":{"single","nonchoice"},
    "biology":{"single","nonchoice"},
}
ANCHORS = {
    "chinese":{5,9,14,22},"english":{31,35,55,67},"math":{8,14,19},
    "physics":{7,13,15},"chemistry":{12,14,17,18},"biology":{15,16,20,21},
}
FLOORS = {"chinese":95,"math":95,"english":95,"physics":55,"chemistry":55,"biology":55}


def instructions(subject):
    return {"dimensions":DIMENSIONS,"probe_role":"pedagogy","profiles":["middle","advanced"],
            "blocks":sorted(BLOCKS[subject]),"gate_items":sorted(ANCHORS[subject]),"advanced_min_minutes":FLOORS[subject],
            "timing_kind":"editorial_estimate",
            "gate_flags":["inverted_difficulty","recalled_routine","repeated_model"]}


def reply_findings(subject, report):
    items=ANCHORS[subject]
    primary=max(items)
    dimensions=report.get("dimensions")
    if not isinstance(dimensions,dict) or set(dimensions)!=set(DIMENSIONS) or not all(
            isinstance(v,str) and len(v.strip())>=8 for v in dimensions.values()):
        yield primary,"board.eight_dimensions","缺逐维、可核对的八项审读回执"
    if report["role"]!="pedagogy":
        return
    probe=report.get("difficulty_probe",{})
    if not isinstance(probe,dict):
        probe={}
    timing=probe.get("minutes",{})
    if not isinstance(timing,dict) or set(timing)!={"middle","advanced"} or any(
           not isinstance(p,dict) or set(p)!=BLOCKS[subject] or not all(
               type(v) in (int,float) and 0<v<=180 for v in p.values()) for p in timing.values()):
        yield primary,"board.timing_missing","缺中等生与尖子生两套逐板块分钟数"
    elif sum(timing["advanced"].values())<FLOORS[subject]:
        yield primary,"board.timing_floor",f"尖子生估计{sum(timing['advanced'].values()):g}分钟，低于{FLOORS[subject]}分钟"
    elif sum(timing["middle"].values())<sum(timing["advanced"].values()):
        yield primary,"board.timing_order","中等生总估时低于尖子生，须复核估时"
    anchors=probe.get("gate_items",[])
    if not isinstance(anchors,list) or any(not isinstance(a,dict) for a in anchors) or len(anchors)!=len(items) \
       or {a.get("number") for a in anchors}!=items:
        yield primary,"board.anchors_missing","缺预登记把关题的逐题难度依据"
        return
    for item in anchors:
        flags=("inverted_difficulty","recalled_routine","repeated_model")
        if not isinstance(item.get("reasoning"),str) or len(item["reasoning"].strip())<8 or any(
                type(item.get(field)) is not bool for field in flags):
            yield item["number"],"board.anchor_invalid","把关题须提交方法证据与三个布尔判断"
        elif bad:=[field for field in flags if item[field]]:
            yield item["number"],"board.anchor_failed",item["reasoning"]+"（"+ "、".join(bad)+"）"
