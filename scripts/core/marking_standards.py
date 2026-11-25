"""Publication marking conventions for the six-subject study platform."""
import re

from gaokao import require

CHINESE_BANDS = [(20,16),(15,11),(10,6),(5,0)]
PENALTIES = "缺标题扣2分。不足800字，每少50字扣1分。每1个错别字扣1分。"
ENGLISH_BANDS = {15: [(13,15),(10,12),(7,9),(4,6),(1,3)],
                 25: [(21,25),(16,20),(11,15),(6,10),(1,5)]}
LANGUAGE_WEIGHT = 40
ENGLISH_LEVELS = (
    "完成任务，内容充实。用词和句式丰富准确，表达自然，衔接连贯。",
    "完成主要任务，内容较充分。用词和句式较丰富，个别错误不影响理解，衔接清楚。",
    "基本完成任务。用词和句式较简单，部分错误影响流畅度，整体可以理解。",
    "部分完成任务。语言重复或错误较多，衔接薄弱，部分意思难以理解。",
    "完成任务很少。语言错误频繁，难以形成连贯表达。",
)
RANGES = re.compile(r"(\d+)\s*[-–—～~至]\s*(\d+)")
PRINTED_FORMAT = re.compile(r"称呼|署名|落款|结束语|salutation|sign.?off|signature", re.I)
AWARDED = re.compile(r"(?:给|得|计|占)\s*(?:\d+|[一二三])\s*分")
SCIENCE_EQUIVALENCE = "评分参考。物理量的等价单位和准确数值可同样给分。题目规定精度时，以规定的有效数字或小数位数为准。题目未限定形式时，等值分数与小数可同样给分。"
ADH_EQUIVALENCE = "抗利尿激素经垂体释放。答“垂体后叶”或“垂体”均可。"
MATH_EQUIVALENCE = "使用高中课程内的常规通法，论证与计算等价的同样给分。"
DEFENSIVE_VARIANCE = re.compile(r"按\s*(?:\\\(\s*)?(?:\\(?:d|t)?frac\s*\{?1\}?\s*\{?n\}?|1\s*/\s*n)(?:\s*\\\))?\s*作为方差")


def language_template(subject, number, points):
    if subject == "chinese":
        if number == 22:
            bands = " / ".join(f"{a}～{b}" for a,b in CHINESE_BANDS)
            return [f"作文评分。内容、表达、发展各20分。四等区间为{bands}。",
                    "综合判断题意、论证或叙述、篇章结构、语言及发展表现，各维度独立定档。",
                    PENALTIES]
        return {
            9: ["综合评分。7～8分：紧扣人物与语境，举动、心理及衔接自然。5～6分：衔接基本自然，举动与心理较完整。",
                "3～4分：部分承接原文，举动或心理缺失。0～2分：与材料脱节或表达难以理解。",
                "根据完成质量先整体定档。不足60字或超过100字，每相差满10字扣1分，扣至0分为止。"],
            10: ["每个正确断点1分。写出超过三处不给分。"],
            16: ["结合诗句说明艺术手法及其表达效果。合理的不同手法维度可等价给分。"],
            17: ["每空1分。有错字、漏字、添字，该空不给分。不得照抄本卷诗句。"],
        }.get(number, [])
    if subject == "english" and number in (66,67):
        return ["按五档整体评分。综合考查内容完成、语言丰富性与准确性（权重40%）以及连贯与得体。题面预印格式不计分。",
                *(f"第{5-i}档（{lo}～{hi}分） {desc}" for i,((lo,hi),desc) in
                  enumerate(zip(ENGLISH_BANDS[points],ENGLISH_LEVELS,strict=True))),
                "零分：未作答，或内容无法辨认、与任务无关。"]
    return []


def generated_only(subject, number):
    return (subject == "chinese" and number in {9,10,17,22}
            or subject == "english" and number in {66,67})


def math_choice(kind, key, points):
    if kind == "single_choice":
        return f"选对得{points}分，选错或不选得0分。"
    if kind == "multiple_choice" and points == 6:
        require(isinstance(key,str) and len(set(key)) == len(key) and len(key) in (2,3),
                "6分多选题须有2项或3项正解")
        partial = "只选对1项得3分" if len(key)==2 else "只选对1项得2分，只选对2项得4分"
        return f"全部选对得6分，{partial}，有选错或不选得0分。"
    return ""


def science_note(subject, question):
    if subject == "biology" and re.search(r"抗利尿激素.{0,45}释放", question.get("stem","")+" ".join(
            p["text"] for p in question.get("parts",[]))):
        return ADH_EQUIVALENCE
    return ""


def grading_findings(subject, questions, reviews, rendered):
    """Audit old or newly rendered keys. The new renderers do not accept a custom writing rubric."""
    for n,q in enumerate(questions,1):
        row = reviews.get(n,{})
        rub = row.get("rubric",[])
        rules = " ".join(str(r.get("step", "")) for r in rub)
        text = rendered.get(n,"")
        if subject == "chinese" and n == 22 and (rules or text):
            if re.search(r"一等\s*17\s*[–—～-]\s*20", rules+text):
                yield n,"chinese_essay_bands","作文使用17～20，要求20～16／15～11／10～6／5～0"
            elif not set(CHINESE_BANDS) <= {tuple(map(int,p)) for p in RANGES.findall(rules+text)}:
                yield n,"chinese_essay_bands","作文四等区间缺失或分界有误"
        if subject == "chinese" and n in (9,10,16,17,22) and text:
            required = {9:("综合评分","60字","100字","扣"),10:("超过三处不给分",),
                        16:("手法","等价"),17:("错字","漏字","添字","不得照抄"),
                        22:("缺标题扣2分","每少50字扣1分","每1个错别字扣1分")}[n]
            if not all(s in text for s in required):
                yield n,"marking_template","评分参考未完整采用本题的印刷规则"
        if subject == "english" and n in (66,67) and (rules or text):
            total = q["points"]
            explicit = re.search(r"语言.{0,16}权重\s*(\d+)\s*%",text)
            # Old point-by-point schemes supply an upper bound: award all points of mixed rows to language.
            language = sum(r["points"] for r in rub if re.search(r"语言|句法|词汇|语法|拼写|语气|表达",r["step"]))
            weight = int(explicit[1]) if explicit else round(100*language/total)
            if weight < LANGUAGE_WEIGHT:
                yield n,"english_language_weight",f"语言评分权重至多{weight}%，最低{LANGUAGE_WEIGHT}%"
            found = {tuple(sorted(map(int,p))) for p in RANGES.findall(text)}
            if "整体评分" not in text or not set(ENGLISH_BANDS[total]) <= found:
                yield n,"english_writing_bands","写作未采用对应总分的五档整体评分"
            if any(PRINTED_FORMAT.search(r["step"]) and (AWARDED.search(r["step"]) or
                    not re.search(r"不计分|不给分|不赋分",r["step"])) for r in rub):
                yield n,"english_printed_credit","向预印称呼、署名或结束语赋分"
        if subject == "math" and q["kind"]=="single_choice" and "可接受数学等价写法" in text:
            yield n,"math_choice_equivalence","单选评分误印“可接受数学等价写法”"
        if subject == "math" and q["kind"] in ("fill_in","constructed_response"):
            for line in text.splitlines():
                math = re.findall(r"\\\((.*?)\\\)",line)
                if re.search(r"/\s*√",line):
                    yield n,"math_radical","解析使用未有理化的根式分母"
                    break
                if math:
                    candidate = math[-1].split("=")[-1]
                    if re.search(r"/\s*(?:\\sqrt|√)|\\(?:d|t)?frac\s*(?:\{[^{}]*\}|[0-9])\s*\{\s*\\sqrt",candidate):
                        yield n,"math_radical","解析的终式分母含根式："+candidate
                        break
        if subject in {"physics","chemistry","biology"} and text and science_note(subject,q):
            if ADH_EQUIVALENCE not in text:
                yield n,"science_equivalence","抗利尿激素题缺垂体与垂体后叶等价评分说明"
