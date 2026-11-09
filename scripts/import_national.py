"""Build content-backed national records; preserve historical identities through occurrences."""

import bootstrap  # noqa: F401
import difflib, json, re
from collections import Counter
from pypdf import PdfReader
from gaokao import ROOT, read_json, atomic_write, digest, require
from storage import atomic_json
from analysis_db import fingerprint
from national_tex import parse, content_signature, readable, subquestion_tree
from national_quality import source_issues, research_eligible


def jsonl(path, rows):
    atomic_write(
        path,
        "".join(
            json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n"
            for x in rows
        ),
    )


def points(row, meta):
    n = row["number"]
    if meta["series_id"] == "cn-zhejiang":
        return (
            4
            if n <= 10
            else (6 if row["raw_problem_latex"].count("fillinblank") > 1 else 4)
            if n <= 17
            else 14
            if n == 18
            else 15
        )
    if meta["track"] != "unified":
        return 5 if n <= 16 else 12 if n <= 21 else 10
    if meta["year"] <= 2023:
        return 5 if n <= 16 else 10 if n == 17 else 12
    return (
        5
        if n <= 8 or 12 <= n <= 14
        else 6
        if n <= 11
        else {15: 13, 16: 15, 17: 15, 18: 17, 19: 17}[n]
    )


def expected(meta):
    if meta["track"] != "unified":
        return 23
    return 22 if meta["year"] <= 2023 else 19


def tag(row):
    # These are literal-content feature flags, not verified knowledge/difficulty analysis.
    text = row["stem"]
    patterns = {
        "数列": r"数列|a_\{?n|S_\{?n|等差|等比",
        "函数与导数": r"函数|导数|切线|零点|单调|极值",
        "概率统计": r"概率|随机|方差|频率|期望|列联|分布",
        "立体几何": r"棱锥|棱柱|四面体|正方体|二面角|平面.*垂直",
        "解析几何": r"椭圆|抛物线|双曲线|圆锥曲线|离心率",
        "三角函数与解三角形": r"三角形|三角函数|\\sin|\\cos|\\tan",
        "平面向量": r"向量|overrightarrow",
        "集合与复数": r"复数|集合|虚部|共轭",
    }
    return [key for key, pattern in patterns.items() if re.search(pattern, text)]


def locate_pdf(path):
    pages = [page.extract_text() or "" for page in PdfReader(path).pages]
    whole = ""
    bounds = []
    for i, text in enumerate(pages):
        bounds.append((len(whole), i + 1))
        whole += text + "\n"
    matches = list(re.finditer(r"(?m)^\s*(\d{1,2})\.\s*", whole))
    loc = {}
    for i, m in enumerate(matches):
        number = int(m[1])
        end = matches[i + 1].start() if i + 1 < len(matches) else len(whole)
        page = max(page for pos, page in bounds if pos <= m.start())
        if number in loc:
            continue
        loc[number] = {"page": page, "extracted_text": whole[m.end() : end]}
    return loc, len(pages)


def main():
    folder = ROOT / ".private/national-reference"
    acquired = read_json(folder / "acquisition-results.json")["papers"]
    asset_records = read_json(folder / "assets.json")
    previews = (
        read_json(folder / "figure-previews.json")
        if (folder / "figure-previews.json").exists()
        else {}
    )
    from urllib.parse import unquote

    asset_hashes = {
        unquote(
            r["url"].split(
                "/" + read_json(ROOT / "national/acquisition.json")["tex_commit"] + "/"
            )[-1]
        ): r["sha256"]
        for r in asset_records
    }

    def asset_ref(name):
        path = "upstream/tex/" + name
        return {
            "path": path,
            "sha256": asset_hashes[name],
            "kind": "tikz_source" if name.endswith(".tex") else "image",
            **({"preview": previews[path]} if path in previews else {}),
        }

    masters = []
    occurrences = []
    answers = []
    papers = []
    duplicates = []
    known = {}
    alignments = []
    variants = []
    failures = []
    changes = (
        read_json(ROOT / "national/curation.json")["overrides"]
        if (ROOT / "national/curation.json").exists()
        else []
    )
    # Import priority controls stable canonical IDs, independent of incidental file ordering.
    acquired = sorted(
        acquired,
        key=lambda x: (
            0
            if x["series_id"] == "cn-new-gaokao-1"
            else 1
            if x["series_id"] == "cn-new-gaokao-2"
            else 2,
            x["year"],
            x["id"],
        ),
    )
    for meta in acquired:
        try:
            source = ROOT / meta["files"]["tex"]["path"]
            text = source.read_text(encoding="utf-8-sig")
            rows = parse(text)
            require(len(rows) == expected(meta), "题数与原卷型不符 " + meta["id"])
            pdf = ROOT / meta["files"]["pdf"]["path"]
            locations, page_count = locate_pdf(pdf)
            for row in rows:
                for asset in row["assets"] + row["answer_assets"]:
                    require(
                        asset in asset_hashes
                        and (folder / "upstream/tex" / asset).is_file(),
                        "依赖图未取得：" + asset,
                    )
        except Exception as error:
            failures.append(
                {"paper_id": meta["id"], "reason": str(error), "imported": False}
            )
            continue
        for row in rows:
            n = row["number"]
            version = meta["id"] + f":q{n:03d}"
            applied = []
            for change in changes:
                if (change["paper_id"], change["number"]) != (meta["id"], n):
                    continue
                require(
                    change["pdf_sha256"] == digest(pdf)
                    and change["tex_sha256"] == digest(source),
                    "修订证据版本变化",
                )
                require(
                    row["raw_problem_latex"].count(change["old_text"]) == 1,
                    "修订文本未精确匹配",
                )
                variants.append(
                    {
                        "occurrence_id": version,
                        "source": "dxathing-pinned",
                        "raw_problem_latex": row["raw_problem_latex"],
                        "sha256": fingerprint(row["raw_problem_latex"]),
                        "superseded_by_pdf_checked_variant": change["id"],
                    }
                )
                row["raw_problem_latex"] = row["raw_problem_latex"].replace(
                    change["old_text"], change["new_text"]
                )
                row["stem"] = readable(row["raw_problem_latex"])
                row["subquestion_tree"] = subquestion_tree(row["raw_problem_latex"])
                row["parts"] = [p["text"] for p in row["subquestion_tree"]]
                row["formulas"] = [
                    readable(a or b)
                    for a, b in re.findall(
                        r"\\\((.*?)\\\)|\\\[(.*?)\\\]", row["raw_problem_latex"], re.S
                    )
                ]
                applied.append(change["id"])
            for a in row["assets"] + row["answer_assets"]:
                require(
                    a in asset_hashes and (folder / "upstream/tex" / a).is_file(),
                    "图像未取得 " + a,
                )
            signature = content_signature(row, asset_hashes)
            canonical = known.get(signature, version)
            location = locations.get(n, {})
            chinese = lambda v: "".join(re.findall(r"[\u4e00-\u9fff]", v))
            comparison_text = row["stem"] + "".join(row["options"].values())
            ratio = round(
                difflib.SequenceMatcher(
                    None,
                    chinese(comparison_text),
                    chinese(location.get("extracted_text", "")),
                ).ratio(),
                3,
            )
            locator = {
                "tex": {
                    "path": source.relative_to(folder).as_posix(),
                    **row["source_lines"],
                    "sha256": meta["files"]["tex"]["sha256"],
                },
                "pdf": {
                    "path": pdf.relative_to(folder).as_posix(),
                    "page": location.get("page"),
                    "sha256": meta["files"]["pdf"]["sha256"],
                },
                "source_ids": ["dxathing-pinned", "deekur-pinned"],
            }
            issues = []
            if ratio < 0.72:
                issues.append("native_pdf_text_alignment_needs_review")
            issues += source_issues(
                meta["id"], row["raw_answer_latex"] + " " + row["raw_solution_latex"]
            )
            complete = bool(row["stem"]) and all(
                a in asset_hashes for a in row["assets"]
            )
            version_hash = fingerprint(
                {
                    "problem": row["raw_problem_latex"],
                    "assets": [asset_hashes[a] for a in row["assets"]],
                }
            )
            occurrence = {
                "id": version,
                "question_id": canonical,
                "paper_id": meta["id"],
                "number": n,
                "kind": row["kind"],
                "points": points(row, meta),
                "version_sha256": version_hash,
                "source_locator": locator,
                "content_complete": complete,
                "issues": issues,
                "research_eligible": research_eligible({"issues": issues}),
                "answer_id": version + ":answer",
                "topic_flags": tag(row),
            }
            if applied:
                occurrence["curation_ids"] = applied
            occurrences.append(occurrence)
            answers.append(
                {
                    "id": version + ":answer",
                    "occurrence_id": version,
                    "question_id": canonical,
                    "reference_answer": row["reference_answer"],
                    "explanation": row["explanation"],
                    "raw_answer_latex": row["raw_answer_latex"],
                    "raw_solution_latex": row["raw_solution_latex"],
                    "asset_refs": [asset_ref(a) for a in row["answer_assets"]],
                    "source_id": "dxathing-pinned",
                    "source_tex_lines": row["answer_lines"],
                    "question_version_sha256": version_hash,
                    "authority": "third_party",
                    "review_status": "冲突题面关联答案，禁止当作原卷答案"
                    if not research_eligible(occurrence)
                    else "未独立核验的整理答案",
                }
            )
            if signature in known:
                duplicates.append(
                    {
                        "occurrence_id": version,
                        "canonical_id": canonical,
                        "evidence": "规范化完整题面与题图SHA均一致",
                        "method": "exact_content_only",
                    }
                )
            else:
                known[signature] = version
                masters.append(
                    {
                        "id": version,
                        "subject": "math",
                        "stem": row["stem"],
                        "options": row["options"],
                        "formulas": row["formulas"],
                        "parts": row["parts"],
                        "subquestion_tree": row["subquestion_tree"],
                        "tables_latex": row["tables_latex"],
                        "asset_refs": [asset_ref(a) for a in row["assets"]],
                        "raw_problem_latex": row["raw_problem_latex"],
                        "content_sha256": signature,
                        "origin_occurrence_id": version,
                        "data_status": "完整第三方候选题面",
                        "review_status": "已解析并自动校验；逐题数学与视觉核验待完成",
                        "human_reviewed": False,
                        "difficulty": None,
                        "knowledge_points": None,
                    }
                )
            alignments.append(
                {
                    "occurrence_id": version,
                    "pdf_page": location.get("page"),
                    "chinese_alignment": ratio,
                    "issues": issues,
                    "formula_equivalence_proved": False,
                }
            )
        name = readable(re.search(r"\\chapter\{([^}]+)\}", text)[1])
        papers.append(
            {
                "id": meta["id"],
                "year": meta["year"],
                "subject": "math",
                "reported_name": name,
                "series_id": meta["series_id"],
                "track": meta["track"],
                "question_count": len(rows),
                "max_score": 150,
                "pdf_pages": page_count,
                "source_files": meta["files"],
                "expected_structure": dict(Counter(x["kind"] for x in rows)),
                "scoring_complete": True,
                "scoring_basis": "按年度原题型计分；浙江多空每空3分、单空4分，18题14分、19—22题15分；见年度来源记录",
                "optional_policy": {"choose": 1, "from": [22, 23]}
                if meta["track"] != "unified"
                else None,
                "curriculum_id": "math-2003"
                if meta["track"] != "unified"
                else "math-2017-2020"
                if meta["year"] >= 2023
                else "math-transition-unresolved",
                "official_original": False,
                "official_name_status": "第三方卷名与外部用卷信息核对；非命题机构原卷认证",
                "answer_authority": "third_party",
                "rights": "底层试题权利待逐份核实；受控本地研究，适用上游CC署名共享要求",
                "all_candidate_stems_present": True,
                "acquisition_date": "2026-11-08",
            }
        )
    jsonl(folder / "questions.jsonl", masters)
    jsonl(folder / "occurrences.jsonl", occurrences)
    jsonl(folder / "answers.jsonl", answers)
    jsonl(folder / "alternative-versions.jsonl", variants)
    atomic_json(
        ROOT / "reports/phase5-import-issues.json",
        {
            "failures": failures,
            "single_source_failure_does_not_stop_other_papers": True,
        },
    )
    jsonl(ROOT / "national/catalog/papers.jsonl", papers)
    jsonl(
        ROOT / "national/catalog/question-registry.jsonl",
        [
            {
                k: v
                for k, v in x.items()
                if k
                not in (
                    "raw_problem_latex",
                    "stem",
                    "formulas",
                    "parts",
                    "subquestion_tree",
                    "options",
                    "tables_latex",
                    "asset_refs",
                )
            }
            for x in masters
        ],
    )
    jsonl(ROOT / "national/catalog/occurrences.jsonl", occurrences)
    atomic_json(
        ROOT / "reports/phase5-dedup.json",
        {
            "occurrences": len(occurrences),
            "unique_new_questions": len(masters),
            "exact_duplicates": duplicates,
            "similarity_is_not_identity": True,
            "adapted_problems_merged": False,
        },
    )
    atomic_json(
        ROOT / "reports/phase5-auto-alignment.json",
        {
            "question_occurrences": len(alignments),
            "records": alignments,
            "limits": "中文原生PDF文本对齐只用于定位和发现差异，不能证明公式正确；人工核验为0。",
        },
    )
    atomic_json(
        folder / "manifest.json",
        {
            "schema_version": 1,
            "papers": [p["id"] for p in papers],
            "questions": len(masters),
            "occurrences": len(occurrences),
            "files": [
                {"path": p.relative_to(folder).as_posix(), "sha256": digest(p)}
                for p in sorted(folder.rglob("*"))
                if p.is_file() and p.name != "manifest.json"
            ],
        },
    )
    print(
        json.dumps(
            {
                "papers": len(papers),
                "question_occurrences": len(occurrences),
                "unique_questions": len(masters),
                "answers": sum(
                    bool(x["reference_answer"] or x["explanation"]) for x in answers
                ),
                "duplicates": len(duplicates),
                "alignment_review": sum(bool(x["issues"]) for x in alignments),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
