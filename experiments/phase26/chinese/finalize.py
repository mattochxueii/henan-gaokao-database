"""Build the teaching copy from the actual blind responses and the editor's reconciled rubric."""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from gaokao import digest,read_json,require
from analysis_db import fingerprint
from core import language_workflow,quality_audit,review_board
from core.language_render import export_docx
from forecast_store import write_new


def prepare(folder):
    score=review_board.replay(folder/"board")
    require(score["status"]=="eligible" and digest(folder/"paper.pdf")==score["pdf_sha256"],"须先通过本轮盲审")
    records=read_json(folder/"board"/f"round{score['round']}.json")["reports"]
    by_role={r["role"]:r["items"] for r in records}
    packet=read_json(folder/"blind-packet.json")
    verify=read_json(folder/"verification.json")
    explanations=read_json(HERE/"source/author-solutions.json")["items"]
    editorial=read_json(HERE/"source/quality-audit-form.json")
    reconciliation=read_json(HERE/"source/final-reconciliation.json")
    require(reconciliation["pdf_sha256"]==score["pdf_sha256"]
            and reconciliation["solver_sha256"]==fingerprint(by_role["solver"]),"须由编辑核对当前求解者答卷")
    editorial.update(reviewer="命题编辑与独立教研、排印逐题对照",paper_version=packet["paper_version"],
                     paper_pdf_sha256=score["pdf_sha256"])
    review={"paper_version":packet["paper_version"],"paper_pdf_sha256":score["pdf_sha256"],
            "reviewer":"独立求解席；编辑逐项核对等义表达及给分点",
            "input_scope":"student_materials_and_listening_only","items":[]}
    for q,x,blind,teacher,visual,row,expected in zip(packet["paper"]["questions"],explanations,
            by_role["solver"],by_role["pedagogy"],by_role["visual"],editorial["items"],verify["expected"],strict=True):
        n=q["number"]
        require({n}=={r["number"] for r in (x,blind,teacher,visual,row)},"题号错位")
        if q["kind"] in ("single_choice","recitation") or n==10:
            require(review_board.normalize_gap(blind["answer"])==review_board.normalize_gap(expected),"精确答案不符")
        else:
            require(str(n) in reconciliation["open_answers"],"缺少开放题逐题裁决")
        x.update(ambiguity=False,independent_answer_verbatim=blind["answer"],independent_reasoning=blind["reasoning"])
        if n==11:
            x["reasoning"]="‘以其言试之河’是按照其所言到河里尝试，故选D。A两处‘释’都有放下义；B处‘安得’是反问；C前一‘或’指有人，‘而或长烟一空’的‘或’指有时。"
            row["distractors"]["C"].update(unchanged="两句都有‘或’，均可译出不确定意味",distortion="把未定的人偷换为未定的时间",
                misconception="混同不定代词与时间副词",mechanism="第二句的‘有时’不能移用于作主语的第一个‘或’")
        review["items"].append(x)
        row["independent_comparison"]=teacher["comparison"]
        row["print_observation"]=visual["reasoning"]
    language_workflow.review(folder,review)
    result=quality_audit.submit(folder,editorial,review=review)
    require(result["status"]=="accepted",str(result["failures"]))
    for name in ("paper","solutions"):
        export_docx(folder/(name+".md"),folder/(name+".docx"))
    return result


if __name__=="__main__":
    prepare(HERE/"final")
