"""Optional forecast context for original generation, isolated from exam rules."""

from gaokao import require
from forecast_store import frozen

MODES = ("standard", "targeted", "forecast-research")
RESEARCH_MARKER = "概率预测研究实验"
MODULE_NAMES = {
    "foundations": {"集合与逻辑", "集合", "不等式", "预备知识"},
    "functions": {"函数与导数", "导数", "函数", "数列", "三角函数与解三角形", "三角函数"},
    "geometry": {"复数", "平面向量", "向量", "立体几何", "解析几何", "几何与代数"},
    "probability": {"概率统计", "统计与概率", "排列组合与计数", "概率与统计", "计数原理"},
}


def research_context(path):
    record = frozen(path)
    payload = record["payload"]
    def tier(row):
        if row["support"] != "estimated" or row["probabilities"].get("frequency") is None:
            return "abstained"
        return "exploratory"

    eligible = {
        row["target"]: {"title":row["title"],"layer":row["layer"],
                       "frequency":row["probabilities"]["frequency"],
                       "recent":row["probabilities"]["recent"],
                       "support":row["support"],"evidence_tier":tier(row)}
        for row in payload["predictions"]
        if tier(row) != "abstained"
        and not row["target"].startswith("paper.")
    }
    require(eligible, "此冻结版本没有可供命题研究使用的方向")
    return {"forecast_run_id":payload["run_id"],"snapshot_sha256":record["payload_sha256"],
            "as_of":payload["as_of"],"target_year":payload["target_year"],"series":payload["series"],
            "status":RESEARCH_MARKER,"eligible_targets":eligible,
            "target_evidence_tiers": {row["target"]:tier(row) for row in payload["predictions"]},
            "prospective_calibration": "unavailable",
            "guard":"仅作研究选题信号，不改变正式卷型、评分或质量门槛，不推导原题或复习取舍"}


def attach_mode(document, mode, forecast=None):
    supplied = "forecast_research" in document or "forecast_snapshot_sha256" in document or any(
        "forecast_targets" in question for question in document.get("questions", [])
    )
    if mode is None and forecast is None:
        require(not supplied, "预测研究须显式提供冻结预测")
        return document
    require(mode in MODES and (forecast is not None) == (mode=="forecast-research"),
            "预测研究模式与冻结文件必须同时提供")
    if mode!="forecast-research":
        require(not supplied, "标准和专项模式须独立于预测")
        if mode=="targeted":
            require(document.get("paper",{}).get("mode")!="full","专项模式须使用专题而非整卷卷型")
        return document
    require(document.get("schema_version")==2, "预测研究须通过三层规范题面")
    require(document.get("forecast_snapshot_sha256")==forecast["snapshot_sha256"],
            "候选未绑定本次冻结预测")
    from mathgen.editorial import compile_writing
    from forecast_features import LINK, match

    binding = []
    for question in document["questions"]:
        refs = question.get("forecast_targets")
        require(isinstance(refs,list) and refs, "每题须记录研究目标及关联依据")
        seen=set()
        visible=compile_writing(question)
        prompt=visible["stem"] + " " + " ".join(p["text"] for p in visible["parts"])
        for ref in refs:
            key = ref["id"]
            require(key in forecast["eligible_targets"] and key not in seen
                    and isinstance(ref.get("why"),str) and ref["why"].strip(), "无效或缺证据的预测目标")
            if key=="method.proof":
                require(visible["kind"]=="constructed_response" and match(r"证明|求证|证[：:]",prompt),
                        "预测标签与实际证明设问不符")
            if key=="method.linked":
                require(match(LINK,prompt), "预测标签与实际显式跨问关系不符")
            if key.startswith("module."):
                require(question.get("module") in MODULE_NAMES[key.split(".",1)[1]],
                        "预测模块与候选的主模块不符")
            seen.add(key)
        binding.append({"question_id":question["id"],"targets":sorted(seen)})
    title = document["paper"]["title"]
    if RESEARCH_MARKER not in title:
        title = title + " · " + RESEARCH_MARKER
    return {**document,"paper":{**document["paper"],"title":title},
            "forecast_research":{**forecast,"questions":binding}}
