"""Answer-free feature proposals and version-bound comparison against a blind benchmark."""

import argparse
from collections import Counter
from pathlib import Path
import re
from analysis_db import fingerprint
from forecast_labels import compare_pairs, in_scope
from forecast_store import write_new
from gaokao import ROOT, digest, dumps, read_json, require

VERSION = "feature-proposals-v2"


def predict(row, rubric):
    stem = row["stem"]
    parts = [p["text"] if isinstance(p, dict) else p for p in row.get("parts", [])]
    text = " ".join([stem, *parts])
    options = row.get("options") or {}
    offered = " ".join(options.values()) if isinstance(options, dict) else " ".join(options)
    labels, evidence = {}, {}

    def offer(target, value, why):
        labels[target] = value
        evidence[target] = why

    def has(pattern, where=text):
        return re.search(pattern, where, re.IGNORECASE | re.DOTALL) is not None

    for item in rubric["targets"]:
        target = item["id"]
        labels[target] = None
        if in_scope(item, row["kind"]):
            evidence[target] = "题面规则尚不能确定该数学关系。"
    if any(f.get("state") == "unavailable" for f in row.get("figures", [])):
        return {"labels":labels, "evidence":evidence}

    seq = "structure.sequence_recurrence"
    # TeX requires braces for a multi-token subscript. a_n-6 is subtraction.
    index = r"([A-Za-z])_\{(n|k|m|i)([+-]\d+)?\}"
    for region in [stem, *parts, offered]:
        # A definition or tested option may have multiple equations; do not
        # infer a relation by joining mentions across sentence boundaries.
        for statement in re.split(r"[；。;\n]", region):
            terms = re.findall(index, statement)
            distinct = {(v, i) for v,i,delta in terms if delta}
            if "=" in statement and any(
                len({delta or "0" for x,j,delta in terms if (x,j)==(v,i)}) >= 2
                or re.search(rf"{v}_{i}(?![A-Za-z0-9])", statement)
                for v,i in distinct
            ) and has(r"数列|前.{0,15}项和|递推|通项|[Pp]_[{]", text):
                offer(seq, 1, "同一等式比较同一状态的不同索引，属于给定或待检验更新关系。")
    if has(r"依次|逐次|按照.{0,16}构造", stem) and has(r"P_\{n-1\}", stem) and has(r"P_n|P_\{n\}", stem) and has(r"数列|S_\{?n", text):
        offer(seq, 1, "用前一点构造下一点，后问要求研究所诱导的数列。")
    if labels[seq] is None and not has(r"数列|递推|通项|前.{0,16}项和|[A-Za-z]_\{(?:n|k|m|i)", text + " " + offered):
        offer(seq, 0, "题面和选项没有离散索引状态或更新任务。")

    conic = "structure.conic_dynamic"
    if not has(r"圆锥曲线|双曲线|抛物线|椭圆|离心率|焦点"):
        offer(conic, 0, "题面没有圆锥曲线对象。")
    elif has(r"任意|动点|运动|依次|斜率为|相交|交于|相切|过.{0,14}直线") and has(
        r"轨迹|定值|定点|最小值|最大值|取值范围|恒成立|充要条件|对任意"
    ):
        offer(conic, 1, "题面同时给出活动点线约束和对一族对象的性质设问。")

    if row["kind"] == "constructed_response":
        proof = "method.explicit_proof"
        offer(proof, int(has(r"证明|求证|(?:^|[。；])\s*证(?=[：:\s\\])")),
              "核对题内证明指令，排除选项和卷面通用说明。")
        depends = "method.explicit_dependence"
        citation = r"(?:利用|根据|由|依据|说明).{0,25}(?:前(?:一|二)?问|上一问|上述结论|[（(]\s*(?:[123一二三]|i{1,3})\s*[）)](?:问|的)?\s*(?:结论|结果|条件))"
        if has(citation):
            offer(depends, 1, "后问直接引用可定位的前问输出。")
        elif len(parts) <= 1 and not has(r"子项|[（(](?:[123]|i{1,3})[）)]", text):
            offer(depends, 0, "没有可关联的多个子问。")

    if has(r"(?:证明|求证).{0,120}(?:充要条件|当且仅当)"):
        offer("method.necessity_sufficiency", 1, "证明指令同时覆盖同一命题的两个方向。")
    if has(r"条件概率|P\s*[(（][^()]{1,45}(?:\\mid|\|)[^()]{1,45}[)）]") and has(r"求|估计|比较|证明"):
        offer("structure.conditional_decision", 1, "题目要求使用明确给定随机事件下的概率。")
    return {"labels":labels, "evidence":evidence}


def coded(packet, rubric):
    require(packet["rubric_version"] == rubric["version"], "输入题面协议不符")
    return {
        "version": VERSION, "prompt_sha256": fingerprint(packet),
        "rubric_sha256": fingerprint(rubric),
        "records": {qid: predict(row, rubric) for qid,row in packet["questions"].items()},
    }


def checked_codes(artifact, packet, rubric):
    records = artifact["records"]
    require(set(records) == set(packet["questions"]), "标注题号缺失或额外")
    for qid, record in records.items():
        labels = record["labels"]
        require(set(labels) == {t["id"] for t in rubric["targets"]}, "标签集不完整")
        for target in rubric["targets"]:
            key = target["id"]
            val = labels[key]
            scoped = in_scope(target, packet["questions"][qid]["kind"])
            require(val is None or scoped and type(val) is int and val in (0,1), "标签值或适用域不符")
            if scoped and val in (None,1):
                require(isinstance(record["evidence"].get(key),str) and record["evidence"][key].strip(),
                        "正例或未知须给证据")
    return records


def diagnostics(pairs):
    counts = Counter(pairs)
    size = len(pairs)
    report = compare_pairs(pairs)
    n_reference = sum(n for (_,b),n in counts.items() if b is not None)
    positives = sum(n for (_,b),n in counts.items() if b == 1)
    negatives = sum(n for (_,b),n in counts.items() if b == 0)
    tp = counts[1,1]
    predicted_positive = tp + counts[1,0]
    report.update({
        "in_scope": size, "reference_positive": positives, "reference_negative": negatives,
        "reference_unknown": size-n_reference, "predictor_unknown": sum(n for (a,_),n in counts.items() if a is None),
        "precision": tp/predicted_positive if predicted_positive else None,
        "recall_with_abstentions": tp/positives if positives else None,
        "coverage_of_reference": report["comparable"]/n_reference if n_reference else None,
        "false_positives": counts[1,0], "false_negatives": counts[0,1],
        "abstained_positive": counts[None,1], "abstained_negative": counts[None,0],
    })
    return report


def score(packet, rubric, key, first, second, gold, auto):
    require(key["rubric_sha256"] and auto["rubric_sha256"] == fingerprint(rubric)
            and auto["prompt_sha256"] == fingerprint(packet), "题面或规则与自动标注不匹配")
    require(len({key["questions"][q]["occurrence_id"] for q in packet["questions"]}) == len(packet["questions"]),
            "同一题重复入组")
    partitions = {}
    for q in key["questions"].values():
        group = q["paper_group"]
        require(partitions.setdefault(group,q["partition"]) == q["partition"], "同一题群跨分区")
    A,B,G,P = (checked_codes(x,packet,rubric) for x in (first,second,gold,auto))
    require(set(key["questions"]) == set(A), "索引题目不匹配")
    for qid, row in packet["questions"].items():
        require(key["questions"][qid]["prompt_sha256"] == fingerprint(row), "题面与索引哈希不匹配")
    stats, errors = {}, []
    for group in ("all","development","holdout"):
        for stratum in ("random","targeted","any"):
            ids = [i for i,k in key["questions"].items() if
                   (group=="all" or k["partition"]==group) and (stratum=="any" or stratum in k["strata"])]
            if not ids:
                continue
            output = {}
            for target in rubric["targets"]:
                t = target["id"]
                scoped = [i for i in ids if in_scope(target,packet["questions"][i]["kind"])]
                independent = [(A[i]["labels"][t],B[i]["labels"][t]) for i in scoped]
                estimated = [(P[i]["labels"][t],G[i]["labels"][t]) for i in scoped]
                output[t] = {"independent_agreement":diagnostics(independent),
                             "auto_vs_adjudication":diagnostics(estimated)}
                if group=="all" and stratum=="any":
                    for i,(a,b),(p,g) in zip(scoped,independent,estimated,strict=True):
                        if a != b or p != g or g is None:
                            errors.append({"question":i,"target":t,"reviewers":[a,b],"auto":p,"gold":g,
                                           "type":"gold_unknown" if g is None else "abstention" if p is None
                                           else "false_positive" if p>g else "false_negative" if p<g else "reviewer_disagreement",
                                           "reason":G[i]["evidence"].get(t)})
            stats[f"{group}.{stratum}"] = {"questions":len(ids),"targets":output}
    limit = rubric["admission"]
    gates = {}
    for target in rubric["targets"]:
        t = target["id"]
        hold = stats.get("holdout.any",{}).get("targets",{}).get(t)
        paper_count = len({k["paper_id"] for i,k in key["questions"].items() if
                           k["partition"]=="holdout" and G[i]["labels"][t] is not None})
        reasons = []
        if not hold or paper_count < limit["minimum_holdout_papers"]:
            reasons.append("评测卷覆盖不足")
        if hold:
            agreement = hold["independent_agreement"]
            metric = hold["auto_vs_adjudication"]
            if (metric["reference_positive"] < limit["minimum_positive"]
                    or metric["reference_negative"] < limit["minimum_negative"]):
                reasons.append("评测正负例不足")
            if agreement["cohen_kappa"] is None or agreement["cohen_kappa"] < limit["minimum_kappa"]:
                reasons.append("独立一致性不足")
            for key_name, threshold in (("precision","minimum_precision"),("recall_with_abstentions","minimum_recall"),
                                        ("coverage_of_reference","minimum_coverage")):
                if metric[key_name] is None or metric[key_name] < limit[threshold]:
                    reasons.append(key_name)
        gates[t] = {"benchmark_passed":not reasons,"holdout_papers":paper_count,
                    "official_forecast_admitted":False,"reasons":reasons+["尚缺完整年度变化和独立前瞻检验"]}
    return {"protocol":rubric["version"],"n":len(A),"stats":stats,"errors":errors,"gates":gates,
            "adjudication_sha256":fingerprint(gold),"automatic_sha256":fingerprint(auto),
            "shared_questions":len(A),"seed":rubric["sample"]["seed"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rubric",type=Path,default=ROOT/"forecast/benchmark/rubric.json")
    commands = parser.add_subparsers(dest="command",required=True)
    p = commands.add_parser("predict")
    p.add_argument("packet",type=Path)
    p.add_argument("output",type=Path)
    e = commands.add_parser("evaluate")
    for name in ("packet","key","review_a","review_b","gold","auto","output"):
        e.add_argument(name,type=Path)
    args = parser.parse_args()
    rubric,packet = read_json(args.rubric),read_json(args.packet)
    if args.command == "predict":
        result = coded(packet,rubric)
    else:
        binding = read_json(args.key)
        require(binding["rubric_sha256"] == digest(args.rubric) and binding["blind_sha256"] == digest(args.packet),
                "留出基准文件校验失败")
        result = score(packet,rubric,binding,*(read_json(getattr(args,x)) for x in ("review_a","review_b","gold","auto")))
    write_new(args.output,result)
    print(dumps({"version":VERSION,"output":str(args.output),"questions":len(packet["questions"])}))


if __name__ == "__main__":
    main()
