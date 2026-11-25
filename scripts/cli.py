"""Run with python scripts/cli.py --help."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from gaokao import (
    ROOT, SUBJECTS, atomic_write, digest, dumps, import_file, load, load_solutions,
    register, relative_path, require, read_lines,
)
from reference import reference_rows
from storage import reference_directory


def select(papers, options):
    subject = next((code for code, label in SUBJECTS.items() if label == options.subject), options.subject)
    if subject == "生物":
        subject = "biology"
    return {
        key: paper for key, paper in papers.items()
        if (options.year is None or paper["year"] == options.year)
        and (subject is None or paper["subject"] == subject)
        and (options.region is None or options.region in paper["regions"])
    }


def summaries(papers, files, entries, solutions=None, references=None):
    solutions = solutions or {}
    references = references or {}
    result = []
    for key, paper in papers.items():
        local = [record for record in files if record["paper_id"] == key]
        rows = [row for row in entries if row["paper_id"] == key]
        transcribed = sum(row["record_type"] == "transcribed" for row in rows)
        roles = {item["role"] for item in local}
        status = "已解析" if transcribed else ("已获取原始资料" if "paper" in roles else "已发现来源")
        result.append({
            "paper_id": key, "title": paper["formal_title"], "edition": paper["edition_label"],
            "identity_status": paper["identity_status"], "content_status": status,
            "expected_questions": paper.get("expected_questions"),
            "indexed_questions": len(rows), "transcribed_questions": transcribed,
            "complete_question_texts": sum(row.get("content_complete") is True for row in rows),
            "independent_solutions": sum(row["id"] in solutions for row in rows),
            "local_reference_questions": sum(row["id"] in references for row in rows),
            "human_reviewed_questions": sum(row["review_status"] == "已人工核验" for row in rows),
            "files": local,
            "missing_local_materials": {role: entry for role, entry in paper["materials"].items() if role not in roles},
            "local_roles_without_complete_version": sorted(
                roles - {item["role"] for item in local if item.get("coverage") == "complete"}
            ),
            "issues": paper.get("issues", []),
        })
    return result


def question_result(row, paper, sources, solution, reference, curation=None):
    result = {
        **row, "year": paper["year"], "subject": paper["subject"],
        "content_complete": row.get("content_complete", False),
        "independent_solution": solution,
        "sources": [sources[key]["url"] for key in row["source_ids"]],
    }
    if reference and row["record_type"] == "index_only":
        result.update(
            stem=reference["stem"], options=reference["options"], formulas=reference["formulas"],
            subquestions=reference.get("subquestions", []), tables=reference.get("tables", []),
            asset_refs=reference["assets"], record_type="candidate_transcription",
            review_status=reference["review_status"], candidate_content_complete=True,
            source_locator={"source_id": reference["source_id"], "original_number": row["original_number"],
                            "candidate_page": reference["page"], "candidate_end_page": reference["end_page"],
                            "locator_type": reference["version"]},
            local_reference={field: reference[field] for field in
                             ("version", "scope", "source_url", "source_files", "page_images", "rendering")},
            version_note=reference.get("version_note"), answer_note=reference.get("answer_note"),
        )
        if reference["source_url"] not in result["sources"]:
            result["sources"].insert(0, reference["source_url"])
    if curation:
        result["curation"] = curation
        result["answer_for_current_candidate"] = curation["answer_for_current_candidate"]
        result["current_solution"] = curation["current_solution"]
    return result


def extract(root, records, identifier):
    record = next((item for item in records if item["id"] == identifier), None)
    require(record and record["role"] == "paper" and record["format"] == "pdf"
            and record["allow_derivatives"], "需提供允许派生处理的已登记 PDF 原卷 ID")
    executable = shutil.which("pdftotext")
    require(executable, "此命令需要可选的 Poppler pdftotext，其他命令无需安装依赖")
    path = relative_path(root, record["path"])
    require(digest(path) == record["sha256"], "原卷校验值不符")
    raw = subprocess.run([executable, "-layout", "-enc", "UTF-8", str(path), "-"],
                         check=True, stdout=subprocess.PIPE).stdout.decode("utf-8")
    pages = raw.replace("\r\n", "\n").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    require(any(page.strip() for page in pages), "PDF 无可提取文本，需要 OCR 或人工录入")
    paper_id = record["paper_id"]
    output = root / ".local-data" / "intake" / "parsed" / paper_id / f"{record['sha256']}.json"
    atomic_write(output, dumps({
        "paper_id": paper_id, "file_id": identifier, "source_sha256": record["sha256"],
        "method": "pdftotext -layout", "status": "待校对",
        "pages": [{"page": index, "text": page, "needs_ocr": not page.strip()}
                  for index, page in enumerate(pages, 1)],
    }) + "\n")
    return {"path": output.relative_to(root).as_posix(), "pages": len(pages), "status": "待校对"}


def parser():
    command = argparse.ArgumentParser(description="高考真题目录与授权资料管理")
    command.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    command.add_argument("--reference-dir", type=Path, help="加载只在本机保存的候选卷面目录")
    actions = command.add_subparsers(dest="action", required=True)
    actions.add_parser("validate", help="校验目录、文件哈希、题号顺序与分值")
    registration = actions.add_parser("register", help="登记经交叉核实的主考卷")
    registration.add_argument("manifest", type=Path)
    intake = actions.add_parser("import-file", help="登记并去重保存已取得授权的本地文件")
    intake.add_argument("paper_id")
    intake.add_argument("file", type=Path)
    intake.add_argument("--receipt", required=True, type=Path)
    extraction = actions.add_parser("extract-pdf", help="提取经授权 PDF 的逐页原生文本")
    extraction.add_argument("file_id")
    for name in ("query", "report"):
        action = actions.add_parser(name, help="检索试卷或题号" if name == "query" else "统计资料完整性")
        action.add_argument("--year", type=int)
        action.add_argument("--subject", help="中文名称或学科代码")
        action.add_argument("--region", help="地区代码，例如 cn-ha")
        if name == "query":
            action.add_argument("--number", help="原始题号，例如 6")
            action.add_argument("--kind", help="题型代码，例如 fill_in")
            action.add_argument("--complete-only", action="store_true", help="仅返回标记完整且已人工核验的题面")
        else:
            action.add_argument("--output", type=Path, help="另存 JSON 报告")
    return command


def main():
    options = parser().parse_args()
    root = options.root.resolve()
    action = options.action
    try:
        if action == "register":
            result = {"paper_id": register(root, options.manifest)}
        elif action == "import-file":
            result = import_file(root, options.paper_id, options.file, options.receipt)
        else:
            sources, papers, records, entries = load(root, check_hash=action == "validate")
            solutions = load_solutions(root, entries, sources)
            curation_path = root / "data/analysis" / "curation.jsonl"
            curation = {row["question_id"]: row for row in read_lines(curation_path)} if curation_path.exists() else {}
            references = reference_rows(reference_directory(root, options.reference_dir), sources, papers, entries,
                                        check_hash=action == "validate")
            if action == "validate":
                result = {
                    "status": "通过", "papers": len(papers), "sources": len(sources),
                    "file_records": len(records), "unique_files": len({item["sha256"] for item in records}),
                    "question_records": len(entries),
                    "transcribed_questions": sum(item["record_type"] == "transcribed" for item in entries),
                    "complete_question_texts": sum(item.get("content_complete") is True for item in entries),
                    "independent_solutions": len(solutions),
                    "local_reference_questions": len(references),
                }
            elif action == "extract-pdf":
                result = extract(root, records, options.file_id)
            else:
                selected = select(papers, options)
                if action == "report":
                    result = summaries(selected, records, entries, solutions, references)
                    if options.output:
                        atomic_write(options.output, dumps(result) + "\n")
                elif options.number is None and options.kind is None and not options.complete_only:
                    result = list(selected.values())
                else:
                    result = [
                        question_result(row, selected[row["paper_id"]], sources,
                                        solutions.get(row["id"]), references.get(row["id"]), curation.get(row["id"]))
                        for row in entries if row["paper_id"] in selected
                        and (options.number is None or row["original_number"] == options.number)
                        and (options.kind is None or row["kind"] == options.kind)
                        and (not options.complete_only or row.get("content_complete") is True)
                    ]
        print(dumps(result))
    except (OSError, KeyError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"操作失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
