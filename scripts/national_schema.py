"""Subject/component invariants shared by future national imports."""

from gaokao import require, SUBJECTS


def validate_paper(p):
    require(p["subject"] in SUBJECTS, "未知学科")
    require(isinstance(p["year"], int) and 1900 <= p["year"] <= 2100, "年份无效")
    require(p.get("id") and p.get("series_id"), "试卷身份不完整")
    if p["subject"] in ("physics", "chemistry", "biology"):
        require(
            p.get("component") in ("composite_section", "selective_provincial"),
            "必须区分理综部分和独立选考",
        )
        if p["component"] == "selective_provincial":
            require(
                p.get("region_id") and p.get("authoring_body"),
                "省级选考须绑定地区与命题机构",
            )
        else:
            require(p.get("parent_paper_id"), "理综部分须关联原理综试卷")
    if p["subject"] == "english":
        require(
            p.get("component") in ("written", "listening", "speaking_listening"),
            "英语须明确笔试、听力或听说",
        )
    if p["subject"] == "math":
        require(
            p.get("track") in ("unified", "liberal", "science"), "数学须明确文理/统一"
        )
    return True
