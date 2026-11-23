"""Unified Gaokao entry point. Math keeps its existing production workflow."""

import argparse
from pathlib import Path
import sys

import bootstrap  # noqa: F401
from core.catalog import import_science, query, rebuild, science_evidence, use
from core.science_forecast import forecast, score
from core.science_workflow import adjudicate, plan, prepare, publish
from forecast_store import write_new
from gaokao import ROOT, dumps, read_json
from subjects import SCIENCES, SUBJECTS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    sub = parser.add_subparsers(dest="command",required=True)
    sub.add_parser("subjects")
    sub.add_parser("math").add_argument("args",nargs=argparse.REMAINDER)
    sub.add_parser("index").add_argument("output",type=Path)
    sub.add_parser("import").add_argument("bundle",type=Path)
    electronic = sub.add_parser("import-electronic", help="从 JSON 或 Markdown 批量导入电子版理科题")
    electronic.add_argument("input", type=Path, help="含卷型和题目元数据的 JSON")
    electronic.add_argument("--markdown", type=Path, help="可选，含逐题题干与答案的 Markdown")
    electronic.add_argument("--images", type=Path, help="实质题图和可选官方原页的本地目录")
    research = sub.add_parser("research")
    research.add_argument("subject",choices=SUBJECTS)
    research.add_argument("--year",type=int)
    research.add_argument("--region")
    research.add_argument("--topic")
    research.add_argument("--limit",type=int,default=10)
    research.add_argument("--verified-only",action="store_true")
    research.add_argument("--official-only",action="store_true",help="只返回已绑定官方原页图像的版本")
    research.add_argument("--strict",action="store_true",help="化学题的跨来源与解答双复核子集")
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
        p.add_argument("subject",choices=SCIENCES)
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
            result = [{"id":k,"label":v,"status":"active" if k in ("math",*SCIENCES) else "catalog_only"}
                      for k,v in SUBJECTS.items()]
        elif command=="research":
            result = query(root,args.subject,year=args.year,region=args.region,topic=args.topic,
                           limit=args.limit,verified_only=args.verified_only,strict=args.strict,official_only=args.official_only)
        elif command in ("physics-index", "chemistry-index"):
            result = science_evidence(root,command.removesuffix("-index"),args.year,args.number,region=args.region)
        elif command=="exam":
            result = use(root,args.subject,args.region,args.year)
        elif command=="index":
            result = rebuild(root,args.output)
        elif command=="import":
            result = import_science(root,args.bundle)
        elif command=="import-electronic":
            from core.science_intake import import_electronic
            result = import_electronic(root,args.input,args.markdown,args.images)
        elif command in ("plan","generate"):
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
        elif command=="review":
            result = adjudicate(args.input,read_json(args.evidence))
        else:
            result = publish(args.input,read_json(args.evidence))
        print(dumps(result))
        return 0
    except (KeyError, OSError, ValueError, TypeError) as exc:
        print("ERROR",exc,file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
