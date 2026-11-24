"""After an editor reconciles the NEW solver responses, adapt only the NEW reports."""
import argparse
import importlib.util
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/"scripts"))
import bootstrap  # noqa: F401 — project-bundled PDF dependencies
from gaokao import digest, read_json, require
from core.review_board import replay
from analysis_db import fingerprint

spec=importlib.util.spec_from_file_location("phase25_editor", HERE.parent/"source/signoff.py")
previous=importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
ADDED_ANCHORS={
    "A":{11:"悬点到球顶的距离 L",12:"电压记录器始终并联于电容器两端",
         13:"上表面恰与界面齐平",14:"轴匀速转动",15:"起初板左端距墙 d"},
    "B":{11:"0、4.8、9.2、13.2、16.8 cm",12:"两根等长同规格导线远端短接",
         13:"接下来的 2.0 m 内匀减速至静止",14:"B→C 在 p–V 图上为直线",15:"左端跨接电容器 C"}}
EDITS={
    "A":{
        1:r"选 B。三条跃迁发出的光子能量分别为 2.0、3.0、5.0 eV。逸出功为 2.4 eV 时，3.0 eV 和 5.0 eV 谱线可使金属发射光电子；逸出功升为 3.2 eV 后，只剩 5.0 eV 谱线。最大初动能均由能量最高的光子决定，由 \(E_k=h\nu-W\) 得它从 2.6 eV 降至 1.8 eV，减小 0.8 eV。",
        12:r"每次电压减半所用时间相同，依次下降的电压却是 4.00 V、2.00 V，故宜固定电压比。两档时间常数分别为 \(\tau_1=0.56/0.70=0.80\) s、\(\tau_2=0.84/0.70=1.20\) s。无分流时总放电电阻随电阻箱由一倍增至两倍，两档减半时间之比为 2。记录器与电阻箱并联，换用更大内阻可减弱分流。由 \(1/\tau=(1/R+1/R_v)/C\)，两档相减消去记录器电导，得 \(C=(1/100000-1/200000)/(1/0.80-1/1.20)=12\) μF。"},
    "B":{
        12:r"电流计在 30.0 cm 和 35.0 cm 两处偏向相反，应在这两个刻度之间细调，直到指零。刻度自 A 向 B 增大，触头读数 32.0 cm 表示两段电阻丝长度分别为 32.0 cm、68.0 cm。设导线单位长度电阻为 k，从 A 经故障线直达碰壳点的路径长 x，从 B 经远端返回的路径长 \(100+(100-x)=200-x\)，长度以 m 计。由平衡条件 \(x/(200-x)=32/68\)，得 \(x=64.0\) m。若完好端额外串入电阻 r，A 端至触头的长度占比变为 \(kx/(200k+r)\)，小于理想值 \(x/200\)，故按理想关系反算的故障距离偏小。"}}
RUBRIC_STEPS={"B":{12:["确定调节下限 30.0 cm","确定调节上限 35.0 cm","调至电流计指零",
                     "写出从 B 经远端到碰壳点的路径长度","由 A、B 两侧电阻比求得故障距离",
                     "根据完好端额外串联电阻判断测距结果偏小"]}}


def finalize(folder,label,binding):
    score=replay(folder/"board")
    require(score["status"]=="eligible","本版尚未取得三角色评审放行")
    require(digest(folder/"paper.pdf")==score["pdf_sha256"],"本版学生 PDF 与评分委员会所读字节不符")
    packet=read_json(folder/"blind-packet.json")
    reports=read_json(folder/"board"/f"round{score['round']}.json")["reports"]
    for item in packet["paper"]["questions"]:
        if not (figure:=item.get("figure")):
            continue
        require(digest(folder/figure["path"])==figure["sha256"],"本版题图与送审版不符")
        n=item["order"]
        for report in reports:
            row=report["items"][n-1]
            require(row["number"]==n and bool(str(row.get("figure_reading") or "").strip()),
                    f"{label}{n} 缺少本版角色对实际题图的观察")
    record=read_json(binding)
    solver=next(r for r in reports if r["role"]=="solver")
    require(record["solver_sha256"]==fingerprint(solver),"本次盲解对照已过期")
    actual=read_json(folder/"verification.json")["answers"]
    require(len(record["comparisons"])==len(actual),"等价核对记录缺题")
    for row,answer,item in zip(record["comparisons"],actual,solver["items"],strict=True):
        require(row["candidate"]==answer and row["independent"]==item["answer"] and
                row["number"]==item["number"],"核对记录与当前原始答卷不符")
        if isinstance(answer,dict):
            require(len(row["part_checks"])==len(answer),"缺每小问的等价校核")
            previous.EQUIVALENCE[label][item["number"]]="；".join(row["part_checks"])
    previous.ANCHORS[label].update(ADDED_ANCHORS[label])
    previous.signoff(folder,label,record,edition_edits=EDITS[label],rubric_steps=RUBRIC_STEPS.get(label))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("folder",type=Path);p.add_argument("label",choices=["A","B"])
    p.add_argument("binding",type=Path,help="编辑依据当前答卷逐问核对后写出的新对照记录")
    args=p.parse_args()
    finalize(args.folder,args.label,args.binding)
