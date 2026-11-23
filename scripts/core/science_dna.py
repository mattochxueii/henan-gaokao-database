"""Separate observed Henan selective-exam profiles from supplementary papers."""
from collections import Counter


DESIGN = {
    "physics": {
        "single_choice":"以一道完整的受力、运动、场或波动模型组织判断，干扰项分别对应一个物理量或模型条件的混淆。",
        "multiple_choice":"让各选项考查不同的时间区间、守恒条件或图像推论，逐项验证方向和适用条件。",
        "experiment":"保留仪器量程、变量控制和数据起点，分开评价读数、作图、误差方向与结论。",
        "calculation":"依据运动阶段分别写约束和动力学方程，验证衔接状态是否落在有效区域。",
    },
    "chemistry": {
        "single_choice":"让各选项围绕物质结构、化学用语、实验条件或反应原理，分别可被题面证据检验。",
        "constructed_response":"让前问的分离条件、物料衡算、速率或结构证据驱动下一问；核对原子、电荷与实验对照。",
    },
    "biology": {
        "single_choice":"围绕概念、适用范围和图表证据分别构造选项；不能由相关性直接推出因果。",
        "constructed_response":"分开评价读图结论、变量与对照、机制推导；解释题要求条件、过程和被观测结果对应。",
    },
}


def paper_observation(paper):
    rows = []
    for q in paper["questions"]:
        rows.append({"number":q["number"],"id":q["id"],"version_sha256":q["version_sha256"],
                     "position":q.get("position",q.get("page")),"kind":q.get("section_kind",q["kind"]),
                     "points":q["points"],"topic":q.get("topic"),"features":q.get("features",[]),
                     "subquestions":len(q.get("parts",[])),"figures":len(q.get("asset_refs",[])),
                     "practice_eligible":q["usable_for_practice"]})
    return {"paper_id":paper["id"],"year":paper["year"],"regions":paper["regions"],
            "series_id":paper["series_id"],"exam_kind":paper["exam_kind"],"source_url":paper["source"]["url"],
            "question_count":paper["question_count"],"points":paper["points"],"minutes":paper.get("minutes"),
            "missing_numbers":paper.get("missing_numbers",[]),"items":rows}


def science_profile(subject,papers):
    formal, adaptations, other = [],[],[]
    for paper in papers:
        row = paper_observation(paper)
        if paper["exam_kind"]=="adaptation_exam":
            adaptations.append(row)
        elif paper["regions"]==["河南"] and paper["series_id"]==f"cn-ha-{subject}-selective":
            formal.append(row)
        else:
            other.append(row)
    by_position = {}
    for paper in formal:
        for q in paper["items"]:
            slot = by_position.setdefault(q["number"],{"samples":[],"topic_counts":Counter(),
                                                      "feature_counts":Counter(),"kinds":Counter()})
            slot["samples"].append({"year":paper["year"],**q})
            slot["kinds"][q["kind"]] += 1
            if q["practice_eligible"]:
                if q["topic"]:
                    slot["topic_counts"][q["topic"]] += 1
                slot["feature_counts"].update(q["features"])
    design = [{"kind":kind,"guidance":guidance,
               "evidence":[{"year":paper["year"],"id":q["id"],"version_sha256":q["version_sha256"]}
                           for paper in formal for q in paper["items"]
                           if q["kind"]==kind and q["practice_eligible"] and q["features"]]}
              for kind,guidance in DESIGN[subject].items()]
    return {"subject":subject,"version":"henan-science-v1",
            "henan_selective_profile":{"by_year":formal,"aggregate":{"positions":by_position,"authoring":design}},
            "supplement":{"adaptation":adaptations,"other_regions":other},
            "scope":"题号与分值为卷面观察。题材与考查动作来自编辑标签。演练及外省卷不进入河南正式统计，缺项不推断为从未考查。"}
