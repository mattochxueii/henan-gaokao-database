"""Explicit subject dispatch. Each science owns its model semantics."""

from importlib import import_module

SCIENCES = ("physics", "chemistry", "biology")
SUBJECTS = {
    "chinese": "语文", "math": "数学", "english": "英语",
    "physics": "物理", "chemistry": "化学", "biology": "生物学",
}


def science_verifier(subject):
    if subject not in SCIENCES:
        raise ValueError("该学科须使用其专用验证入口")
    return import_module("subjects." + subject).verify
