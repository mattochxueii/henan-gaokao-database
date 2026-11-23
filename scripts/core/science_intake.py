"""Convert reviewed electronic science questions to the existing local-only bundle."""

from pathlib import Path
import re
from urllib.parse import urlsplit
import shutil
from tempfile import TemporaryDirectory

from PIL import Image

from analysis_db import fingerprint
from core.catalog import import_science, use
from gaokao import digest, read_json, relative_path, require
from local_archive import TABLES, write_bundle
from subjects import SCIENCES


def markdown_questions(path):
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"(?m)^##[ \t]+(\d+)[ \t]*$", text)
    result = {}
    for number, block in zip(blocks[1::2], blocks[2::2], strict=True):
        number = int(number)
        pieces = re.split(r"(?m)^###[ \t]+答案[ \t]*$", block)
        require(number not in result and len(pieces) == 2 and all(x.strip() for x in pieces),
                "Markdown 每题须有唯一的 ## 题号和 ### 答案")
        result[number] = dict(zip(("stem", "answer"), (x.strip() for x in pieces), strict=True))
    require(result, "Markdown 中没有题目")
    return result


def import_electronic(root, path, markdown=None, images=None):
    doc = read_json(path)
    subject, region, year = doc["subject"], doc.get("region", "河南"), doc["year"]
    require(subject in SCIENCES, "电子快导当前接收物理、化学、生物学")
    mappings = use(root, subject, region, year)
    require(len(mappings) == 1 and mappings[0]["status"] == "historical_selective",
            "只可导入已登记为该省当年实际使用的选择性考试卷")
    mapping = mappings[0]
    paper_id = mapping["paper_id"]
    require(doc.get("paper_id", paper_id) == paper_id, "导入文件的试卷身份与卷型不符")
    source = doc["source"]
    require(isinstance(source.get("rights_basis"), str) and source["rights_basis"].strip()
            and isinstance(source.get("title"), str) and source["title"].strip(), "缺少来源标题或本地使用依据")
    if source_url := source.get("url"):
        parsed_url = urlsplit(source_url)
        require(parsed_url.scheme in ("http", "https") and parsed_url.hostname, "来源 URL 无效")
    source_id = doc["dataset_id"] + ":source"
    questions = doc["questions"]
    require(isinstance(questions, list) and questions, "缺少题目")
    source_text = markdown_questions(markdown) if markdown else {}
    if markdown:
        require(source_text.keys() == {x["number"] for x in questions}, "Markdown 与元数据题号不一致")
    tables = {table: [] for table in TABLES}
    tables["papers"].append({"id":paper_id,"subject":subject,"year":year,"series_id":mapping["series_id"],
                             "reported_name":doc["title"],"question_count":len(questions),
                             "component":"selective_provincial","region_id":region,
                             "exam_system_id":mapping["exam_system_id"],"authoring_body":mapping["authoring_body"],
                             "curriculum_id":mapping.get("curriculum_id")})
    tables["paper-regions"].append({"paper_id":paper_id,"subject":subject,"year":year,"region_id":region,
                                    "exam_system_id":mapping["exam_system_id"],"evidence":mapping["evidence"]})
    tables["sources"].append({**source,"id":source_id,"rights":"local_copy_authorized"})
    with TemporaryDirectory(prefix="gaokao-electronic-") as tmp:
        folder = Path(tmp)
        for entry in questions:
            question = {**entry, **source_text.get(entry["number"], {})}
            number = question["number"]
            require(type(number) is int and number > 0, "题号须为正整数")
            typed = question["kind"]
            require(typed in {"single_choice", "multiple_choice", "fill_in", "constructed_response"}, "无效题型")
            stem, parts, answer = question["stem"], question.get("parts", []), question["answer"]
            require(isinstance(stem, str) and stem.strip(), "缺少完整题干")
            require(isinstance(parts, list) and all(isinstance(part, dict)
                    and all(isinstance(part.get(k), str) and part[k].strip() for k in ("label", "text"))
                    for part in parts), "子问须提供题标与完整内容")
            require((isinstance(answer, str) and answer.strip()) or
                    (isinstance(answer, dict) and answer and all(
                        isinstance(v, str) and v.strip() for v in answer.values())), "缺少可读答案")
            options = question.get("options", {})
            if typed in ("single_choice", "multiple_choice"):
                key = answer
                require(isinstance(options, dict) and set(options) == set("ABCD")
                        and all(isinstance(v, str) and v.strip() for v in options.values())
                        and isinstance(key, str) and key and set(key) <= set(options)
                        and len(key) == len(set(key)) and (len(key) == 1) == (typed == "single_choice"),
                        "选择题须含全部选项和有效答案键")
            else:
                require(not options, "非选择题不应提供选择题选项")
            severity = question.get("conflict_severity", "minor")
            require(severity in {"minor", "material"}, "不支持的冲突程度")
            assets = []
            for role, name in [("figure", x) for x in question.get("images", [])] + (
                [("official_page", question["official_page"])] if question.get("official_page") else []
            ):
                require(images is not None, "请指定本地图片目录")
                asset = relative_path(images, name)
                require(asset.is_file() and not asset.is_symlink() and asset.suffix.lower() in (".png", ".jpg", ".jpeg"),
                        "原页或题图缺失，或不是 PNG/JPEG")
                try:
                    with Image.open(asset) as image:
                        require(image.format in ("PNG", "JPEG"), "实际图片格式须为 PNG 或 JPEG")
                        image.verify()
                except OSError as exc:
                    raise ValueError(f"图片无法读取：{name}") from exc
                sha = digest(asset)
                dest = folder / "assets" / (sha + asset.suffix.lower())
                dest.parent.mkdir(exist_ok=True)
                shutil.copyfile(asset, dest)
                assets.append({"path":dest.relative_to(folder).as_posix(),"sha256":sha,"role":role})
            require(not question.get("requires_figure") or any(a["role"] == "figure" for a in assets), "缺少解题必需图表")
            identifier = f"{paper_id}:q{number:03d}"
            payload = {"id":identifier,"stem":question["stem"],"options":options,"parts":question.get("parts",[]),
                       "formulas":question.get("formulas",[]),"asset_refs":assets,"topic":question.get("topic"),
                       "practice_reviewed":True,"conflict_note":question.get("conflict_note"),"conflict_severity":severity}
            if page_sha := next((a["sha256"] for a in assets if a["role"] == "official_page"), None):
                payload["official_page_sha256"] = page_sha
            version = fingerprint(payload)
            tables["questions"].append(payload)
            locator = {"source_id":source_id,"position":question.get("position") or f"电子版第 {number} 题"}
            if "page" in question:
                require(type(question["page"]) is int and question["page"] > 0, "原页页码须为正整数")
                locator["page"] = question["page"]
            tables["occurrences"].append({"id":identifier,"question_id":identifier,"paper_id":paper_id,
                                          "number":number,"points":question["points"],"kind":typed,
                                          "answer_id":identifier+":answer","version_sha256":version,
                                          "source_locator":locator,"content_complete":True})
            tables["answers"].append({"id":identifier+":answer","occurrence_id":identifier,"version_sha256":version,
                                     "payload":question["answer"]})
        write_bundle(folder,doc["dataset_id"],"local-only",tables)
        return import_science(root, folder)
