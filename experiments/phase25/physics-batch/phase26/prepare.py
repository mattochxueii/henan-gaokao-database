"""Bind the reviewed round-three questions to the new diagrams and current DNA."""
import argparse
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/"scripts"))
from analysis_db import fingerprint
from gaokao import digest, read_json
from storage import atomic_json
from draw import FIGURES

INSERTIONS={
    "A": {
        11: ("在摆球平衡位置安装窄光束探头", "如图，在摆球平衡位置安装窄光束探头"),
        12: ("用电阻箱放电", "按图示连接用电阻箱放电"),
        13: ("将浮标压至其上表面恰与界面齐平", "如图，将浮标压至其上表面恰与界面齐平"),
        14: ("忽略机械摩擦与自感", "图示为沿转轴观察的线圈和等效电路。忽略机械摩擦与自感"),
        15: ("一块质量为", "如图，一块质量为"),
    },
    "B": {
        11: ("以等时间间隔", "图示为第一组的频闪合成示意。以等时间间隔"),
        12: ("检修台上两根等长同规格导线远端短接", "如图，检修台上两根等长同规格导线远端短接"),
        13: ("质量为 500 kg", "如图，质量为 500 kg"),
        14: ("温差试验台中的一定量单原子理想气体", "图示温差试验台中的一定量单原子理想气体"),
        15: ("光滑水平面上", "如俯视图所示，光滑水平面上"),
    },
}


def prepare(context_path):
    context=read_json(context_path)
    for label in ("A","B"):
        source=HERE.parent/label/"round3"/"candidate.json"
        manuscript=read_json(source)
        manuscript["provenance"].update(
            dna_sha256=context["dna_sha256"],context_sha256=digest(context_path),
            quality_reference_sha256=fingerprint(context["quality_benchmarks"]))
        for n,q in enumerate(manuscript["questions"],1):
            code=f"{label}{n:02}"
            if code not in FIGURES:
                continue
            target=HERE/label/"figures"/(code+".png")
            q["figure"]={"path":"figures/"+target.name,"sha256":digest(target)}
            if n in INSERTIONS[label]:
                old,new=INSERTIONS[label][n]
                if q["stem"].count(old)!=1:
                    raise ValueError(f"{code} 题干锚点与留档不符")
                q["stem"]=q["stem"].replace(old,new)
        atomic_json(HERE/label/"candidate.json",manuscript)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("context",type=Path)
    prepare(parser.parse_args().context)
