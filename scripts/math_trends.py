"""Validate the frozen qualitative pilot and score later annotated 2027 evidence."""
import argparse
from datetime import date
from pathlib import Path

from gaokao import ROOT, digest, dumps, read_json, relative_path, require

SNAPSHOT = Path("forecast/preregistered/2027-math-trends.json")
SIGNALS = Path("data/signals/math")
LOCKED_FILES = ("evidence.json","position-comparison.json","crowding_watchlist.json")
GRADES = {"强证据","有限观察","证据不足"}
V3 = Path("forecast/frozen/henan-2027-math-v3.json")
V3_SHA256 = "33c20281a81ddc747189bc251564b90fc725ad86f540ad068c767ea0ee185931"


def index(root):
    evidence = read_json(root / SIGNALS / "evidence.json")
    compare = read_json(root / SIGNALS / "position-comparison.json")
    watch = read_json(root / SIGNALS / "crowding_watchlist.json")["items"]
    known = {source["id"]:source["issued"] for source in evidence["sources"]}
    cutoff = max(known.values())
    ids = {card["id"]:known.get(card["source"],cutoff) for card in evidence["cards"]}
    for sample in compare["papers"]:
        for row in sample["positions"]:
            ids[row["question_id"]] = known[sample["source"]]
    return ids, {row["id"]:row for row in watch}


def validate_snapshot(root):
    require((root / SNAPSHOT).is_file(), "当前数据目录缺数学冻结趋势卡及配套证据")
    snapshot = read_json(root / SNAPSHOT)
    require(snapshot["target"] == {"year":2027,"subject":"math","region":"河南",
                                   "series":"cn-new-gaokao-1","papers":"official_exam"},
            "趋势卡适用卷型错配")
    cutoff = date.fromisoformat(snapshot["cutoff"])
    require(cutoff < date(2027,6,1), "证据截止须早于2027年考试")
    require(snapshot["v3_sha256"] == digest(root / V3) == V3_SHA256, "已冻结的v3字节发生变化")
    require(snapshot["inputs"] == {name:digest(root / SIGNALS / name) for name in LOCKED_FILES},
            "证据文件内容与冻结版本不一致")
    evidence, watch = index(root)
    ids = set()
    for entry in snapshot["entries"]:
        require(entry["id"] not in ids and entry["grade"] in GRADES, "趋势卡 ID 重复或证据分级无效")
        ids.add(entry["id"])
        require(entry["decision"] == ("abstain" if entry["grade"] == "证据不足" else "register"),
                "证据不足须弃权")
        require(entry["basis"] and all(ref in evidence and date.fromisoformat(evidence[ref]) <= cutoff
                                      for ref in entry["basis"]), "存在未登记或越过截止日的证据")
        rule = entry["criterion"]
        require(rule["hit"].strip() and rule["miss"].strip() and rule["all"]
                and set(rule["positions"]) <= set(range(1,20))
                and 0 < rule["min_items"] <= len(rule["positions"]),
                "考后判据不完整")
    require(entries_have_abstentions(snapshot), "须保留实际弃权项")
    return snapshot


def entries_have_abstentions(snapshot):
    return any(e["decision"] == "abstain" for e in snapshot["entries"])


def bind_pack_positions(reference, document):
    """Select the author-declared comparable slots from current real papers."""
    require(document.get("paper", {}).get("edition") == "trend_pack", "须使用独立趋势专题候选")
    declared = (document.get("quality_benchmarks") or {}).get("benchmark_slots", {})
    questions = document["questions"]
    require(set(declared) == {str(q["order"]) for q in questions}, "趋势专题缺对应正式题位")
    for q in questions:
        slot = declared[str(q["order"])]
        sample = reference["slots"].get(str(slot), {})
        require(type(slot) is int and bool(sample)
                and all(p["kind"] == q["kind"] for p in sample.values()), "趋势专题的题型与对照题位不一致")
    return {**reference, "benchmark_slots": declared,
            "slots": {key: reference["slots"][str(slot)] for key, slot in declared.items()}}


def validate_pack(root, document):
    snapshot = validate_snapshot(root)
    require(document["trend_snapshot_sha256"] == digest(root / SNAPSHOT), "趋势专题未绑定考前冻结版本")
    require(document["paper"]["edition"] == "trend_pack" and "趋势" in document["paper"]["title"],
            "趋势专题标题及版别缺失")
    questions = document["questions"]
    kinds = [q["kind"] for q in questions]
    require(4 <= len(questions) <= 5 and kinds.count("constructed_response") == 2
            and "multiple_choice" in kinds and "fill_in" in kinds, "专题应包含高阶多选、填空和两道解答")
    known, watch = index(root)
    entries = {e["id"]:e for e in snapshot["entries"] if e["decision"] == "register"}
    for q in questions:
        card = q.get("trend_basis",{})
        item = entries.get(card.get("entry"))
        require(item and card.get("strength") == item["grade"] and card.get("evidence")
                and all(ref in known for ref in card["evidence"])
                and set(card["evidence"]) & set(item["basis"])
                and card.get("avoided") in watch and card.get("surface","").strip()
                and card.get("retained","").strip()
                and card.get("difference","").strip(), "每道趋势题须有可回查的命题依据卡")


def score(snapshot, evidence):
    """Compare predeclared markers after official release; never rewrite the registration."""
    require(evidence["target"] == snapshot["target"], "考后证据须来自指定年度实际正式卷")
    require(date.fromisoformat(evidence["published"]) >= date(2027,6,1)
            and evidence["source_url"].startswith("https://"), "须提供2027考后可访问的卷面来源")
    if not evidence["nineteen_item_structure"]:
        return {"state":"卷型变化，预注册题位判据不适用","entries":[]}
    rows = {row["number"]:row for row in evidence["items"]}
    require(len(rows) == len(evidence["items"]), "考后证据重复题号")
    grades = []
    for entry in snapshot["entries"]:
        if entry["decision"] == "abstain":
            grades.append({"id":entry["id"],"verdict":"弃权"})
            continue
        rule = entry["criterion"]
        require(all(n in rows and rows[n]["locator"].strip() and rows[n]["reasoning"].strip()
                    for n in rule["positions"]), "预注册题位缺逐题证据")
        positives = [n for n in rule["positions"] if set(rule["all"]) <= set(rows[n]["markers"])]
        grades.append({"id":entry["id"],"verdict":"命中" if len(positives)>=rule["min_items"] else "落空",
                       "matching_numbers":positives})
    return {"state":"按冻结规则核验","entries":grades}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--score",type=Path,help="2027正式卷公布后的结构化逐题核验依据")
    a=parser.parse_args(argv)
    snapshot=validate_snapshot(a.root.resolve())
    print(dumps(score(snapshot,read_json(a.score)) if a.score else
                {"status":"预注册文件与证据哈希一致","entries":len(snapshot["entries"]),
                 "snapshot_sha256":digest(a.root.resolve()/SNAPSHOT),"v3_sha256":snapshot["v3_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
