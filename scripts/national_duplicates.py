"""Content-backed identity and adaptation suggestions; never merge by file name or topic."""

import bootstrap  # noqa: F401
import json, re, itertools, difflib, hashlib
from collections import defaultdict
from gaokao import ROOT
from national_db import rows
from storage import atomic_json


def condition_skeleton(text):
    # Keep inequalities, operators, quantifiers and names. Only concrete numerals change.
    value = re.sub(r"\s+", "", text)
    return re.sub(r"(?<![A-Za-z])\d+(?:\.\d+)?", "#", value)


def compare(data):
    masters = {r["id"]: r for r in data}
    buckets = defaultdict(list)
    for r in masters.values():
        skeleton = condition_skeleton(r.get("raw_problem_latex", r["stem"]))
        chinese = "".join(re.findall(r"[\u4e00-\u9fff]", skeleton))
        if len(chinese) >= 12:
            buckets[(r["kind"], chinese)].append((r, skeleton))
    suggestions = []
    for bucket in buckets.values():
        for (a, sa), (b, sb) in itertools.combinations(bucket, 2):
            if a["id"] == b["id"]:
                continue
            score = difflib.SequenceMatcher(None, sa, sb, autojunk=False).ratio()
            if score >= 0.9:
                suggestions.append(
                    {
                        "left_id": a["id"],
                        "right_id": b["id"],
                        "skeleton_similarity": round(score, 4),
                        "relationship": "possible_adaptation_or_version_needs_review",
                        "auto_merged": False,
                        "limits": "相同中文条件骨架及数值归一相似，只提示复核；不是数学等价证明",
                    }
                )
    bypaper = defaultdict(list)
    for r in data:
        bypaper[r["paper_id"]].append(r)
    paper_groups = defaultdict(list)
    for pid, group in bypaper.items():
        value = [
            (
                r["number"],
                r["kind"],
                r["points"],
                r.get("content_sha256", r["version_sha256"]),
            )
            for r in sorted(group, key=lambda x: x["number"])
        ]
        signature = hashlib.sha256(json.dumps(value).encode()).hexdigest()
        paper_groups[(group[0]["year"], group[0]["subject"], signature)].append(pid)
    return {
        "questions_compared": len(masters),
        "paper_instances_compared": len(bypaper),
        "identical_content_paper_suggestions": [
            {"paper_ids": ids, "auto_merged": False}
            for ids in paper_groups.values()
            if len(ids) > 1
        ],
        "adaptation_suggestions": suggestions,
        "similar_topics_never_merged": True,
        "identity_basis": "完整题面及图片哈希严格一致共享主记录；省份只关联卷；近似关系不自动合并",
    }


if __name__ == "__main__":
    result = compare(rows(ROOT))
    atomic_json(ROOT / "reports/phase5-structured-dedup.json", result)
    print(
        json.dumps(
            {
                "unique_compared": result["questions_compared"],
                "adaptation_suggestions": len(result["adaptation_suggestions"]),
                "auto_merged_adaptations": 0,
            },
            ensure_ascii=False,
        )
    )
