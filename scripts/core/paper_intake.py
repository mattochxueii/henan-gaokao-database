"""Plain-text paper store shared by research and authoring."""
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit
import re
import shutil

from analysis_db import fingerprint
from gaokao import digest, read_json, relative_path, require
from storage import atomic_json
from subjects import SCIENCES

CORE = ("math", "chinese", "english")
PAPER_SUBJECTS = (*CORE, *SCIENCES)
PUBLIC = Path("data/papers")
LOCAL = Path(".local-data/papers")
SAFE_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,99}\Z")


def archive_questions(questions):
    """Remove only derivatives from a comparison with the old local math snapshot."""
    normalized = []
    for q in questions:
        row = {**q, "asset_refs":[{k:v for k,v in asset.items() if k not in ("plaintext_path","plaintext_sha256")}
                                 for asset in q.get("asset_refs",[])]}
        if row.pop("practice_review",None):
            row["usable_for_practice"] = False
        normalized.append(row)
    return normalized


def listening_fingerprint(doc):
    return fingerprint({key: doc[key] for key in
                        ("listening_groups", "listening_transcript", "listening_source")})


def documents(root, subject):
    by_id = {}
    for base in (PUBLIC, LOCAL):
        for path in sorted((root / base / subject).glob("*.json")):
            doc = read_json(path)
            require(doc["subject"] == subject and doc["content_sha256"] == fingerprint(doc["questions"]),
                    "明文库校验失败：" + str(path))
            if "listening_sha256" in doc:
                require(doc["listening_sha256"] == listening_fingerprint(doc),
                        "听力文本或来源校验失败：" + str(path))
            if prior := by_id.get(doc["id"]):
                previous = prior[1]
                same = previous["content_sha256"] == doc["content_sha256"]
                if not same and previous.get("compatibility") == doc.get("compatibility") == "national-math-v1":
                    same = archive_questions(previous["questions"]) == archive_questions(doc["questions"])
                require(prior[0].is_relative_to(root / PUBLIC) and base == LOCAL and same,
                        "重复或冲突的明文试卷：" + doc["id"])
                continue
            by_id[doc["id"]] = (path, doc)
    return list(by_id.values())


def ingest(root, doc, markdown=None, images=None, *, track=False):
    from core.science_intake import markdown_questions, validate_plain_identity, validate_plain_question
    doc = {**doc}
    subject, year, identifier = doc["subject"], doc["year"], doc["id"]
    science = subject in SCIENCES
    require(subject in PAPER_SUBJECTS and SAFE_ID.fullmatch(identifier) and type(year) is int and 1952 <= year <= 2100,
            "明文卷须有合法的学科、年份及稳定ID")
    require(doc["exam_kind"] in ("official_exam", "adaptation_exam"), "适应性演练须单独分类")
    require(doc["series_id"] and doc["title"] and isinstance(doc["regions"], list) and doc["regions"],
            "缺卷系、卷名或适用地区")
    source = dict(doc["source"])
    url = urlsplit(source["url"])
    require(source["title"].strip() and url.scheme in ("http", "https") and url.hostname,
            "缺少来源标题或可追溯网址")
    source["rights_basis"] = "仅用于个人学习与教研归档"
    doc["source"] = source
    require(not any(d["id"] == identifier for _, d in documents(root, subject)), "该试卷已导入")
    questions = doc["questions"]
    from_text = markdown_questions(markdown) if markdown else {}
    require(not markdown or set(from_text) == {q["number"] for q in questions}, "Markdown题号不匹配")
    first = 21 if subject=="english" and doc.get("written_only") is True and questions and questions[0]["number"]==21 else 1
    require(type(doc["question_count"]) is int and doc["question_count"] > 0, "缺少已核题数")
    numbers = list(range(first, first + doc["question_count"]))
    missing = doc.get("missing_numbers", [])
    require(isinstance(missing,list) and (not missing or science) and missing == sorted(set(missing))
            and all(type(n) is int and n in numbers for n in missing), "缺题清单无效")
    require(questions and [q["number"] for q in questions] == [n for n in numbers if n not in missing],
            "题号与已核题量或缺题清单不符")
    if science:
        validate_plain_identity(root, doc)
    if (subject in ("chinese","english")
            and doc["series_id"] == "cn-new-gaokao-1" and doc["exam_kind"] == "official_exam"
            and "河南" in doc["regions"] and year in (2024,2025,2026)):
        from core.language_workflow import plan
        blueprint=plan(root,subject,"河南",year)
        scores=[x for section in blueprint["sections"] for x in section["scores"]]
        require([q["points"] for q in questions] == scores[first-1:], "该卷题量或逐题分值与历史蓝图不符")
    doc["distribution"] = "private-research" if track else "local-only"
    path = root / (PUBLIC if track else LOCAL) / subject / (identifier + ".json")
    passages = doc.get("passages", {})
    require(isinstance(passages, dict) and all(isinstance(v, str) and v.strip() for v in passages.values()),
            "阅读材料必须完整")
    require(subject != "english" or doc.get("listening_transcript") or doc.get("written_only") is True,
            "英语完整卷缺听力文本")
    assets = {}
    normalized = []
    for raw in questions:
        q = {**raw, **from_text.get(raw["number"], {})}
        answer = q.get("answer")
        answer_missing = answer in (None,"",{},[])
        require(isinstance(q["stem"], str) and q["stem"].strip()
                and (not answer_missing or (science and q.get("missing_answer") is True))
                and ((type(q["points"]) in (int,float) and q["points"] > 0)
                     or (science and q["points"] is None and q.get("missing_points") is True)),
                "题面、答案或分值不完整")
        require(not q.get("passage") or q["passage"] in passages, "缺共享阅读材料")
        require(q.get("position") or q.get("page"), "须提供原题来源定位")
        options = q.get("options", {})
        if science:
            validate_plain_question(q, answer_missing)
        elif q["kind"] == "single_choice":
            require(isinstance(options, dict) and len(options) >= 3 and answer in options
                    and all(isinstance(o, str) and o.strip() for o in options.values()), "客观题缺选项或答案无效")
        refs = []
        for name in q.pop("images", []):
            require(images is not None, "须指定本地图件目录")
            image = relative_path(images, name)
            require(image.is_file() and not image.is_symlink() and image.suffix.lower() in (".png",".jpg",".jpeg")
                    and image.stat().st_size <= 2_000_000, "只接受轻量PNG/JPEG图件")
            from PIL import Image
            with Image.open(image) as img:
                require(img.format in ("PNG", "JPEG"), "题图格式不符")
                img.verify()
            sha = digest(image)
            file = "assets/" + sha + image.suffix.lower()
            assets[file] = image
            ref = {"path": file, "sha256": sha}
            if caption := q.get("image_captions",{}).get(name):
                ref["caption"] = caption
            refs.append(ref)
        q.pop("image_captions", None)
        if science and q.get("requires_figure") and not refs:
            q["missing_figure"] = True
        else:
            require(science or not q.get("requires_figure") or refs, "缺必要图件")
        q.update(asset_refs=refs, id=f'{identifier}:q{q["number"]:03d}',
                 usable_for_practice=q.get("conflict_severity") != "material"
                 and not (science and (q.get("missing_figure") or q.get("missing_answer") or
                                       q.get("missing_points") or q.get("incomplete_text"))),
                 source_and_solution_reviewed=False)
        q["version_sha256"] = fingerprint(q)
        normalized.append(q)
    actual = sum(q["points"] or 0 for q in normalized)
    unknown_points = missing or any(q.get("missing_points") for q in normalized)
    require((actual < doc["points"] if unknown_points else actual == doc["points"]), "分值总和不符")
    doc["questions"] = normalized
    doc["content_sha256"] = fingerprint(normalized)
    for file, image in assets.items():
        dest = path.parent / file
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            shutil.copyfile(image,dest)
        require(digest(dest) == digest(image), "题图校验失败")
    atomic_json(path,doc)
    return {"installed":len(normalized),"path":path.relative_to(root).as_posix(),
            "eligible":sum(q["usable_for_practice"] for q in normalized)}


def research(root, subject, *, year=None, region=None, topic=None, limit=10,
             verified_only=False, exam_kind="official_exam", exclude_compatible_math=False,
             include_incomplete=False):
    from national_quality import practice_view

    result = []
    for path, doc in documents(root, subject):
        if exclude_compatible_math and doc.get("compatibility") == "national-math-v1":
            continue
        if ((year is not None and doc["year"] != year) or (region and region not in doc["regions"])
                or doc["exam_kind"] != exam_kind):
            continue
        for q in doc["questions"]:
            if ((not include_incomplete and not q.get("usable_for_practice", False))
                    or (verified_only and not q.get("source_and_solution_reviewed"))):
                continue
            if topic and not any(topic in str(q.get(field, "")) for field in ("topic","features","stem")):
                continue
            result.append({**practice_view(q), "subject":subject, "year":doc["year"], "paper_id":doc["id"],
                           "source":doc["source"], "record_type":"full_text",
                           **({"region":doc["regions"][0], "regions":doc["regions"],"series_id":doc["series_id"],
                               "exam_kind":doc["exam_kind"]} if subject in SCIENCES else {}),
                           "passage_text":doc.get("passages",{}).get(q.get("passage")),
                            "listening_text":doc.get("listening_transcript",{}).get(q.get("listen_group")),
                           "asset_root":path.parent.relative_to(root).as_posix()})
    return result[:limit]


def dna(root, subject, *, tracked_only=False):
    from core.paper_dna import official_first_profiles
    stats = {}
    times = Counter()
    references = []
    files = [(path,doc) for path,doc in documents(root,subject)
             if not tracked_only or path.is_relative_to(root / PUBLIC)]
    if subject in SCIENCES:
        from core.science_dna import science_profile
        return science_profile(subject, [paper for _, paper in files])
    for _, paper in files:
        if paper["exam_kind"] != "official_exam":
            continue
        for q in paper["questions"]:
            if not q.get("usable_for_practice"):
                continue
            entry = stats.setdefault(q["number"], {
                "topics": Counter(), "kinds": Counter(), "features": Counter(), "points": Counter(),
                "scores": Counter(), "texts": [],
            })
            for val in q.get("features", []):
                entry["features"][val] += 1
            entry["topics"].update(q.get("topic_flags", []))
            if q.get("topic"):
                entry["topics"][q["topic"]] += 1
            entry["kinds"][q["kind"]] += 1
            entry["points"][str(q["points"])] += 1
            if rubric := q.get("rubric"):
                entry["scores"][str(len(rubric))] += 1
            if p := paper.get("passages",{}).get(q.get("passage")):
                length = len(p.split()) if subject == "english" else len(re.sub(r"\s","",p))
                entry["texts"].append(length)
            times[str(paper["year"])] += 1
            references.append({"paper_id":paper["id"], "number":q["number"], "version_sha256":q["version_sha256"]})
    for position in stats.values():
        lengths=position.pop("texts")
        position["passage_length_range"] = [min(lengths), max(lengths)] if lengths else None
    return {"subject":subject,"eligible_rows_by_year":times,"positions":stats,"references":references,
            "tags_are_editorial":True,
            "national_first_profile":official_first_profiles(subject, [paper for _, paper in files]),
            "scope":"仅统计可读完整题及现有审定的结构标签；无标注不推断难度、考点或干扰项。"}
