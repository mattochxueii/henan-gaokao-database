"""Compare paper-level forecasts on fixed, year-blocked historical windows."""

from collections import defaultdict
from pathlib import Path
from statistics import mean
from analysis_db import fingerprint
from forecast_model import (
    annual_blocks, backtest, contemporaneous_observations, course_shares, evidence_by_date,
    loss, usable_date, weighted_beta,
)
from forecast_store import inputs, write_new
from gaokao import ROOT, digest, dumps, read_json, require

MODELS = (
    "even", "historical_rate", "frequency", "last_year", "recent",
    "course_reference", "recent_plus_course", "recent_plus_course_policy",
)
COMPACT = "paper.compact"


def metric(rows):
    if not rows:
        return None
    return {key: mean(row[key] for row in rows) for key in ("brier", "log_loss")}


def score_blocked(rows, models):
    groups = defaultdict(list)
    for row in rows:
        groups[row["year"]].append(row)
    result = {}
    for name in models:
        years = {y: metric([loss(r["p"][name], r["y"]) for r in block]) for y, block in groups.items()}
        metrics = metric(list(years.values()))
        result[name] = {
            "year_equal": metrics, "paper_equal": metric([loss(r["p"][name], r["y"]) for r in rows]),
            "per_year": years, "leave_one_evaluation_year": {
                y: metric([entry for k, entry in years.items() if k != y]) for y in years
            },
        }
    reference = result["even"]["year_equal"]
    for model in result.values():
        model["skill_vs_even"] = {
            k: 1 - model["year_equal"][k] / reference[k] for k in reference
        } if reference else None
    return result


def eligible_for_fold(observations, cutoff, year, held_out_groups):
    end = usable_date(cutoff)
    return [
        r for r in observations if r["year"] < year and r.get("raw_available_on")
        and usable_date(r["raw_available_on"]) <= end
        and not held_out_groups.intersection(r.get("question_groups", []))
    ]


def validate_observations(protocol, observations, *, dated_structure):
    keys = set()
    targets = {x["id"] for x in protocol["targets"]}
    locked = usable_date(protocol["locked_on"])
    for row in observations:
        year, series = row["year"], row["series"]
        require(year in protocol["archive_years"] and series in protocol["series"], "超出固定年份或卷系")
        require((year, series) not in keys, "同年同卷系不得重复")
        keys.add((year, series))
        available = usable_date(row["raw_available_on"])
        labeled = usable_date(row.get("labels_produced_on"))
        require(not available or year <= available.year and available <= locked,
                "原卷证据时间不能早于考试年份或晚于本轮截止")
        if not dated_structure:
            require(labeled and locked <= labeled, "回溯标注时间不能倒填")
            require(bool(row.get("paper_version_sha256")) and row["label_protocol"] == protocol["version"],
                    "缺少历史题面和标签版本绑定")
            if available:
                require(row.get("dated_source"), "缺少原资料日期来源")
        for key, value in row["events"].items():
            require(key in targets and (value is None or type(value) is int and value in (0, 1)),
                    "目标或二值标签不合法")


def predictions(protocol, history, evidence, target, year, cutoff, series):
    blocks = annual_blocks(history, target, series, secondary_weight=1)
    if len(blocks) < protocol["minimum_history_years"]:
        return None, blocks, None
    recent_weights = [2 ** (-(year - max(b["years"]) - 1) / protocol["half_life_years"]) for b in blocks]
    raw = mean(b["value"] for b in blocks)
    freq = weighted_beta(blocks, [1] * len(blocks), protocol["prior"])
    recent = weighted_beta(blocks, recent_weights, protocol["prior"])
    last = next((r["events"].get(target) for r in history
                 if r["year"] == year-1 and r["series"] == series), None)
    eps = protocol["epsilon"]
    course = course_shares(evidence_by_date(evidence, cutoff, year)).get("module.functions")
    external = target == "module.functions_anchor" and course is not None
    course_p = 1 - (1 - course) ** protocol["course_reference_slots"] if external else None
    weight = protocol["course_pseudo_years"]
    effective = sum(protocol["prior"]) + sum(recent_weights)
    course_blend = (recent * effective + weight * course_p) / (effective + weight) if external else recent
    return {
        "even": 0.5, "historical_rate": min(1-eps, max(eps, raw)), "frequency": freq,
        "last_year": 0.5 if last is None else (1-eps if last else eps),
        "recent": recent, "course_reference": course_p if external else 0.5,
        "recent_plus_course": course_blend, "recent_plus_course_policy": course_blend,
    }, blocks, {
        "course_prior_active": external, "policy_numeric_mapping_active": False,
        "last_year_used": last is not None, "unclipped_historical_rate": raw,
    }


def replay(protocol, evidence, observations, *, strict_format=False, legacy=None):
    validate_observations(protocol, observations, dated_structure=strict_format)
    modes = (*MODELS, "legacy_policy_break") if strict_format else MODELS
    targets = [x["id"] for x in protocol["targets"] if
               x["id"] == COMPACT and strict_format or x["disposition"] == "replay" and not strict_format]
    index = {(r["year"], r["series"]): r for r in observations}
    results = {}
    for target in targets:
        scored, skipped = [], []
        for year in protocol["years"]:
            cutoff = f"{year-1}-12-31"
            heldout = set().union(*(r.get("question_groups", []) for r in observations if r["year"] == year))
            history = eligible_for_fold(observations, cutoff, year, heldout)
            docs = evidence_by_date(evidence, cutoff, year)
            for series in protocol["series"]:
                base = {"year": year, "series": series, "cutoff": cutoff}
                row = index.get((year, series))
                if row is None or not row["raw_available_on"] or row["events"].get(target) is None:
                    skipped.append({**base, "reason": "undated_or_unknown_outcome"})
                    continue
                p, blocks, meta = predictions(protocol, history, evidence, target, year, cutoff, series)
                if p is None:
                    skipped.append({**base, "reason": "insufficient_dated_history", "training_blocks": blocks})
                    continue
                if strict_format:
                    p["legacy_policy_break"] = legacy[(year, series)]
                used = {p_id for b in blocks for p_id in b["papers"]}
                scored.append({
                    **base, "y": row["events"][target], "p": p, "inputs": meta,
                    "policy_candidates_as_of": sorted(k for k, e in docs.items() if e["type"] == "PolicyDocument"),
                    "training_blocks": blocks,
                    "training_dates": {r["paper_id"]: r["raw_available_on"] for r in history if r["paper_id"] in used},
                    "training_evidence": {r["paper_id"]: r["dated_source"] for r in history if r["paper_id"] in used},
                    "outcome_available_on": row["raw_available_on"],
                    "outcome_evidence": row["dated_source"],
                })
        # Keep the known structure break explicit. These are diagnostics on the same fitted folds.
        year_counts = len({r["year"] for r in scored})
        results[target] = {
            "n": len(scored), "year_blocks": year_counts,
            "outcomes": {str(i): sum(r["y"] == i for r in scored) for i in (0, 1)},
            "scores": score_blocked(scored, modes), "scored": scored, "skipped": skipped,
            "structural_break_slices": {
                label: score_blocked(subset, modes) for label, subset in (
                    ("2024_only", [r for r in scored if r["year"] == 2024]),
                    ("without_2024", [r for r in scored if r["year"] != 2024]),
                ) if subset
            },
            "discrimination_status": (
                "outcome_does_not_vary" if scored and len({r["y"] for r in scored}) == 1 else
                "insufficient_evaluation_years" if year_counts < protocol["minimum_replay_years"] else
                "exploratory_only"
            ),
            "external_increments": {
                "course_active_pairs": sum(r["inputs"]["course_prior_active"] for r in scored),
                "policy_active_pairs": 0, "teaching_saturation_measurements": 0,
                "comparison_order": ["recent", "recent_plus_course", "recent_plus_course_policy"],
            },
        }
    return results


def run(root, archive=None):
    spec, evidence, raw = inputs(root)
    protocol_file = root / "forecast/validation/protocol.json"
    protocol = read_json(protocol_file)
    require(digest(protocol_file) == "b8f4bb87bd94831d52011929dd0d38319dd649d7bbcf6f889ad0bb0752e4ca9c",
            "协议与评价前锁定的内容不一致，请建立新版")
    dated = contemporaneous_observations(raw, evidence)
    previous = backtest(spec, evidence, dated, years=protocol["years"])
    legacy = {(r["year"], r["series"]): r["p"] for f in previous["folds"] for r in f["scored"]
              if r["model"] == "policy_experiment" and r["target"] == COMPACT}
    phase10 = root / "forecast/research/backtest.json"
    if phase10.exists():
        require(previous == read_json(phase10), "第十阶段原始回测重算不一致")
    format_rows = [{**r, "raw_available_on": r["available_on"], "dated_source": r["evidence"]} for r in dated]
    format_replay = replay(protocol, evidence, format_rows, strict_format=True, legacy=legacy)
    require(format_replay[COMPACT]["n"] == len(legacy), "共同评价集合和原题量回测不一致")
    reconstructed = None
    if archive is not None:
        require(archive["protocol_sha256"] == digest(protocol_file), "历史标签的协议版本不符")
        dates_path = root / "forecast/validation/paper-dates.json"
        require(archive["dates_sha256"] == digest(dates_path), "历史标签的来源日期版本不符")
        sources = {(r["year"], r["series"]): (r["raw_available_on"], r["url"])
                   for r in read_json(dates_path)["records"]}
        for row in archive["observations"]:
            require((row["raw_available_on"], row["dated_source"]) ==
                    sources.get((row["year"], row["series"]), (None, None)),
                    "题面可用日期与带日期来源不一致")
        reconstructed = replay(protocol, evidence, archive["observations"])
    return {
        "protocol": protocol["version"], "protocol_sha256": digest(protocol_file),
        "legacy_results_fingerprint": fingerprint(previous),
        "legacy_results_match_tracked": phase10.exists(),
        "as_of_dated_replay": format_replay,
        "retrospective_label_replay": reconstructed,
        "retrospective_input_fingerprint": fingerprint(archive) if archive is not None else None,
        "prospective_scored": 0,
        "designs": {
            "as_of_dated_replay": "date-gated facts with retrospectively selected comparison rules",
            "retrospective_label_replay": "dated source papers with later version-bound coding",
            "legacy_policy_break": "post-outcome model-selection risk even with date-gated features",
        },
        "status": "four_correlated_years_no_inference",
    }


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--archive", type=Path, help="Private date- and version-bound observations")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.root, read_json(args.archive) if args.archive else None)
        if args.output:
            write_new(args.output, result)
        print(dumps(result if not args.output else {
            "output": str(args.output), "protocol": result["protocol"],
            "as_of_dated_replay": {k: v["n"] for k, v in result["as_of_dated_replay"].items()},
            "retrospective_label_replay": {k: v["n"] for k, v in
                                           (result["retrospective_label_replay"] or {}).items()},
        }))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("ERROR", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
