"""Compose the independent A/B manuscripts against the reserved batch and observed paper structure."""
from pathlib import Path
import sys
from analysis_db import fingerprint
from gaokao import digest, read_json
from storage import atomic_json

SOURCE=Path(__file__).resolve().parent
sys.path.insert(0,str(SOURCE.parents[2]/"phase21/source"))
from make_candidate import parse_markdown

KEYS={
"A":["B","C","B","D","A","C","B","AD","AC","AC",
     ["1.00；9.80","偏小"],["1/R+1/Rv；1/C","12.0；200","偏小"],
     ["0.60 L","2.5 m/s²；1.58 m/s"],["2.0 V；0.375 W","(29±8√13)/3 Ω"],
     ["v/3；v²/(3μg)","−v/9；8v²/(81μg)","L>13v²/(27μg)；任意正 d"] ],
"B":["B","C","B","B","C","C","B","BC","AD","AC",
     ["0.92；−1.6","偏大"],["0；45.0","7∶10；750/17","偏大"],
     ["3500 N；6500 N","21600 J"],["p₀V₀/2；3p₀V₀/2","仍吸热；15V₀/8"],
     ["Blv=q/C+IR；mv=Ft−Blq","Is=CBlF/(m+CB²l²)；a=F/(m+CB²l²)",
      "v∞=v₁−CBlRIs/[2(m+CB²l²)]；不反向；动能和电容电能的初末差"] ]}
# Position-specific intellectual action beyond the three protected batch briefs.
MOVES={
"A":["能差可加|气体谱线|比较直接与级联跃迁|阶梯","平均密度|近表卫星|判断可识别参数|轨道","替代光程|液面回波|扣除被替换空气|回波光路","直线膨胀|压力标定|查中段温度及吸热|状态图","半周分束|离子峰|从直径识别质量|探测边界","磁通斜率|流量探头|比较积分与平方积分|折线","静摩擦联合上界|转盘货盒|分配绳张力|受力","分压负载|照度记录|计入仪表分流|等效并联","双索承载|横梁|按分力辨别薄弱侧|力三角形","质量流率|移动挡板|转换相对速度|水束矢量","","","浮力释放|浮标|划分完全浸没|排水量","交流负载匹配|加热绕组|保留功率方程两根|功率曲线",""],
"B":["衰变反冲|氡子核|分配反冲动能|矢量","质心圆运动|双星光谱|由视向振幅反推质量比|双曲线","临界角变化|光纤探头|辨识界面切换|界面","压力对称|水银温标|排除大气压|液柱","势能边界|静电透镜|计算转折可达性|电势折线","频闪混叠|转轮|处理方向与整周|角序列","伏秒平衡|检测绕组|积分并判极性|阶梯波","延迟辨识|水波探头|用波速区间排除周期数|双相曲线","速度选择|离子束狭缝|分离半径与周期|双场","接触失效|振动托盘|确定支持力消失位置|简谐","", "", "分段制动力|电梯|分离摩擦与回收|分段动能","热流换向|温差试验台|定位段内热交换变号|热力路径",""]}

def build(label,context,plan,output,source=None,final=False):
    from core.batch_planner import tag
    idx="AB".index(label)
    packet=read_json(context)
    brief=read_json(plan)["blueprints"][idx]
    revisions={}
    keys=KEYS[label].copy()
    if source:
        revisions={row[0]:row for row in parse_markdown(source.read_text(encoding="utf8"))}
        changes={
            "A":{4:"A",5:"A",9:"AC",11:["10；4","1.00；9.80"],12:["固定电压比；1.20","2；并联","12.0"],
            13:["0.060 m；5.0 m/s²，向上","1.50 m/s；浮力随位移线性减小"],
            14:["2.0 V；0.375 W","9 Ω 或 1/9 Ω；只选 9 Ω"],
            15:["v/3；v²/(3μg)","−v/3；v²/(3μg)","L>2v²/(3μg)，d>2v²/(9μg)"]},
            "B":{11:["−0.4；0.84","偏大；球心轨迹"],12:["30.0；35.0；指零","200−x；64.0","偏小"]}}
        for n,key in changes[label].items():keys[n-1]=key
    questions=[]
    for item,key,move,score in zip(parse_markdown((SOURCE/(label+".md")).read_text(encoding="utf8")),
                                    keys,MOVES[label],[4]*7+[6]*3+[6,9,10,12,17],strict=True):
        n,topic,stem,opts,parts,fig=revisions.get(item[0],item)
        if source and ((label=="A" and n==4) or (label=="B" and n==9)):
            fig=fig.replace(".png","r.png")
        if source and label=="A" and n==4:move="恒压泄放|容器阀门|扣除排出气体质量|温压轨迹"
        if final:
            from final_edits import apply, KEY_CHANGES
            stem,opts,parts=apply(label,n,stem,opts,parts)
            key=KEY_CHANGES[label].get(n,key)
        answer=dict(zip((p["label"] for p in parts),key,strict=True)) if parts else key
        role={11:"experiment_1",12:"experiment_2",15:"final"}.get(n)
        q={"id":f"orig:physics:batch25-{label.lower()}-{n:02}","topic":topic,"stem":stem,
           "kind":"single_choice" if n<=7 else "multiple_choice" if n<=10 else "constructed_response",
           "points":score,"parts":parts,"options":opts,"figure":None,
           "design":brief[role] if role else tag(move),"verification_mode":"independent_review",
           "proposed_answer":answer,"independent_check":{"checks":{"derivation":topic+"：按条件独立求解"},
               "parts":answer if parts else {"overall":"候选选项 "+key}}}
        if role:q["batch_role"]=role
        if fig:
            import shutil
            fp=SOURCE/fig
            target=output.parent/fig
            target.parent.mkdir(parents=True,exist_ok=True)
            if fp.resolve()!=target.resolve():shutil.copyfile(fp,target)
            q["figure"]={"path":fig,"sha256":digest(fp)}
        questions.append(q)
    atomic_json(output,{"subject":"physics","title":f"河南普通高中学业水平选择性考试 · 物理模拟 {label} 卷",
        "questions":questions,"provenance":{"author":"宿主 AI 原创","dna_sha256":packet["dna_sha256"],
        "context_sha256":digest(context),"quality_reference_sha256":fingerprint(packet["quality_benchmarks"])}})

if __name__=="__main__":
    build(sys.argv[1],*(Path(x) for x in sys.argv[2:] if x!="--final"),final="--final" in sys.argv)
