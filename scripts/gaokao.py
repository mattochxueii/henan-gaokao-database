"""Local catalog, asset intake, and retrieval. Python 3.10+."""
import hashlib
import json
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from datetime import date
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CODE = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
SUBJECTS = dict(zip(("chinese", "math", "english", "physics", "chemistry", "biology"),
                    ("语文", "数学", "英语", "物理", "化学", "生物学")))
STATES = ("已发现来源", "已获取原始资料", "已解析", "已自动校验", "已人工核验", "存在问题")
ROLES = {
    "paper": ".local-data/intake/originals", "answer": ".local-data/intake/answers",
    "explanation": ".local-data/intake/answers", "image": ".local-data/intake/assets",
    "listening_questions": ".local-data/intake/assets",
    "listening_transcript": ".local-data/intake/assets", "listening_audio": ".local-data/intake/assets",
}
FORMATS = {
    "paper": {"pdf", "docx", "doc", "png", "jpg", "jpeg", "tif", "tiff", "webp"},
    "answer": {"pdf", "docx", "doc", "txt", "md", "png", "jpg"},
    "explanation": {"pdf", "docx", "doc", "txt", "md"},
    "image": {"png", "jpg", "jpeg", "tif", "tiff", "webp"},
    "listening_questions": {"pdf", "docx", "txt"},
    "listening_transcript": {"pdf", "docx", "txt", "md"},
    "listening_audio": {"mp3", "wav", "m4a", "ogg", "flac"},
}
QUESTION_FIELDS = set(("id paper_id original_number order kind stem options formulas asset_refs "
                       "points reference_answer explanation knowledge_points difficulty intent "
                       "confidence review_status source_ids record_type source_locator").split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_lines(path):
    with path.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except ValueError as error:
                    raise ValueError(f"{path}:{number}: {error}") from error


def dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        stream.write(content.encode("utf-8"))
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def write_json(path, value):
    atomic_write(path, dumps(value) + "\n")


@contextmanager
def intake_lock(root):
    lock = root / "data/metadata" / ".intake.lock"
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError("另一项登记正在运行，或上次进程异常退出，请参阅 README") from error
    try:
        yield
    finally:
        lock.rmdir()


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else digest_stream(stream)


def digest_stream(stream):
    sha = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        sha.update(chunk)
    return sha.hexdigest()


def date_value(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), "日期须为 YYYY-MM-DD")
    date.fromisoformat(value)


def relative_path(root, value):
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
            and ":" not in value and path.parts, f"无效相对路径 {value}")
    target = root.joinpath(*path.parts)
    require(target.resolve().is_relative_to(root.resolve()), f"路径超出仓库 {value}")
    return target


def source_catalog(root):
    sources = {}
    for source in read_lines(root / "data/metadata" / "sources.jsonl"):
        key = source["id"]
        require(CODE.fullmatch(key) and key not in sources, f"重复或无效来源 ID {key}")
        url = urlsplit(source["url"])
        require(url.scheme in {"http", "https"} and url.hostname, f"来源 URL 无效 {key}")
        date_value(source["accessed_on"])
        require(all(source[name] for name in ("title", "publisher", "tier", "access", "rights_status", "note")),
                f"来源信息不全 {key}")
        sources[key] = source
    return sources


def paper_key(paper):
    return f"{paper['year']}-{paper['scope']}-{paper['subject']}-{paper['edition']}"


def validate_paper(paper, sources):
    key = paper["id"]
    require(paper["schema_version"] == 1, f"{key} 数据版本不受支持")
    require(type(paper["year"]) is int and 1900 <= paper["year"] <= 9999, f"{key} 年份无效")
    require(all(CODE.fullmatch(paper[name]) for name in ("scope", "subject", "edition")), f"{key} 编码无效")
    require(key == paper_key(paper), f"试卷 ID 应为 {paper_key(paper)}")
    require(paper["exam_kind"] in {"national_unified", "provincial_selective"}
            and paper["session"] == "main", f"{key} 核心目录仅接受正式主考卷")
    require(paper["identity_status"] == "verified_for_listed_regions" and paper["regions"]
            and all(CODE.fullmatch(region) for region in paper["regions"]),
            f"{key} 地区归属尚未核实")
    require(all(paper[field] for field in ("formal_title", "title_basis", "edition_label", "regime", "authoring_body",
                                           "identity_note")), f"{key} 试卷身份信息不全")
    date_value(paper["researched_on"])
    evidence = paper["attribution_sources"]
    require(len(set(evidence)) >= 2 and all(item in sources for item in evidence)
            and any(sources[item]["tier"] == "official" for item in evidence), f"{key} 缺少归属交叉证据")
    require({"paper", "answer", "explanation", "image"} <= paper["materials"].keys(),
            f"{key} 缺少基础资料状态")
    for role, entry in paper["materials"].items():
        require(role in ROLES and entry["state"] in {"linked", "not_found", "partial"}
                and entry["note"] and all(item in sources for item in entry["source_ids"]),
                f"{key} 资料项无效 {role}")
        require(bool(entry["source_ids"]) == (entry["state"] != "not_found"),
                f"{key} 候选状态与来源不一致 {role}")
    for issue in paper.get("issues", []):
        require(issue["source_ids"] and all(item in sources for item in issue["source_ids"])
                and issue["detail"] and issue["disposition"], f"{key} 差异记录缺少证据或处理说明")


def load_papers(root, sources):
    papers = {}
    for path in sorted((root / "data/metadata" / "papers").glob("*.json")):
        paper = read_json(path)
        validate_paper(paper, sources)
        require(path.stem == paper["id"], f"文件名与 ID 不符 {path.name}")
        papers[paper["id"]] = paper
    return papers


def validate_receipt(receipt, paper, sources):
    key = paper["id"]
    require(receipt["role"] in paper["materials"], f"{key} 未定义该资料类别")
    require(receipt["source_id"] in sources, "资料来源未登记")
    date_value(receipt["acquired_on"])
    require(receipt["rights"] in {"licensed", "public_domain", "rightsholder_permission"}
            and bool(receipt["evidence"].strip()) and bool(receipt["rights_holder"].strip())
            and receipt["allow_local_storage"] is True and type(receipt["allow_redistribution"]) is bool,
            "需登记权利人、适用本文件的许可依据和明确的本地保存权限")
    require(type(receipt["allow_derivatives"]) is bool, "需分别标明派生处理权限")
    require(receipt.get("coverage", "unknown") in {"complete", "partial", "unknown"}, "资料覆盖状态无效")
    require(receipt["variant"] in {"official_original", "scan", "retypeset", "third_party",
                                   "supporting_material"}, "资料版本类型无效")
    require(receipt["variant"] != "official_original" or sources[receipt["source_id"]]["tier"] == "official",
            "官方原卷必须来自官方渠道")
    if receipt["role"] in {"answer", "explanation"}:
        require(receipt["authority"] in {"official", "third_party"}, "答案或解析须区分发布者")
        require(receipt["authority"] != "official" or sources[receipt["source_id"]]["tier"] == "official",
                "仅经核实的官方发布渠道可标官方")


def file_records(root, papers, sources, check_hash=False):
    records = []
    blobs = {}
    for path in sorted((root / "data/metadata" / "files").glob("*.json")):
        record = read_json(path)
        key, sha, role = record["paper_id"], record["sha256"], record["role"]
        require(key in papers and SHA256.fullmatch(sha), f"文件归属或哈希无效 {path.name}")
        validate_receipt(record, papers[key], sources)
        require(record["id"] == f"{key}--{role}--{sha}" == path.stem, f"文件登记 ID 无效 {path.name}")
        extension = record["format"]
        require(extension in FORMATS[role], f"文件格式无效 {path.name}")
        target = relative_path(root, record["path"])
        require(target.suffix == "." + extension and target.stem == sha
                and PurePosixPath(record["path"]).parent.is_relative_to(PurePosixPath(ROLES[role])),
                f"文件保存路径无效 {path.name}")
        require(target.is_file() and target.stat().st_size == record["bytes"] > 0,
                f"文件丢失或大小不符 {target}")
        require(blobs.setdefault(sha, target) == target, f"相同 SHA-256 引用多个存储位置 {sha}")
        if check_hash:
            require(digest(target) == sha, f"SHA-256 不符 {target}")
        records.append(record)
    return records


def questions(root, papers, sources, records):
    assets = {entry["id"]: entry for entry in records if entry["role"] == "image"}
    permitted = {entry["id"]: entry for entry in records if entry["allow_derivatives"]}
    result = []
    for path in sorted((root / "data/questions").glob("*/*/*.jsonl")):
        key = path.stem
        require(key in papers, f"题目所属试卷不存在 {key}")
        paper = papers[key]
        require(path == root / "data/questions" / str(paper["year"]) / paper["subject"] / f"{key}.jsonl",
                f"题目文件分类错误 {path}")
        seen = set()
        points = 0
        all_scored = True
        entries = list(read_lines(path))
        for order, entry in enumerate(entries, 1):
            require(QUESTION_FIELDS <= entry.keys(), f"{path}:{order} 缺少题目字段")
            number = entry["original_number"]
            require(isinstance(number, str) and number and number not in seen and entry["order"] == order
                    and entry["paper_id"] == key and entry["id"] == f"{key}:q{order:03}",
                    f"{path}:{order} 题号、顺序、归属或 ID 无效")
            seen.add(number)
            require(entry["review_status"] in STATES and entry["source_ids"]
                    and all(source in sources for source in entry["source_ids"]), f"{entry['id']} 缺少审核状态或来源")
            require(isinstance(entry["asset_refs"], list)
                    and all(ref in assets and assets[ref]["paper_id"] == key for ref in entry["asset_refs"]),
                    f"{entry['id']} 存在未登记或错卷的图像")
            score = entry["points"]
            require(score is None or (type(score) in {int, float} and 0 < score <= 150),
                    f"{entry['id']} 分值无效")
            if score is None:
                all_scored = False
            else:
                points += score
            if entry["record_type"] == "index_only":
                require(entry["review_status"] == "已发现来源" and not entry["asset_refs"]
                        and all(entry[field] is None for field in ("stem", "options", "formulas",
                                "reference_answer", "explanation", "knowledge_points", "difficulty", "intent")),
                        f"{entry['id']} 索引记录不得夹带全文或分析")
            else:
                locator = entry["source_locator"] or {}
                parent = permitted.get(locator.get("file_id"))
                require(entry["record_type"] == "transcribed" and parent and parent["role"] == "paper"
                        and parent["paper_id"] == key and parent["source_id"] in entry["source_ids"]
                        and isinstance(entry["stem"], str) and entry["stem"].strip()
                        and entry["review_status"] != "已发现来源" and type(locator.get("page")) is int
                        and locator["page"] > 0,
                        f"{entry['id']} 转写需具备合法可处理原卷、题干和原卷定位")
                for field, role in (("reference_answer", "answer"), ("explanation", "explanation")):
                    if entry[field] is not None:
                        supplement = permitted.get(entry.get(f"{role}_file_id"))
                        require(supplement and supplement["role"] == role and supplement["paper_id"] == key
                                and supplement["source_id"] in entry["source_ids"],
                                f"{entry['id']} {field} 缺少可派生的资料登记")
                if entry["review_status"] == "已人工核验":
                    require(entry.get("reviewer") and entry.get("reviewed_on") and entry.get("review_note"),
                            f"{entry['id']} 人工核验缺少审核记录")
                    date_value(entry["reviewed_on"])
            if entry.get("content_complete", False):
                require(entry["content_complete"] is True and entry["record_type"] == "transcribed"
                        and entry["review_status"] == "已人工核验",
                        f"{entry['id']} 标为完整题面前须完成原卷人工核验")
                if entry["kind"] in {"single_choice", "multiple_choice"}:
                    require(isinstance(entry["options"], (dict, list)) and len(entry["options"]) >= 2,
                            f"{entry['id']} 完整选择题须有选项")
        expected = paper.get("expected_questions")
        if expected is not None:
            require(len(entries) <= expected, f"{key} 超出已知题数")
        if entries and len(entries) == expected and all_scored and paper.get("max_points") is not None:
            require(abs(points - paper["max_points"]) < 0.0001, f"{key} 整卷分值不符")
        result.extend(entries)
    return result


def load_solutions(root, entries, sources):
    path = root / "data/metadata" / "independent-solutions.jsonl"
    if not path.exists():
        return {}
    known = {entry["id"] for entry in entries}
    solutions = {}
    for row in read_lines(path):
        key = row["question_id"]
        require(key in known and key not in solutions, f"独立解答题号无效或重复 {key}")
        require(row["status"] in {"independently_derived", "conditional_on_candidate"}
                and row["result"] and row["steps"] and row["scope"], f"{key} 独立解答缺少结果、推导或条件")
        require(row["evidence"] and all(locator["source_id"] in sources and locator["location"]
                                       for locator in row["evidence"]), f"{key} 独立解答缺少题面定位")
        solutions[key] = row
    return solutions


def load(root, check_hash=False):
    sources = source_catalog(root)
    papers = load_papers(root, sources)
    files = file_records(root, papers, sources, check_hash)
    return sources, papers, files, questions(root, papers, sources, files)


def register(root, manifest):
    paper = read_json(manifest)
    with intake_lock(root):
        validate_paper(paper, source_catalog(root))
        target = root / "data/metadata" / "papers" / f"{paper['id']}.json"
        if target.exists():
            require(read_json(target) == paper, "试卷 ID 已登记且内容不同，请审阅后修改现有记录")
        else:
            write_json(target, paper)
    return paper["id"]


def import_file(root, key, path, receipt_path):
    receipt = read_json(receipt_path)
    with intake_lock(root):
        sources, papers, records, _ = load(root)
        require(key in papers, f"试卷未登记 {key}")
        paper = papers[key]
        validate_receipt(receipt, paper, sources)
        role = receipt["role"]
        extension = path.suffix.lower().lstrip(".")
        require(extension in FORMATS[role] and path.is_file() and path.stat().st_size > 0, "文件缺失、为空或格式不受支持")
        if extension == "pdf":
            with path.open("rb") as stream:
                require(stream.read(5) == b"%PDF-", "文件扩展名为 PDF，但文件头不匹配")
        sha = digest(path)
        identifier = f"{key}--{role}--{sha}"
        manifest = root / "data/metadata" / "files" / f"{identifier}.json"
        if manifest.exists():
            existing = read_json(manifest)
            require(all(existing.get(name) == value for name, value in receipt.items()),
                    "文件已登记但收据不同，请审阅现有记录")
            require(digest(relative_path(root, existing["path"])) == sha, "已登记文件校验失败")
            return existing
        match = next((record for record in records if record["sha256"] == sha), None)
        if match:
            require(match["format"] == extension, "相同内容使用了不同扩展名，请检查文件格式")
            target = relative_path(root, match["path"])
        else:
            target = root / ROLES[role] / str(paper["year"]) / paper["subject"] / key / f"{sha}.{extension}"
        require(target.resolve().is_relative_to(root.resolve()), "文件路径超出仓库")
        if target.exists():
            require(digest(target) == sha, "现有文件校验失败，请检查磁盘内容")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                temp = Path(stream.name)
            try:
                shutil.copyfile(path, temp)
                require(digest(temp) == sha, "复制期间源文件改变，请重新登记")
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        record = {
            **receipt, "id": identifier, "paper_id": key, "sha256": sha,
            "format": extension, "path": target.relative_to(root).as_posix(),
            "bytes": target.stat().st_size, "original_filename": path.name,
        }
        write_json(manifest, record)
        return record
