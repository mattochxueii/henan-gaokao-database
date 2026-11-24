"""Unified command-line transport for host reviewers and reusable batch planning."""
from pathlib import Path
from gaokao import read_json, require
from forecast_store import write_new
from subjects import SUBJECTS
from core import batch_planner, review_board


def arguments(sub):
    p=sub.add_parser("batch-plan")
    p.add_argument("subject",choices=SUBJECTS); p.add_argument("output",type=Path)
    p.add_argument("--count",type=int,required=True); p.add_argument("--pool",type=Path)
    p=sub.add_parser("batch-run")
    p.add_argument("plan",type=Path); p.add_argument("year",type=int); p.add_argument("context",type=Path); p.add_argument("job",type=Path)
    p=sub.add_parser("batch-check")
    p.add_argument("plan",type=Path); p.add_argument("candidates",type=Path,nargs="+")
    p.add_argument("--output",type=Path,required=True)
    p=sub.add_parser("export-external-review",help="离线导出版本绑定的学生卷和外部盲审模板")
    p.add_argument("folder",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--year",type=int,help="仅供未登记年份的历史试卷")
    p=sub.add_parser("import-external-review",help="登记外审缺陷并指派下一轮返工题位")
    p.add_argument("folder",type=Path)
    p.add_argument("reply",type=Path)
    for name in ("exam-qa","board-packet","board-score","board-cycle"):
        p=sub.add_parser(name)
        p.add_argument("folder",type=Path)
        if name=="board-packet":
            p.add_argument("role",choices=review_board.ROLES); p.add_argument("output",type=Path)
        elif name=="board-cycle":
            p.add_argument("inbox",type=Path); p.add_argument("--previous",type=Path)
            p.add_argument("--repair-slot",type=int,action="append",default=[])
        elif name=="board-score":
            p.add_argument("reports",type=Path,nargs="*"); p.add_argument("--previous",type=Path)
            p.add_argument("--repair-slot",type=int,action="append",default=[])
        else:
            p.add_argument("--output",type=Path)


def run(root,a):
    if a.command=="batch-plan":
        result=batch_planner.plan(a.subject,a.count,read_json(a.pool) if a.pool else None)
        write_new(a.output,result)
    elif a.command=="batch-run":
        from core.batch_runner import run as produce
        from gaokao_platform import main
        result=produce(root,a.plan,a.year,a.context,a.job,main)
    elif a.command=="batch-check":
        result=batch_planner.check(read_json(a.plan),[read_json(p) for p in a.candidates])
        write_new(a.output,result)
    elif a.command=="board-packet":
        result=review_board.export_blind(root,a.folder,a.role,a.output)
    elif a.command=="board-cycle":
        from core.board_cycle import cycle
        result=cycle(root,a.folder,a.inbox,a.previous,a.repair_slot)
    elif a.command=="board-score":
        result=review_board.record(root,a.folder,[read_json(p) for p in a.reports],a.previous,a.repair_slot)
        if result["protocol"] == review_board.VERSION:
            result=review_board.decision_view(result)
    elif a.command=="export-external-review":
        from core.external_review import export

        result=export(root,a.folder,a.output,year=a.year)
    elif a.command=="import-external-review":
        from core.external_review import import_reply

        result=import_reply(root,a.folder,read_json(a.reply))
    else:
        result=review_board.evidence(root,a.folder,recheck_legacy_policy=True,enforce_release=True)["preflight"]
        if a.output:write_new(a.output,result)
    return result


def batch_binding(subject, candidate_path, plan_path, paths, slot):
    from analysis_db import fingerprint
    plan=read_json(plan_path)
    require(plan["subject"]==subject and slot is not None and 1<=slot<=len(paths)
            and paths[slot-1].resolve()==candidate_path.resolve(),"批次、题本及卷序不匹配")
    require(subject != "physics" or plan.get("physics_corridor"),
            "物理批次须重新规划各卷独立的分值走廊")
    result=batch_planner.check(plan,[read_json(p) for p in paths])
    require(result["passed"],"跨卷碰撞，退回重配："+str(result["issues"]))
    return {"batch_check":result,"slot":slot,"plan_sha256":fingerprint(plan)}
