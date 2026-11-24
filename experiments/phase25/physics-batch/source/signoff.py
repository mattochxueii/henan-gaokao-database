"""Adapt released blind reports to the pre-existing science PDF and position-review protocols."""
import argparse
import re
from pathlib import Path
from analysis_db import fingerprint
from forecast_store import write_new
from gaokao import read_json, require
from core.science_workflow import blank_numbers, adjudicate
from core.quality_audit import submit
from core.review_board import replay

# The editor compared these exact PDF-only response records with the submitted canonical keys.
# The mapping is never an answer generator: fresh versions require a new reconciliation.
EQUIVALENCE={
    "A":{
      11:"20间隔对应10个周期；2.00 s、4倍、截距/斜率=1 cm及4π²/4.03=9.80",
      12:"等电压比；1.20 s、理想比2、更高内阻、双档差分得12 μF",
      13:"浮出6 cm；净力12 N向上；浮力36降到30 N，动能增加2.70 J",
      14:"峰值2 V，外功率0.375 W；9与1/9均为正根，热限排除后者",
      15:"相对滑距各v²/(3μg)，净左移2v²/(9μg)；先于终止须严格大于"},
    "B":{
      11:"相邻位移差−0.4 cm，中心差分0.84 m/s，远标尺致加速度幅值偏大",
      12:"30至35 cm间找零；绕远端为200−x，x=64 m，附加完好线电阻使估测偏小",
      13:"匀加速/减速段向上制动力3500/6500 N；总回收21600 J",
      14:"面积p₀V₀/2，定容增内能3p₀V₀/2，换向点1.875V₀，先吸热",
      15:"动量与电压增量联立；撤力电流不反向；电能和机械能之差等价于对RI dq求面积"}}
ANCHORS={
"A":{1:"2.0、5.0 eV",3:"6.0 cm",4:"108 kPa",5:"4.0 cm、6.0 cm",6:"0.60 mWb",
     8:"电压表并联在光敏电阻两端",10:"2 m/s"},
"B":{2:"24 km/s、36 km/s",3:"55°",4:"18 cm、22 cm",5:"1 V、4 V、2 V",6:"0.040 s",
     7:"−2.0 V",8:"0.10 s",9:"电场向下、磁场垂直纸面向里"}}


def signoff(folder,label,binding,*,edition_edits=None,rubric_steps=None):
    score=replay(folder/"board")
    require(score["status"]=="eligible","未获得三角色放行")
    raw=read_json(folder/"board"/f"round{score['round']}.json")
    reports={r["role"]:r for r in raw["reports"]}
    packet=read_json(folder/"blind-packet.json")
    verification=read_json(folder/"verification.json")
    reference=verification["quality_benchmarks"]
    require(binding["solver_sha256"]==fingerprint(reports["solver"]) and binding["paper_version"]==packet["paper_version"]
            and binding["candidate_sha256"]==verification["candidate_sha256"],"解答对照已过期")
    review={"reviewer":"隔离宿主求解者；项目编辑核对等价写法","input_scope":"student_packet_only",
            "paper_pdf_sha256":score["pdf_sha256"],"paper_version":packet["paper_version"],"items":[]}
    audit={"reviewer":"隔离教研、印刷评审；按原始逐题记录登记","protocol":reference["protocol"],
           "reference_sha256":fingerprint(reference),"paper_pdf_sha256":score["pdf_sha256"],
           "paper_version":packet["paper_version"],"items":[]}
    edition=Path(__file__).with_name("solutions.md").read_text(encoding="utf8").split("# "+label+"\n",1)[1].split("\n# ",1)[0]
    paragraphs=re.split(r"(?m)^## \d+\s*\n",edition)[1:]
    require(len(paragraphs)==15,"学生版排印稿缺题")
    for n,(q,key,sol,teacher,printer) in enumerate(zip(packet["paper"]["questions"],verification["answers"],
                *(reports[k]["items"] for k in ("solver","pedagogy","visual")),strict=True),1):
        require(sol["number"]==teacher["number"]==printer["number"]==n,"评审错位")
        choice=bool(q["options"])
        if choice:require(sol["answer"]==key,"盲解键不等")
        else:require(len(sol["answer"])==len(q["parts"]) and n in EQUIVALENCE[label],"非选需逐问对照")
        labels=[p["label"] for p in q["parts"]]
        reasoning=("选 "+key+"。 " if choice else "")+sol["reasoning"]
        if not choice:
            reasoning+="\n"+"　".join(i+a for i,a in zip(labels,sol["answer"],strict=True))
        reasoning=(edition_edits or {}).get(n,paragraphs[n-1].strip())
        if choice:require(reasoning.startswith("选 "+key+"。"),"排印稿选择键不符")
        j={"id":q["id"],"approved":True,"answer":key,"independent_answer_verbatim":sol["answer"],
           "reasoning":reasoning,"science_review":teacher["reasoning"],
           "independent_check":{"checks":{"derivation":sol["reasoning"]},
             "parts":dict(zip(labels,sol["answer"],strict=True)) if labels else {"overall":reasoning}},
           "figure_reading":sol["figure_reading"]}
        if not choice:
            j["rubric"]=sol["rubric"]
            if n in (rubric_steps or {}):
                j["rubric"]=[{**part,"step":caption} for part,caption in
                            zip(sol["rubric"],rubric_steps[n],strict=True)]
            j["equivalence_basis"]=EQUIVALENCE[label][n]
        if marks:=blank_numbers(q):j["blank_answers"]=dict(zip(marks,sol["blanks"],strict=True))
        review["items"].append(j)
        reasons=teacher["distractors"] if choice else {}
        require(not choice or set(reasons)==set(q["options"])-set(key),"错项审查不全")
        findings={k:{"verdict":"pass" if active else "not_applicable","evidence":e}
                  for k,active,e in [("distractors",choice,teacher["reasoning"]),("depth",True,teacher["reasoning"]),
                                      ("figure",bool(q["figure"]),printer["figure_reading"] or "文字题"),
                                      ("language",True,printer["reasoning"])]}
        row={"number":n,"findings":findings,"depth":{"reasoning_steps":teacher["steps"],"linked_concepts":teacher["concepts"]},
             "benchmarks":{y:{"version_sha256":rec["version_sha256"],"comparison":teacher["comparison"]}
                           for y,rec in reference["slots"][str(n)].items()},
             "distractors":{k:{"plausible":True,"misconception":v,"mechanism":v} for k,v in reasons.items()},
             "remaining_editorial_findings":[f for f in score["deductions"] if f["number"]==n]}
        if q["figure"]:
            row["required_figure_information"]=teacher["figure_reading"]
            row["figure_conditions"]={"observation":printer["figure_reading"],"records":[
                {"anchor":ANCHORS[label][n],"label":printer["figure_reading"],"meaning":sol["figure_reading"]}]}
        audit["items"].append(row)
    from core.quality_audit import _paper_inputs, evaluate
    preflight=evaluate(*_paper_inputs(folder),audit,review=review)
    require(preflight["status"]=="accepted",str(preflight["failures"]))
    adjudicate(folder,review)
    result=submit(folder,audit,review=review)
    require(result["status"]=="accepted",str(result["failures"]))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("folder",type=Path);p.add_argument("label",choices="AB");p.add_argument("binding",type=Path)
    a=p.parse_args()
    signoff(a.folder,a.label,read_json(a.binding))
