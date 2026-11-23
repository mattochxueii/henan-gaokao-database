"""Unified Gaokao entry point. Math keeps its existing production workflow."""

import argparse
from pathlib import Path
import sys

import bootstrap  # noqa: F401
from core.catalog import import_science, query, rebuild, science_evidence, use
from core.science_forecast import forecast, score
from core.science_workflow import adjudicate, plan, prepare, publish
from core import language_workflow, paper_intake
from forecast_store import write_new
from gaokao import ROOT, dumps, read_json
from subjects import SCIENCES, SUBJECTS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    sub = parser.add_subparsers(dest="command",required=True)
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
    listen=sub.add_parser("attach-listening")
    listen.add_argument("paper_id")
    listen.add_argument("packet",type=Path)
    check=sub.add_parser("workbook-review")
    check.add_argument("output",type=Path)
    check.add_argument("review",type=Path)
    docx = sub.add_parser("docx")
    docx.add_argument("markdown", type=Path)
    docx.add_argument("output", type=Path)
    sub.add_parser("english-score").add_argument("written", type=float)
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
    for command in ("review","publish","score"):
        p = sub.add_parser(command)
        p.add_argument("input",type=Path)
        p.add_argument("evidence",type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    command = args.command
    try:
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
                                                  question_ids=args.question_id,limit=args.limit,adaptation=args.adaptation)
                result=practice_workbook.render_archive(root,args.subject,chosen,args.output,
                    title=args.title or SUBJECTS[args.subject]+(f" · {args.topic}专项" if args.topic else " · 历年真题练习"),
                    minutes=args.minutes)
        elif command=="attach-listening":
            from core.paper_listening import attach
            result=attach(root,args.paper_id,read_json(args.packet))
        elif command=="simulate":
            from analysis_db import fingerprint
            from core.practice_workbook import authoring_context
            from gaokao import digest, require
            packet=read_json(args.context)
            candidate=read_json(args.candidate)
            actual=authoring_context(root,args.subject,**packet["query"])
            years = {2025,2026} if args.subject in SCIENCES else {2024,2025,2026}
            require(fingerprint(actual)==fingerprint(packet) and packet["subject"]==args.subject
                    and not packet["query"]["topic"] and not packet["query"]["source_id"]
                    and years<={q["year"] for q in packet["references"]},
                    "整卷上下文须覆盖目标卷系已要求的完整年份范围，并绑定当前命题画像")
            proof=candidate.get("provenance",{})
            require(proof.get("dna_sha256")==actual["dna_sha256"] and
                    proof.get("context_sha256")==digest(args.context),"候选须绑定当前命题上下文")
            if args.subject=="math":
                from math_skill import main as math_main
                return math_main(["--root",str(root),"generate","--engine","ai","--study-mode","standard",
                                  "--mode","full","--skip-pilot","--candidates",str(args.candidate),
                                  "--output",str(args.output)])
            if args.subject in SCIENCES:
                blueprint=plan(root,args.subject,"河南",args.year,"standard")
                result=prepare(root,blueprint,candidate,args.output,args.candidate.parent)
            else:
                blueprint=language_workflow.plan(root,args.subject,"河南",args.year)
                result=language_workflow.prepare(root,blueprint,candidate,args.output)
        elif command=="dna":
            result=paper_intake.dna(root,args.subject)
        elif command=="docx":
            from core.language_render import export_docx
            export_docx(args.markdown,args.output)
            result={"output":str(args.output)}
        elif command=="english-score":
            result={"written":args.written,"henan_score":language_workflow.henan_english_score(args.written)}
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
            if args.subject in language_workflow.LANGUAGES:
                result=language_workflow.plan(root,args.subject,args.region,args.year)
                if command=="generate":
                    result=language_workflow.prepare(root,result,read_json(args.candidates),args.output)
            else:
                result = plan(root,args.subject,args.region,args.year,args.mode,args.topic)
                if command=="generate":
                    result = prepare(root,result,read_json(args.candidates),args.output,args.candidates.parent)
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
            result=handler(args.input,read_json(args.evidence))
        print(dumps(result))
        return 0
    except (KeyError, OSError, ValueError, TypeError) as exc:
        print("ERROR",exc,file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
