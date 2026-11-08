"""Blueprint -> draft -> independent solving -> quality gates -> immutable run."""

from collections import Counter
import json
from analysis_db import fingerprint, research, rules
from gaokao import require
from storage import atomic_json
from .generate import FAMILIES
from .providers import FamilyProvider, Limits
from .quality import verify, duplicate_check, assert_fresh

SEQUENCES = [
    "seq_interlace",
    "seq_reciprocal",
    "seq_telescope",
    "seq_alternating",
    "seq_optimize",
]
DERIVATIVES = list(FAMILIES)[5:10]
FULL_FAMILIES = [
    "complex_norm",
    "integer_set",
    "trig_square",
    "vector_sum",
    "ellipse_chord",
    "urn_pair",
    "positive_roots",
    "trig_count",
    "seq_interlace",
    "geometry_assertions",
    "logquad_assertions",
    "binomial",
    "variance",
    "exp_peak",
    "urn_mixture",
    "tetrahedron",
    "seq_alternating",
    "ellipse_conjugate",
    "deriv_logroots",
]
TITLES = {
    "sequence": "数列专项 · 五题递进",
    "derivative": "导数专项 · 推理与综合",
    "mixed": "数学综合检测 · 50分",
    "full": "河南2027高考风格数学模拟 · 150分",
}


def blueprint(root, mode):
    regulations = rules(root)
    if mode == "full":
        slots = []
        for group in regulations["blueprint"]["sections"]:
            points = group.get("points", [group.get("points_each")] * group["count"])
            slots.extend([{"kind": group["kind"], "points": p} for p in points])
        require(len(slots) == len(FULL_FAMILIES), "历史蓝图变化，需要更新题目族安排")
        for slot, family in zip(slots, FULL_FAMILIES):
            slot["family"] = family
    elif mode == "mixed":
        slots = [
            {
                "family": f,
                "kind": "constructed_response" if i >= 5 else "single_choice",
                "points": p,
            }
            for i, (f, p) in enumerate(
                zip(
                    [
                        "complex_norm",
                        "integer_set",
                        "vector_sum",
                        "urn_pair",
                        "binomial",
                        "tetrahedron",
                        "deriv_logroots",
                    ],
                    [5, 5, 5, 5, 5, 10, 15],
                )
            )
        ]
    else:
        families = SEQUENCES if mode == "sequence" else DERIVATIVES
        slots = [
            {"family": f, "kind": "constructed_response", "points": p}
            for f, p in zip(families, [6, 8, 10, 12, 14])
        ]
    return {
        "mode": mode,
        "title": TITLES[mode],
        "slots": slots,
        "total_points": sum(s["points"] for s in slots),
        "rules_sha256": fingerprint(regulations),
        "target_year": 2027,
        "difficulty_target": regulations["blueprint"]["difficulty_target"]
        if mode == "full"
        else None,
        "verified_features": ["两个候选样本的历史结构"]
        if mode == "full"
        else ["本次指定题量与总分"],
        "simulation_settings": [
            "2027详细结构沿用历史候选；正式通知优先",
            "难度按方法与推理层数设计，未实测",
            "本地题目族生成，AI设计与数学验证分离",
        ],
        "official_2027_paper_prediction": False,
    }


def custom_blueprint(root, topic, count, kind, difficulty):
    require(1 <= count <= 30, "题量应在1到30之间")
    knowledge = {
        "seq_interlace": ["等差数列", "奇偶子列"],
        "seq_reciprocal": ["递推数列", "倒数递推"],
        "seq_alternating": ["等比数列", "递推数列", "交错数列"],
        "seq_telescope": ["数列求和", "裂项相消", "递推数列"],
        "seq_optimize": ["不等式", "数列最值", "正项数列"],
    }
    matched = [
        name
        for name, (module, level) in FAMILIES.items()
        if (
            topic in module
            or any(topic in label for label in knowledge.get(name, []))
            or (
                topic == "导数"
                and (
                    name.startswith("deriv_")
                    or name in ("exp_peak", "logquad_assertions")
                )
            )
        )
        and (difficulty is None or level == difficulty)
    ]
    multi = {"seq_interlace", "geometry_assertions", "variance", "logquad_assertions"}
    scalar = {
        "complex_norm",
        "integer_set",
        "trig_square",
        "vector_sum",
        "ellipse_chord",
        "urn_pair",
        "positive_roots",
        "trig_count",
        "binomial",
        "variance",
        "exp_peak",
        "seq_interlace",
    }
    if kind == "multiple_choice":
        matched = [name for name in matched if name in multi]
    elif kind == "single_choice":
        matched = [name for name in matched if name in scalar]
    else:
        matched = [
            name
            for name in matched
            if name not in ("geometry_assertions", "logquad_assertions")
        ]
    require(
        len(matched) >= count,
        f"当前受支持且互不重复的题目族仅{len(matched)}个，需扩展并测试求解器后再增加题量",
    )
    point = (
        6
        if kind == "multiple_choice"
        else 5
        if kind in ("single_choice", "fill_in")
        else 10
    )
    return {
        "mode": "custom",
        "title": topic + "专项练习",
        "slots": [
            {"family": f, "kind": kind, "points": point} for f in matched[:count]
        ],
        "total_points": count * point,
        "rules_sha256": fingerprint(rules(root)),
        "target_year": 2027,
        "verified_features": ["用户指定的知识模块、题型、题量与设计难度"],
        "simulation_settings": ["题目族范围有限，难度为主观设计等级"],
        "official_2027_paper_prediction": False,
    }


def structure_check(plan, questions):
    require(len(questions) == len(plan["slots"]), "题量与蓝图不符")
    require(sum(q["points"] for q in questions) == plan["total_points"], "总分不符")
    require(
        all(
            q["kind"] == slot["kind"] and q["points"] == slot["points"]
            for q, slot in zip(questions, plan["slots"])
        ),
        "分段结构不符",
    )
    if plan["mode"] == "full":
        require(len({q["module"] for q in questions}) >= 6, "模块覆盖不足")
        require(
            dict(Counter(str(q["difficulty"]) for q in questions))
            == plan["difficulty_target"]["ordinal_counts"],
            "设计难度分布与蓝图不符",
        )
    return {
        "passed": True,
        "questions": len(questions),
        "points": sum(q["points"] for q in questions),
        "kind_counts": dict(Counter(q["kind"] for q in questions)),
        "module_counts": dict(Counter(q["module"] for q in questions)),
        "difficulty_counts": dict(Counter(str(q["difficulty"]) for q in questions)),
    }


def run(root, mode, seed, output, export=True, plan=None):
    require(not output.exists(), "输出目录已存在，请用新的目录保留先前记录")
    plan = plan or blueprint(root, mode)
    limits = Limits()
    require(len(plan["slots"]) <= limits.max_questions, "超过单次命题数量限制")
    originals = research(root)
    provider = FamilyProvider()
    questions, verifications, events = [], [], []
    output.mkdir(parents=True)
    for number, slot in enumerate(plan["slots"], 1):
        accepted = False
        for attempt in range(limits.max_attempts_per_question):
            item_seed = seed + number * 101 + attempt * 10007
            question = provider.propose(
                slot["family"], item_seed, slot["kind"], slot["points"]
            )
            question.update(
                id=f"orig:henan-math:{mode}:{seed}:q{number:03d}:v{attempt + 1}",
                order=number,
                revision=attempt + 1,
                novelty_basis="与38道候选比较题面，AI设计不同条件结构。通用方法可重合，未证明全球首创。",
            )
            verification = verify(question)
            duplication = duplicate_check(question, originals, questions)
            review = {
                "duplicate": duplication,
                "syllabus_module": question["module"],
                "ambiguity_review": "标准题面与参数绑定校验；有定义域与量词，尚需教师盲审",
                "difficulty_basis": question["difficulty_basis"],
                "calculation_review": "完整步骤保存在验证记录，未实测作答时间",
                "passed": verification["passed"] and duplication["passed"],
            }
            events.append(
                {
                    "question_id": question["id"],
                    "attempt": attempt + 1,
                    "passed": review["passed"],
                    "verification": verification,
                    "quality": review,
                }
            )
            atomic_json(output / "attempts.json", events)
            if review["passed"]:
                assert_fresh(question, verification)
                questions.append(question)
                verifications.append(verification)
                accepted = True
                break
        require(accepted, f"题{number}在有限重试内未通过质量门槛，停止出卷")
    structure = structure_check(plan, questions)
    record = {
        "schema_version": 1,
        "blueprint": plan,
        "seed": seed,
        "provider": provider.name,
        "rules_snapshot": rules(root),
        "limits": vars(limits),
        "remote_model_calls": 0,
        "host_model_version": "not_exposed_by_host",
        "questions": questions,
        "verifications": verifications,
        "events": events,
        "structure": structure,
        "overall_status": "prototype_verified_with_reasoning_review",
        "limitations": [
            "主观难度与高考风格尚无教师盲评或考生实测",
            "符号验证仅覆盖受支持数学题目族",
            "文本相似度不能排除外部题库重复",
        ],
    }
    require(
        len(json.dumps(record, ensure_ascii=False)) <= limits.max_output_characters,
        "生成记录超长",
    )
    atomic_json(output / "run.json", record)
    if export:
        from .export import export_run

        record["files"] = export_run(record, output)
        atomic_json(output / "run.json", record)
    return record
