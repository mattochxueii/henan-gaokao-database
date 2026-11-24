"""Select dated exam rules and check the instructions visible to students."""
from decimal import Decimal, ROUND_HALF_UP
import re
from unicodedata import normalize

from gaokao import read_json, require

TABLE = "data/exam-policy.json"
NATIONAL_SERIES = "cn-new-gaokao-1"
PHYSICS_SERIES = "cn-ha-physics-selective"


def resolve(root, subject, year, region, series):
    require(type(year) is int and 1977 <= year <= 2200 and region and series, "需要明确的考试年份、地区和卷系")
    table = read_json(root / TABLE)
    require(table["schema_version"] == 1, "未知考制政策表版本")
    rules = {}
    for record in table["rules"]:
        if (record["subject"] != subject
                or record.get("region", region) != region
                or series not in record.get("series", [series])
                or not record.get("from_year", 1977) <= year <= record.get("through_year", 2200)):
            continue
        kind = record["kind"]
        require(kind not in rules, f"考制规则生效范围重叠：{kind}")
        rules[kind] = record
    return {"schema_version": table["schema_version"], "subject": subject, "year": year,
            "region": region, "series": series, "rules": rules}


def parameters(snapshot, kind):
    return (snapshot or {}).get("rules", {}).get(kind, {}).get("parameters", {})


def guess_snapshot(root, subject, title, *, region="河南", series=None):
    """Only for old review artifacts that predate the explicit year field."""
    match = re.search(r"(?<!\d)(20\d{2})\s*年", title)
    if match:
        series = series or (PHYSICS_SERIES if subject == "physics" else NATIONAL_SERIES)
        return resolve(root, subject, int(match[1]), region, series)
    return None


def english_score(snapshot, written, listening=None):
    rule = parameters(snapshot, "english_score")
    require(rule, "指定地区与年份没有外语计分规则")
    written = Decimal(str(written))
    require(written.is_finite() and 0 <= written <= rule["written_points"], "笔试分数超出范围")
    if listening is not None:
        listening = Decimal(str(listening))
        require(listening.is_finite() and 0 <= listening <= rule["listening_points"], "听力分数超出范围")
    if rule["method"] == "written_conversion":
        require(rule["rounding"] == "half_up", "未知笔试取整方式")
        return int((written * Decimal(rule["written_multiplier"])).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    require(rule["method"] == "listening_plus_written" and listening is not None, "该年份须同时提供笔试和听力原始分")
    return float(written + listening)


def listening_notes(snapshot, *, invigilator=False):
    notes = {}
    for index, section in enumerate(parameters(snapshot, "listening").get("sections", [])):
        name = ("第一节", "第二节")[index]
        repeats = {1: "一", 2: "两"}[section["repeats"]]
        length = section["recordings"]
        form = {"short_dialogues": "短对话", "dialogues_or_monologues": "长对话或独白"}[section["scope"]]
        before = section["read_seconds_per_item"]
        after = section["answer_seconds_per_item"]
        if before:
            timing = f"播放前每小题留{before}秒读题，播放完毕后每小题留{after}秒作答。"
        else:
            timing = f"每段播放完毕后留{after}秒作答并阅读下一小题。"
        instruction = f"{name}　{'监考：' if invigilator else ''}共{length}段{form}，每段录音播放{repeats}遍。{timing}"
        notes[section["first_number"]] = instruction
    return notes


def student_instructions(snapshot):
    score = parameters(snapshot, "english_score").get("header")
    multi = parameters(snapshot, "multiple_choice").get("instruction")
    return [x for x in (score, *listening_notes(snapshot).values(), multi) if x]


def compact(text):
    return re.sub(r"\s+", "", normalize("NFKC", text)).casefold()


SCALE = re.compile(r"(?:×|\*|\\times|乘(?:以)?|(?<![a-z])x)1[.·]25(?!\d)|(?<!\d)1[.·]25倍")
WRITTEN_ONLY = re.compile(r"听力(?:部分|成绩|分值|分数|得分)*(?:不(?:再)?计(?:入|算)|单列)"
                          r"|(?:仅|只)(?:将|以|计入)?笔试.{0,18}(?:计入|计分|成绩)"
                          r"|(?:excluding|without)(?:the)?listening(?:score|marks)")
COMINGLED = re.compile(r"听力(?:成绩|原始分|分值)?(?:与|和|加上|\+)(?:笔试|written)"
                        r"|(?:两项原始分|听力成绩).{0,16}(?:合计150分|直接计入.{0,6}(?:总分|总成绩))")
# Explicit printed listening directions only. Ordinary dialogue such as "I read it once" is unaffected.
REPEATS = re.compile(
    r"(?:每段(?:录音|材料|对话或独白|对话|独白)?(?:只|仅|仅读|仅读取|只读|播放|朗读|读|播|听){1,3}"
    r"|(?:只|仅|可)?(?:播放|朗读|听|仅读|只读)?)"
    r"([一两二12])(?:遍|次)(?![万千百十分])"
)
REPEAT_ANCHOR = re.compile(r"每段|(?:录音|短对话|长对话|对话|材料|独白).{0,10}(?:播|读)"
                           r"|(?:仅读|只读|播放|朗读|播音|听力)")
ENGLISH_REPEATS = re.compile(
    r"(?:each|every|the)(?:short|long)?(?:recording|dialogue|conversation|monologue|item)"
    r"(?:willbe|is|are)?(?:played|read)(?:only)?(once|twice)"
)


def conflicts(snapshot, fields):
    """Read question text and instructions. An explicit contradiction is a fatal issue."""
    for number, raw in fields:
        text = compact(raw)
        score = parameters(snapshot, "english_score")
        if score.get("method") == "listening_plus_written" and (SCALE.search(text) or WRITTEN_ONLY.search(text)):
            yield number, "听力与笔试已合计计入，题面出现笔试折算或听力单列旧制"
        if score.get("method") == "written_conversion" and COMINGLED.search(text):
            yield number, "本年度河南外语只以折算笔试分计入，题面出现含听力合计计入的说明"
        sections = parameters(snapshot, "listening").get("sections", []) if number <= 20 else []
        for match in REPEATS.finditer(text):
            vicinity = text[max(0, match.start() - 26):match.end()]
            if sections and REPEAT_ANCHOR.search(vicinity):
                actual = 1 if match[1] in ("一", "1") else 2
                first = "第一节" in vicinity or "短对话" in vicinity
                second = not first and (number >= 6 or bool(re.search(r"第二节|长对话|独白", vicinity)))
                # A heading, question number or descriptive cue identifies the section. Where no
                # cue exists, compare against the set of legally possible counts for that year.
                expected = ({sections[1]["repeats"]} if second else {sections[0]["repeats"]}
                            if number or first
                            else {entry["repeats"] for entry in sections})
                if actual not in expected:
                    yield number, "听力播放次数与目标年度规则冲突"
                    break
        for match in ENGLISH_REPEATS.finditer(text):
            if sections:
                expected = sections[int(number >= 6 or "section2" in text or "part2" in text)]["repeats"]
                if (1 if match[1] == "once" else 2) != expected:
                    yield number, "英文听力指令的播放次数与目标年度冲突"
                    break
        multi = parameters(snapshot, "multiple_choice")
        if multi and ("全选对" in text or "全部选对" in text or "选对但不全" in text or "部分选对" in text):
            fixed = re.search(r"(?:选对但不全|部分选对)(?:的)?得(\d+)分", text)
            generic = re.search(r"(?:选对但不全|部分选对)(?:的)?得部分分", text)
            full = re.search(r"全(?:部)?选对(?:的)?得(\d+)分", text)
            wrong = re.search(r"(?:有|凡有)选错(?:的)?得(\d+)分", text)
            partial = multi["partial_credit"]
            if ((fixed and (partial == "variable" or int(fixed[1]) != partial))
                    or (generic and partial != "variable")
                    or (full and int(full[1]) != multi["full_credit"])
                    or (wrong and int(wrong[1]) != multi["wrong_credit"])):
                yield number, "多选给分说明与目标卷系冲突"
