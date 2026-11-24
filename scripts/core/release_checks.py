"""Deterministic preflight checks for a standard paper and its actual artifacts."""
import re
from collections import Counter
from pathlib import Path

from gaokao import read_json, require
from core import marking_standards as marking
from core.editorial_rules import item_text

VERSION = "henan-standard-release-v1"
SUBJECT_COUNTS = {"chinese":22,"math":19,"english":67,"physics":15,"chemistry":18,"biology":21}
SCIENCE = {"physics","chemistry","biology"}
CARD = re.compile(r"(?:请)?(?:按(?:如下格式)?)?在答题卡(?:的)?相应位置作答")
TERMS = ("氧化数","气体活度","伯碳原子","同源体","居群","腐屑","生产者现存量","连锁相位",
         "水平磁力","项目参考评分","候选答","主语域","示文","自行扣扣","监考：")
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

    lines = []
    # Count independent stroked drawing paths. A valid grid is one path with 21/26 verticals and 2 horizontals.
    counts = Counter()
    for page in PdfReader(pdf).pages:
        lines.append(page.extract_text() or "")
        content = page.get_contents()
        if content is None:
            continue
        strokes = []
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
                strokes = []
                start = None
    return {"essay_grid_cells":sum(width*count for width,count in counts.items()),
            "essay_columns_and_rows":dict(counts),
            "essay_800_mark":bool(re.search(r"800\s*字","\n".join(lines)))}


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
    return {"student_md":read("paper.md"),"solutions":rendered,
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
            tokens=WORDS.findall(data["text"].casefold())
            # Longer, non-core lexical items approximate register. Report limitations in documentation.
            fraction=sum(len(t)>=7 and t not in CORE_ENGLISH for t in tokens)/max(len(tokens),1)
            if fraction<.11:
                yield 28 if data.get("title")=="C" else 32,"english_reading_register",f"{key}较长非基础词占比{fraction:.1%}，低于11%"
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


def math_checks(paper, rows, texts):
    if sum(bool(re.search(r"[(（]\s*3\s*[)）]",t)) for t in texts[17:19])==0:
        yield 18,"math_progression","第18、19题均无第三问递进"
    conics=[name for name in ("椭圆","双曲线","抛物线") if any(name in t for t in texts)]
    if len(conics)<2:
        yield 18,"math_conic_coverage","全卷圆锥曲线仅覆盖："+("、".join(conics) or "无")
    if not any(re.search(r"正态|回归|独立性检验|百分位数|置信|成对数据",t) for t in texts):
        yield 10,"math_inference_coverage","缺现代统计推断或数据分位分析"
    if sum(bool(re.search(r"数列|递推|等差|等比",t)) for t in texts)==0:
        yield 14,"math_sequence_coverage","缺数列考查"
    for n,t in enumerate(texts,1):
        if marking.DEFENSIVE_VARIANCE.search(t):
            yield n,"math_defensive_variance","普通高中方差无需指定按1/n作为方差"
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
        for n,t in enumerate(texts,1):
            if re.search(r"有机|合成路线|苯乙酮",t):
                continue
            solution=rendered.get(n,"")
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
        if subject in SCIENCE and rendered and not any(marking.SCIENCE_EQUIVALENCE in t for t in rendered.values()):
            yield SUBJECT_COUNTS[subject],"science_quantity_equivalence","评分参考缺等价单位、有效数字与分数小数规则"
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
    base=(root/"samples/2027-henan").resolve()
    return path.parent==base and path.name in SUBJECT_COUNTS


def require_release(root,folder):
    from core.review_board import evidence

    state=evidence(root,folder,enforce_release=True)
    issues=state["preflight"]["issues"]
    require(not issues,"标准发布硬安检失败："+ "；".join(
        f"第{x['number']}题 {x['rule']} {x['evidence']}" for x in issues))
