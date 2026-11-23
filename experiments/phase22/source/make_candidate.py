"""Build the draft and the rewritten papers through the same science simulator."""
import argparse
import json
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(SOURCE.parents[1] / "phase21" / "source"))
from analysis_db import fingerprint
from gaokao import digest, read_json
from make_candidate import parse_markdown


def build(subject, context_file, output, *, draft=False):
    context = read_json(context_file)
    spec = read_json(SOURCE / "author-keys.json")[subject]
    edits = read_json(SOURCE / "draft-edits.json")[subject] if draft else {}
    rows = parse_markdown((SOURCE / f"{subject}.md").read_text(encoding="utf-8"),retain_paragraphs=True)
    questions = []
    for expected, (row, points, answer) in enumerate(
        zip(rows, spec["scores"], spec["answers"], strict=True), 1
    ):
        number, topic, stem, options, parts, figure = row
        if number != expected:
            raise ValueError(f"题号错位：{number}；应为 {expected}")
        if edit := edits.get(str(number)):
            stem, answer = edit["stem"], edit["answer"]
            if "parts" in edit:
                parts = [{"label":p["label"], "text":line} for p,line in zip(parts,edit["parts"],strict=True)]
            if "options" in edit:
                options = dict(zip("ABCD",edit["options"],strict=True))
            figure = None if edit.get("remove_figure") else edit.get("figure",figure)
        if parts:
            answer = dict(zip((p["label"] for p in parts),answer,strict=True))
        questions.append({
            "id": f"orig:{subject}:phase22-q{number:02d}",
            "topic": topic,
            "kind": ("single_choice" if number <= spec["single"] else
                     "multiple_choice" if options else "constructed_response"),
            "points": points, "stem": stem, "options": options, "parts": parts,
            "figure": {"path": figure, "sha256": digest(output.parent / figure)} if figure else None,
            "verification_mode": "independent_review",
            "independent_check": {
                "checks": {"derivation": f"命题端预解对象：{topic}。将数值和条件交独立求解再对照。"},
                "parts": answer if parts else {"overall": f"命题预期选择 {answer}。"},
            },
            "proposed_answer": answer,
        })
    title = {"physics":"河南新高考物理模拟试卷","chemistry":"河南新高考化学模拟试卷"}[subject]
    packet = {
        "subject": subject, "title": title,
        "provenance": {
            "author": "Work 宿主 AI", "revision": "draft" if draft else "rewritten",
            "dna_sha256": context["dna_sha256"], "context_sha256": digest(context_file),
            "quality_reference_sha256": fingerprint(context["quality_benchmarks"]),
        },
        "questions": questions,
    }
    output.write_text(json.dumps(packet,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject",choices=("physics","chemistry"))
    parser.add_argument("context",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--draft",action="store_true")
    args=parser.parse_args()
    build(args.subject,args.context,args.output,draft=args.draft)
