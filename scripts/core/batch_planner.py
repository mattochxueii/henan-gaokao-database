"""Reserve distinct design briefs, then compare the written questions as well as the briefs."""
import re
from itertools import combinations
from analysis_db import fingerprint
from gaokao import require
from core import physics_corridor

# These are open-ended design briefs. No stem, answer, or question family is selected.
BRIEFS = {
    "physics": {
        "experiment_1": ["摆长截距|单摆测重力|校正系统偏差|拟合截距","时标误差|滚动影像|差分与帧率|频闪序列","冲量测量|软垫传感器|积分反证|力时图"],
        "experiment_2": ["并联漏导|电容放电|改变负载分离仪表效应|衰减记录","滑线电桥|换臂消去接头阻值|零示比较|桥臂拓扑","电功率标定|量热比较|分离散热截距|温升曲线"],
        "mechanics_calculation": [
            "反向制动滑板|缓冲平台|相对位移与触界先后|分段运动",
            "绳约束与碰接|货物转接|离绳临界与冲量分配|约束轨迹",
            "斜台摩擦换向|可倾输送线|边界停驻与返回|速度区间",
        ],
        "final": [
            "磁场分区偏转|离子速度分选|越界条件与轨道拼接|圆弧轨迹",
            "电容磁耦合|导轨电荷转移|稳态与撤力能量|电荷回路",
            "交变磁通制动|巡检器线圈|换向区间与能量界限|磁通时序",
        ],
    },
    "chemistry": {"process":["选择性浸出|废电极|分段保留|流程","结晶分离|盐湖|循环物料衡算|相图","膜分离|废液|离子迁移|膜室"],
        "final":["官能团保护|香料|比较合成次序|路线","环化选择性|功能材料|追踪碳架|键线","官能团定位|医药中间体|鉴别异构体|谱图"]},
    "biology": {"experiment":["气体交换|叶片|识别限制因素|响应曲线","种群增长|湿地|分层对照|样方图","运动调节|反射|识别对照|时间序列"],
        "final":["遗传互作|花色|判别亲本|系谱","物质代谢|萌发|碳收支|示踪表","生态演替|潮滩|检验干预|食物网"]},
    "math": {"extended":["空间截面|多面体|建立角度界限|投影","条件抽样|质检|修正概率|树图","轨迹|定位|参数消元|坐标"],
        "final":["递推不变量|离散调度|证明存在|数轴","导数比较|函数族|必要充分|曲线","组合计数|格点路径|双计数|格图"]},
    "chinese": {"reading":["论证边界|古建维护|辨析必要条件|文字","隐含冲突|乡村渡口|还原叙事视角|手记","反事实|节气物候|比较材料证据|论述"],
        "final":["标准的适用|工艺更新|权衡例外|材料","公共记忆|街巷命名|处理多方立场|对话","选择的成本|时间安排|论证责任|札记"]},
    "english": {"reading":["comparison bias|city shade|weigh controls|report","memory updating|oral history|trace a qualification|interview","sampling|wildlife count|interpret absence|dispatch"],
        "final":["reversal|rehearsal|repair a misunderstanding|dialogue","joint decision|community garden|resolve constraints|action","perspective shift|lost notebook|reconcile motives|detail"]},
}


def tag(value):
    fields=value.split("|")
    require(len(fields)==4 and all(fields), "设计指纹须有模型、情境、动作及表示")
    return dict(zip(("model","scene","action","representation"),fields,strict=True))


def plan(subject, count, pool=None):
    groups=pool if pool is not None else BRIEFS[subject]
    require(type(count) is int and count>0 and groups,"批量卷数或题位组无效")
    if subject == "physics":
        require(groups.keys() == physics_corridor.ROLE_SLOTS.keys(), "物理命题池须含两类实验、力学综合和电磁压轴")
    sets=[{} for _ in range(count)]
    for role,values in groups.items():
        chosen=[]
        def assign(index):
            if len(chosen)==count:
                return True
            for i in range(index,len(values)):
                entry=tag(values[i])
                if any(any(entry[k]==old[k] for k in entry) for old in chosen):
                    continue
                chosen.append(entry)
                if assign(i+1):
                    return True
                chosen.pop()
            return False
        require(assign(0),f"{role} 中无足够互斥的命题方向，请增加设计池")
        for paper,entry in zip(sets,chosen,strict=True):
            paper[role]=entry
    result = {"subject":subject,"count":count,"blueprints":sets,"pool_sha256":fingerprint(groups)}
    if subject == "physics":
        result["physics_corridor"] = corridor_brief()
    return result


def corridor_brief():
    return {"limits": {k:list(v) for k,v in physics_corridor.LIMITS.items()},
            "thermal_max": physics_corridor.THERMAL_MAX,
            "roles": {k:{"number":n,"group":g} for k,(n,g) in physics_corridor.ROLE_SLOTS.items()},
            "feasible_slot_example": list(physics_corridor.SLOT_EXAMPLE)}


def canonical(text):
    text=re.sub(r"\d+(?:[.．]\d+)?","数",text.casefold())
    return re.sub(r"[\W_]","",text)


def shingles(text):
    text=canonical(text)
    return {text[i:i+3] for i in range(max(1,len(text)-2))}


def implied_models(text):
    """Recognize a shared thermodynamic segment even when the prompts/name tags differ."""
    from unicodedata import normalize
    if "直线" not in text:
        return set()
    clean=normalize("NFKC",text.casefold()).replace(" ","").replace("_","").replace("\\","")
    states=[(int(v or 1),int(p or 1)) for v,p in re.findall(r"\((\d*)v0,(\d*)p0\)",clean)]
    return {"直线热力路径"+str(sorted((a,b))) for a,b in zip(states,states[1:])
            if (a[0]-b[0])*(a[1]-b[1])<0}


def question_text(q):
    if "writing" in q:
        w=q["writing"]
        text=" ".join([w["stem"],*(p["text"] for p in w.get("parts",[]))])
        return re.sub(r"\{\{(\w+)\}\}",lambda m:w["formulae"][m[1]]["latex"],text)
    return " ".join([q["stem"],*(p["text"] for p in q.get("parts",[]))])


def check(schedule, candidates):
    require(len(candidates)==schedule["count"],"批次数量不符")
    seen=[]
    failures=[]
    physics = schedule.get("physics_corridor")
    if physics is not None:
        require(schedule["subject"] == "physics" and physics == corridor_brief(), "物理蓝图走廊已变化，请重新规划")
    allocations = []
    for i,(candidate,brief) in enumerate(zip(candidates,schedule["blueprints"],strict=True)):
        require(candidate.get("subject","math" if "paper" in candidate and "schema_version" in candidate else None)==schedule["subject"],"批次学科不匹配")
        roles={}
        if physics:
            weights, findings = physics_corridor.allocation(candidate["questions"])
            allocations.append(weights)
            planned = physics["feasible_slot_example"]
            groups = weights["question_groups"]
            different = [n for n,g in enumerate(planned,1) if groups.get(str(n))!=g]
            for n,rule,fact in findings:
                failures.append({"paper":i+1,"number":n,"reason":fact,"rule":rule,
                                 "repair_numbers":[n] if n else different or [4, 14]})
        for n,q in enumerate(candidate["questions"],1):
            design=q["design"]
            require(all(isinstance(design.get(k),str) and design[k].strip()
                        for k in ("model","scene","action","representation")), "题目缺实际设计指纹")
            if role:=q.get("batch_role"):
                require(role not in roles and role in brief,"角色重复或不在设计中")
                roles[role]=True
                if any(design[k]!=v for k,v in brief[role].items()):
                    failures.append({"paper":i+1,"number":n,"reason":"偏离预留蓝图","role":role})
                if physics:
                    slot = physics["roles"][role]
                    if n != slot["number"] or weights["question_groups"].get(str(n)) != slot["group"]:
                        failures.append({"paper":i+1,"number":n,"reason":"批量换题须在指定板块和题位内",
                                         "role":role,"repair_numbers":sorted({n,slot["number"]})})
            text=question_text(q)
            material=candidate.get("materials",{}).get(q.get("material"),{})
            passage=material.get("text","")
            if len(passage)>160:
                text+=" "+passage
            seen.append((i+1,n,design,role or "",shingles(text),implied_models(text)))
        require(roles.keys()==brief.keys(),"预留的实验或压轴角色未全部使用")
    for (i,n,a,r,x,semantic_a),(j,m,b,s,y,semantic_b) in combinations(seen,2):
        if i==j:
            continue
        matched=[k for k in a.keys() & b.keys() if canonical(a[k])==canonical(b[k])]
        similarity=len(x&y)/max(1,len(x|y))
        if ({"model","action"}<=set(matched) or {"scene","action"}<=set(matched)
                or (r and s and "model" in matched) or semantic_a & semantic_b or similarity>=.58):
            failures.append({"paper":j,"number":m,"compares_to":[i,n],"matching_fields":sorted(matched),
                             "shared_structures":sorted(semantic_a & semantic_b),"text_jaccard":round(similarity,3),"reason":"跨卷设计或文字撞车"})
    return {"passed":not failures,"issues":failures,"schedule_sha256":fingerprint(schedule),
            "candidate_sha256":[fingerprint(c) for c in candidates],
            **({"allocations":allocations} if physics else {})}
