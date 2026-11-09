"""Build region/series/system relationships without duplicating shared national papers."""

import bootstrap  # noqa: F401
import re
from gaokao import ROOT, read_json, read_lines
from storage import atomic_json
from import_national import jsonl


def main():
    catalog = ROOT / "national/catalog"
    series = [
        {
            "id": "cn-new-gaokao-1",
            "label": "全国新高考Ⅰ卷历史系列",
            "scope": "national",
            "subject": "math",
            "year_names": {
                "2020-2022": "新高考全国Ⅰ卷",
                "2023-2024": "新课标Ⅰ卷",
                "2025-2026": "全国一卷",
            },
            "continuity": "研究系列，不表示逐年结构相同",
        },
        {
            "id": "cn-new-gaokao-2",
            "label": "全国新高考Ⅱ卷历史系列",
            "scope": "national",
            "subject": "math",
            "year_names": {
                "2020-2022": "新高考全国Ⅱ卷",
                "2023-2024": "新课标Ⅱ卷",
                "2025-2026": "全国二卷",
            },
            "continuity": "研究系列，不表示逐年适用地区或制度相同",
        },
        {
            "id": "cn-national-1-legacy",
            "label": "旧高考全国Ⅰ卷",
            "scope": "national",
            "subject": "math",
            "distinct_from": "cn-new-gaokao-1",
        },
        {
            "id": "cn-national-b",
            "label": "旧高考全国乙卷",
            "scope": "national",
            "subject": "math",
            "tracks": ["liberal", "science"],
        },
        {
            "id": "cn-zhejiang",
            "label": "浙江自主命题数学",
            "scope": "province",
            "subject": "math",
            "end_year": 2022,
        },
    ]
    jsonl(catalog / "series.jsonl", series)
    jsonl(
        catalog / "systems.jsonl",
        [
            {
                "id": "legacy-3+x",
                "label": "旧高考3+文综/理综",
                "math_track_policy": "通常文理分别登记；2024河南等新课标数学同卷须按用卷关系例外标记",
                "science_components": "理综下的物理/化学/生物部分，不能伪装独立选考试卷",
            },
            {
                "id": "new-3+3",
                "label": "新高考3+3",
                "science_components": "地区年度独立选考试卷",
            },
            {
                "id": "new-3+1+2",
                "label": "新高考3+1+2",
                "science_components": "地区年度独立选择性考试；不得按制度合并省卷",
            },
        ],
    )
    jsonl(
        catalog / "curricula.jsonl",
        [
            {
                "id": "math-2003",
                "subject": "math",
                "label": "普通高中数学课程标准（实验）",
                "certainty": "旧卷选考结构对应；具体教材版本保留来源",
            },
            {
                "id": "math-2017-2020",
                "subject": "math",
                "label": "普通高中数学课程标准（2017年版2020年修订）",
                "certainty": "2023以后新课标系列",
            },
            {
                "id": "math-transition-unresolved",
                "subject": "math",
                "label": "新高考过渡期课标版本待逐省核实",
                "certainty": "unknown；不能按3+1+2推断课标",
            },
        ],
    )
    subjects = {
        "chinese": {"components": ["written"]},
        "math": {"tracks": ["unified", "liberal", "science"]},
        "english": {
            "components": ["written", "listening", "speaking_listening"],
            "same_written_does_not_imply_same_audio": True,
        },
        "physics": {"components": ["composite_section", "selective_provincial"]},
        "chemistry": {"components": ["composite_section", "selective_provincial"]},
        "biology": {"components": ["composite_section", "selective_provincial"]},
    }
    atomic_json(
        ROOT / "national/schema.json",
        {
            "schema_version": 1,
            "entities": [
                "Paper",
                "Question",
                "QuestionOccurrence",
                "ExamSeries",
                "Region",
                "ExamSystem",
                "Source",
                "Answer",
                "Analysis",
                "Curriculum",
            ],
            "subjects": subjects,
            "identity": [
                "paper_id includes year/subject/series/track/session",
                "question master may have multiple paper occurrences",
            ],
            "required_provincial_fields": ["year", "region_id", "subject", "component"],
            "unknown_values_are_null": True,
        },
    )
    sources = [
        {
            "id": "deekur-pinned",
            "url": "https://github.com/deekur/gaokaomath",
            "tier": "third_party_compilation",
            "commit": read_json(ROOT / "national/acquisition.json")["pdf_commit"],
            "license_scope": "CC BY 4.0整理成果；底层第三方权利保留",
        },
        {
            "id": "dxathing-pinned",
            "url": "https://github.com/DxAThing/Gaokao-Math-Problems-Compilation",
            "tier": "third_party_retypeset",
            "commit": read_json(ROOT / "national/acquisition.json")["tex_commit"],
            "license_scope": "CC BY-SA 4.0项目自有贡献；底层第三方权利保留",
        },
        {
            "id": "eol-2022-map",
            "url": "https://www.eol.cn/m/gaokao/202304/t20230406_2370206.shtml",
            "tier": "education_media",
            "finding": "2022年全国乙、甲、新I、新II的地区表；2023年浙江改用新I",
        },
        {
            "id": "math-journal-2021-I",
            "url": "https://m.fx361.com/news/2022/1118/11127901.html",
            "tier": "teacher_research_journal",
            "finding": "2021新I数学为山东河北湖北湖南江苏广东福建七省使用；不分文理。",
        },
        {
            "id": "eol-2024-map",
            "url": "https://gaokao.eol.cn/e_html/gk/gkst/2024st.shtml",
            "tier": "education_media",
            "finding": "2024新I和新II用卷表，明确西藏仅语文用II；不得套用到数学。",
        },
        {
            "id": "zj-2022-exam-review",
            "url": "https://www.zjzs.net/art/2022/6/13/art_31_4562.html",
            "tier": "provincial_exam_authority",
            "finding": "2022浙江数学自主命题收官之作；题型、分值保持稳定。",
        },
        {
            "id": "zj-2022-scoring",
            "url": "https://jx.panqjy.cn/doc-13723224.html",
            "tier": "third_party_exam_transcription",
            "finding": "22题：单选40分、填空36分（多空每空3分/单空4分），解答74分；18题14分，余4题各15分。",
        },
        {
            "id": "moe-2020-review-reprint",
            "url": "https://news.iqilu.com/shandong/yuanchuang/2020/0708/4585688.shtml",
            "tier": "official_review_republication",
            "finding": "2020新I山东、新II海南；新卷22题结构",
        },
        {
            "id": "exam-research-2023-map",
            "url": "https://www.nygz.xhedu.sh.cn/oss/0e/0e7f8fd7-bb1f-47b5-a31a-22da3656b8d4/0e7f8fd7-bb1f-47b5-a31a-22da3656b8d4.pdf",
            "tier": "school_hosted_research",
            "finding": "表1逐卷列2023数学使用省份，包含仍采用旧高考制度但数学同用新课标卷的地区",
        },
        {
            "id": "henan-2024-policy",
            "url": "https://gaokao.chsi.com.cn/gkxx/zc/ss/202406/20240624/2293299891.html",
            "tier": "official_admission_portal_republication",
            "finding": "河南2024仍语数外+综合，首次使用2017版2020修订的新课标命题，不能等同2025选科改革",
        },
        {
            "id": "henan-2024-math-use",
            "url": "https://app.gaokaozhitongche.com/news/h/WO8KmlGz",
            "tier": "education_media_local_teacher",
            "finding": "河南2024数学使用新课标Ⅰ卷；与对应卷面及汇编地区标注交叉",
        },
        {
            "id": "moe-2024-review-reprint",
            "url": "https://gaokao.haedu.cn/lnzt/2024/0608/135002.html",
            "tier": "official_review_republication",
            "finding": "来源标为教育部教育考试院，19题新结构及新I第19题数列新定义的评析；本次完整打开超时，检索摘要可见",
        },
    ]
    sources += [
        {
            "id": "eol-2020-math-use",
            "url": "https://gaokao.eol.cn/shiti/zhenti/202007/t20200709_1737395.shtml",
            "tier": "education_media",
            "finding": "2020数学全国I适用九省，明确含河南；不据2022反推",
        },
        {
            "id": "henan-2020-math-review",
            "url": "https://gaokao.haedu.cn/lnzt/2020/0708/121536.html",
            "tier": "provincial_education_portal_reprint",
            "finding": "河南当年文理数学点评分别明确全国I卷",
        },
        {
            "id": "eol-2021-map",
            "url": "https://gaokao.eol.cn/e_html/gk/gkst/2021st.shtml",
            "tier": "education_media",
            "finding": "2021当年乙卷适用12省，数学文理分别列出",
        },
    ]
    jsonl(catalog / "sources.jsonl", sources)
    regions = set()
    uses = []
    parsed = list(read_lines(catalog / "papers.jsonl"))
    # Region names are retained as candidate mappings where independent year-specific evidence remains absent.
    files = {
        r["id"]: r for r in read_json(ROOT / "national/acquisition.json")["records"]
    }
    for paper in parsed:
        meta = files[paper["id"]]
        filename = meta["pdf"]["path"].split("/")[-1]
        match = re.search(r"\(([^)]+)\)", filename)
        names = (
            re.split(r"[,，.]+", match[1])
            if match
            else ["浙江"]
            if paper["series_id"] == "cn-zhejiang"
            else []
        )
        names = [n.strip() for n in names if n.strip()]
        for name in names:
            regions.add(name)
            year = paper["year"]
            system = system_for(name, year)
            evidence = ["deekur-pinned"]
            if (
                year == 2020
                and paper["series_id"] == "cn-national-1-legacy"
                and name
                in {
                    "安徽",
                    "湖北",
                    "福建",
                    "湖南",
                    "山西",
                    "河北",
                    "江西",
                    "广东",
                    "河南",
                }
            ):
                evidence += ["eol-2020-math-use"]
                if name == "河南":
                    evidence += ["henan-2020-math-review"]
            if (
                year == 2021
                and paper["series_id"] == "cn-national-b"
                and name
                in {
                    "甘肃",
                    "青海",
                    "黑龙江",
                    "吉林",
                    "宁夏",
                    "新疆",
                    "内蒙古",
                    "陕西",
                    "安徽",
                    "山西",
                    "江西",
                    "河南",
                }
            ):
                evidence += ["eol-2021-map"]
            if year == 2020 and "new-gaokao" in paper["id"]:
                evidence += ["moe-2020-review-reprint"]
            elif year in (2021, 2022):
                evidence += ["eol-2022-map"] if year == 2022 else []
            elif year == 2023:
                evidence += ["exam-research-2023-map"]
            if name == "河南" and year == 2024:
                evidence += ["henan-2024-policy", "henan-2024-math-use"]
            if year == 2021 and paper["series_id"] == "cn-new-gaokao-1":
                evidence += ["math-journal-2021-I"]
            if year == 2024:
                evidence += ["eol-2024-map"]
            if name == "浙江" and year == 2022:
                evidence += ["zj-2022-exam-review", "zj-2022-scoring"]
            # Do not label a one-source mapping as verified.
            status = (
                "cross_checked_third_party"
                if len(evidence) > 1
                else "candidate_requires_independent_source"
            )
            uses.append(
                {
                    "paper_id": paper["id"],
                    "region_id": name,
                    "year": year,
                    "subject": "math",
                    "exam_system_id": system,
                    "track": paper["track"],
                    "usage_status": status,
                    "evidence": evidence,
                    "note": "数学同卷不表示考试制度、小科或英语听力同卷",
                }
            )
    # Legacy math IDs remain the primary records; do not collect either I paper again.
    legacy = []
    for path in sorted((ROOT / "metadata/papers").glob("*.json")):
        p = read_json(path)
        entry = {
            "id": p["id"],
            "year": p["year"],
            "subject": p["subject"],
            "legacy_path": path.relative_to(ROOT).as_posix(),
            "reported_name": p["formal_title"],
            "series_id": "cn-new-gaokao-1" if p["subject"] == "math" else None,
            "question_count": p.get("expected_questions"),
            "track": "unified" if p["subject"] == "math" else None,
            "curriculum_id": "math-2017-2020" if p["subject"] == "math" else None,
            "official_original": False,
        }
        legacy.append(entry)
        if p["subject"] == "math":
            # Only the previously verified Henan relationship is promoted, not all eleven provinces.
            uses.append(
                {
                    "paper_id": p["id"],
                    "region_id": "河南",
                    "year": p["year"],
                    "subject": "math",
                    "exam_system_id": "new-3+1+2",
                    "track": "unified",
                    "usage_status": "previously_verified_for_region",
                    "evidence": p["attribution_sources"],
                    "legacy": True,
                }
            )
            regions.add("河南")
    jsonl(catalog / "legacy-papers.jsonl", legacy)
    jsonl(catalog / "paper-regions.jsonl", uses)
    jsonl(catalog / "regions.jsonl", [{"id": n, "name": n} for n in sorted(regions)])
    atomic_json(
        ROOT / "national/targets/cn-ha-2027-math.json",
        {
            "region_id": "河南",
            "year": 2027,
            "subject": "math",
            "exam_system_id": "new-3+1+2",
            "curriculum_id": "math-2017-2020",
            "primary_series": "cn-new-gaokao-1",
            "series_status": "沿用已核2025/2026实际用卷作为2027模拟设定，非2027详细卷型公告",
            "structure_source": "analysis/rules.json",
            "immutable_current_structure": True,
            "reference_tiers": {
                "current_used_series": 100,
                "same_series_history": 80,
                "comparable_new_series": 55,
                "legacy_or_specialty": 25,
            },
            "module_coverage_weights": {
                "集合与复数": 1,
                "三角函数与解三角形": 2,
                "平面向量": 1,
                "立体几何": 2,
                "解析几何": 2,
                "概率统计": 2,
                "数列": 2,
                "函数与导数": 3,
            },
            "weight_basis": "目标课程模块覆盖的显式模拟设定，非题目数量投票",
            "per_paper_reference_cap": 2,
        },
    )
    atomic_json(
        ROOT / "national/config.json",
        {
            "schema_version": 1,
            "reference_dir": ".private/national-reference",
            "catalog_dir": "national/catalog",
            "default_target": "national/targets/cn-ha-2027-math.json",
            "index": ".private/national-index.sqlite",
            "legacy_adapter": "original IDs preserved, read-only",
        },
    )


def system_for(region, year):
    if region in ("山东", "海南", "浙江"):
        return "new-3+3" if year >= 2020 else "unknown"
    if (
        region in ("河北", "辽宁", "江苏", "福建", "湖北", "湖南", "广东", "重庆")
        and year >= 2021
    ):
        return "new-3+1+2"
    if (
        region in ("吉林", "黑龙江", "安徽", "江西", "广西", "贵州", "甘肃")
        and year >= 2024
    ):
        return "new-3+1+2"
    if (
        region in ("山西", "内蒙古", "河南", "四川", "云南", "陕西", "青海", "宁夏")
        and year >= 2025
    ):
        return "new-3+1+2"
    return "legacy-3+x"


if __name__ == "__main__":
    main()
