"""Resume a multi-edition job from its author and reviewer inboxes, without releasing partial batches."""
from forecast_store import write_new
from gaokao import digest, read_json, require
from analysis_db import fingerprint
from core.batch_planner import check
from core.board_cycle import cycle


def run(root, schedule_file, year, context, job, invoke, providers=None):
    schedule=read_json(schedule_file)
    subject=schedule["subject"]
    slots=list(range(1,schedule["count"]+1))
    accepted={}
    previous={}
    active=set(slots)

    def invoke_ok(args):
        require(invoke(["--root",str(root),*map(str,args)])==0,"工作流子步骤失败："+args[0])

    for number in range(1,4):
        work={s:job/f"paper-{s}"/f"round{number}" for s in active}
        files={s:work[s]/"candidate.json" if s in active else accepted[s][0] for s in slots}
        missing=[str(p) for p in files.values() if not p.is_file()]
        if missing:return {"state":"await_host_author","round":number,"required":missing}
        candidates=[read_json(files[s]) for s in slots]
        cross=check(schedule,candidates)
        cross_file=job/f"cross-round{number}.json"
        if cross_file.is_file():
            require(read_json(cross_file)==cross,"本轮候选已登记，请在下一轮改稿")
        else:write_new(cross_file,cross)
        if not cross["passed"]:
            if number==3:return {"state":"rejected","round":number,"collisions":cross["issues"]}
            # Every paper carries forward; only nominated questions may be edited.
            next_paths=[]
            for s,c in zip(slots,candidates,strict=True):
                if s not in active:continue
                targets={i["number"] for i in cross["issues"] if i["paper"]==s}
                targets.update(i["compares_to"][1] for i in cross["issues"]
                               if i["paper"] not in active and i.get("compares_to",[0])[0]==s)
                path=job/f"paper-{s}"/f"round{number+1}"/"candidate.json"
                if not targets and not path.exists():
                    import shutil
                    shutil.copytree(files[s].parent,path.parent,dirs_exist_ok=True,
                                    ignore=shutil.ignore_patterns("delivery","inbox"))
                if not path.exists():
                    next_paths.append({"paper":s,"rewrite":sorted(targets),"path":str(path)})
                else:
                    new=read_json(path)
                    require(len(new["questions"])==len(c["questions"]) and all(
                        fingerprint(a)==fingerprint(b) for n,(a,b) in enumerate(
                            zip(c["questions"],new["questions"],strict=True),1) if n not in targets),
                        "跨卷返工改变了锁定题目")
            if next_paths:return {"state":"await_collision_rewrite","round":number,"requests":next_paths}
            continue
        pending=[]
        for s in sorted(active):
            folder=work[s]/"delivery"
            if not folder.exists():
                invoke_ok(["simulate",subject,year,files[s],folder,"--context",context,"--batch-plan",schedule_file,
                           "--batch-candidates",*[files[k] for k in slots],"--slot",s])
            # Bind resume to exactly the scheduled candidate, even after an interrupted invocation.
            from core.quality_audit import _paper_inputs
            reference=_paper_inputs(folder)[0]
            require(reference["batch"]["batch_check"]==cross and reference["batch"]["slot"]==s,
                    "历史送审稿与本批候选不符")
            requested=work[s]/"repair-slots.json"
            decision=cycle(root,folder,work[s]/"inbox",previous.get(s),
                           read_json(requested) if requested.is_file() else (),providers=providers)
            if decision["state"]=="eligible":
                accepted[s]=(files[s],folder)
            elif decision["state"]=="returned":
                previous[s]=folder
            elif decision["state"]=="rejected":
                return {"state":"rejected","paper":s,"decision":decision}
            else:pending.append({"paper":s,**decision})
        if pending:return {"state":"await_isolated_readers","pending":pending}
        active.difference_update(accepted)
        if active:continue

        # The original subject gates still check the independent solutions, positions and both PDF hashes.
        needed=[]
        for s,(_,folder) in accepted.items():
            signatures=folder.parent/"signoff"
            names=(["review","comparison","audit"] if subject=="math" else ["review","audit","visual"])
            needed.extend(str(signatures/(name+".json")) for name in names if not (signatures/(name+".json")).is_file())
        if needed:return {"state":"await_subject_signoff","required":needed}
        for s,(_,folder) in accepted.items():
            ev=folder.parent/"signoff"
            if (folder/"publication.json").exists():continue
            if subject!="math" and not (folder/"independent-review.json").exists():
                invoke_ok(["review",folder,ev/"review.json"])
            if not (folder/"quality-audit.json").exists():
                args=["quality-audit",folder,ev/"audit.json"]
                if subject=="math":args.extend(["--blind-review",ev/"review.json"])
                invoke_ok(args)
            if subject=="math":invoke_ok(["math","publish",folder,"--student-review",ev/"review.json","--math-comparison",ev/"comparison.json"])
            else:invoke_ok(["publish",folder,ev/"visual.json"])
        return {"state":"published","plan_sha256":digest(schedule_file),
                "editions":{s:str(folder) for s,(_,folder) in accepted.items()}}
    return {"state":"rejected","round":3,"unresolved":sorted(active)}
