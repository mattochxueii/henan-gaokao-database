"""Runnable, append-only workflows for forecast research and evaluation."""

from datetime import date
from pathlib import Path
from gaokao import ROOT, digest, dumps, read_json, require
from analysis_db import fingerprint
from forecast_features import aggregate, feature_ledger
from forecast_model import backtest, contemporaneous_observations, course_shares, evidence_by_date, loss, predict
from forecast_store import envelope, frozen, inputs, materialize, model_files, paper_catalog, write_new


def archive_observations(records, papers, dated):
    result = aggregate(records, papers)
    by_key = {(r["year"],r["series"]):r for r in dated if "paper.compact" in r["events"]}
    for row in result:
        fact = by_key.get((row["year"],row["series"]))
        if fact:
            require(row["events"]["paper.compact"] == fact["events"]["paper.compact"],
                    "档案题量与同期证据冲突")
            row["format_evidence"] = fact["evidence"]
    return result


def hypotheses(evidence, archive, report, *, year, cutoff):
    courses = course_shares(evidence_by_date(evidence, cutoff, year))
    comparisons = {}
    if courses:
        for model, expected in (("course_hours",courses), ("equal_four_modules",{k:0.25 for k in courses})):
            bounds = []
            for row in archive:
                for key, forecast in expected.items():
                    lower, upper = row["shares"][key]
                    bounds.append((max(lower-forecast,forecast-upper,0),
                                   max(abs(lower-forecast),abs(upper-forecast))))
            comparisons[model] = {
                "n_paper_topics":len(bounds),
                "mean_absolute_error_bounds":[sum(b[i] for b in bounds)/len(bounds) for i in (0,1)] if bounds else None,
            }
    return {
        "A_course_weight": {
            "exposure":"数学必修和选择性必修中四个主模块建议课时，去掉建模活动和机动",
            "response":"已复核题按主模块的原始满分比重，未确认分保留区间",
            "design":"跨卷描述性比较；每卷每主题为一个观察，年份和主题相关",
            "baseline":"四类等权作为可比较零模型",
            "success_rule":"课时模型的平均绝对误差上界低于等权基线的下界才支持稳健改进",
            "source":"curriculum-2020","models":comparisons,
            "status":(
                "bounded_descriptive_support" if comparisons
                and comparisons["course_hours"]["mean_absolute_error_bounds"]
                and comparisons["course_hours"]["mean_absolute_error_bounds"][1]
                    < comparisons["equal_four_modules"]["mean_absolute_error_bounds"][0]
                else "insufficient_to_distinguish"
            ),
        },
        "B_reform_transmission":{
            "exposure":"按同期可用文件记录的卷型分界、河南3+1+2、全国评价要求",
            "response":"实际不足22题的试卷，能力考查改变需另有同期标签",
            "control":"历史频率与近期加权；同年I/II作相关观察",
            "time_order":"2024年卷型先变，2025年建设纲要后发；河南2025实行改革，不能据此解释全国2024变化",
            "success_rule":"政策模型在足够独立年份重复降低同期滚动损失，并对能力标签有稳定证据",
            "observed_scored_years":sorted({f["year"] for f in report["folds"] if f["scored"]}),
            "annual_brier_deltas":report["paired_annual_brier_deltas"].get("policy_experiment",[]),
            "status":"observable_format_break_causal_and_capability_effect_not_identified",
        },
        "C_teaching_saturation":{
            "exposure":"考前教辅和联考中预注册套路的采用率，需要可归档发布时间和稳定抽样框",
            "response":"后续同类套路在独立编码真题中的占比，检验分卷型和跨年滞后",
            "control":"无饱和变量的近期模型，按教辅来源聚类",
            "success_rule":"滞后外部变量在分组回测中稳定改善损失；无覆盖或不能改善即不支持",
            "qualitative_evidence":["teaching-direction-2021"],"quantitative_exposures":0,
            "status":"not_testable_without_dated_teaching_corpus",
        },
    }


def versioned_prediction(root, spec, evidence, observed, *, year, cutoff, series, label):
    result = predict(spec,evidence,observed,year=year,cutoff=cutoff,series=series)
    result.update({
        "run_id":label,"model_files_sha256":model_files(root),
        "target_spec_sha256":fingerprint(spec),"registry_sha256":fingerprint(evidence),
        "target_identity":{
            "region":"河南","subject":"math","exam_system":"3+1+2",
            "series_status":"全国Ⅰ卷为条件性研究设定，须待实际适用卷确认",
            "confirmed_system_evidence":"henan-2027-registration" if year == 2027 else None,
        },
        "prospective_grade":{
            "status":"await_official_paper_and_independent_feature_audit",
            "binary_metrics":["brier","log_loss"],
            "share_metric":"绝对误差区间；只有实际完整且同口径才给点值",
            "missing":"无证据和不明卷型不评分，不当作0",
            "identity_rule":"河南实际适用卷与冻结卷系不同，则本卷系条件预测不可计分",
        },
        "timestamp_status":"append_only_sha256; no_independent_timestamp_token",
        "probability_scope":"互不排斥的纸卷级事件；无高考分数、考生难度或原题命中预测",
    })
    return envelope(result)


def score_future(snapshot, outcome, today=None):
    payload = snapshot["payload"]
    require(snapshot["payload_sha256"] == fingerprint(payload), "预测校验失败")
    now = today or date.today()
    visible = date.fromisoformat(outcome["published_on"])
    exam = date.fromisoformat(outcome["exam_date"])
    require(exam.year == visible.year == payload["target_year"] and exam <= visible <= now
            and exam > date.fromisoformat(payload["as_of"]), "结果须在目标考试之后真实可用")
    require(outcome["target_year"] == payload["target_year"]
            and outcome["subject"] == "math" and outcome["region"] == "河南"
            and outcome["series"] == payload["series"] and outcome["series_confirmed"] is True,
            "实际适用卷与预测条件不符或尚未确认")
    require(outcome["independent_review"] is True and outcome["paper_version_sha256"]
            and outcome["target_spec_sha256"] == payload["target_spec_sha256"]
            and outcome["official_identity_url"].startswith("https://"), "缺少独立标签与版本证据")
    result = []
    for row in payload["predictions"]:
        value = outcome["events"].get(row["target"])
        if value is None:
            continue
        require(type(value) is int and value in (0,1), "实测标签必须是0、1或未知")
        result.extend({"target":row["target"],"model":m,"p":p,"y":value,**loss(p,value)}
                      for m,p in row["probabilities"].items() if p is not None)
    shares = []
    for row in payload["predictions"]:
        actual = outcome.get("shares",{}).get(row["target"])
        predicted = row["primary_score_share_bounds"]
        if actual is not None and predicted is not None:
            lo,hi = predicted
            require(type(actual) in (int,float) and 0 <= actual <= 1,"实测分值占比越界")
            shares.append({"target":row["target"],"actual":actual,"predicted":predicted,
                           "absolute_error_bounds":[max(lo-actual,actual-hi,0),max(abs(actual-lo),abs(actual-hi))]})
    return {"snapshot_sha256":snapshot["payload_sha256"],"outcome_sha256":fingerprint(outcome),
            "binary_scores":result,"share_scores":shares,"questions_quality_assessed":False}


def main(argv=None):
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    commands = parser.add_subparsers(dest="command",required=True)
    report = commands.add_parser("backtest")
    report.add_argument("--output",type=Path)
    study = commands.add_parser("study")
    study.add_argument("--audit",required=True,type=Path)
    study.add_argument("--output",required=True,type=Path)
    study.add_argument("--cutoff",required=True)
    study.add_argument("--snapshot",required=True,type=Path)
    lite = commands.add_parser("database")
    lite.add_argument("--output",required=True,type=Path)
    verify = commands.add_parser("verify-freeze")
    verify.add_argument("snapshot",type=Path)
    score = commands.add_parser("score")
    score.add_argument("snapshot",type=Path)
    score.add_argument("outcome",type=Path)
    score.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    root=args.root.resolve()
    try:
        if args.command=="verify-freeze":
            record=frozen(args.snapshot)
            result={"run_id":record["payload"]["run_id"],"sha256":record["payload_sha256"],"valid":True}
        elif args.command=="score":
            result=score_future(frozen(args.snapshot),read_json(args.outcome))
            if args.output:
                write_new(args.output,result)
        else:
            spec,evidence,entries=inputs(root)
            dated=contemporaneous_observations(entries,evidence)
            tests=backtest(spec,evidence,dated)
            if args.command=="backtest":
                if args.output:
                    write_new(args.output,tests)
                result={"metrics":tests["metrics"],"scope":tests["scope"],
                        "independent_years_at_most":tests["independent_years_at_most"]}
            elif args.command=="database":
                result=materialize(args.output,spec,evidence,[],dated,[],backtest=tests)
            else:
                require(not args.output.exists() and not args.snapshot.exists(),"请为研究与冻结指定新路径")
                independent=read_json(args.audit)
                release=independent["available_on"]
                require(date(2026,11,10) <= date.fromisoformat(release)
                        <= date.fromisoformat(args.cutoff) <= date.today(), "禁止倒填或预填标签及冻结日期")
                records,agreement=feature_ledger(root,independent,release)
                archive=archive_observations(records,paper_catalog(root),dated)
                obj=versioned_prediction(root,spec,evidence,archive,year=2027,cutoff=args.cutoff,series="I",label=args.snapshot.stem)
                obj["payload"]["features_sha256"]=fingerprint(records)
                obj["payload"]["independent_labels_sha256"]=digest(args.audit)
                obj["payload_sha256"]=fingerprint(obj["payload"])
                args.output.mkdir(parents=True)
                write_new(args.output/"features.json",records)
                write_new(args.output/"observations.json",archive)
                write_new(args.output/"agreement.json",agreement)
                write_new(args.output/"backtest.json",tests)
                write_new(args.output/"hypotheses.json",hypotheses(evidence,archive,tests,year=2027,cutoff=args.cutoff))
                result=materialize(args.output/"research.sqlite",spec,evidence,records,dated,archive,prediction=obj,backtest=tests)
                write_new(args.snapshot,obj)
                result={"counts":result,"snapshot_sha256":obj["payload_sha256"],"agreement":agreement}
        print(dumps(result))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as error:
        print("ERROR",error,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
