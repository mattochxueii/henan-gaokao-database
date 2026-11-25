"""Exam-design observations attached to the archived National I question versions."""
from collections import Counter

MATH_MODULES = {
    2024: "sets complex vectors trig solids functions trig functions probability functions conics conics functions probability trig conics solids functions sequence",
    2025: "complex sets conics trig functions vectors conics functions solids conics trig functions sequence probability probability sequence solids conics trig",
    2026: "probability vectors sets functions conics functions sequence probability complex solids conics conics trig sequence solids trig probability conics functions",
}
MODULE_NAMES = dict(zip(
    "sets complex vectors trig solids functions probability conics sequence".split(),
    "集合与逻辑 复数 平面向量 三角函数与解三角形 立体几何 函数与导数 统计与概率 解析几何 数列".split(),
    strict=True,
))
MATH_TAIL_DESIGN = {
    8: (
        "把分段函数的全域不等式拆成分支约束，取交集",
        "用公共对数参数表示三个变量，比较交点并排除一种排列",
        "有限均匀样本空间删去一点，先利用对称性再修正期望",
    ),
    11: (
        "将坐标与距离条件转成圆锥曲线关系，再逐项检验局部和整体性质",
        "由两条三角恒等关系约束三角形，分别检查角、边及其量值",
        "由弦长推出圆心到直线的距离；在多个圆间联立距离条件",
    ),
    14: (
        "四轮不放回对阵，用逐轮计数得到至少一次或比赛结果",
        "直接数不同编号不便，改用各号出现的指示量累加",
        "分块部分和给出每三项的总量，再将局部等比约束转成公比上界",
    ),
    18: (
        "从单个函数性质入手，逐步处理受约束的参数关系",
        "由离心率和已知点求标准方程，再把动点条件表示成轨迹方程",
        "椭圆标准方程与焦点弦；求斜率和角的最值。局部有版本争议，仅取明确共性",
    ),
    19: (
        "用新定义把删项后的四项组变成可验证构造，从特例到一般再接概率下界",
        "先求三角函数在区间的极值，再证明覆盖引理并用于相位的全局最值",
        "新定义比较函数值的位移集合，逐步推出集合与函数序关系",
    ),
}
MATH_PROMPTS = {
    8: "同一短题干提供一个能消去变量或利用对称性的结构；留足检查边界、等号或不可行情形的空间。",
    11: "四个命题共享同一模型，分别考查条件、全域性质、反例和数值关系。只套一次公式不应同时判断四项。",
    14: "用短设问要求一次关键转化。证明极值可达或排除遗漏，不靠冗长枚举。",
    18: "先得到标准方程或不变量，再让它驱动第二问的存在性、位置关系或受限极值。",
    19: "第一问产出可用于后续的引理或比较关系；最后一问检验量词、参数范围与边界。",
}
CHINESE_GROUPS = (
    ("信息阅读",1,5,"从对照材料观点到定位论证证据，再跨材料归纳或迁移。",
     ("扩大适用范围","把例证写成唯一原因","将材料外判断当作结论"),
     ("答出明确观点","引用或概括两条相符的材料证据","说明证据与结论的关系")),
    ("文学阅读",6,9,"从情节、语词或叙述角度出发，解释人物、表达效果或结构。",
     ("将某人物态度归给另一人物","把局部情绪扩大为全文主题","叙述技法存在但作用归因错误"),
     ("明示观察角度","结合具体文句或情节","解释审美效果或主题作用")),
    ("文言文",10,14,"断句、词义对比、事实归属、翻译与信息整合。",
     ("混淆主客体","颠倒事件先后或因果","用现代词义解释古义"),
     ("翻译覆盖关键实词和句式","概括须回到原文措施与结果")),
    ("古诗",15,16,"辨识诗句与用典细节，联系语境解释诗意或情感。",
     ("颠倒诗中时空","将诗人态度与典故人物混同"),
     ("写出情感或主旨","结合意象、关键字或用典阐明依据")),
    ("默写",17,17,"按语境补写，保留开放设问的合格备选。",
     (),("逐空核字","开放例句同时满足场景与两句出处")),
)
CHINESE_ACTION = {
    2024:{18:"以指定本体写借喻",19:"成语语境",20:"病句与逻辑",21:"补写",22:"评议词语搭配"},
    2025:{18:"病句与逻辑",19:"句子衔接",20:"词语辨析",21:"剪纸图意和谐音",22:"按文意列研究问题"},
    2026:{18:"找出并改正错字",19:"语句排序",20:"病句与逻辑",21:"热词释义及例句"},
}
ENGLISH_GROUPS = (
    ("听力短对话",1,5,"结合问答判断关系、场景、意图、下一行动或时间",
     ("选背景中出现的地点或动作","把建议当成已经发生的行动","把旧时间误作更新后的时间"),
     ("定位改口、答复和能区分场景的措辞",)),
    ("听力长对话与独白",6,20,"跟踪角色、计划与执行顺序，在较长语篇中归纳态度、理由或规则",
     ("把最初计划当成最后决定","将某人意见归给另一人","把装置或规则的细节误作目的"),
     ("按各场景及说话人分别核对","数值与程序题须回到条件以及先后顺序")),
    ("阅读A",21,23,"信息检索、数值比较、限制条件合取",
     ("使用一项正确数字但漏掉加总","忽略日期或对象限制","将另一个条目的特点移用"),
     ("要求把答案定位到条目、表格或一组条件",)),
    ("阅读B",24,27,"从行为或叙述转折推断态度，再归纳人物变化或主旨",
     ("真实细节不回应设问","把前期动机当最终目的","把他人的经历归给主角"),
     ("证据至少落到具体行为、言语或对照",)),
    ("阅读C、D",28,35,"辨析作者观点、研究目的、方法、结果和结论",
     ("把研究发现写为研究动机","把相关性扩大成因果","用文中词汇拼成未经支持的主张"),
     ("指出证据来自哪一段","区分原文结论与推论")),
    ("七选五",36,40,"用上下指代、段落主题和转折递进双向检验句子",
     ("话题相同但无指代先行词","过渡方向错误","句式合适但上下文时序不通"),
     ("同时解释空格前后的衔接",)),
    ("完形填空",41,55,"沿人物目标和事件转折推断词义，辨别近义词与真实搭配",
     ("单句可配但与人物行动冲突","语义近似但褒贬或强度不合"),
     ("同时核对语法、搭配和事件走向",)),
    ("语法填空",56,65,"先判句子成分，再核对时态、语态或派生形式",
     (),("区分提示词的语根与句中语法角色","列出确有句法依据的可接受变体")),
    ("应用文",66,66,"明确对象与交际目的，逐条完成任务",
     (),("对象、目的、要点覆盖","语体得体","衔接与表达准确")),
    ("读后续写",67,67,"首段推进矛盾，段间接上给定第二段首句，再收束人物变化",
     (),("两段首句衔接","人物与原文设定一致","事件因果与细节可追踪","语言连贯")),
)


def question_ref(paper, n):
    q = next((q for q in paper["questions"] if q["number"] == n), None)
    if q is None:
        return None
    return {"number":n,"id":q.get("occurrence_id",q["id"]),
            "sha256":q["version_sha256"],"practice_eligible":q["usable_for_practice"]}


def authoring_guidance(subject, papers):
    years = {p["year"]:p for p in papers if p["series_id"]=="cn-new-gaokao-1"
             and p["exam_kind"]=="official_exam" and 2024 <= p["year"] <= 2026}
    if not years:
        return {}
    scope = "近三年真实正文的编辑归纳；干扰项方法和评分颗粒供原创设计，缺少官方评分时仅为项目建议。"
    if subject=="math":
        positions=[]
        for n in range(1,20):
            samples=[{"year":year,"module":MODULE_NAMES[MATH_MODULES[year].split()[n-1]],**question_ref(p,n)}
                     for year,p in sorted(years.items())]
            counts=Counter(x["module"] for x in samples if x["practice_eligible"])
            item={"number":n,"samples":samples,"module_counts":dict(counts)}
            if n in MATH_TAIL_DESIGN:
                item.update(structures=[{"year":year,**question_ref(p,n),
                                         "description":MATH_TAIL_DESIGN[n][year-2024]}
                                        for year,p in sorted(years.items())],
                            design_guidance=MATH_PROMPTS[n])
            positions.append(item)
        return {"scope":scope,"position_rotation":positions,
                "sections":{"single_choice":[1,8],"multiple_choice":[9,11],"fill_in":[12,14],"constructed_response":[15,19]},
                "workload_note":"8、11、14 是题型收尾的对照样本。模块与具体题号是历史观察，不能作为下一届排位规则。"}
    source = CHINESE_GROUPS if subject=="chinese" else ENGLISH_GROUPS
    groups=[]
    for group,start,end,ask,errors,rubric in source:
        examples=[{"year":year,"items":[x for n in range(start,end+1) if (x:=question_ref(p,n))]}
                  for year,p in sorted(years.items())]
        groups.append({"group":group,"position_range":[start,end],"typical_prompt":ask,
                       "distractor_patterns":list(errors),"scoring_components":list(rubric),"evidence":examples})
    if subject=="chinese":
        language_examples=[{"year":year,"items":[question_ref(p,n) for n in range(18,len(p["questions"]))]}
                           for year,p in sorted(years.items())]
        groups.append({"group":"语言文字运用","position_range":[18,22],
                       "typical_prompt":"依据上下文改正、重排、补写或解释。图文题指明视觉细节到寓意的联系。",
                       "distractor_patterns":["只看单句顺畅度而忽略全段衔接","将熟悉义项代入不匹配的语境"],
                       "scoring_components":["指出具体语义或表达问题","给出保持原意的改写",
                                             "根据要求说明语境依据或给出可检验例句"],
                       "evidence":language_examples})
        groups.append({"group":"写作","typical_prompt":"明确材料中的论题，形成可用论据检验的立场",
                       "scoring_components":["回应材料的问题","提出并论证立场","例证与论点有实质联系","表达与结构完整"],
                       "evidence":[{"year":year,"items":[question_ref(p,len(p["questions"]))]} for year,p in sorted(years.items())]})
        evolution=[{"year":year,"item":question_ref(years[year],n),"action":action}
                   for year,actions in CHINESE_ACTION.items() if year in years for n,action in actions.items()]
    else:
        evolution=[{"year":year,"item":question_ref(years[year],21),"action":action}
                   for year,action in {2024:"活动招募与时间地点筛选",2025:"用交通排放图合计两类份额",
                                       2026:"按场馆规定与活动日期定位信息"}.items() if year in years]
    return {"scope":scope,"groups":groups,"evolution":evolution}
