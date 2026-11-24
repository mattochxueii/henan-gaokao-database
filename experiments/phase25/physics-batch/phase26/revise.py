"""Second production pass, limited to positions returned by the scorecard."""
from pathlib import Path
import shutil
import sys

from draw import HERE, cable_bridge, save_figure, plt
from gaokao import digest, read_json
from storage import atomic_json


def revise(label):
    base=HERE/label
    target=base/"round2"
    manuscript=read_json(base/"candidate.json")
    (target/"figures").mkdir(parents=True,exist_ok=True)
    for question in manuscript["questions"]:
        if figure:=question.get("figure"):
            shutil.copyfile(base/figure["path"],target/figure["path"])
    q=manuscript["questions"]
    if label=="A":
        q[0].update(topic="原子跃迁与光电效应",
            stem="一群原子从图示的 5.0 eV 能级向下跃迁，三个能级为 0、2.0、5.0 eV。让所有可能的谱线分别照射逸出功为 2.4 eV 的金属，再换用逸出功为 3.2 eV 的金属。只考虑单光子过程。换用金属后，能产生光电子的谱线数和光电子最大初动能分别怎样变化？",
            options={"A":"由 3 条变为 2 条，减小 0.8 eV","B":"由 2 条变为 1 条，减小 0.8 eV",
                     "C":"由 2 条变为 1 条，增大 0.8 eV","D":"由 2 条变为 2 条，最大初动能不变"},
            design={"model":"跃迁光电阈值","scene":"谱线检测金属","action":"按能差筛选谱线并比较最强光电子","representation":"能级箭头"})
        q[11]["stem"]="电容器充电后断开电源，按图放电。电压记录器始终并联于电容器两端。电阻箱取 100 kΩ 时，电压从 8.00 V 降至 4.00 V、再降至 2.00 V 各用 0.56 s；换为 200 kΩ 后各用 0.84 s。时间常数 τ 等于电容与总放电电阻的乘积；电压降至初值的 1/e 用时 τ，减半用时 τ ln 2。取 ln 2=0.70，忽略电容器自身漏电。"
        q[11]["parts"][0]["text"]="同一档两次计时表明宜固定 ________（填“电压差”或“电压比”）。换档后，电压降至初值 1/e 的时间为 ________ s。"
        q[11]["parts"][1]["text"]="若记录器不分流，200 kΩ 与 100 kΩ 两档的减半时间之比为 ________。要使实测比值更接近它，应选内阻 ________ 的记录器（填“更大”或“更小”）。"
        q[11]["parts"][2]["text"]="由两档数据求得电容为 ________ μF。"
        q[11]["proposed_answer"]["（1）"]="电压比；1.20"
        q[11]["independent_check"]["parts"]["（1）"]="电压比；1.20"
    else:
        q[11]["stem"]="如图，两根等长同规格导线远端短接，每根长 100 m。故障线距近端 x 处碰壳，接触电阻和外壳电阻均忽略。均匀电阻丝的 A 端接故障线近端，B 端接完好线近端。刻度从 A 端的 0 cm 向 B 端的 100 cm 增大。电源接在滑动触头与近端外壳之间，电流计跨接 A、B。平衡时电流计指零；从 A、B 经电缆到故障点的电阻之比，等于电阻丝 A 端至触头与触头至 B 端的阻值之比。"
        q[11]["parts"][1]["text"]="平衡时触头读数为 32.0 cm。沿故障线近端到碰壳点长 x，沿完好线近端绕远端到碰壳点长 ________（用 x 表示，单位 m）。故障点距故障线近端 ________ m。"
        figure=q[11]["figure"]
        fig=cable_bridge(scale_marked=True)
        save_figure(fig,target/figure["path"],subject="physics")
        plt.close(fig)
        figure["sha256"]=digest(target/figure["path"])
    atomic_json(target/"candidate.json", manuscript)


def clarify_atomic_levels():
    old=HERE/"A/round2"
    target=HERE/"A/round3"
    manuscript=read_json(old/"candidate.json")
    question=manuscript["questions"][0]
    question["stem"]=question["stem"].replace(
        "一群原子从图示的 5.0 eV 能级向下跃迁，三个能级为 0、2.0、5.0 eV。",
        "图中三个原子能级为 0、2.0、5.0 eV。一群原子从最高能级向下跃迁。")
    shutil.copytree(old/"figures",target/"figures",dirs_exist_ok=True)
    atomic_json(target/"candidate.json",manuscript)


if __name__=="__main__":
    if sys.argv[1:]==["A3"]:
        clarify_atomic_levels()
    else:
        for label in sys.argv[1:] or ("A","B"):
            revise(label)
