"""Verify both independent visual reports against the files, publish, then replay the certificate."""
import argparse
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/"scripts"))
import bootstrap  # noqa: F401
from forecast_store import write_new
from gaokao import digest, read_json, require
from pypdf import PdfReader
from core.review_board import replay
from core.science_workflow import publish, check_publication


def release(label, report_path):
    dest=HERE/label/"final"
    decision=replay(dest/"board")
    require(decision["status"]=="eligible","审稿未放行")
    reports=read_json(dest/"board"/f"round{decision['round']}.json")["reports"]
    printed=next(r for r in reports if r["role"]=="visual")
    appendix=read_json(report_path)
    packet=read_json(dest/"blind-packet.json")
    visual={"paper_version":packet["paper_version"],"passed":True,
            "reviewer":printed["identity"]+"（学生卷）；"+appendix["reviewer"]+"（解析）",
            "solutions_visual_report":appendix,"paper_visual_pages":printed["pages"]}
    for edition,sha,notes in (
            ("paper",printed["pdf_sha256"],[p["note"] for p in printed["pages"]]),
            ("solutions",appendix["sha256"],appendix["pages"])):
        pdf=dest/(edition+".pdf")
        require(digest(pdf)==sha and len(notes)==len(PdfReader(pdf).pages)
                and all(n.strip() for n in notes),"逐页视觉记录的页数、内容或版本不匹配")
        visual[edition+"_sha256"]=sha
        visual[edition+"_pages"]=len(notes)
        visual[edition+"_note"]=" ".join(f"第{i}页：{note}" for i,note in enumerate(notes,1))
    write_new(dest/"visual-check.json",visual)
    certificate=publish(dest,visual)
    check_publication(dest,certificate)
    return certificate["status"]


if __name__=="__main__":
    args=argparse.ArgumentParser()
    args.add_argument("label",choices=["A","B"])
    args.add_argument("solutions_visual",type=Path)
    options=args.parse_args()
    print(release(options.label,options.solutions_visual))
