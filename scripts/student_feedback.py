"""Collect pseudonymous observations bound to an immutable published practice paper."""

import argparse
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
        set(row)
        == {
            "participant_code",
            "paper_sha256",
            "question_id",
            "seconds",
            "score",
            "status",
            "error_types",
            "reading_difficulty",
            "method_note",
        },
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
    return row


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
        }
    return {
        "records": len(rows),
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
    args = parser.parse_args()
    try:
        paper_sha, points = checked_questions(args.paper)
        if args.mode == "prepare":
            rows = [validate(row, paper_sha, points) for row in read_lines(args.input)]
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
