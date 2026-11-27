"""Plan, verify and render science exercises through a subject-specific gate."""

from collections import Counter
import math
from pathlib import Path
import re
import shutil

from analysis_db import fingerprint
from core import exam_policy
from core.catalog import catalog, query, use
from core.science_dna import STANDARD_LAYOUT
from core.editorial_rules import LAYOUT_MODES, REVISION
from forecast_store import write_new
from gaokao import digest, read_json, relative_path, require
from subjects import SCIENCES, SUBJECTS, science_verifier

KINDS = ("single_choice","multiple_choice","fill_in","constructed_response")
VERSION = "science-workflow-v1"
BLANKS = re.compile(r"\\\(.*?\\\)|([①-⑳])?(_{3,})", re.S)


def same_answer(first, second):
    if type(first) in (int,float) and type(second) in (int,float):
        return math.isfinite(first) and math.isfinite(second) and first==second
    if type(first) is not type(second):
        return False
    if isinstance(first,dict):
        return first.keys()==second.keys() and all(same_answer(v,second[k]) for k,v in first.items())
    if isinstance(first,list):
        return len(first)==len(second) and all(same_answer(a,b) for a,b in zip(first,second))
    return first==second


def plan(root, subject, region, year, mode="targeted", topics=()):
    require(subject in SCIENCES, "数学使用原有蓝图，语文和英语只登记学科")
    usages = use(root,subject,region,year)
    require(len(usages)==1, "地区和年份应有唯一适用省卷")
    mapping = usages[0]
    require(mapping["status"]!="historical_component", "旧理综分科不能充当独立选择性考试蓝图")
    knowledge = [x["title"] for x in catalog(root)["entities"]["KnowledgePoint"] if x["subject"]==subject]
    layout = mapping.get("structure")
    structure_mapping = mapping
    if mode == "standard":
        if mapping["status"] == "system_announced":
            history = [row for row in catalog(root)["exam_uses"]
                       if row["subject"] == subject and row["region"] == region
                       and row["year"] < year and row["series_id"] == mapping["series_id"]
                       and row["exam_system_id"] == mapping["exam_system_id"]
                       and row["status"] == "historical_selective"
                       and (row.get("structure") or {}).get("sections")]
            require(history, "没有可沿用的同省同卷系历史结构")
            structure_mapping = max(history, key=lambda row: row["year"])
            layout = structure_mapping["structure"]
        require(structure_mapping["status"] == "historical_selective" and layout and layout.get("sections"),
                "缺少可用的同省同卷系卷面结构")
    else:
        require(mode=="targeted", "概率研究使用独立命令")
    result = {
        "workflow":VERSION,"subject":subject,"region":region,"year":year,"mode":mode,
        "mapping":mapping,"curriculum_topics":knowledge,"requested_topics":list(topics),
        "reference_candidates": [{k:q.get(k) for k in ("id","topic","source_url","review_status","version_sha256",
                                                          "usable_for_practice","strict_official_verified","conflict_note")}
                                 for q in query(root,subject,year=structure_mapping["year"],region=region,verified_only=True)],
        "structure":layout if mode=="standard" else None,
        "structure_minutes": structure_mapping.get("minutes") if mode == "standard" else None,
        "structure_year": structure_mapping["year"] if mode == "standard" else None,
        "scope": ("专项分数和时长由练习设定" if mode == "targeted" else
                  "同年同省已见卷面结构，项目原创" if structure_mapping is mapping else
                  f"沿用河南 {structure_mapping['year']} 年已见卷面结构的项目模拟；{year} 年实际卷型待确认"),
    }
    if mode == "standard":
        result["exam_policy"] = exam_policy.resolve(root, subject, year, region, mapping["series_id"])
    return result


def normalize_subject_item(item, order, folder):
    from core.native_tables import normalize_table

    kind = item.get("kind","single_choice" if item.get("options") else "constructed_response")
    options = item.get("options",{})
    points = item["points"]
    require(kind in KINDS and type(points) is int and 0<points<=30, "题型或分值无效")
    require((kind in KINDS[:2] and tuple(options)==tuple("ABCD")) or (kind in KINDS[2:] and not options),
            "选择题必须有顺序正确的四个选项")
    stem, parts = item["stem"], item.get("parts",[])
    require(isinstance(stem,str) and stem.strip() and all(p["label"] and p["text"] for p in parts),
            "题干或子问不完整")
    text = " ".join([stem,*options.values(),*(p["text"] for p in parts)])
    require(not re.search(r"【答案】|参考答案[：:]|(?:^|\s)solution:|\\begin\{",text,re.I), "学生版含泄漏或不支持的格式")
    figure = item.get("figure")
    if figure:
        require(isinstance(figure,dict) and figure.get("sha256"), "图像须有内容绑定")
        actual = relative_path(folder,figure["path"])
        require(actual.is_file() and not actual.is_symlink() and digest(actual)==figure["sha256"]
                and actual.suffix.lower() in (".png",".jpg",".jpeg"), "题图缺失或版本不符")
        figure = {"path":"figures/"+figure["sha256"]+actual.suffix.lower(),
                  "sha256":figure["sha256"]}
    data={"id":item["id"],"order":order,"kind":kind,"points":points,"stem":stem,
          "options":options,"parts":parts,"figure":figure}
    if item.get("response_area") is not None:
        require(kind=="constructed_response" and item["response_area"]=="calculation",
                "仅非选择题可申请纯空白演算区")
        data["response_area"]=item["response_area"]
    if "table" in item:
        data["table"]=normalize_table(item["table"])
    if "experiment_archetype" in item:
        require(isinstance(item["experiment_archetype"],str) and item["experiment_archetype"].strip(),
                "实验范式须为非空字符串")
        data["experiment_archetype"]=item["experiment_archetype"]
    if "model_fingerprint" in item:
        require(isinstance(item["model_fingerprint"],str) and item["model_fingerprint"].strip(),
                "模型指纹须为非空字符串")
        data["model_fingerprint"]=item["model_fingerprint"]
    return data


def normalize_prose(text):
    paragraphs = re.split(r"\n[ \t]*\n+", text.strip().replace("\r\n", "\n"))
    return "\n".join(re.sub(r"[ \t]*\n[ \t]*", " ", paragraph) for paragraph in paragraphs)


def blank_numbers(question):
    fields = [question["stem"], *(part["text"] for part in question["parts"])]
    return [match[1] for text in fields for match in BLANKS.finditer(text) if match[2]]


def standard_presentation(question):
    """Fold transcription line breaks and assign blank markers in reading order."""
    index = 0

    def mark(match):
        nonlocal index
        if match[2] is None:
            return match[0]
        require(index < 20, "单题空位超过圈号范围")
        number = chr(ord("①")+index)
        require(match[1] in (None, number), "填空圈号须按题内顺序连续")
        index += 1
        return number+match[2]

    stem = BLANKS.sub(mark, normalize_prose(question["stem"]))
    parts = [{**part,"text":BLANKS.sub(mark, normalize_prose(part["text"]))}
             for part in question["parts"]]
    options = {key: normalize_prose(value) for key, value in question["options"].items()}
    return {**question,"stem":stem,"parts":parts,"options":options}


def check_standard_layout(questions, rules):
    figured_choices = [q for q in questions if q["kind"] in KINDS[:2] and q["figure"]]
    require(len(figured_choices) >= rules["choice_figures_minimum"],
            f'选择题须至少有 {rules["choice_figures_minimum"]} 道使用题图')
    require(all("图" in q["stem"] for q in figured_choices), "选择题题干须指向参与解题的图件")
    nonchoice = {n for n,q in enumerate(questions,1) if q["kind"] not in KINDS[:2] and q.get("figure")}
    missing = set(rules.get("required_figure_positions", ())) - nonchoice
    require(not missing and len(nonchoice) >= rules.get("nonchoice_figures_minimum", 0),
            f"非选择题配图不足，已配图 {sorted(nonchoice)}，必配题位缺图 {sorted(missing)}")
    require(all(blank_numbers(questions[n-1]) for n in rules["embedded_blanks"]),
            "指定非选择题须提供嵌入式填空横线")
    require(all(not blank_numbers(questions[n-1]) for n in rules.get("extended_calculations", ())),
            "物理计算题须保留完整演算要求")
    require(not any(re.search(r"全(?:部)?选对得|选对但不全得|少选且无错得", q["stem"]) for q in questions),
            "选择题组的评分说明由栏目统一排版")


INDEPENDENT_CATEGORIES = {"conservation", "dimensions", "reaction_conditions", "experimental_controls",
                          "derivation", "assumptions"}


def independent_evidence(evidence, labels):
    require(isinstance(evidence, dict), "缺少结构化 independent_check")
    checks, parts = evidence.get("checks"), evidence.get("parts")
    require(isinstance(checks, dict) and checks and checks.keys() <= INDEPENDENT_CATEGORIES
            and all(isinstance(v, str) and v.strip() for v in checks.values()), "缺少有效学科核对要点")
    require(isinstance(parts, dict) and parts.keys() == labels
            and all(isinstance(v, str) and v.strip() for v in parts.values()), "核对记录须覆盖全部子问")
    return evidence


def prepare(root, blueprint, candidate, output, figure_root=None, *, layout_mode="practice"):
    subject = blueprint["subject"]
    require(layout_mode in LAYOUT_MODES, "排版模式须为 practice 或 exam")
    require(candidate["subject"]==subject, "候选学科与蓝图不符")
    questions = candidate["questions"]
    require(questions and isinstance(questions,list) and len(questions)<=50, "题量不合理")
    ids = [q["id"] for q in questions]
    require(len(ids)==len(set(ids)) and all(i.startswith("orig:"+subject+":") for i in ids),
            "原创 ID 不能跨学科或重复")
    visible, answers, checks = [],[],[]
    source_rows = query(root,subject,region=blueprint["region"],limit=10000)
    known_text = {re.sub(r"\W","", q.get("stem") or q.get("semantic_summary") or "") for q in source_rows}
    seen = set()
    solver = science_verifier(subject)
    standard = blueprint["mode"] == "standard"
    from core.review_board import VERSION as current_board
    strict_qa = standard and (candidate.get("quality_benchmarks") or {}).get("review_board") == current_board
    for order,q in enumerate(questions,1):
        public = normalize_subject_item(q,order,figure_root or root)
        if standard:
            public = standard_presentation(public)
        if strict_qa and subject == "physics":
            public.update({key: q[key] for key in ("physics_module", "pi_checks") if key in q})
        figure_models = {"physics": {"velocity_graph", "terminal_data"},
                         "chemistry": {"iodine_evidence"}}
        normalized = re.sub(r"\W","",public["stem"])
        require(normalized and normalized not in known_text and normalized not in seen, "题干与现存真题或同卷题完全重复")
        seen.add(normalized)
        require(isinstance(q["topic"],str) and q["topic"].strip(), "题目缺少学科知识标签")
        require(not blueprint["requested_topics"] or q["topic"] in blueprint["requested_topics"],
                "题目超出专项知识点范围")
        mode = q.get("verification_mode", "program")
        require(mode in ("program", "independent_review"), "未知理科验证通道")
        if mode == "program":
            problem = q.get("problem")
            require(isinstance(problem, dict) and problem.get("op"), "程序通道须提供 problem.op")
            if problem["op"] in figure_models.get(subject, ()):
                require(public["figure"], "学科规格需要学生版题图")
            result = solver(problem)
            require(same_answer(q["proposed_answer"],result["answer"]), "候选答案与独立程序不一致")
            require(result["checks"] and result["explanation"], "缺少程序验证依据")
        else:
            labels = {p["label"] for p in public["parts"]} or {"overall"}
            details = independent_evidence(q.get("independent_check"), labels)
            answer = q.get("proposed_answer")
            require(answer is not None and answer not in ("", {}, []), "独立复核通道须提交待核答案")
            if public["parts"]:
                require(isinstance(answer, dict) and answer.keys() == labels
                        and all(v not in (None,"",{},[]) for v in answer.values()), "候选解须逐问提供")
            result = {"answer":answer,"checks":[],"unverified":["完整学科推导待独立核对"],
                      "explanation":"待审候选答案，未运行算子", "independent_check":details}
        if public["kind"] in KINDS[:2]:
            require(isinstance(result["answer"],str) and result["answer"] and
                    len(set(result["answer"]))==len(result["answer"]) and
                    set(result["answer"])<=set(public["options"]) and
                    (len(result["answer"])==1)==(public["kind"]=="single_choice"), "选项键与题型不符")
        visible.append(public)
        answers.append(result["answer"])
        checks.append({"id":q["id"],"topic":q["topic"],"version_sha256":fingerprint(q),"verification_mode":mode,"verification":result})
    types = Counter(q["kind"] for q in visible)
    points = sum(q["points"] for q in visible)
    require(len({q["topic"] for q in questions})>1 or blueprint["mode"]!="standard", "整卷主题覆盖不足")
    if standard:
        sections = blueprint["structure"]["sections"]
        by_kind = Counter()
        for q in visible:
            by_kind[q["kind"]] += q["points"]
        require(types == Counter({s["kind"]:s["count"] for s in sections})
                and by_kind == Counter({s["kind"]:s["points"] for s in sections})
                and points==sum(s["points"] for s in sections), "题型数量、分值或总分与已核卷面不符")
        offset = 0
        for section in blueprint["structure"]["source_details"]:
            count = section.get("count",section.get("questions",len(section.get("numbers",[]))))
            kind = {"experiment":"constructed_response","calculation":"constructed_response"}.get(
                section["kind"],section["kind"])
            group = visible[offset:offset+count]
            require(all(q["kind"]==kind for q in group), "题序与实际试卷题组不符")
            if "points_each" in section or "each" in section:
                each = section.get("points_each",section.get("each"))
                require(all(q["points"]==each for q in group), "单题分值与题组不符")
            if detail := section.get("individual_points",section.get("individual")):
                require([q["points"] for q in group]==detail, "已核逐题分值不符")
            offset += count
        rules = STANDARD_LAYOUT[subject]
        check_standard_layout(visible, rules)
        minutes = blueprint["structure_minutes"]
    else:
        minutes = candidate.get("minutes", max(5,len(visible)*6))
        require(type(minutes) is int and 0<minutes<=180, "专项练习时长无效")
    paper = {"subject":subject,"title":candidate.get("title") or SUBJECTS[subject]+("原创专项练习" if blueprint["mode"]=="targeted" else "原创模拟卷"),
             "minutes":minutes,"total_points":points,"questions":visible,"layout_mode":layout_mode}
    if standard:
        paper["exam_policy"] = blueprint["exam_policy"]
        if strict_qa:
            paper["qa_protocol"] = current_board
        if reference := candidate.get("quality_benchmarks"):
            paper.update(quality_reference_sha256=fingerprint(reference), standard=True, edition_rules=REVISION)
            if reference.get("release_rules"):
                paper["release_rules"]=reference["release_rules"]
                paper["ledger_topics"]=candidate.get("ledger_topics",{})
                if subject=="chemistry":
                    from core.chemistry_data import ATOMIC_NUMBERS, sort_atomic_masses

                    masses=candidate.get("relative_atomic_masses",{})
                    require(isinstance(masses,dict) and masses and all(
                        element in ATOMIC_NUMBERS and type(mass) in (int,float) and 0<mass<300
                        for element,mass in masses.items()),"化学标准卷须附可核对的相对原子质量")
                    paper["relative_atomic_masses"]=sort_atomic_masses(masses)
        paper["layout"] = "science"
        paper["layout_rules"] = rules
        # Only other series lack a policy record and use their archived scoring note.
        paper["partial_credit"] = next((s.get("partial_correct_points")
            for s in blueprint["structure"]["source_details"] if s["kind"] == "multiple_choice"), None)
    output.mkdir(parents=True,exist_ok=False)
    for q, view in zip(questions,visible,strict=True):
        if view["figure"]:
            asset = relative_path(output,view["figure"]["path"])
            asset.parent.mkdir(exist_ok=True)
            shutil.copyfile(relative_path(figure_root or root,q["figure"]["path"]),asset)
    packet = {"subject":subject,"paper":paper,"paper_version":fingerprint(paper)}
    write_new(output/"blind-packet.json",packet)
    from mathgen.student_pdf import render
    rendered = {**paper,"questions":[
        {**q,"figure":str(relative_path(output,q["figure"]["path"]).resolve()) if q["figure"] else None}
        for q in visible
    ]}
    render(rendered,output/"paper.pdf")
    write_new(output/"verification.json",{"blueprint":blueprint,"questions":checks,"answers":answers,
              **({"quality_benchmarks":reference} if standard and (reference := candidate.get("quality_benchmarks")) else {}),
              "candidate_sha256":fingerprint(candidate),"paper_version":packet["paper_version"],
              "paper_pdf_sha256":digest(output/"paper.pdf")})
    return {"state":"await_independent_review","paper_version":packet["paper_version"],
            "questions":len(visible),"points":points,"pdf_sha256":digest(output/"paper.pdf")}


def adjudicate(folder, review):
    packet = read_json(folder/"blind-packet.json")
    checks = read_json(folder/"verification.json")
    require(review["paper_version"]==packet["paper_version"]==checks["paper_version"]==fingerprint(packet["paper"]),
            "独立审题与当前题面版本不匹配")
    require(digest(folder/"paper.pdf")==checks["paper_pdf_sha256"], "学生版与程序验证时的PDF不符")
    require(not (folder/"independent-review.json").exists(), "本版本已审查")
    require(review.get("input_scope")=="student_packet_only" and
            isinstance(review.get("reviewer"),str) and review["reviewer"].strip(), "须提供只看题面的独立审查记录")
    if packet["paper"].get("layout_rules"):
        require(review.get("paper_pdf_sha256")==checks["paper_pdf_sha256"], "重解须绑定最终学生 PDF")
    questions = packet["paper"]["questions"]
    judgments = {j["id"]:j for j in review["items"]}
    require(set(judgments)=={q["id"] for q in questions} and len(judgments)==len(review["items"]),
            "独立审核须覆盖每题")
    verified = []
    for q, answer, check in zip(questions,checks["answers"],checks["questions"],strict=True):
        j = judgments[q["id"]]
        require(j.get("approved") is True and isinstance(j.get("reasoning"),str) and j["reasoning"].strip()
                and same_answer(j["answer"],answer), "独立解答未与绑定答案一致")
        if check.get("verification_mode") == "independent_review":
            labels = {p["label"] for p in q["parts"]} or {"overall"}
            independent_evidence(j.get("independent_check"), labels)
            require(j.get("independent_check") != check["verification"]["independent_check"],
                    "独立核对不能原样复制候选核对要点")
            if q["kind"] == "constructed_response" and checks["blueprint"]["mode"] == "standard":
                require(j.get("rubric"), "整卷非选择题须有分步评分")
        if check["verification"]["unverified"]:
            require(isinstance(j.get("science_review"),str) and j["science_review"].strip(),
                    "程序覆盖外的科学判断须由审查者说明")
        paragraphs = [j["reasoning"]]
        if packet["paper"].get("layout_rules"):
            if q["kind"] in KINDS[:2] and q["figure"]:
                require(isinstance(j.get("figure_reading"),str) and j["figure_reading"].strip(),
                        "配图选择题须记录独立解题所用图示条件")
            if labels := blank_numbers(q):
                slots = j.get("blank_answers")
                require(isinstance(slots,dict) and list(slots)==labels
                        and all(isinstance(v,str) and v.strip() for v in slots.values()), "解析须按圈号逐空登记")
                paragraphs.insert(0, "填空答案　"+"；".join(f"{n} {slots[n]}" for n in labels)+"。")
        if rubric := j.get("rubric"):
            require(isinstance(rubric,list) and all(type(k["points"]) is int and k["points"]>0
                    and isinstance(k["step"],str) and k["step"].strip() for k in rubric)
                    and sum(k["points"] for k in rubric)==q["points"], "分步评分与本题分值不符")
            from core.chemistry_data import format_science_rubric
            from core.marking_standards import science_note

            rubric_text = "评分参考　"+"；".join(f'{k["step"]}（{k["points"]}分）' for k in rubric)+"。"
            paragraphs.append(format_science_rubric(rubric_text))
            if note := science_note(packet["paper"]["subject"],q):
                paragraphs.append(note)
        entry = {**q, "solution_paragraphs": paragraphs}
        if sol_table := j.get("solution_table"):
            from core.native_tables import normalize_table

            entry["solution_table"] = normalize_table(sol_table)
        if sol_figs := j.get("solution_figures"):
            require(isinstance(sol_figs, list), "答案插图 solution_figures 须为列表")
            bound_figs = []
            for fig in sol_figs:
                require(isinstance(fig, dict) and fig.get("path") and fig.get("sha256"),
                        "答案插图须有路径与 sha256 内容绑定")
                actual = relative_path(folder, fig["path"])
                require(actual.is_file() and not actual.is_symlink()
                        and digest(actual) == fig["sha256"]
                        and actual.suffix.lower() in (".png", ".jpg", ".jpeg"),
                        "答案插图缺失或哈希不符")
                asset = relative_path(folder, "figures/" + fig["sha256"] + actual.suffix.lower())
                asset.parent.mkdir(exist_ok=True)
                if actual.resolve() != asset.resolve():
                    shutil.copyfile(actual, asset)
                item_fig = {"path": str(asset.resolve()), "sha256": fig["sha256"]}
                if fig.get("caption") is not None:
                    require(isinstance(fig["caption"], str) and fig["caption"].strip(), "答案插图说明须为非空文本")
                    item_fig["caption"] = fig["caption"]
                bound_figs.append(item_fig)
            entry["solution_figures"] = bound_figs
        verified.append(entry)
    from mathgen.student_pdf import render
    render({**packet["paper"],"questions":verified},folder/"solutions.pdf",solutions=True)
    write_new(folder/"independent-review.json",review)
    write_new(folder/"visual-pending.json",{
        "review_sha256":fingerprint(review),"verification_sha256":fingerprint(checks),
        "paper_sha256":digest(folder/"paper.pdf"),"solutions_sha256":digest(folder/"solutions.pdf"),
    })
    return {"state":"await_visual_review","paper_sha256":digest(folder/"paper.pdf"),
            "solutions_sha256":digest(folder/"solutions.pdf"),"questions":len(questions)}


def publication_record(folder, visual):
    packet = read_json(folder/"blind-packet.json")
    review = read_json(folder/"independent-review.json")
    pending = read_json(folder/"visual-pending.json")
    require(visual["paper_version"]==packet["paper_version"]==review["paper_version"]==fingerprint(packet["paper"])
            and visual.get("passed") is True and visual.get("reviewer"), "缺少视觉审题")
    require(pending["review_sha256"]==fingerprint(review)
            and pending["verification_sha256"]==fingerprint(read_json(folder/"verification.json")),
            "审查或程序验证已改变")
    for q in packet["paper"]["questions"]:
        if fig := q.get("figure"):
            require(digest(relative_path(folder,fig["path"]))==fig["sha256"],"题图与审核版本不符")
    for item in review.get("items", []):
        for fig in item.get("solution_figures", []):
            actual = relative_path(folder, fig["path"])
            if not actual.is_file():
                actual = relative_path(folder, "figures/" + fig["sha256"] + Path(fig["path"]).suffix.lower())
            require(actual.is_file() and digest(actual) == fig["sha256"], "答案插图与审核版本不符")
    from pypdf import PdfReader
    for label in ("paper","solutions"):
        path = folder/(label+".pdf")
        require(visual[label+"_sha256"]==digest(path)==pending[label+"_sha256"]
                and visual[label+"_pages"]==len(PdfReader(path).pages)
                and visual.get(label+"_note"), "视觉记录与PDF版本或页数不符")
    from core.quality_audit import publication_quality

    quality = publication_quality(folder, review) if packet["paper"].get("quality_reference_sha256") else None
    record = {
        **({"quality_audit_sha256":quality} if quality else {}),
        "status":"project_practice_independently_reviewed","subject":packet["subject"],
        "paper_version":packet["paper_version"],"question_ids":[q["id"] for q in packet["paper"]["questions"]],
        "review_sha256":fingerprint(review),"verification_sha256":pending["verification_sha256"],"visual":visual,
        "scope":"学科程序只覆盖明确模型。另有独立推理和PDF审题记录，教师与实测另行记录。",
    }
    if packet["paper"].get("qa_protocol") == "three-readers-v2":
        from core.review_board import LOCAL_QA_PASSED

        record["local_qa_status"] = LOCAL_QA_PASSED
    return record


def publish(folder, visual, *, root=None):
    from core.release_checks import is_frozen_sample, require_release

    root=root or Path(__file__).resolve().parents[2]
    paper=read_json(folder/"blind-packet.json")["paper"]
    if paper.get("release_rules") or is_frozen_sample(root,folder):
        require_release(root,folder)
    record = publication_record(folder, visual)
    if paper.get("release_rules"):
        from core.publication_ledger import register

        register(root,paper["subject"],paper,digest(folder/"paper.pdf"))
    write_new(folder/"publication.json",record)
    return record


def check_publication(folder, certificate):
    require(publication_record(folder,certificate["visual"])==certificate,"理科试卷发布记录不匹配")
    return read_json(folder/"blind-packet.json")["paper"]
