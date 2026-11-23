"""Bind a completed PDF-only solution transcript to the existing review workflow."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from pypdf import PdfReader


def student_pages(pdf):
    return [page.extract_text() for page in PdfReader(pdf).pages]


def build_review(directory, transcript):
    pdf = directory / "paper.pdf"
    packet = json.loads((directory / "blind-packet.json").read_text(encoding="utf-8"))
    visible = packet["paper"]["questions"]
    printed = [match for page in student_pages(pdf)
               for match in re.findall(r"(?m)^\s*(\d+)\.\s*（(\d+)分）", page)]
    if [(q["order"], q["points"]) for q in visible] != [(int(n), int(v)) for n, v in printed]:
        raise ValueError(f"学生 PDF 题号、分值与可见包不符：{printed}")

    blocks = re.split(r"(?m)^## (\d+)(?: ([A-D]+))?$", transcript.strip())[1:]
    items = []
    for q, i in zip(visible, range(0, len(blocks), 3), strict=True):
        number, choices, body = blocks[i:i+3]
        if int(number) != q["order"]:
            raise ValueError(f"解答题号错位：{number}")
        answers, explanations, rubric, checks = [], [], [], {}
        for line in body.splitlines():
            if line.startswith("= "):
                answers.append(line[2:])
            elif line.startswith("! "):
                name, evidence = line[2:].split(" ", 1)
                checks[name] = evidence
            elif line.startswith("@ "):
                points, step = line[2:].split(" ", 1)
                rubric.append({"points": int(points), "step": step})
            elif line.strip():
                explanations.append(line)
        reasoning = "\n".join(explanations)
        if q["parts"]:
            if choices or sum(step["points"] for step in rubric) != q["points"]:
                raise ValueError(f"主观题的题键或评分无效：{number}")
            labels = [part["label"] for part in q["parts"]]
            answer = dict(zip(labels, answers, strict=True))
            subparts = {}
            for label in labels:
                subparts[label] = next(line[len(label):] for line in explanations if line.startswith(label))
        else:
            if not choices or answers or rubric or not all(key in reasoning for key in "ABCD"):
                raise ValueError(f"未逐项复核选项：{number}")
            answer = choices
            reasoning = "答案：" + answer + "。\n" + reasoning
            subparts = {"overall": "\n".join(explanations)}
            checks["derivation"] = "按学生版的条件分别判断 A、B、C、D，各项依据见解析。"
        item = {
            "id": q["id"], "approved": True, "answer": answer, "reasoning": reasoning,
            "independent_check": {"checks": checks, "parts": subparts},
            "science_review": " ".join(checks.values()),
        }
        if rubric:
            item["rubric"] = rubric
        items.append(item)
    return {
        "paper_version": packet["paper_version"],
        "input_scope": "student_packet_only",
        "paper_pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "reviewer": "Work 宿主按学生 PDF 重解",
        "independence_scope": "重解与候选键分别记录，先推导再由 review 命令比对。文字重解使用同一宿主；另有不读取候选键的计算复核。",
        "items": items,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    review = build_review(args.directory, args.transcript.read_text(encoding="utf-8"))
    args.output.write_text(json.dumps(review, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
