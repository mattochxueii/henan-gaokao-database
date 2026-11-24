"""Resumable host-driven production. The three inboxes are the optional provider boundary."""
from pathlib import Path
from forecast_store import write_new
from gaokao import read_json, require, digest
from core import review_board as board


def cycle(root,folder,inbox,previous=None,repair_slots=(),providers=None):
    """Render with simulate first. Resume after isolated reviewers deposit their independent replies."""
    inbox.mkdir(parents=True,exist_ok=True)
    state=board.evidence(root,folder)
    if (folder/"board").exists():
        result=board.replay(folder/"board")
        require(result["pdf_sha256"]==state["pdf_sha256"],"旧评分与当前学生卷不匹配")
    else:
        replies=[]
        missing=[]
        if state["preflight"]["passed"]:
            for role in board.ROLES:
                assignment=inbox/role
                if not assignment.exists():
                    board.export_blind(root,folder,role,assignment)
                require(digest(assignment/"student.pdf")==state["pdf_sha256"],"不能复用旧版本盲审邮箱")
                reply=assignment/"reply.json"
                if not reply.exists() and providers and role in providers:
                    write_new(reply,board.dispatch(root,folder,role,providers[role]))
                if reply.is_file():
                    report=read_json(reply)
                    require(report["role"]==role,"审稿件送入了错误邮箱")
                    replies.append(report)
                else:missing.append(role)
            if missing:return {"state":"await_isolated_readers","pending":missing,"pdf_sha256":state["pdf_sha256"]}
        result=board.record(root,folder,replies,previous,repair_slots)
    decision={"state":result["status"],"round":result["round"],"score":result["final_score"],
              "fatal_count":result["fatal_count"],"rewrite":result["rewrite"],"locked":result["locked"],
              "deductions":result["deductions"],"pdf_sha256":result["pdf_sha256"]}
    path=folder/"board"/"decision.json"
    if not path.exists():write_new(path,decision)
    else:require(read_json(path)==decision,"返工指令与评分不一致")
    return decision
