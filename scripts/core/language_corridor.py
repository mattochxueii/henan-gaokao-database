"""Deterministic checks on the actual passages, prompts and tagged language answers."""
from collections import Counter
from itertools import groupby
import re
from unicodedata import normalize

from core.editorial_rules import item_text

CHINESE_LENGTHS = {"information": (1600, 2100), "literary": (1600, 2300), "classical": (520, 750)}
ENGLISH_READING_LENGTH = (1380, 1650)
MIN_READING_SENTENCE_WORDS = 17
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002ffff]")
WORD = re.compile(r"[A-Za-z]+(?:[’'-][A-Za-z]+)*")
MARKUP = re.compile(r"</?(?:u|em|strong|sub|sup)>")
FAMILIAR = {
    "日喻": ("生而眇者不识日", "扣盘而得其声"),
    "轮扁斲轮": ("不徐不疾", "得之于手而应于心"),
    "庖丁解牛": ("臣之所好者道也", "以神遇而不以目视"),
    "劝学": ("学不可以已", "青取之于蓝而青于蓝"),
    "师说": ("古之学者必有师", "师者所以传道受业解惑也"),
    "岳阳楼记": ("滕子京谪守巴陵郡", "不以物喜不以己悲"),
    "出师表": ("先帝创业未半", "今天下三分"),
    "陈情表": ("生孩六月慈父见背", "茕茕孑立形影相吊"),
    "桃花源记": ("晋太元中武陵人捕鱼为业", "芳草鲜美落英缤纷"),
}
AUTHOR_ALIASES = {"李太白": "李白", "杜子美": "杜甫", "苏东坡": "苏轼", "陶潜": "陶渊明"}
FORM_TYPES = {
    "finite": {"tense", "passive", "agreement", "modal"},
    "nonfinite": {"infinitive", "ing", "past_participle"},
    "conversion": {"noun", "adjective", "adverb", "verb"},
    "clause": {"relative", "nominal", "adverbial"},
    "determiner": {"article", "other"},
    "preposition": {"collocation", "time_place"},
    "pronoun": {"personal", "reflexive", "relative_reference"},
    "inflection": {"number", "comparative", "superlative"},
    "conjunction": {"coordinating"},
}
IRREGULAR_PARTICIPLE = set("been born built bought brought come cut done drawn drunk eaten felt found frozen given gone grown had heard held hit kept known laid led left lent let lost made meant met paid put read risen run said seen sent set shaken shot shown shut sung slept sold spent spoken stood struck taken taught thought told torn understood worn won written".split())
CLAUSE_WORDS = {
    "relative": set("that who whom whose which where when why".split()),
    "nominal": set("that if whether what whatever who whoever whom whose which when where why how".split()),
    "adverbial": set("after although as because before if once since though till unless until when whenever where whereas while".split()),
}
GRAMMAR_BLANK = re.compile(
    r"(?:\[\s*(5[6-9]|6[0-5])\s*\]|\(\s*(5[6-9]|6[0-5])\s*\)|(?<!\d)(5[6-9]|6[0-5])\s*\.)"
    r"[ \t]*_{2,}[ \t]*(?:\(([-A-Za-z]+)\))?"
)
RECITATION_PART = re.compile(r"(?m)^\s*(?:[（(]([1-3])[）)]|([1-3])[.．、]|([①-③]))\s*")
TIME = re.compile(r"(?<![\d.])(?:[01]?\d|2[0-3])\.[0-5]\d(?![\d.])")
AMERICAN = {"colour": "color", "colours": "colors", "favourite": "favorite", "behaviour": "behavior",
            "centre": "center", "theatre": "theater", "organise": "organize", "travelled": "traveled",
            "travelling": "traveling", "grey": "gray", "programme": "program"}


def bare(text):
    return MARKUP.sub("", normalize("NFKC", text))


def word_count(text):
    return len(WORD.findall(bare(text)))


def mean_sentence_length(text):
    cleaned = bare(text)
    cleaned = re.sub(r"\b(?:Mr|Mrs|Ms|Dr|Prof|St|vs|etc)\.", lambda m: m[0][:-1], cleaned)
    cleaned = re.sub(r"\b(?:[A-Za-z]\.){2,}", lambda m: m[0].replace(".", ""), cleaned)
    cleaned = re.sub(r"(?<=\d)\.(?=\d)", "", cleaned)
    counts = [len(WORD.findall(s)) for s in re.split(r"[.!?]+", cleaned)]
    sentences = [n for n in counts if n]
    return sum(sentences)/len(sentences) if sentences else 0


def primary_single_quote(text, *, chinese):
    depth = 0
    for i, char in enumerate(text):
        if char == "“":
            depth += 1
        elif char == "”":
            depth = max(0, depth - 1)
        elif char == '"':
            if chinese and not depth:
                return True
            depth = 0 if depth else 1
        elif char in "'‘’＇" and not depth:
            before, after = text[i-1:i], text[i+1:i+2]
            if before.isascii() and before.isalpha() and (after.isascii() and after.isalpha()):
                continue  # apostrophe internal to an English word
            if chinese or char == "‘":
                return True
            # Pair a straight opening quote with its closing quote. Apostrophes in
            # contractions, students' and James' are not opening delimiters.
            if not before.isalnum() and after and not after.isspace():
                if char != "’" and re.search(r"['’](?![A-Za-z])", text[i+1:]):
                    return True
    return False


def dotted_time(text):
    value = bare(text)
    if TIME.fullmatch(value.strip().rstrip(".?!")):
        return True
    for match in TIME.finditer(value):
        left = value[max(0, match.start()-45):match.start()]
        right = value[match.end():match.end()+32]
        if re.search(r"[$£€]\s*$", left) or re.match(r"\s*(?:%|°|(?:\d*[kmc]?m|kg|g|liters?|dollars?|yuan)\b)", right, re.I):
            continue
        if (re.search(r"\b(?:at|by|from|until|after|before|between|and|time|starts?|begins?|ends?)\s*$", left, re.I)
                or re.match(r"\s*(?:(?:[ap]\.?m\.?|o'clock)\b|[–—:-]\s*(?:\d|[A-Za-z]))", right, re.I)
                or re.search(r"(?im)^\s*(?:[A-D]\.\s*)?$", left.split("\n")[-1])):
            return True
    return False


def material_slots(questions, section):
    groups = {}
    for n, q in enumerate(questions, 1):
        if q.get("section") == section and q.get("material"):
            groups.setdefault(q["material"], n)
    return groups


def author_name(text):
    name = re.sub(r"[\s·]", "", bare(text))
    return AUTHOR_ALIASES.get(name, name)


def recitation_problems(question):
    sources = question.get("recitation_sources")
    if not isinstance(sources, list) or len(sources) != 3:
        yield "名句默写须按三小题提供作者和篇目"
        return
    authors, titles = set(), set()
    parts = RECITATION_PART.split(question["stem"])
    printed = parts[4::4] if len(parts) == 13 else []
    if len(printed) != 3:
        yield "名句默写题面须有三条编号明确的小题"
    for i, row in enumerate(sources):
        if (not isinstance(row, dict) or not isinstance(row.get("author"), str)
                or not isinstance(row.get("title"), str) or not row["author"].strip() or not row["title"].strip()):
            yield f"名句默写第 {i+1} 小题缺规范作者或篇目"
            continue
        author = author_name(row["author"])
        title = bare(row["title"]).strip().strip("《》")
        if author in authors or title in titles:
            yield f"名句默写第 {i+1} 小题重复作者或篇目"
        authors.add(author)
        titles.add(title)
        if printed:
            heading = printed[i].strip().split("，", 1)[0].removeprefix("在")
            evidence = re.match(r"([^\W\d_]{2,4})《([^》]+)》", heading)
            if evidence and (author_name(evidence[1]), bare(evidence[2])) != (author, title):
                yield f"名句默写第 {i+1} 小题明示的作者、篇目和标注不同"
            elif (work := re.search(r"《([^》]+)》", heading)) and bare(work[1]) != title:
                yield f"名句默写第 {i+1} 小题明示篇目和标注不同"


def familiar_material(material):
    text = bare(material["text"])
    titles = " ".join([material.get("title", ""), material.get("source_title", "")])
    simple = "".join(HAN.findall(text))
    for title, markers in FAMILIAR.items():
        if (f"《{title}》" in titles or material.get("source_title") == title
                or re.search(rf"(?:选自|节选自|摘编自)\s*《{title}》", text)
                or all(marker in simple for marker in markers)):
            return title
    if any(f"《{variant}》" in titles for variant in ("轮扁斫轮", "輪扁斲輪")):
        return "轮扁斲轮"
    return None


def chinese_findings(paper, fields):
    rows, materials = paper["questions"], paper.get("materials", {})
    lengths = {}
    for section, (low, high) in CHINESE_LENGTHS.items():
        groups = material_slots(rows, section)
        count = sum(len(HAN.findall(bare(materials.get(key, {}).get("text", "")))) for key in groups)
        lengths[section] = count
        if not low <= count <= high:
            yield next(iter(groups.values()), 0), "chinese_volume", f"{section}材料 {count} 字，要求 {low}–{high} 字"
        if section == "classical":
            for key, n in groups.items():
                if title := familiar_material(materials[key]):
                    yield n, "chinese_classical", f"文言主材料命中熟文《{title}》"
    for n, section in ((12, "classical"), (15, "poetry")):
        if len(rows) >= n and (rows[n-1].get("section") != section
                              or not re.search(r"不正确的\s*(?:一项|是)", rows[n-1]["stem"])):
            yield n, "chinese_prompt", "该题位须明确选择不正确的一项"
    if len(rows) >= 17:
        for evidence in recitation_problems(rows[16]):
            yield 17, "chinese_recitation", evidence
    for n, text in fields:
        if primary_single_quote(text, chinese=True):
            yield n, "chinese_quote", "一级引文须使用中文双引号"


def compatible_form(category, form, answer, hint, prefix):
    if not isinstance(answer, str):
        return False
    key = answer.strip().lower()
    if not re.fullmatch(r"[a-z]+(?: [a-z]+){0,2}", key):
        return False
    if category == "clause":
        return hint is None and key in CLAUSE_WORDS[form]
    if category == "nonfinite":
        return bool(hint and (
            re.fullmatch(r"to [a-z]+", key) if form == "infinitive"
            else key.endswith("ing") if form == "ing"
            else key.endswith("ed") or key in IRREGULAR_PARTICIPLE))
    if category == "determiner":
        return hint is None and (key in {"a", "an", "the"} if form == "article" else key in {"each", "every", "any", "both", "some", "either", "neither", "all", "no"})
    if category == "preposition":
        return hint is None and key in set("in on at by with for from to into within through over under of as about among between before after across without behind along upon against around".split())
    if category == "conversion":
        if not hint or hint.lower() == key or " " in key:
            return False
        return form != "adverb" or key.endswith(("ly", "ward", "wards", "wise")) or key in {"well", "straight", "fast"}
    if category == "finite":
        if not hint:
            return False
        if form == "passive":
            return (key.split()[-1].endswith("ed") or key.split()[-1] in IRREGULAR_PARTICIPLE) and (
                len(key.split()) > 1 or re.search(r"\b(?:am|is|are|was|were|be|been|being)\s*$", prefix, re.I))
        return not key.startswith("to ") and (not key.endswith("ing") or bool(
            re.match(r"(?:am|is|are|was|were) [a-z]+ing$",key)))
    if category == "inflection":
        return bool(hint and hint.lower() != key)
    if category == "conjunction":
        return hint is None and key in {"and", "but", "or", "nor", "so", "for", "yet"}
    return True


def grammar_findings(rows, materials, answers):
    slots = material_slots(rows, "grammar")
    if len(slots) != 1:
        yield 56, "english_grammar", "第56–65题须绑定同一语法填空原文"
        return
    body = bare(materials[next(iter(slots))]["text"])
    sources = list(GRAMMAR_BLANK.finditer(body))
    numbers = [int(m[1] or m[2] or m[3]) for m in sources]
    if numbers != list(range(56, 66)):
        yield 56, "english_grammar", "语篇中十处编号空位必须按 56–65 排列且不重复"
        return
    used = Counter()
    for number, match in zip(numbers, sources, strict=True):
        tag = rows[number-1].get("grammar_tag", {})
        category, form = (tag.get("category"), tag.get("form")) if isinstance(tag, dict) else (None, None)
        if (not isinstance(category, str) or not isinstance(form, str) or form not in FORM_TYPES.get(category, ())
                or not compatible_form(category, form, answers[number-1], match[4], body[max(0, match.start()-32):match.start()])):
            yield number, "english_grammar", "语法细类未登记，或与原文空位、提示词及候选语形不符"
            continue
        used[(category, form)] += 1
        if used[(category, form)] > 2:
            yield number, "english_grammar", f"{category}.{form} 超过 2 空"
    categories = {c for c, _ in used}
    if len(categories) < 5 or not {"finite", "nonfinite", "conversion", "clause"} <= categories:
        yield 56, "english_grammar", "十空须覆盖至少五类，含谓语、非谓语、词性转换和从句"
    if sum(c == "nonfinite" for c, _ in used) < 2:
        yield 56, "english_grammar", "非谓语至少覆盖两种不同形态"


def english_findings(paper, answers, fields):
    rows, materials = paper["questions"], paper.get("materials", {})
    passages = material_slots(rows, "reading")
    reading = [q.get("material") for q in rows if q.get("section") == "reading"]
    groups = [sum(1 for _ in items) for _,items in groupby(reading)]
    if len(passages) != 4 or groups != [3,4,4,4]:
        yield 21, "english_volume", "第21–35题须依次绑定 A、B、C、D 四篇阅读，各 3、4、4、4 题"
    group = [materials.get(name, {}).get("text", "") for name in passages]
    count = sum(map(word_count, group))
    low, high = ENGLISH_READING_LENGTH
    if not low <= count <= high:
        yield 21, "english_volume", f"A–D 阅读共 {count} 词，要求 {low}–{high} 词"
    for name, (first_number, text) in zip("CD", zip(list(passages.values())[2:], group[2:])):
        length = mean_sentence_length(text)
        if length < MIN_READING_SENTENCE_WORDS:
            yield first_number, "english_sentence", f"{name} 篇平均句长 {length:.1f} 词，下限为 {MIN_READING_SENTENCE_WORDS}"
    if len(rows) >= 65:
        yield from grammar_findings(rows, materials, answers)
    for n, text in fields:
        if dotted_time(text):
            yield n, "english_time", "钟点须用冒号，例如 13:45"
        if primary_single_quote(text, chinese=False):
            yield n, "english_quote", "一级英文引文须使用双引号"


def student_fields(paper):
    """Visible prose with stable question locators. Shared materials are checked once."""
    yield 0, paper.get("title", "")
    seen = set()
    materials = paper.get("materials", {})
    for n, question in enumerate(paper["questions"], 1):
        yield n, item_text(question, options=True)
        name = question.get("material")
        if name in materials and name not in seen:
            material = materials[name]
            for line in (material["title"], material["text"], *(material.get("options") or {}).values()):
                yield n, line
            seen.add(name)


def spelling_warnings(fields):
    for number, text in fields:
        variants = sorted({word for word in WORD.findall(text.casefold()) if word in AMERICAN})
        if variants:
            replacements = "、".join(f"{word} → {AMERICAN[word]}" for word in variants)
            yield {"number": number, "rule": "english_spelling", "evidence": "优先核对常用美式拼写：" + replacements}
