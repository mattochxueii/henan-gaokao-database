"""Prepare reproducible Stage 24 candidates from the existing sources and review deltas."""
import argparse
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[2]
sys.path[:0] = [str(ROOT / "scripts"), str(SOURCE.parents[1] / "phase21/source")]
from analysis_db import fingerprint
from gaokao import digest, read_json
from make_candidate import parse_markdown
from storage import atomic_json

PHYSICS_TEXT = {
    3: (r"速度变化如图。", r"速度随时间线性变化，如图。两试验初速均为 6.0 m/s，2.0 s 末甲、乙的速度分别为 4.0、2.0 m/s。"),
    5: (r"图中纸面外、内的磁场强度大小均为", r"如图，左、右磁区的磁场分别垂直纸面向外、向内，大小均为"),
    6: (r"时刻 \(t\) 的光强与其初始光强之比。", r"时刻 \(t\) 的光强与其初始光强之比。2.0 s 时甲、乙的归一化光强分别为 0.50、0.25。"),
    8: (r"拍摄间隔为 10 ms。", r"拍摄间隔为 10 ms，相邻节点间距为 0.40 m。"),
    10: (r"空气间隙如图。", r"两电容器并联，可动支路初始间距为 \(d\)，固定支路间距为 \(2d\)，连接线 a 位于两支路的上极板之间，如图。"),
    11: (r"遮光片很窄，", r"P、Q 相距 0.40 m。图 2 中，当 \(x^2=2.0\times10^{-3}\ \mathrm{m^2}\)、\(8.0\times10^{-3}\ \mathrm{m^2}\) 时，\(v_Q^2\) 分别为 \(0.50\ \mathrm{m^2/s^2}\)、\(3.50\ \mathrm{m^2/s^2}\)。遮光片很窄，"),
    12: (r"改变电流，待阻值稳定后读数，", r"以可调直流电源改变电流，待阻值稳定后读数，"),
    13: (r"板间距为 \(h\)。", r"板间距为 \(h\)，偏转板长为 \(L\)，偏转板右端到荧光屏的水平距离也为 \(L\)。"),
    15: (r"图中有短斜线标记的区段粗糙，", r"如图，O 至 P 段粗糙，长度为 \(d\)，"),
}
CHEMISTRY_TEXT = {
    3: (r"滴定前后滴定管读数如图。", r"滴定前后的凹液面读数分别为 3.10 mL、20.40 mL，如图。"),
    8: (r"各状态的相对焓如图。", r"如图，反应物、过渡态Ⅰ、中间体、过渡态Ⅱ、产物的相对焓，甲依次为 0、24、−24、18、−18，乙依次为 0、33、−12、25、−18，单位均为 \(\mathrm{kJ\cdot mol^{-1}}\)。"),
    10: (r"交叉点横坐标如图", r"两处相邻曲线交点的横坐标分别为 pH 4.0 和 pH 8.0"),
    11: (r"坐标均以 \(a\) 为单位", r"坐标均以 \(a\) 为单位，图示四层的高度分别为 \(0,0.25,0.50,0.75\)"),
    12: (r"质量随温度的变化如图。", r"热重曲线如图，A、B、C、D 四个平台对应的相对质量依次为 100.0%、87.7%、68.5%、38.4%。"),
    13: (r"阿司匹林分子中碳的标记位置如图。",
         r"阿司匹林乙酰基的羰基碳用 \({}^{13}\mathrm{C}\) 标记，结构如图。"),
    14: (r"忽略体积变化及配合物。", r"用硝酸维持溶液为酸性，避免金属离子水解；控制总体积基本不变。"),
    17: (r"见图。", r"如图，\(T_1\) 下二氧化碳转化率为 \(0.75\)、甲烷选择性为 \(2/3\)，\(T_2\) 下分别为 \(0.80,0.50\)。"),
    16: (r"数据如图。", r"未加 \(\mathrm{MnO_2}\) 时原样、空白的滴定体积为 26.00、14.00 mL；接触 \(\mathrm{MnO_2}\) 时分别为 20.00、14.00 mL，如图。"),
}
BIO_ANSWERS = [
    "B","C","A","C","B","D","A","C","B","D","A","C","B","A","D","A",
    ["19；16", "气孔导度变小，CO₂进入叶片受限，降低碳同化", "不能；同叶龄取样，统一测定温度、底物和酶量，测碳固定酶活性"],
    ["肾上腺接受的神经信号", "C、D；补加激素C使淋巴细胞增殖由98降至71，提示激素可介导", "等量淋巴细胞分别加激素C和等量溶剂；相对增殖指标"],
    ["17%；15", "次生演替；在各水文带随机选取多个样方", "同一水位带一组去除本地草、一组假处理，比较入侵草盖度变化"],
    ["AaBb；aabb；白花需要aa、红花需要bb，9:3:3少一个白花纯合型且白花未见bb", "1/9", "3:1:3；aabb不能成株"],
    ["P、R；分别向片段内部延伸", "甲；0.8+0.3=1.1 kb", "导入同骨架空载体的叶片细胞；同条件下的荧光信号"],
]
ANSWERS = {
    "physics": {1:"A",2:"B",4:"C",7:"C",
                14:["v>qBL/m", "2√3L；4πm/(3qB)", "qBL/m<v<2qBL/m"]},
    "chemistry": {
        6:"C", 15:["2LiFePO₄+H₂O₂+2H⁺→2FePO₄+2Li⁺+2H₂O；0.500 mol","5.5；Al(OH)₄⁻",
                   "Mg(OH)₂；避免铝渣在第二段碱性条件下重溶并混入含镁流程","32.19 g"],
        16:["玻璃棒；由蓝色变为无色；H₂O₂+2I⁻+2H⁺→I₂+2H₂O；I₂+2S₂O₃²⁻→2I⁻+S₄O₆²⁻",
            "0.0120 mol/L；0.0600 mmol","6.00×10^-4 mol/(L·min)","不能；继续分解H₂O₂使耗量变小，氧化I⁻使耗量变大"],
    },
}

def substitute(stem, before, after):
    if before not in stem:
        raise ValueError("无法定位修订原文：" + before)
    return stem.replace(before, after, 1)


def draft_biology(questions):
    questions[0]["stem"] = questions[0]["stem"].replace(
        "ATP 不透过膜，在测定条件下腔内无产酸反应。", ""
    )
    for n, options, prompt in (
        (3, ("6","16","4","5"), "由图可知，外液 X 浓度为 16 时甲的摄取初速为"),
        (10, ("70%","76%","36%","72%"), "由图可知，加入 M 且有外加 ABA 时的萌发率为"),
    ):
        q = questions[n-1]
        q["options"] = dict(zip("ABCD", options, strict=True))
        q["stem"] = q["stem"].split("下列")[0] + prompt
        q["proposed_answer"] = "A"
    q = questions[19]
    q["stem"] = r"两对等位基因独立遗传，所有合子均存活。\(A\_B\_\) 为紫花，\(A\_bb\) 为红花，\(aa\) 为白花。用一株 \(AaBb\) 自交。"
    prompt = ["紫花亲本产生的配子类型有 ________ 种。",
              "存活子代紫、红、白花比例为 ________。",
              "子代中白花所占比例为 ________。"]
    for part, text in zip(q["parts"], prompt,strict=True):
        part["text"] = text
    q["proposed_answer"] = dict(zip((p["label"] for p in q["parts"]),
                                    ["4","9:3:4","1/4"],strict=True))


def build(subject, context_path, output, draft):
    context = read_json(context_path)
    previous = SOURCE.parents[1] / "phase22/source"
    if subject == "biology":
        source = SOURCE / "biology.md"
        spec = {"single":16,"scores":[3]*16+[10,11,10,10,11],"answers":BIO_ANSWERS}
        edits = {}
    else:
        source = previous / (subject + ".md")
        spec = read_json(previous / "author-keys.json")[subject]
        edits = {r[0]:r for r in parse_markdown((SOURCE / (subject+"-revisions.md")).read_text(encoding="utf-8"))}
    questions = []
    for original, points, key in zip(parse_markdown(source.read_text(encoding="utf-8"), retain_paragraphs=True),
                                     spec["scores"], spec["answers"],strict=True):
        n, topic, stem, options, parts, fig = edits.get(original[0], original)
        key = ANSWERS.get(subject,{}).get(n,key)
        if subject == "physics":
            if n in PHYSICS_TEXT:
                stem = substitute(stem, *PHYSICS_TEXT[n])
            if n == 10:
                stem = stem.replace("将图中可动极板缓慢移至虚线位置",r"将可动极板缓慢移至虚线处，间距从 \(d\) 变为 \(2d\)")
            if n == 12:
                stem += r"图 2 的纵截距为 \(10.0\ \mathrm{k\Omega}^{-1}\)，\(I^2=100\ \mathrm{mA}^2\) 时纵坐标为 \(8.0\ \mathrm{k\Omega}^{-1}\)。"
        if subject == "chemistry":
            if n in CHEMISTRY_TEXT:
                stem = substitute(stem, *CHEMISTRY_TEXT[n])
            if n == 14:
                stem = substitute(stem, "理论平衡关系。", r"理论平衡关系。银、铅两条线分别满足 \(pAg=10-pCl\)、\(pPb=5-2pCl\)。")
            if n == 16:
                parts[0]["text"] = "重力过滤时，用于引流的玻璃仪器是 ________。滴定接近终点时加入淀粉溶液，终点的颜色变化为 ________。" + parts[0]["text"]
        if parts:
            key = dict(zip((p["label"] for p in parts),key,strict=True))
        questions.append({
            "id":f"orig:{subject}:phase{24 if subject=='biology' else 22}-q{n:02d}", "topic":topic,
            "kind":"single_choice" if n<=spec["single"] else "multiple_choice" if options else "constructed_response",
            "points":points,"stem":stem,"options":options,"parts":parts,
            "figure":{"path":fig,"sha256":digest(output.parent/fig)} if fig else None,
            "verification_mode":"independent_review", "proposed_answer":key,
        })
    if draft:
        if subject != "biology":
            raise ValueError("只生成生物学编辑初稿")
        draft_biology(questions)
    for q in questions:
        key = q["proposed_answer"]
        q["independent_check"]={"checks":{"derivation":"候选先按题设核对，保留关键结论供学生页重解比对。"},
                                "parts": key if q["parts"] else {"overall": f"命题预选 {key}。"}}
    titles={"physics":"河南新高考物理模拟试卷","chemistry":"河南新高考化学模拟试卷",
            "biology":"河南新高考生物学标杆模拟卷"}
    atomic_json(output,{"subject":subject,"title":titles[subject],"provenance":{
        "author":"Work 宿主 AI","revision":"phase24-draft" if draft else "phase24-revised",
        "dna_sha256":context["dna_sha256"],"context_sha256":digest(context_path),
        "quality_reference_sha256":fingerprint(context["quality_benchmarks"]),
    },"questions":questions})


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("subject", choices=("physics","chemistry","biology"))
    p.add_argument("context",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--draft",action="store_true")
    a=p.parse_args()
    build(a.subject,a.context,a.output,a.draft)
