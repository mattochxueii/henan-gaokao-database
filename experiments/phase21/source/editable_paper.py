"""Export the exact reviewed student text with its relative, hash-bound figures."""

import argparse
import json
from pathlib import Path


def editable_student(directory):
    packet = json.loads((directory / "blind-packet.json").read_text(encoding="utf-8"))
    paper = packet["paper"]
    labels = {
        "single_choice": "单项选择题",
        "multiple_choice": "多项选择题",
        "constructed_response": "解答题",
    }
    lines = [f'# {paper["title"]}', "",
             f'满分 {paper["total_points"]} 分，考试时间 {paper["minutes"]} 分钟。', ""]
    previous = None
    for q in paper["questions"]:
        if q["kind"] != previous:
            lines.extend([f'## {labels[q["kind"]]}', ""])
            previous = q["kind"]
        lines.extend([f'### {q["order"]}.（{q["points"]} 分）', "", q["stem"], ""])
        if q["figure"]:
            image = q["figure"]["path"]
            lines.extend([f'![第 {q["order"]} 题图]({image})', ""])
        for key, option in q["options"].items():
            lines.extend([f'{key}．{option}', ""])
        for part in q["parts"]:
            lines.extend([f'{part["label"]}{part["text"]}', ""])
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    (directory / "paper.md").write_text(editable_student(directory), encoding="utf-8")
