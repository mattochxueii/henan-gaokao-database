"""Editorial release gate for new standard papers in the unified authoring flow."""
import re

from analysis_db import fingerprint
from forecast_store import write_new
from gaokao import digest, read_json, require
from subjects import SCIENCES
from core.editorial_rules import REVISION, figure_issues, item_text, notation_issues, paper_issues, solution_competition

VERSION = "gaokao-editorial-audit-v1"
MAIN_VERSION = "gaokao-editorial-audit-v2"
MAIN_SUBJECTS = {"math", "chinese", "english"}
YEARS = (2025, 2026)
LANGUAGE_TRAPS = {"scope", "cause", "qualifier", "order", "referent", "stance",
                  "inference_boundary", "collocation", "cohesion"}
READING = {"information", "literary", "classical", "poetry", "reading", "reading_a",
           "reading_b", "reading_c", "reading_d", "gap_match", "cloze", "grammar"}
TEMPLATE = re.compile(r"作为(?:一[个名])?(?:AI|人工智能)|让我们一起来(?:探讨|思考)|作为语言模型|AI生成|此处省略正文", re.I)
RULES = ("distractors", "depth", "figure", "language")
CHOICE = ("single_choice", "multiple_choice")
DEEP_SLOTS = {
    "physics": {*range(4, 11), 15},
    "chemistry": {*range(8, 15), 18},
}


def position_reference(root, subject):
    """Bind official-series position evidence and exclude rehearsal and other regions."""
    from core.paper_intake import PUBLIC, documents

    series = f"cn-ha-{subject}-selective" if subject in SCIENCES else "cn-new-gaokao-1"
    matches = [
        d for p, d in documents(root, subject)
        if p.is_relative_to(root / PUBLIC) and d["year"] in YEARS
        and d["series_id"] == series and d["exam_kind"] == "official_exam"
        and "河南" in d["regions"]
    ]
    papers = {d["year"]: d for d in matches}
    require(len(papers) == len(matches), "同年同卷系有多份正式对照，须先核定版本")
    if not all(year in papers for year in YEARS):
        return None
    slots = {}
    for year in YEARS:
        d = papers[year]
        for q in d["questions"]:
            if not q.get("stem") or not q.get("version_sha256"):
                continue
            slots.setdefault(str(q["number"]), {})[str(year)] = {
                "id": q["id"], "version_sha256": q["version_sha256"],
                "source_url": d["source"]["url"], "topic": q.get("topic"),
                "features": q.get("features", []), "kind": q["kind"], "points": q["points"],
                "scope": "practice_text" if q.get("usable_for_practice") else "limited_position_evidence",
            }
    version = MAIN_VERSION if subject in MAIN_SUBJECTS else VERSION
    reference = {"protocol": version, "subject": subject, "series": series, "slots": slots}
    if subject in {"chinese", "english"}:
        reference["slots_by_basis_year"] = _language_slots(root, subject, slots)
        reference["slots"] = reference["slots_by_basis_year"]["2026"]
    return reference


def _language_slots(root, subject, published_slots):
    """Track each reading, language-use and writing position within its section."""
    blueprints = read_json(root / "data/language-blueprints.json")[subject]["years"]
    by_section = {year: {s["id"]: s for s in b["sections"]} for year, b in blueprints.items()}
    mapped = {}
    for basis, sections in by_section.items():
        edition = {}
        for section, target in sections.items():
            for offset in range(len(target["scores"])):
                number = target["first"] + offset
                references = {}
                for year in map(str, YEARS):
                    peer = by_section[year][section]
                    peer_offset = min(offset, len(peer["scores"]) - 1)
                    original = peer["first"] + peer_offset
                    source = published_slots.get(str(original), {}).get(year)
                    require(source is not None, f"{subject} {year} {section}第{original}题缺对照材料")
                    references[year] = {
                        **source, "reference_number": original, "reference_section": section,
                        "alignment": "same_section_position" if offset == peer_offset else "same_section_only",
                    }
                edition[str(number)] = references
        mapped[basis] = edition
    return mapped


def language_edition(reference, basis_year):
    edition = reference["slots_by_basis_year"].get(str(basis_year))
    require(edition is not None, "语英蓝图与真题题位对照不符")
    return {**reference, "slots": edition, "basis_year": basis_year}


def bound_reference(context, candidate):
    reference = context.get("quality_benchmarks")
    require(reference and candidate.get("provenance", {}).get("quality_reference_sha256") == fingerprint(reference),
            "候选缺2025、2026同题位真题画像绑定，请先读取 authoring-context")
    if context["subject"] in {"chinese", "english"}:
        corpus = context.get("language_corpus", [])
        rehearsal = context.get("rehearsal_references", [])
        require(len(corpus) == 4 and candidate.get("reference_scope") == "fulltext"
                and candidate["provenance"].get("language_corpus_sha256") == fingerprint(corpus)
                and len(rehearsal) == corpus[-1]["questions"]
                and all(q.get("paper_id") == corpus[-1]["id"] and _text(q.get("stem")) for q in rehearsal),
                "语英标准卷须绑定四套真实全文与 DNA")
    return reference


def _option_keys(paper, question):
    options = question.get("options") or {}
    if not options and question.get("material"):
        options = paper.get("materials", {}).get(question["material"], {}).get("options") or {}
    if isinstance(options, list):
        return set("ABCDEFG"[:len(options)])
    return set(options)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _versions(paper):
    return {str(n): fingerprint(q) for n, q in enumerate(paper["questions"], 1)}


def _answers(paper, review):
    # The three production flows retain their existing independent review schemas.
    if "items" in review:
        decisions = {q.get("id", q.get("number")): q.get("answer") for q in review["items"]}
        return [decisions.get(q.get("id"), decisions.get(q.get("number", n)))
                for n, q in enumerate(paper["questions"], 1)]
    return [q.get("answer_key") for q in review["questions"]]


def _main_findings(subject, paper, q, row, n, reject, independent):
    material = paper.get("materials", {}).get(q.get("material"), {})
    if subject == "math":
        slot = paper.get("benchmark_slots", {}).get(str(n), n)
        demanding = slot in {7,8,9,10,11,14,15,16,17,18,19}
        profile = row.get("math_depth", {})
        chain = profile.get("linked_turns", [])
        if demanding and (not isinstance(chain, list) or len(chain) < 2
                          or not all(_text(x) for x in chain) or len(set(chain)) != len(chain)
                          or not _text(profile.get("routine_shortcut_rejected"))):
            reject("depth", "该题位须具备至少两次相连的非代入推理及捷径失效说明")
        if demanding and independent is not None:
            from mathgen.paper_quality import reasoning_profile

            moves = independent.get("moves")
            required_band = 4 if slot in {18, 19} else 3
            if not moves or reasoning_profile(moves)["band"] < required_band:
                reject("depth", "独立重解显示实际推理未达到这一题位的要求")
        figure = q.get("figure")
        requires_reference = re.search(r"如图|图示|见图|读图", q["stem"])
        if (q.get("figure_required") or requires_reference) and not figure:
            reject("figure", "适用几何/函数题缺少规范示意图")
        if q.get("module") == "立体几何" and q["kind"] == "constructed_response":
            if not isinstance(figure, dict) or figure.get("type") != "wireframe":
                reject("figure", "立体几何大题须有三维线框")
        return
    style = row.get("language_style", {})
    rendered = " ".join([q["stem"], material.get("text", ""), *q.get("options", {}).values()])
    if (style.get("natural") is not True or not _text(style.get("register"))
            or not _text(style.get("evidence")) or TEMPLATE.search(rendered)):
        reject("language", "缺文体与语气依据，或题面含生成模板腔")
    if q.get("section") == "classical" and (style.get("classical_checked") is not True
            or re.search(r"进行相关|具体来说|在这种情况下|不由得感慨", material.get("text", ""))):
        reject("language", "文言材料出现白话拟古，或缺语句体例核查")
    if q.get("section") in READING:
        material_text = material.get("text", "")
        decision = row.get("reading_turn", {})
        span = decision.get("span")
        normalize = lambda value: "".join(value.split())
        if (not _text(span) or normalize(span) not in normalize(material_text)
                or not _text(decision.get("from"))
                or not _text(decision.get("to"))
                or decision["from"] == decision["to"]):
            reject("depth", "阅读设问须定位实际材料并说明从哪条信息转到哪一推断")


def evaluate(reference, paper, version, pdf_sha, document, *, review=None, prior=None):
    require(reference and reference.get("protocol") == document.get("protocol")
            and reference["protocol"] in (VERSION, MAIN_VERSION),
            "质量审稿规则版本缺失或不符")
    require(document["paper_version"] == version and document["paper_pdf_sha256"] == pdf_sha
            and document["reference_sha256"] == fingerprint(reference)
            and _text(document.get("reviewer")), "审稿未绑定同题位依据及当前学生 PDF")
    items = document["items"]
    questions = paper["questions"]
    require([r["number"] for r in items] == list(range(1, len(questions) + 1)),
            "质量审稿漏题或题号错位")
    main = reference["protocol"] == MAIN_VERSION
    subject = reference["subject"]
    versions = _versions(paper)
    keys = _answers(paper, review) if review is not None else None
    require(keys is None or len(keys) == len(items), "独立核对题数不符")
    current_edition = paper.get("edition_rules") == REVISION
    failures = [{"number":0,"rule":"coverage","reason":reason} for reason in paper_issues(subject, paper)]
    for n, (q, row) in enumerate(zip(questions, items, strict=True), 1):
        def reject(rule, evidence):
            failures.append({"number": n, "rule": rule, "reason": evidence})

        choice = q["kind"] in CHOICE or (bool(_option_keys(paper, q)) and not q.get("parts"))
        figure = bool(q.get("figure") or q.get("archive_figures") or q.get("figures"))
        findings = row["findings"]
        require(set(findings) == set(RULES), f"第{n}题缺质量红线检查")
        for rule, finding in findings.items():
            active = (choice if rule == "distractors" else figure if rule == "figure" else True)
            verdict = finding["verdict"]
            require(verdict in ("pass", "return", "not_applicable") and _text(finding["evidence"]),
                    f"第{n}题的{rule}判断缺具体证据")
            if verdict == "return":
                reject(rule, finding["evidence"])
            elif active != (verdict == "pass"):
                reject(rule, "审稿跳过适用规则或将不存在的项目标为通过")

        references = reference["slots"].get(str(n), {})
        comparisons = row["benchmarks"]
        if (not references or set(comparisons) != set(references)
                or any(comparisons[year].get("version_sha256") != sample["version_sha256"]
                       or not _text(comparisons[year].get("comparison"))
                       for year, sample in references.items())):
            reject("depth", "同题位对照缺失、题位错配或版本不符")
        depth = row["depth"]
        steps = depth.get("reasoning_steps", [])
        concepts = depth.get("linked_concepts", [])
        minimum = 2 if n in DEEP_SLOTS.get(reference["subject"], ()) else 1
        if not all(isinstance(values, list) and len(values) >= minimum
                   and all(_text(value) for value in values)
                   and len(set(values)) == len(values) for values in (steps, concepts)):
            reject("depth", "缺少同题位要求的不同信息处理步骤及相互联结的概念")
        if current_edition and subject not in {"chinese","english"}:
            for issue in figure_issues(q, row):
                reject("figure", issue)
            if subject == "math" and (issue := notation_issues(item_text(q, options=True))):
                reject("language", issue)
            if subject == "chemistry" and (issue := solution_competition(q, row)):
                reject("depth", issue)
        if main:
            independent = review["questions"][n - 1] if subject == "math" and review is not None else None
            _main_findings(subject, paper, q, row, n, reject, independent)
        if figure and not _text(row.get("required_figure_information")):
            reject("figure", "缺少移去题图后无法取得的条件或数据说明")
        if choice:
            paths = row["distractors"]
            options = _option_keys(paper, q)
            correct = set((keys[n - 1] if keys is not None else row.get("answer_key")) or ())
            if not correct or not correct < options or set(paths) != options - correct:
                reject("distractors", "干扰项记录须覆盖所有且仅覆盖独立答案排除的选项")
            for option, path in paths.items():
                if (path.get("plausible") is not True or not _text(path.get("misconception"))
                        or not _text(path.get("mechanism"))):
                    reject("distractors", f"{option}项缺可信的学生误区或具体推错路径")
                if main and subject in {"chinese", "english"} and (
                    path.get("trap") not in LANGUAGE_TRAPS
                    or path.get("subtle") is not True
                    or not _text(path.get("unchanged")) or not _text(path.get("distortion"))
                ):
                    reject("distractors", f"{option}项须指出保留信息和单一可信偏移")

    if prior is not None:
        require(prior["status"] == "returned" and prior["reference_sha256"] == fingerprint(reference),
                "退稿与当前真题标尺不符")
        revisions = document.get("revisions", {})
        for failure in prior["failures"]:
            n = str(failure["number"])
            change = revisions.get(n, {}).get(failure["rule"])
            changed = (versions != prior["item_versions"] if n == "0"
                       else versions.get(n) != prior["item_versions"].get(n))
            if not changed or not _text(change):
                failures.append({**failure, "reason": "退稿题未换版，或缺少针对该项退稿的改写记录"})
    require(failures or review is not None, "通过版须以独立重解核定选择题键")
    return {
        "protocol": reference["protocol"], "status": "returned" if failures else "accepted",
        "reference_sha256": fingerprint(reference), "paper_version": version, "paper_pdf_sha256": pdf_sha,
        "item_versions": versions, "audit_sha256": fingerprint(document),
        "independent_review_sha256": fingerprint(review) if review is not None else None,
        "prior_rejection_sha256": fingerprint(prior) if prior is not None else None,
        "failures": failures,
    }


def _paper_inputs(folder):
    if (folder / "blind-packet.json").is_file():
        packet = read_json(folder / "blind-packet.json")
        binding = read_json(folder / "verification.json")
        require(fingerprint(packet["paper"]) == packet["paper_version"] == binding["paper_version"],
                "学生题面已修改，须重新生成")
        reference = binding.get("quality_benchmarks")
        require(packet["paper"].get("quality_reference_sha256") == (fingerprint(reference) if reference else None),
                "学生卷对应的同题位证据版本不符")
        pdf = digest(folder / "paper.pdf")
        require(pdf == binding.get("paper_pdf_sha256", binding.get("paper_sha256")), "PDF已修改，须重新生成")
        return reference, packet["paper"], packet["paper_version"], pdf
    candidate = read_json(folder / "raw-ai-candidate.json")
    manifest = read_json(folder / "review-manifest.json")
    paper = read_json(folder / "student-text.json")
    require(fingerprint(candidate) == manifest["candidate_sha256"]
            and fingerprint(paper) == manifest["writing_sha256"], "数学题面已修改，须重新生成")
    # Once released, validate the distributed bytes instead of old local preview files.
    published = folder / "paper.pdf"
    preview = folder / "review-only/paper.pdf"
    use_published = (folder / "publication.json").is_file() or not preview.is_file()
    pdf = digest(published if use_published else preview)
    require(pdf == manifest["pdf_sha256"], "PDF已修改，须重新生成")
    return candidate.get("quality_benchmarks"), paper, manifest["writing_sha256"], pdf


def submit(folder, document, *, review=None, prior=None):
    """Store one immutable editorial decision per candidate folder."""
    if review is None and (folder / "independent-review.json").is_file():
        review = read_json(folder / "independent-review.json")
    bound = _paper_inputs(folder)
    if review is not None:
        require(review.get("paper_pdf_sha256", review.get("pdf_sha256", bound[3])) == bound[3]
                and review.get("paper_version", bound[2]) == bound[2], "独立重解与送审卷版本不符")
    result = evaluate(*bound, document, review=review, prior=prior)
    require(not any((folder / name).exists() for name in (
        "quality-audit.json", "quality-result.json", "draft-quality-rejection.json")), "该卷已提交审稿，请另存修订版")
    if prior is not None:
        write_new(folder / "draft-quality-rejection.json", prior)
    write_new(folder / "quality-audit.json", document)
    write_new(folder / "quality-result.json", result)
    return result


def publication_quality(folder, review):
    """Recompute the release decision; never trust a stand-alone accepted flag."""
    bound = _paper_inputs(folder)
    if bound[0] is None:
        return None  # Existing pre-gate editions and specialty workflows.
    require((folder / "quality-audit.json").is_file() and (folder / "quality-result.json").is_file(),
            "缺 quality-audit.json 或审稿结果，禁止发布")
    prior_path = folder / "draft-quality-rejection.json"
    result = evaluate(*bound, read_json(folder / "quality-audit.json"), review=review,
                      prior=read_json(prior_path) if prior_path.is_file() else None)
    require(result["status"] == "accepted" and result == read_json(folder / "quality-result.json"),
            "质量审稿未通过或审稿证据改变，禁止发布")
    return result["audit_sha256"]
