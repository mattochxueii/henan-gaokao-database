"""Offline export and version-bound feedback from an external reviewer."""
from shutil import copyfile

from analysis_db import fingerprint
from core import exam_policy
from forecast_store import write_new
from gaokao import atomic_write, digest, read_json, require

PROTOCOL = "gaokao-external-review-v1"
EXTRA_RULES = {"exam.policy", "all.graphic"}
LAYOUT_RULES = EXTRA_RULES
REFERENCE_FIELDS = ("id", "kind", "points", "topic", "features", "reference_number",
                    "reference_section", "alignment", "scope", "source_url", "version_sha256")
INSTRUCTIONS = """# 独立盲审

先只看学生卷与年份政策，独立核对可作答性、唯一答案、跨题重复、课程范围和印刷。
同题位摘要可用于对照。请不要索取命题稿或标准答案。英语听力另看随附朗读稿。
使用 findings-template.json 的字段原样返回 JSON。保留版本与 PDF 的 SHA-256，填写实际模型家族和型号。

每条缺陷给出题号、排雷编号、fatal 或 major、可复核事实及具体改法。题号 0 表示全卷问题。
全卷内容缺陷须注明承接修改的 repair_numbers。纯政策或版面缺陷可留空。
数学证据、页面位置和相反条件需明确。请剔除与题目无关的偏好判断，无实质缺陷就提交空 findings。
不提供全卷分数、答案对照表或考生实测推断。
"""


def clean_markdown(paper, snapshot):
    """Reconstruct student Markdown from the bound packet, with no access to answer files."""
    lines = ["# " + paper["title"], f'满分{paper.get("points", paper.get("total_points"))}分，考试时间{paper["minutes"]}分钟。']
    for kind,field in (("english_score","header"),("multiple_choice","instruction")):
        if note := exam_policy.parameters(snapshot,kind).get(field):
            lines.append(note)
    listening_notes = exam_policy.listening_notes(snapshot)
    sections = {item["id"]:item["title"] for item in paper.get("sections", [])}
    previous = None
    seen = set()
    for n, q in enumerate(paper["questions"], 1):
        section = q.get("section")
        if section and section != previous:
            lines.append("## " + sections[section])
            previous = section
        if section == "listening" and n in listening_notes:
            lines.append(listening_notes[n])
        name = q.get("material")
        if name and name not in seen:
            material = paper["materials"][name]
            lines.extend((material["title"], material["text"]))
            lines.extend(f"{key}. {text}" for key,text in material.get("options", {}).items())
            seen.add(name)
        lines.append(f'{n}.（{q["points"]:g}分）' + q["stem"])
        options = q.get("options") or {}
        lines.extend(f"{key}. {text}" for key,text in (options.items() if isinstance(options, dict) else zip("ABCDEFG",options)))
        lines.extend(f'{part.get("label","")} {part["text"]}'.strip() for part in q.get("parts",[]))
        if q.get("figure") or q.get("archive_figures"):
            lines.append("本题图件见随附的同版学生卷 PDF。")
    return "\n\n".join(lines) + "\n"


def export(root, folder, target, *, year=None):
    from core.exam_qa import policies
    from core.quality_audit import _paper_inputs
    from core.review_board import packet_path

    ref, paper, version, pdf_sha256 = _paper_inputs(folder)
    require(ref and isinstance(ref.get("slots"), dict), "试卷须绑定两年同题位摘要")
    subject = ref["subject"]
    policy = paper.get("exam_policy") or (
        exam_policy.resolve(root, subject, year, "河南", ref["series"]) if year
        else exam_policy.guess_snapshot(root, subject, paper["title"], series=ref["series"]))
    require(policy and (year is None or policy["year"] == year), "需要与试卷绑定的目标年份")
    summaries = {slot: {y: {key:row[key] for key in REFERENCE_FIELDS if key in row}
                        for y,row in observations.items()}
                 for slot,observations in ref["slots"].items()}
    rules = ref.get("qa_policy") or policies(root, subject)
    letters = {
        "protocol": PROTOCOL, "paper_version": version, "pdf_sha256": pdf_sha256,
        "model_family": "", "model": "", "findings": [],
    }
    listening_path = folder/"listening-review.json"
    listening = read_json(listening_path) if listening_path.is_file() else {}
    if listening:
        spec = read_json(folder/"verification.json")
        require(fingerprint(listening) == spec["listening_sha256"], "外审听力材料版本不符")
    target.mkdir(parents=True,exist_ok=False)
    copyfile(packet_path(folder),target/"student.pdf")
    printed_policy = paper.get("exam_policy")
    atomic_write(target/"student.md",clean_markdown(paper,printed_policy))
    atomic_write(target/"instructions.md",INSTRUCTIONS)
    write_new(target/"policy-check.json",{"policy":policy,"year_source":"bound" if printed_policy else "legacy_year",
              "student_instructions":exam_policy.student_instructions(policy),
              "invigilator_instructions":exam_policy.listening_notes(policy,invigilator=True)})
    write_new(target/"position-summaries.json",summaries)
    write_new(target/"anti-patterns.json",{"entries":rules,"additional_rules":sorted(EXTRA_RULES)})
    write_new(target/"findings-template.json",letters)
    if listening:
        notes = exam_policy.listening_notes(printed_policy, invigilator=True)
        groups = {}
        for number, q in enumerate(paper["questions"][:20],1):
            groups.setdefault(q["material"], number)
        material = [line for key, body in listening.items()
                    for line in (notes.get(groups[key]), paper["materials"][key]["title"], body) if line]
        atomic_write(target/"listening.md","# 监考朗读稿\n\n"+"\n\n".join(material)+"\n")
    require(digest(target/"student.pdf") == pdf_sha256, "导出的学生 PDF 版本变动")
    return {"state":"exported","directory":str(target),"paper_version":version,"pdf_sha256":pdf_sha256}


def validate(response, local, rules):
    require(isinstance(response, dict) and response.keys() == {
        "protocol", "paper_version", "pdf_sha256", "model_family", "model", "findings"},
        "外审 JSON 字段与模板不符")
    require(response["protocol"] == PROTOCOL and response["paper_version"] == local["paper_version"]
            and response["pdf_sha256"] == local["pdf_sha256"], "外审回执绑定的试卷版本不符")
    require(all(isinstance(response[k], str) and 0 < len(response[k].strip()) <= 160 for k in ("model_family","model")),
            "须填写实际外部模型家族和型号")
    require(isinstance(response["findings"], list), "findings 须为逐条缺陷数组")
    numbers = set(range(1,len(local["ids"])+1))
    known = {r["id"] for r in rules} | EXTRA_RULES
    for item in response["findings"]:
        require(isinstance(item, dict) and {"number","rule","severity","evidence","revision"} <= item.keys()
                and item.keys() <= {"number","rule","severity","evidence","revision","repair_numbers"},
                "外审缺陷须包含题号、规则、严重度、事实和局部改法")
        number = item["number"]
        require(type(number) is int and number in numbers | {0}, "外审题号越界")
        require(isinstance(item["rule"],str) and item["rule"] in known and item["severity"] in ("fatal","major"),
                "外审规则或严重度无效")
        require(all(isinstance(item[k],str) and item[k].strip() for k in ("evidence","revision")),
                "外审缺陷缺可复核事实或改法")
        selected = item.get("repair_numbers",[])
        require(isinstance(selected,list) and all(type(n) is int and n in numbers for n in selected)
                and len(set(selected))==len(selected) and (not number or not selected),
                "只有全卷缺陷可另列承接修订题号")
        require(number or selected or item["rule"] in LAYOUT_RULES, "全卷内容缺陷需指定承接题号")
    return response


def repair_targets(responses, local, rules):
    items = [item for response in responses for item in validate(response,local,rules)["findings"]]
    targets = {n for item in items for n in (item.get("repair_numbers",[]) or [item["number"]]) if n}
    layout_only = bool(items) and all(item["rule"] in LAYOUT_RULES and not item.get("repair_numbers") for item in items)
    return targets, layout_only


def active_findings(folder, local):
    if not (folder/"external-reviews").is_dir():
        return []
    state = read_json(folder/"board"/f'round{local["round"]}.json')["state"]
    results = []
    for path in sorted((folder/"external-reviews").glob("*.json")):
        reply = validate(read_json(path),local,state["rules"])
        require(path.stem == fingerprint(reply), "外审回执内容已经改变")
        if reply["findings"]:
            results.append(reply)
    return results


def return_decision(folder, local, rules):
    responses = active_findings(folder,local)
    if not responses:
        return None
    rewrite, layout = repair_targets(responses,local,rules)
    return {"state":"returned","review_state":"EXTERNAL_REVIEW_RETURNED",
            "pdf_sha256":local["pdf_sha256"],"rewrite":sorted(rewrite),
            "locked":sorted(set(range(1,len(local["ids"])+1))-rewrite),"layout_repair":layout,
            "external_findings":[item for response in responses for item in response["findings"]],
            "next":"重新生成到新目录并通过 board-cycle --previous 指回本次送审目录"}


def import_reply(root, folder, response):
    from core.review_board import LOCAL_QA_PASSED, evidence, replay

    local = replay(folder/"board")
    require(local and local["status"] == LOCAL_QA_PASSED, "请先完成当前试卷的本地盲审")
    state = evidence(root, folder)
    require(state["version"] == local["paper_version"] and state["pdf_sha256"] == local["pdf_sha256"],
            "当前试卷与本地盲审版本不符")
    validate(response,local,state["rules"])
    receipt = folder/"external-reviews"/(fingerprint(response)+".json")
    if not receipt.is_file():
        write_new(receipt,response)
    else:
        require(read_json(receipt) == response, "外审回执内容不一致")
    return {"state":"external_review_recorded","receipt":receipt.name,
            "decision":return_decision(folder,local,state["rules"])}
