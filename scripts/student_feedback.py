"""Collect pseudonymous observations bound to an immutable published practice paper."""

import argparse
import csv
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import bootstrap  # noqa: F401
from gaokao import dumps, read_json, read_lines, require
from mathgen.exam_workflow import verify_certificate

ERRORS = ("concept", "model", "calculation", "logic", "reading", "time", "other")
STATUSES = ("correct", "partial", "incorrect", "unfinished")
CODE = re.compile(r"[a-zA-Z0-9_-]{4,32}\Z")
REQUIRED = {
    "participant_code", "paper_sha256", "question_id", "seconds", "score",
    "status", "error_types", "reading_difficulty", "method_note",
}
OPTIONAL = {"ambiguity_reported", "explanation_clarity"}
CSV_FIELDS = (
    "paper_id", "paper_sha256", "number", "question_id", "participant_code",
    "seconds", "score", "status", "error_types", "reading_difficulty",
    "ambiguity_reported", "explanation_clarity", "method_note",
)


def checked_questions(paper_dir):
    certificate = read_json(paper_dir / "publication.json")
    require(certificate.get("published") is True, "反馈须对应已审核题卷")
    verify_certificate(paper_dir, certificate)
    return certificate["pdf_sha256"], {
        q["id"]: q["points"]
        for q in read_json(paper_dir / "student-text.json")["questions"]
    }


def validate(row, paper_sha, questions):
    require(
        REQUIRED <= set(row) <= REQUIRED | OPTIONAL,
        "反馈字段不符，请勿加入身份信息",
    )
    require(
        isinstance(row["participant_code"], str)
        and CODE.fullmatch(row["participant_code"]),
        "请用研究方分配的匿名代码",
    )
    require(
        row["paper_sha256"] == paper_sha and row["question_id"] in questions,
        "反馈与题卷版本不符",
    )
    points = questions[row["question_id"]]
    seconds, score, status = row["seconds"], row["score"], row["status"]
    require(type(seconds) is int and 0 <= seconds <= 21600, "用时须为0至21600秒")
    require(
        type(score) in (int, float) and math.isfinite(score) and 0 <= score <= points,
        "得分不在该题分值范围内",
    )
    require(status in STATUSES, "作答状态不正确")
    require(
        (status == "correct" and score == points)
        or (status == "partial" and 0 < score < points)
        or (status == "incorrect" and score == 0)
        or (status == "unfinished" and score < points),
        "得分与作答状态矛盾",
    )
    errors = row["error_types"]
    require(
        isinstance(errors, list) and all(x in ERRORS for x in errors),
        "错误类型不受支持",
    )
    require(len(errors) == len(set(errors)), "错误类型重复")
    require(
        type(row["reading_difficulty"]) is int and 0 <= row["reading_difficulty"] <= 3,
        "题意困难程度为0至3",
    )
    require(
        isinstance(row["method_note"], str) and len(row["method_note"]) <= 1000,
        "解题思路过长",
    )
    if "ambiguity_reported" in row:
        require(type(row["ambiguity_reported"]) is bool, "歧义字段须为布尔值")
    if "explanation_clarity" in row:
        value = row["explanation_clarity"]
        require(type(value) is int and 0 <= value <= 3, "解析理解程度为0至3")
    return row


def paper_layout(paper_dir):
    document = read_json(paper_dir / "raw-ai-candidate.json")
    return (
        document["paper"].get("study_id", document["paper"]["title"]),
        {str(q["order"]): q["id"] for q in document["questions"]},
    )


def make_csv(path, paper_id, paper_sha, numbers):
    with path.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for number, qid in numbers.items():
            writer.writerow({
                "paper_id": paper_id, "paper_sha256": paper_sha,
                "number": number, "question_id": qid,
            })


def csv_rows(path, paper_id, paper_sha, numbers):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == list(CSV_FIELDS), "请保留CSV列名")
        for row in reader:
            require(None not in row and all(v is not None for v in row.values()), "CSV列数不符")
            require(
                row["paper_id"] == paper_id and row["paper_sha256"] == paper_sha
                and numbers.get(row["number"]) == row["question_id"],
                "CSV题号或试卷版本不符",
            )
            entry = {k: row[k] for k in REQUIRED}
            response_keys = REQUIRED - {"paper_sha256", "question_id"}
            if not any(row[k] for k in response_keys | OPTIONAL):
                continue
            for k in ("seconds", "reading_difficulty"):
                entry[k] = int(row[k])
            entry["score"] = float(row["score"])
            entry["error_types"] = [v.strip() for v in row["error_types"].split("|") if v.strip()]
            if row["ambiguity_reported"]:
                require(row["ambiguity_reported"] in ("0", "1"), "歧义字段填写0或1")
                entry["ambiguity_reported"] = row["ambiguity_reported"] == "1"
            if row["explanation_clarity"]:
                entry["explanation_clarity"] = int(row["explanation_clarity"])
            yield entry


def summary(rows, points, min_sample=10):
    from statistics import median

    require(min_sample >= 10, "小于10人的样本只可报告原始记录")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["question_id"]].append(row)
    result = {}
    for qid, records in grouped.items():
        n = len(records)
        correct = sum(r["status"] == "correct" for r in records)
        ratio = sum(r["score"] for r in records) / (n * points[qid])
        adjustment = None
        ambiguity = [r["ambiguity_reported"] for r in records if "ambiguity_reported" in r]
        clarity = [r["explanation_clarity"] for r in records if "explanation_clarity" in r]
        if n >= min_sample:
            adjustment = (
                "复查是否过难"
                if ratio < 0.35
                else "复查是否过易"
                if ratio >= 0.85
                else "暂保留编辑判断"
            )
        result[qid] = {
            "n": n,
            "full_score_count": correct,
            "unfinished_count": sum(r["status"] == "unfinished" for r in records),
            "observed_score_ratio": ratio,
            "median_seconds": median(r["seconds"] for r in records),
            "error_counts": {
                e: sum(e in r["error_types"] for r in records) for e in ERRORS
            },
            "reading_difficulty_median": median(
                r["reading_difficulty"] for r in records
            ),
            "calibration_hint": adjustment,
            "ambiguity_responses": len(ambiguity),
            "ambiguity_reports": sum(ambiguity),
            "explanation_clarity_responses": len(clarity),
            "explanation_clarity_median": median(clarity) if clarity else None,
        }
    return {
        "records": len(rows),
        "participants": len({r["participant_code"] for r in rows}),
        "questions": result,
        "scope": "仅反映录入样本；无真实数据时输出0条，无正式难度标定",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paper", type=Path)
    modes = parser.add_subparsers(dest="mode", required=True)
    intake = modes.add_parser("prepare")
    intake.add_argument("input", type=Path, help="本地 JSONL，逐题逐作答")
    intake.add_argument("output", type=Path, help="新本地反馈文件")
    report = modes.add_parser("summary")
    report.add_argument("feedback", type=Path)
    report.add_argument("--min-sample", type=int, default=10)
    form = modes.add_parser("blank-csv")
    form.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        paper_sha, points = checked_questions(args.paper)
        if args.mode == "blank-csv":
            paper_id, numbers = paper_layout(args.paper)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            make_csv(args.output, paper_id, paper_sha, numbers)
            print(dumps({"paper_id": paper_id, "paper_sha256": paper_sha, "records": 0}))
            return 0
        if args.mode == "prepare":
            if args.input.suffix.lower() == ".csv":
                paper_id, numbers = paper_layout(args.paper)
                source = csv_rows(args.input, paper_id, paper_sha, numbers)
            else:
                source = read_lines(args.input)
            rows = [validate(row, paper_sha, points) for row in source]
        else:
            rows = [
                validate(row, paper_sha, points) for row in read_json(args.feedback)
            ]
        keys = {(r["participant_code"], r["question_id"]) for r in rows}
        require(len(keys) == len(rows), "同一匿名参与者同一题只能登记一次")
        if args.mode == "prepare":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf8") as target:
                target.write(dumps(rows) + "\n")
        result = summary(rows, points, getattr(args, "min_sample", 10))
        print(dumps(result))
        return 0
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(dumps({"error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
