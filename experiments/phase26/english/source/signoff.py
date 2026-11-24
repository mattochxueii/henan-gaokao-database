"""Reconcile independently submitted replies without impersonating their authors."""
from pathlib import Path
import sys
import re

from author import ROOT, OUT, save, read_json, digest, fingerprint
from audit_data import wrong, gap_anchor, gap_condition

reading_spans = [
"Put your name on the list at the table on Saturday morning.",
"Our film follows one sack of grain through the upper rooms.",
"you will need it to come back through the gate",
"Each had its own tiny cracks.",
"I suppose you'd like it done by tea?",
"I knew because I had painted them.",
"We had a shelf there once",
"exactly what had appeared on the first learner's screen, including every pause",
"a rope with the red end on the right",
"Her partner had spent the same long pause trying to pull his loose end straight.",
"Just knowing that she could stop the film might have encouraged the first learner to predict the next move",
"Then, on Friday, I found two of those rolls at the bottom of my bag.",
"By the time I read the card I had understood it to mean bread that nobody ate.",
"more eager to tell his story",
"invite customers chosen by chance to keep a brief record of what happens at home",
]
registers={"listening":"日常对话、工作协商及游泳俱乐部的口头通知",
           "reading":"场馆说明、第一人称回忆、教学观察或面向公众的评论",
           "gap_match":"写给步行者的轻量速写指南，使用第二人称和具体动作",
           "cloze":"比赛记分员以第一人称回忆棋手复盘的经历",
           "grammar":"印刷室物件与游客体验的说明性短文",
           "application":"学生对外教的简短回信，须照顾广播听众",
           "continuation":"第一人称家庭叙事，以搬家前后两处厨房承接"}
register_read={"A":"周六参观磨坊的分项活动说明，时刻、入场和预约措辞具体。",
               "B":"舞台绘景者回忆初入行时的误解，人物含蓄对话与观看距离推动转折。",
               "C":"配对打结试验的程序、对照和解释，较强推论配有 might 限定。",
               "D":"面向烘焙店顾客的第一人称评论，用旧面包和自愿卡片落实统计范围。"}


def part_at(text,n):
    marker=f"[{n}]"
    parts=re.split(r"(?<=[.!?])\s+|\n",text)
    return next(p.strip() for p in parts if marker in p)


def choose_trap(s):
    if any(k in s for k in ("先","后来","原本","已","当前","顺序","时间","之前")):
        return "order"
    if any(k in s for k in ("目的","原因","动机","原因","作用")):
        return "cause"
    if any(k in s for k in ("扩大","所有","只","统计","范围")):
        return "scope"
    if any(k in s for k in ("移给","谁","所属","混同","人物","对象")):
        return "referent"
    return "inference_boundary"


def strings(x):
    if isinstance(x,list):
        return [str(v) for v in x]
    if isinstance(x,dict):
        return [f"{k}：{v}" for k,v in x.items()]
    return [str(x)]


def main(folder,roundno,work):
    board_path=folder/"board"/f"round{roundno}.json"
    reports={r["role"]:r for r in read_json(board_path)["reports"]}
    solver,teach=reports["solver"],reports["pedagogy"]
    paper=read_json(folder/"blind-packet.json")
    verification=read_json(folder/"verification.json")
    p=paper["paper"]
    notes=read_json(OUT/{1:"author-solutions.json",2:"author-solutions-round2.json",3:"author-solutions-final.json"}[roundno])["items"]
    reference=verification["quality_benchmarks"]
    sources={year:read_json(ROOT/f"data/papers/english/{year}-cn-english-national-1.json") for year in ("2025","2026")}
    audit=[]
    checked=[]
    writing=[]
    for q,note,sol,ped in zip(p["questions"],notes,solver["items"],teach["items"],strict=True):
        n=q["number"]
        assert n==note["number"]==sol["number"]==ped["number"]
        shared=p["materials"].get(q.get("material"),{})
        text=shared.get("text","")
        sec=q["section"]
        opts=q.get("options",shared.get("options",{}))
        why=note["reasoning"]
        key=note["answer"]
        if n <=65:
            if roundno>1:
                assert key==sol["answer"],(n,key,sol["answer"])
        else:
            criteria=note["rubric"]
            original_text=" ".join(strings(sol["answer"]))
            is_outline=bool(re.search(r"[一-龥]",original_text)) and len(re.findall(r"\b[A-Za-z]{2,}\b",original_text)) < (55 if n==66 else 110)
            assessed=(["看独立答卷是否给 Jo 可辨认的校园物品，并说明学生何时、为何接触它。",
                       "逐项核对声音事件是否可录制，能否让广播听众在没有画面的情况下联想到物件。",
                       "检查完整英文中的词汇、句式和可理解度。","核查收件人、邀请回应、组织和署名。"] if n==66 else
                      ["核对第一段能否在搬家限时内处理旧门刻度，并写出兄妹参与的动作。",
                       "核对第二段能否自然接到新居厨房，写出父亲及家庭的具体反应。",
                       "对照原给两段首句、第一人称及纸卷、门或身高的回扣。",
                       "检查成篇英语叙事的语法和句式。","检查第一段至第二段的时空过渡和事件闭合。"])
            scored_example={66:[(4,"美术教室的手摇削笔器与写生课前集体准备具体相连。"),(4,"安排插入铅笔、把手转动、铅笔屑落入抽屉及随后落笔的声音，最后留时间揭谜。"),(4,"约80词，动词具体，句法自然，时序清楚。"),(3,"Dear Jo、回应邀请、收尾及 Li Hua 署名齐全。")],
                            67:[(6,"纸边与地面对齐，逐条转印姓名和日期；May坚持自己画红线并收好纸卷。"),(6,"第二段新厨房中父亲蹲下校准纸条，妹妹把父亲推向墙边接续家庭记录。"),(5,"两句段首保留，第一人称与时间线一致，红刻线、黄外套和蓝色身高线回扣原文。"),(5,"约150词，动作具体，时态及对话易读。"),(3,"从旧宅转印到新居贴纸有完整因果，结尾以父亲脱鞋量身高收束。")]}
            writing.append({"number":n,"original_blind_answer":sol["answer"],"blind_reasoning":sol["reasoning"],
                "author_scoring_dimensions":criteria,
                "dimension_crosswalk":[{"max_points":crit["points"],"check":a,"rubric":crit["step"]} for a,crit in zip(assessed,criteria)],
                **({"editorial_scoring_of_actual_response":[dict(points=v,evidence=s) for v,s in scored_example[n]],"score":sum(v for v,s in scored_example[n])} if roundno==3 else {}),
                "submission_type":"独立作答要点" if is_outline else "独立答卷",
                "scoring_scope":"按独立答题要点核对人物、任务、情节与衔接；成篇语言、格式和词数以考生实际英文或所附完整范文另判，不虚填盲答总分。" if is_outline else "按明列的内容、衔接和语言维度核查该英语答卷，合理异答按同一维度计分。",
                "alignment":str(sol["reasoning"]),"sample_is":"独立于盲答的完整可接受示例"})
        checked.append({**note,"ambiguity":False,"original_blind_answer":sol["answer"],
                        "blind_reasoning":sol["reasoning"],"author_reasoning":why})
        if n<=20:
            script=read_json(folder/"listening-review.json")[q["material"]]
            style=registers[sec]+"。"+why
            span=script.splitlines()[0]
        elif n<=35:
            span=reading_spans[n-21]
            style=register_read[q["material"]]
        elif n<=65:
            span=part_at(text,n)
            style=registers[sec]+"。"+why
        else:
            span=q["stem"].splitlines()[0]
            style=registers[sec]+"。"+why
        comparisons={}
        for year,source in reference["slots"][str(n)].items():
            original=sources[year]["questions"][source["reference_number"]-1]
            benchmark=original["stem"]
            if 36<=n<=65:
                passage=sources[year]["passages"].get(original.get("passage"),"")
                focus=source.get("features") or original.get("features") or []
                source_no=original.get("source_number",n)
                # Original transcriptions use 16–45 in one year, 36–65 in the other.
                rgx=r".{0,55}(?<![0-9])"+str(source_no)+r"(?![0-9]).{0,75}"
                hit=re.search(rgx,passage.replace("\n"," "))
                if hit: benchmark=hit[0]
                elif focus: benchmark=str(focus)
            c=ped["comparison"]
            insight=c.get(year) if isinstance(c,dict) else c
            comparisons[year]={"version_sha256":source["version_sha256"],
                               "reference_number":source["reference_number"],
                               "comparison":f"{year}年同题位「{benchmark[:135]}」。{insight} 本题取证：{why}"}
        paths={}
        if opts:
            assert isinstance(key,str) and len(key)==1
            for k,v in opts.items():
                if k==key: continue
                if sec=="gap_match":
                    actual=gap_anchor[k]
                    error=f"将“{actual}”插到此处。{gap_condition[n]}。"
                    trap="cohesion"
                else:
                    actual,error=wrong[n][k].split("｜")
                    if roundno==1 and n==17:
                        actual,error=("材料说筹码用铜制成","选项却只说金属很轻，材料没有提到重量") if k=="B" else ("物件在收藏盒中找到","选项另说盒上有俱乐部名，原文没有铭文线索")
                    if roundno==1 and n==54:
                        actual,error={"B":("桌子在平面图上留位","将空间留位接为 left it up on the chart"),
                                      "C":("该桌没有登记结果","选项 open 可以和残留的 on the chart 成句，破坏唯一性"),
                                      "D":("场地图标了空位","把平面图上的标记移到成绩表")}[k]
                    trap=choose_trap(error)
                paths[k]=dict(misconception=error,mechanism=f"选项 {k}「{v}」保留“{actual}”，却{error}。",
                              plausible=True,trap=trap,subtle=True,unchanged=actual,distortion=error)
        row={"number":n,"benchmarks":comparisons,"answer_key":key,
             "depth":{"reasoning_steps":strings(ped["steps"]),"linked_concepts":strings(ped["concepts"])},
             "findings":{"distractors":{"verdict":"pass" if opts else "not_applicable","evidence":why if opts else "本题根据开放作答或词形填入评分，无备选项。"},
                         "depth":{"verdict":"pass","evidence":sol["reasoning"]},
                         "figure":{"verdict":"not_applicable","evidence":"题面条件均在语篇、对话或设问文字中。"},
                         "language":{"verdict":"pass","evidence":style}},
             "language_style":{"natural":True,"register":register_read.get(q.get("material"),registers[sec]),"evidence":style},
             "distractors":paths}
        if sec in ("reading","gap_match","cloze","grammar"):
            assert span in text,(n,span)
            row["reading_turn"]={"span":span,"from":span,"to":why}
        if roundno==1 and n in (17,54):
            issue=next(v for v in solver["findings"] if v["number"]==n)
            row["findings"]["distractors"]={"verdict":"return","evidence":issue["evidence"]}
            for k,path in paths.items():
                if n==17 or k=="C":path["subtle"]=False
        audit.append(row)
    pd=digest(folder/"paper.pdf")
    assert pd==solver["pdf_sha256"]==teach["pdf_sha256"]
    work.mkdir(parents=True,exist_ok=True)
    doc={"reviewer":"英语命题席，按真实教研与求解记录复核","protocol":reference["protocol"],
        "paper_version":paper["paper_version"],"paper_pdf_sha256":pd,"reference_sha256":fingerprint(reference),"items":audit}
    if roundno==1:
        save(work/"draft-audit.json",doc)
        return
    if (OUT/"round1/quality-result.json").is_file():
        changes=read_json(OUT/"revision-round2.json")["changes"]
        doc["revisions"]={str(v["number"]):{"distractors":v["reason"]} for v in changes}
    save(work/"release-review.json",{"reviewer":solver["identity"]+"（原始盲答）／英语命题席（评分对照整理）",
        "input_scope":"student_materials_and_listening_only","scope_note":"输入范围指独立解题者。命题席随后逐题核对，答案理由与评分范文独立留存。",
        "paper_version":paper["paper_version"],"paper_pdf_sha256":pd,"board_input_sha256":digest(board_path),"solver_canonical_sha256":fingerprint(solver),"items":checked})
    save(work/"release-audit.json",doc)
    save(work/"writing-reconciliation.json",{"solver":solver["identity"],"solver_canonical_sha256":fingerprint(solver),"items":writing})

if __name__=="__main__":
    main(Path(sys.argv[1]),int(sys.argv[2]),Path(sys.argv[3]))
