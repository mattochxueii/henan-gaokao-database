"""Editorial release gate for new standard papers in the unified authoring flow."""
from analysis_db import fingerprint
from forecast_store import write_new
from gaokao import digest, read_json, require
from subjects import SCIENCES

VERSION = "gaokao-editorial-audit-v1"
YEARS = (2025, 2026)
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
    return {"protocol": VERSION, "subject": subject, "series": series, "slots": slots}


def bound_reference(context, candidate):
    reference = context.get("quality_benchmarks")
    require(reference and candidate.get("provenance", {}).get("quality_reference_sha256") == fingerprint(reference),
            "候选缺2025、2026同题位真题画像绑定，请先读取 authoring-context")
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


def evaluate(reference, paper, version, pdf_sha, document, *, review=None, prior=None):
    require(reference and reference.get("protocol") == document.get("protocol") == VERSION,
            "质量审稿规则版本缺失或不符")
    require(document["paper_version"] == version and document["paper_pdf_sha256"] == pdf_sha
            and document["reference_sha256"] == fingerprint(reference)
            and _text(document.get("reviewer")), "审稿未绑定同题位依据及当前学生 PDF")
    items = document["items"]
    questions = paper["questions"]
    require([r["number"] for r in items] == list(range(1, len(questions) + 1)),
            "质量审稿漏题或题号错位")
    versions = _versions(paper)
    keys = _answers(paper, review) if review is not None else None
    require(keys is None or len(keys) == len(items), "独立核对题数不符")
    failures = []
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

    if prior is not None:
        require(prior["status"] == "returned" and prior["reference_sha256"] == fingerprint(reference),
                "退稿与当前真题标尺不符")
        revisions = document.get("revisions", {})
        for failure in prior["failures"]:
            n = str(failure["number"])
            change = revisions.get(n, {}).get(failure["rule"])
            if versions[n] == prior["item_versions"][n] or not _text(change):
                failures.append({**failure, "reason": "退稿题未换版，或缺少针对该项退稿的改写记录"})
    require(failures or review is not None, "通过版须以独立重解核定选择题键")
    return {
        "protocol": VERSION, "status": "returned" if failures else "accepted",
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
    pdf = digest(folder / "review-only/paper.pdf")
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
