"""Deterministic preflight checks for a standard paper and its actual artifacts."""
import re
from collections import Counter
from fractions import Fraction
from math import pi, sqrt
from pathlib import Path

from gaokao import read_json, require
from core import marking_standards as marking
from core.editorial_rules import item_text

VERSION = "henan-standard-release-v1"
SUBJECT_COUNTS = {"chinese":22,"math":19,"english":67,"physics":15,"chemistry":18,"biology":21}
SCIENCE = {"physics","chemistry","biology"}
CARD = re.compile(r"(?:请)?(?:按(?:如下格式)?)?在答题卡(?:的)?相应位置作答")
TERMS = ("氧化数","气体活度","伯碳原子","同源体","居群","腐屑","生产者现存量","连锁相位",
         "水平磁力","项目参考评分","候选答","主语域","示文","自行扣扣","监考：",
         "数量投影","项目自拟评分","校核独立核定答案")
WORDS = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
SPEAKER = re.compile(r"^(?:M|W):\s*",re.M)
CIRCLE = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
HEAD = re.compile(r"^#{2,4}\s+(?:第\s*)?(\d+)\s*(?:[.．、（(]|题)",re.M)
HEDGE = re.compile(r"支持|有助于|提供了证据|仍需.{0,20}证据|不能确定")
TOPICS = {
    "periodic":r"元素周期表|元素周期律|同主族|电子排布|价电子排布|原子序数.{0,28}元素",
    "molecular_genetics":r"中心法则|基因表达|转录.{0,40}翻译|mRNA|DNA复制|染色体变异|基因突变|表观遗传",
    "bioengineering":r"载体.{0,30}(?:连接|构建)|双酶切|重组质粒|PCR.{0,30}引物|基因工程|转基因|植物组织培养",
    "ac":r"交变电流|正弦交流|变压器|交流电源",
    "oscillation":r"简谐|振动图|波形|位移.{0,14}周期|机械波.{0,20}波长",
    "induction_rod":r"(?:导体棒|金属棒).{0,130}(?:感应|切割|安培力|磁场)|(?:切割|感应).{0,90}(?:导体棒|金属棒)",
    "projectile_or_circle":r"平抛|抛体|向心力|圆周运动|半周|圆轨道",
}
MATH_TECHNIQUE = re.compile(r"[a-z][a-z0-9_-]{2,63}")
CORE_ENGLISH = frozenset("""the a an and or but at in on with by from to of for about from as is are was were be been
 have has had do does did can could may might must should will would i we you he she it they their them
 this that these those not no yes all some any much many most more less only then when what where while
 if even also often always never usually other another one two three first last here there just very
 each both own your our its my who which such because so how over under up out before after through
 during into just make made get got go went come came take took look see saw know give think say tell
 keep use need want find leave put read write work time day place year people man woman child school
 book home house room part way thing great good bad new old long short little large big high low next
 help start stop end light water city town right left live life group small change different important
 same show mean let try call set well early open close move play answer meet around without still""".split())


def numbered_sections(text):
    headings=list(HEAD.finditer(text))
    return {int(h[1]): text[h.end():(headings[i+1].start() if i+1<len(headings) else len(text))]
            for i,h in enumerate(headings)}


def listening_words(listening):
    # Count numerals/times as spoken tokens, contractions as words, and exclude speaker labels.
    return len(re.findall(r"\b[A-Za-z0-9]+(?:['’:-][A-Za-z0-9]+)*",
                          SPEAKER.sub("", "\n".join(listening.values()))))


def layout_evidence(pdf):
    """Read the actual 25×36 legacy or 20×50 new manuscript grid drawn by ReportLab."""
    if pdf is None or not pdf.is_file():
        return {}
    from pypdf import PdfReader

    marker = False
    # Count independent stroked drawing paths. A valid grid is one path with 21/26 verticals and 2 horizontals.
    counts = Counter()
    for page in PdfReader(pdf).pages:
        content = page.get_contents()
        if content is None:
            continue
        strokes = []
        grid_right_edges = []
        start = None
        for coords, op in content.operations:
            if op == b"m":
                start = tuple(map(float,coords))
            elif op == b"l" and start is not None:
                end = tuple(map(float,coords))
                strokes.append((start,end))
                start = end
            elif op in (b"S",b"s",b"n"):
                vertical = [(a,b) for a,b in strokes if abs(a[0]-b[0])<1e-5 and abs(a[1]-b[1])>4]
                flat = [(a,b) for a,b in strokes if abs(a[1]-b[1])<1e-5 and abs(a[0]-b[0])>400]
                if len(strokes)==len(vertical)+2 and len(vertical) in (21,26) and len(flat)==2:
                    counts[len(vertical)-1]+=1
                    grid_right_edges.append((max(a[0] for a,_ in vertical), min(a[1] for a,_ in flat)))
                strokes = []
                start = None
        if grid_right_edges:
            def locate(text, user_matrix, text_matrix, font, size):
                nonlocal marker
                x, y = text_matrix[4:6]
                # A font subset may split the digits and the CJK suffix into separate operators.
                if re.fullmatch(r"\s*▲?\s*800\s*字?\s*",text) and any(
                    0 <= x-right <= 12 and abs(y-base) <= 5 for right,base in grid_right_edges
                ):
                    marker = True

            page.extract_text(visitor_text=locate)
    return {"essay_grid_cells":sum(width*count for width,count in counts.items()),
            "essay_columns_and_rows":dict(counts),
            "essay_800_mark":marker}


def from_folder(folder, pdf):
    def read(name):
        path=folder/name
        return path.read_text(encoding="utf-8-sig") if path.is_file() else ""
    path = folder/"independent-review.json"
    items = read_json(path).get("items",[]) if path.is_file() else []
    rendered=numbered_sections(read("solutions.md"))
    if not rendered and (candidate:=folder/"raw-ai-candidate.json").is_file():
        rendered={n:"\n".join(q["solution"]["paragraphs"])
                  for n,q in enumerate(read_json(candidate)["questions"],1)}
    return {"student_md":read("paper.md"),"solutions":rendered,"solutions_md":read("solutions.md"),
            "listening_md":read("listening-script.md"),
            "reviews":{i.get("number",n):i for n,i in enumerate(items,1)},
            "student_pdf":pdf,"figure_folder":folder}


def choice_findings(rows, answers, subject):
    # Listening and written single-choice sections have different option alphabets.
    keys=[(n,key) for n,(q,key) in enumerate(zip(rows,answers,strict=True),1)
          if q["kind"]=="single_choice" and isinstance(key,str) and len(key)==1]
    groups=[keys]
    if subject=="english":
        groups=[[r for r in keys if r[0]<=20],[r for r in keys if r[0]>20]]
    for group in groups:
        if not group:
            continue
        total=len(group)
        cap=3 if total in (8,9) else 5 if total in (14,15,16) else total
        for key,count in Counter(key for _,key in group).items():
            if count>cap or count/total>.45:
                yield next(n for n,k in group if k==key),"answer_distribution",f"单选{key}有{count}/{total}题，超过上限"
        for start in range(len(group)-3):
            run=group[start:start+4]
            if len({k for _,k in run})==1 and run[-1][0]-run[0][0]==3:
                yield run[0][0],"answer_streak",f"第{run[0][0]}至{run[-1][0]}题连续选{run[0][1]}"
        if total >= 10:
            observed = {opt for n, _ in group for opt in (rows[n - 1].get("options") or ())}
            alphabet = (
                sorted(observed) if observed
                else (["A", "B", "C"] if subject == "english" and group[0][0] <= 20 else ["A", "B", "C", "D"])
            )
            for opt in alphabet:
                streak_start = None
                streak_len = 0
                for idx, (n, key) in enumerate(group):
                    if key != opt:
                        if streak_len == 0:
                            streak_start = n
                        streak_len += 1
                    else:
                        if streak_len >= 10:
                            yield streak_start, "answer_option_absent_streak", f"第{streak_start}至{group[idx - 1][0]}题连续{streak_len}题缺失选项{opt}"
                            break
                        streak_len = 0
                else:
                    if streak_len >= 10:
                        yield streak_start, "answer_option_absent_streak", f"第{streak_start}至{group[-1][0]}题连续{streak_len}题缺失选项{opt}"
    if subject == "math":
        multi = [
            (n, "".join(key) if isinstance(key, list) else key)
            for n, (q, key) in enumerate(zip(rows, answers, strict=True), 1)
            if q.get("kind") == "multiple_choice" and key
        ]
        if len(multi) >= 3:
            sizes = {len(set(k)) for _, k in multi if isinstance(k, str)}
            if sizes and not ({2, 3} <= sizes):
                yield multi[0][0], "math_multiple_choice_mix", f"数学多选题正解项数均为{sorted(sizes)}项，须同时包含2选与3选"
    if subject != "english":
        sc_with_stem = [(n, q) for n, q in enumerate(rows, 1) if q.get("kind") == "single_choice" and q.get("stem")]
        if len(sc_with_stem) >= 14:
            neg = [
                n for n, q in sc_with_stem
                if re.search(
                    r"错误的|不正确的|不合理的|不符合|不恰当的|有误的|不能(?:达到|实现|用|共存)|不包括|不属于|不成立",
                    q["stem"],
                )
            ]
            if len(neg) < 2:
                yield sc_with_stem[0][0], "choice_prompt_polarity", (
                    f"{len(sc_with_stem)}道单选仅{len(neg)}道逆向设问（错误的/不正确的是），禁止清一色全问“正确的是”"
                )


def chinese_checks(paper, rows, texts, metrics):
    materials=paper["materials"]
    images=set("犬马风月火雁鹤舟柳蝉雪梅猿")
    poem=materials[rows[14]["material"]]["text"].split("【")[0]
    oral=rows[16]["stem"].split("（3）")[-1]
    shared=[i for i in sorted(images) if i in poem and i in oral]
    if shared:
        yield 17,"chinese_imagery","古诗和开放默写重复意象："+ "、".join(shared)
    for n,q in enumerate(rows,1):
        stem=q["stem"]
        if q.get("material") not in materials:
            continue
        chunks=[t.strip() for t in re.split(r"\n\s*\n",materials[q["material"]]["text"]) if t.strip()]
        for match in re.finditer(r"((?:首段?[、和及与，]?末(?:两)?|首|末|第\s*[0-9一二三四五六七八九十]+\s*)段)[^。“”]{0,20}?(?:(一|两|三|\d+)处|中的?|的|原词)“([^”]{1,18})”",stem):
            where,count,word=match.groups()
            indices=[0,-1] if "首" in where and "末" in where else [0] if "首" in where else [-1] if "末" in where else []
            if not indices:
                raw=re.search(r"[0-9一二三四五六七八九十]+",where)[0]
                indices=[int(raw)-1 if raw.isdigit() else "一二三四五六七八九十".find(raw)]
            counts=[chunks[i].count(word) if -len(chunks)<=i<len(chunks) else 0 for i in indices]
            minimum={"一":1,"两":2,"三":3}.get(count, int(count) if count and count.isdigit() else 1)
            if any(x==0 for x in counts) or sum(counts)<minimum:
                yield n,"chinese_paragraph_quote",f"“{word}”在{where}分别出现{counts}次"
    if not any(re.search(r"词语|成语|语病|病句|修改|修辞|标点|衔接|用词|辨析",t)
               for t in texts[17:21]):
        yield 18,"chinese_language_coverage","四道语用题缺词语、病句、修辞、标点或衔接"
    if paper.get("layout_mode")=="practice" and metrics:
        n=metrics["essay_grid_cells"]
        if metrics["essay_columns_and_rows"]!={20:50} or not metrics["essay_800_mark"]:
            yield 22,"chinese_essay_grid",f"实际作文稿纸{n}格，800字标尺{'有' if metrics['essay_800_mark'] else '缺失'}"
    if paper.get("release_rules")==VERSION:
        # The theme identifiers declare the material's main conflict, rather than tagging repeated surface words.
        themes=[v.get("theme_id") for k,v in materials.items() if k in
                {rows[n-1].get("material") for n in (1,6,18,22)}]
        if len(themes)!=4 or any(not t for t in themes) or len(set(themes))!=4:
            yield 1,"chinese_theme_overlap","四组原创材料需登记各自不同的核心冲突主题"


def english_checks(paper, rows, answers, listening):
    words=listening_words(listening)
    if not 1050<=words<=1300:
        yield 1,"english_listening_length",f"有效朗读{words}词，要求1050～1300词"
    materials=paper["materials"]
    gram=materials[rows[55]["material"]]["text"]
    prompts=re.findall(r"\[(5[6-9]|6[0-5])\]\s*_{2,}\s*\(([A-Za-z][A-Za-z '-]*)\)",gram)
    if len(set(prompts)) not in (6,7) or len({n for n,_ in prompts})!=len(prompts):
        yield 56,"english_grammar_prompts",f"有提示词{len(prompts)}空，无提示词{10-len(prompts)}空，要求6～7与3～4"
    reading={}
    for n,q in enumerate(rows,1):
        if q.get("section","").startswith("reading"):
            key=q.get("material")
            reading[key]=reading.get(key,"")+ " "+materials[key]["text"]+" "+q.get("options",{}).get(answers[n-1],"")
    reading_vocab=set(WORDS.findall(" ".join(reading.values()).casefold()))
    for n in range(41,66):
        q=rows[n-1]
        word=q.get("options",{}).get(answers[n-1],"") if n<56 else answers[n-1]
        if isinstance(word,str) and word.casefold() not in CORE_ENGLISH|{"which","between","therefore","whether",
                "although","unless","against","within","without","throughout","among","whose"} and \
                re.fullmatch("[A-Za-z]{5,}",word) and word.casefold() in reading_vocab:
            yield n,"english_cross_item_leak",f"正确实词 {word} 已出现在本卷阅读材料或正确项"
    for key,data in materials.items():
        if data.get("title") in ("C","D") or key in {rows[n]["material"] for n in (27,31)}:
            fraction, variety = reading_register(data["text"])
            if fraction < .11 or variety < .06:
                yield 28 if key==rows[27]["material"] else 32,"english_reading_register",(
                    f"{key}较长非基础词占比{fraction:.1%}，去重后占比{variety:.1%}，下限分别为11%与6%")
    sections={}
    for n,q in enumerate(rows,1):
        section=q["section"]
        material=q.get("material")
        include=(listening.get(material) or materials.get(material,{}).get("text",""))+" "+q["stem"]
        group="reading" if section.startswith("reading") else section
        sections[group]=sections.get(group,"")+" "+include
    for expression in (r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
                       r"\b(?:community (?:garden|volunteer\w*)|volunteer(?:s|ing)?)\b"):
        matches={}
        for part,text in sections.items():
            for token in set(re.findall(expression,text,re.I)):
                key="community volunteer" if "volunteer" in token.casefold() else token.casefold()
                matches.setdefault(key,set()).add(part)
        for token,parts in matches.items():
            if len(parts)>=3:
                yield 1,"english_theme_overlap",f"{token}在{len(parts)}个板块出现（{', '.join(sorted(parts))}）"


def reading_register(text):
    tokens=WORDS.findall(text.casefold())
    noncore=[t for t in tokens if len(t)>=7 and t not in CORE_ENGLISH]
    size=max(len(tokens),1)
    return len(noncore)/size, len(set(noncore))/size


def math_surface_findings(rows, texts):
    interval = re.compile(r"[\[(]\s*([-−+]?\d+(?:\.\d+)?)\s*[,，]\s*([-−+]?\d+(?:\.\d+)?)\s*[\])]")
    for n,(row,text) in enumerate(zip(rows,texts,strict=True),1):
        plain = re.sub(r"\\(?:left|right)(?![A-Za-z])","",text)
        if re.search(r"\[\s*[a-z]\s*[,，][^\]\n]{1,60}\]",plain) and re.search(r"(?:≠\s*∅|\\ne(?:q)?\s*\\(?:emptyset|varnothing))",plain):
            yield n,"math_parameter_interval","含参端点和非空条件须改写为集合描述法"
        if row.get("kind")=="single_choice":
            endpoints = []
            for option in row.get("options",{}).values():
                option = re.sub(r"\\(?:left|right)(?![A-Za-z])|\\[()]", "", option).strip()
                if match := interval.fullmatch(option):
                    endpoints.append(tuple(float(x.replace("−","-")) for x in match.groups()))
            if any(count>=3 for count in Counter(endpoints).values()):
                yield n,"math_interval_options","至少三个选项使用相同的数值端点，作答范围被选项泄露"


_CONTINGENCY_MENTION = re.compile(
    r"(?:得到|如下|下表|制成|整理|列出|补全|填写|给出|绘制)[^。；\n]{0,24}列联表|列联表(?:如下|所示)"
)
_MATH_AI_OPENER = re.compile(
    r"^\s*本题(?:研究|考察|考查|旨在|探讨|讨论|通过|结合|主要|聚焦|围绕|涉及)"
)
_MATH_INTERVAL_SPOILER = re.compile(
    r"(?:取值范围|范围|解集|区间)\s*(?:为|是)\s*[\[(]\s*"
    r"(?:[-−+]?\\?infty|[-−+]?∞|-?\d+(?:\.\d+)?|[a-zA-Z])\s*[,，]\s*"
    r"(?:[-−+]?\\?infty|[-−+]?∞|-?\d+(?:\.\d+)?|[a-zA-Z])\s*[\])]"
    r"[^。？\n]{0,20}(?:其中|则)\s*[a-zA-Z]\s*(?:等于|的值为|的值是|为|=|是)"
)
_MATH_LINE_CIRCLE = re.compile(
    r"(?<![椭])圆(?![柱锥台弧周])[^。；\n]{0,24}(?:方程|切线|弦长|相切|相交|相离|圆心|半径)"
    r"|直线[^。；\n]{0,20}与(?<![椭])圆(?![柱锥台])"
    r"|圆的方程"
    r"|\(\s*x\s*[+-][^)]+\)\s*\^2\s*\+\s*\(\s*y\s*[+-][^)]+\)\s*\^2"
    r"|x\^2\s*\+\s*y\^2\s*[+-]\s*\d*\s*[xy]"
)
_MATH_REVOLUTION_SOLID = re.compile(
    r"外接球|内切球|球面|球体|半球|球心|球的(?:表面积|体积|半径)|圆柱|圆锥|圆台|旋转体"
)


def math_checks(paper, rows, texts):
    def has_progression(question):
        # Compiled subquestions keep labels and content in separate fields.
        parts=question.get("parts",[])
        return len(parts)>=3 and all(
            re.fullmatch(rf"[(（]\s*{n}\s*[)）]",part.get("label","")) and part.get("text","").strip()
            for n,part in enumerate(parts[:3],1))

    if not any(has_progression(question) for question in rows[17:19]):
        yield 18,"math_progression","第18、19题均无第三问递进"
    conics=[name for name in ("椭圆","双曲线","抛物线") if any(name in t for t in texts)]
    if len(conics)<2:
        yield 18,"math_conic_coverage","全卷圆锥曲线仅覆盖："+("、".join(conics) or "无")
    if not any(re.search(r"正态|回归|独立性检验|百分位数|置信|成对数据",t) for t in texts):
        yield 10,"math_inference_coverage","缺现代统计推断或数据分位分析"
    if sum(bool(re.search(r"数列|递推|等差|等比",t)) for t in texts)==0:
        yield 14,"math_sequence_coverage","缺数列考查"
    yield from math_surface_findings(rows,texts)
    yield from math_overlap_findings(rows,texts)
    if not any(re.search(r"指数函数|对数函数|指数式|对数式|抽象函数|\\ln\b|\\log\b|e\^|\\mathrm\{e\}\^",t)
               or (re.search(r"函数",t) and re.search(r"奇函数|偶函数|周期函数|奇偶性|对称中心",t))
               for t in texts[:14]):
        yield 14,"math_short_function","选填题缺指对数或抽象函数性质"
    if not any(re.search(r"二面角|线面角|异面直线.{0,18}(?:角|夹角)|直线.{0,40}与平面.{0,20}(?:夹角|所成的角)",t)
               for t in texts[14:]):
        yield 16,"math_spatial_angle","解答题未考查空间角"
    if not any(re.search(r"分布列|数学期望|随机变量.{0,45}(?:期望|分布)|\\mathrm\{E\}[ ({]",t) for t in texts):
        yield 17,"math_random_variable","缺随机变量分布列或数学期望"
    for n,(q,t) in enumerate(zip(rows,texts,strict=True),1):
        if marking.DEFENSIVE_VARIANCE.search(t):
            yield n,"math_defensive_variance","普通高中方差无需指定按1/n作为方差"
        if _CONTINGENCY_MENTION.search(t) and not q.get("table"):
            yield n,"math_missing_contingency_table","题干提及列联表但未提供原生 table: {headers, rows}"
        stem = q.get("stem", "")
        if q.get("kind") == "constructed_response" and _MATH_AI_OPENER.search(stem):
            yield n,"math_ai_stem_opener","解答题题干开头禁止使用“本题研究……”等 AI 导语"
        if q.get("kind") == "single_choice":
            plain_stem = re.sub(r"\\(?:left|right)(?![A-Za-z])|\\[()]|\$", "", stem)
            if _MATH_INTERVAL_SPOILER.search(plain_stem):
                yield n,"math_interval_spoiler","单选题禁止将区间设问强改为“取值范围为 (m, +∞)，其中 m 等于”的剧透句式"
    if paper.get("release_rules")==VERSION:
        seen={}
        for n,q in enumerate(rows,1):
            key=q.get("math_technique","")
            if not isinstance(key,str) or not MATH_TECHNIQUE.fullmatch(key):
                yield n,"math_technique_missing","缺可比较的核心解题方法代码"
            elif key in seen:
                yield n,"math_technique_overlap",f"核心方法{key}与第{seen[key]}题相同"
            else:
                seen[key]=n


def math_notation_findings(number, text):
    patterns = {
        "math_script_notation": (r"!=|>=|<=|(?<!\.)\.\.(?!\.)", "改用规范的数学关系符或省略号"),
        "math_combination_notation": (r"\\[dt]?binom\b", r"组合数用 \mathrm{C}_n^m"),
        "math_complement_notation": (r"\\mathbb\s*(?:\{\s*C\s*\}|C)\s*_|ℂ", r"补集用 \complement_U"),
        "math_line_typo": (r"直线\s*(?:\\\(\s*|\$)?1\s*(?:\\\)|\$)?\s*(?:恒过|交于|与)", "检查直线编号 1 是否误写了字母 l"),
        "math_dihedral_term": (r"锐\s*二面角", "两平面所成锐角用“两平面夹角”表述"),
        "math_acute_prime": ("\u00b4", "重音符 ´ 不可冒充导数或顶点撇号，请改用 ' 或 ′"),
        "math_set_colon": (
            r"\\?\{\s*(?:[A-Za-z]|\(\s*[A-Za-z]\s*,\s*[A-Za-z]\s*\))\s*(?:(?:\\in|∈)[^}:|\n]{1,40})?\s*:",
            r"集合描述法用 \mid 或 |，不用冒号",
        ),
        "math_period_before_ze": (r"。\s*则", "“则”前误用句号，请改为逗号“，则”"),
        "math_abs_typo": (
            r"(?<!\\)(?<!\|)\|\|\s*[A-Za-z][A-Za-z0-9_{}^\\]*\s*\|(?!\|)"
            r"|(?<!\\)(?<!\|)\|\s*[A-Za-z][A-Za-z0-9_{}^\\]*\s*\|\|(?!\|)",
            "绝对值/模长竖线不配对（疑似笔误如 ||AB|）",
        ),
        "math_mode_hyphen": (
            r"\\\(\s*[A-Za-z0-9]+\s*-\s*\\\)|(?<!\\)\$\s*[A-Za-z0-9]+\s*-\s*\$",
            r"连字符不可置于数学模式内（会印成减号），请改为 \(k\)- 形式",
        ),
        "math_axis_vector": (
            r"\\(?:overrightarrow|vec)\s*\{\s*[A-Z](?:_\{?[0-9]+\}?|[0-9]+)?[xyz]\s*\}",
            "非定点坐标轴字母不可加向量箭头（如 \\overrightarrow{Cz}）",
        ),
    }
    for rule,(pattern,instruction) in patterns.items():
        if match := re.search(pattern,text):
            yield number,rule,f"{match[0]}：{instruction}"
    for m in re.finditer(r"\\\((.*?)\\\)|(?<!\\)\$([^$\n]+)\$", text, re.S):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        stripped = re.sub(r"\\(?:mathrm|text|operatorname)\{[^{}]*\}|\\[A-Za-z]+", " ", inner)
        if bad := re.search(r"(?:sin|cos|tan|ln|log)(?![a-z]{2,})", stripped):
            yield number, "math_italic_function", f"{bad[0]}：公式内函数漏写反斜杠，应写为 \\{bad[0]}"
            break


def math_coverage_warnings(rows):
    texts = [item_text(q, options=True) for q in rows]
    if not any(_MATH_LINE_CIRCLE.search(t) for t in texts):
        yield 0, "math_line_circle_missing", "全卷“直线与圆”为 0 分缺失，建议评估是否补入选填题位"
    if not any(_MATH_REVOLUTION_SOLID.search(t) for t in texts):
        yield 0, "math_revolution_solid_missing", "全卷“旋转体（球/圆柱/圆锥/圆台）”为 0 分缺失，建议评估是否补入立体几何选填"


def _eval_simple_fraction(raw):
    """Safely evaluate a pure numeric/fraction/power TeX or arithmetic expression to Fraction."""
    import ast

    expr = raw.strip()
    if not expr:
        return None, None
    dp = None
    if m := re.fullmatch(r"[-+]?\d+\.(\d+)", expr):
        dp = len(m.group(1))
    expr = expr.replace("−", "-").replace("×", "*").replace("⋅", "*")
    expr = re.sub(r"\\(?:left|right)\b|\\[,;!]", "", expr)
    expr = re.sub(r"\\(?:times|cdot)\b", "*", expr)
    expr = expr.replace("²", "**2").replace("³", "**3")
    expr = re.sub(r"\^\{([^}]+)\}", r"**(\1)", expr)
    expr = re.sub(r"\^(\d+)", r"**\1", expr)
    for _ in range(4):
        updated = re.sub(r"\\[dt]?frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"((\1)/(\2))", expr)
        if updated == expr:
            break
        expr = updated
    expr = expr.replace("{", "(").replace("}", ")")
    expr = re.sub(r"(\d)\s*\(", r"\1*(", expr)
    expr = re.sub(r"\)\s*(\d|\()", r")*\1", expr)
    if not re.fullmatch(r"[0-9.\s+\-*/()]+", expr):
        return None, None
    try:
        tree = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None, None

    def _walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            val = _walk(node.operand)
            return -val if isinstance(node.op, ast.USub) else val
        if isinstance(node, ast.BinOp):
            left, right = _walk(node.left), _walk(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if right == 0:
                    raise ZeroDivisionError
                return left / right
            if isinstance(node.op, ast.Pow):
                if right.denominator != 1 or abs(right.numerator) > 12:
                    raise ValueError
                return left ** right.numerator
        raise ValueError

    try:
        return _walk(tree), dp
    except (ValueError, ZeroDivisionError, OverflowError):
        return None, None


def _extract_2x2_table(table):
    if not isinstance(table, dict):
        return None
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    if len(rows) < 2 or len(headers) < 3:
        return None
    # Drop trailing summary row/column labeled 合计/总计.
    col_indices = [i for i in range(1, len(headers)) if not re.search(r"合计|总计", headers[i])]
    data_rows = [r for r in rows if not re.search(r"合计|总计", r[0])]
    if len(data_rows) != 2 or len(col_indices) != 2:
        return None
    cells = []
    for r in data_rows:
        row_vals = []
        for c in col_indices:
            token = re.sub(r"\\[()]|\$|\s+", "", r[c])
            if not re.fullmatch(r"\d+", token):
                return None
            row_vals.append(int(token))
        cells.append(row_vals)
    a, b = cells[0]
    c, d = cells[1]
    if min(a, b, c, d) < 0 or (a + b) == 0 or (c + d) == 0 or (a + c) == 0 or (b + d) == 0:
        return None
    return a, b, c, d


_CHI2_NUM = r"(\d+)\s*\*?\s*[(|]\s*(\d+)\s*\*\s*(\d+)\s*-\s*(\d+)\s*\*\s*(\d+)\s*[)|]\s*\^\s*\{?2\}?"
_CHI2_DEN = r"(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)\s*\*\s*(\d+)"
_CHI2_EXPR = re.compile(
    rf"(?:\\frac\s*\{{\s*{_CHI2_NUM}\s*\}}\s*\{{\s*{_CHI2_DEN}\s*\}})"
    rf"|(?:{_CHI2_NUM}\s*/\s*\(\s*{_CHI2_DEN}\s*\))"
)


def math_chi_square_findings(number, question, solution_text):
    """Deterministically recalculate 2x2 chi-square expressions and enforce 0 <= chi2 <= n."""
    if not solution_text:
        return
    norm = solution_text.replace("−", "-").replace("×", "*").replace("⋅", "*").replace("²", "^2")
    norm = re.sub(r"\\(?:left|right)\b|\\[,;!]", "", norm)
    norm = re.sub(r"\\(?:dfrac|tfrac)\b", r"\\frac", norm)
    norm = re.sub(r"\\(?:times|cdot)\b", "*", norm)
    found_formula = False
    for m in _CHI2_EXPR.finditer(norm):
        found_formula = True
        groups = m.groups()[:9] if m.group(1) is not None else m.groups()[9:]
        n_val, a, d, b, c, m1, m2, m3, m4 = map(int, groups)
        if min(m1, m2, m3, m4) <= 0:
            yield number, "math_chi_square_mismatch", "2×2列联表卡方分母含非正数"
            continue
        if a + b + c + d != n_val or sorted([m1, m2, m3, m4]) != sorted([a + b, c + d, a + c, b + d]):
            yield number, "math_chi_square_marginals", (
                f"2×2列联表卡方公式边缘和不一致：n={n_val}，四格=({a},{b},{c},{d})，分母=({m1},{m2},{m3},{m4})"
            )
            continue
        exact = Fraction(n_val * (a * d - b * c) ** 2, m1 * m2 * m3 * m4)
        tail = norm[m.end():]
        # Stop scanning at sentence/formula boundary or inequality comparison.
        stop = re.search(r"\\\)|\$|\n|[，。；]|\\(?:le|ge|lt|gt)\b|[<>]", tail)
        chain = tail[:stop.start()] if stop else tail
        tokens = re.split(r"(=|\\approx|≈)", chain)
        for idx in range(1, len(tokens) - 1, 2):
            op, rhs_raw = tokens[idx], tokens[idx + 1].strip()
            val, dp = _eval_simple_fraction(rhs_raw)
            if val is None:
                continue
            if val < 0 or val > n_val:
                yield number, "math_chi_square_bound", (
                    f"2×2列联表卡方值 {rhs_raw} 超出数学上界 [0, {n_val}]（精确值应为 {exact}≈{float(exact):.4f}）"
                )
            elif op == "=":
                if val != exact:
                    yield number, "math_chi_square_mismatch", (
                        f"2×2列联表卡方精确重算为 {exact}（约 {float(exact):.4f}），解析误算为 {rhs_raw}"
                    )
            else:
                tol = max(0.005, 0.6 * (10 ** (-dp))) if dp is not None else 0.55
                if abs(float(val) - float(exact)) > tol:
                    yield number, "math_chi_square_mismatch", (
                        f"2×2列联表卡方约值应为 {float(exact):.4f}（精确 {exact}），解析误写为 {rhs_raw}"
                    )
    # Cross-check against a native 2x2 table even when the solution omits the expanded fraction.
    if not found_formula and question and question.get("table") and re.search(r"\\chi\^|χ|K\^2|K²|独立性检验", solution_text):
        cells = _extract_2x2_table(question["table"])
        if cells:
            a, b, c, d = cells
            n_val = a + b + c + d
            exact = Fraction(n_val * (a * d - b * c) ** 2, (a + b) * (c + d) * (a + c) * (b + d))
            for m in re.finditer(
                r"(?:\\chi\s*\^\s*\{?2\}?|χ\s*\^2|K\s*\^\s*\{?2\}?)\s*(=|\\approx|≈)\s*"
                r"(\\frac\s*\{\s*\d+\s*\}\s*\{\s*\d+\s*\}|\d+(?:\.\d+)?(?:/\d+)?)",
                norm,
            ):
                op, rhs_raw = m.group(1), m.group(2).strip()
                val, dp = _eval_simple_fraction(rhs_raw)
                if val is None:
                    continue
                if val < 0 or val > n_val:
                    yield number, "math_chi_square_bound", (
                        f"2×2列联表卡方值 {rhs_raw} 超出数学上界 [0, {n_val}]（由题表重算为 {exact}≈{float(exact):.4f}）"
                    )
                elif op == "=" and val != exact:
                    yield number, "math_chi_square_mismatch", (
                        f"由2×2列联表重算卡方为 {exact}（约 {float(exact):.4f}），解析误算为 {rhs_raw}"
                    )
                elif op != "=":
                    tol = max(0.005, 0.6 * (10 ** (-dp))) if dp is not None else 0.55
                    if abs(float(val) - float(exact)) > tol:
                        yield number, "math_chi_square_mismatch", (
                            f"由2×2列联表重算卡方约 {float(exact):.4f}，解析误写为 {rhs_raw}"
                        )


def math_point_warnings(rows, rendered):
    # Only compare points explicitly named by constructions. Given vertices and
    # mere references to a point in a rubric do not count as new constructions.
    name = re.compile(r"(?:交|相交|垂足|取交点)(?:于|为|记作)\s*(?:\\\(\s*|\$)?([A-Z])\b")
    rubric_point = re.compile(r"(?:交点|垂足|辅助点)\s*(?:\\\(\s*|\$)?([A-Z])\b")
    for n,q in enumerate(rows,1):
        if q["kind"]!="constructed_response":
            continue
        solution,_,rubric = rendered.get(n,"").partition("\n评分")
        given = {x for x in name.findall(item_text(q))}
        derived = set(name.findall(solution))-given
        marked = (set(name.findall(rubric))|set(rubric_point.findall(rubric)))-given
        if derived and marked and marked-derived:
            yield n,"math_auxiliary_point",f"解析辅助交点 {sorted(derived)}，评分细则另写 {sorted(marked-derived)}，请核对"


FILL_TOPICS = {
    "计数与组合":r"排列组合|计数原理|二项式|展开式.{0,20}系数|放入.{0,25}方法|排成一列.{0,30}(?:方法|种)",
    "数列求和":r"(?:数列|递推|等差|等比).{0,100}(?:前\s*.{1,12}项和|求和)",
    "向量数量积":r"向量.{0,100}(?:数量积|\\cdot)",
    "导数与切线":r"切线.{0,30}(?:斜率|方程)|(?:斜率|方程).{0,16}切线",
}


def math_overlap_findings(rows,texts):
    templates = {}
    fill_in = {}
    tangents = []
    for n,(q,t) in enumerate(zip(rows,texts,strict=True),1):
        kind = q.get("kind")
        if kind=="fill_in":
            for topic,pattern in FILL_TOPICS.items():
                if re.search(pattern,t):
                    if topic in fill_in:
                        yield n,"math_fill_topic_overlap",f"两道填空均考{topic}（第 {fill_in[topic]}、{n} 题）"
                    else:
                        fill_in[topic]=n
        if re.search(r"切线",t) and re.search(r"导数|导函数|函数|曲线",t) \
                and re.search(r"斜率|方程|求.{0,12}切线|写出.{0,10}切线",t):
            tangents.append(n)
        new = []
        if re.search(r"三角形|\\triangle",t):
            # Match labelled, defining triangle data. ABC alone identifies no model.
            conditions = re.findall(r"(?<![A-Za-z])(?:[abcABC]|[A-C]{2})\s*=\s*(?:-?\d+|\\frac\{[^{}]+\}\{[^{}]+\}|\\sqrt\{[^{}]+\})",t)
            if len(set(conditions))>=2:
                new.append(("三角形",tuple(sorted({re.sub(r"\s+","",c) for c in conditions}))))
        formulae = re.findall(r"\\\((.*?)\\\)|\$([^$\n]+)\$",t)
        for left,right in formulae:
            defined = re.match(r"[a-z]\s*\(\s*[a-z]\s*\)\s*=\s*(.+)",left or right)
            if not defined:
                continue
            # Normalize whitespace, variable names, and numeric coefficients; retain exponents.
            model = re.sub(r"\s+|\\(?:left|right)\b","",defined[1].split(r"\quad")[0])
            if re.search(r"[\u3400-\u9fff]",model):
                continue
            model = re.sub(r"\\[A-Za-z]+|\^\{\d+\}|\^\d+|\d+(?:\.\d+)?|[a-z]",
                lambda m:m[0].replace("{","").replace("}","") if m[0].startswith(("^","\\")) else
                "" if m[0][0].isdigit() and m.end()<len(model) and model[m.end()].isalpha()
                else "#" if m[0][0].isdigit() else "x",model)
            if len(model)>=4:
                new.append(("函数",model))
        for signature in set(new):
            previous = templates.setdefault(signature,{})
            other = previous.get(kind!="constructed_response")
            if other is not None:
                yield n,"math_cross_section_model",f"第 {other}、{n} 题跨题型复用{signature[0]}核心模型"
            previous.setdefault(kind=="constructed_response",n)
        if kind=="single_choice":
            opts = q.get("options",{})
            values = [numeric_option(value) for value in opts.values()]
            if len(values)==4 and all(value is not None for value in values) and \
                    values not in (sorted(values),sorted(values,reverse=True)):
                yield n,"math_numeric_order","四个纯数值选项须按升序或降序排列"
        yield from unused_function_findings(n,q)
    if len(tangents)>1:
        yield tangents[-1],"math_tangent_overlap",f"同卷重复考查由函数求切线（题号 {tangents}）"


def numeric_option(text):
    text = re.sub(r"\\[()]|\$|\s+","",text).replace("−","-")
    fraction = re.fullmatch(r"([+-]?)\\[dt]?frac\{([+-]?\d+)\}\{(\d+)\}",text)
    if fraction and int(fraction[3]):
        return Fraction(int(fraction[2])*(-1 if fraction[1]=="-" else 1),int(fraction[3]))
    if re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:/[1-9]\d*)?",text):
        try:
            return Fraction(text)
        except ValueError:
            return None
    if radical := re.fullmatch(r"([+-]?\d*)\\sqrt\{(\d{1,12}(?:\.\d{1,8})?)\}",text):
        return int(radical[1]+"1" if radical[1] in ("","-","+") else radical[1])*sqrt(float(radical[2]))
    if circle := re.fullmatch(r"([+-]?\d*)(?:\\pi|π)(?:/([1-9]\d*))?",text):
        return int(circle[1]+"1" if circle[1] in ("","-","+") else circle[1])*pi/int(circle[2] or 1)
    return None


def unused_function_findings(number,q):
    stem = re.sub(r"\\[()]|\$|\s+","",q.get("stem","")).replace("′","'")
    later = re.sub(r"\\[()]|\$|\s+",""," ".join(
        [p["text"] for p in q.get("parts",[])]+list(q.get("options",{}).values()))).replace("′","'")
    declarations = (
        r"([a-z]'?\([a-z]\))(?:为|表示)(?:其|该函数的)?(?:导函数|函数)",
        r"(?:设|记|定义)(?:函数|导函数)([a-z]'?\([a-z]\))=[^，。；;]+",
    )
    for match in (m for pattern in declarations for m in re.finditer(pattern,stem)):
        symbol = match[1].split("(")[0]
        usage = rf"(?<![A-Za-z]){re.escape(symbol)}(?:\(|(?=的|是|为|$))"
        if not re.search(usage,stem[match.end():]+later):
            yield number,"math_unused_function",f"已引入 {match[1]}，后续题面与选项未使用"


def leaked_blanks(q, keys):
    texts=[p["text"] for p in q.get("parts",[])]
    for i,key in enumerate(keys):
        if i>=len(CIRCLE) or not isinstance(key,str):
            continue
        topic=key.removesuffix("反应")
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,8}",topic):
            continue
        for text in texts:
            if m:=re.search(re.escape(CIRCLE[i])+r"_{2,}",text):
                cue=text[:m.start()].rsplit("。",1)[-1]
                if topic in cue:
                    yield CIRCLE[i],key
                step=re.search(r"(?:步骤|反应)\s*[ⅠⅡⅢ\d]+",cue)
                if step:
                    clauses=re.split("[。；，]",q["stem"].split("已知：",1)[0])
                    if any(step[0] in clause and topic in clause for clause in clauses):
                        yield CIRCLE[i],key


PHYSICS_PROSE_SYMBOL = re.compile(
    r"(?:周期|板长|磁感应强度|质量|速度|重力加速度|引力常量|电流|电压|电阻|长度|位移|半径|间距)"
    r"(?:分别|大小)?(?:为|是|取|记为|等于)?\s*([a-zA-Z])(?![A-Za-z0-9_])"
)


def physics_notation_findings(number, question, solution):
    fields = [question["stem"], *(p["text"] for p in question.get("parts",[]))]
    prose = [re.sub(r"\\\(.*?\\\)|(?<!\\)\$[^$\n]+\$", " ■ ",text,flags=re.S) for text in fields]
    loose = {m[1] for text in prose for m in PHYSICS_PROSE_SYMBOL.finditer(text)
             if text[m.end():].lstrip()[:1] not in ("点","端","板")}
    if loose:
        yield number,"physics_italic_quantity","正文物理量未用公式斜体："+ "、".join(sorted(loose))
    if question.get("kind")!="constructed_response" or number<13:
        return
    text = " ".join(fields)
    declarations = {"g":r"(?:重力加速度|自由落体加速度)[^，。；]{0,28}(?<![A-Za-z])g(?![A-Za-z])",
                    "G":r"(?:万有引力常[量数]|引力常[量数])[^，。；]{0,28}(?<![A-Za-z])G(?![A-Za-z])"}
    expressions = [
        re.sub(r"\\(?:mathrm|text)\{[^{}]*\}|\\[A-Za-z]+","",match[-1].split("=")[-1])
        for line in re.split(r"[，。；\n]", solution)
        if (match:=re.findall(r"\\\((.*?)\\\)",line))
    ]
    for symbol, declaration in declarations.items():
        if any(symbol in expr for expr in expressions) and not re.search(declaration,text):
            yield number,"physics_undeclared_constant",f"字母结果含 {symbol}，题面未声明对应常量"


_CHEM_ORGANIC_SCAFFOLDS = {
    "呋喃二甲酸": r"呋喃二甲酸|FDCA",
    "羟甲基糠醛": r"羟甲基糠醛|HMF",
    "糠醛": r"(?<!羟甲基)糠醛",
    "香豆素": r"香豆素",
    "水杨酸/阿司匹林": r"阿司匹林|乙酰水杨酸|水杨酸",
    "布洛芬": r"布洛芬",
    "对苯二甲酸": r"对苯二甲酸|\bPTA\b",
    "苯并杂环": r"苯并[噁恶噻咪吡][唑嗪啶]",
    "噁嗪酮": r"[噁恶]嗪酮",
    "吡啶甲酸": r"吡啶[二]?甲酸",
    "噻吩甲酸": r"噻吩[二]?甲酸",
    "喹啉": r"喹啉",
    "吲哚": r"吲哚",
    "咔唑": r"咔唑",
    "吩嗪/吩噻嗪": r"吩[噻噁恶]?嗪",
    "己内酰胺": r"己内酰胺",
    "顺丁烯二酸酐/马来酸酐": r"顺丁烯二酸酐|马来酸酐",
    "肉桂酸/肉桂醛": r"肉桂[酸醛]",
    "扁桃酸": r"扁桃酸",
    "咖啡酸": r"咖啡酸",
    "白藜芦醇": r"白藜芦醇",
    "黄酮": r"黄酮",
    "姜黄素": r"姜黄素",
    "绿原酸": r"绿原酸",
    "青蒿素": r"青蒿素",
    "双酚A": r"双酚\s*A",
    "环戊二烯": r"环戊二烯",
    "降冰片烯": r"降冰片烯",
}
_CHEM_DYNAMIC_SCAFFOLD = re.compile(r"[\u4e00-\u9fff]{2,8}(?:二甲酸|三甲酸|二酸酐|嗪酮)")
_CHEM_ACID_SALT_FAMILIES = {
    "草酸/草酸盐": r"草酸|乙二酸|H_?\{?2\}?C_?\{?2\}?O_?\{?4\}?|H₂C₂O₄|C_?\{?2\}?O_?\{?4\}?\^?\{?2[-−]\}?|C₂O₄",
    "硫代硫酸/硫代硫酸盐": r"硫代硫酸|S_?\{?2\}?O_?\{?3\}?\^?\{?2[-−]\}?|S₂O₃",
    "过二硫酸/过硫酸盐": r"过二硫酸|过硫酸|S_?\{?2\}?O_?\{?8\}?|S₂O₈",
    "重铬酸/重铬酸盐": r"重铬酸|Cr_?\{?2\}?O_?\{?7\}?|Cr₂O₇",
    "磷酸/磷酸盐": r"磷酸(?!铁锂)|H_?\{?3\}?PO_?\{?4\}?|H₃PO₄|PO_?\{?4\}?\^?\{?3[-−]\}?|PO₄",
    "亚硫酸/亚硫酸盐": r"亚硫酸|H_?\{?2\}?SO_?\{?3\}?|H₂SO₃|SO_?\{?3\}?\^?\{?2[-−]\}?|SO₃²⁻",
    "次氯酸/次氯酸盐": r"次氯酸|HClO|ClO\^?\{?[-−]\}?|ClO⁻",
    "硼酸/硼酸盐": r"硼酸|H_?\{?3\}?BO_?\{?3\}?|H₃BO₃|B\(OH\)_?\{?3\}?",
    "柠檬酸/柠檬酸盐": r"柠檬酸",
    "酒石酸/酒石酸盐": r"酒石酸",
    "丙二酸/丙二酸盐": r"丙二酸",
    "乳酸/乳酸盐": r"乳酸",
    "硫氰酸/硫氰酸盐": r"硫氰酸|KSCN|SCN\^?\{?[-−]\}?|SCN⁻",
}
_CHEM_MOLAR_UNIT = r"(?:g\s*/\s*mol|g\s*·\s*mol\s*(?:\^?\s*\{?-1\}?|-1))"
_CHEM_MOLAR_AFTER = re.compile(
    rf"([A-Za-z0-9()\[\]·]+)\s*[（(,，]?\s*(?:M|摩尔质量)\s*(?:=|为)\s*(\d+(?:\.\d+)?)\s*{_CHEM_MOLAR_UNIT}"
)
_CHEM_MOLAR_FUNC = re.compile(
    rf"(?<![A-Za-z])M\s*[（(]\s*([A-Za-z0-9()\[\]·]+)\s*[）)]\s*=\s*(\d+(?:\.\d+)?)\s*{_CHEM_MOLAR_UNIT}"
)


def _norm_chem_text(text):
    value = text.replace(r"\(", " ").replace(r"\)", " ").replace("$", " ")
    value = re.sub(r"\\(?:left|right)\b", "", value)
    value = re.sub(r"\\[,;! ]", " ", value)
    value = re.sub(r"\\(?:cdot|bullet)\b", "·", value)
    for _ in range(4):
        updated = re.sub(r"\\(?:mathrm|text|rm)\s*\{([^{}]*)\}", r"\1", value)
        if updated == value:
            break
        value = updated
    value = value.replace("⋅", "·").replace("•", "·").replace("−", "-")
    value = value.translate(str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "01234567890123456789+-"))
    value = re.sub(r"_\{(\d+)\}", r"\1", value)
    value = re.sub(r"_(\d)", r"\1", value)
    return value


def chemistry_molar_mass_findings(number, text, paper_masses=None):
    """Verify declared chemical formula molar masses (M = ... g/mol) within 1 g/mol tolerance."""
    from core.chemistry_data import formula_molar_mass

    if not text or not re.search(r"g\s*/\s*mol|g\s*(?:\\cdot|[·⋅])\s*mol|mol\^?\{?[-−]1|mol⁻¹", text):
        return
    norm = _norm_chem_text(text)
    seen = set()
    for pattern in (_CHEM_MOLAR_AFTER, _CHEM_MOLAR_FUNC):
        for m in pattern.finditer(norm):
            formula, claimed_str = m.group(1).strip(), m.group(2)
            # Trim unmatched leading parenthesis from prose like "（莫尔盐(NH4)2...（M=...）"
            while formula.startswith("(") and formula.count("(") > formula.count(")"):
                formula = formula[1:]
            while formula.endswith(")") and formula.count(")") > formula.count("("):
                formula = formula[:-1]
            key = (formula, claimed_str)
            if key in seen:
                continue
            std_mass = formula_molar_mass(formula)
            if std_mass is None:
                continue
            seen.add(key)
            claimed = float(claimed_str)
            diff = abs(claimed - std_mass)
            if paper_masses:
                hdr_mass = formula_molar_mass(formula, paper_masses)
                if hdr_mass is not None:
                    diff = min(diff, abs(claimed - hdr_mass))
            if diff > 1.0:
                yield number, "chemistry_molar_mass", (
                    f"{formula} 理论摩尔质量约 {std_mass:.2f} g/mol，题面标称 {claimed:g} g/mol，偏差超 1 g/mol"
                )


def chemistry_convention_findings(number, text):
    """Check 2019 PEP chemistry textbook conventions and bare unrendered N_A."""
    if not text:
        return
    if m := re.search(r"(?<![A-Za-z])(?:AlO(?:_\{?2\}?|2|₂)\s*(?:\^\{?[-−]\}?|[-−⁻])|NaAlO(?:_\{?2\}?|2|₂)(?![0-9]))", text):
        yield number, "chemistry_legacy_aluminate", f"{m[0]}：2019人教版须使用 [Al(OH)4]- / Na[Al(OH)4]"
    if m := re.search(r"分子(?:的)?杂化方式|分子杂化类型", text):
        yield number, "chemistry_molecular_hybridization", f"{m[0]}：应规范表述为“中心原子的杂化方式”"
    if "价层排布式" in text:
        yield number, "chemistry_valence_config_term", "价层排布式：应规范表述为“价层电子排布式”"
    if "恶嗪酮" in text:
        yield number, "chemistry_oxazinone_typo", "恶嗪酮：全国名词委规范用字应为“噁嗪酮”"
    prose = re.sub(r"\\\(.*?\\\)|(?<!\\)\$[^$\n]+\$", " ", text, flags=re.S)
    if re.search(r"(?<![A-Za-z0-9_])N_A(?![A-Za-z0-9_])", prose):
        yield number, "chemistry_bare_na", r"裸露未渲染的 N_A，请包裹为公式 \(N_{\mathrm{A}}\) 或 \(N_A\)"


_RXN_CONNECTOR = re.compile(
    r"=|⇌|→|\\(?:rightleftharpoons|leftrightarrow|to|rightarrow|longrightarrow|xlongequal|xrightarrow|overset)\b"
)
_RXN_CONDITION_WORD = re.compile(r"^(?:Δ|△|高温|加热|通电|电解|点燃|催化剂|光照|浓硫酸|稀硫酸)$")


def _split_species_tokens(clause):
    """Split a reaction-like clause into whitespace/plus-delimited tokens, preserving ion charges."""
    spaced = re.sub(r"([\u3400-\u9fff])([A-Za-z0-9(\[])", r"\1 \2", clause)
    spaced = re.sub(r"([A-Za-z0-9)\]+↑↓])([\u3400-\u9fff])", r"\1 \2", spaced)
    # Separate binary '+' between species without splitting ion charges like Fe2+ or SO4^2-.
    spaced = re.sub(r"\+(?=[A-Za-z0-9(\[])", " + ", spaced)
    spaced = re.sub(r"(?<=[A-Za-z0-9)\]])\+(?=\s)", " + ", spaced)
    return [tok for tok in re.split(r"\s+", spaced.strip()) if tok]


def _missing_symbol_in_clause(clause):
    from core.chemistry_data import is_chemical_species

    if _RXN_CONNECTOR.search(clause):
        return False
    if re.search(r"[<>]|\\(?:le|ge|leq|geq|approx|ne|neq|times|frac)\b", clause):
        return False
    if "+" not in clause:
        return False
    tokens = _split_species_tokens(clause)
    if "+" not in tokens or len(tokens) < 4:
        return False
    # Verify at least one '+' actually joins two valid chemical species.
    has_binary_species_plus = any(
        tokens[i] == "+" and i > 0 and i + 1 < len(tokens)
        and is_chemical_species(tokens[i - 1]) and is_chemical_species(tokens[i + 1])
        for i in range(len(tokens))
    )
    if not has_binary_species_plus:
        return False
    # Look for two chemical species separated only by whitespace (or a bare condition word).
    for i in range(len(tokens) - 1):
        left = tokens[i]
        if left == "+" or not is_chemical_species(left, require_structure=True):
            continue
        nxt = tokens[i + 1]
        if nxt == "+":
            continue
        if is_chemical_species(nxt):
            return True
        if _RXN_CONDITION_WORD.match(nxt) and i + 2 < len(tokens) and tokens[i + 2] != "+" and is_chemical_species(tokens[i + 2]):
            return True
    return False


def chemistry_equation_integrity_findings(number, text):
    """Detect chemical equations missing = / ⇌ / → between reactants and products."""
    if not text:
        return
    # 1. Inspect every math span \(...\) and $...$.
    for m in re.finditer(r"\\\((.*?)\\\)|(?<!\\)\$([^$\n]+)\$", text, re.S):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        norm = re.sub(r"\\(?:quad|qquad|enspace|hspace\{[^{}]*\})\b", " ", inner)
        norm = _norm_chem_text(norm)
        if _missing_symbol_in_clause(norm):
            yield number, "chemistry_missing_reaction_symbol", f"化学方程式疑似丢失等号/可逆/箭头符号：{inner.strip()}"
            return
    # 2. Inspect plain prose/solution clauses outside math spans.
    prose = re.sub(r"\\\(.*?\\\)|(?<!\\)\$[^$\n]+\$", "\n", text, flags=re.S)
    for clause in re.split(r"[，。；;、\n：:]+", prose):
        norm = _norm_chem_text(clause)
        if _missing_symbol_in_clause(norm):
            yield number, "chemistry_missing_reaction_symbol", f"化学方程式疑似丢失等号/可逆/箭头符号：{clause.strip()}"
            return


def _canonical_reversible_reactions(text):
    from math import gcd
    from core.chemistry_data import parse_formula_counts

    if not text or not re.search(r"⇌|\\(?:rightleftharpoons|leftrightarrow)\b", text):
        return []
    # Extract equation candidates from math spans and reversible-arrow lines.
    candidates = [m.group(1) if m.group(1) is not None else m.group(2)
                  for m in re.finditer(r"\\\((.*?)\\\)|(?<!\\)\$([^$\n]+)\$", text, re.S)]
    prose = re.sub(r"\\\(.*?\\\)|(?<!\\)\$[^$\n]+\$", "\n", text, flags=re.S)
    candidates.extend(re.split(r"[。；;\n，,]+", prose))
    results = []
    for raw in candidates:
        if not re.search(r"⇌|\\(?:rightleftharpoons|leftrightarrow)\b", raw):
            continue
        cleaned = re.split(r"\\quad|\\Delta\s*H|ΔH|[;；,，。]", raw, maxsplit=1)[0]
        cleaned = re.sub(r"\\(?:rightleftharpoons|leftrightarrow)\b", " ⇌ ", cleaned)
        cleaned = _norm_chem_text(cleaned)
        parts = cleaned.split("⇌")
        if len(parts) != 2:
            continue
        lhs_raw = re.sub(r"^.*[\u3400-\u9fff：:]", "", parts[0])
        rhs_raw = re.sub(r"[\u3400-\u9fff：:].*$", "", parts[1])
        sides = []
        all_coeffs = []
        valid = True
        for side in (lhs_raw, rhs_raw):
            norm_side = side
            # Remove phase markers (g)/(l)/(s)/(aq) and arrows ↑↓.
            norm_side = re.sub(r"\((?:g|l|s|aq)\)|[↑↓]", "", norm_side)
            # Split on binary '+' (not charge trailing '+' before end/space).
            tokens = [t.strip() for t in re.split(r"\s*\+(?=\s*[A-Za-z0-9(\[])\s*", norm_side.strip()) if t.strip()]
            parsed_side = []
            for tok in tokens:
                tok = re.sub(r"\s+", "", tok)
                m = re.match(r"^(\d+)?(.*)$", tok)
                coeff = int(m.group(1)) if m and m.group(1) else 1
                species = m.group(2) if m else tok
                core = re.sub(r"\^?\{?\d*[+-]\}?$", "", species)
                if not species or not parse_formula_counts(core):
                    valid = False
                    break
                parsed_side.append((coeff, species))
                all_coeffs.append(coeff)
            if not valid or not parsed_side:
                valid = False
                break
            sides.append(parsed_side)
        if not valid or not all_coeffs:
            continue
        g = 0
        for c in all_coeffs:
            g = gcd(g, c)
        g = g or 1
        norm_sides = [tuple(sorted((c // g, sp) for c, sp in side)) for side in sides]
        sig = frozenset(norm_sides)
        # Ignore trivial pure water autoionization.
        if sig == frozenset({((1, "H2O"),), ((1, "H+"), (1, "OH-"))}):
            continue
        total_species = sum(len(s) for s in norm_sides)
        if total_species < 2:
            continue
        display = " + ".join(f"{'' if c == 1 else c}{sp}" for c, sp in norm_sides[0]) + " ⇌ " + \
                  " + ".join(f"{'' if c == 1 else c}{sp}" for c, sp in norm_sides[1])
        results.append((sig, display))
    return results


def chemistry_overlap_findings(rows, texts, rendered=None):
    """Detect choice/nonchoice duplicate reversible reactions, repeated organic scaffolds, and acid/salt clusters."""
    rendered = rendered or {}
    full_texts = [
        "\n".join((t, *(q.get("options") or {}).values()))
        for q, t in zip(rows, texts, strict=True)
    ]
    # 1. Duplicate core reversible reaction between choice and non-choice questions.
    choice_rxns = {}
    nonchoice_rxns = {}
    for n, (q, full) in enumerate(zip(rows, full_texts, strict=True), 1):
        is_choice = q.get("kind") in ("single_choice", "multiple_choice")
        target = choice_rxns if is_choice else nonchoice_rxns
        for sig, display in _canonical_reversible_reactions(full + "\n" + rendered.get(n, "")):
            target.setdefault(sig, (n, display))
    for sig, (nc_n, display) in nonchoice_rxns.items():
        if sig in choice_rxns:
            c_n, _ = choice_rxns[sig]
            yield nc_n, "chemistry_duplicate_reversible_reaction", (
                f"第{c_n}题（选择）与第{nc_n}题（非选择）复用同一核心可逆反应：{display}"
            )
    # 2. Same-paper >=2 questions reusing the same characteristic organic scaffold.
    scaffold_hits = {}
    for name, pat in _CHEM_ORGANIC_SCAFFOLDS.items():
        found = [n for n, full in enumerate(full_texts, 1) if re.search(pat, full)]
        if len(found) >= 2:
            scaffold_hits[name] = found
    dynamic_hits = {}
    for n, full in enumerate(full_texts, 1):
        for tok in set(_CHEM_DYNAMIC_SCAFFOLD.findall(full)):
            canon = tok.replace("恶嗪酮", "噁嗪酮")
            dynamic_hits.setdefault(canon, []).append(n)
    for name, found in dynamic_hits.items():
        if len(found) >= 2 and not any(set(found) == set(existing) for existing in scaffold_hits.values()):
            scaffold_hits[name] = found
    for name, found in scaffold_hits.items():
        yield found[-1], "chemistry_organic_scaffold_overlap", f"同卷第{found}题复用同一特征有机母体：{name}"
    # 3. Same-paper >=3 questions clustering on the same characteristic acid/salt family.
    for family, pat in _CHEM_ACID_SALT_FAMILIES.items():
        found = [n for n, full in enumerate(full_texts, 1) if re.search(pat, full)]
        if len(found) >= 3:
            yield found[-1], "chemistry_acid_salt_cluster", f"同卷第{found}题扎堆同一特征酸/盐系：{family}"


def science_checks(subject, paper, rows, texts, answers, rendered, artifacts):
    def hits(pattern):
        return [n for n,t in enumerate(texts,1) if re.search(pattern,t)]
    for n,q in enumerate(rows,1):
        if q["kind"] not in ("single_choice","multiple_choice"):
            review=artifacts["reviews"].get(n,{})
            keys=review.get("independent_blank_answers") or list(review.get("blank_answers",{}).values())
            for symbol,answer in sorted(set(leaked_blanks(q,keys))):
                yield n,"answer_leak",f"题干已给出空{symbol}的答案线索“{answer}”"
    if subject=="physics":
        dc=[n for n in hits(r"光伏|欧姆定律|伏安法|内阻|直流|电压表.{0,60}电流表|供电导线.{0,45}电阻")
            if rows[n-1].get("physics_module","electrostatics_circuits")=="electrostatics_circuits"]
        points=sum(rows[n-1]["points"] for n in dc
                   if not any(re.search(TOPICS[k],texts[n-1]) for k in ("ac","induction_rod")))
        if points>14:
            yield dc[-1],"physics_dc_share",f"纯直流电路{points}分（相关题号{dc}），上限14分"
        missing=[topic for topic in ("ac","oscillation","induction_rod","projectile_or_circle")
                 if not hits(TOPICS[topic])]
        if len(missing)>1:
            yield 13,"physics_core_topics","高频核心缺："+ "、".join(missing)
        for n in range(13,16):
            if n in dc and not re.search(TOPICS["induction_rod"],texts[n-1]):
                yield n,"physics_dc_calculation","计算题使用纯直流模型"
        archetypes = [q.get("experiment_archetype") for q in rows[10:12]]
        reverse = [bool(re.search(r"零偏|偏置|零点|零误差|零位偏差|常量偏差",t) and
                        re.search(r"换向|反向|两方向|方向相反|正向|两个方向|分别向右、向左",t)) for t in texts[10:12]]
        if all(reverse) or (all(archetypes) and len(set(archetypes))==1):
            yield 12,"physics_experiment_overlap","第11、12题共用实验范式（零偏与换向抵消或相同范式代码）"
        if paper.get("release_rules")==VERSION:
            if not all(archetypes):
                yield 11,"physics_experiment_archetype","两道实验题须分别登记实验范式"
            if not any(re.search(r"纸带|刻度尺|读数|电表|电流表|刻度|接线",t) for t in texts[10:12]):
                yield 11,"physics_experiment_instrument","实验缺实物读数或实操"
        for n,q in enumerate(rows,1):
            if any(re.search(r"\\sqrt\s*\{\s*\d+\.\d+\s*\}",s) for s in q.get("options",{}).values()):
                yield n,"physics_radical_decimal","选择题速率等结果根号内直接保留小数"
            solution=rendered.get(n,"")
            yield from physics_notation_findings(n,q,solution)
            energies=[float(e) for group in re.findall(
                r"((?:\d+(?:\.\d+)?,\s*)*\d+(?:\.\d+)?)\s*(?:\\,)?(?:\\mathrm\{)?eV",solution)
                      for e in group.split(",")]
            # Violet extends below 400 nm, so an absolute 3.1 eV cutoff would reject visible violet.
            if energies and max(energies)>1239.842/380 and "可见" in solution and "探测" in q["stem"] and \
               not re.search(r"紫外|不可见|可见光.{0,15}范围|不等于.{0,10}可见",solution):
                yield n,"physics_visible_uv",f"把仪器可检出的最高{max(energies):g} eV谱线归入可见谱线"
    elif subject=="chemistry":
        if not hits(TOPICS["periodic"]):
            yield 1,"chemistry_periodic","缺原子结构与元素周期律推断"
        if not hits(r"离子方程式.{0,18}(?:正确|错误|不正确)|能用.{0,16}离子方程式.{0,16}(?:表示|解释)"):
            yield 5,"chemistry_ionic_judgment","缺离子方程式正误判断题"
        paper_masses = paper.get("relative_atomic_masses")
        for n,t in enumerate(texts,1):
            q=rows[n-1]
            solution=rendered.get(n,"")
            combined="\n".join((t, *(q.get("options") or {}).values(), solution))
            yield from chemistry_molar_mass_findings(n, combined, paper_masses=paper_masses)
            yield from chemistry_convention_findings(n, combined)
            yield from chemistry_equation_integrity_findings(n, combined)
            if re.search(r"有机|合成路线|苯乙酮",t):
                continue
            for eq in re.findall(r"\\\((.*?)\\\)",t+" "+solution):
                if re.search(r"\\(?:to|longrightarrow|rightarrow)\b|→",eq) and "+" in eq and r"\mathrm" in eq:
                    yield n,"chemistry_inorganic_arrow","无机方程式使用箭头："+eq
                    break
            if re.search(r"离子方程式|滴定",t) and re.search(
                r"\\(?:to|longrightarrow|rightarrow)\s*\\mathrm\{(?:CO_2|H_2)\}\+",solution):
                yield n,"chemistry_gas_marker","生成气体的方程式缺↑"
            if re.search(r"K_\{?p",t+solution) and re.search(r"p_i/p\^|K\^\\ominus",t+solution):
                yield n,"chemistry_equilibrium_notation","标准分压比的无量纲常数与Kp记号混用"
            if re.search(r"醋酸|乙酸",t) and "电离焓" in t and re.search(r"\b6\.7\b",t):
                yield n,"chemistry_acetic_enthalpy","乙酸电离焓与常用教学条件不符，需核查条件与来源"
        yield from chemistry_overlap_findings(rows, texts, rendered)
    else:
        for name in ("molecular_genetics","bioengineering"):
            if not hits(TOPICS[name]):
                yield 15 if name=="molecular_genetics" else 21,"biology_"+name,"缺相应主干考查"
        selected=[(n,q.get("options",{}).get(key,"")) for n,(q,key) in
                  enumerate(zip(rows,answers,strict=True),1)
                  if q["kind"]=="single_choice" and isinstance(key,str)]
        hedge=[n for n,line in selected if HEDGE.search(line)]
        if len(hedge)>.35*len(selected):
            yield hedge[0],"biology_hedged_keys",f"{len(hedge)}/{len(selected)}道单选正解使用对冲句式，题号{hedge}"
        base=artifacts.get("figure_folder")
        studio=base/"figure-checks.json" if base else None
        labels=read_json(studio) if studio and studio.is_file() else {}
        for n,q in enumerate(rows,1):
            tags=labels.get(str(n),{}).get("figure_labels",[])
            table=q.get("table") or sum(bool(re.fullmatch(r"\d+(?:\.\d+)?",s.strip())) for s in tags)>=6 \
                and any(re.search(r"表现型|网袋|浓度|指标|处理组|浸泡|相对量|标记碳",s) for s in tags)
            if table and re.search(r"如图|图示|图中|下图|见图|由图",texts[n-1]):
                yield n,"biology_table_reference","该数据为表格，题干仍指称“图”"


def findings(subject,paper,answers,*,header="",listening=None,artifacts=None):
    rows=paper["questions"]
    if len(rows)!=SUBJECT_COUNTS[subject]:
        return
    artifacts=artifacts or {}
    rendered=artifacts.get("solutions",{})
    texts=[item_text(q) for q in rows]
    yield from choice_findings(rows,answers,subject)
    review_map=artifacts.get("reviews",{})
    yield from marking.grading_findings(subject,rows,review_map,rendered)
    for n,t in enumerate(texts,1):
        q=rows[n-1]
        combined="\n".join((t,*q.get("options",{}).values(),rendered.get(n,"")))
        terms=[word for word in TERMS if word in combined]
        if terms:
            yield n,"terminology","不规范用语："+ "、".join(terms)
        if subject=="math":
            yield from math_notation_findings(n,combined)
            if q.get("kind")=="constructed_response":
                yield from math_chi_square_findings(n,q,rendered.get(n,""))
    answer_titles = [line for line in artifacts.get("solutions_md","").splitlines() if line.startswith("# ")]
    if any("项目自拟评分" in title for title in answer_titles):
        yield 1,"terminology","答案标题含内部模板用语：项目自拟评分"
    printed=header+"\n"+artifacts.get("student_md","")
    if subject in {"chemistry","biology"} and re.search(r"计算题须写出",printed):
        yield 1,"science_wrong_instructions","化学生物卷误印物理计算题导语"
    if paper.get("layout_mode")=="practice" and CARD.search(printed):
        yield 1,"practice_answer_card","自印练习版含答题卡作答指令"
    if paper.get("release_rules")==VERSION:
        if paper.get("layout_mode")=="exam" and not CARD.search(printed):
            yield 1,"exam_answer_card","考场版缺答题卡作答指令"
        if subject=="chemistry" and not re.search(r"可能用到的相对原子质量",printed):
            yield 1,"chemistry_atomic_masses","化学卷头缺相对原子质量表"
        if subject in SCIENCE and (rendered or artifacts.get("solutions_md")):
            sol_text = artifacts.get("solutions_md", "") or "\n".join(rendered.values())
            expected_equiv = marking.science_equivalence(subject)
            if expected_equiv not in sol_text:
                yield SUBJECT_COUNTS[subject],"science_quantity_equivalence","答案卷非选择题开头缺对应学科评分总则"
            elif sol_text.count(expected_equiv) > 1:
                yield SUBJECT_COUNTS[subject],"science_quantity_equivalence","学科评分总则仅须在非选择题开头印一次，禁止逐题重复粘贴"
    if subject=="chinese":
        yield from chinese_checks(paper,rows,texts,layout_evidence(artifacts.get("student_pdf")))
    elif subject=="english":
        yield from english_checks(paper,rows,answers,listening or {})
        if "监考：" in artifacts.get("listening_md",""):
            yield 1,"english_invigilator","听力朗读稿使用“监考：”"
    elif subject=="math":
        yield from math_checks(paper,rows,texts)
    else:
        if not artifacts:
            artifacts={"reviews":{}}
        yield from science_checks(subject,paper,rows,texts,answers,rendered,artifacts)


def is_frozen_sample(root,folder):
    path=folder.resolve()
    base=(root/"tests/fixtures/redteam-legacy").resolve()
    return path.parent==base and path.name in SUBJECT_COUNTS


def require_release(root,folder):
    from core.review_board import evidence

    state=evidence(root,folder,enforce_release=True)
    issues=state["preflight"]["issues"]
    require(not issues,"标准发布硬安检失败："+ "；".join(
        f"第{x['number']}题 {x['rule']} {x['evidence']}" for x in issues))
