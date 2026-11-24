"""Blind review transport, deterministic scoring and immutable, item-locked revisions."""
from pathlib import Path
from typing import Protocol
import shutil

from analysis_db import fingerprint
from forecast_store import write_new
from gaokao import digest, read_json, require
from core.exam_qa import inspect, policies

VERSION="three-readers-v1"
ROLES=("solver","pedagogy","visual")
TARIFF={"coverage":6,"depth":4,"weak":3,"abstract":2,"graphic":2}
HARD={"constant","scoring","missing_blank","figures","notation"}
RULE_COST={"device":"coverage","coverage":"coverage"}


class BlindProvider(Protocol):
    """Optional heterogenous provider; the caller sends only these allowlisted inputs."""
    def review(self, *, role: str, student_pdf: bytes, rules: list,
               benchmarks: list, listening_script: dict | None) -> dict: ...


def packet_path(folder):
    pdf=folder/"paper.pdf"
    return pdf if pdf.is_file() else folder/"review-only/paper.pdf"


def evidence(root, folder, rule_snapshot=None):
    from core.quality_audit import _paper_inputs
    from pypdf import PdfReader

    ref,paper,version,pdf_sha=_paper_inputs(folder)
    pdf=packet_path(folder)
    doc=PdfReader(pdf)
    subj=ref["subject"]
    if (folder/"verification.json").exists():
        spec=read_json(folder/"verification.json")
        answers=spec.get("answers")
        if answers is None:
            answers=spec["expected"]
    else:
        spec=read_json(folder/"raw-ai-candidate.json")
        answers=[q.get("answer_key") for q in read_json(folder/"math-verification.json")]
    header="".join("".join((p.extract_text() or "").split()) for p in doc.pages)
    rules=rule_snapshot if rule_snapshot is not None else ref.get("qa_policy") or policies(root,subj)
    gate=inspect(root,subj,paper,answers,header=header,observations=ref.get("constant_observations",()),
                 policy_snapshot=rules)
    # Lock printed stems, options, parts, content-bound figures and any shared passage.
    versions={str(n):fingerprint([q,paper.get("materials",{}).get(q.get("material")),
                                   answers[n-1]]) for n,q in enumerate(paper["questions"],1)}
    return {"subject":subj,"version":version,"pdf_sha256":pdf_sha,"pages":len(doc.pages),
            "item_versions":versions,"ids":[q.get("id",q.get("number",n)) for n,q in enumerate(paper["questions"],1)],
            "choice_keys":{str(n):ans for n,(q,ans) in enumerate(zip(paper["questions"],answers),1)
                            if q.get("options") and isinstance(ans,str)},
            "rules":rules,"preflight":gate,"reference_sha256":fingerprint(ref)}


def blind_bundle(root, folder, role):
    from core.practice_workbook import authoring_context
    require(role in ROLES,"未知评审角色")
    state=evidence(root,folder)
    require(state["preflight"]["passed"],"先修复机器安检硬错误，再送盲审")
    examples=[]
    if role=="pedagogy":
        for q in authoring_context(root,state["subject"],limit=150)["references"]:
            if q["year"] in (2025,2026):
                examples.append({k:q.get(k) for k in ("id","year","number","topic","stem","parts","options")})
    listening=folder/"listening-review.json"
    return {"role":role,"rules":state["rules"],"benchmarks":examples,
            "listening_script":read_json(listening) if listening.is_file() and role!="visual" else None,
            "student_pdf":packet_path(folder).read_bytes()}


def dispatch(root,folder,role,provider):
    return provider.review(**blind_bundle(root,folder,role))


def export_blind(root,folder,role,target):
    payload=blind_bundle(root,folder,role)
    target.mkdir(parents=True,exist_ok=False)
    (target/"student.pdf").write_bytes(payload.pop("student_pdf"))
    write_new(target/"instructions.json",payload)
    return {"role":role,"pdf_sha256":digest(target/"student.pdf")}


def score_exam(state, reports, previous=None):
    pre=state["preflight"]
    versions=state["item_versions"]
    numbers=set(range(1,len(versions)+1))
    require(set(versions)=={str(n) for n in numbers},"题号不连续")
    round_no=previous["round"]+1 if previous else 1
    require(round_no<=3,"三轮用尽，禁止继续")
    if previous:
        require(previous["status"]!="rejected" and state["ids"]==previous["ids"]
                and previous["subject"]==state["subject"] and set(previous["item_versions"])==set(versions),
                "与此前试卷身份或题序不符")
        changed={int(k) for k,v in versions.items() if previous["item_versions"][k]!=v}
        allowed=set(previous["rewrite"])
        require(changed<=allowed and bool(changed),"零扣分题已锁定，或没有任何修订")
    charges=[]
    def add(n,category,rule,fact,reader,points=None):
        require(type(n) is int and (n in numbers or (reader=="machine" and n==0))
                and isinstance(fact,str) and fact.strip() and isinstance(rule,str) and rule,
                "扣分须有题号、规则及事实")
        require(category=="fatal" or category in TARIFF,"未知扣分维度")
        cost=0 if category=="fatal" else TARIFF[category]
        if category=="graphic" and points is not None:
            require(type(points) is int and points in (2,3),"图件瑕疵只扣2或3分")
            cost=points
        charges.append({"number":n,"category":category,"rule":rule,"points":cost,"evidence":fact,"reader":reader})
    shared=iter(state.get("repair_slots",()))
    for issue in pre["issues"]:
        number=issue["number"]
        if number==0:
            number=next(shared,None)
            require(number in numbers,"整卷问题缺少实际承接修订的题位")
        add(number,"fatal" if issue["rule"] in HARD else RULE_COST.get(issue["rule"],"fatal"),
            issue["rule"],issue["evidence"],"machine")
    if pre["passed"]:
        require(len(reports)==3 and {r["role"] for r in reports}==set(ROLES)
                and len({r["identity"] for r in reports})==3,"须有三份不同身份的隔离审稿")
        rules={r["id"] for r in state["rules"]}
        for report in reports:
            role=report["role"]
            require(report["identity"].strip() and report["pdf_sha256"].lower()==state["pdf_sha256"],"审稿身份或PDF版本不符")
            items=report["items"]
            require(len(items)==len(numbers) and {i["number"] for i in items}==numbers
                    and all(str(i.get("reasoning","")).strip() for i in items),"缺逐题审读记录")
            if role=="solver":
                require(all(i.get("answer") not in (None,"",{},[]) for i in items),"须由仅看题面的解题者给出逐题答案")
                for item in items:
                    key=state.get("choice_keys",{}).get(str(item["number"]))
                    if key is not None and sorted(str(item["answer"]))!=sorted(key):
                        add(item["number"],"fatal","all.solution","独立选项 "+str(item["answer"])+" 与提交键 "+key+" 不一致","comparison")
            if role=="pedagogy":
                require(all(i.get("comparison") and i.get("steps") and i.get("concepts") for i in items),"教研员缺同题位比较与推理证据")
            if role=="visual":
                require([p["number"] for p in report["pages"]]==list(range(1,state["pages"]+1))
                        and all(p["note"].strip() for p in report["pages"]),"漏审印刷页")
            for issue in report["findings"]:
                require(issue["rule"] in rules,"扣分未绑定当前排雷条目")
                add(issue["number"],issue["category"],issue["rule"],issue["evidence"],role,issue.get("points"))
    else:
        require(not reports,"机器安检未通过前不可先行AI评分")
    # Each per-question depth/choice defect is charged once even when independently confirmed twice.
    booked={}
    for c in charges:
        key=(c["number"],c["category"],"" if c["category"] in {"weak","depth"} else c["evidence"])
        booked[key]=max(booked.get(key,0),c["points"])
    fatal=sum(c["category"]=="fatal" for c in charges)
    score=0 if fatal else max(0,100-sum(booked.values()))
    rewrite=sorted({c["number"] for c in charges if c["number"]})
    status="eligible" if pre["passed"] and not fatal and score>=85 else "rejected" if round_no==3 else "returned"
    return {"protocol":VERSION,"round":round_no,"subject":state["subject"],"ids":state["ids"],
            "pdf_sha256":state["pdf_sha256"],"item_versions":dict(versions),"fatal_count":fatal,"final_score":score,
            "status":status,"deductions":charges,"charged_points":sum(booked.values()),
            "rewrite":rewrite,"locked":sorted(numbers-set(rewrite)),
            "prior_sha256":fingerprint(previous) if previous else None,
            "inputs_sha256":fingerprint([state,reports])}


def replay(history):
    last=None
    for index in range(1,4):
        path=history/f"round{index}.json"
        if not path.exists():
            break
        doc=read_json(path)
        last=score_exam(doc["state"],doc["reports"],last)
        require(last==read_json(history/f"scorecard-round{index}.json"),"历史评分或审稿输入被更改")
    return last


def record(root,folder,reports,previous_folder=None,repair_slots=()):
    from tempfile import TemporaryDirectory
    state=evidence(root,folder)
    state["repair_slots"]=list(repair_slots)
    require(not (folder/"board").exists(),"已评分版本不可覆写")
    prior=None
    if previous_folder:
        prior=replay(previous_folder/"board")
        require(prior is not None,"缺历史评分链")
    global_issues=[x for x in state["preflight"]["issues"] if not x["number"]]
    if global_issues and not repair_slots:
        # Prefer an editable choice currently overrepresented in the matched modules.
        counts={int(n):0 for n in state["item_versions"]}
        for hits in state["preflight"]["coverage"].values():
            for n in hits:counts[n]+=max(0,len(hits)-1)
        allowed=set(prior["rewrite"]) if prior else set(counts)
        options=sorted(allowed,key=lambda n:(str(n) not in state["choice_keys"],-counts[n],n))
        require(options,"缺可修改的题位")
        state["repair_slots"]=[options[i%len(options)] for i in range(len(global_issues))]
    result=score_exam(state,reports,prior)
    with TemporaryDirectory(dir=folder) as scratch:
        target=Path(scratch)/"board"
        if previous_folder:shutil.copytree(previous_folder/"board",target)
        write_new(target/f"round{result['round']}.json",{"state":state,"reports":reports})
        write_new(target/f"scorecard-round{result['round']}.json",result)
        target.rename(folder/"board")
    return result


def authorize(root,folder):
    history=folder/"board"
    result=replay(history)
    require(result is not None and result["status"]=="eligible","独立评分未达到发布条件")
    state=read_json(history/f"round{result['round']}.json")["state"]
    current=evidence(root,folder,state["rules"])
    require(all(state[k]==v for k,v in current.items()),"发布前题面、答案、规则或 PDF 已变更")
    return fingerprint(result)
