"""Recompute actual delivery bindings, difficulty records and numeric distractor models."""

import bootstrap
import itertools
import sympy as s
from gaokao import ROOT, read_json, require, digest
from storage import atomic_json
from analysis_db import fingerprint
from mathgen.exam_workflow import verify_certificate
from mathgen.ai_spec import parse


def main():
    dimensions = []
    options = []
    papers = []
    # Independent erroneous calculations derived from the actual A question conditions.
    z = (1 + 2 * s.I) / (2 - s.I)
    digits = list(itertools.permutations(range(1, 7), 3))
    even = [v for v in digits if sum(v) % 2 == 0]
    two_odd = [v for v in even if sum(n % 2 for n in v) == 2]
    models = {
        1: {"A": abs(z), "C": abs(z) + 1, "D": abs(1 + 2 * s.I)},
        2: {
            "A": len([n for n in range(-3, 4) if 2 < n <= 5]),
            "C": len([n for n in range(-4, 5) if 1 < n <= 4]),
            "D": len([n for n in range(-5, 6) if 1 < n <= 5]),
        },
        3: {
            "B": abs((-s.Rational(4, 5) + s.Rational(3, 5)) / s.sqrt(2)),
            "C": (s.Rational(4, 5) + s.Rational(3, 5)) / s.sqrt(2),
            "D": (-s.Rational(4, 5) - s.Rational(3, 5)) / s.sqrt(2),
        },
        4: {
            "A": 6,
            "B": (700 - 4**2 + 14**2) / s.Integer(10) - 8**2,
            "D": s.Rational(10, 9) * 7,
        },
        5: {"A": 2, "C": s.Rational(1, 2) * 2, "D": 2 * (s.Rational(1, 2) + 2)},
        6: {
            "B": s.sqrt(5 * (5 - 3) * (5 - 3) * (5 - 4)),
            "C": s.Rational(1, 2) * 4 * 2,
            "D": s.sqrt(15) / 2,
        },
        7: {"A": -1, "B": 3 * 2**2 - 6 * 2, "D": 3 * 2**2 + 1},
        8: {"A": len(even) // 6, "B": len(two_odd) // 2, "C": len(even)},
    }
    for name in ("A", "B"):
        folder = ROOT / f"experiments/phase4/final/full{name}"
        cert = read_json(folder / "publication.json")
        verify_certificate(folder, cert)
        raw = read_json(folder / "raw-ai-candidate.json")
        review = read_json(folder / "student-review.json")
        require(
            cert["question_count"] == 19
            and sum(q["points"] for q in raw["questions"]) == 150,
            "结构不符",
        )
        papers.append(
            {
                "paper": name,
                "pdf_sha256": cert["pdf_sha256"],
                "questions": 19,
                "points": 150,
                "published_ai_reviewed": True,
                "human_reviewed": False,
                "author_estimated_minutes": sum(
                    q["assessment"]["estimated_minutes"] for q in raw["questions"]
                ),
            }
        )
        for q, row in zip(raw["questions"], review["questions"]):
            dimensions.append(
                {
                    "paper": name,
                    "id": q["id"],
                    "number": q["order"],
                    "points": q["points"],
                    "assessment": q["assessment"],
                    "pdf_reviewer_points_pass": row["points_appropriate"],
                    "pdf_reviewer_observation": row.get(
                        "points_comment", row.get("difficulty_comment", "见独立PDF报告")
                    ),
                    "candidate_sha256": fingerprint(q),
                    "empirical": False,
                }
            )
            if q["kind"] != "single_choice":
                continue
            key = row["answer_key"]
            for letter, option in q["math_spec"]["options"].items():
                if letter == key:
                    continue
                model = models.get(q["order"], {}).get(letter) if name == "A" else None
                matched = (
                    None
                    if model is None
                    else s.simplify(parse(option["semantic_value"]) - model) == 0
                )
                require(
                    matched is not False, f"错因模型不匹配{name}{q['order']}{letter}"
                )
                options.append(
                    {
                        "paper": name,
                        "number": q["order"],
                        "option": letter,
                        "error_path": option.get("error_path"),
                        "semantic_value": option["semantic_value"],
                        "rederived_wrong_calculation": None
                        if model is None
                        else str(model),
                        "wrong_calculation_matches_option": matched,
                        "status": "独立重算的错误计算模型"
                        if model is not None
                        else "作者错误路径假设；未进行独立计算路径证明",
                        "cognitive_validity_proved": False,
                        "empirically_validated": False,
                    }
                )
    atomic_json(
        ROOT / "reports/phase4-distractor-audit.json",
        {
            "version": 1,
            "options": options,
            "rederived_models": sum(
                r["wrong_calculation_matches_option"] is True for r in options
            ),
            "limits": [
                "数值一致不证明学生会犯此错",
                "B卷错因路径保留作者设计假设，独立PDF审题确认选项含义和唯一性，不声称实测或认知证明",
            ],
        },
    )
    atomic_json(
        ROOT / "reports/phase4-difficulty-score-review.json",
        {
            "papers": papers,
            "questions": dimensions,
            "method": "八项有依据的编辑维度加估计时间；独立考生PDF审题另行记录。旧70题的九维逐题审核在legacy-audit。",
            "uncertainty": "作者与独立审题者估时差异显著，未做考生实测，不当作客观难度或区分度。",
            "formal_proof": False,
            "human_reviewed": False,
        },
    )
    print(
        "38 scored questions, 48 distractors; "
        + str(sum(r["wrong_calculation_matches_option"] is True for r in options))
        + " error models recalculated"
    )


if __name__ == "__main__":
    main()
