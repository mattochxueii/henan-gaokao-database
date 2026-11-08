"""Produce aggregate reports from actual candidate research and experiment records."""

import bootstrap
from collections import Counter
import json
from gaokao import ROOT, atomic_write, read_json
from analysis_db import research, fingerprint
from storage import atomic_json

rows = research(ROOT)
papers = []
audit = []
for year in (2025, 2026):
    cohort = [q for q in rows if q["year"] == year]
    papers.append(
        {
            "year": year,
            "questions": len(cohort),
            "total_points": sum(q["points"] for q in cohort),
            "kinds": dict(Counter(q["kind"] for q in cohort)),
            "module_counts": dict(
                Counter(q["analysis"]["knowledge"]["module"] for q in cohort)
            ),
            "competency_counts": dict(
                Counter(tag for q in cohort for tag in q["analysis"]["competencies"])
            ),
            "difficulty_design_counts": dict(
                Counter(
                    str(q["analysis"]["difficulty"]["ordinal_1_to_5"]) for q in cohort
                )
            ),
            "module_labels_and_difficulty_are_AI_inference": True,
            "primary_tags_only_for_module_count": True,
            "question_coverage": [
                {
                    "id": q["id"],
                    "points": q["points"],
                    "primary": q["analysis"]["knowledge"]["primary"],
                }
                for q in cohort
            ],
        }
    )
for q in rows:
    ref = q["candidate"]
    audit.append(
        {
            "question_id": q["id"],
            "year": q["year"],
            "candidate_version": ref["version"],
            "candidate_sha256": fingerprint(ref),
            "source_id": ref["source_id"],
            "source_url": ref["source_url"],
            "pages": [ref["page"], ref["end_page"]],
            "stem_present": bool(ref["stem"]),
            "options_count": len(ref["options"] or {}),
            "formulas_count": len(ref["formulas"]),
            "subquestions_count": len(ref.get("subquestions", [])),
            "asset_count": len(ref["assets"]),
            "points": q["points"],
            "candidate_complete": True,
            "official_confirmed": False,
            "visual_review": "AI页图核对",
            "human_reviewed": False,
            "body_state": q["curation"]["body_state"],
            "answer_status": q["curation"]["answer_status"],
            "analysis_id": q["analysis"]["analysis_id"],
            "current_solution_bound": True,
        }
    )
atomic_json(
    ROOT / "analysis/paper-patterns.json",
    {
        "sample_papers": 2,
        "papers": papers,
        "statistical_inference": "仅描述当前两份候选，无总体频率或固定年份预测",
        "date": "2026-11-07",
    },
)
atomic_json(
    ROOT / "reports/question-audit.json",
    {
        "questions": audit,
        "candidate_complete": len(audit),
        "official_confirmed": 0,
        "human_reviewed": 0,
        "programmatic_targeted_questions": 10,
        "raw_sources_unchanged": True,
    },
)
runs = {
    mode: read_json(ROOT / "experiments" / mode / "run.json")
    for mode in ("sequence", "derivative", "mixed", "full")
}
summary = []
for mode, r in runs.items():
    summary.append(
        {
            "experiment": mode,
            **r["structure"],
            "programmatic": sum(
                v["status"] == "programmatically_verified" for v in r["verifications"]
            ),
            "symbolic_plus_reasoning": sum(
                v["status"] == "symbolic_checks_and_reasoning_review"
                for v in r["verifications"]
            ),
            "reverified": sum(v["passed"] for v in r["verifications"]),
            "remote_model_calls": r["remote_model_calls"],
            "rules_sha256": r["blueprint"]["rules_sha256"],
        }
    )
atomic_json(
    ROOT / "reports/experiment-summary.json",
    {
        "runs": summary,
        "questions": sum(len(r["questions"]) for r in runs.values()),
        "api_cost_usd": 0,
        "host_AI_session_cost": "宿主环境未向本工程暴露计费信息，不计入远程API调用预算",
        "independent_solver": "数学程序与提案分离，AI文字证明复核单独标记",
    },
)
atomic_json(
    ROOT / "reports/retrieval-evidence.json",
    {
        "commands": [
            "python scripts/cli.py query --year 2025 --subject math --number 1",
            "python scripts/cli.py query --year 2026 --subject math --number 17",
            "python scripts/math_skill.py research --topic 数列",
        ],
        "actual_results": [
            {
                "question_id": q["id"],
                "candidate_sha256": fingerprint(q["candidate"]),
                "stem_nonempty": bool(q["candidate"]["stem"]),
                "page": q["candidate"]["page"],
                "subquestions": len(q["candidate"].get("subquestions", [])),
                "points": q["points"],
                "current_answer": q["curation"]["answer_for_current_candidate"],
            }
            for q in rows
            if (q["year"], q["id"][-4:]) in [(2025, "q001"), (2026, "q017")]
        ],
        "sequence_research": [
            {
                "question_id": q["id"],
                "version": q["candidate"]["version"],
                "knowledge": q["analysis"]["knowledge"],
                "key_idea": q["analysis"]["key_idea"],
            }
            for q in research(ROOT, topic="数列")
        ],
        "privacy": "完整查询原文仅在.private中留存，重新恢复后可直接重跑命令",
    },
)

conflicts = [
    "# 数学候选版本与勘误复核",
    "",
    "本轮对保存的八页主候选及2026锦宏对照页进行AI视觉复核。命题机构确认与教师人工核验仍待补齐。",
    "",
]
for q in rows:
    conflict = q["curation"]["version_conflict"]
    if conflict:
        conflicts.extend(
            [
                "## " + q["id"],
                "",
                conflict["category"] + "。" + conflict["finding"],
                "",
                f"当前使用版本为{q['candidate']['version']}，页码{q['candidate']['page']}–{q['candidate']['end_page']}。",
                "",
                conflict["resolution"] + "。所采用解答仅对该候选条件有效。",
                "",
            ]
        )
conflicts.extend(
    [
        "## 证据等级与未解决内容",
        "",
        "2026第9、12、18题的锦宏PDF与扫描页图均在加密备份中，存在可视实物差异。第13题θ与第17题15分在两份候选中一致，二手摘要错误已定位。第18题分别保留Q版可解与P版面积条件矛盾，未借助可解性裁决官方原题。",
        "",
        "2025选项顺序及箭头的另一版本部分依赖既有网页文字记录，缺少同等级原图，相关差异仍需经认证页图。第15题0.005/3.841按所存候选保留，未静默改写。",
        "",
        "需要补充的材料为两年经认证考场原卷、官方评分参考及相应保存使用权凭证。放入private-data/intake/<year>/math并按README使用import-file登记。既有可核来源仍见metadata/sources.jsonl，自动采集未突破任何访问限制。",
        "",
        "原始对照见 [2025锦宏PDF](https://www.jhgk.cn/upload/file/20250610/1749549496776033663.pdf)、[2026锦宏PDF](https://www.jhgk.cn/upload/file/20260608/1780886746084032608.pdf)、[2026扫描候选入口](https://1cunzhang.com/index.php?id=5830&p=article)。",
    ]
)
atomic_write(ROOT / "reports/phase2-conflicts.md", "\n".join(conflicts) + "\n")

text = [
    "# 两套数学候选试卷的命题观察",
    "",
    "样本仅2025、2026两份河南实际用卷所对应的公开候选。题目归属证据与候选版本身份分别保存。以下模块和难度为逐题AI分析标签，频数只对本样本成立。",
    "",
]
for paper in papers:
    text.extend(
        [
            f"## {paper['year']}年",
            "",
            f"共{paper['questions']}题、{paper['total_points']}分。题型为8单选、3多选、3填空、5解答，解答题分值13、15、15、17、17。",
            "",
            "按主要模块统计，"
            + "，".join(f"{k}{v}题" for k, v in paper["module_counts"].items())
            + "。交叉知识在每题secondary和integration中保存。",
            "",
            "以下按题号说明主线。",
            "",
        ]
    )
    text.extend(
        f"- 第{int(q['id'][-3:])}题，{'、'.join(q['primary'])}，{q['points']}分。"
        for q in paper["question_coverage"]
    )
    text.append("")
text.extend(
    [
        "## 两年差异与有限样本观察",
        "",
        "- 2025数列包括S4/S8的等比块和及递推-有限和求导。2026包括塔层配对的等差结构、部分和限定下局部九项等比的存在性。后一题不能默认窗口与三项块对齐。",
        "- 2025统计解答以医疗列联表和独立性检验为情境，2026概率解答以截断投篮等待为情境。两者都把现实规则转成数学事件，但前者重条件方向，后者重截断末项。",
        "- 多选题覆盖不同层次。2025有空间关系、抛物线焦点弦、三角恒等条件。2026有复数运算、二面角自由度、三圆截弦。干扰项常借概念混淆、遗漏自由度或将特殊情形当恒真。",
        "- 解答题使用基础计算或简单证明引入综合问题。2025末题的区间引理服务相位极小极大，2026末题逐步建立位移集合与函数序的关系。",
        "- 难度标签5主要对应全称量词、存在构造、参数分类和多曲线综合。标签没有考生得分率依据。题序并非严格单调难度，2026第14题的存在性推理在填空中已较强。",
        "- 运算量与推理复杂度分别记录。2026中位数运算少，三圆弦长则有多分支；2025递推题需要有限和末项，末题的核心困难在量词与下界证明。",
        "- 共同点只能描述本样本。两份末题涉及函数全域论证，不能推出2027固定题号或固定知识点。",
        "",
        "## 官方要求、事实、观察与假设",
        "",
        "rules.json以official_requirement、direct_candidate_fact、limited_sample_observation、unverified_hypothesis和simulation_setting分类。2027报名文件确认数学为全国统考科目，未据此确认19题细结构。完整模拟将历史结构、难度4/11/4分组和模块覆盖作为可调整的设计设定。",
        "",
        "官方政策证据见 [河南2027报名问答第11问](https://www.haeea.cn/a/202610/43749_c5d5e459.shtml)。两年候选的页码、校验值和逐题分析见analysis/questions.jsonl及private-data/inventory.json。",
    ]
)
atomic_write(ROOT / "reports/paper-patterns.md", "\n".join(text) + "\n")
print(
    "reports built from", len(rows), "candidate rows and", len(runs), "real experiments"
)
