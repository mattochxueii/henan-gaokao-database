"""Version-bound descriptions of official National I papers in the plaintext corpus."""
from collections import Counter
import re

SERIES = "cn-new-gaokao-1"

MATH_FINAL = {
    2020: ("椭圆与定点定值", "由离心率与过点确定椭圆，再研究互相垂直的弦和垂足。"),
    2021: ("对数函数与严格界", "由单调性比较函数值，将双变量等式用于倒数和的上下界。"),
    2022: ("两函数最值与等差交点", "先用共同最小值确定参数，再论证同一水平线的三个交点。"),
    2023: ("抛物线轨迹与周长", "先由距离条件得到轨迹，再将三个顶点在曲线上的条件转化为矩形周长下界。"),
    2024: ("可分数列新定义", "从小规模枚举到一般分组构造，再把结构转化为概率下界。"),
    2025: ("三角函数全局极值", "先求给定区间极值，再证明余弦覆盖引理，最后用引理比较可选相位的全局上界。"),
    2026: ("函数比较集合的新定义", "用集合记录函数值严格增大的位移，再把该关系用于函数性质与序关系推理。"),
}
MATH_TOPICS = {
    "数列": r"数列|递推",
    "导数": r"导数|f\s*['′]|切线",
    "圆锥曲线": r"椭圆|抛物线|双曲线|圆锥曲线",
    "概率统计": r"概率|分布列|数学期望|方差|频率",
}

CHINESE = {
    2020: ("历史地理论述", "叙事散文", "正史传记", "疫情应对与青年担当"),
    2021: ("诗画论述对读", "小说", "编年史", "体育与强弱转化"),
    2022: ("文艺论说", "历史小说", "战国政事", "围棋术语与学习次序"),
    2023: ("科学传播论述", "散文", "史料及评论", "故事的社会和个人作用"),
    2024: ("战略论述", "回忆散文", "史传与评论", "技术条件变化下的答案与提问"),
    2025: ("园艺问答", "小说与创作谈", "史传与辨伪", "文学材料中的发声与家国"),
    2026: ("人物通讯和科研文本", "小说", "政论与史料", "词义理解变化与个人成长"),
}
LANGUAGE_ACTIONS = {
    "语句补写": r"补写|填入恰当的语句",
    "修改语病": r"语病|表述不当|修改.{0,12}画线",
    "解释语言效果": r"表达效果|表达作用|修辞",
    "字形或标点": r"标点|错别字|字形",
    "图文转换": r"图[表形]|图画|剪纸|根据下图|按照示例",
    "衔接或排序": r"衔接|语句排序",
    "词义与例句": r"释义|义项",
    "问句提纲": r"写作提纲|四个问句",
    "语言逻辑论证": r"合逻辑|简要说明理由",
}
# One primary answer mechanism per grammar blank, in the original order.
GRAMMAR = {
    2020: "词形 并列 非谓语 定语从句 谓语 谓语 代词 非谓语 词形 介词",
    2021: "名词性从句 名词数 词形 比较级 非谓语 谓语 并列 非谓语 代词 冠词",
    2022: "非谓语 冠词 谓语 非谓语 谓语 并列 名词数 词形 介词 定语从句",
    2023: "词形 非谓语 并列 非谓语 介词 非谓语 代词 冠词 词形 非谓语",
    2024: "词形 词形 非谓语 词形 谓语 冠词 名词数 介词 定语从句 词形",
    2025: "定语从句 冠词 非谓语 词形 谓语 谓语 介词 词形 并列 词形",
    2026: "非谓语 词形 冠词 谓语 名词数 介词 非谓语 定语从句 非谓语 比较级",
}
ENGLISH = {
    2020: ("实用说明 人物叙事 评论 研究报道", "介绍身边值得尊敬的人", "帮助邻里与分工"),
    2021: ("实用说明 人物叙事 说明 观点论述", "给创刊十周年的校刊投稿", "母亲节惊喜"),
    2022: ("实用说明 观点论述 报道 研究报道", "邀请外教接受节目访谈", "坚持参加越野跑"),
    2023: ("实用说明 人物叙事 观点论述 研究报道", "向外教提出口语分组建议", "写作比赛与师生"),
    2024: ("实用说明 人物叙事 观点论述 研究报道", "向Chris分享公园美术课", "陌生人援助与守诺"),
    2025: ("研究说明 人物叙事 观点论述 研究报道", "就拟增英语报栏目写信给外教说明选择", "家庭成员重建联系"),
    2026: ("实用说明 观点论述 报道 研究报道", "向校报投稿并说明大学生活三事项排序", "雪中救助与回访"),
}
READING_ACTIONS = {
    "主旨或标题": r"\bmain(?:ly)?\b|best title|main idea",
    "词句推断": r"underlined|refer to|\bimply\b|\binfer\b",
    "写作目的": r"\bpurpose\b|why (?:does|did|do) the author",
    "建议或立场": r"\bsuggest\w*\b|\battitude\b|\bopinion\b",
}


def reference(question):
    return {"number":question["number"], "question_id":question["id"], "version_sha256":question["version_sha256"]}


def official_first_profiles(subject, papers):
    result = []
    for paper in sorted(papers, key=lambda p: p["year"]):
        year = paper["year"]
        if paper["series_id"] != SERIES or paper["exam_kind"] != "official_exam" or year not in MATH_FINAL:
            continue
        questions = paper["questions"]
        row = {"year":year, "paper_id":paper["id"], "paper_sha256":paper["content_sha256"],
               "source_url":paper["source"]["url"], "question_count":len(questions),
               "eligible_questions":sum(q["usable_for_practice"] for q in questions)}
        if subject == "math":
            last = questions[-1]
            label, approach = MATH_FINAL[year]
            row["tail"] = {**reference(last), "structure":label, "approach":approach,
                           "explicit_new_structure":year in (2024,2026)}
            row["position_by_topic"] = {
                label:[reference(q) for q in questions if q["usable_for_practice"]
                       and (label in q.get("topic_flags",[]) or re.search(pattern,q["stem"]))]
                for label,pattern in MATH_TOPICS.items()}
        elif subject == "chinese":
            topics = CHINESE[year]
            row["reading"] = []
            for index,num in enumerate((1,6,10)):
                q = questions[num-1]
                material=paper["passages"][q["passage"]]
                row["reading"].append({**reference(q), "genre":topics[index],
                                       "characters":len(re.sub(r"<[^>]+>|\s","",material))})
            row["language_actions"] = {
                action:[reference(q) for q in questions[17:-1] if re.search(pattern,q["stem"])]
                for action,pattern in LANGUAGE_ACTIONS.items()}
            row["essay"] = {**reference(questions[-1]),"theme":topics[-1]}
        else:
            genres, application, continuation = ENGLISH[year]
            row["reading"]=[]
            for index,start in enumerate((21,24,28,32)):
                q=questions[start-21]
                row["reading"].append({**reference(q),"genre":genres.split()[index],
                    "words":len(re.findall(r"[A-Za-z]+(?:[’'-][A-Za-z]+)*",paper["passages"][q["passage"]])),
                    "stem_actions":{a:[reference(x) for x in questions if x.get("passage")==q["passage"]
                                       and re.search(p,x["stem"],re.IGNORECASE)] for a,p in READING_ACTIONS.items()}})
            row["grammar"] = [{**reference(q),"focus":category}
                              for q,category in zip(questions[35:45],GRAMMAR[year].split(),strict=True)]
            row["application"] = {**reference(questions[-2]),"theme":application}
            row["continuation"] = {**reference(questions[-1]),"theme":continuation}
        result.append(row)
    summary = {}
    if subject=="english":
        summary["grammar_counts"]=dict(Counter(q["focus"] for row in result for q in row["grammar"]))
        summary["reading_genres"]=dict(Counter(q["genre"] for row in result for q in row["reading"]))
    if subject=="chinese":
        summary["reading_length_range"]={name:[min(row["reading"][i]["characters"] for row in result),
                                                    max(row["reading"][i]["characters"] for row in result)]
                                         for i,name in enumerate(("信息类","文学类","文言文"))} if result else {}
    return {"series_id":SERIES, "label_version":"phase18-v1", "by_year":result,
            "aggregate":summary,
            "scope":"题位和字数从已入库文本计算；主题、体裁和语法为逐卷编辑标注；设问检出使用表面词规则，可漏检。"}
