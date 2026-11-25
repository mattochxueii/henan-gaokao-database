"""Unified Gaokao entry point. Math keeps its existing production workflow."""

import argparse
import os
from pathlib import Path
import sys

import bootstrap  # noqa: F401
from core.catalog import import_science, query, rebuild, science_evidence, use
from core.science_forecast import forecast, score
from core.science_workflow import adjudicate, plan, prepare, publish
from core import board_cli, exam_policy, language_workflow, paper_intake
from forecast_store import write_new
from gaokao import ROOT, dumps, read_json
from subjects import SCIENCES, SUBJECTS


def main(argv=None):
    host_session=(os.environ.get("GAOKAO_SESSION_ID") or os.environ.get("CODEX_THREAD_ID")) if argv is None else None
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    sub = parser.add_subparsers(dest="command",required=True)
    board_cli.arguments(sub)
    sub.add_parser("subjects")
    sub.add_parser("dna").add_argument("subject", choices=paper_intake.PAPER_SUBJECTS)
    context = sub.add_parser("authoring-context", help="读取命题画像和目标卷系近年真题")
    context.add_argument("subject",choices=paper_intake.PAPER_SUBJECTS)
    context.add_argument("--topic")
    context.add_argument("--source-id")
    context.add_argument("--limit",type=int,default=12)
    context.add_argument("--output",type=Path,required=True)
    for action in ("assemble","train"):
        worksheet=sub.add_parser(action)
        worksheet.add_argument("subject",choices=paper_intake.PAPER_SUBJECTS)
        worksheet.add_argument("output",type=Path)
        worksheet.add_argument("--year",type=int)
        worksheet.add_argument("--region")
        worksheet.add_argument("--kind")
        worksheet.add_argument("--topic",required=action=="train")
        worksheet.add_argument("--question-id",action="append",default=[])
        worksheet.add_argument("--paper-id",help="只从这份真题抽题")
        worksheet.add_argument("--limit",type=int,default=6)
        worksheet.add_argument("--adaptation",action="store_true")
        worksheet.add_argument("--title")
        worksheet.add_argument("--minutes",type=int,default=30)
    adapt=sub.add_parser("adapt")
    adapt.add_argument("subject",choices=paper_intake.PAPER_SUBJECTS)
    adapt.add_argument("candidate",type=Path)
    adapt.add_argument("output",type=Path)
    simulate=sub.add_parser("simulate",help="使用绑定近期真题和DNA的原创候选生成整卷")
    simulate.add_argument("subject",choices=paper_intake.PAPER_SUBJECTS)
    simulate.add_argument("year",type=int)
    simulate.add_argument("candidate",type=Path)
    simulate.add_argument("output",type=Path)
    simulate.add_argument("--context",required=True,type=Path)
    simulate.add_argument("--layout-mode", choices=("practice","exam"), default="exam")
    simulate.add_argument("--session",type=Path,help="持久化本轮唯一学科与试卷 ID；修订沿用同一文件")
    simulate.add_argument("--batch-plan",type=Path)
    simulate.add_argument("--batch-candidates",type=Path,nargs="+")
    simulate.add_argument("--slot",type=int)
    trend = sub.add_parser("trend-pack", help="按冻结研判制作独立的数学专题审阅稿")
    trend.add_argument("candidate", type=Path)
    trend.add_argument("output", type=Path)
    trend.add_argument("--context", required=True, type=Path)
    trend.add_argument("--layout-mode", choices=("practice","exam"), default="practice")
    audit=sub.add_parser("quality-audit", help="审查当前学生 PDF 的逐题命题质量")
    audit.add_argument("input",type=Path)
    audit.add_argument("evidence",type=Path)
    audit.add_argument("--blind-review",type=Path)
    audit.add_argument("--previous-rejection",type=Path)
    listen=sub.add_parser("attach-listening")
    listen.add_argument("paper_id")
    listen.add_argument("packet",type=Path)
    policy = sub.add_parser("exam-policy", help="查看地区、年份、卷系对应的政策与来源")
    policy.add_argument("subject",choices=SUBJECTS)
    policy.add_argument("year",type=int)
    policy.add_argument("--region",default="河南")
    policy.add_argument("--series")
    merge = sub.add_parser("merge-sections",help="校验并合并语文或英语的三个创作片段")
    merge.add_argument("subject",choices=language_workflow.LANGUAGES)
    merge.add_argument("year",type=int)
    merge.add_argument("output",type=Path)
    merge.add_argument("parts",type=Path,nargs=3)
    merge.add_argument("--context",type=Path,required=True)
    check=sub.add_parser("workbook-review")
    check.add_argument("output",type=Path)
    check.add_argument("review",type=Path)
    docx = sub.add_parser("docx")
    docx.add_argument("markdown", type=Path)
    docx.add_argument("output", type=Path)
    english_score = sub.add_parser("english-score")
    english_score.add_argument("written", type=float)
    english_score.add_argument("--year",type=int,default=2026)
    english_score.add_argument("--listening",type=float)
    sub.add_parser("math").add_argument("args",nargs=argparse.REMAINDER)
    sub.add_parser("index").add_argument("output",type=Path)
    sub.add_parser("import").add_argument("bundle",type=Path)
    electronic = sub.add_parser("import-electronic", help="从 JSON 或 Markdown 批量导入电子版试卷")
    electronic.add_argument("input", type=Path, help="含卷型和题目元数据的 JSON")
    electronic.add_argument("--markdown", type=Path, help="可选，含逐题题干与答案的 Markdown")
    electronic.add_argument("--images", type=Path, help="实质题图和可选官方原页的本地目录")
    electronic.add_argument("--track", action="store_true", help="写入 Git 跟踪的私有教研目录")
    research = sub.add_parser("research")
    research.add_argument("subject",choices=SUBJECTS)
    research.add_argument("--year",type=int)
    research.add_argument("--adaptation",action="store_true",help="仅查适应性演练")
    research.add_argument("--region")
    research.add_argument("--topic")
    research.add_argument("--limit",type=int,default=10)
    research.add_argument("--verified-only",action="store_true")
    research.add_argument("--official-only",action="store_true",help="只返回已绑定官方原页图像的版本")
    research.add_argument("--strict",action="store_true",help="化学题的跨来源与解答双复核子集")
    research.add_argument("--include-incomplete",action="store_true",help="显示明文档案中的缺图、缺答及隔离题")
    for subject in ("physics", "chemistry"):
        evidence = sub.add_parser(f"{subject}-index", help=f"河南{SUBJECTS[subject]}逐题证据")
        evidence.add_argument("year",type=int)
        evidence.add_argument("--number",type=int)
        evidence.add_argument("--region",default="河南")
    mapping = sub.add_parser("exam")
    mapping.add_argument("subject",choices=SUBJECTS)
    mapping.add_argument("year",type=int)
    mapping.add_argument("--region",default="河南")
    for command in ("plan","generate","forecast"):
        p = sub.add_parser(command)
        p.add_argument("subject",choices=SCIENCES if command=="forecast" else (*SCIENCES,*language_workflow.LANGUAGES))
        p.add_argument("year",type=int)
        p.add_argument("--region",default="河南")
        if command=="forecast":
            p.add_argument("--cutoff",required=True)
            p.add_argument("--evidence",type=Path)
            p.add_argument("--freeze",type=Path)
        else:
            p.add_argument("--mode",choices=("standard","targeted"),default="targeted")
            p.add_argument("--topic",action="append",default=[])
            if command=="generate":
                p.add_argument("candidates",type=Path)
                p.add_argument("output",type=Path)
                p.add_argument("--context",type=Path)
                p.add_argument("--layout-mode", choices=("practice","exam"), default="exam")
    for command in ("review","publish","score"):
        p = sub.add_parser(command)
        p.add_argument("input",type=Path)
        p.add_argument("evidence",type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    command = args.command
    try:
        if command in ("batch-plan","batch-run","batch-check","exam-qa","board-packet","board-score","board-cycle",
                       "export-external-review","import-external-review"):
            result=board_cli.run(root,args)
            print(dumps(result))
            return int(result.get("passed") is False or result.get("status",result.get("state")) in ("returned","rejected"))
        if command=="math":
            from subjects.math import run
            return run(root,args.args)
        if command=="subjects":
            result = [{"id":k,"label":v,"status":"active"}
                      for k,v in SUBJECTS.items()]
        elif command in ("authoring-context","assemble","train","adapt","workbook-review"):
            from core import practice_workbook
            from storage import atomic_json
            if command=="authoring-context":
                result=practice_workbook.authoring_context(root,args.subject,topic=args.topic,
                                                          source_id=args.source_id,limit=args.limit)
                atomic_json(args.output,result)
                result={"output":str(args.output),"reference_count":len(result["references"]),"dna_sha256":result["dna_sha256"]}
            elif command=="adapt":
                result=practice_workbook.adaptive_workbook(root,args.subject,read_json(args.candidate),args.output,
                                                           args.candidate.parent)
            elif command=="workbook-review":
                result=practice_workbook.review_workbook(args.output,read_json(args.review))
            else:
                chosen=practice_workbook.selection(root,args.subject,year=args.year,region=args.region,kind=args.kind,topic=args.topic,
                                                  question_ids=args.question_id,limit=args.limit,adaptation=args.adaptation,
                                                  paper_id=args.paper_id)
                result=practice_workbook.render_archive(root,args.subject,chosen,args.output,
                    title=args.title or SUBJECTS[args.subject]+(f" · {args.topic}专项" if args.topic else " · 历年真题练习"),
                    minutes=args.minutes)
        elif command=="attach-listening":
            from core.paper_listening import attach
            result=attach(root,args.paper_id,read_json(args.packet))
        elif command=="exam-policy":
            series = args.series or (f"cn-ha-{args.subject}-selective" if args.subject in SCIENCES and args.region == "河南"
                                     else exam_policy.NATIONAL_SERIES)
            result=exam_policy.resolve(root,args.subject,args.year,args.region,series)
        elif command=="merge-sections":
            from core.language_sections import merge

            result=merge(root,args.subject,args.year,args.parts,args.context,args.output)
        elif command=="quality-audit":
            from core.quality_audit import submit

            result=submit(args.input,read_json(args.evidence),
                          review=read_json(args.blind_review) if args.blind_review else None,
                          prior=read_json(args.previous_rejection) if args.previous_rejection else None)
            print(dumps(result))
            return 1 if result["status"] == "returned" else 0
        elif command=="trend-pack":
            from core.practice_workbook import validate_authoring_context
            from math_trends import bind_pack_positions
            from mathgen.exam_workflow import prepare as prepare_math

            candidate = read_json(args.candidate)
            reference = validate_authoring_context(root, "math", args.context, candidate)
            candidate["quality_benchmarks"] = bind_pack_positions(reference, candidate)
            result = prepare_math(root, candidate, args.output, layout_mode=args.layout_mode)
        elif command=="simulate":
            from core.practice_workbook import validate_authoring_context

            candidate=read_json(args.candidate)
            quality_reference=validate_authoring_context(root,args.subject,args.context,candidate)
            from core.review_board import VERSION as board_version
            from core.release_checks import VERSION as release_version
            snapshot=exam_policy.resolve(root,args.subject,args.year,"河南",quality_reference["series"])
            quality_reference={**quality_reference,"review_board":board_version,"release_rules":release_version,
                               "qa_policy":read_json(args.context)["anti_patterns"],"exam_policy":snapshot}
            if any((args.batch_plan,args.batch_candidates,args.slot)):
                if not all((args.batch_plan,args.batch_candidates,args.slot)):
                    raise ValueError("批量模拟须同时提供计划、整批候选和卷序")
                quality_reference["batch"]=board_cli.batch_binding(args.subject,args.candidate,args.batch_plan,args.batch_candidates,args.slot)
            else:
                from core.publication_ledger import claim

                if host_session:
                    from analysis_db import fingerprint

                    receipt=root/"work/authoring-sessions"/(fingerprint(host_session)+".json")
                else:
                    receipt=args.session or args.context.with_suffix(".session.json")
                quality_reference["session"]=claim(receipt,args.subject,candidate)
            if candidate.get("constant_observations"):
                quality_reference["constant_observations"]=candidate["constant_observations"]
            candidate={**candidate,"quality_benchmarks":quality_reference}
            if args.subject=="math":
                from math_skill import main as math_main
                return math_main(["--root",str(root),"generate","--engine","ai","--study-mode","standard",
                                  "--mode","full","--skip-pilot","--candidates",str(args.candidate),
                                  "--output",str(args.output),"--layout-mode",args.layout_mode],
                                 quality_reference=quality_reference)
            if args.subject in SCIENCES:
                blueprint=plan(root,args.subject,"河南",args.year,"standard")
                result=prepare(root,blueprint,candidate,args.output,args.candidate.parent,layout_mode=args.layout_mode)
            else:
                from core.quality_audit import language_edition

                blueprint=language_workflow.plan(root,args.subject,"河南",args.year)
                candidate["quality_benchmarks"] = language_edition(quality_reference, blueprint["basis_year"])
                result=language_workflow.prepare(root,blueprint,candidate,args.output,layout_mode=args.layout_mode)
        elif command=="dna":
            result=paper_intake.dna(root,args.subject)
        elif command=="docx":
            from core.language_render import export_docx
            export_docx(args.markdown,args.output)
            result={"output":str(args.output)}
        elif command=="english-score":
            result={"written":args.written,"listening":args.listening,"year":args.year,
                    "henan_score":language_workflow.henan_english_score(args.written,year=args.year,
                                                                     listening=args.listening,root=root)}
        elif command=="research" and (args.subject in language_workflow.LANGUAGES or args.adaptation or args.include_incomplete):
            if args.official_only or args.strict:
                raise ValueError("此查询通道不支持官方原页或历史理科摘要过滤")
            result=paper_intake.research(root,args.subject,year=args.year,region=args.region,topic=args.topic,
                                         limit=args.limit,verified_only=args.verified_only,
                                         exam_kind="adaptation_exam" if args.adaptation else "official_exam",
                                         include_incomplete=args.include_incomplete)
        elif command=="research":
            result = query(root,args.subject,year=args.year,region=args.region,topic=args.topic,
                           limit=args.limit,verified_only=args.verified_only,strict=args.strict,official_only=args.official_only)
            if args.subject=="math":
                extra=paper_intake.research(root,"math",year=args.year,region=args.region,topic=args.topic,
                                            limit=args.limit,verified_only=args.verified_only,exclude_compatible_math=True)
                by_slot={(q["paper_id"],q["number"]):q for q in [*result,*extra]}
                result=list(by_slot.values())[:args.limit]
        elif command in ("physics-index", "chemistry-index"):
            result = science_evidence(root,command.removesuffix("-index"),args.year,args.number,region=args.region)
        elif command=="exam":
            result = (language_workflow.plan(root,args.subject,args.region,args.year)
                      if args.subject in language_workflow.LANGUAGES else use(root,args.subject,args.region,args.year))
        elif command=="index":
            result = rebuild(root,args.output)
        elif command=="import":
            result = import_science(root,args.bundle)
        elif command=="import-electronic":
            from core.science_intake import import_electronic, import_plain
            doc=read_json(args.input)
            if doc["subject"] in paper_intake.CORE:
                result = paper_intake.ingest(root,doc,args.markdown,args.images,track=args.track)
            elif args.track or doc.get("id"):
                result = import_plain(root,doc,args.markdown,args.images,track=args.track)
            else:
                result = import_electronic(root,args.input,args.markdown,args.images)
        elif command in ("plan","generate"):
            if command=="generate" and (args.subject in language_workflow.LANGUAGES or args.mode=="standard"):
                if args.context is None or args.region != "河南":
                    raise ValueError("河南标准卷须先读取 authoring-context，使用 simulate --context")
                invocation=["--root",str(root),"simulate",args.subject,str(args.year),
                             str(args.candidates),str(args.output),"--context",str(args.context),
                             "--layout-mode",args.layout_mode]
                if host_session:
                    from analysis_db import fingerprint

                    invocation.extend(["--session",str(root/"work/authoring-sessions"/(fingerprint(host_session)+".json"))])
                return main(invocation)
            if args.subject in language_workflow.LANGUAGES:
                result=language_workflow.plan(root,args.subject,args.region,args.year)
            else:
                result = plan(root,args.subject,args.region,args.year,args.mode,args.topic)
                if command=="generate":
                    result = prepare(root,result,read_json(args.candidates),args.output,args.candidates.parent,
                                     layout_mode=args.layout_mode)
            if command=="plan":
                from core.publication_ledger import history

                result["publication_history"]=history(root,args.subject)
        elif command=="forecast":
            result = forecast(root,args.subject,args.region,args.year,args.cutoff,
                              read_json(args.evidence) if args.evidence else None)
            if args.freeze:
                write_new(args.freeze,result)
        elif command=="score":
            result = score(read_json(args.input),read_json(args.evidence))
        else:
            packet=read_json(args.input/"blind-packet.json")
            language=packet["paper"].get("subject") in language_workflow.LANGUAGES
            handler=(language_workflow.review if language else adjudicate) if command=="review" else (
                language_workflow.publish if language else publish)
            result=handler(args.input,read_json(args.evidence),root=root) if command=="publish" else handler(args.input,read_json(args.evidence))
        print(dumps(result))
        if command == "exam-qa" and not result["passed"]:
            return 1
        return 0
    except (KeyError, OSError, ValueError, TypeError) as exc:
        print("ERROR",exc,file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
