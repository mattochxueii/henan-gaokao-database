"""Read locally retained candidate papers without merging them into publishable records."""
from gaokao import digest, read_json, read_lines, relative_path, require


def reference_rows(root, sources, papers, entries, check_hash=False):
    if root is None:
        return {}
    manifest = read_json(root / "manifest.json")
    require(manifest["schema_version"] == 1 and manifest["scope"] == "local_reference",
            "本地参考资料清单的版本或范围无效")
    indexed = {(row["paper_id"], row["original_number"]): row for row in entries}
    references = {}
    for paper_id, version in manifest["papers"].items():
        require(paper_id in papers and version["source_id"] in sources and version["version"],
                f"本地资料缺少试卷或来源登记 {paper_id}")
        paper = papers[paper_id]
        pages = {page["page"]: page for page in version["pages"]}
        require(sorted(pages) == list(range(1, len(version["pages"]) + 1)),
                f"{paper_id} 页码缺失或重复")
        for page in pages.values():
            require(relative_path(root, page["image"]).is_file(), f"{paper_id} 本地页图缺失")
        require(version["source_files"], f"{paper_id} 缺少源文件")
        for source_file in version["source_files"]:
            path = relative_path(root, source_file["path"])
            require(path.is_file(), f"本地源文件缺失 {path}")
            if check_hash:
                require(digest(path) == source_file["sha256"], f"本地源文件 SHA-256 不符 {path}")
        data_path = root / "questions" / str(paper["year"]) / paper["subject"] / f"{paper_id}.jsonl"
        for local in read_lines(data_path):
            row = indexed.get((paper_id, local["original_number"]))
            require(row and row["id"] not in references and local["stem"].strip(),
                    f"{paper_id} 本地题号无效、重复或题干为空")
            first, last = local["page"], local["end_page"]
            require(first in pages and last in pages and first <= last,
                    f"{row['id']} 页码范围无效")
            require(local["review_status"] == "candidate_pages_checked"
                    and local["rendering"] == "normalized_from_candidate",
                    f"{row['id']} 本地候选复核类型无效")
            require(all(isinstance(value, str) and value for value in local["formulas"]),
                    f"{row['id']} 公式字段无效")
            if row["kind"] in {"single_choice", "multiple_choice"}:
                options = local["options"]
                require(isinstance(options, dict) and set(options) == set("ABCD")
                        and all(isinstance(value, str) and value.strip() for value in options.values()),
                        f"{row['id']} 本地选项不完整")
            if row["kind"] == "constructed_response":
                parts = local["subquestions"]
                require(parts and len({part["number"] for part in parts}) == len(parts)
                        and all(part["text"].strip() for part in parts),
                        f"{row['id']} 本地子问缺失或重复")
            for asset in local["assets"]:
                page = asset["page"]
                require(first <= page <= last and asset["image"] == pages[page]["image"],
                        f"{row['id']} 图表和题目页码不符")
                x1, y1, x2, y2 = asset["box"]
                require(0 <= x1 < x2 <= pages[page]["width"] and 0 <= y1 < y2 <= pages[page]["height"],
                        f"{row['id']} 图表框超出页图")
            references[row["id"]] = {
                **local, "version": version["version"], "scope": "local_reference",
                "source_id": version["source_id"], "source_url": sources[version["source_id"]]["url"],
                "source_files": version["source_files"],
                "page_images": [pages[number]["image"] for number in range(first, last + 1)],
            }
    return references
