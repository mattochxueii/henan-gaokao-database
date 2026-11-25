"""Dated rolling probability models for an intentionally small paper archive."""

from collections import defaultdict
from datetime import date
import math
from analysis_db import fingerprint
from gaokao import require

VERSION = "math-probability-v1"
MODELS = ("frequency", "recent", "curriculum", "policy_experiment")


def usable_date(value):
    return date.fromisoformat(value) if value else None


def evidence_by_date(evidence, cutoff, year):
    end = usable_date(cutoff)
    return {
        e["id"]: e for e in evidence
        if e["subject"] == "math" and e["available_on"]
        and usable_date(e["available_on"]) <= end
        and (e["applies_from"] is None or e["applies_from"] <= year)
        and (e["applies_to"] is None or year <= e["applies_to"])
    }


def contemporaneous_observations(entries, evidence):
    registry = {e["id"]: e for e in evidence}
    result = []
    seen = set()
    for entry in entries:
        e = registry[entry["evidence"]]
        require(e["type"] == "OfficialReview" and e["available_on"]
                and e["applies_from"] <= entry["year"] <= e["applies_to"]
                and type(entry["value"]) is int and entry["value"] in (0, 1),
                "同期记录与证据类型、时间或二值不符")
        key = (entry["year"], entry["series"], entry["target"])
        require(key not in seen, "同一套全国卷的重复同期观察")
        seen.add(key)
        result.append({
            "paper_id": f"core-{entry['year']}-{entry['series']}", "year": entry["year"],
            "series": entry["series"], "available_on": e["available_on"],
            "events": {entry["target"]: entry["value"]}, "shares": {},
            "question_groups": [], "evidence": [e["id"]],
        })
    return result


def eligible(rows, cutoff, target_year):
    end = usable_date(cutoff)
    require(end.year < target_year, "预测截止须早于目标考试年份")
    selected = [
        row for row in rows if row["year"] < target_year and row.get("available_on")
        and usable_date(row["available_on"]) <= end
    ]
    keys = [(row["year"], row["series"], target) for row in selected for target in row["events"]]
    require(len(keys) == len(set(keys)), "同卷重复，须合并省份和版本后再估计")
    return selected


def annual_blocks(rows, target, series, secondary_weight=0.5):
    # Year is the unit. Related question groups spanning years merge those years
    # into one effective block, while official same-year papers are averaged.
    known = [r for r in rows if r["events"].get(target) is not None]
    parents = {r["year"]: r["year"] for r in known}
    first = {}
    def find(year):
        while parents[year] != year:
            year = parents[year]
        return year
    for r in known:
        for group in r.get("question_groups", []):
            year = r["year"]
            earlier = first.setdefault(group, year)
            parents[find(earlier)] = find(year)
    buckets = defaultdict(lambda: defaultdict(list))
    for row in known:
        buckets[find(row["year"])][row["year"]].append(row)
    result = []
    for cluster in buckets.values():
        years = sorted(cluster)
        values = []
        for year in years:
            matched = cluster[year]
            weights = [1 if r["series"] == series else secondary_weight for r in matched]
            values.append(sum(w * r["events"][target] for w, r in zip(weights, matched)) / sum(weights))
        result.append({"years": years, "value": sum(values) / len(values),
                       "papers": [r["paper_id"] for y in years for r in cluster[y]]})
    return sorted(result, key=lambda b: b["years"])


def course_shares(documents):
    weight = documents.get("curriculum-2020")
    if weight is None:
        return {}
    hours = weight["variables"]["hours"]
    keys = ("foundations", "functions", "geometry", "probability")
    totals = {key: sum(v.get(key, 0) for v in hours.values()) for key in keys}
    denominator = sum(totals.values())
    return {"module." + k: v / denominator for k, v in totals.items()}


def weighted_beta(blocks, weights, prior):
    a, b = prior
    return (a + sum(w * t["value"] for t, w in zip(blocks, weights, strict=True))) / (a + b + sum(weights))


def predict(spec, evidence, observations, *, year, cutoff, series):
    source = eligible(observations, cutoff, year)
    docs = evidence_by_date(evidence, cutoff, year)
    curriculum = course_shares(docs)
    cfg = spec["models"]
    # This is a lagged structural observation, admitted only once published.
    structural_change_known = any(
        r["year"] == 2024 and r["events"].get("paper.compact") == 1
        and "review-2024" in (r.get("evidence") or r.get("format_evidence", []))
        for r in source
    )
    result = []
    for item in spec["targets"]:
        key = item["id"]
        blocks = annual_blocks(source, key, series, cfg["secondary_series_weight"])
        coverage = [r for r in source if key in r["events"]]
        unknown = sum(r["events"][key] is None for r in coverage)
        low_coverage = unknown > len(coverage) * cfg["max_unknown_fraction"]
        enough = len(blocks) >= cfg["min_years"] and not low_coverage
        zero_structure = enough and key.startswith("structure.") and not any(b["value"] > 0 for b in blocks)
        raw = [1] * len(blocks)
        recent = [2 ** (-(year - max(block["years"]) - 1) / cfg["recent_half_life_years"]) for block in blocks]
        hist = weighted_beta(blocks, raw, cfg["beta_prior"]) if enough else None
        lag = weighted_beta(blocks, recent, cfg["beta_prior"]) if enough else None
        course = 1 - (1 - curriculum[key]) ** cfg["curriculum_effective_slots"] if key in curriculum else None
        experiment = None
        policy_path = []
        if enough:
            experiment = lag
            if key == "paper.compact" and structural_change_known:
                weights = [w if min(b["years"]) >= 2024 else w * cfg["pre_break_format_weight"]
                           for b, w in zip(blocks, recent)]
                experiment = weighted_beta(blocks, weights, cfg["beta_prior"])
                policy_path.append("review-2024")
            priors = []
            if course is not None:
                priors.append(course)
                policy_path.append("curriculum-2020")
            if key in {"method.context", "method.linked"} and "evaluation-2020" in docs:
                priors.append(0.65)  # explicit, uncalibrated editorial prior
                policy_path.append("evaluation-2020")
            if key in {"method.proof", "method.linked"} and "national-plan-2025" in docs:
                priors.append(0.70)
                policy_path.append("national-plan-2025")
            if priors:
                w = cfg["policy_pseudo_years"]
                experiment = (experiment * (2 + sum(recent)) + w * sum(priors)) / (2 + sum(recent) + w * len(priors))
        paired_shares = [
            r["shares"][key] for r in source if key in r["shares"] and r["series"] == series
        ]
        share_range = ([sum(x[i] for x in paired_shares) / len(paired_shares) for i in (0, 1)]
                       if len(paired_shares) >= cfg["min_years"] else None)
        # Missing primary points propagate as an interval, not a fabricated precise allocation.
        reference = curriculum.get(key)
        blend = ([(x * len(paired_shares) + reference) / (len(paired_shares) + 1) for x in share_range]
                 if share_range is not None and reference is not None else share_range)
        sensitivity = None
        if len(blocks) >= 3:
            ref = [weighted_beta(blocks[:i] + blocks[i+1:], [1] * (len(blocks)-1), cfg["beta_prior"])
                   for i in range(len(blocks))]
            sensitivity = [min(ref), max(ref)]
        coverage_range = None
        if unknown:
            endpoints = []
            for value in (0, 1):
                completed = [{**r, "events": {**r["events"], key: value}}
                             if r["events"][key] is None else r for r in coverage]
                completed_blocks = annual_blocks(completed, key, series, cfg["secondary_series_weight"])
                if len(completed_blocks) >= cfg["min_years"]:
                    endpoints.append(weighted_beta(completed_blocks, [1]*len(completed_blocks), cfg["beta_prior"]))
            if len(endpoints) == 2:
                coverage_range = endpoints
        result.append({
            "target": key, "layer": item["layer"], "title": item["title"],
            "probabilities": dict(zip(MODELS, (hist, lag, course, experiment), strict=True)),
            "primary_score_share_bounds": share_range, "curriculum_share_reference": reference,
            "policy_score_share_bounds": blend, "effective_year_blocks": len(blocks),
            "training_papers": sorted({p for block in blocks for p in block["papers"]}),
            "training_years": sorted({y for b in blocks for y in b["years"]}),
            "frequency_leave_one_block_range": sensitivity, "used_prior_evidence": policy_path,
            "paper_observations": len(coverage), "unknown_paper_observations": unknown,
            "frequency_missing_label_range": coverage_range,
            "support": ("prior_dominated_zero_positive" if zero_structure else
                        "estimated" if enough else "too_many_unknown_labels"
                        if low_coverage else "insufficient_dated_observations"),
        })
    return {
        "model_version": VERSION, "target_version": spec["version"], "as_of": cutoff,
        "target_year": year, "series": series, "input_sha256": fingerprint(source),
        "evidence_sha256": fingerprint(docs), "visible_policy_evidence": sorted(docs),
        "retrospective_features_allowed": any(not r.get("evidence") for r in source),
        "predictions": result,
    }


def loss(p, y):
    require(0 < p < 1 and y in (0, 1), "概率或结果越界")
    return {"brier": (p-y)**2, "log_loss": -math.log(p if y else 1-p)}


def summarize(scored):
    if not scored:
        return {"n": 0, "brier": None, "log_loss": None, "reliability": []}
    bins = defaultdict(list)
    for row in scored:
        bins[min(3, int(row["p"] * 4))].append(row)
    return {
        "n": len(scored), "brier": sum(row["brier"] for row in scored) / len(scored),
        "log_loss": sum(row["log_loss"] for row in scored) / len(scored),
        "reliability": [{
            "bounds": [i/4, (i+1)/4], "n": len(rows),
            "mean_p": sum(r["p"] for r in rows)/len(rows),
            "rate": sum(r["y"] for r in rows)/len(rows),
        } for i, rows in sorted(bins.items())],
    }


def backtest(spec, evidence, contemporaneous, years=(2023, 2024, 2025, 2026)):
    # Model selection and feature curation are later than these exams. Dated
    # input isolation makes this an as-of replay, never a historical pre-registration.
    folds = []
    pooled = defaultdict(list)
    paired = defaultdict(list)
    for year in years:
        cutoff = f"{year-1}-12-31"
        current = []
        forecasts = {}
        for series in ("I", "II"):
            run = predict(spec, evidence, contemporaneous, year=year, cutoff=cutoff, series=series)
            forecasts[series] = run
            truth = {k: v for r in contemporaneous if r["year"] == year and r["series"] == series
                     for k, v in r["events"].items()}
            for item in run["predictions"]:
                k = item["target"]
                if k not in truth:
                    continue
                for model, p in item["probabilities"].items():
                    if p is None:
                        continue
                    row = {"year": year, "series": series, "target": k, "model": model,
                           "p": p, "y": truth[k], **loss(p, truth[k])}
                    current.append(row)
                    pooled[model].append(row)
        by_key = {(r["series"], r["target"], r["model"]): r for r in current}
        for model in MODELS[1:]:
            differences = [
                r["brier"] - by_key[(r["series"], r["target"], "frequency")]["brier"]
                for r in current if r["model"] == model
                and (r["series"], r["target"], "frequency") in by_key
            ]
            if differences:
                paired[model].append({"year": year, "n": len(differences),
                                      "brier_delta": sum(differences) / len(differences)})
        folds.append({"year": year, "cutoff": cutoff, "forecasts": forecasts, "scored": current})
    return {
        "version": VERSION, "scope": "strict_dated_inputs_only", "folds": folds,
        "metrics": {m: summarize(pooled[m]) for m in MODELS},
        "paired_annual_brier_deltas": dict(paired),
        "independent_years_at_most": len(years),
        "limitations": "研究方案制定于2026年；同期证据仅覆盖卷面题数。卷内方向相关，I/II同年非独立。样本不足以证明校准或泛化。",
    }
